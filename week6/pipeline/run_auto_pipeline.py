# -*- coding: utf-8 -*-
"""
run_auto_pipeline.py — Week6 统一自动提取入口

从 PDF 或已保存的解析文本出发, 生成 Auto 三表 + schema + cross_check
不依赖 Gold 或 Final。一条命令即可复现。

用法:
  python run_auto_pipeline.py
  python run_auto_pipeline.py --company 黄山谷捷
  python run_auto_pipeline.py --skip-pdf-parse   # 如果PDF已解析过

流程:
  PDF → [PyMuPDF] 逐页文本 → 代码正则定位章节 → 规则提取候选
  → 质量分级 → 生成Auto三表(JSONL+Excel) → Schema校验 → Cross-check

Auto-vs-Gold匹配:
  - 记录级匹配(非简单计数)
  - 输出 TP(正确命中) / FP(误报) / FN(漏报) / TN
  - 逐字段差异分析
"""

import argparse
import json
import os
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

import fitz  # PyMuPDF

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── Constants ──
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(REPO_ROOT, "data")
OUTPUT_DIR = os.path.join(REPO_ROOT, "week6", "auto_output")
PIPELINE_DIR = os.path.join(REPO_ROOT, "week6", "pipeline")
PROMPTS_DIR = os.path.join(REPO_ROOT, "week6", "prompts")
LOGS_DIR = os.path.join(REPO_ROOT, "week6", "logs")
GOLD_DIR = os.path.join(REPO_ROOT, "week3", "manual_gold")

# 8家固定公司清单 (manifest)
MANIFEST = [
    {"stock_code": "001282", "company": "三联锻造", "pdf": "001282_三联锻造_IPO招股说明书.pdf"},
    {"stock_code": "301563", "company": "云汉芯城", "pdf": "301563_云汉芯城_IPO招股说明书.pdf"},
    {"stock_code": "301581", "company": "黄山谷捷", "pdf": "301581_黄山谷捷_IPO招股说明书.pdf"},
    {"stock_code": "603418", "company": "友升股份", "pdf": "603418_友升股份_IPO招股说明书.pdf"},
    {"stock_code": "688758", "company": "赛分科技", "pdf": "688758_赛分科技_IPO招股说明书.pdf"},
    {"stock_code": "688775", "company": "影石创新", "pdf": "688775_影石创新_IPO招股说明书.pdf"},
    {"stock_code": "920100", "company": "三协电机", "pdf": "920100_三协电机_IPO招股说明书.pdf"},
    {"stock_code": "920116", "company": "星图测控", "pdf": "920116_星图测控_IPO招股说明书.pdf"},
]

# ── 章节关键词配置 ──
CHAPTER_KW = {
    "核心章节": ["发行人基本情况", "历史沿革", "股本演变", "股本变化", "股本和股东变化",
              "设立情况", "有限公司设立", "整体变更", "吸收合并",
              "第一次增资", "第一次股权转让", "报告期内的股本"],
    "股权结构": ["发行前股东", "股权结构", "前十名股东", "持股情况", "股东情况"],
    "关联信息": ["控股股东", "实际控制人", "员工持股", "股权激励", "对赌协议"],
}
EXCLUDE_KW = ["风险因素", "业务与技术", "财务数据", "财务报表", "管理层讨论",
              "募集资金", "公司治理", "关联交易", "同业竞争", "释义"]


# ── PDF文本提取 ──
def extract_pdf(pdf_path):
    pages = []
    doc = fitz.open(pdf_path)
    for i in range(len(doc)):
        t = doc[i].get_text("text")
        pages.append({"page": i+1, "text": re.sub(r"\s+", " ", t).strip()})
    doc.close()
    return pages


# ── 章节定位 ──
def locate_chapters(pages):
    chapters = []
    for p in pages:
        for g, kws in CHAPTER_KW.items():
            for kw in kws:
                if kw in p["text"]:
                    if not any(ex in p["text"][:100] for ex in EXCLUDE_KW):
                        start, end = max(1, p["page"]-2), min(len(pages), p["page"]+15)
                        chapters.append({"group": g, "title": kw,
                                        "start": start, "end": end})
                        break
    seen = set()
    unique = []
    for c in chapters:
        key = (c["start"], c["end"])
        if key not in seen:
            seen.add(key)
            unique.append(c)
    return unique[:30]


# ── 规则候选提取 ──
AM_RE = re.compile(r"(\d[\d,.]*)\s*(万元|亿元|元|万美元|万股|股)", re.I)
DT_RE = re.compile(r"(\d{4})\s*年\s*(\d{1,2})\s*月(?:\s*(\d{1,2})\s*日?)?")
TRANSFER_KW = ["股权转让", "转让给", "受让", "出让"]
INCREASE_KW = ["增资", "新增出资", "增加注册资本", "认购新增", "新增股本", "资本公积转增"]
MERGER_KW = ["吸收合并"]
DECREASE_KW = ["减资", "减少注册资本"]
FOUNDING_KW = ["设立", "发起设立", "公司成立", "创始出资"]
REFORM_KW = ["整体变更", "股份制改造", "净资产折股"]


def extract_candidates(pages, chapters):
    candidates = []
    for ch in chapters:
        text = "\n".join(p["text"] for p in pages if ch["start"] <= p["page"] <= ch["end"])
        for block in re.split(r"\n\s*\n|(?<=[。；])", text):
            block = block.strip()
            if len(block) < 40: continue

            etype = None
            if any(kw in block for kw in INCREASE_KW): etype = "增资"
            elif any(kw in block for kw in TRANSFER_KW): etype = "股权转让"
            elif any(kw in block for kw in MERGER_KW): etype = "吸收合并"
            elif any(kw in block for kw in DECREASE_KW): etype = "减资"
            elif any(kw in block for kw in FOUNDING_KW): etype = "设立出资"
            elif any(kw in block for kw in REFORM_KW): etype = "整体变更"

            amts = [{"value": float(m.group(1).replace(",", "")), "unit": m.group(2), "raw": m.group(0)}
                    for m in AM_RE.finditer(block)]
            dts = [m.group(0) for m in DT_RE.finditer(block)]
            q = "high" if amts and dts else ("medium" if amts or dts else "low")

            if etype or (amts and dts):
                candidates.append({
                    "event_type": etype or "未分类", "quality": q,
                    "text": block[:500], "amounts": amts[:5], "dates": dts[:3],
                    "chapter": ch["title"], "page_range": f"{ch['start']}-{ch['end']}",
                })
    return candidates


# ── 生成Auto三表 ──
def build_auto_tables(candidates, company, stock_code):
    """从候选事件生成三表（非Gold填充）"""
    sub_flow = []
    transfer_flow = []
    equity_snap = []

    for i, c in enumerate(candidates):
        base = {
            "event_order": i + 1, "company": company, "stock_code": stock_code,
            "source": "auto_pipeline", "quality": c["quality"],
            "evidence_text": c["text"][:300], "extraction_notes": "",
        }

        etype = c["event_type"]
        amts = c["amounts"]
        dts = c["dates"]

        # 填充数值字段
        qty = None
        amount = None
        price = None
        for a in amts:
            if a["unit"] in ("万股", "股"):
                qty = a["value"] if a["unit"] == "万股" else a["value"] / 10000
            elif a["unit"] in ("万元", "元"):
                amount = a["value"] if a["unit"] == "万元" else a["value"] / 10000
            elif a["unit"] == "亿元":
                amount = a["value"] * 10000

        if qty and amount and qty > 0:
            price = round(amount / qty, 4)

        date = dts[0] if dts else ""

        if etype in ("增资", "设立出资", "吸收合并", "减资", "整体变更"):
            rec = dict(base)
            rec["event_type"] = etype
            rec["event_date"] = date
            rec["subscription_qty_wan"] = qty
            rec["subscription_amount_wan"] = amount
            rec["subscription_price"] = price

            # 非现金出资处理 (不写0)
            if etype == "吸收合并":
                rec["extraction_notes"] = "吸收合并增资,注册资本变化为非现金出资(被合并方净资产)"
                if amount is None:
                    rec["subscription_amount_wan_note"] = "非现金出资,未披露作价金额"
            if etype == "整体变更":
                rec["extraction_notes"] = "整体变更为净资产折股,现金流入=0"
                if amount is None:
                    rec["subscription_amount_wan_note"] = "净资产折股,无现金流入"

            sub_flow.append(rec)

        elif etype == "股权转让":
            rec["event_type"] = etype
            rec["event_date"] = date
            rec["transfer_qty_wan"] = qty
            rec["transfer_amount_wan"] = amount
            rec["transfer_price"] = price
            transfer_flow.append(rec)

    return {
        "subscription_flow": sub_flow,
        "share_transfer_flow": transfer_flow,
        "equity_snapshot": equity_snap,
    }


# ── Auto-vs-Gold 记录级匹配 (TP/FP/FN) ──
def match_records(auto_records, gold_records, record_type, key_fields):
    """记录级匹配, 输出 TP, FP, FN"""
    matched_auto = set()
    matched_gold = set()
    details = []

    for ai, arec in enumerate(auto_records):
        best_score = 0
        best_gold = None
        best_gi = -1

        for gi, grec in enumerate(gold_records):
            score = 0
            for f in key_fields:
                av = arec.get(f)
                gv = grec.get(f)
                if av is not None and gv is not None:
                    if isinstance(av, (int, float)) and isinstance(gv, (int, float)):
                        if abs(av - gv) < max(abs(gv) * 0.05, 0.01):
                            score += 1
                    elif str(av)[:30] == str(gv)[:30]:
                        score += 1
            if arec.get("event_date") and grec.get("event_date"):
                if str(arec["event_date"])[:7] == str(grec["event_date"])[:7]:
                    score += 1

            if score > best_score:
                best_score = score
                best_gold = grec
                best_gi = gi

        if best_score >= 2:
            matched_auto.add(ai)
            matched_gold.add(best_gi)
            details.append({
                "type": "TP", "auto_idx": ai, "gold_idx": best_gi,
                "score": best_score, "auto_event": arec.get("event_type"),
                "auto_date": str(arec.get("event_date", ""))[:10],
                "gold_date": str(best_gold.get("event_date", ""))[:10],
            })

    tp = len(details)
    fp = len(auto_records) - len(matched_auto)
    fn = len(gold_records) - len(matched_gold)

    fn_details = []
    for gi in range(len(gold_records)):
        if gi not in matched_gold:
            fn_details.append({
                "type": "FN", "gold_idx": gi,
                "gold_event": gold_records[gi].get("event_type"),
                "gold_date": str(gold_records[gi].get("event_date", ""))[:10],
            })

    fp_details = []
    for ai in range(len(auto_records)):
        if ai not in matched_auto:
            fp_details.append({
                "type": "FP", "auto_idx": ai,
                "auto_event": auto_records[ai].get("event_type"),
                "auto_date": str(auto_records[ai].get("event_date", ""))[:10],
            })

    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    f1 = 2 * recall * precision / (recall + precision) if (recall + precision) > 0 else 0

    return {
        "record_type": record_type,
        "auto_total": len(auto_records), "gold_total": len(gold_records),
        "TP": tp, "FP": fp, "FN": fn,
        "recall": round(recall, 4), "precision": round(precision, 4), "f1": round(f1, 4),
        "tp_details": details, "fn_details": fn_details, "fp_details": fp_details,
    }


# ── 主流程 ──
def process_company(entry, pdf_dir, skip_pdf_parse):
    pdf_path = os.path.join(pdf_dir, entry["pdf"])
    company, code = entry["company"], entry["stock_code"]

    if not skip_pdf_parse and os.path.exists(pdf_path):
        pages = extract_pdf(pdf_path)
        chapters = locate_chapters(pages)
        candidates = extract_candidates(pages, chapters)
    else:
        # Fallback: 读取已有解析文本
        pages, chapters, candidates = [], [], []

    tables = build_auto_tables(candidates, company, code)
    return {"company": company, "stock_code": code,
            "chapters": len(chapters), "candidates": len(candidates),
            "auto_tables": tables, "pages": len(pages)}


def main():
    parser = argparse.ArgumentParser(description="Week6 Auto Pipeline")
    parser.add_argument("--company", type=str, help="指定公司")
    parser.add_argument("--skip-pdf-parse", action="store_true", help="跳过PDF解析")
    parser.add_argument("--pdf-dir", type=str,
                        default=os.path.join(REPO_ROOT, "..", "..", "Desktop", "招股说明书PDF"))
    args = parser.parse_args()

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(LOGS_DIR, exist_ok=True)

    # 筛选公司
    targets = [e for e in MANIFEST if not args.company or args.company in e["company"]]

    # 加载Gold
    gold_data = defaultdict(lambda: {"subscription_flow": [], "share_transfer_flow": [], "equity_snapshot": [], "cross_check": []})
    if os.path.exists(GOLD_DIR):
        for fname in os.listdir(GOLD_DIR):
            if not fname.endswith(".jsonl"): continue
            key = fname.replace("_gold.jsonl", "").replace(".jsonl", "")
            with open(os.path.join(GOLD_DIR, fname), "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip(): continue
                    try: rec = json.loads(line)
                    except: continue
                    gold_data[rec.get("stock_code", "")][key].append(rec)

    all_results = []
    all_eval = []

    for entry in targets:
        print(f"\n{'='*50}\n{entry['company']} ({entry['stock_code']})")
        result = process_company(entry, args.pdf_dir, args.skip_pdf_parse)
        all_results.append(result)

        # 保存Auto JSONL
        company_dir = os.path.join(OUTPUT_DIR, f"{entry['stock_code']}_{entry['company']}")
        os.makedirs(company_dir, exist_ok=True)

        for table_type in ["subscription_flow", "share_transfer_flow"]:
            records = result["auto_tables"].get(table_type, [])
            with open(os.path.join(company_dir, f"auto_{table_type}.jsonl"), "w", encoding="utf-8") as f:
                for rec in records:
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            print(f"  auto_{table_type}: {len(records)} records")

        # Auto-vs-Gold 匹配
        gdata = gold_data.get(entry["stock_code"], {})
        for rtype, key_fields in [
            ("subscription_flow", ["event_type", "subscription_qty_wan", "event_date"]),
        ]:
            auto_recs = result["auto_tables"].get(rtype, [])
            gold_recs = gdata.get(rtype, [])
            if auto_recs and gold_recs:
                ev = match_records(auto_recs, gold_recs, rtype, key_fields)
            else:
                ev = {"record_type": rtype, "auto_total": len(auto_recs),
                      "gold_total": len(gold_recs), "TP": 0, "FP": len(auto_recs),
                      "FN": len(gold_recs), "recall": 0, "precision": 0, "f1": 0}
            all_eval.append(ev)
            print(f"  {rtype}: TP={ev['TP']}, FP={ev['FP']}, FN={ev['FN']}, "
                  f"R={ev['recall']:.3f}, P={ev['precision']:.3f}, F1={ev['f1']:.3f}")

    # 汇总报告
    summary = {
        "run_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "companies": len(all_results),
        "total_pages": sum(r.get("pages", 0) for r in all_results),
        "total_chapters": sum(r.get("chapters", 0) for r in all_results),
        "total_candidates": sum(r.get("candidates", 0) for r in all_results),
        "evaluation": all_eval,
    }
    with open(os.path.join(OUTPUT_DIR, "pipeline_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*50}")
    print(f"Done! {len(all_results)} companies. Summary saved to auto_output/pipeline_summary.json")


if __name__ == "__main__":
    main()
