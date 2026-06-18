#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
JSONL 校验脚本 -- 对 week2 JSONL 抽取结果执行三级校验:
  1. Schema 校验  (Pydantic 模型解析)
  2. 业务规则校验 (数值逻辑 / 持股比例合计 / t0 存在性)
  3. Cross-check 校验 (相邻时点股本 + 中间认缴的一致性)

用法:
  python scripts/validate_jsonl.py
  python scripts/validate_jsonl.py --input-dir outputs/week2_jsonl --output-dir logs
  python scripts/validate_jsonl.py --company 688758
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

# ---------------------------------------------------------------------------
# 项目根目录 & 模块导入
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from schemas.extraction_models import (
    EquitySnapshot,
    RecordType,
    SubscriptionFlow,
)

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------
TOLERANCE = 0.05  # 5% 误差容忍度

VALID_RECORD_TYPES = {RecordType.SUBSCRIPTION_FLOW.value, RecordType.EQUITY_SNAPSHOT.value}


# ===================================================================
# 工具函数
# ===================================================================

def safe_float(v: Any) -> Optional[float]:
    """将值安全转为 float，失败返回 None"""
    if v is None:
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def approx_eq(a: Optional[float], b: Optional[float], tol: float = TOLERANCE) -> bool:
    """判断两个数值是否在容差范围内近似相等"""
    if a is None or b is None:
        return True  # 缺失值不报错
    if a == 0 and b == 0:
        return True
    if a == 0 or b == 0:
        return abs(a - b) < 1e-6
    return abs(a - b) / max(abs(a), abs(b)) <= tol


def parse_snapshot_order(label: str) -> int:
    """从 snapshot_label (如 t0, t1, t2) 提取排序序号"""
    m = re.search(r"(\d+)", label)
    return int(m.group(1)) if m else 0


def parse_date_sort_key(date_str: Optional[str]) -> str:
    """将日期字符串转为可排序的 key，越早越小"""
    if not date_str:
        return ""
    s = str(date_str).strip()
    # 尝试补齐为 YYYY-MM-DD
    parts = re.split(r"[-/年月日]", s)
    parts = [p for p in parts if p.strip()]
    normalized = "-".join(parts[i].zfill(2 if i > 0 else 4) for i in range(min(len(parts), 3)))
    return normalized


# ===================================================================
# 1. Schema 校验
# ===================================================================

def validate_schema_line(
    line_num: int,
    raw_json: dict,
    file_path: str,
) -> list[dict]:
    """
    对单行 JSON 做 Schema 校验，返回校验结果列表（每条一个 dict）。
    """
    results: list[dict] = []

    record_type = raw_json.get("record_type", "")

    # --- record_type 合法性 ---
    if record_type not in VALID_RECORD_TYPES:
        results.append({
            "file": file_path,
            "line": line_num,
            "company_name": raw_json.get("company_name", ""),
            "stock_code": raw_json.get("stock_code", ""),
            "record_type": record_type,
            "check_level": "schema",
            "check_type": "record_type_invalid",
            "status": "FAIL",
            "detail": f"record_type='{record_type}' 不是合法值 ({', '.join(VALID_RECORD_TYPES)})",
        })
        return results  # 类型不合法则无法继续 Pydantic 解析

    # --- Pydantic 解析 ---
    try:
        if record_type == RecordType.SUBSCRIPTION_FLOW.value:
            SubscriptionFlow.model_validate(raw_json)
        elif record_type == RecordType.EQUITY_SNAPSHOT.value:
            EquitySnapshot.model_validate(raw_json)
        results.append({
            "file": file_path,
            "line": line_num,
            "company_name": raw_json.get("company_name", ""),
            "stock_code": raw_json.get("stock_code", ""),
            "record_type": record_type,
            "check_level": "schema",
            "check_type": "pydantic_parse",
            "status": "PASS",
            "detail": "",
        })
    except Exception as e:
        results.append({
            "file": file_path,
            "line": line_num,
            "company_name": raw_json.get("company_name", ""),
            "stock_code": raw_json.get("stock_code", ""),
            "record_type": record_type,
            "check_level": "schema",
            "check_type": "pydantic_parse",
            "status": "FAIL",
            "detail": str(e),
        })

    # --- 必填字段非空检查 ---
    if record_type == RecordType.SUBSCRIPTION_FLOW.value:
        required_fields = ["company_name", "stock_code", "investor_name"]
    else:
        required_fields = ["company_name", "stock_code", "snapshot_label"]

    for field in required_fields:
        val = raw_json.get(field)
        if val is None or (isinstance(val, str) and val.strip() == ""):
            results.append({
                "file": file_path,
                "line": line_num,
                "company_name": raw_json.get("company_name", ""),
                "stock_code": raw_json.get("stock_code", ""),
                "record_type": record_type,
                "check_level": "schema",
                "check_type": "required_field_missing",
                "status": "FAIL",
                "detail": f"必填字段 '{field}' 缺失或为空",
            })

    return results


# ===================================================================
# 2. 业务规则校验
# ===================================================================

def validate_business_rules(
    line_num: int,
    raw_json: dict,
    file_path: str,
) -> list[dict]:
    """
    对单行 JSON 做业务规则校验。
    """
    results: list[dict] = []
    record_type = raw_json.get("record_type", "")
    company_name = raw_json.get("company_name", "")
    stock_code = raw_json.get("stock_code", "")

    # ---- subscription_flow 业务规则 ----
    if record_type == RecordType.SUBSCRIPTION_FLOW.value:
        qty = safe_float(raw_json.get("subscription_qty_wan"))
        amount = safe_float(raw_json.get("subscription_amount_wan"))
        price = safe_float(raw_json.get("subscription_price"))

        # 非负检查（Pydantic 已做，这里做兜底）
        for name_, val_ in [("subscription_qty_wan", qty), ("subscription_amount_wan", amount), ("subscription_price", price)]:
            if val_ is not None and val_ < 0:
                results.append({
                    "file": file_path, "line": line_num,
                    "company_name": company_name, "stock_code": stock_code,
                    "record_type": record_type,
                    "check_level": "business", "check_type": "negative_value",
                    "status": "FAIL",
                    "detail": f"{name_}={val_} 不能为负数",
                })

        # qty * price ≈ amount
        if qty is not None and price is not None and amount is not None:
            expected = qty * price
            if not approx_eq(expected, amount):
                results.append({
                    "file": file_path, "line": line_num,
                    "company_name": company_name, "stock_code": stock_code,
                    "record_type": record_type,
                    "check_level": "business", "check_type": "amount_consistency",
                    "status": "FAIL",
                    "detail": (
                        f"subscription_qty_wan({qty}) * subscription_price({price}) "
                        f"= {expected:.4f}, 与 subscription_amount_wan({amount}) 偏差超过 {TOLERANCE*100}%"
                    ),
                })
            else:
                results.append({
                    "file": file_path, "line": line_num,
                    "company_name": company_name, "stock_code": stock_code,
                    "record_type": record_type,
                    "check_level": "business", "check_type": "amount_consistency",
                    "status": "PASS",
                    "detail": "",
                })

    # ---- equity_snapshot 业务规则 ----
    elif record_type == RecordType.EQUITY_SNAPSHOT.value:
        shareholders = raw_json.get("shareholders", [])
        snapshot_label = raw_json.get("snapshot_label", "")

        # 持股比例合计 95%-105%
        pct_sum = 0.0
        pct_count = 0
        for sh in shareholders:
            pct = safe_float(sh.get("shareholding_pct"))
            if pct is not None:
                pct_sum += pct
                pct_count += 1

        if pct_count > 0:
            if pct_sum < 95 or pct_sum > 105:
                results.append({
                    "file": file_path, "line": line_num,
                    "company_name": company_name, "stock_code": stock_code,
                    "record_type": record_type,
                    "check_level": "business", "check_type": "shareholding_pct_sum",
                    "status": "FAIL",
                    "detail": f"时点 {snapshot_label} 持股比例合计={pct_sum:.2f}%, 不在 95%-105% 范围内",
                })
            else:
                results.append({
                    "file": file_path, "line": line_num,
                    "company_name": company_name, "stock_code": stock_code,
                    "record_type": record_type,
                    "check_level": "business", "check_type": "shareholding_pct_sum",
                    "status": "PASS",
                    "detail": f"时点 {snapshot_label} 持股比例合计={pct_sum:.2f}%",
                })

        # t0 存在性检查 -- 在 cross-check 阶段按公司汇总判断

    return results


# ===================================================================
# 3. Cross-check 校验
# ===================================================================

def cross_check_company(
    stock_code: str,
    company_name: str,
    snapshots: list[dict],
    subscriptions: list[dict],
) -> list[dict]:
    """
    对单家公司执行 cross-check:
      - 检查 t0 存在
      - 按时点排序后，检查相邻时点之间的股本/持股一致性
    """
    results: list[dict] = []

    if not snapshots:
        results.append({
            "company_name": company_name,
            "stock_code": stock_code,
            "check_type": "no_snapshot",
            "status": "FAIL",
            "detail": "该公司没有任何 equity_snapshot 记录",
            "from_label": "",
            "to_label": "",
            "field": "",
            "expected": "",
            "actual": "",
        })
        return results

    # --- t0 存在性 ---
    has_t0 = any(s.get("snapshot_label", "").startswith("t0") for s in snapshots)
    if not has_t0:
        results.append({
            "company_name": company_name,
            "stock_code": stock_code,
            "check_type": "t0_missing",
            "status": "FAIL",
            "detail": "缺少 t0 时点的 equity_snapshot 记录",
            "from_label": "",
            "to_label": "",
            "field": "",
            "expected": "",
            "actual": "",
        })

    # --- 按时点排序 ---
    snapshots_sorted = sorted(snapshots, key=lambda s: parse_snapshot_order(s.get("snapshot_label", "")))

    for idx in range(len(snapshots_sorted) - 1):
        snap_prev = snapshots_sorted[idx]
        snap_next = snapshots_sorted[idx + 1]
        prev_label = snap_prev.get("snapshot_label", "")
        next_label = snap_next.get("snapshot_label", "")

        # 找到两个时点之间的 subscription_flow 记录
        # 判断依据: subscription_date 在 (prev_date, next_date] 之间
        prev_date_key = parse_date_sort_key(snap_prev.get("snapshot_date"))
        next_date_key = parse_date_sort_key(snap_next.get("snapshot_date"))

        # 如果日期不可用，则按 snapshot_label 顺序取中间所有 subscription
        # 这里采用更宽松的策略: 取所有 subscription，因为日期可能不精确
        middle_subs = [sub for sub in subscriptions if sub.get("event_type", "").startswith("增资")]

        # 如果有日期信息，可以更精确过滤
        if prev_date_key and next_date_key:
            middle_subs = [
                sub for sub in subscriptions
                if prev_date_key < parse_date_sort_key(sub.get("subscription_date")) <= next_date_key
            ]
            # 如果精确过滤后为空，回退到全部
            if not middle_subs:
                middle_subs = subscriptions

        # 计算中间认缴合计
        total_sub_qty = 0.0
        sub_by_investor: dict[str, float] = defaultdict(float)
        for sub in middle_subs:
            qty = safe_float(sub.get("subscription_qty_wan"))
            if qty is not None:
                total_sub_qty += qty
                inv_name = sub.get("investor_name", "")
                sub_by_investor[inv_name] += qty

        # --- 总股本一致性 ---
        prev_total = safe_float(snap_prev.get("total_shares"))
        next_total = safe_float(snap_next.get("total_shares"))

        if prev_total is not None and next_total is not None:
            expected_total = prev_total + total_sub_qty
            if not approx_eq(expected_total, next_total):
                results.append({
                    "company_name": company_name,
                    "stock_code": stock_code,
                    "check_type": "total_shares_mismatch",
                    "status": "FAIL",
                    "detail": (
                        f"{prev_label}-> {next_label}: "
                        f"上一时点total_shares({prev_total}) + 中间认缴合计({total_sub_qty}) "
                        f"= {expected_total:.4f}, 与下一时点total_shares({next_total}) 偏差超过 {TOLERANCE*100}%"
                    ),
                    "from_label": prev_label,
                    "to_label": next_label,
                    "field": "total_shares",
                    "expected": f"{expected_total:.4f}",
                    "actual": f"{next_total}",
                })
            else:
                results.append({
                    "company_name": company_name,
                    "stock_code": stock_code,
                    "check_type": "total_shares_consistency",
                    "status": "PASS",
                    "detail": (
                        f"{prev_label}-> {next_label}: "
                        f"total_shares 一致 ({prev_total} + {total_sub_qty} = {expected_total:.4f})"
                    ),
                    "from_label": prev_label,
                    "to_label": next_label,
                    "field": "total_shares",
                    "expected": f"{expected_total:.4f}",
                    "actual": f"{next_total}",
                })

        # --- 逐股东持股一致性 ---
        prev_shareholders = {sh.get("shareholder_name", ""): sh for sh in snap_prev.get("shareholders", [])}
        next_shareholders = {sh.get("shareholder_name", ""): sh for sh in snap_next.get("shareholders", [])}

        all_names = set(prev_shareholders.keys()) | set(next_shareholders.keys())
        for name in all_names:
            prev_sh = prev_shareholders.get(name, {})
            next_sh = next_shareholders.get(name, {})
            prev_shares = safe_float(prev_sh.get("shares"))
            next_shares = safe_float(next_sh.get("shares"))
            sub_qty = sub_by_investor.get(name, 0.0)

            if prev_shares is not None and next_shares is not None:
                expected_shares = prev_shares + sub_qty
                if not approx_eq(expected_shares, next_shares):
                    results.append({
                        "company_name": company_name,
                        "stock_code": stock_code,
                        "check_type": "shareholder_shares_mismatch",
                        "status": "FAIL",
                        "detail": (
                            f"{prev_label}-> {next_label} 股东[{name}]: "
                            f"上一时点shares({prev_shares}) + 认购({sub_qty}) "
                            f"= {expected_shares:.4f}, 与下一时点shares({next_shares}) 偏差超过 {TOLERANCE*100}%"
                        ),
                        "from_label": prev_label,
                        "to_label": next_label,
                        "field": f"shareholder[{name}].shares",
                        "expected": f"{expected_shares:.4f}",
                        "actual": f"{next_shares}",
                    })
                else:
                    results.append({
                        "company_name": company_name,
                        "stock_code": stock_code,
                        "check_type": "shareholder_shares_consistency",
                        "status": "PASS",
                        "detail": (
                            f"{prev_label}-> {next_label} 股东[{name}]: "
                            f"shares 一致 ({prev_shares} + {sub_qty} = {expected_shares:.4f})"
                        ),
                        "from_label": prev_label,
                        "to_label": next_label,
                        "field": f"shareholder[{name}].shares",
                        "expected": f"{expected_shares:.4f}",
                        "actual": f"{next_shares}",
                    })

    return results


# ===================================================================
# 主流程
# ===================================================================

def process_file(
    file_path: Path,
    schema_results: list[dict],
    business_results: list[dict],
    company_snapshots: dict[str, list[dict]],
    company_subscriptions: dict[str, list[dict]],
    company_names: dict[str, str],
) -> int:
    """
    处理单个 JSONL 文件，逐行校验。
    返回总行数。
    """
    total_lines = 0
    with open(file_path, "r", encoding="utf-8") as f:
        for line_num, raw_line in enumerate(f, start=1):
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            total_lines += 1

            # JSON 解析
            try:
                data = json.loads(raw_line)
            except json.JSONDecodeError as e:
                schema_results.append({
                    "file": str(file_path),
                    "line": line_num,
                    "company_name": "",
                    "stock_code": "",
                    "record_type": "",
                    "check_level": "schema",
                    "check_type": "json_parse_error",
                    "status": "FAIL",
                    "detail": f"JSON 解析失败: {e}",
                })
                continue

            # Schema 校验
            schema_results.extend(validate_schema_line(line_num, data, str(file_path)))

            # 业务规则校验
            business_results.extend(validate_business_rules(line_num, data, str(file_path)))

            # 按公司分类收集记录，供 cross-check 使用
            stock_code = str(data.get("stock_code", ""))
            company_name = str(data.get("company_name", ""))
            if stock_code:
                company_names[stock_code] = company_name
                record_type = data.get("record_type", "")
                if record_type == RecordType.EQUITY_SNAPSHOT.value:
                    company_snapshots[stock_code].append(data)
                elif record_type == RecordType.SUBSCRIPTION_FLOW.value:
                    company_subscriptions[stock_code].append(data)

    return total_lines


def main():
    parser = argparse.ArgumentParser(description="JSONL 校验脚本 -- Schema / 业务规则 / Cross-check")
    parser.add_argument(
        "--input-dir",
        type=str,
        default="outputs/week2_jsonl",
        help="JSONL 输入目录 (相对于项目根目录, 默认: outputs/week2_jsonl)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="logs",
        help="日志输出目录 (相对于项目根目录, 默认: logs)",
    )
    parser.add_argument(
        "--company",
        type=str,
        default=None,
        help="只校验指定公司 (股票代码, 如 688758)",
    )
    args = parser.parse_args()

    input_dir: Path = PROJECT_ROOT / args.input_dir
    output_dir: Path = PROJECT_ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    schema_log_path = output_dir / "schema_validation_log.csv"
    cross_check_log_path = output_dir / "cross_check_summary.csv"

    # ---- 收集文件列表 ----
    if not input_dir.exists():
        print(f"[ERROR] 输入目录不存在: {input_dir}")
        sys.exit(1)

    jsonl_files = sorted(input_dir.glob("*.jsonl"))
    if not jsonl_files:
        print(f"[WARN] 输入目录下没有 .jsonl 文件: {input_dir}")
        sys.exit(0)

    # 如果指定了公司，过滤文件
    if args.company:
        jsonl_files = [f for f in jsonl_files if args.company in f.name]
        if not jsonl_files:
            print(f"[WARN] 没有匹配公司 {args.company} 的 .jsonl 文件")
            sys.exit(0)

    print("=" * 70)
    print("JSONL 校验脚本")
    print(f"  输入目录: {input_dir}")
    print(f"  输出目录: {output_dir}")
    print(f"  文件数量: {len(jsonl_files)}")
    if args.company:
        print(f"  指定公司: {args.company}")
    print("=" * 70)

    # ---- 逐文件处理 ----
    schema_results: list[dict] = []
    business_results: list[dict] = []
    company_snapshots: dict[str, list[dict]] = defaultdict(list)
    company_subscriptions: dict[str, list[dict]] = defaultdict(list)
    company_names: dict[str, str] = {}

    total_files = 0
    total_lines = 0
    total_schema_pass = 0
    total_schema_fail = 0
    total_business_pass = 0
    total_business_fail = 0

    for file_path in jsonl_files:
        print(f"\n处理文件: {file_path.name}")
        line_count = process_file(
            file_path,
            schema_results,
            business_results,
            company_snapshots,
            company_subscriptions,
            company_names,
        )
        total_files += 1
        total_lines += line_count
        print(f"  行数: {line_count}")

    # ---- 如果指定了公司，只 cross-check 该公司 ----
    cross_check_codes = list(company_snapshots.keys())
    if args.company:
        cross_check_codes = [c for c in cross_check_codes if c == args.company]

    # ---- Cross-check ----
    print("\n" + "=" * 70)
    print("Cross-check 校验")
    print("=" * 70)

    cross_check_results: list[dict] = []
    for code in sorted(cross_check_codes):
        name = company_names.get(code, "")
        snaps = company_snapshots.get(code, [])
        subs = company_subscriptions.get(code, [])
        print(f"\n  公司: {name} ({code})")
        print(f"    快照数: {len(snaps)}, 认缴记录数: {len(subs)}")

        cc = cross_check_company(code, name, snaps, subs)
        cross_check_results.extend(cc)

        for r in cc:
            icon = "PASS" if r["status"] == "PASS" else "FAIL"
            print(f"    [{icon}] {r['check_type']}: {r['detail']}")

    # ---- 统计 ----
    all_schema = schema_results + business_results
    for r in all_schema:
        if r["status"] == "PASS":
            if r["check_level"] == "schema":
                total_schema_pass += 1
            else:
                total_business_pass += 1
        else:
            if r["check_level"] == "schema":
                total_schema_fail += 1
            else:
                total_business_fail += 1

    total_cross_pass = sum(1 for r in cross_check_results if r["status"] == "PASS")
    total_cross_fail = sum(1 for r in cross_check_results if r["status"] == "FAIL")

    print("\n" + "=" * 70)
    print("校验汇总")
    print("=" * 70)
    print(f"  文件数: {total_files}")
    print(f"  总行数: {total_lines}")
    print(f"  Schema 校验:  PASS={total_schema_pass}  FAIL={total_schema_fail}")
    print(f"  业务规则校验: PASS={total_business_pass}  FAIL={total_business_fail}")
    print(f"  Cross-check:  PASS={total_cross_pass}  FAIL={total_cross_fail}")

    # ---- 写入 schema_validation_log.csv ----
    schema_log_fieldnames = [
        "file", "line", "company_name", "stock_code", "record_type",
        "check_level", "check_type", "status", "detail",
    ]
    with open(schema_log_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=schema_log_fieldnames)
        writer.writeheader()
        for row in all_schema:
            writer.writerow(row)
    print(f"\n  Schema/业务日志: {schema_log_path}")

    # ---- 写入 cross_check_summary.csv ----
    cross_log_fieldnames = [
        "company_name", "stock_code", "check_type", "status", "detail",
        "from_label", "to_label", "field", "expected", "actual",
    ]
    with open(cross_check_log_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=cross_log_fieldnames)
        writer.writeheader()
        for row in cross_check_results:
            writer.writerow(row)
    print(f"  Cross-check日志: {cross_check_log_path}")

    print("\n校验完成。")


if __name__ == "__main__":
    main()
