# -*- coding: utf-8 -*-
"""
classify_events.py — 事件分类过滤器
====================================

在 LLM 提取之前，对候选事件文本块进行前置分类过滤，
排除非股权事件文本（公司介绍、行业分析、风险提示等），
仅将含有股权变动信号的文本块送入 LLM 结构化提取。

这是对老师反馈"auto JSONL 噪声较重，LLM 前的候选事件包不够干净"
的直接响应 —— 不是 prompt 多写几句就能解决，前置定位和候选过滤要加强。

用法:
    python classify_events.py \
        --candidates-dir ../outputs/raw_llm_outputs \
        --output-dir ../outputs/raw_llm_outputs \
        --sections-dir ../outputs/logs

过滤逻辑:
    1. 关键词匹配：识别明确的股权事件关键词
    2. 排除词匹配：识别明确的非事件文本
    3. 结构特征：识别表格型股权结构、百分比列表等
    4. 语义信号：年份+增资/转让/变更等组合信号

输出:
    *_classified.json — 每个候选块的分类结果和置信度
    *_classified_filtered.json — 仅保留分类为"事件"的候选块
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
# 关键词规则
# ---------------------------------------------------------------------------

# 强事件信号词（出现则高概率为股权事件）
STRONG_EVENT_KEYWORDS = [
    # 增资
    "增资", "新增注册资本", "增加注册资本", "认购新增", "认缴新增",
    "增资扩股", "新增股份", "注册资本增至", "注册资本由.*增至",
    # 股权转让
    "股权转让", "股份转让", "转让.*股权", "转让.*股份",
    "转让方", "受让方", "转让价格", "转让价款",
    # 整体变更/改制
    "整体变更", "变更为股份有限公司", "整体变更为",
    "净资产折股", "折合.*股本",
    # 股权激励
    "股权激励", "员工持股平台", "限制性股票",
    # 股本变化
    "增资完成后", "本次增资后", "股权结构如下", "股本结构如下",
    "变更完成后", "转让完成后", "转让后.*股权结构",
    # 资本公积转增
    "资本公积转增", "转增股本", "公积金转增",
]

# 弱事件信号词（需要配合其他信号）
WEAK_EVENT_KEYWORDS = [
    "注册资本", "股本", "股东", "持股", "出资",
    "股权", "股份", "认购", "认缴",
]

# 明确的非事件关键词（出现则大概率不是股权事件）
NON_EVENT_KEYWORDS = [
    # 公司基本信息
    "经营范围", "主营业务", "商业模式", "竞争优势", "行业地位",
    "核心竞争力", "发展战略", "发展规划",
    # 财务数据（非股权）
    "营业收入", "净利润", "毛利率", "资产负债", "经营活动",
    "现金流量", "应收账款", "存货", "固定资产", "无形资产",
    # 风险因素
    "风险因素", "风险提示", "重大风险", "特别风险",
    # 管理层讨论
    "管理层讨论", "经营情况讨论", "业务回顾",
    # 行业分析
    "行业概况", "市场规模", "产业链", "竞争格局",
    # 募集资金
    "募集资金", "募投项目", "发行方案", "发行费用",
    # 公司治理
    "董事.*简历", "监事.*简历", "高级管理人员",
    "内部控制", "关联交易", "同业竞争",
    # 财务报告
    "审计报告", "财务报表", "合并报表",
    # 其他
    "释义", "目录", "附录",
]

# 排除整段的触发词（整段都不可能是事件）
SECTION_EXCLUDE_KEYWORDS = [
    "释义", "目录", "释义及目录",
    "发行人声明", "重大事项提示",
    "本次发行概况", "本次发行基本情况",
    "财务会计信息", "管理层讨论与分析",
    "业务与技术", "业务发展目标",
    "公司治理", "内部控制",
]


# ---------------------------------------------------------------------------
# 分类函数
# ---------------------------------------------------------------------------

def classify_candidate_block(block_text, block_meta=None):
    """对单个候选文本块进行事件分类。

    Args:
        block_text: 候选块的文本
        block_meta: 候选块的元信息（页码等）

    Returns:
        dict: {
            "is_event": bool,
            "confidence": float,  # 0-1
            "signals": [str],     # 匹配到的信号
            "reason": str,        # 分类理由
        }
    """
    text = block_text.strip()
    if not text or len(text) < 20:
        return {
            "is_event": False,
            "confidence": 0.0,
            "signals": [],
            "reason": "文本过短（<20字符）"
        }

    signals = []
    exclusions = []

    # 1. 检查排除关键词（整段排除）
    for kw in SECTION_EXCLUDE_KEYWORDS:
        if kw in text:
            return {
                "is_event": False,
                "confidence": 0.0,
                "signals": [],
                "reason": f"整段排除：匹配到选项词「{kw}」"
            }

    # 2. 检查强事件信号
    for kw in STRONG_EVENT_KEYWORDS:
        if kw in text:
            signals.append(f"强信号: {kw}")

    # 3. 检查弱事件信号
    weak_signals = []
    for kw in WEAK_EVENT_KEYWORDS:
        if kw in text:
            weak_signals.append(kw)

    # 4. 检查非事件信号
    non_event_count = 0
    for kw in NON_EVENT_KEYWORDS:
        if kw in text:
            non_event_count += 1
            if non_event_count <= 3:
                exclusions.append(kw)

    # 5. 结构特征检测
    # 检测表格型股权结构（通常是 snapshot 候选）
    has_shareholder_table = bool(re.search(
        r'(股东|持股|出资).*(比例|百分比|%).*[\d.]+.*%', text
    ))
    if has_shareholder_table and (weak_signals or signals):
        signals.append("结构信号: 股东比例表格")

    # 检测日期+金额组合（常见于出资事件）
    has_date_amount = bool(re.search(
        r'\d{4}\s*年\s*\d{1,2}\s*月.*[\d,.]+\s*(万|元)', text
    ))
    if has_date_amount and weak_signals:
        signals.append("结构信号: 日期+金额组合")

    # 6. 综合判定
    strong_count = len([s for s in signals if s.startswith("强信号")])
    total_signal_count = len(signals)

    if strong_count >= 2:
        # 2个以上强信号 → 高置信事件
        return {
            "is_event": True,
            "confidence": 0.95,
            "signals": signals,
            "reason": f"多个强事件信号: {', '.join(signals[:3])}"
        }
    elif strong_count >= 1 and non_event_count <= 2:
        # 1个强信号 + 少量排除 → 中高置信事件
        return {
            "is_event": True,
            "confidence": 0.85,
            "signals": signals,
            "reason": f"强事件信号: {signals[0]}"
        }
    elif strong_count >= 1 and non_event_count > 2:
        # 1个强信号 + 较多排除 → 中等置信（需人工复核）
        return {
            "is_event": True,
            "confidence": 0.6,
            "signals": signals + [f"排除信号({non_event_count}): {', '.join(exclusions[:3])}"],
            "reason": f"事件信号与排除信号混合（排除{non_event_count}个），建议人工复核"
        }
    elif has_shareholder_table and len(weak_signals) >= 3:
        # 股东表格 + 多个弱信号 → 可能是 snapshot
        return {
            "is_event": True,
            "confidence": 0.7,
            "signals": signals + [f"弱信号: {', '.join(weak_signals[:5])}"],
            "reason": "股东比例表格 + 多个弱股权信号"
        }
    elif non_event_count >= 5 and strong_count == 0:
        # 多个排除信号 且 无事件信号 → 非事件
        return {
            "is_event": False,
            "confidence": 0.9,
            "signals": [f"排除信号: {', '.join(exclusions[:5])}"],
            "reason": f"大量非事件信号（{non_event_count}个）且无事件信号"
        }
    else:
        # 不确定 → 保留但标记低置信度
        return {
            "is_event": True,  # 宁可多保留
            "confidence": 0.3,
            "signals": [f"弱信号: {', '.join(weak_signals[:5])}"],
            "reason": f"无明确分类信号，弱保留（非事件排除{non_event_count}个）"
        }


# ---------------------------------------------------------------------------
# 批量处理
# ---------------------------------------------------------------------------

def classify_candidates_file(candidates_path, output_path, confidence_threshold=0.3):
    """对整个 candidates JSON 文件进行分类和过滤。

    Args:
        candidates_path: 输入 *_candidates.json 路径
        output_path: 输出 *_classified_filtered.json 路径
        confidence_threshold: 置信度阈值（低于此值的块被过滤）

    Returns:
        dict: 统计信息
    """
    with open(candidates_path, "r", encoding="utf-8") as f:
        candidates = json.load(f)

    blocks = candidates if isinstance(candidates, list) else candidates.get("blocks", [candidates])

    classified = []
    kept = []
    event_count = 0
    total_count = len(blocks)

    for block in blocks:
        if isinstance(block, str):
            text = block
            meta = {}
        else:
            text = block.get("text", block.get("content", str(block)))
            meta = block

        result = classify_candidate_block(text, meta)
        classified.append({
            "text": text[:500] + ("..." if len(text) > 500 else ""),
            "classification": result,
            "meta": meta if isinstance(meta, dict) else {}
        })

        if result["is_event"] and result["confidence"] >= confidence_threshold:
            kept.append(block)
            event_count += 1

    # 写出分类结果（含所有块的分类详情）
    classified_path = output_path.replace("_filtered.json", ".json")
    with open(classified_path, "w", encoding="utf-8") as f:
        json.dump(classified, f, ensure_ascii=False, indent=2)

    # 写出过滤后的结果
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(kept, f, ensure_ascii=False, indent=2)

    stats = {
        "total_blocks": total_count,
        "event_blocks": event_count,
        "filtered_out": total_count - event_count,
        "keep_ratio": f"{event_count}/{total_count} ({100*event_count/total_count:.1f}%)" if total_count > 0 else "0",
        "classified_file": classified_path,
        "filtered_file": output_path,
    }

    return stats


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="事件分类过滤器 — 在 LLM 提取前过滤非股权事件文本"
    )
    parser.add_argument(
        "--candidates-dir",
        default="../outputs/raw_llm_outputs",
        help="候选事件 JSON 目录"
    )
    parser.add_argument(
        "--output-dir",
        default="../outputs/raw_llm_outputs",
        help="分类结果输出目录"
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.3,
        help="置信度阈值（默认0.3，≤此值的事件块被过滤）"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅统计不写出文件"
    )
    args = parser.parse_args()

    candidates_dir = Path(args.candidates_dir)
    output_dir = Path(args.output_dir)

    if not candidates_dir.exists():
        logger.error(f"候选文件目录不存在: {candidates_dir}")
        sys.exit(1)

    if not args.dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)

    json_files = sorted(candidates_dir.glob("*_candidates.json"))

    if not json_files:
        logger.warning(f"未找到 *_candidates.json 文件于: {candidates_dir}")
        sys.exit(1)

    logger.info("=" * 60)
    logger.info("  事件分类过滤器")
    logger.info("  非事件文本 → 过滤 | 股权事件 → 保留 → LLM 提取")
    logger.info("=" * 60)

    total_stats = {"total_blocks": 0, "event_blocks": 0, "filtered_out": 0}

    for jf in json_files:
        company_name = jf.stem.replace("_candidates", "")
        out_path = output_dir / f"{company_name}_classified_filtered.json"

        if args.dry_run:
            logger.info(f"  [DRY-RUN] {company_name}")
            stats = classify_candidates_file(str(jf), str(out_path))
        else:
            logger.info(f"  处理: {company_name}")
            stats = classify_candidates_file(str(jf), str(out_path))
            logger.info(f"    → {stats['keep_ratio']} 保留为事件")

        total_stats["total_blocks"] += stats["total_blocks"]
        total_stats["event_blocks"] += stats["event_blocks"]
        total_stats["filtered_out"] += stats["filtered_out"]

    logger.info("=" * 60)
    logger.info(f"  总计: {total_stats['total_blocks']} 候选块 → "
                f"{total_stats['event_blocks']} 保留为事件, "
                f"{total_stats['filtered_out']} 过滤")
    logger.info(f"  保留率: {100*total_stats['event_blocks']/max(total_stats['total_blocks'],1):.1f}%")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
