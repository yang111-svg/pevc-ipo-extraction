# -*- coding: utf-8 -*-
"""
compare_to_gold.py - 与gold标准对比脚本

将自动提取结果 (auto_jsonl/) 与人工标注的 gold standard (manual_gold/)
进行逐字段对比，计算匹配率，输出评估报告。

用法:
    python compare_to_gold.py --auto-dir ../outputs/auto_jsonl --gold-dir ../manual_gold --output-dir ../evaluation
"""

import argparse
import csv
import json
import logging
import os
import re
import sys
from collections import defaultdict

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    encoding="utf-8",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 对比字段
# ---------------------------------------------------------------------------

COMPARE_FIELDS = [
    "investor_name",
    "subscription_amount",
    "subscription_shares",
    "price_per_share",
    "date",
    "total_capital_after",
]


# ---------------------------------------------------------------------------
# 数值比较工具
# ---------------------------------------------------------------------------

def normalize_number(s):
    """标准化数值字符串用于比较。"""
    if not s or not s.strip():
        return ""
    s = s.strip().replace(",", "").replace(" ", "")
    s = re.sub(r"[万亿元股]", "", s)
    try:
        val = float(s)
        # 避免浮点精度问题
        if val == int(val):
            return str(int(val))
        return "{:.4f}".format(val).rstrip("0").rstrip(".")
    except ValueError:
        return s.strip()


def normalize_date(s):
    """标准化日期字符串用于比较。"""
    if not s or not s.strip():
        return ""
    s = s.strip()
    # 统一格式
    s = re.sub(r"\s+", "", s)
    return s


def normalize_string(s):
    """标准化字符串用于比较。"""
    if not s or not s.strip():
        return ""
    s = s.strip()
    # 去除多余空白
    s = re.sub(r"\s+", "", s)
    return s


def field_match(auto_val, gold_val, field_name):
    """比较两个字段值是否匹配。

    Returns:
        (is_match: bool, auto_normalized: str, gold_normalized: str)
    """
    if field_name in ("subscription_amount", "subscription_shares", "price_per_share"):
        a = normalize_number(auto_val)
        g = normalize_number(gold_val)
        return a == g, a, g
    elif field_name == "date":
        a = normalize_date(auto_val)
        g = normalize_date(gold_val)
        return a == g, a, g
    else:
        a = normalize_string(auto_val)
        g = normalize_string(gold_val)
        return a == g, a, g


# ---------------------------------------------------------------------------
# 文件加载
# ---------------------------------------------------------------------------

def load_jsonl(directory):
    """加载目录下所有JSONL文件。

    Returns:
        {source_name: [record, ...], ...}
    """
    data = {}
    if not os.path.isdir(directory):
        logger.warning("目录不存在: %s", directory)
        return data

    for fname in sorted(os.listdir(directory)):
        if fname.endswith(".jsonl"):
            source_name = fname.replace("_auto.jsonl", "").replace(".jsonl", "")
            fpath = os.path.join(directory, fname)
            records = []
            with open(fpath, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            records.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass
            data[source_name] = records

    return data


def load_jsonl_or_json(directory):
    """加载目录下所有JSONL或JSON文件。"""
    data = {}
    if not os.path.isdir(directory):
        logger.warning("目录不存在: %s", directory)
        return data

    for fname in sorted(os.listdir(directory)):
        fpath = os.path.join(directory, fname)
        source_name = os.path.splitext(fname)[0]

        if fname.endswith(".jsonl"):
            records = []
            with open(fpath, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            records.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass
            data[source_name] = records
        elif fname.endswith(".json"):
            with open(fpath, "r", encoding="utf-8") as f:
                try:
                    data[source_name] = json.load(f)
                    if not isinstance(data[source_name], list):
                        data[source_name] = [data[source_name]]
                except json.JSONDecodeError:
                    pass

    return data


# ---------------------------------------------------------------------------
# 对比逻辑
# ---------------------------------------------------------------------------

def compare_records(auto_records, gold_records):
    """逐行对比自动提取结果与gold标准。

    策略: 按event_index或行号一一对应。

    Returns:
        [row_match_dict, ...]
    """
    row_matches = []

    max_len = max(len(auto_records), len(gold_records))

    for i in range(max_len):
        auto_rec = auto_records[i] if i < len(auto_records) else {}
        gold_rec = gold_records[i] if i < len(gold_records) else {}

        row = {
            "row_index": i + 1,
            "has_auto": i < len(auto_records),
            "has_gold": i < len(gold_records),
        }

        field_results = {}
        for field in COMPARE_FIELDS:
            auto_val = auto_rec.get(field, "")
            gold_val = gold_rec.get(field, "")
            is_match, auto_norm, gold_norm = field_match(auto_val, gold_val, field)
            field_results[field] = {
                "auto": auto_norm,
                "gold": gold_norm,
                "match": is_match,
            }
            row["{}_auto".format(field)] = auto_norm
            row["{}_gold".format(field)] = gold_norm
            row["{}_match".format(field)] = "Y" if is_match else "N"

        row_matches.append(row)

    return row_matches


def compute_summary(row_matches):
    """计算各字段的匹配率汇总。

    Returns:
        {field: {total, matched, rate}, ...}
    """
    summary = {}
    for field in COMPARE_FIELDS:
        total = 0
        matched = 0
        for row in row_matches:
            if row.get("has_auto") and row.get("has_gold"):
                total += 1
                if row.get("{}_match".format(field)) == "Y":
                    matched += 1
        rate = matched / total if total > 0 else 0
        summary[field] = {
            "total": total,
            "matched": matched,
            "rate": rate,
        }
    return summary


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="与gold对比 - 将自动提取结果与人工标注进行逐字段对比"
    )
    parser.add_argument(
        "--auto-dir",
        type=str,
        default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "outputs", "auto_jsonl"),
        help="自动提取JSONL目录 (默认: ../outputs/auto_jsonl)",
    )
    parser.add_argument(
        "--gold-dir",
        type=str,
        default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "manual_gold"),
        help="人工gold standard目录 (默认: ../manual_gold)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "evaluation"),
        help="评估结果输出目录 (默认: ../evaluation)",
    )
    args = parser.parse_args()

    logger.info("自动提取目录: %s", os.path.abspath(args.auto_dir))
    logger.info("Gold标准目录: %s", os.path.abspath(args.gold_dir))
    logger.info("输出目录: %s", os.path.abspath(args.output_dir))

    os.makedirs(args.output_dir, exist_ok=True)

    # 加载数据
    auto_data = load_jsonl(args.auto_dir)
    gold_data = load_jsonl_or_json(args.gold_dir)

    logger.info("自动提取: %d 个文件", len(auto_data))
    logger.info("Gold标准: %d 个文件", len(gold_data))

    # 将gold数据按stock_code分组（gold文件可能将所有公司合并在一个文件中）
    gold_by_stock_code = defaultdict(list)
    gold_company_map = {}  # company_name → stock_code
    for source_name, records in gold_data.items():
        for rec in records:
            sc = rec.get("stock_code", "")
            cn = rec.get("company_name", "")
            if sc:
                gold_by_stock_code[sc].append(rec)
                if cn and sc not in gold_company_map:
                    gold_company_map[cn] = sc

    logger.info("Gold按stock_code分组: %d 个公司", len(gold_by_stock_code))

    # 将auto数据按stock_code分组，auto文件缺少stock_code字段，从文件名推断
    auto_by_stock_code = defaultdict(list)
    for source_name, records in auto_data.items():
        matched_code = None
        best_score = 0
        for gold_cn, gold_sc in gold_company_map.items():
            # 逐字符检查公共前缀，找到最长匹配
            score = 0
            for i in range(2, min(len(source_name), len(gold_cn)) + 1):
                if source_name[:i] in gold_cn:
                    score = i
                else:
                    break
            if score > best_score:
                best_score = score
                matched_code = gold_sc
        # 备用策略：通过文件名中的关键字匹配（用2字符滑动窗口）
        if not matched_code or best_score < 3:
            for gold_cn, gold_sc in gold_company_map.items():
                for i in range(len(source_name) - 1):
                    chunk = source_name[i:i+2]
                    if len(chunk) >= 2 and chunk in gold_cn:
                        if best_score < 2:
                            best_score = 2
                            matched_code = gold_sc
                        break
        # 最后备用：从文件名中找数字代码
        if not matched_code:
            import re as re2
            code_match = re2.search(r'(\d{6})', source_name)
            if code_match:
                matched_code = code_match.group(1)
        if matched_code:
            for rec in records:
                auto_by_stock_code[matched_code].append(rec)
            logger.info("  %s → %s (%d 条, score=%d)", source_name, matched_code, len(records), best_score)
        else:
            logger.warning("  无法匹配公司代码: %s", source_name)

    logger.info("Auto按stock_code分组: %d 个公司", len(auto_by_stock_code))

    # 找到共同的公司
    common_codes = set(auto_by_stock_code.keys()) & set(gold_by_stock_code.keys())
    if not common_codes:
        logger.warning("未找到可对比的公司（无共同stock_code）")
        sys.exit(0)

    logger.info("可对比: %d 个公司", len(common_codes))

    # 逐公司对比
    all_row_matches = []
    all_summaries = []

    for stock_code in sorted(common_codes):
        logger.info("对比: %s", stock_code)

        auto_records = auto_by_stock_code.get(stock_code, [])
        gold_records = gold_by_stock_code.get(stock_code, [])

        if not auto_records:
            logger.warning("  自动提取结果为空")
            continue
        if not gold_records:
            logger.warning("  Gold标准为空")
            continue

        row_matches = compare_records(auto_records, gold_records)
        summary = compute_summary(row_matches)

        # 标记来源
        for row in row_matches:
            row["source"] = "{}_auto".format(stock_code)
        all_row_matches.extend(row_matches)

        # 获取公司简称
        company_name = gold_records[0].get("company_name", stock_code) if gold_records else stock_code
        source_label = "{}_{}".format(stock_code, company_name[:4] if company_name else "")

        for field, stats in summary.items():
            all_summaries.append({
                "source": source_label,
                "field": field,
                "total": stats["total"],
                "matched": stats["matched"],
                "missed": stats["total"] - stats["matched"],
                "rate": "{:.2%}".format(stats["rate"]),
            })

        # 打印简要结果
        for field, stats in summary.items():
            logger.info(
                "  %s: %d/%d (%.1f%%)",
                field, stats["matched"], stats["total"], stats["rate"] * 100,
            )

    # 写入 row_match.csv
    row_match_path = os.path.join(args.output_dir, "row_match.csv")
    row_fields = ["source", "row_index", "has_auto", "has_gold"]
    for field in COMPARE_FIELDS:
        row_fields.extend([
            "{}_auto".format(field),
            "{}_gold".format(field),
            "{}_match".format(field),
        ])
    with open(row_match_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=row_fields)
        writer.writeheader()
        writer.writerows(all_row_matches)
    logger.info("逐行对比结果: %s", row_match_path)

    # 写入 event_summary.csv
    summary_path = os.path.join(args.output_dir, "event_summary.csv")
    with open(summary_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["source", "field", "total", "matched", "missed", "rate"]
        )
        writer.writeheader()
        writer.writerows(all_summaries)
    logger.info("汇总评估结果: %s", summary_path)

    # 计算总体匹配率
    if all_summaries:
        total_matched = sum(s["matched"] for s in all_summaries)
        total_count = sum(s["total"] for s in all_summaries)
        overall_rate = total_matched / total_count if total_count > 0 else 0
        logger.info(
            "总体匹配率: %d/%d (%.1f%%)",
            total_matched, total_count, overall_rate * 100,
        )

    logger.info("对比完成!")


if __name__ == "__main__":
    main()