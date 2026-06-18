# -*- coding: utf-8 -*-
"""
extract_with_rules.py - 规则提取脚本

使用正则表达式从候选事件文本中提取结构化信息:
- 投资者名称
- 认缴金额
- 认缴股数
- 价格
- 日期

输出为 JSONL 格式，每行一个JSON对象。

用法:
    python extract_with_rules.py --input-dir ../outputs/raw_llm_outputs --output-dir ../outputs/auto_jsonl
"""

import argparse
import json
import logging
import os
import re
import sys
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    encoding="utf-8",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 正则表达式模式
# ---------------------------------------------------------------------------

# 日期模式
DATE_PATTERNS = [
    # 2023年12月31日 / 2023年12月 / 2023年
    re.compile(r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日"),
    re.compile(r"(\d{4})\s*年\s*(\d{1,2})\s*月"),
    re.compile(r"(\d{4})\s*年"),
    # 2023-12-31 / 2023/12/31
    re.compile(r"(\d{4})\s*[-/]\s*(\d{1,2})\s*[-/]\s*(\d{1,2})"),
    # 2023.12.31
    re.compile(r"(\d{4})\s*[.]\s*(\d{1,2})\s*[.]\s*(\d{1,2})"),
]

# 金额模式（万元/元）
AMOUNT_PATTERNS = [
    # 数字+万元
    re.compile(r"([\d,]+\.?\d*)\s*万\s*元"),
    re.compile(r"([\d,]+\.?\d*)\s*元"),
    # 中文数字金额
    re.compile(r"([\d,]+\.?\d*)\s*(?:万元|元|美元|港币)"),
]

# 股数模式
SHARES_PATTERNS = [
    # 数字+万股/股
    re.compile(r"([\d,]+\.?\d*)\s*万\s*股"),
    re.compile(r"([\d,]+\.?\d*)\s*股"),
    # 注册资本
    re.compile(r"注册资本\s*(?:为|变更为|增加至|减少至)?\s*([\d,]+\.?\d*)\s*万?\s*元?"),
]

# 价格模式
PRICE_PATTERNS = [
    # 每股X元
    re.compile(r"每股\s*([\d,]+\.?\d*)\s*元"),
    re.compile(r"出资价格\s*(?:为|约)?\s*([\d,]+\.?\d*)\s*元"),
    re.compile(r"增资价格\s*(?:为|约)?\s*([\d,]+\.?\d*)\s*元"),
    re.compile(r"认购价格\s*(?:为|约)?\s*([\d,]+\.?\d*)\s*元"),
    re.compile(r"作价\s*([\d,]+\.?\d*)\s*元(?:/股)?"),
]

# 投资者/股东名称模式
INVESTOR_PATTERNS = [
    # "XX公司" / "XX有限(责任)公司" / "XX股份(有限)公司"
    re.compile(r"([\u4e00-\u9fff\w]+(?:有限公司|股份有限公司|有限责任公司|合伙企业|集团|基金|投资|资本|控股|科技|实业))"),
    # "股东: XX" / "投资者: XX"
    re.compile(r"(?:股东|投资者|认购方|增资方|出资方|受让方|转让方)\s*[:：]\s*([\u4e00-\u9fff\w]+)"),
    # "由XX增资" / "XX认缴"
    re.compile(r"([\u4e00-\u9fff\w]{2,20})\s*(?:增资|认缴|认购|出资|受让|转让|入股)"),
]


# ---------------------------------------------------------------------------
# 提取函数
# ---------------------------------------------------------------------------

def extract_dates(text):
    """从文本中提取日期。"""
    dates = []
    for pattern in DATE_PATTERNS:
        for m in pattern.finditer(text):
            groups = m.groups()
            if len(groups) == 3:
                date_str = "{}年{}月{}日".format(groups[0], groups[1], groups[2])
            elif len(groups) == 2:
                date_str = "{}年{}月".format(groups[0], groups[1])
            else:
                date_str = "{}年".format(groups[0])
            dates.append(date_str)
    return dates


def extract_amounts(text):
    """从文本中提取金额。"""
    amounts = []
    for pattern in AMOUNT_PATTERNS:
        for m in pattern.finditer(text):
            amount_str = m.group(1).replace(",", "")
            amounts.append(amount_str)
    return amounts


def extract_shares(text):
    """从文本中提取股数。"""
    shares = []
    for pattern in SHARES_PATTERNS:
        for m in pattern.finditer(text):
            share_str = m.group(1).replace(",", "")
            shares.append(share_str)
    return shares


def extract_prices(text):
    """从文本中提取价格。"""
    prices = []
    for pattern in PRICE_PATTERNS:
        for m in pattern.finditer(text):
            price_str = m.group(1).replace(",", "")
            prices.append(price_str)
    return prices


def extract_investors(text):
    """从文本中提取投资者名称。"""
    investors = []
    for pattern in INVESTOR_PATTERNS:
        for m in pattern.finditer(text):
            name = m.group(1).strip()
            # 过滤过短或明显不是人名/公司名的结果
            if len(name) >= 2 and len(name) <= 50:
                investors.append(name)
    return investors


def extract_event(text, section, source_page, candidate_index):
    """从单个候选文本中提取一个事件。"""
    dates = extract_dates(text)
    amounts = extract_amounts(text)
    shares = extract_shares(text)
    prices = extract_prices(text)
    investors = extract_investors(text)

    event = {
        "event_index": candidate_index,
        "section": section,
        "source_page": source_page,
        "investor_name": investors[0] if investors else "",
        "subscription_amount": amounts[0] if amounts else "",
        "subscription_shares": shares[0] if shares else "",
        "price_per_share": prices[0] if prices else "",
        "date": dates[0] if dates else "",
        "total_capital_after": "",
        "raw_text": text[:500],  # 保留原始文本前500字
        "extraction_method": "rule",
        "confidence": "high" if (investors and (amounts or shares)) else "low",
    }

    return event


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="规则提取 - 使用正则表达式从候选事件中提取结构化信息"
    )
    parser.add_argument(
        "--input-dir",
        type=str,
        default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "outputs", "raw_llm_outputs"),
        help="候选事件文件目录 (默认: ../outputs/raw_llm_outputs)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "outputs", "auto_jsonl"),
        help="JSONL输出目录 (默认: ../outputs/auto_jsonl)",
    )
    args = parser.parse_args()

    logger.info("输入目录: %s", os.path.abspath(args.input_dir))
    logger.info("输出目录: %s", os.path.abspath(args.output_dir))

    # 查找所有 _candidates.json 文件
    candidate_files = sorted([
        f for f in os.listdir(args.input_dir)
        if f.endswith("_candidates.json")
    ])

    if not candidate_files:
        logger.warning("未找到任何 _candidates.json 文件")
        sys.exit(0)

    logger.info("找到 %d 个候选文件", len(candidate_files))

    os.makedirs(args.output_dir, exist_ok=True)

    for cand_file in candidate_files:
        source_name = cand_file.replace("_candidates.json", "")
        logger.info("正在处理: %s", source_name)

        try:
            cand_path = os.path.join(args.input_dir, cand_file)
            with open(cand_path, "r", encoding="utf-8") as f:
                candidates = json.load(f)

            # 输出JSONL文件
            output_filename = "{}_auto.jsonl".format(
                re.sub(r'[\\/:*?"<>|]', '_', source_name)
            )
            output_path = os.path.join(args.output_dir, output_filename)

            event_count = 0
            with open(output_path, "w", encoding="utf-8") as out_f:
                for cand in candidates:
                    event = extract_event(
                        text=cand["text"],
                        section=cand.get("section", ""),
                        source_page=cand.get("source_page", 0),
                        candidate_index=cand.get("index", 0),
                    )
                    out_f.write(json.dumps(event, ensure_ascii=False) + "\n")
                    event_count += 1

            logger.info("  提取 %d 条事件 -> %s", event_count, output_path)

        except Exception as e:
            logger.error("处理失败 %s: %s", cand_file, e)

    logger.info("全部完成!")


if __name__ == "__main__":
    main()