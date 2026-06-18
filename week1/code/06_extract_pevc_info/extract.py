import csv
import json
import re
from pathlib import Path
from datetime import datetime

BASE_DIR = Path("C:/Users/HP/Desktop/prospectus-pevc-project")
INPUT_DIR = BASE_DIR / "outputs" / "week1_candidate_texts"
OUTPUT_DIR = BASE_DIR / "outputs" / "week1_sample_json"
COMPANY_LIST = BASE_DIR / "company_lists" / "week1_public_samples.csv"
LOG_FILE = BASE_DIR / "logs" / "extraction_log.csv"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def extract_pevc_info(candidate_text, company_info):
    """从候选文本中提取PE/VC信息"""
    events = []
    text = candidate_text
    
    # 查找融资事件模式
    patterns = [
        r"(\d{4})年?(\d{1,2})月?\s*([\u589e\u8d44\u80a1\u6743\u8f6c\u8ba9\u51fa\u8d44\u8ba4\u8d2d\u5165\u80a1]+)\s*([^，。\n]{2,20})\s*([^，。\n]{2,30})",
        r"([\u589e\u8d44\u80a1\u6743\u8f6c\u8ba9]+)\s*([^，。\n]{2,20})\s*(\d{4})年",
        r"([\u6295\u8d44\u8005|PE|VC|\u521b\u6295|\u79c1\u52df\u80a1\u6743]+)\s*([^，。\n]{2,30})\s*(\d{4})年",
    ]
    
    for pattern in patterns:
        matches = re.finditer(pattern, text)
        for match in matches:
            event = {
                "event_type": "增资" if "增" in match.group(0) else "股权转让" if "转让" in match.group(0) else "其他",
                "date": match.group(1) if len(match.groups()) > 0 else "",
                "amount": "",
                "investor": "",
                "valuation_pre": "",
                "valuation_post": "",
                "share_percentage": "",
                "lock_up_period": "",
                "evidence_text": match.group(0)[:200]
            }
            events.append(event)
    
    # 去重
    seen = set()
    unique_events = []
    for e in events:
        key = e["evidence_text"]
        if key not in seen:
            seen.add(key)
            unique_events.append(e)
    
    return unique_events[:10]  # 最多返回10个事件

def process_company(company):
    code = company["stock_code"]
    name = company["company_name"]
    
    # 查找候选文本文件
    candidate_file = None
    for f in INPUT_DIR.glob(f"{code}*候选文本.md"):
        candidate_file = f
        break
    
    if not candidate_file:
        return {"success": False, "error": "候选文本文件不存在"}
    
    with open(candidate_file, "r", encoding="utf-8") as f:
        candidate_text = f.read()
    
    # 提取PE/VC信息
    events = extract_pevc_info(candidate_text, company)
    
    # 构建JSON输出
    output = {
        "company": {
            "company_name": name,
            "stock_code": code,
            "exchange": company.get("exchange", ""),
            "board": company.get("board", ""),
            "listing_date": company.get("listing_date", ""),
            "prospectus_title": company.get("prospectus_title", ""),
            "prospectus_url": company.get("prospectus_url", ""),
            "prospectus_version": company.get("prospectus_version", ""),
            "prospectus_date": company.get("prospectus_date", "")
        },
        "financing_events": events,
        "processing": {
            "download_status": company.get("download_status", ""),
            "parse_status": company.get("parse_status", ""),
            "locate_status": company.get("locate_status", ""),
            "extract_status": "success" if events else "partial",
            "review_status": "待复核",
            "notes": company.get("notes", "")
        }
    }
    
    # 保存JSON
    output_file = OUTPUT_DIR / f"{code}_{name.split('股份')[0]}_pevc_info.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    return {
        "success": True,
        "events_count": len(events),
        "output_file": str(output_file)
    }

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
    print(f"抽取: {name} ({code})")
    
    result = process_company(company)
    if result["success"]:
        print(f"  事件数: {result['events_count']} -> {Path(result['output_file']).name}")
    else:
        print(f"  失败: {result['error']}")
    
    results.append({
        "code": code,
        "name": name,
        "status": "success" if result["success"] else "fail",
        "events": result.get("events_count", 0),
        "file": result.get("output_file", ""),
        "error": result.get("error", "")
    })

# 更新企业清单
rows = []
with open(COMPANY_LIST, "r", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        for r in results:
            if row["stock_code"] == r["code"]:
                if r["status"] == "success" and r["events"] > 0:
                    row["extract_status"] = "success"
                elif r["status"] == "success":
                    row["extract_status"] = "partial"
                else:
                    row["extract_status"] = "fail"
        rows.append(row)

with open(COMPANY_LIST, "w", encoding="utf-8", newline="") as f:
    csv.DictWriter(f, fieldnames=rows[0].keys()).writeheader()
    csv.DictWriter(f, fieldnames=rows[0].keys()).writerows(rows)

print("\n企业清单已更新")

# 更新日志
log_exists = LOG_FILE.exists()
with open(LOG_FILE, "a", encoding="utf-8", newline="") as f:
    w = csv.writer(f)
    if not log_exists:
        w.writerow(["company_name", "stock_code", "candidate_text_path", "model_name", "prompt_version", "json_path", "status", "error_message"])
    for r in results:
        w.writerow([r["name"], r["code"], f"outputs/week1_candidate_texts/{r['code']}_候选文本.md", "rule-based", "v1", r["file"], r["status"], r["error"]])

print("抽取日志已更新")
print(f"\n完成: {sum(1 for x in results if x['status'] == 'success')}/{len(results)}")


# ============================================================================
# 以下为 LLM 抽取方案：使用 OpenAI 兼容 API + 精心设计的 prompt 实现
# ============================================================================

import requests

# ---------------------------------------------------------------------------
# Prompt 模板：角色设定 + 任务说明 + JSON Schema + 抽取规则 + 输出要求
# ---------------------------------------------------------------------------
EXTRACTION_PROMPT_TEMPLATE = """\
你是一个专业的PE/VC融资信息提取专家。你的任务是从A股上市公司招股说明书的候选文本中，精准提取所有与外部PE/VC机构相关的融资事件，并输出结构化的JSON。

## 任务说明
请仔细阅读以下招股说明书候选文本，识别其中记载的每一次外部融资事件（包括增资、股权转让、出资认缴等），并将提取结果以严格的JSON格式返回。

## JSON Schema 定义
请严格按照以下结构输出JSON，所有字段均为必填（若无法从文本中获取，则填null）：

```json
{
  "company": {
    "company_name": "公司全称（字符串）",
    "stock_code": "股票代码（字符串）",
    "exchange": "上市交易所（字符串）",
    "board": "上市板块（字符串）",
    "listing_date": "上市日期（字符串，格式YYYY-MM-DD）",
    "prospectus_title": "招股书标题（字符串）",
    "prospectus_url": "招股书URL（字符串）",
    "prospectus_version": "招股书版本（字符串）",
    "prospectus_date": "招股书日期（字符串，格式YYYY-MM-DD）"
  },
  "financing_events": [
    {
      "event_order": 1,
      "event_date": "融资事件发生日期（字符串，格式YYYY-MM-DD或YYYY-MM或YYYY）",
      "date_type": "日期类型（精确日期/月份/年份/未披露）",
      "event_type": "事件类型（增资/股权转让/增资+股权转让/出资认购/其他）",
      "disclosed_round": "招股书中披露的融资轮次名称（字符串，如无则填null）",
      "inferred_round": "根据投资时间和金额推断的融资轮次（字符串，如A轮、B轮、Pre-IPO等，如无法推断则填null）",
      "total_investment_amount": "本次融资总金额（数字，单位为万元人民币，如无法确定则填null）",
      "currency": "货币类型（CNY/USD/其他）",
      "share_price": "每股价格（数字，单位为元/股，如无则填null）",
      "pre_valuation": "投前估值（数字，单位为万元，如无则填null）",
      "post_valuation": "投后估值（数字，单位为万元，如无则填null）",
      "investors": [
        {
          "investor_name": "投资者名称（字符串）",
          "investor_type": "投资者类型（PE机构/VC机构/天使投资人/产业资本/政府引导基金/个人/其他）",
          "investment_amount": "该投资者的投资金额（数字，单位为万元，如无则填null）",
          "share_percentage": "该投资者获得的持股比例（数字，百分比，如3.5表示3.5%，如无则填null）",
          "share_count": "该投资者获得的股份数量（数字，单位为股，如无则填null）",
          "share_price": "该投资者的每股价格（数字，单位为元/股，如无则填null）"
        }
      ],
      "total_shares_issued": "本次发行/转让的总股份数（数字，单位为股，如无则填null）",
      "evidence_text": "招股书中支持该事件提取的原文片段（字符串，尽量完整引用）",
      "extraction_notes": "提取备注（字符串，标注任何不确定或需要人工复核的地方）"
    }
  ],
  "processing": {
    "extraction_method": "llm",
    "model_name": "使用的模型名称",
    "prompt_version": "v1",
    "extraction_status": "success/partial/failed",
    "review_status": "待复核",
    "notes": "整体提取备注"
  }
}
```

## 抽取规则
1. **只提取外部融资事件**：排除以下类型的事件：
   - 公司内部股东之间的股权调整（如员工持股平台内部份额调整）
   - 子公司层面的融资事件（除非明确涉及母公司层面的PE/VC投资）
   - 红利转增、资本公积转增等非融资性事件
   - 重复记载的同一事件（同一时间、同一批投资者、同一金额只计为一条）
2. **区分事件类型**：
   - "增资"：投资者向公司新增出资，公司注册资本增加
   - "股权转让"：现有股东将所持股份转让给新投资者，公司注册资本不变
   - "增资+股权转让"：同一事件中同时包含增资和股权转让
   - "出资认购"：投资者认购新增出资份额
3. **识别外部PE/VC投资者**：
   - 关注名称中包含"投资""资本""基金""创投""资产管理"等关键词的机构
   - 关注知名的PE/VC机构名称（如红杉、深创投、达晨、高瓴等）
   - 个人投资者如果是知名天使投资人也应提取
   - 公司创始人、员工、关联方不视为外部PE/VC投资者
4. **金额处理**：
   - 将所有金额统一转换为万元人民币
   - 如原文为美元，按汇率折算（如未披露汇率，按1美元=7万元人民币估算）
   - 如原文只给出估值范围，取中间值
5. **时间处理**：
   - 按时间先后排列事件，event_order从1开始递增
   - 如原文只给出年份，date_type填"年份"
   - 如原文给出年月，date_type填"月份"
   - 如原文给出完整日期，date_type填"精确日期"

## 输出要求
- 只输出合法的JSON，不要输出任何其他文本、解释或markdown标记
- JSON必须可被Python的json.loads()正确解析
- 所有中文字段值使用中文
- 如果候选文本中没有找到任何融资事件，financing_events返回空列表[]
"""


def extract_pevc_info_by_llm(candidate_text, company_info, api_key=None, model="deepseek-chat"):
    """
    使用 LLM（OpenAI 兼容 API）从候选文本中提取 PE/VC 融资信息。

    参数:
        candidate_text (str): 招股说明书候选文本
        company_info (dict): 公司信息字典，至少包含 company_name, stock_code 等字段
        api_key (str|None): API 密钥，若为 None 则从环境变量 DEEPSEEK_API_KEY 获取
        model (str): 模型名称，默认为 deepseek-chat，也可使用 gpt-4o、qwen-plus 等

    返回:
        dict: 包含 company / financing_events / processing 三层结构的字典，
              与 rule-based 方法的输出格式兼容。
    """
    import os

    if api_key is None:
        api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        raise ValueError(
            "未提供 API 密钥。请通过参数传入 api_key，或设置环境变量 DEEPSEEK_API_KEY。"
        )

    # ---- 1. 构造 system prompt ----
    system_prompt = EXTRACTION_PROMPT_TEMPLATE

    # ---- 2. 构造 user prompt ----
    company_name = company_info.get("company_name", "未知公司")
    stock_code = company_info.get("stock_code", "未知代码")
    exchange = company_info.get("exchange", "")
    board = company_info.get("board", "")
    listing_date = company_info.get("listing_date", "")
    prospectus_title = company_info.get("prospectus_title", "")
    prospectus_url = company_info.get("prospectus_url", "")
    prospectus_version = company_info.get("prospectus_version", "")
    prospectus_date = company_info.get("prospectus_date", "")

    user_prompt = f"""\
请从以下招股说明书候选文本中提取所有外部PE/VC融资事件。

## 公司基本信息
- 公司全称：{company_name}
- 股票代码：{stock_code}
- 上市交易所：{exchange}
- 上市板块：{board}
- 上市日期：{listing_date}
- 招股书标题：{prospectus_title}
- 招股书URL：{prospectus_url}
- 招股书版本：{prospectus_version}
- 招股书日期：{prospectus_date}

## 候选文本
{candidate_text}

请严格按照JSON Schema输出结构化JSON。只输出JSON，不要输出任何其他文本。"""

    # ---- 3. 调用 OpenAI 兼容 API ----
    api_url = "https://api.deepseek.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.1,       # 低温度，减少随机性，提高抽取稳定性
        "max_tokens": 8192,       # 融资事件JSON可能较长
        "response_format": {"type": "json_object"},  # 要求模型返回合法JSON
    }

    resp = requests.post(api_url, headers=headers, json=payload, timeout=120)
    resp.raise_for_status()
    resp_data = resp.json()

    # ---- 4. 提取模型返回的文本内容 ----
    try:
        content = resp_data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"API 返回格式异常: {e}\n原始返回: {resp_data}")

    # ---- 5. 解析并校验 JSON ----
    try:
        result = json.loads(content)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"模型返回的不是合法JSON: {e}\n原始内容前500字符: {content[:500]}")

    # 校验顶层结构
    required_top_keys = {"company", "financing_events", "processing"}
    if not required_top_keys.issubset(result.keys()):
        missing = required_top_keys - set(result.keys())
        raise RuntimeError(f"JSON 缺少必要顶层字段: {missing}")

    # 确保 financing_events 是列表
    if not isinstance(result["financing_events"], list):
        raise RuntimeError("financing_events 字段必须是列表")

    # 为每个 event 补充默认值，确保字段完整
    event_required_fields = [
        "event_order", "event_date", "date_type", "event_type",
        "disclosed_round", "inferred_round", "total_investment_amount",
        "currency", "share_price", "pre_valuation", "post_valuation",
        "investors", "total_shares_issued", "evidence_text", "extraction_notes",
    ]
    investor_required_fields = [
        "investor_name", "investor_type", "investment_amount",
        "share_percentage", "share_count", "share_price",
    ]
    for idx, event in enumerate(result["financing_events"]):
        for field in event_required_fields:
            event.setdefault(field, None)
        # 确保 investors 是列表
        if not isinstance(event.get("investors"), list):
            event["investors"] = []
        for inv in event["investors"]:
            for field in investor_required_fields:
                inv.setdefault(field, None)

    # 填充 processing 信息
    result["processing"].setdefault("extraction_method", "llm")
    result["processing"].setdefault("model_name", model)
    result["processing"].setdefault("prompt_version", "v1")
    result["processing"].setdefault("extraction_status", "success" if result["financing_events"] else "partial")
    result["processing"].setdefault("review_status", "待复核")
    result["processing"].setdefault("notes", "")

    # 填充 company 信息（以 company_info 为准，防止模型编造）
    company = result.get("company", {})
    company["company_name"] = company_name
    company["stock_code"] = stock_code
    company["exchange"] = exchange
    company["board"] = board
    company["listing_date"] = listing_date
    company["prospectus_title"] = prospectus_title
    company["prospectus_url"] = prospectus_url
    company["prospectus_version"] = prospectus_version
    company["prospectus_date"] = prospectus_date
    result["company"] = company

    return result


# ============================================================================
# 演示：选择 rule-based 或 llm 模式运行
# ============================================================================
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="PE/VC 融资信息抽取工具")
    parser.add_argument(
        "--mode",
        choices=["rule", "llm"],
        default="rule",
        help="抽取模式: rule=正则规则抽取（baseline）, llm=大模型抽取",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="LLM 模式的 API 密钥（也可通过环境变量 DEEPSEEK_API_KEY 设置）",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="deepseek-chat",
        help="LLM 模型名称（默认 deepseek-chat）",
    )
    parser.add_argument(
        "--company",
        type=str,
        default=None,
        help="指定抽取某一家公司（股票代码），不指定则批量处理全部",
    )
    args = parser.parse_args()

    if args.mode == "rule":
        print("=" * 60)
        print("模式: rule-based（正则规则抽取 baseline）")
        print("=" * 60)
        # rule-based 批量处理逻辑已在上方主体代码中实现
        # 此处直接运行主体逻辑（由上方代码自动执行）

    elif args.mode == "llm":
        print("=" * 60)
        print(f"模式: LLM 抽取（模型: {args.model}）")
        print("=" * 60)

        # 读取企业清单
        llm_companies = []
        with open(COMPANY_LIST, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                llm_companies.append(row)

        # 如果指定了某家公司，则只处理该家公司
        if args.company:
            llm_companies = [c for c in llm_companies if c["stock_code"] == args.company]
            if not llm_companies:
                print(f"未找到股票代码为 {args.company} 的公司")
                exit(1)

        print(f"共 {len(llm_companies)} 家公司待抽取\n")

        llm_results = []
        for company in llm_companies:
            code = company["stock_code"]
            name = company["company_name"]
            print(f"LLM 抽取: {name} ({code})")

            # 查找候选文本文件
            candidate_file = None
            for f in INPUT_DIR.glob(f"{code}*候选文本.md"):
                candidate_file = f
                break

            if not candidate_file:
                print(f"  失败: 候选文本文件不存在")
                llm_results.append({
                    "code": code, "name": name,
                    "status": "fail", "events": 0,
                    "file": "", "error": "候选文本文件不存在",
                })
                continue

            with open(candidate_file, "r", encoding="utf-8") as f:
                candidate_text = f.read()

            try:
                result = extract_pevc_info_by_llm(
                    candidate_text, company,
                    api_key=args.api_key,
                    model=args.model,
                )
                events_count = len(result["financing_events"])

                # 保存 JSON
                output_file = OUTPUT_DIR / f"{code}_{name.split('股份')[0]}_pevc_info.json"
                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)

                print(f"  事件数: {events_count} -> {output_file.name}")
                llm_results.append({
                    "code": code, "name": name,
                    "status": "success" if events_count > 0 else "partial",
                    "events": events_count,
                    "file": str(output_file),
                    "error": "",
                })
            except Exception as e:
                print(f"  失败: {e}")
                llm_results.append({
                    "code": code, "name": name,
                    "status": "fail", "events": 0,
                    "file": "", "error": str(e),
                })

        # 更新企业清单
        rows = []
        with open(COMPANY_LIST, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                for r in llm_results:
                    if row["stock_code"] == r["code"]:
                        if r["status"] == "success":
                            row["extract_status"] = "success"
                        elif r["status"] == "partial":
                            row["extract_status"] = "partial"
                        else:
                            row["extract_status"] = "fail"
                rows.append(row)

        with open(COMPANY_LIST, "w", encoding="utf-8", newline="") as f:
            csv.DictWriter(f, fieldnames=rows[0].keys()).writeheader()
            csv.DictWriter(f, fieldnames=rows[0].keys()).writerows(rows)

        print("\n企业清单已更新")

        # 更新日志
        log_exists = LOG_FILE.exists()
        with open(LOG_FILE, "a", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            if not log_exists:
                w.writerow([
                    "company_name", "stock_code", "candidate_text_path",
                    "model_name", "prompt_version", "json_path",
                    "status", "error_message",
                ])
            for r in llm_results:
                w.writerow([
                    r["name"], r["code"],
                    f"outputs/week1_candidate_texts/{r['code']}_候选文本.md",
                    args.model, "v1", r["file"],
                    r["status"], r["error"],
                ])

        print("抽取日志已更新")
        print(f"\n完成: {sum(1 for x in llm_results if x['status'] == 'success')}/{len(llm_results)}")
