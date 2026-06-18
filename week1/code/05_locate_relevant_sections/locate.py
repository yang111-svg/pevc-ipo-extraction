import csv
import re
from pathlib import Path
from datetime import datetime

BASE_DIR = Path("C:/Users/HP/Desktop/prospectus-pevc-project")
OUTPUT_DIR = BASE_DIR / "outputs" / "week1_candidate_texts"
COMPANY_LIST = BASE_DIR / "company_lists" / "week1_public_samples.csv"
LOG_FILE = BASE_DIR / "logs" / "locate_log.csv"

SECTION_KW = ["历史沿革", "股本形成", "增资", "股权转让", "股东情况", "股本演变", "股权结构", "投资者"]
FINANCE_KW = ["增资", "股权转让", "出资", "认购", "入股", "投资者", "外部投资者", "财务投资者", "风险投资", "私募股权", "创投", "创业投资", "产业基金", "股权投资基金", "合伙企业", "员工持股平台", "估值", "PE", "VC", "股份锁定"]

def find_headers(text):
    headers = []
    patterns = [
        r"(?:第[一二三四五六七八九十]+节|第[0-9]+节)\s*[章节]?\s*(.+)",
        r"^[一二三四五六七八九十百零\d]+[、.．]\s*(.+)",
        r"^[（(][一二三四五六七八九十]+[)）]\s*(.+)",
        r"^#{1,3}\s*(.+)",
    ]
    for i, line in enumerate(text.split("\n")):
        line = line.strip()
        if not line:
            continue
        for pattern in patterns:
            match = re.search(pattern, line)
            if match:
                title = match.group(1).strip()
                for kw in SECTION_KW + FINANCE_KW:
                    if kw in title:
                        headers.append({"line": i, "title": title, "kw": kw})
                        break
                break
    return headers

def find_contexts(text, kw, lines=80):
    res = []
    all_lines = text.split("\n")
    for i, line in enumerate(all_lines):
        if kw in line:
            start = max(0, i - 5)
            end = min(len(all_lines), i + lines)
            res.append({"line": i, "kw": kw, "text": "\n".join(all_lines[start:end])})
    return res

def process_file(md_path, out_dir):
    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()
    headers = find_headers(content)
    all_ctx = []
    for kw in FINANCE_KW:
        all_ctx.extend(find_contexts(content, kw))
    seen = set()
    unique = []
    for ctx in all_ctx:
        key = (ctx["line"], ctx["kw"])
        if key not in seen:
            seen.add(key)
            unique.append(ctx)
    if unique:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        txt = ["# " + md_path.stem + " - 候选文本\n\n"]
        txt.append("**时间**: " + ts + "\n\n")
        txt.append("**章节数**: " + str(len(headers)) + "\n\n")
        txt.append("**候选段数**: " + str(len(unique)) + "\n\n")
        txt.append("---\n\n")
        if headers:
            txt.append("## 相关章节\n\n")
            for h in headers[:20]:
                txt.append("- 行" + str(h["line"]) + ": " + h["title"] + " (" + h["kw"] + ")\n")
            txt.append("\n---\n\n")
        txt.append("## 候选段落\n\n")
        for i, ctx in enumerate(unique[:50]):
            txt.append("### 候选" + str(i+1) + "\n\n")
            txt.append("**关键词**: " + ctx["kw"] + " **行**: " + str(ctx["line"]) + "\n\n")
            txt.append(ctx["text"] + "\n\n---\n\n")
        out_file = out_dir / (md_path.stem + "_候选文本.md")
        with open(out_file, "w", encoding="utf-8") as f:
            f.write("".join(txt))
        return {"success": True, "headers": len(headers), "candidates": len(unique), "file": str(out_file)}
    return {"success": False, "headers": 0, "candidates": 0, "file": ""}

companies = []
with open(COMPANY_LIST, "r", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        companies.append(row)

print("共 " + str(len(companies)) + " 家公司\n")
results = []
for company in companies:
    code = company["stock_code"]
    name = company["company_name"]
    md_file = None
    for f in OUTPUT_DIR.glob(code + "*完整解析.md"):
        md_file = f
        break
    if not md_file:
        print("找不到: " + code)
        results.append({"code": code, "name": name, "status": "fail", "hdr": 0, "ctx": 0, "file": "", "err": "not found"})
        continue
    print("定位: " + name + " (" + code + ")")
    r = process_file(md_file, OUTPUT_DIR)
    if r["success"]:
        print("  章节:" + str(r["headers"]) + " 候选:" + str(r["candidates"]) + " -> " + Path(r["file"]).name)
    else:
        print("  失败")
    results.append({"code": code, "name": name, "status": "success" if r["success"] else "fail",
                    "hdr": r["headers"], "ctx": r["candidates"], "file": r["file"], "err": ""})

rows = []
with open(COMPANY_LIST, "r", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        for r in results:
            if row["stock_code"] == r["code"]:
                if r["status"] == "success" and r["ctx"] > 0:
                    row["locate_status"] = "success"
                elif r["status"] == "success":
                    row["locate_status"] = "partial"
                else:
                    row["locate_status"] = "fail"
        rows.append(row)
with open(COMPANY_LIST, "w", encoding="utf-8", newline="") as f:
    csv.DictWriter(f, fieldnames=rows[0].keys()).writeheader()
    csv.DictWriter(f, fieldnames=rows[0].keys()).writerows(rows)
print("\n企业清单已更新")

log_exists = LOG_FILE.exists()
with open(LOG_FILE, "a", encoding="utf-8", newline="") as f:
    w = csv.writer(f)
    if not log_exists:
        w.writerow(["company_name", "stock_code", "matched_keyword", "source_section", "start_position", "end_position", "candidate_text_path", "status", "error_message"])
    for r in results:
        w.writerow([r["name"], r["code"], "历史沿革/增资/股权转让等", "章节" + str(r["hdr"]), "0", str(r["ctx"]), r["file"], r["status"], r["err"]])
print("日志已更新")
print("\n完成: " + str(sum(1 for x in results if x["status"] == "success")) + "/" + str(len(results)))
