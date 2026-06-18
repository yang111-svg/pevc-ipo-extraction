# -*- coding: utf-8 -*-
"""
extract_candidates.py - 候选事件包生成脚本

读取 locate_sections.py 输出的 sections JSON 文件，
结合原始 parsed txt 文本，按小标题或段落边界将章节内容
切块为候选事件文本块。

用法:
    python extract_candidates.py --input-dir ../outputs/logs --output-dir ../outputs/raw_llm_outputs
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
# 小标题/段落分割正则
# ---------------------------------------------------------------------------

# 匹配子标题行（常见格式）
SUBSECTION_PATTERNS = [
    # "1. xxx" / "1、xxx"
    re.compile(r"^\s*(\d+)[、.．]\s*.+", re.MULTILINE),
    # "（一）xxx" / "(1) xxx"
    re.compile(r"^\s*[（(]\s*[一二三四五六七八九十\d]+\s*[）)]\s*.+", re.MULTILINE),
    # "第X次 xxx"
    re.compile(r"^\s*第[一二三四五六七八九十\d]+\s*次\s*.+", re.MULTILINE),
    # "xxxx年xx月" 开头的段落（时间标记）
    re.compile(r"^\s*\d{4}\s*年\s*\d{1,2}\s*月\s*.+", re.MULTILINE),
]


# ---------------------------------------------------------------------------
# 文本解析
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

    if current_page is not None:
        pages.append({
            "page": current_page,
            "text": "\n".join(current_text).strip(),
        })

    return pages


def extract_section_text(pages, start_page, end_page):
    """提取指定页码范围内的文本。"""
    texts = []
    for page in pages:
        if start_page <= page["page"] <= end_page:
            texts.append(page["text"])
    return "\n".join(texts)


# ---------------------------------------------------------------------------
# 候选事件切块
# ---------------------------------------------------------------------------

def split_into_candidates(section_text, section_title, start_page):
    """将章节文本按小标题或段落边界切块为候选事件。

    策略:
    1. 先尝试按子标题分割
    2. 若子标题分割结果为空或块过大，则按段落分割
    3. 过滤过短的块（少于20字）

    Returns:
        [{"index": int, "text": str, "section": str, "source_page": int}, ...]
    """
    candidates = []

    # 策略1: 按子标题分割
    split_points = []
    for pattern in SUBSECTION_PATTERNS:
        for m in pattern.finditer(section_text):
            split_points.append((m.start(), m.end()))

    # 去重并排序
    split_points = sorted(set(split_points), key=lambda x: x[0])

    if split_points:
        # 按分割点切块
        prev_end = 0
        for start, end in split_points:
            if start > prev_end:
                chunk = section_text[prev_end:start].strip()
                if len(chunk) >= 20:
                    candidates.append(chunk)
            prev_end = start

        # 最后一个块
        last_chunk = section_text[split_points[-1][1]:].strip()
        if len(last_chunk) >= 20:
            candidates.append(last_chunk)
    else:
        # 策略2: 按段落（换行）分割
        paragraphs = re.split(r"\n+", section_text)
        for para in paragraphs:
            para = para.strip()
            if len(para) >= 20:
                candidates.append(para)

    # 如果仍然没有候选，把整个章节作为一个候选
    if not candidates:
        candidates.append(section_text.strip())

    # 构造结果
    result = []
    for i, text in enumerate(candidates, start=1):
        result.append({
            "index": i,
            "text": text,
            "section": section_title,
            "source_page": start_page,
        })

    return result


# ---------------------------------------------------------------------------
# 输出
# ---------------------------------------------------------------------------

def write_candidates(candidates, output_dir, source_name):
    """将候选事件写入JSON文件。"""
    os.makedirs(output_dir, exist_ok=True)

    filename = "{}_candidates.json".format(
        re.sub(r'[\\/:*?"<>|]', '_', source_name)
    )
    output_path = os.path.join(output_dir, filename)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(candidates, f, ensure_ascii=False, indent=2)

    logger.info("  候选事件已写入: %s (%d 条)", output_path, len(candidates))
    return output_path


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="候选事件包生成 - 将章节内容切块为候选事件文本"
    )
    parser.add_argument(
        "--input-dir",
        type=str,
        default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "outputs", "logs"),
        help="sections文件和parsed txt文件所在目录 (默认: ../outputs/logs)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "outputs", "raw_llm_outputs"),
        help="候选事件输出目录 (默认: ../outputs/raw_llm_outputs)",
    )
    args = parser.parse_args()

    logger.info("输入目录: %s", os.path.abspath(args.input_dir))
    logger.info("输出目录: %s", os.path.abspath(args.output_dir))

    # 查找所有 _sections.json 文件
    section_files = sorted([
        f for f in os.listdir(args.input_dir)
        if f.endswith("_sections.json")
    ])

    if not section_files:
        logger.warning("未找到任何 _sections.json 文件")
        sys.exit(0)

    logger.info("找到 %d 个sections文件", len(section_files))

    for sec_file in section_files:
        source_name = sec_file.replace("_sections.json", "")
        logger.info("正在处理: %s", source_name)

        try:
            # 读取章节定位结果
            sec_path = os.path.join(args.input_dir, sec_file)
            with open(sec_path, "r", encoding="utf-8") as f:
                sections = json.load(f)

            if not sections:
                logger.info("  无目标章节，跳过")
                continue

            # 读取对应的 parsed txt 文件
            txt_file = "{}_parsed.txt".format(source_name)
            txt_path = os.path.join(args.input_dir, txt_file)
            if not os.path.isfile(txt_path):
                logger.warning("  未找到对应的解析文件: %s", txt_file)
                continue

            pages = parse_pages(txt_path)

            # 对每个章节生成候选事件
            all_candidates = []
            for sec in sections:
                section_text = extract_section_text(
                    pages, sec["start_page"], sec["end_page"]
                )
                candidates = split_into_candidates(
                    section_text, sec["section_title"], sec["start_page"]
                )
                all_candidates.extend(candidates)

            logger.info("  共生成 %d 条候选事件", len(all_candidates))
            write_candidates(all_candidates, args.output_dir, source_name)

        except Exception as e:
            logger.error("处理失败 %s: %s", sec_file, e)

    logger.info("全部完成!")


if __name__ == "__main__":
    main()