# -*- coding: utf-8 -*-
"""
post_filter.py — LLM精筛后的代码级二次过滤

解决的问题:
  即使LLM判为is_event=true, 仍有很多"提及事件但非事件本身"的文本。
  例如: "上述吸收合并对发行人的影响...资产总额21.82%"
  这些文本提到了事件关键词, 但实际内容是财务影响分析, 不是股本变化事件。

过滤规则(基于你删除的18条总结):
  1. 事件影响/分析段落(非事件本身)
  2. 仅有金额无股本变化的财务数据
  3. 发行/上市相关(非历史沿革)
  4. 纯引用/参见/详见(非事件段落)
"""

import json
import os
import re

# ═══════════════════════════════════════════
# 噪声模式(已通过你删除的18条验证)
# ═══════════════════════════════════════════

NOISE_PATTERNS = [
    # 1. 事件影响分析(非事件本身)
    (r"对发行人的影响", "事件影响分析,非事件本身"),
    (r"不会?对.*(?:产生|造成|构成).*影响", "事件影响分析"),
    (r"上述.*?(?:对|不会|未).*?(?:影响|改变|变化)", "事件影响分析"),

    # 2. 仅有财务指标无股本变化
    (r"资产总额[（(].*?万元[）)].*?营业收入", "财务数据对比,无股本变化"),
    (r"资产总额.*?\d+\.?\d*%.*?营业收入.*?\d+\.?\d*%", "财务比例对比"),
    (r"利润总额.*?万元.*?\d+\.?\d*%", "利润数据,无股本变化"),

    # 3. 发行/上市相关(非历史沿革)
    (r"本次发行.*?(?:股[票份]|募集|融资)", "IPO发行信息,非历史股本变化"),
    (r"发行价[格款]|发行数量|发行市盈率", "发行参数"),
    (r"募集资金.*?万元|融资.*?万元", "募集资金,非股本变化"),

    # 4. 纯引用/参见(非事件段落)
    (r"^(?:详见|参见|具体.*?参见).*?$", "引用性文字"),
    (r"具体情况.*?见.*?之[""'].*?[""']", "引用见其他章节"),

    # 5. 业务描述/行业分析混入
    (r"公司.*?(?:主要|专业).*?(?:从事|经营|生产|销售)", "业务描述,非事件"),
    (r"市场(?:地位|占有率|竞争力)", "市场分析,非事件"),

    # 6. 仅有股东名/比例无增资动作的描述
    (r"本次.*?(?:前后).*?(?:股权结构|持股).*?(?:不变|未.*?变|保持)", "股权结构描述,无变化事件"),
]

# 关键词缺一不可: 必须有"数字+单位+动作"三要素
MUST_HAVE_EVENT_WORDS = re.compile(
    r"增资|新增出资|增加注册资本|注册资本.*?变[更为]|股权转让|转让.*?股权|"
    r"受让|出让|吸收合并|被吸收|合并.*?注销|减资|减少注册资本|"
    r"设立.*?出资|发起设立|整体变更|折股|变更为.*?股份"
)

MUST_HAVE_NUMBER = re.compile(r"\d[\d,.]*\s*(?:万元|亿元|万股|股|%)")


def is_noise(record):
    """判断一条记录是否为噪声(应删除)"""
    evidence = record.get("evidence_text", record.get("text", ""))
    reason = record.get("llm_reason", "")

    # Rule 0: 必须有事件关键词 + 数字
    if not MUST_HAVE_EVENT_WORDS.search(evidence):
        return True, "缺少事件关键词"

    if not MUST_HAVE_NUMBER.search(evidence):
        return True, "缺少数字/单位"

    # Rule 1-6: 噪声模式匹配
    for pattern, label in NOISE_PATTERNS:
        if re.search(pattern, evidence):
            return True, label

    # Rule 7: LLM给出的理由是"描述了...影响/作用/意义"而非事件本身
    impact_words = ["影响", "作用", "意义", "目的", "背景", "风险", "优势", "前景"]
    if any(w in reason for w in impact_words) and "注册资本" not in evidence:
        return True, f"LLM判为影响/分析({reason[:60]})"

    return False, ""


def filter_company(input_path, output_path):
    """对单个公司的精筛结果做后过滤"""
    kept = []
    removed = []
    total = 0

    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            total += 1
            try:
                rec = json.loads(line)
            except:
                continue

            is_noise_flag, noise_reason = is_noise(rec)
            if is_noise_flag:
                removed.append({"evidence_preview": rec.get("evidence_text", "")[:120],
                                "reason": noise_reason,
                                "event_type": rec.get("event_type", ""),
                                "llm_confidence": rec.get("llm_confidence", "")})
            else:
                kept.append(rec)

    # 保存过滤后结果
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for rec in kept:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    return {
        "total": total,
        "kept": len(kept),
        "removed": len(removed),
        "removal_rate": f"{len(removed)/total*100:.1f}%" if total > 0 else "0%",
        "removed_samples": removed[:5],  # 前5条被删除的示例
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="后过滤LLM精筛结果")
    parser.add_argument("--company", type=str, default=None)
    args = parser.parse_args()

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    filtered_dir = os.path.join(base_dir, "auto_output_filtered")
    post_filtered_dir = os.path.join(base_dir, "auto_output_post_filtered")

    os.makedirs(post_filtered_dir, exist_ok=True)

    companies = [d for d in os.listdir(filtered_dir) if os.path.isdir(os.path.join(filtered_dir, d))]
    if args.company:
        companies = [c for c in companies if args.company in c]

    print(f"{'='*60}")
    print(f"后过滤 {len(companies)} 家公司\n")

    all_stats = {}
    for code in sorted(companies):
        input_path = os.path.join(filtered_dir, code, "filtered_sub_flow.jsonl")
        if not os.path.exists(input_path):
            print(f"  {code}: skipped (no input)")
            continue

        output_dir = os.path.join(post_filtered_dir, code)
        output_path = os.path.join(output_dir, "post_filtered.jsonl")

        stats = filter_company(input_path, output_path)
        all_stats[code] = stats

        print(f"  {code}: {stats['total']} -> {stats['kept']} "
              f"(removed {stats['removed']} = {stats['removal_rate']})")
        for s in stats["removed_samples"][:3]:
            print(f"    [REMOVED:{s['reason'][:30]}] {s['evidence_preview'][:80]}...")

    # 汇总
    total_in = sum(s["total"] for s in all_stats.values())
    total_out = sum(s["kept"] for s in all_stats.values())
    print(f"\n  TOTAL: {total_in} -> {total_out} ({total_in-total_out} removed overall)")
    print(f"  Output: {post_filtered_dir}/")


if __name__ == "__main__":
    main()
