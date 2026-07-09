# -*- coding: utf-8 -*-
"""
extract_candidates_rules.py — 基于规则的候选事件提取

核心理念:
  先让代码做第一轮过滤，识别可能的增资/转让/快照段落，
  再让 LLM 做精细提取。代码处理能做的（模式匹配），
  LLM 处理代码做不了的（语义理解）。

用法:
    python extract_candidates_rules.py --sections-dir ../outputs/sections --output-dir ../outputs/candidates
"""

import argparse
import json
import logging
import os
import re
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    encoding="utf-8",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 规则模式
# ---------------------------------------------------------------------------

# 金额/股数表达式
AMOUNT_PATTERN = re.compile(
    r"(\d[\d,.]*)\s*(万元|亿元|元|万美元|万港元|万股|股|万)",
    re.IGNORECASE,
)

# 日期表达式 (中文: XXXX年XX月XX日)
DATE_CN_PATTERN = re.compile(
    r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})?\s*日?",
)

# 增资关键词
CAPITAL_INCREASE_KW = [
    "增资", "新增出资", "增加注册资本", "新增注册资本",
    "认购", "认缴新增", "追加投资", "新增股本",
    "资本公积转增", "转增股本",
]

# 股权转让关键词
TRANSFER_KW = [
    "股权转让", "股份转让", "转让股权", "转让股份",
    "受让", "出让", "转让给",
]

# 减资关键词
CAPITAL_DECREASE_KW = ["减资", "减少注册资本", "回购注销"]

# 设立关键词
FOUNDING_KW = ["设立", "发起人", "公司成立", "创始出资", "发起设立"]

# 吸收合并关键词
MERGER_KW = ["吸收合并", "合并", "被吸收"]

# 股东名称模式 (XX有限公司/合伙企业/个人名)
SHAREHOLDER_PATTERN = re.compile(
    r"([一-龥（）()]{2,20}(?:有限公司|有限责任公司|股份公司|合伙企业|有限合伙|"
    r"投资管理|资产管理|投资中心|创投|基金|资本|集团|控股))"
)

# 持股比例模式
SHARE_PCT_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)\s*%|(\d+(?:\.\d+)?)\s*％"
)


# ---------------------------------------------------------------------------
# 候选事件识别
# ---------------------------------------------------------------------------

def identify_candidates(section_text, section_title=""):
    """识别文本中的候选事件。

    Returns:
        [{
            "type": "candidate",
            "candidate_type": "capital_increase" | "transfer" | "decrease" |
                              "founding" | "merger" | "snapshot" | "other",
            "text": str,          # 候选文本片段
            "keywords_found": [], # 匹配到的关键词
            "amounts_found": [],  # 提取到的金额/数量
            "dates_found": [],    # 提取到的日期
            "shareholders_found": [],  # 提取到的股东
            "pcts_found": [],     # 提取到的持股比例
            "section": str,       # 来源章节
        }, ...]
    """
    candidates = []

    # 按空行分割成段落
    paragraphs = re.split(r"\n\s*\n", section_text)
    # 如果段落太长，按句子分割
    refined = []
    for para in paragraphs:
        if len(para) > 1000:
            sentences = re.split(r"(?<=[。；;])", para)
            refined.extend(s for s in sentences if s.strip())
        else:
            refined.append(para)

    for para in refined:
        para = para.strip()
        if len(para) < 30:  # 跳过过短的段落
            continue

        kw_found = []
        candidate_type = None

        # 检测增资
        for kw in CAPITAL_INCREASE_KW:
            if kw in para:
                kw_found.append(kw)
                candidate_type = "capital_increase"

        # 检测股权转让
        for kw in TRANSFER_KW:
            if kw in para:
                kw_found.append(kw)
                if candidate_type != "capital_increase":
                    candidate_type = "transfer"
                else:
                    candidate_type = "mixed"  # 同时有增资和转让

        # 检测减资
        for kw in CAPITAL_DECREASE_KW:
            if kw in para:
                kw_found.append(kw)
                if not candidate_type:
                    candidate_type = "decrease"

        # 检测设立
        for kw in FOUNDING_KW:
            if kw in para:
                kw_found.append(kw)
                if not candidate_type:
                    candidate_type = "founding"

        # 检测吸收合并
        for kw in MERGER_KW:
            if kw in para:
                kw_found.append(kw)
                if not candidate_type:
                    candidate_type = "merger"

        # 检测快照（股权结构表）
        if re.search(r"(?:持股比[例列]|股权结构|股东名[称册]|出资比[例列])", para):
            if not candidate_type:
                candidate_type = "snapshot"

        # 即使没有明确类型，如果包含金额+日期也标记
        if not candidate_type and len(para) > 80:
            # 检查是否包含金额 + 股东信息
            has_amount = bool(AMOUNT_PATTERN.search(para))
            has_date = bool(DATE_CN_PATTERN.search(para))
            has_shareholder = bool(SHAREHOLDER_PATTERN.search(para))
            if has_amount and has_date and has_shareholder:
                candidate_type = "other"

        if not candidate_type:
            continue

        # 提取金额
        amounts = []
        for m in AMOUNT_PATTERN.finditer(para):
            value = float(m.group(1).replace(",", ""))
            unit = m.group(2)
            amounts.append({"value": value, "unit": unit, "raw": m.group(0)})

        # 提取日期
        dates = []
        for m in DATE_CN_PATTERN.finditer(para):
            year = int(m.group(1))
            month = int(m.group(2))
            day = int(m.group(3)) if m.group(3) else None
            dates.append({
                "year": year, "month": month, "day": day,
                "raw": m.group(0),
            })

        # 提取股东
        shareholders = [m.group(1) for m in SHAREHOLDER_PATTERN.finditer(para)]

        # 提取持股比例
        pcts = []
        for m in SHARE_PCT_PATTERN.finditer(para):
            pct = float(m.group(1) or m.group(2))
            pcts.append(pct)

        candidates.append({
            "candidate_type": candidate_type,
            "text": para,
            "keywords_found": list(set(kw_found)),
            "amounts_found": amounts[:10],   # 最多10个金额
            "dates_found": dates[:5],        # 最多5个日期
            "shareholders_found": list(set(shareholders))[:10],
            "pcts_found": pcts[:20],
            "section": section_title,
            "text_length": len(para),
        })

    return candidates


# ---------------------------------------------------------------------------
# 主逻辑
# ---------------------------------------------------------------------------

def process_sections(sections_json_path):
    """处理单个 sections JSON 文件，提取候选事件"""
    with open(sections_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    all_candidates = []
    source = data.get("source", "")

    for section in data.get("sections", []):
        if section.get("group") != "core":
            continue  # 只处理核心章节

        candidates = identify_candidates(
            section.get("text", ""),
            section.get("title", ""),
        )
        logger.info("  [%s] %s → %d 候选事件",
                    section.get("title", "")[:40],
                    section.get("group", ""),
                    len(candidates))
        all_candidates.extend(candidates)

    # 统计
    type_counts = {}
    for c in all_candidates:
        t = c["candidate_type"]
        type_counts[t] = type_counts.get(t, 0) + 1

    logger.info("%s: 共 %d 个候选事件, 分布: %s",
                source, len(all_candidates), type_counts)

    return {
        "source": source,
        "total_candidates": len(all_candidates),
        "type_distribution": type_counts,
        "candidates": all_candidates,
    }


def main():
    parser = argparse.ArgumentParser(description="基于规则的候选事件提取")
    parser.add_argument("--sections-dir", type=str, required=True)
    parser.add_argument("--output-dir", type=str,
                        default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                            "..", "outputs", "candidates"))
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    json_files = sorted([
        f for f in os.listdir(args.sections_dir)
        if f.endswith("_sections.json")
    ])

    if not json_files:
        logger.warning("未找到 sections JSON 文件")
        return

    for json_file in json_files:
        path = os.path.join(args.sections_dir, json_file)
        logger.info("处理: %s", json_file)
        try:
            result = process_sections(path)
            out_path = os.path.join(
                args.output_dir,
                json_file.replace("_sections.json", "_candidates.json")
            )
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            logger.info("  → %s", out_path)
        except Exception as e:
            logger.error("处理失败: %s", e)


if __name__ == "__main__":
    main()
