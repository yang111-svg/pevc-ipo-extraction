import csv
import json
from pathlib import Path
from datetime import datetime

BASE_DIR = Path("C:/Users/HP/Desktop/prospectus-pevc-project")
JSON_DIR = BASE_DIR / "outputs" / "week1_sample_json"
COMPANY_LIST = BASE_DIR / "company_lists" / "week1_public_samples.csv"
LOG_FILE = BASE_DIR / "logs" / "validation_log.csv"

def validate_json(json_file):
    """校验JSON文件（增强版）"""
    result = {
        "valid": False,
        "missing_fields": [],
        "type_errors": [],
        "logic_errors": [],
        "review_required": False,
        "upgrade_level": "basic",
        "event_field_issues": [],
        "investor_issues": []
    }

    try:
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        # ===================== 原有校验：最外层字段 =====================
        required_company_fields = ["company_name", "stock_code", "exchange", "board"]
        required_processing_fields = ["download_status", "parse_status", "locate_status", "extract_status"]

        if "company" not in data:
            result["missing_fields"].append("company")
        else:
            for field in required_company_fields:
                if field not in data["company"] or not data["company"][field]:
                    result["missing_fields"].append(f"company.{field}")

        if "financing_events" not in data:
            result["missing_fields"].append("financing_events")

        if "processing" not in data:
            result["missing_fields"].append("processing")
        else:
            for field in required_processing_fields:
                if field not in data["processing"] or not data["processing"][field]:
                    result["missing_fields"].append(f"processing.{field}")

        # ===================== 字段类型校验：financing_events 应为列表 =====================
        if "financing_events" in data:
            events = data["financing_events"]
            if not isinstance(events, list):
                result["type_errors"].append("financing_events 应为列表类型")
                events = []
        else:
            events = []

        # ===================== 原有校验：逻辑错误（financing_events为空） =====================
        if not events:
            if "financing_events" not in data:
                pass  # 已在 missing_fields 中记录
            else:
                result["logic_errors"].append("financing_events为空列表")
        else:
            # ===================== 增强校验：融资事件内部字段 =====================
            required_event_fields = ["event_order", "event_date", "event_type", "evidence_text", "confidence"]
            required_investor_fields = ["investor_original_name", "investor_type", "is_pevc"]

            for i, event in enumerate(events):
                event_label = f"事件{i+1}"

                # 检查必需的事件字段
                for field in required_event_fields:
                    if field not in event or event[field] is None or str(event[field]).strip() == "":
                        result["event_field_issues"].append(f"{event_label} 缺少字段 {field}")

                # ===================== 增强校验：字段类型 =====================
                if "event_order" in event and event["event_order"] is not None:
                    if not isinstance(event["event_order"], int):
                        result["type_errors"].append(f"{event_label} event_order 应为整数，实际为 {type(event['event_order']).__name__}")

                numeric_fields = ["total_investment_amount", "share_price", "shareholding_ratio_after_event"]
                for nf in numeric_fields:
                    if nf in event and event[nf] is not None:
                        if not isinstance(event[nf], (int, float)):
                            result["type_errors"].append(f"{event_label} {nf} 应为数字，实际为 {type(event[nf]).__name__}")

                # ===================== 增强校验：投资者数组 =====================
                if "investors" in event and isinstance(event["investors"], list):
                    for j, investor in enumerate(event["investors"]):
                        inv_label = f"{event_label} 投资者{j+1}"
                        for inv_field in required_investor_fields:
                            if inv_field not in investor or investor[inv_field] is None or str(investor[inv_field]).strip() == "":
                                result["investor_issues"].append(f"{inv_label} 缺少字段 {inv_field}")

                # ===================== 增强校验：total_investment_amount 不应为负数 =====================
                if "total_investment_amount" in event and event["total_investment_amount"] is not None:
                    if isinstance(event["total_investment_amount"], (int, float)) and event["total_investment_amount"] < 0:
                        result["logic_errors"].append(f"{event_label} total_investment_amount 不应为负数")

            # ===================== 增强校验：事件日期按时间顺序排列 =====================
            events_with_date = []
            for i, event in enumerate(events):
                if "event_order" in event and "event_date" in event:
                    try:
                        dt = datetime.strptime(str(event["event_date"]), "%Y-%m-%d")
                        events_with_date.append((event["event_order"], dt, i + 1))
                    except ValueError:
                        pass  # 日期格式问题已在字段校验中处理

            for k in range(1, len(events_with_date)):
                prev_order, prev_dt, prev_idx = events_with_date[k - 1]
                curr_order, curr_dt, curr_idx = events_with_date[k]
                if curr_order < prev_order:
                    result["logic_errors"].append(
                        f"事件{curr_idx} 的 event_order({curr_order}) 小于 事件{prev_idx} 的 event_order({prev_order})，顺序异常"
                    )
                    break
                if curr_order == prev_order and curr_dt < prev_dt:
                    result["logic_errors"].append(
                        f"事件{curr_idx} 与 事件{prev_idx} 的 event_order 相同但日期倒序"
                    )
                    break

            # ===================== 增强校验：重复事件检测 =====================
            seen = set()
            for i, event in enumerate(events):
                key = (str(event.get("event_date", "")), str(event.get("event_type", "")))
                if key != ("", "") and key in seen:
                    result["logic_errors"].append(
                        f"事件{i+1} 与之前的事件重复（event_date={event.get('event_date')}, event_type={event.get('event_type')}）"
                    )
                seen.add(key)

        # ===================== 原有校验：事件缺少 evidence_text =====================
        for i, event in enumerate(events):
            if not event.get("evidence_text"):
                result["logic_errors"].append(f"事件{i+1}缺少evidence_text")

        # ===================== 增强校验：升级版JSON检测 =====================
        upgraded_fields = [
            "disclosed_round", "inferred_round", "round_inference_basis",
            "pre_money_valuation", "post_money_valuation"
        ]
        upgraded_count = 0
        for i, event in enumerate(events):
            for uf in upgraded_fields:
                if uf in event and event[uf] is not None and str(event[uf]).strip() != "":
                    upgraded_count += 1

        if upgraded_count > 0:
            result["upgrade_level"] = "upgraded"

        # ===================== 判断是否需要复核 =====================
        if (result["missing_fields"] or result["logic_errors"]
                or result["type_errors"] or result["event_field_issues"]
                or result["investor_issues"]):
            result["review_required"] = True

        result["valid"] = (len(result["missing_fields"]) == 0
                           and len(result["logic_errors"]) == 0
                           and len(result["type_errors"]) == 0
                           and len(result["event_field_issues"]) == 0
                           and len(result["investor_issues"]) == 0)

    except Exception as e:
        result["logic_errors"].append(f"JSON解析错误: {str(e)}")

    return result

# 读取企业清单
companies = []
with open(COMPANY_LIST, "r", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        companies.append(row)

print(f"共 {len(companies)} 家公司\n")

results = []
for company in companies:
    code = company["stock_code"]
    name = company["company_name"]

    json_file = None
    for f in JSON_DIR.glob(f"{code}*.json"):
        json_file = f
        break

    if not json_file:
        print(f"找不到JSON: {code}")
        results.append({"code": code, "name": name, "valid": False, "missing": "JSON文件不存在", "type": "", "logic": "", "review": True, "upgrade": "basic", "event_issues": "", "investor_issues": ""})
        continue

    print(f"校验: {name} ({code})")
    result = validate_json(json_file)

    status = "valid" if result["valid"] else "invalid"
    print(f"  状态: {status}")
    if result["missing_fields"]:
        print(f"  缺失字段: {', '.join(result['missing_fields'])}")
    if result["type_errors"]:
        print(f"  类型错误: {', '.join(result['type_errors'])}")
    if result["logic_errors"]:
        print(f"  逻辑错误: {', '.join(result['logic_errors'])}")
    if result["event_field_issues"]:
        print(f"  事件字段问题: {', '.join(result['event_field_issues'])}")
    if result["investor_issues"]:
        print(f"  投资者字段问题: {', '.join(result['investor_issues'])}")
    print(f"  升级级别: {result['upgrade_level']}")

    results.append({
        "code": code,
        "name": name,
        "valid": result["valid"],
        "missing": "; ".join(result["missing_fields"]),
        "type": "; ".join(result["type_errors"]),
        "logic": "; ".join(result["logic_errors"]),
        "review": result["review_required"],
        "upgrade": result["upgrade_level"],
        "event_issues": "; ".join(result["event_field_issues"]),
        "investor_issues": "; ".join(result["investor_issues"])
    })

# 更新日志
log_exists = LOG_FILE.exists()
with open(LOG_FILE, "a", encoding="utf-8", newline="") as f:
    w = csv.writer(f)
    if not log_exists:
        w.writerow([
            "company_name", "stock_code", "json_path",
            "validation_status", "missing_fields", "type_errors",
            "logic_errors", "review_required", "upgrade_level",
            "event_field_issues", "investor_issues"
        ])
    for r in results:
        w.writerow([
            r["name"], r["code"],
            f"outputs/week1_sample_json/{r['code']}_pevc_info.json",
            "valid" if r["valid"] else "invalid",
            r["missing"], r["type"], r["logic"],
            "yes" if r["review"] else "no",
            r["upgrade"], r["event_issues"], r["investor_issues"]
        ])

print("\n校验日志已更新")
print(f"\n完成: {sum(1 for x in results if x['valid'])}/{len(results)} 通过校验")
