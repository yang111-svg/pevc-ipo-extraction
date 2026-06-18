import csv
from pathlib import Path
from datetime import datetime

COMPANY_LIST = Path("C:/Users/HP/Desktop/prospectus-pevc-project/company_lists/week1_public_samples.csv")
LOG_FILE = Path("C:/Users/HP/Desktop/prospectus-pevc-project/logs/parse_log.csv")

parse_results = [
    {"code": "001282", "name": "芜湖三联锻造股份有限公司", "pages": 476, "status": "success"},
    {"code": "603418", "name": "上海友升铝业股份有限公司", "pages": 398, "status": "success"},
    {"code": "301581", "name": "黄山谷捷股份有限公司", "pages": 343, "status": "success"},
    {"code": "301563", "name": "云汉芯城（上海）互联网科技股份有限公司", "pages": 443, "status": "success"},
    {"code": "688758", "name": "苏州赛分科技股份有限公司", "pages": 468, "status": "success"},
    {"code": "688775", "name": "影石创新科技股份有限公司", "pages": 555, "status": "success"},
    {"code": "920100", "name": "常州三协电机股份有限公司", "pages": 382, "status": "success"},
    {"code": "920116", "name": "中科星图测控技术股份有限公司", "pages": 365, "status": "success"}
]

rows = []
with open(COMPANY_LIST, "r", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    fieldnames = reader.fieldnames
    for row in reader:
        for r in parse_results:
            if row["stock_code"] == r["code"]:
                row["parse_status"] = r["status"]
        rows.append(row)

with open(COMPANY_LIST, "w", encoding="utf-8-sig", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print("企业清单已更新")

log_exists = LOG_FILE.exists()
with open(LOG_FILE, "a", encoding="utf-8-sig", newline="") as f:
    writer = csv.writer(f)
    if not log_exists:
        writer.writerow(["company_name", "stock_code", "file_name", "parser", "parse_time", "page_count", "markdown_path", "status", "error_message"])  
    for r in parse_results:
        writer.writerow([
            r["name"],
            r["code"],
            f"{r['code']}_IPO招股说明书.pdf",
            "MinerU (pypdfium2)",
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            r["pages"],
            f"outputs/week1_candidate_texts/{r['code']}_{r['name'].split('股份')[0]}_解析结果.md",
            r["status"],
            ""
        ])

print("解析日志已更新")
