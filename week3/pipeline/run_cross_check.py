# -*- coding: utf-8 -*-
"""
run_cross_check.py - Cross-check校验脚本

对提取的股本变化事件进行总量核对:
    prev_total + subscription = next_total

即验证: 前一次总股本 + 本次认缴股数 = 本次变更后总股本

用法:
    python run_cross_check.py --input-dir ../outputs/auto_jsonl --output-dir ../outputs/logs
"""

import argparse
import csv
import json
import logging
import os
import re
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    encoding="utf-8",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 数值解析工具
# ---------------------------------------------------------------------------

def parse_number(s):
    """将字符串解析为浮点数。

    支持格式: "1,234.56", "1234", "1,234万" 等。
    """
    if not s or not s.strip():
        return None
    s = s.strip().replace(",", "").replace(" ", "")
    # 去除单位
    s = re.sub(r"[万亿元股]", "", s)
    try:
        return float(s)
    except ValueError:
        return None


def check_total(prev_total, subscription, next_total, tolerance=0.01):
    """校验: prev_total + subscription == next_total

    Args:
        prev_total: 前一次总股本 (float or None)
        subscription: 本次认缴股数 (float or None)
        next_total: 本次变更后总股本 (float or None)
        tolerance: 允许的浮点误差

    Returns:
        (is_valid, diff, message)
    """
    if prev_total is None or subscription is None or next_total is None:
        return None, None, "数据不完整，无法校验"

    expected = prev_total + subscription
    diff = abs(expected - next_total)

    if diff <= tolerance:
        return True, diff, "校验通过 (差异: {:.4f})".format(diff)
    else:
        return False, diff, "校验失败: {} + {} = {}, 实际: {} (差异: {:.4f})".format(
            prev_total, subscription, expected, next_total, diff
        )


# ---------------------------------------------------------------------------
# Cross-check逻辑
# ---------------------------------------------------------------------------

def cross_check_records(records):
    """对一组记录进行cross-check。

    按事件顺序排列，逐对校验 prev_total + subscription = next_total。

    Returns:
        [{
            "event_index": int,
            "prev_total": float,
            "subscription": float,
            "next_total": float,
            "expected": float,
            "diff": float,
            "is_valid": bool,
            "message": str,
        }, ...]
    """
    results = []

    for i in range(1, len(records)):
        prev = records[i - 1]
        curr = records[i]

        # 尝试获取数值
        prev_total = parse_number(prev.get("total_capital_after", ""))
        subscription = parse_number(curr.get("subscription_shares", ""))
        next_total = parse_number(curr.get("total_capital_after", ""))

        # 如果 total_capital_after 为空，尝试从 subscription_shares 推断
        if prev_total is None:
            prev_total = parse_number(prev.get("subscription_shares", ""))

        is_valid, diff, message = check_total(prev_total, subscription, next_total)

        results.append({
            "event_index": curr.get("event_index", i),
            "prev_total": prev_total,
            "subscription": subscription,
            "next_total": next_total,
            "expected": prev_total + subscription if (prev_total is not None and subscription is not None) else None,
            "diff": diff,
            "is_valid": is_valid,
            "message": message,
        })

    return results


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Cross-check校验 - 核验股本变化总量一致性"
    )
    parser.add_argument(
        "--input-dir",
        type=str,
        default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "outputs", "auto_jsonl"),
        help="JSONL文件目录 (默认: ../outputs/auto_jsonl)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "outputs", "logs"),
        help="校验结果输出目录 (默认: ../outputs/logs)",
    )
    args = parser.parse_args()

    logger.info("输入目录: %s", os.path.abspath(args.input_dir))
    logger.info("输出目录: %s", os.path.abspath(args.output_dir))

    # 查找所有 JSONL 文件
    jsonl_files = sorted([
        f for f in os.listdir(args.input_dir)
        if f.endswith(".jsonl")
    ])

    if not jsonl_files:
        logger.warning("未找到任何 .jsonl 文件")
        sys.exit(0)

    logger.info("找到 %d 个JSONL文件", len(jsonl_files))

    os.makedirs(args.output_dir, exist_ok=True)

    all_results = []

    for jsonl_file in jsonl_files:
        source_name = jsonl_file.replace("_auto.jsonl", "").replace(".jsonl", "")
        logger.info("正在校验: %s", source_name)

        jsonl_path = os.path.join(args.input_dir, jsonl_file)

        try:
            # 读取所有记录
            records = []
            with open(jsonl_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        records.append(json.loads(line))

            if len(records) < 2:
                logger.info("  记录数不足2条，跳过cross-check")
                continue

            # 按event_index排序
            records.sort(key=lambda x: x.get("event_index", 0))

            # 执行cross-check
            results = cross_check_records(records)

            for r in results:
                all_results.append({
                    "source": source_name,
                    "event_index": r["event_index"],
                    "prev_total": r["prev_total"] if r["prev_total"] is not None else "",
                    "subscription": r["subscription"] if r["subscription"] is not None else "",
                    "next_total": r["next_total"] if r["next_total"] is not None else "",
                    "expected": r["expected"] if r["expected"] is not None else "",
                    "diff": r["diff"] if r["diff"] is not None else "",
                    "is_valid": r["is_valid"] if r["is_valid"] is not None else "N/A",
                    "message": r["message"],
                })

            valid_count = sum(1 for r in results if r["is_valid"] is True)
            invalid_count = sum(1 for r in results if r["is_valid"] is False)
            na_count = sum(1 for r in results if r["is_valid"] is None)
            logger.info(
                "  校验结果: 通过=%d, 失败=%d, 不可校验=%d",
                valid_count, invalid_count, na_count,
            )

        except Exception as e:
            logger.error("校验失败 %s: %s", jsonl_file, e)

    # 写入CSV
    output_path = os.path.join(args.output_dir, "cross_check_summary.csv")
    fieldnames = [
        "source", "event_index", "prev_total", "subscription",
        "next_total", "expected", "diff", "is_valid", "message",
    ]
    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_results)

    # 统计
    total = len(all_results)
    valid = sum(1 for r in all_results if r["is_valid"] is True)
    invalid = sum(1 for r in all_results if r["is_valid"] is False)

    logger.info("Cross-check完成! 总计: %d, 通过: %d, 失败: %d", total, valid, invalid)
    logger.info("结果已写入: %s", output_path)


if __name__ == "__main__":
    main()