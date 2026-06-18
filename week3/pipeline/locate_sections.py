# -*- coding: utf-8 -*-
"""
locate_sections.py - 章节定位脚本

读取 parse_pdf.py 输出的 txt 文件，使用正则表达式匹配
"股本演变"/"历史沿革"/"股本变化"等章节标题，标注起止页码。

用法:
    python locate_sections.py --input-dir ../outputs/logs --output-dir ../outputs/logs
"""

import argparse
import json
import logging
import os
import re
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    encoding="utf-8",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 章节标题正则模式
# ---------------------------------------------------------------------------

# 目标章节关键词（按优先级排列）
SECTION_KEYWORDS = [
    "股本演变",
    "股本变化",
    "股本变动",
    "注册资本变更",
    "股本及股权结构",
    "历史沿革",
    "发行人股本演变",
    "发行人历史沿革",
    "公司股本演变",
    "公司历史沿革",
]

# 构建正则: 匹配 "第X节 标题" 或 "X 标题" 或直接标题行
# 常见格式: "第三节 股本演变" / "三、股本演变" / "3.1 股本演变"
SECTION_PATTERNS = [
    # "第X节 股本演变"
    re.compile(
        r"第[一二三四五六七八九十百\d]+节\s*[{keywords}]".format(
            keywords="|".join(SECTION_KEYWORDS)
        ),
        re.IGNORECASE,
    ),
    # "X、股本演变" 或 "X. 股本演变"
    re.compile(
        r"[一二三四五六七八九十\d]+[、.．]\s*[{keywords}]".format(
            keywords="|".join(SECTION_KEYWORDS)
        ),
        re.IGNORECASE,
    ),
    # 纯标题行（整行匹配关键词）
    re.compile(
        r"^\s*[{keywords}]\s*$".format(
            keywords="|".join(SECTION_KEYWORDS)
        ),
        re.IGNORECASE | re.MULTILINE,
    ),
    # 带编号子标题: "3.1.1 xxx"
    re.compile(
        r"^\s*\d+(?:\.\d+)*\s*[{keywords}]".format(
            keywords="|".join(SECTION_KEYWORDS)
        ),
        re.IGNORECASE | re.MULTILINE,
    ),
]


# ---------------------------------------------------------------------------
# 页面解析
# ---------------------------------------------------------------------------

def parse_pages(txt_path):
    """解析 parse_pdf.py 输出的txt文件，返回页面列表。

    Returns:
        [{"page": int, "text": str}, ...]
    """
    pages = []
    current_page = None
    current_text = []

    with open(txt_path, "r", encoding="utf-8") as f:
        for line in f:
            # 匹配页码标记: [第X页]
            m = re.match(r"^\[第(\d+)页\]", line.strip())
            if m:
                if current_page is not None:
                    pages.append({
                        "page": current_page,
                        "text": "\n".join(current_text).strip(),
                    })
                current_page = int(m.group(1))
                current_text = []
            else:
                current_text.append(line)

    # 最后一页
    if current_page is not None:
        pages.append({
            "page": current_page,
            "text": "\n".join(current_text).strip(),
        })

    return pages


# ---------------------------------------------------------------------------
# 章节定位
# ---------------------------------------------------------------------------

def locate_sections(pages):
    """在页面列表中定位目标章节。

    Returns:
        [{
            "section_title": str,
            "keyword": str,
            "start_page": int,
            "end_page": int,
            "matched_line": str,
        }, ...]
    """
    sections = []
    found_sections = []  # [(page_index, title, keyword, matched_line)]

    for idx, page in enumerate(pages):
        for pattern in SECTION_PATTERNS:
            matches = pattern.finditer(page["text"])
            for m in matches:
                matched_line = m.group(0).strip()
                # 确定匹配到的关键词
                keyword = "unknown"
                for kw in SECTION_KEYWORDS:
                    if kw in matched_line:
                        keyword = kw
                        break
                found_sections.append((idx, matched_line, keyword, matched_line))

    # 确定每个章节的起止页码
    for i, (page_idx, title, keyword, matched_line) in enumerate(found_sections):
        start_page = pages[page_idx]["page"]
        # 终止页码: 下一章节的起始页 - 1，或文档末页
        if i + 1 < len(found_sections):
            end_page = pages[found_sections[i + 1][0]]["page"] - 1
        else:
            end_page = pages[-1]["page"]

        sections.append({
            "section_title": title,
            "keyword": keyword,
            "start_page": start_page,
            "end_page": end_page,
            "matched_line": matched_line,
        })

    return sections


# ---------------------------------------------------------------------------
# 输出
# ---------------------------------------------------------------------------

def write_sections(sections, output_dir, source_name):
    """将章节定位结果写入文件。"""
    os.makedirs(output_dir, exist_ok=True)

    # JSON格式输出
    json_filename = "{}_sections.json".format(
        re.sub(r'[\\/:*?"<>|]', '_', source_name)
    )
    json_path = os.path.join(output_dir, json_filename)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(sections, f, ensure_ascii=False, indent=2)

    # 同时生成可读的文本摘要
    txt_filename = "{}_sections.txt".format(
        re.sub(r'[\\/:*?"<>|]', '_', source_name)
    )
    txt_path = os.path.join(output_dir, txt_filename)
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("章节定位结果: {}\n".format(source_name))
        f.write("=" * 60 + "\n\n")
        if not sections:
            f.write("未找到任何目标章节\n")
        for sec in sections:
            f.write("章节: {}\n".format(sec["section_title"]))
            f.write("  关键词: {}\n".format(sec["keyword"]))
            f.write("  起始页: 第{}页\n".format(sec["start_page"]))
            f.write("  终止页: 第{}页\n".format(sec["end_page"]))
            f.write("  匹配行: {}\n".format(sec["matched_line"]))
            f.write("-" * 40 + "\n")

    logger.info("章节定位结果已写入: %s", json_path)
    return json_path


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="章节定位 - 在解析后的文本中定位股本演变/历史沿革等章节"
    )
    parser.add_argument(
        "--input-dir",
        type=str,
        default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "outputs", "logs"),
        help="parse_pdf.py输出的txt文件目录 (默认: ../outputs/logs)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "outputs", "logs"),
        help="章节定位结果输出目录 (默认: ../outputs/logs)",
    )
    args = parser.parse_args()

    logger.info("输入目录: %s", os.path.abspath(args.input_dir))
    logger.info("输出目录: %s", os.path.abspath(args.output_dir))

    # 查找所有 _parsed.txt 文件
    txt_files = sorted([
        f for f in os.listdir(args.input_dir)
        if f.endswith("_parsed.txt")
    ])

    if not txt_files:
        logger.warning("未找到任何 _parsed.txt 文件")
        sys.exit(0)

    logger.info("找到 %d 个解析文件", len(txt_files))

    for txt_file in txt_files:
        txt_path = os.path.join(args.input_dir, txt_file)
        source_name = txt_file.replace("_parsed.txt", "")
        logger.info("正在处理: %s", source_name)

        try:
            pages = parse_pages(txt_path)
            logger.info("  共 %d 页", len(pages))

            sections = locate_sections(pages)
            logger.info("  定位到 %d 个目标章节", len(sections))

            for sec in sections:
                logger.info(
                    "  -> %s (第%d-%d页)",
                    sec["section_title"], sec["start_page"], sec["end_page"],
                )

            write_sections(sections, args.output_dir, source_name)

        except Exception as e:
            logger.error("处理失败 %s: %s", txt_file, e)

    logger.info("全部完成!")


if __name__ == "__main__":
    main()