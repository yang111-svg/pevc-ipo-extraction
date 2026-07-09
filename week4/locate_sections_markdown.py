# -*- coding: utf-8 -*-
"""
locate_sections_markdown.py — 基于 MinerU Markdown 输出的精确章节定位

核心理念 (老师建议):
  让代码去章节定位，而不是把全文塞给 LLM。
  利用 MinerU 输出的 Markdown 标题层级（# ## ###）精确定位目标章节，
  只提取相关文本块，大幅减少 LLM 输入噪声。

相比 locate_sections.py 的改进:
  - 利用 Markdown 标题层级结构 (不是 regex 猜标题)
  - 支持多级标题树: 第四节 > 一、历史沿革 > 1. 设立情况
  - 输出结构化 JSON: {"section": {..., "paragraphs": [...], "tables": [...]}}
  - Table-aware: 保留 MinerU 解析出的表格数据
  - 支持按关键词 + 标题层级组合过滤

用法:
    python locate_sections_markdown.py --md-dir ../outputs/mineru_md --output-dir ../outputs/sections
"""

import argparse
import json
import logging
import os
import re
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    encoding="utf-8",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 目标章节配置
# ---------------------------------------------------------------------------

# 目标章节关键词及其优先级 (数字越小越优先)
TARGET_CHAPTERS = [
    # (关键词列表, 最低标题层级, 最高标题层级, 章节标签)
    # H1: 中国证监会格式准则中的大章
    (["历史沿革", "发行人历史沿革", "公司历史沿革",
      "股本演变", "股本及股权结构", "发行人股本演变",
      "股本形成", "发行人股本形成", "发行人股本情况",
      "设立情况", "改制情况", "公司设立", "股份公司设立"], 1, 3, "core"),

    # H2: 次级章节
    (["历次增资", "历次股权变更", "历次出资",
      "股权转让", "股权变动", "股份转让",
      "注册资本变更", "注册资本变化",
      "整体变更", "股份制改造"], 1, 3, "core"),

    # 发行前股权结构
    (["发行前股东", "发行前股权结构", "发行前股本",
      "股东结构", "前十名股东", "持股情况"], 1, 4, "equity_structure"),

    # 发起人/主要股东
    (["发起人", "主要股东", "控股股东", "实际控制人"], 1, 4, "shareholders"),

    # 员工持股/股权激励
    (["员工持股", "股权激励", "持股平台", "合伙人"], 1, 4, "esop"),

    # PEVC 相关
    (["私募", "投资基金", "创投", "基金入股",
      "外部投资者", "机构投资者", "战略投资者"], 1, 4, "pevc"),
]

# 需要排除的章节 (非股本变化相关内容)
EXCLUDE_KEYWORDS = [
    "风险因素", "风险提示", "重大事项",
    "业务与技术", "业务发展", "主营业务",
    "财务数据", "财务报表", "会计信息",
    "管理层讨论", "经营情况",
    "募集资金", "募集资金运用",
    "公司治理", "董事", "监事", "高管",
    "关联交易", "同业竞争",
    "备查文件", "声明", "释义",
]


# ---------------------------------------------------------------------------
# Markdown 解析
# ---------------------------------------------------------------------------

def parse_markdown_structure(md_path):
    """解析 MinerU 输出的 Markdown 文件，返回结构化文本块列表。

    MinerU 输出的 Markdown 特点:
      - ## 通常对应大章节标题
      - ### 对应子标题
      - #### 对应细目
      - 表格以 Markdown table 格式出现 (| col1 | col2 |)
      - 段落之间以空行分隔

    Returns:
        [{
            "type": "heading" | "paragraph" | "table" | "page_break",
            "level": int,          # 仅 heading: 1-6
            "text": str,           # 标题文本或段落文本
            "data": [...]          # 仅 table: 行数据
            "line_start": int,     # 在文件中的起始行号
            "line_end": int,       # 终止行号
        }, ...]
    """
    blocks = []
    with open(md_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    i = 0
    while i < len(lines):
        line = lines[i].rstrip("\n")

        # 标题: # Heading / ## Heading
        heading_match = re.match(r"^(#{1,6})\s+(.+)", line)
        if heading_match:
            level = len(heading_match.group(1))
            text = heading_match.group(2).strip()
            blocks.append({
                "type": "heading",
                "level": level,
                "text": text,
                "line_start": i,
                "line_end": i,
            })
            i += 1
            continue

        # 表格: | col1 | col2 |
        if line.strip().startswith("|") and line.strip().endswith("|"):
            table_rows = []
            table_start = i
            while i < len(lines) and lines[i].strip().startswith("|"):
                row_text = lines[i].strip()
                # 跳过分隔行 (| --- | --- |)
                if not re.match(r"^\|[\s\-:]+\|", row_text):
                    cells = [c.strip() for c in row_text.split("|")[1:-1]]
                    table_rows.append(cells)
                i += 1
            blocks.append({
                "type": "table",
                "data": table_rows,
                "line_start": table_start,
                "line_end": i - 1,
            })
            continue

        # 空行：跳过
        if not line.strip():
            i += 1
            continue

        # 普通段落
        para_start = i
        para_lines = [line]
        i += 1
        while i < len(lines):
            next_line = lines[i].rstrip("\n")
            if not next_line.strip():
                i += 1
                break
            if next_line.strip().startswith("|") and next_line.strip().endswith("|"):
                break
            if re.match(r"^(#{1,6})\s+", next_line):
                break
            para_lines.append(next_line)
            i += 1

        blocks.append({
            "type": "paragraph",
            "text": "\n".join(para_lines).strip(),
            "line_start": para_start,
            "line_end": i - 1,
        })

    return blocks


def build_heading_tree(blocks):
    """构建标题层级树。

    Returns:
        [(heading_block, children_blocks), ...]
        其中 children_blocks 包括该标题下的所有子块
    """
    tree = []
    stack = []  # [(level, heading, children)]

    for block in blocks:
        if block["type"] == "heading":
            # 弹出所有层级 >= 当前标题的节点
            while stack and stack[-1][0] >= block["level"]:
                level, heading, children = stack.pop()
                if stack:
                    stack[-1][2].append((heading, children))
                else:
                    tree.append((heading, children))
            stack.append((block["level"], block, []))
        else:
            if stack:
                stack[-1][2].append(block)
            else:
                # 没有标题的块，放在根层级
                pass

    # 弹出剩余
    while stack:
        level, heading, children = stack.pop()
        if stack:
            stack[-1][2].append((heading, children))
        else:
            tree.append((heading, children))

    return tree


# ---------------------------------------------------------------------------
# 关键词匹配
# ---------------------------------------------------------------------------

def heading_matches(block, keywords):
    """检查标题块是否匹配任意关键词"""
    if block["type"] != "heading":
        return False
    text = block["text"].strip()
    for kw in keywords:
        if kw in text:
            return True
    return False


def should_exclude(block, exclude_keywords):
    """检查是否应该排除"""
    if block["type"] != "heading":
        return False
    text = block["text"].strip()
    for kw in exclude_keywords:
        if kw in text:
            return True
    return False


# ---------------------------------------------------------------------------
# 章节定位主逻辑
# ---------------------------------------------------------------------------

def locate_target_sections(blocks):
    """在 Markdown 块序列中定位目标章节。

    策略:
      1. 扫描所有标题块，匹配目标关键词
      2. 对于匹配的标题，收集其下所有子块（段落 + 子标题 + 表格）
      3. 直到遇到同级或更高级标题（不属于目标章节）为止
      4. 排除排除列表中的章节

    Returns:
        [{
            "section_title": str,
            "heading_level": int,
            "keyword_matched": str,
            "blocks": [...],
            "text_all": str,   # 合并的纯文本
            "tables": [...],   # 表格数据
        }, ...]
    """
    sections = []
    i = 0
    while i < len(blocks):
        block = blocks[i]
        if block["type"] != "heading":
            i += 1
            continue

        # 检查排除
        if should_exclude(block, EXCLUDE_KEYWORDS):
            i += 1
            continue

        # 检查匹配
        matched_kw = None
        matched_group = None
        for keywords, min_level, max_level, group_label in TARGET_CHAPTERS:
            if block["level"] < min_level or block["level"] > max_level:
                continue
            for kw in keywords:
                if kw in block["text"]:
                    matched_kw = kw
                    matched_group = group_label
                    break
            if matched_kw:
                break

        if not matched_kw:
            i += 1
            continue

        # 收集该章节下所有子块
        section_blocks = [block]
        j = i + 1
        while j < len(blocks):
            child = blocks[j]
            # 遇到同级或更高级标题 → 停止 (除非它也是目标章节)
            if child["type"] == "heading" and child["level"] <= block["level"]:
                # 检查是不是目标章节的子标题
                is_child_heading = False
                for keywords, min_level, max_level, group_label in TARGET_CHAPTERS:
                    if child["level"] >= min_level and child["level"] <= max_level:
                        for kw in keywords:
                            if kw in child["text"]:
                                is_child_heading = True
                                break
                    if is_child_heading:
                        break
                if not is_child_heading:
                    # 检查排除
                    if should_exclude(child, EXCLUDE_KEYWORDS):
                        break
                    # 不是目标章节的子标题 → 停止
                    if child["level"] == block["level"]:
                        break

            section_blocks.append(child)
            j += 1

        # 合并文本
        all_texts = []
        all_tables = []
        for sb in section_blocks:
            if sb["type"] in ("heading", "paragraph"):
                all_texts.append(sb["text"])
            elif sb["type"] == "table":
                all_tables.append(sb["data"])

        sections.append({
            "section_title": block["text"],
            "heading_level": block["level"],
            "keyword_matched": matched_kw,
            "group": matched_group,
            "blocks": section_blocks,
            "text_all": "\n\n".join(all_texts),
            "tables": all_tables,
            "start_line": block["line_start"],
            "end_line": section_blocks[-1]["line_end"],
        })

        i = j

    return sections


# ---------------------------------------------------------------------------
# 输出
# ---------------------------------------------------------------------------

def write_sections_json(sections, output_path, source_name):
    """将定位的章节写入 JSON 文件"""
    output = {
        "source": source_name,
        "section_count": len(sections),
        "sections": [],
    }

    for sec in sections:
        output["sections"].append({
            "title": sec["section_title"],
            "level": sec["heading_level"],
            "keyword": sec["keyword_matched"],
            "group": sec["group"],
            "text_length": len(sec["text_all"]),
            "table_count": len(sec["tables"]),
            "text": sec["text_all"],
            "tables": [
                {
                    "columns": t[0] if len(t) > 0 else [],
                    "rows": t[1:] if len(t) > 1 else [],
                }
                for t in sec["tables"] if t
            ],
        })

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    logger.info("章节 JSON 已写入: %s", output_path)
    return output_path


def write_sections_markdown(sections, output_path, source_name):
    """将定位的章节写入可读的 Markdown 摘要"""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"# 章节定位结果: {source_name}\n\n")
        f.write(f"共定位到 {len(sections)} 个目标章节\n\n")
        f.write("---\n\n")

        for i, sec in enumerate(sections, 1):
            f.write(f"## {i}. {sec['section_title']}\n\n")
            f.write(f"- **层级**: H{sec['heading_level']}\n")
            f.write(f"- **关键词**: {sec['keyword_matched']}\n")
            f.write(f"- **分组**: {sec['group']}\n")
            f.write(f"- **文本长度**: {len(sec['text_all'])} 字符\n")
            f.write(f"- **表格数**: {len(sec['tables'])}\n")
            f.write(f"- **行范围**: L{sec['start_line']}-L{sec['end_line']}\n\n")

            # 显示前 500 字符的预览
            preview = sec['text_all'][:500].replace("\n", "\n> ")
            f.write(f"> {preview}...\n\n")
            f.write("---\n\n")

    logger.info("章节摘要已写入: %s", output_path)


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="基于 MinerU Markdown 的精确章节定位"
    )
    parser.add_argument(
        "--md-dir",
        type=str,
        default=None,
        help="MinerU 输出的 Markdown 目录",
    )
    parser.add_argument(
        "--md-file",
        type=str,
        default=None,
        help="单个 Markdown 文件路径 (优先级高于 --md-dir)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "outputs", "sections"),
        help="输出目录",
    )
    args = parser.parse_args()

    md_files = []
    if args.md_file:
        md_files = [args.md_file]
    elif args.md_dir:
        md_files = sorted([
            os.path.join(args.md_dir, f)
            for f in os.listdir(args.md_dir)
            if f.endswith(".md")
        ])
    else:
        logger.error("需要指定 --md-dir 或 --md-file")
        sys.exit(1)

    if not md_files:
        logger.warning("未找到 Markdown 文件")
        sys.exit(0)

    logger.info("找到 %d 个 Markdown 文件", len(md_files))

    for md_path in md_files:
        source_name = Path(md_path).stem
        logger.info("处理: %s", source_name)

        try:
            blocks = parse_markdown_structure(md_path)
            logger.info("  解析到 %d 个文本块 (标题: %d, 段落: %d, 表格: %d)",
                        len(blocks),
                        sum(1 for b in blocks if b["type"] == "heading"),
                        sum(1 for b in blocks if b["type"] == "paragraph"),
                        sum(1 for b in blocks if b["type"] == "table"),
                        )

            sections = locate_target_sections(blocks)
            logger.info("  定位到 %d 个目标章节", len(sections))
            for sec in sections:
                logger.info("    [%s] %s (H%d, %d字, %d表)",
                            sec["group"], sec["section_title"],
                            sec["heading_level"],
                            len(sec["text_all"]),
                            len(sec["tables"]),
                            )

            # 写入 JSON
            json_filename = f"{source_name}_sections.json"
            write_sections_json(sections,
                                os.path.join(args.output_dir, json_filename),
                                source_name)

            # 写入 Markdown 摘要
            md_filename = f"{source_name}_sections_summary.md"
            write_sections_markdown(sections,
                                    os.path.join(args.output_dir, md_filename),
                                    source_name)

        except Exception as e:
            logger.error("处理失败 %s: %s", md_path, e)
            import traceback
            traceback.print_exc()

    logger.info("全部完成!")


if __name__ == "__main__":
    main()
