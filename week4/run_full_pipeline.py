# -*- coding: utf-8 -*-
"""
run_full_pipeline.py — 一键执行完整 pipeline

流程:
  1. PDF 逐页提取文本 (PyMuPDF，快速，低内存)
  2. 正则定位章节 + 用代码找到关键段落
  3. 规则提取候选事件 (金额/日期/股东/比例)
  4. 输出结构化 JSON

相比 Week3 的核心改进:
  - 代码做章节定位和候选过滤（不再全量给 LLM）
  - 保留原文 raw_value + raw_unit（支持复核）
  - 标记 unit_issue（黄山谷捷 78/780 问题）

用法:
    python run_full_pipeline.py --pdf "path/to/301581_黄山谷捷.pdf"
"""

import argparse
import json
import logging
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

# 尝试导入 pdfplumber，失败则用 PyMuPDF
try:
    import pdfplumber
    PDF_BACKEND = "pdfplumber"
except ImportError:
    import fitz
    PDF_BACKEND = "pymupdf"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    encoding="utf-8",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 章节关键词配置
# ---------------------------------------------------------------------------

CHAPTER_KEYWORDS = {
    "核心章节": [
        "发行人基本情况",             # 招股书第四节，含历史沿革
        "发行人的设立情况",           # 设立情况子章节
        "报告期内的股本和股东变化",   # 股本变化时间线
        "股本和股东变化情况",
        "历史沿革", "股本演变", "股本变化", "股本变动",
        "发行人股本演变", "发行人历史沿革", "公司历史沿革",
        "股本及股权结构", "股本形成", "发行人股本形成",
        "注册资本变更", "历次增资", "历次股权变更",
        "第一次股权转让", "第二次股权转让",  # 具体事件标题
        "第一次增资", "第二次增资",
        "吸收合并", "整体变更",
        "设立情况", "有限公司设立",
        "发行人股本情况", "发行人设立以来股本演变",
    ],
    "股权结构": [
        "发行前股东", "发行前股权结构", "发行前股本结构",
        "股东结构", "前十名股东", "持股情况", "股东情况",
        "发行人股权结构", "股权结构如下", "股权结构图",
    ],
    "关联信息": [
        "发起人", "控股股东", "实际控制人",
        "员工持股", "股权激励", "持股平台",
        "对赌协议", "股东特殊权利",
    ],
}


# ---------------------------------------------------------------------------
# PDF 文本提取
# ---------------------------------------------------------------------------

def extract_text_pdfplumber(pdf_path):
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            text = re.sub(r"\s+", " ", text).strip()
            pages.append({"page": i, "text": text})
    return pages


def extract_text_pymupdf(pdf_path):
    pages = []
    doc = fitz.open(pdf_path)
    for i in range(len(doc)):
        text = doc[i].get_text("text")
        text = re.sub(r"\s+", " ", text).strip()
        pages.append({"page": i + 1, "text": text})
    doc.close()
    return pages


# ---------------------------------------------------------------------------
# 章节定位（核心：代码做定位，不是 LLM）
# ---------------------------------------------------------------------------

def locate_chapters(pages):
    """在页面中定位目标章节。

    返回: [
        {"chapter_group": str, "chapter_title": str,
         "start_page": int, "end_page": int, "pages_text": str}
    ]
    """
    # Step 1: 逐页扫描，找章节标题
    found = []
    for p in pages:
        for group_name, keywords in CHAPTER_KEYWORDS.items():
            for kw in keywords:
                if kw in p["text"]:
                    found.append({
                        "group": group_name,
                        "keyword": kw,
                        "page": p["page"],
                        "text_snippet": p["text"][:200],
                    })
                    break
            if found and found[-1]["page"] == p["page"]:
                break  # 每页只记一个匹配

    logger.info("找到 %d 个章节标题候选", len(found))

    # Step 2: 合并相邻的同组页面
    chapters = []
    current = None
    for f in found:
        if current is None:
            current = {
                "chapter_group": f["group"],
                "chapter_title": f["keyword"],
                "start_page": f["page"],
                "end_page": f["page"],
                "pages": [f["page"]],
            }
        elif (f["group"] == current["chapter_group"]
              and f["page"] - current["end_page"] <= 5):
            current["end_page"] = f["page"]
            current["pages"].append(f["page"])
            if f["keyword"] not in current["chapter_title"]:
                current["chapter_title"] += " / " + f["keyword"]
        else:
            # 扩展范围（前2页后10页）
            start = max(1, current["start_page"] - 2)
            end = min(len(pages), current["end_page"] + 10)
            current["start_page"] = start
            current["end_page"] = end
            chapters.append(current)

            current = {
                "chapter_group": f["group"],
                "chapter_title": f["keyword"],
                "start_page": f["page"],
                "end_page": f["page"],
                "pages": [f["page"]],
            }

    # 最后一个
    if current:
        start = max(1, current["start_page"] - 2)
        end = min(len(pages), current["end_page"] + 10)
        current["start_page"] = start
        current["end_page"] = end
        chapters.append(current)

    # Step 3: 提取每章的文本
    for ch in chapters:
        ch["pages_text"] = "\n\n".join(
            f"[第{p['page']}页]\n{p['text']}"
            for p in pages
            if ch["start_page"] <= p["page"] <= ch["end_page"]
        )

    logger.info("合并为 %d 个章节块", len(chapters))
    for ch in chapters:
        logger.info("  [%s] %s (第%d-%d页, %d字)",
                    ch["chapter_group"],
                    ch["chapter_title"][:50],
                    ch["start_page"], ch["end_page"],
                    len(ch["pages_text"]))

    return chapters


# ---------------------------------------------------------------------------
# 候选事件提取（代码做第一轮过滤）
# ---------------------------------------------------------------------------

AMOUNT_RE = re.compile(
    r"(\d[\d,.]*)\s*(万元|亿元|元|万美元|万港元|万股|股)",
)
DATE_RE = re.compile(r"(\d{4})\s*年\s*(\d{1,2})\s*月(?:\s*(\d{1,2})\s*日?)?")
PCT_RE = re.compile(r"(\d+\.?\d*)\s*[%％]")
SHAREHOLDER_RE = re.compile(
    r"([一-龥（）()\w]{2,30}(?:有限公司|有限责任公司|股份公司|"
    r"合伙企业|有限合伙|投资管理|资产管理|投资中心|"
    r"创投|基金|资本|集团|控股|企业|公司))"
)


def extract_candidates_from_text(text, chapter_info):
    """从指定章节文本中提取候选事件段落。"""
    # 按句子/段落分割
    blocks = re.split(r"\n\s*\n|(?<=[。；])", text)

    candidates = []
    for block in blocks:
        block = block.strip()
        if len(block) < 40:
            continue

        # 判断事件类型
        event_type = None
        keywords = []

        if re.search(r"增资|新增出资|增加注册资本|认购新增|新增股本", block):
            event_type = "增资"
            keywords.append("增资")
        if re.search(r"股权转让|股份转让|转让股权|转让给|受让|出让", block):
            if event_type:
                keywords.append("转让")
            else:
                event_type = "股权转让"
                keywords.append("转让")
        if re.search(r"减资|减少注册资本|回购注销", block):
            event_type = "减资" if not event_type else event_type
        if re.search(r"设立|发起设立|公司成立|创始出资", block):
            if not event_type:
                event_type = "设立出资"
        if re.search(r"吸收合并", block):
            if not event_type:
                event_type = "吸收合并"

        # 提取结构化信息
        amounts = []
        for m in AMOUNT_RE.finditer(block):
            amounts.append({
                "value": float(m.group(1).replace(",", "")),
                "unit": m.group(2),
                "raw": m.group(0),
            })

        dates = [m.group(0) for m in DATE_RE.finditer(block)]
        pcts = [float(m.group(1)) for m in PCT_RE.finditer(block)]
        shareholders = [m.group(1) for m in SHAREHOLDER_RE.finditer(block)]

        # 有金额+日期+股东的高质量候选
        quality = "low"
        if amounts and dates:
            quality = "medium"
        if amounts and dates and shareholders:
            quality = "high"

        if event_type or quality in ("medium", "high"):
            candidates.append({
                "candidate_type": event_type or "未分类",
                "quality": quality,
                "text": block,
                "keywords": keywords,
                "amounts": amounts,
                "dates": dates,
                "pcts": pcts,
                "shareholders": list(set(shareholders)),
                "chapter": chapter_info.get("chapter_title", ""),
                "pages": chapter_info.get("start_page", 0),
            })

    return candidates


# ---------------------------------------------------------------------------
# 黄山谷捷专项检测
# ---------------------------------------------------------------------------

def check_huangshan_issues(candidates):
    """针对黄山谷捷的已知问题做专项检查"""
    issues = []
    for c in candidates:
        text = c["text"]
        # 检查 78/780 单位混淆
        if re.search(r"78\s*万元?(?:出资|注册)", text):
            issues.append({
                "type": "unit_confusion",
                "detail": "78万元出资额转让 —— 需确认是78还是780",
                "candidate_text": text[:200],
            })
        # 检查 11/110 单位混淆
        if re.search(r"11\s*万元?(?:出资|注册|转让)", text):
            issues.append({
                "type": "unit_confusion",
                "detail": "11/110万元单位口径 —— 需人工复核",
                "candidate_text": text[:200],
            })
        # 检查吸收合并
        if "吸收合并" in text:
            issues.append({
                "type": "complex_event",
                "detail": "涉及吸收合并事件，需关注股权变动链条",
                "candidate_text": text[:200],
            })
    return issues


# ---------------------------------------------------------------------------
# 输出
# ---------------------------------------------------------------------------

def save_results(chapters, all_candidates, issues, output_dir, pdf_name):
    """保存所有提取结果"""
    os.makedirs(output_dir, exist_ok=True)

    # 1. 章节定位结果
    chapters_out = {
        "source": pdf_name,
        "chapter_count": len(chapters),
        "chapters": [
            {
                "group": ch["chapter_group"],
                "title": ch["chapter_title"],
                "start_page": ch["start_page"],
                "end_page": ch["end_page"],
                "text_length": len(ch["pages_text"]),
            }
            for ch in chapters
        ],
    }
    with open(os.path.join(output_dir, f"{pdf_name}_chapters.json"),
              "w", encoding="utf-8") as f:
        json.dump(chapters_out, f, ensure_ascii=False, indent=2)

    # 2. 候选事件
    candidates_out = {
        "source": pdf_name,
        "total": len(all_candidates),
        "by_type": {},
        "by_quality": {},
        "candidates": all_candidates,
    }
    for c in all_candidates:
        t = c["candidate_type"]
        q = c["quality"]
        candidates_out["by_type"][t] = candidates_out["by_type"].get(t, 0) + 1
        candidates_out["by_quality"][q] = candidates_out["by_quality"].get(q, 0) + 1

    with open(os.path.join(output_dir, f"{pdf_name}_candidates.json"),
              "w", encoding="utf-8") as f:
        json.dump(candidates_out, f, ensure_ascii=False, indent=2)

    # 3. 问题标记
    with open(os.path.join(output_dir, f"{pdf_name}_issues.json"),
              "w", encoding="utf-8") as f:
        json.dump({"source": pdf_name, "issues": issues},
                  f, ensure_ascii=False, indent=2)

    # 4. 核心章节文本 (给 LLM 用的、经过代码筛选的输入)
    core_text = "\n\n".join(
        f"## {ch['chapter_title']}\n({ch['start_page']}-{ch['end_page']}页)\n\n{ch['pages_text']}"
        for ch in chapters
        if ch["chapter_group"] in ("核心章节", "股权结构")
    )
    with open(os.path.join(output_dir, f"{pdf_name}_core_sections.txt"),
              "w", encoding="utf-8") as f:
        f.write(core_text)

    # 5. 摘要
    logger.info("=" * 60)
    logger.info("提取结果摘要: %s", pdf_name)
    logger.info("  章节数: %d", len(chapters))
    logger.info("  候选事件: %d", len(all_candidates))
    logger.info("  类型分布: %s",
                ", ".join(f"{k}={v}" for k, v in candidates_out["by_type"].items()))
    logger.info("  质量分布: %s",
                ", ".join(f"{k}={v}" for k, v in candidates_out["by_quality"].items()))
    logger.info("  专项问题: %d 个", len(issues))
    for iss in issues:
        logger.info("    [%s] %s", iss["type"], iss["detail"])
    logger.info("  输出目录: %s", output_dir)
    logger.info("=" * 60)


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="一键执行: PDF → 章节定位 → 候选提取"
    )
    parser.add_argument("--pdf", type=str, required=True,
                        help="PDF 文件路径")
    parser.add_argument("--output-dir", type=str,
                        help="输出目录")
    parser.add_argument("--company-name", type=str, default=None,
                        help="公司全称（可选）")
    parser.add_argument("--stock-code", type=str, default=None,
                        help="股票代码（可选）")
    args = parser.parse_args()

    pdf_name = Path(args.pdf).stem
    if not args.output_dir:
        args.output_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "outputs", "pipeline_results", pdf_name
        )

    logger.info("PDF: %s", args.pdf)
    logger.info("输出: %s", args.output_dir)

    # Step 1: 提取文本
    logger.info("--- Step 1: PDF 文本提取 ---")
    if PDF_BACKEND == "pdfplumber":
        pages = extract_text_pdfplumber(args.pdf)
    else:
        pages = extract_text_pymupdf(args.pdf)
    logger.info("共 %d 页", len(pages))

    # Step 2: 代码定位章节
    logger.info("--- Step 2: 代码定位章节 ---")
    chapters = locate_chapters(pages)

    # Step 3: 候选事件提取
    logger.info("--- Step 3: 候选事件提取 ---")
    all_candidates = []
    for ch in chapters:
        candidates = extract_candidates_from_text(ch["pages_text"], ch)
        all_candidates.extend(candidates)
    logger.info("共提取 %d 个候选事件", len(all_candidates))

    # Step 4: 专项问题检测
    logger.info("--- Step 4: 专项问题检测 ---")
    issues = check_huangshan_issues(all_candidates)

    # Step 5: 保存
    logger.info("--- Step 5: 保存结果 ---")
    save_results(chapters, all_candidates, issues, args.output_dir, pdf_name)


if __name__ == "__main__":
    main()
