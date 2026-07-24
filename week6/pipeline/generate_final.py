# -*- coding: utf-8 -*-
"""
generate_final.py — 自动生成final: 加载post-filtered → 逐条检查 → 对Gold去重 → 存final

规则:
  1. 后过滤结果逐条检查 (代码级)
  2. 与Gold去重 (跨字段匹配,避免同一事件存两次)
  3. Gold全量保留 (人工确认,不可删除)
  4. 后过滤中与Gold不重复的高质量事件补充进final
  5. 标记每条的来源: Gold / Auto_PostFilter / Auto_PostFilter_DuplicateOfGold
"""

import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GOLD_DIR = os.path.join(REPO, "week3", "manual_gold")
POST_DIR = os.path.join(REPO, "week6", "auto_output_post_filtered")
FINAL_DIR = os.path.join(REPO, "week6", "final")
DB_SCRIPT = os.path.join(REPO, "week5", "database", "import_to_postgres.py")

MANIFEST = {
    "001282": "芜湖三联锻造股份有限公司",
    "301563": "云汉芯城（上海）互联网科技股份有限公司",
    "301581": "黄山谷捷股份有限公司",
    "603418": "上海友升铝业股份有限公司",
    "688758": "苏州赛分科技股份有限公司",
    "688775": "影石创新科技股份有限公司",
    "920100": "常州三协电机股份有限公司",
    "920116": "中科星图测控技术股份有限公司",
}

# ═══════════════════════════════
# Step 1: Load
# ═══════════════════════════════

def load_gold():
    gold = defaultdict(lambda: {"sub": [], "transfer": [], "snapshot": [], "cross": []})
    for fname in os.listdir(GOLD_DIR):
        if not fname.endswith(".jsonl"): continue
        key_map = {
            "subscription_flow_gold.jsonl": "sub",
            "share_transfer_flow_gold.jsonl": "transfer",
            "equity_snapshot_gold.jsonl": "snapshot",
            "cross_check_gold.jsonl": "cross",
        }
        k = key_map.get(fname)
        if not k: continue
        with open(os.path.join(GOLD_DIR, fname), "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip(): continue
                try:
                    r = json.loads(line)
                    gold[r.get("stock_code","?")][k].append(r)
                except: pass
    return gold


def load_post_filtered():
    results = {}
    for d in os.listdir(POST_DIR):
        dpath = os.path.join(POST_DIR, d)
        if not os.path.isdir(dpath): continue
        fpath = os.path.join(dpath, "post_filtered.jsonl")
        if not os.path.exists(fpath): continue
        with open(fpath, "r", encoding="utf-8") as f:
            recs = [json.loads(l) for l in f if l.strip()]
        code = d  # directory name is stock code
        results[code] = recs
    return results


# ═══════════════════════════════
# Step 2: Dedup + Merge
# ═══════════════════════════════

def is_duplicate(post_rec, gold_recs):
    """判断一条post-filtered记录是否与Gold重复"""
    for gr in gold_recs:
        score = 0
        # 股票代码必须匹配
        pc = post_rec.get("stock_code", "")
        gc = gr.get("stock_code", "")
        if pc != gc: continue

        # 日期匹配(年+月)
        pd = str(post_rec.get("event_date", ""))[:7]
        gd = (gr.get("subscription_date") or gr.get("event_date") or gr.get("transfer_date", ""))
        gd = str(gd)[:7]
        if pd and gd and pd == gd: score += 2

        # 事件类型匹配
        pe = post_rec.get("event_type", "")
        ge = gr.get("event_type", "")
        if pe and ge and pe == ge: score += 1

        # 数量匹配
        pq = post_rec.get("subscription_qty_wan") or post_rec.get("transfer_qty_wan")
        gq = (gr.get("subscription_qty_wan") or gr.get("transferred_registered_capital_wan")
              or gr.get("transferred_shares_wan"))
        if pq and gq and abs(pq - gq) < max(abs(gq)*0.1, 0.1): score += 1

        if score >= 3: return True
    return False


def qty_str(v):
    if v is None: return None
    return round(float(v), 4)


def make_final_rec(rec, source, company_name):
    """标准化一条final记录"""
    return {
        "stock_code": rec.get("stock_code", ""),
        "company_name": company_name,
        "event_type": rec.get("event_type", ""),
        "event_date": rec.get("event_date", rec.get("subscription_date", rec.get("transfer_date", ""))),
        "investor_name": rec.get("investor_name", rec.get("transferor", rec.get("transferee", ""))),
        "subscription_qty_wan": qty_str(rec.get("subscription_qty_wan")),
        "subscription_amount_wan": qty_str(rec.get("subscription_amount_wan")),
        "subscription_price": qty_str(rec.get("subscription_price")),
        "transfer_qty_wan": qty_str(rec.get("transfer_qty_wan") or rec.get("transferred_registered_capital_wan")),
        "evidence_text": str(rec.get("evidence_text", ""))[:500],
        "source": source,
        "extraction_notes": rec.get("extraction_notes", rec.get("llm_reason", "")),
    }


# ═══════════════════════════════
# Step 3: Final quality check
# ═══════════════════════════════

FP_PATTERNS = [
    (r"资产总额.*?万元.*?营业收入.*?利润总额", "财务三表对比,非事件"),
    (r"募集资金.*?(?:万元|亿元)", "IPO募集资金,非历史沿革"),
    (r"发行价[格款]|发行市盈率|发行数量", "IPO发行参数"),
    (r"对发行人的影响|不会.*?构成.*?影响", "事件影响分析"),
    (r"公司.*?(?:主要|专业).*?(?:从事|经营|生产).*?(?:业务|产品)", "业务描述"),
]

def final_quality_check(rec):
    """最后一轮质量检查"""
    text = rec.get("evidence_text", "")
    for pattern, label in FP_PATTERNS:
        if re.search(pattern, text):
            return False, label
    return True, "pass"


# ═══════════════════════════════
# Main
# ═══════════════════════════════

def main():
    os.makedirs(FINAL_DIR, exist_ok=True)

    gold = load_gold()
    post = load_post_filtered()
    print(f"Loaded Gold: {sum(len(v['sub'])+len(v['transfer']) for v in gold.values())} records")
    print(f"Loaded Post-filtered: {sum(len(v) for v in post.values())} records")

    all_stats = {}

    for code in sorted(set(list(MANIFEST.keys()))):
        cname = MANIFEST.get(code, code)
        gold_subs = gold[code]["sub"]
        gold_trans = gold[code]["transfer"]
        gold_total = len(gold_subs) + len(gold_trans)
        post_recs = post.get(code, [])

        print(f"\n{'='*50}")
        print(f"[{code}] {cname}")
        print(f"  Gold: {len(gold_subs)} sub + {len(gold_trans)} trans = {gold_total}")
        print(f"  Post-filtered: {len(post_recs)}")

        final_recs = []

        # 1. Gold全量保留(人工确认过的)
        for gr in gold_subs:
            r = make_final_rec(gr, "Gold_Manual", cname)
            ok, reason = final_quality_check(r)
            r["quality_check"] = "pass" if ok else f"FLAGGED:{reason}"
            final_recs.append(r)
        for gr in gold_trans:
            r = make_final_rec(gr, "Gold_Manual", cname)
            ok, reason = final_quality_check(r)
            r["quality_check"] = "pass" if ok else f"FLAGGED:{reason}"
            final_recs.append(r)

        gold_kept = len(final_recs)

        # 2. 后过滤中不重复的高质量事件补充
        added = 0
        dup = 0
        flagged = 0
        for pr in post_recs:
            # 检查重复
            if is_duplicate(pr, gold_subs + gold_trans):
                dup += 1
                continue

            # 质量检查
            ok, reason = final_quality_check(pr)
            if not ok:
                flagged += 1
                continue

            r = make_final_rec(pr, "Auto_PostFilter", cname)
            r["quality_check"] = "pass"
            final_recs.append(r)
            added += 1

        # 3. 保存
        fpath = os.path.join(FINAL_DIR, f"{code}_{cname}_final.jsonl")
        with open(fpath, "w", encoding="utf-8") as f:
            for r in final_recs:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

        all_stats[code] = {
            "company": cname,
            "gold_kept": gold_kept,
            "post_duplicates": dup,
            "post_flagged": flagged,
            "post_added": added,
            "final_total": len(final_recs),
        }

        print(f"  Final: {gold_kept} gold + {added} post = {len(final_recs)} total "
              f"({dup} duplicates, {flagged} flagged)")

    # ── Summary ──
    print(f"\n{'='*60}")
    print(f"{'Company':20s} {'Gold':>5s} {'+Post':>5s} {'Final':>5s} {'Dup':>4s} {'Flag':>4s}")
    print("-"*60)
    total_g, total_p, total_f = 0, 0, 0
    for code in sorted(all_stats.keys()):
        s = all_stats[code]
        total_g += s["gold_kept"]
        total_p += s["post_added"]
        total_f += s["final_total"]
        print(f"{s['company'][:18]:20s} {s['gold_kept']:5d} {s['post_added']:5d} "
              f"{s['final_total']:5d} {s['post_duplicates']:4d} {s['post_flagged']:4d}")
    print("-"*60)
    print(f"{'TOTAL':20s} {total_g:5d} {total_p:5d} {total_f:5d}")
    print(f"\nFinal files saved to: {FINAL_DIR}/")

    # ── Summary JSON ──
    summary = {
        "generated": "2026-07-24",
        "method": "Gold全量保留 + Post-filtered去重补充 + 最后质量检查",
        "stats": {code: s for code, s in all_stats.items()},
        "total_final_records": total_f,
    }
    with open(os.path.join(FINAL_DIR, "final_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"Summary: {FINAL_DIR}/final_summary.json")

    return all_stats


if __name__ == "__main__":
    main()
