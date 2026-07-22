# -*- coding: utf-8 -*-
"""
llm_classifier.py — LLM 精筛候选事件

用 DeepSeek API 对规则提取的候选事件逐条做判断:
  - 是股本变化事件吗? (is_event)
  - 什么类型? (event_type)
  - 置信度? (confidence)
  - 判定理由 (reason)

设计原则:
  - Temperature=0.0 (最大化确定性)
  - JSON模式 (强制结构化输出)
  - 只做分类,不做提取 (职责分离)

用法:
  python llm_classifier.py                     # 全部8家
  python llm_classifier.py --company 黄山谷捷   # 单家测试
  python llm_classifier.py --dry-run            # 只打印prompt,不调API
"""

import json
import os
import re
import sys
import time
import hashlib
from collections import defaultdict
from pathlib import Path

from openai import OpenAI

# ═══════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════

API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
MODEL = "deepseek-chat"
TEMPERATURE = 0.0
MAX_TOKENS = 300
BATCH_DELAY = 0.5  # 每条之间延迟(秒), 避免触发限流

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
AUTO_DIR = os.path.join(REPO_ROOT, "week6", "auto_output")
RAW_DIR = os.path.join(REPO_ROOT, "week6", "raw_llm_responses")
FILTERED_DIR = os.path.join(REPO_ROOT, "week6", "auto_output_filtered")
LOGS_DIR = os.path.join(REPO_ROOT, "week6", "logs")

# 8家固定公司
MANIFEST = [
    "001282", "301563", "301581", "603418",
    "688758", "688775", "920100", "920116",
]

# ═══════════════════════════════════════════
# Prompt 定义
# ═══════════════════════════════════════════

SYSTEM_PROMPT = """你是一个IPO招股说明书审核助手。
你的唯一任务是:判断给定的文本片段是否包含"股本变化事件"。

## 股本变化事件(应判定为 is_event=true):
- 增资:投资者向公司新增出资,公司注册资本增加。关键词:增资/新增出资/增加注册资本/认购新增/增资扩股
- 股权转让:股东间股权流转,公司注册资本不变。关键词:股权转让/转让给/受让/出让
- 吸收合并:公司合并另一家,注册资本变化。关键词:吸收合并/被合并方
- 减资/设立出资/整体变更(净资产折股)

## 非事件(必须判定为 is_event=false):
- 营业收入、净利润、资产评估值、现金流等财务数据
- 募集资金金额、IPO发行价格、发行股数(这些是上市发行,不是历史股本变化)
- 目录、声明、释义、风险提示等非正文
- 业务描述、行业分析、竞争优势、管理层讨论
- 募投项目金额、固定资产投资等
- 公司获得的荣誉、奖项、认证等
- 专利数量、研发费用等技术指标

## 判定规则:
1. 必须明确涉及公司注册资本/股本/股权的变化
2. 仅有"万元""亿元"等金额关键词但无股本变化描述的→非事件
3. 仅有股东名称但无具体增资/转让动作的→非事件
4. 事件发生时间应在公司上市前(历史沿革阶段),IPO发行本身不算

## 输出要求:
返回严格JSON格式,不要任何其他文本。"""

USER_PROMPT_TEMPLATE = """请判断以下文本是否包含股本变化事件:

{text}

返回JSON:
{{"is_event": true/false, "event_type": "增资/股权转让/吸收合并/减资/设立出资/整体变更/null", "confidence": "high/medium/low", "reason": "一句话理由,引用原文关键词"}}"""


# ═══════════════════════════════════════════
# 核心逻辑
# ═══════════════════════════════════════════

def load_auto_candidates(company_code):
    """加载 auto 候选事件"""
    candidates = []
    company_dirs = [d for d in os.listdir(AUTO_DIR) if d.startswith(company_code)]
    if not company_dirs:
        return candidates
    d = os.path.join(AUTO_DIR, company_dirs[0])
    for fname in ["auto_subscription_flow.jsonl", "auto_share_transfer_flow.jsonl"]:
        fpath = os.path.join(d, fname)
        if os.path.exists(fpath):
            with open(fpath, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        try:
                            candidates.append(json.loads(line))
                        except:
                            pass
    return candidates


def classify_candidate(client, candidate, dry_run=False):
    """用 LLM 对单条候选事件做分类"""
    text = candidate.get("evidence_text", candidate.get("text", ""))[:800]

    if dry_run:
        print(f"  [DRY RUN] text={text[:100]}...")
        return None

    # 计算文本哈希(用于缓存/去重)
    text_hash = hashlib.md5(text.encode()).hexdigest()[:8]

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": USER_PROMPT_TEMPLATE.format(text=text)},
            ],
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
            response_format={"type": "json_object"},
        )
        raw_response = response.choices[0].message.content

        # 解析 JSON
        try:
            result = json.loads(raw_response)
        except json.JSONDecodeError:
            # 尝试从回复中提取 JSON
            m = re.search(r'\{[^{}]*"is_event"[^{}]*\}', raw_response, re.DOTALL)
            if m:
                result = json.loads(m.group(0))
            else:
                result = {"is_event": False, "event_type": None,
                          "confidence": "low", "reason": "JSON parse failed"}

        return {
            "text_hash": text_hash,
            "raw_response": raw_response,
            "is_event": result.get("is_event", False),
            "event_type": result.get("event_type"),
            "confidence": result.get("confidence", "low"),
            "reason": result.get("reason", ""),
            "original_candidate": candidate,
        }

    except Exception as e:
        return {
            "text_hash": text_hash,
            "raw_response": str(e),
            "is_event": False,
            "event_type": None,
            "confidence": "low",
            "reason": f"API error: {e}",
            "original_candidate": candidate,
        }


def process_company(client, company_code, dry_run=False):
    """处理单个公司的所有候选事件"""
    candidates = load_auto_candidates(company_code)
    if not candidates:
        print(f"  No candidates found")
        return None

    print(f"  {len(candidates)} candidates to classify...")

    results = []
    stats = {"total": len(candidates), "is_event": 0, "not_event": 0, "error": 0,
             "high": 0, "medium": 0, "low": 0}

    for i, c in enumerate(candidates):
        if i > 0 and not dry_run:
            time.sleep(BATCH_DELAY)

        if (i + 1) % 50 == 0:
            print(f"    {i+1}/{len(candidates)}...")

        result = classify_candidate(client, c, dry_run)
        if result is None:
            continue

        results.append(result)

        if result["is_event"]:
            stats["is_event"] += 1
        else:
            stats["not_event"] += 1

        if result["confidence"] == "high":
            stats["high"] += 1
        elif result["confidence"] == "medium":
            stats["medium"] += 1
        else:
            stats["low"] += 1

    # 保存结果
    company_dir = os.path.join(FILTERED_DIR, company_code)
    os.makedirs(company_dir, exist_ok=True)

    # 1. 原始 LLM 回复
    raw_dir = os.path.join(RAW_DIR, company_code)
    os.makedirs(raw_dir, exist_ok=True)
    with open(os.path.join(raw_dir, "classification_results.jsonl"), "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # 2. 精筛后的事件(只保留 is_event=true 且 confidence!=low)
    filtered = [r for r in results if r["is_event"] and r["confidence"] == "high"]
    with open(os.path.join(company_dir, "filtered_sub_flow.jsonl"), "w", encoding="utf-8") as f:
        for r in filtered:
            # 把 LLM 判定的事件类型回写
            rec = dict(r["original_candidate"])
            rec["event_type"] = r.get("event_type") or rec.get("event_type", "未分类")
            rec["llm_confidence"] = r.get("confidence", "low")
            rec["llm_reason"] = r.get("reason", "")
            rec["llm_verified"] = True
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # 3. 统计
    stats["filtered_count"] = len(filtered)
    noise_reduction = (stats["total"] - stats["filtered_count"]) / stats["total"] * 100 if stats["total"] > 0 else 0

    print(f"    Result: {stats['is_event']} events, {stats['not_event']} noise")
    print(f"    Confidence: high={stats['high']}, medium={stats['medium']}, low={stats['low']}")
    print(f"    Filtered (is_event + conf!=low): {stats['filtered_count']} records ({noise_reduction:.1f}% noise removed)")

    return stats


def main():
    import argparse
    parser = argparse.ArgumentParser(description="LLM精筛候选事件")
    parser.add_argument("--company", type=str, help="单家公司测试")
    parser.add_argument("--dry-run", action="store_true", help="只打印prompt")
    parser.add_argument("--start-from", type=int, default=0, help="从第几条开始(断点续跑)")
    args = parser.parse_args()

    os.makedirs(RAW_DIR, exist_ok=True)
    os.makedirs(FILTERED_DIR, exist_ok=True)
    os.makedirs(LOGS_DIR, exist_ok=True)

    if not API_KEY:
        print("ERROR: Set DEEPSEEK_API_KEY environment variable first!")
        print("  set DEEPSEEK_API_KEY=sk-your-key-here")
        return

    if args.dry_run:
        print("=== DRY RUN MODE ===\n")
        print("SYSTEM PROMPT:\n" + SYSTEM_PROMPT[:500] + "...\n")
        print("USER PROMPT EXAMPLE:\n" + USER_PROMPT_TEMPLATE.format(text="[示例文本]")[:300])
        return

    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

    targets = [c for c in MANIFEST if not args.company or args.company in c]

    all_stats = {}
    for code in targets:
        print(f"\n{'='*50}")
        print(f"[{code}]")
        stats = process_company(client, code)
        if stats:
            all_stats[code] = stats

    # 汇总
    print(f"\n{'='*50}")
    print("ALL DONE! Summary:\n")
    total, total_filtered = 0, 0
    for code, s in all_stats.items():
        total += s["total"]
        total_filtered += s["filtered_count"]
        print(f"  {code}: {s['total']} -> {s['filtered_count']} (noise removed: {s['total']-s['filtered_count']})")

    reduction = (total - total_filtered) / total * 100 if total > 0 else 0
    print(f"\n  Total: {total} candidates -> {total_filtered} after filtering ({reduction:.1f}% noise removed)")
    print(f"  Raw responses: {RAW_DIR}/")
    print(f"  Filtered output: {FILTERED_DIR}/")


if __name__ == "__main__":
    main()
