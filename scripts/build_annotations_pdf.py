#!/usr/bin/env python3
"""
build_annotations_pdf.py —— 从 Gold JSONL 记录生成 PDF 关键页批注文件
======================================================================

功能概述：
  1. 读取 week3/manual_gold/ 下所有 *_gold.jsonl 文件
  2. 按公司分组，在 week3/data/ 中匹配源 PDF
  3. 为每条有 pdf_page 的记录，在对应 PDF 页面上绘制：
     - 红色矩形边框（"关键页"视觉标记）
     - 黄色便签批注（记录摘要：类型、主体、金额、日期）
  4. 输出带批注的 PDF 到 annotations_pdf/{股票代码}_{公司简称}/
  5. 导出每页 PNG 截图（方便 GitHub 上预览）
  6. 生成 annotations_pdf/关键页索引.csv

使用方式：
  python scripts/build_annotations_pdf.py

依赖：
  pip install pymupdf

参考来源：
  - 项目结构参考: tdj49vhhwv-wq/prospectus--project/week2/annotations_pdf
  - 脚本逻辑参考: Lzr729/week2/scripts/build_annotations_pdf.py
"""

import os
import sys
import json
import csv
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# ---- Windows 控制台 UTF-8 兼容处理 ----
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ---------------------------------------------------------------------------
# 路径配置 —— 基于脚本所在目录自动推导项目根目录
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent  # 脚本在 scripts/ 下，项目根为上一级

# 输入源
MANUAL_GOLD_DIR = PROJECT_ROOT / "week3" / "manual_gold"
ANNOTATION_INDEX_CSV = MANUAL_GOLD_DIR / "annotation_index.csv"  # 人工标注索引
PDF_DATA_DIR = PROJECT_ROOT / "week3" / "data"

# 输出
OUTPUT_DIR = PROJECT_ROOT / "annotations_pdf"
INDEX_CSV_PATH = OUTPUT_DIR / "关键页索引.csv"

# ---------------------------------------------------------------------------
# 工具函数：JSONL 读写
# ---------------------------------------------------------------------------

def read_jsonl(filepath: Path) -> list[dict]:
    """读取 JSONL 文件，跳过空行，返回带 _source_file 标记的记录列表。"""
    records = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                rec["_source_file"] = filepath.name
                rec["_line_no"] = line_no
                records.append(rec)
            except json.JSONDecodeError as e:
                print(f"  ⚠ JSON 解析错误 [{filepath.name}:{line_no}]: {e}")
    return records


def load_all_gold_records(gold_dir: Path) -> list[dict]:
    """加载 manual_gold/ 下所有 *_gold.jsonl 文件并合并。"""
    all_records = []
    jsonl_files = sorted(gold_dir.glob("*_gold.jsonl"))
    if not jsonl_files:
        print(f"❌ 未在 {gold_dir} 中找到 *_gold.jsonl 文件")
        return all_records

    print(f"📂 加载 Gold JSONL 文件 ({len(jsonl_files)} 个):")
    for fp in jsonl_files:
        recs = read_jsonl(fp)
        all_records.extend(recs)
        print(f"   ✅ {fp.name}: {len(recs)} 条记录")
    print(f"   📊 合计: {len(all_records)} 条记录\n")
    return all_records


# ---------------------------------------------------------------------------
# 工具函数：PDF 匹配
# ---------------------------------------------------------------------------

def find_pdf_by_stock_code(stock_code: str, pdf_dir: Path) -> Path | None:
    """在 pdf_dir 中查找文件名包含 stock_code 的 PDF 文件。"""
    candidates = []
    for pdf_path in pdf_dir.glob("*.pdf"):
        if stock_code in pdf_path.name:
            candidates.append(pdf_path)
    if not candidates:
        return None
    # 多个匹配时取文件名最短的（通常是最干净的命名）
    candidates.sort(key=lambda p: len(p.name))
    return candidates[0]


# ---------------------------------------------------------------------------
# 工具函数：页码标准化
# ---------------------------------------------------------------------------

def normalize_pdf_page(value) -> int | None:
    """将 pdf_page 值统一转为 1-based 整数页码。"""
    if value is None:
        return None
    try:
        page = int(float(str(value)))
        return page if page >= 1 else None
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# 工具函数：文本截断
# ---------------------------------------------------------------------------

def short_text(text: str, max_len: int = 80) -> str:
    """截断文本，替换换行符为空格。"""
    if not text:
        return ""
    text = text.replace("\n", " ").replace("\r", " ")
    if len(text) > max_len:
        return text[:max_len] + "..."
    return text


# ---------------------------------------------------------------------------
# 批注内容构建
# ---------------------------------------------------------------------------

def build_note_for_page(page_no: int, records: list[dict]) -> str:
    """为指定 PDF 页面生成便签批注内容。

    根据记录类型提取关键信息：
    - subscription_flow: 增资方 / 金额 / 价格 / 日期
    - equity_snapshot:  快照标签 / 总股本 / 日期
    - cross_check:      核查类型 / 状态 / 差异
    """
    lines = [f"=== 关键页 #{page_no} ==="]
    lines.append(f"关联记录数: {len(records)}")
    lines.append("")

    type_labels = {
        "subscription_flow": "📌 增资/股权变动",
        "equity_snapshot": "📊 股权快照",
        "cross_check": "🔍 交叉验证",
    }

    for i, rec in enumerate(records, 1):
        rtype = rec.get("record_type", "cross_check" if "cross_check_id" in rec else "?")
        label = type_labels.get(rtype, f"📄 {rtype}")
        lines.append(f"--- 记录 {i}/{len(records)}: {label} ---")

        if rtype == "subscription_flow":
            investor = rec.get("investor_name", "?")
            qty = rec.get("subscription_qty_wan", "")
            amount = rec.get("subscription_amount_wan", "")
            price = rec.get("subscription_price", "")
            date = rec.get("subscription_date", "")
            event = rec.get("event_type", "")
            transfer_from = rec.get("transfer_counterparty", "")
            direction = rec.get("transfer_direction", "")
            lines.append(f"  事件类型: {event}")
            lines.append(f"  日期: {date}")
            if transfer_from:
                lines.append(f"  对方: {transfer_from} ({direction})")
            lines.append(f"  投资方: {investor} ({rec.get('investor_type', '?')})")
            lines.append(f"  股数(万): {qty}  |  金额(万): {amount}  |  价格: {price}")
            lines.append(f"  币种: {rec.get('currency', '?')}")

        elif rtype == "equity_snapshot":
            label_t = rec.get("snapshot_label", "?")
            date = rec.get("snapshot_date", "?")
            total = rec.get("total_shares", "")
            reg_cap = rec.get("registered_capital", "")
            lines.append(f"  快照: {label_t}")
            lines.append(f"  日期: {date}")
            lines.append(f"  总股本(万): {total}  |  注册资本(万): {reg_cap}")
            shareholders = rec.get("shareholders", [])
            lines.append(f"  股东数: {len(shareholders)}")
            for sh in shareholders[:5]:  # 最多显示前5个股东
                lines.append(f"    - {sh.get('shareholder_name','?')}: "
                             f"{sh.get('shares','')}万股 ({sh.get('shareholding_pct','')}%)")
            if len(shareholders) > 5:
                lines.append(f"    ... 还有 {len(shareholders)-5} 位股东")

        elif rtype == "cross_check" or "cross_check_id" in rec:
            cid = rec.get("cross_check_id", "?")
            ctype = rec.get("check_type", "?")
            status = rec.get("check_status", "?")
            diff = rec.get("diff_wan", "")
            diff_pct = rec.get("diff_pct", "")
            lines.append(f"  ID: {cid}")
            lines.append(f"  核查类型: {ctype}")
            lines.append(f"  状态: {status}  |  差异(万): {diff}  |  差异%: {diff_pct}")
            lines.append(f"  前快照→后快照: {rec.get('prev_snapshot_label','?')} → {rec.get('next_snapshot_label','?')}")

        # 证据文本
        evidence = rec.get("evidence_text", "")
        if evidence:
            lines.append(f"  证据: {short_text(evidence, 100)}")

        # 人工备注
        notes = rec.get("extraction_notes", "") or rec.get("notes", "")
        if notes:
            lines.append(f"  备注: {short_text(notes, 100)}")

        lines.append(f"  来源: {rec.get('_source_file', '?')} 行{rec.get('_line_no', '?')}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 核心：生成单公司批注 PDF
# ---------------------------------------------------------------------------

def build_annotation_pdf(
    stock_code: str,
    company_name: str,
    records: list[dict],
    source_pdf: Path,
    output_dir: Path,
) -> list[dict]:
    """为一家公司生成带批注的 PDF 及 PNG 截图。

    参数:
        stock_code: 股票代码
        company_name: 公司全称
        records: 该公司的所有 gold 记录
        source_pdf: 源 PDF 文件路径
        output_dir: 公司输出子目录 (如 annotations_pdf/920100_三协电机/)

    返回:
        index_rows: 用于写入 关键页索引.csv 的行列表
    """
    import fitz  # PyMuPDF —— 延迟导入，让前面的错误检查先执行

    # 按 pdf_page 分组记录
    page_records: dict[int, list[dict]] = defaultdict(list)
    skipped = 0

    for rec in records:
        raw_page = rec.get("pdf_page") or rec.get("evidence_pdf_page")
        page_no = normalize_pdf_page(raw_page)
        if page_no is None:
            skipped += 1
            continue
        page_records[page_no].append(rec)

    if skipped:
        print(f"   ⚠ {skipped} 条记录缺少有效 pdf_page，已跳过")

    if not page_records:
        print(f"   ❌ 没有可用于标注的页码记录")
        return []

    # 打开源 PDF
    try:
        src_doc = fitz.open(str(source_pdf))
    except Exception as e:
        print(f"   ❌ 无法打开 PDF [{source_pdf.name}]: {e}")
        return []

    total_pages = src_doc.page_count
    print(f"   源 PDF: {source_pdf.name} ({total_pages} 页)")

    # 创建输出 PDF
    out_doc = fitz.open()  # 空白新文档
    index_rows = []
    company_short = company_name.replace("（", "(").replace("）", ")")

    sorted_pages = sorted(page_records.keys())

    for page_no in sorted_pages:
        recs = page_records[page_no]

        # PDF 页码从 0 开始
        pdf_index = page_no - 1
        if pdf_index < 0 or pdf_index >= total_pages:
            print(f"   ⚠ 页码 {page_no} 超出 PDF 范围 (1-{total_pages})，已跳过")
            continue

        # 复制源页面到输出文档
        out_doc.insert_pdf(src_doc, from_page=pdf_index, to_page=pdf_index)
        out_page = out_doc[-1]  # 刚插入的最后一页

        # --- 获取页面尺寸 ---
        rect = out_page.rect
        margin = 20

        # --- 绘制红色矩形边框（20px 内缩） ---
        border_rect = fitz.Rect(
            rect.x0 + margin,
            rect.y0 + margin,
            rect.x1 - margin,
            rect.y1 - margin,
        )
        out_page.draw_rect(
            border_rect,
            color=(1.0, 0.0, 0.0),  # 红色
            width=2.0,
            fill=None,
        )

        # --- 添加便签批注 ---
        note_text = build_note_for_page(page_no, recs)
        annot = out_page.add_text_annot(
            point=(36, 36),  # 便签图标位置 (左上角)
            text=note_text,
        )
        annot.set_colors(
            stroke=(0.8, 0.6, 0.0),  # 便签图标颜色：深黄
        )
        annot.update()

        # --- 导出 PNG 截图 ---
        png_name = f"{stock_code}_{company_short}_p{page_no}.png"
        png_path = output_dir / png_name
        try:
            pix = out_page.get_pixmap(dpi=150)
            pix.save(str(png_path))
        except Exception as e:
            print(f"   ⚠ 导出 PNG 失败 (p{page_no}): {e}")

        # --- 为每条记录生成索引行 ---
        for rec in recs:
            rtype = rec.get("record_type", "cross_check" if "cross_check_id" in rec else "?")

            # 提取 subject_name
            if rtype == "subscription_flow":
                subject_name = rec.get("investor_name", "")
                event_date = rec.get("subscription_date", "")
            elif rtype == "equity_snapshot":
                subject_name = rec.get("snapshot_label", "")
                event_date = rec.get("snapshot_date", "")
            elif rtype == "cross_check" or "cross_check_id" in rec:
                subject_name = rec.get("cross_check_id", "")
                event_date = ""
            else:
                subject_name = ""
                event_date = ""

            index_rows.append({
                "股票代码": stock_code,
                "公司": company_name,
                "PDF页码": page_no,
                "记录类型": rtype,
                "事件类型": rec.get("event_type", rec.get("check_type", "")),
                "日期": event_date,
                "主体名称": subject_name,
                "证据摘要": short_text(rec.get("evidence_text", ""), 100),
                "来源文件": rec.get("_source_file", ""),
                "JSONL行号": rec.get("_line_no", ""),
                "是否有截图": "是" if png_path.exists() else "否",
            })

    # --- 保存批注 PDF ---
    pdf_name = f"{stock_code}_{company_short}_关键页批注.pdf"
    pdf_path = output_dir / pdf_name
    num_pages_annotated = out_doc.page_count  # 先获取页数（close 后无法访问）
    out_doc.save(str(pdf_path))
    out_doc.close()
    src_doc.close()

    print(f"   ✅ 已生成: {pdf_name} (标注 {len(sorted_pages)} 个关键页, {len(index_rows)} 条索引)")
    return index_rows


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("  PDF 关键页批注生成工具")
    print("  PEVC IPO 招股书项目 — annotations_pdf")
    print("=" * 60)
    print()

    # ---- 0. 环境检查 ----
    try:
        import fitz  # noqa: F401
    except ImportError:
        print("❌ 缺少依赖 PyMuPDF，请运行: pip install pymupdf")
        sys.exit(1)

    if not PDF_DATA_DIR.exists():
        print(f"❌ PDF 数据目录不存在: {PDF_DATA_DIR}")
        sys.exit(1)

    # ---- 1. 加载 Gold 记录 ----
    print("📂 [1/5] 加载 Gold JSONL 记录...")
    all_records = load_all_gold_records(MANUAL_GOLD_DIR)
    if not all_records:
        print("❌ 没有找到任何 gold 记录，退出。")
        sys.exit(1)

    # ---- 2. 筛选有 pdf_page 的记录并按公司分组 ----
    print("🔍 [2/5] 按公司分组记录...")
    company_records: dict[str, dict] = {}  # stock_code -> {name, records}

    for rec in all_records:
        stock_code = rec.get("stock_code", "")
        company_name = rec.get("company_name", "")
        if not stock_code or not company_name:
            continue

        # 必须有 pdf_page 或 evidence_pdf_page
        page = rec.get("pdf_page") or rec.get("evidence_pdf_page")
        if page is None:
            continue

        if stock_code not in company_records:
            company_records[stock_code] = {"name": company_name, "records": []}
        company_records[stock_code]["records"].append(rec)

    print(f"   共 {len(company_records)} 家公司有可标注记录:\n")
    for code, info in sorted(company_records.items()):
        print(f"   {code} {info['name']}: {len(info['records'])} 条记录")

    # ---- 3. 匹配 PDF ----
    print("\n📄 [3/5] 匹配源 PDF 文件...")
    pdf_files = list(PDF_DATA_DIR.glob("*.pdf"))
    print(f"   PDF 目录: {PDF_DATA_DIR} ({len(pdf_files)} 个 PDF)")

    company_pdf_map: dict[str, Path] = {}
    missing_pdf = []
    for code in sorted(company_records.keys()):
        pdf_path = find_pdf_by_stock_code(code, PDF_DATA_DIR)
        if pdf_path:
            company_pdf_map[code] = pdf_path
            print(f"   ✅ {code} → {pdf_path.name}")
        else:
            missing_pdf.append(code)
            print(f"   ❌ {code} → 未找到匹配 PDF")

    if missing_pdf:
        print(f"\n   ⚠ {len(missing_pdf)} 家公司缺少 PDF: {missing_pdf}")

    # ---- 4. 生成批注 PDF ----
    print("\n🖊️  [4/5] 生成批注 PDF 和 PNG 截图...")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    all_index_rows = []
    total_annotated_pages = 0

    for stock_code in sorted(company_records.keys()):
        info = company_records[stock_code]
        company_name = info["name"]
        records = info["records"]
        source_pdf = company_pdf_map.get(stock_code)

        if source_pdf is None:
            print(f"\n   ⏭ {stock_code} {company_name}: 跳过（无源 PDF）")
            continue

        # 创建公司子目录
        company_short = company_name.replace("（", "(").replace("）", ")")
        company_dir = OUTPUT_DIR / f"{stock_code}_{company_short}"
        company_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n   📌 {stock_code} {company_name}")
        print(f"      记录数: {len(records)} | 输出目录: {company_dir.name}")

        index_rows = build_annotation_pdf(
            stock_code=stock_code,
            company_name=company_name,
            records=records,
            source_pdf=source_pdf,
            output_dir=company_dir,
        )
        all_index_rows.extend(index_rows)
        if index_rows:
            # 统计唯��页码
            unique_pages = set(r["PDF页码"] for r in index_rows)
            total_annotated_pages += len(unique_pages)

    # ---- 5. 写 CSV 索引 ----
    print(f"\n📋 [5/5] 生成关键页索引 CSV...")

    csv_columns = [
        "股票代码", "公司", "PDF页码", "记录类型", "事件类型",
        "日期", "主体名称", "证据摘要", "来源文件", "JSONL行号", "是否有截图",
    ]

    with open(INDEX_CSV_PATH, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=csv_columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_index_rows)

    print(f"   ✅ 已写入 {len(all_index_rows)} 条索引至: {INDEX_CSV_PATH}")

    # ---- 6. 汇总 ----
    print("\n" + "=" * 60)
    print("  ✅ 完成!")
    print(f"  📊 处理公司: {len(company_records) - len(missing_pdf)}/{len(company_records)}")
    print(f"  📄 标注关键页: {total_annotated_pages}")
    print(f"  📝 索引记录: {len(all_index_rows)}")
    print(f"  📁 输出目录: {OUTPUT_DIR}")
    print(f"  📋 索引文件: {INDEX_CSV_PATH}")
    print("=" * 60)


if __name__ == "__main__":
    main()
