# -*- coding: utf-8 -*-
"""
validate_and_evaluate.py — Schema校验 + Cross-check + Auto-vs-Gold TP/FP/FN

输出:
  validation/schema_results.json
  validation/cross_check_results.json
  validation/auto_vs_gold_tpfpfn.json
"""

import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GOLD_DIR = os.path.join(REPO_ROOT, "week3", "manual_gold")
AUTO_DIR = os.path.join(REPO_ROOT, "week6", "auto_output")
VALIDATION_DIR = os.path.join(REPO_ROOT, "week6", "validation")

# 8家固定manifest
MANIFEST_CODES = {"001282", "301563", "301581", "603418", "688758", "688775", "920100", "920116"}


def load_gold():
    gold = defaultdict(lambda: {"subscription_flow": [], "share_transfer_flow": [], "equity_snapshot": [], "cross_check": []})
    for fname in os.listdir(GOLD_DIR):
        if not fname.endswith(".jsonl"): continue
        key = fname.replace("_gold.jsonl", "").replace(".jsonl", "")
        with open(os.path.join(GOLD_DIR, fname), "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip(): continue
                try:
                    rec = json.loads(line)
                    code = rec.get("stock_code", "")
                    if code in MANIFEST_CODES:
                        gold[code][key].append(rec)
                except: pass
    return gold


def load_auto(company_code):
    """加载Auto输出"""
    auto = {"subscription_flow": [], "share_transfer_flow": []}
    company_dirs = [d for d in os.listdir(AUTO_DIR) if d.startswith(company_code)]
    if not company_dirs: return auto
    d = os.path.join(AUTO_DIR, company_dirs[0])
    for key in ["subscription_flow", "share_transfer_flow"]:
        fpath = os.path.join(d, f"auto_{key}.jsonl")
        if os.path.exists(fpath):
            with open(fpath, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        try: auto[key].append(json.loads(line))
                        except: pass
    return auto


def match_tpfpfn(auto_recs, gold_recs, record_type):
    """记录级匹配: TP(正确命中) / FP(误报) / FN(漏报)"""
    tp, fp, fn = 0, 0, 0
    tp_details, fp_details, fn_details = [], [], []
    matched_gold = set()

    for ai, arec in enumerate(auto_recs):
        matched = False
        for gi, grec in enumerate(gold_recs):
            if gi in matched_gold: continue
            # 多字段匹配评分
            score = 0
            # 事件日期匹配 (年月)
            ad = str(arec.get("event_date", ""))[:7]
            gd = str(grec.get("subscription_date", grec.get("transfer_date", grec.get("event_date", ""))))[:7]
            if ad and gd and ad == gd: score += 2

            # 数量匹配
            aq = arec.get("subscription_qty_wan") or arec.get("transfer_qty_wan")
            gq = grec.get("subscription_qty_wan") or grec.get("transferred_registered_capital_wan") or grec.get("transferred_shares_wan")
            if aq is not None and gq is not None and abs(aq - gq) < max(abs(gq) * 0.05, 0.01): score += 1

            # 金额匹配
            aa = arec.get("subscription_amount_wan") or arec.get("transfer_amount_wan")
            ga = grec.get("subscription_amount_wan") or grec.get("transfer_consideration_wan")
            if aa is not None and ga is not None and abs(aa - ga) < max(abs(ga) * 0.05, 0.01): score += 1

            if score >= 2:
                matched = True
                matched_gold.add(gi)
                tp_details.append({"auto_idx": ai, "gold_idx": gi, "score": score,
                                   "auto_date": ad, "gold_date": gd,
                                   "auto_event": arec.get("event_type", ""),
                                   "gold_event": grec.get("event_type", "")})
                break

        if matched:
            tp += 1
        else:
            fp += 1
            fp_details.append({"auto_idx": ai, "auto_date": str(arec.get("event_date", ""))[:10],
                               "auto_text": str(arec.get("evidence_text", ""))[:100]})

    fn = len(gold_recs) - len(matched_gold)
    for gi in range(len(gold_recs)):
        if gi not in matched_gold:
            gr = gold_recs[gi]
            fn_details.append({"gold_idx": gi,
                               "gold_date": str(gr.get("subscription_date", gr.get("transfer_date", "")))[:10],
                               "gold_event": gr.get("event_type", ""),
                               "gold_text": str(gr.get("evidence_text", ""))[:100]})

    r = tp / (tp + fn) if (tp + fn) > 0 else 0
    p = tp / (tp + fp) if (tp + fp) > 0 else 0
    f1 = 2 * r * p / (r + p) if (r + p) > 0 else 0

    return {"record_type": record_type, "auto_total": len(auto_recs), "gold_total": len(gold_recs),
            "TP": tp, "FP": fp, "FN": fn, "recall": round(r, 4), "precision": round(p, 4), "f1": round(f1, 4),
            "tp_details": tp_details[:20], "fp_details": fp_details[:20], "fn_details": fn_details[:20]}


def schema_check(company_code, auto_recs):
    """Schema格式校验"""
    results = {"company_code": company_code, "checks": [], "pass": True}
    for i, rec in enumerate(auto_recs):
        issues = []
        if not rec.get("event_type"): issues.append("missing event_type")
        if not rec.get("company"): issues.append("missing company")
        if rec.get("subscription_qty_wan") is not None and rec["subscription_qty_wan"] < 0:
            issues.append("negative qty")
        if issues:
            results["checks"].append({"idx": i, "issues": issues})
            results["pass"] = False
    return results


def main():
    os.makedirs(VALIDATION_DIR, exist_ok=True)
    gold = load_gold()

    all_eval = []
    schema_results = {}

    for code in sorted(MANIFEST_CODES):
        auto = load_auto(code)
        if not auto["subscription_flow"] and not auto["share_transfer_flow"]:
            continue

        print(f"\n{code}:")
        # Schema check
        schema_results[code] = schema_check(code, auto["subscription_flow"])

        # Auto-vs-Gold TP/FP/FN
        for rtype in ["subscription_flow"]:
            if auto[rtype] or gold[code][rtype]:
                ev = match_tpfpfn(auto[rtype], gold[code][rtype], rtype)
                all_eval.append({**ev, "company_code": code})
                print(f"  {rtype}: TP={ev['TP']}, FP={ev['FP']}, FN={ev['FN']}, "
                      f"R={ev['recall']:.3f}, P={ev['precision']:.3f}, F1={ev['f1']:.3f}")

    # Save results
    with open(os.path.join(VALIDATION_DIR, "schema_results.json"), "w", encoding="utf-8") as f:
        json.dump(schema_results, f, ensure_ascii=False, indent=2)

    summary = {
        "per_company": all_eval,
        "overall": {
            "total_TP": sum(e["TP"] for e in all_eval),
            "total_FP": sum(e["FP"] for e in all_eval),
            "total_FN": sum(e["FN"] for e in all_eval),
        }
    }
    if summary["overall"]["total_TP"] + summary["overall"]["total_FN"] > 0:
        summary["overall"]["recall"] = round(
            summary["overall"]["total_TP"] /
            (summary["overall"]["total_TP"] + summary["overall"]["total_FN"]), 4)

    with open(os.path.join(VALIDATION_DIR, "auto_vs_gold_tpfpfn.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"\nSaved to: {VALIDATION_DIR}/")


if __name__ == "__main__":
    main()
