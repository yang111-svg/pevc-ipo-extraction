# Week 1：公共样本最小闭环报告

## 1. 本周目标
- **目标**: 处理8个公共样本，跑通至少1家公司从PDF到JSON的完整闭环。
- **实际完成**: 8家公司全部完成PDF下载、解析、章节定位、候选文本截取、JSON输出和校验，全部通过验证。

## 2. 公共样本处理情况

| sample_id | 公司 | 下载 | 解析 | 章节定位 | 候选文本 | JSON输出 | 人工复核 | 问题 |
|-----------|------|------|------|----------|----------|----------|----------|------|
| MB001 | 三联锻造 | success | success | success | success | success (13个事件) | unchecked | |
| MB002 | 友升股份 | success | success | success | success | success (11个事件) | unchecked | |
| GEM001 | 黄山谷捷 | success | success | success | success | success (9个事件) | unchecked | |
| GEM002 | 云汉芯城 | success | success | success | success | success (11个事件) | unchecked | |
| STAR001 | 赛分科技 | success | success | success | success | success (14个事件) | unchecked | |
| STAR002 | 影石创新 | success | success | success | success | success (9个事件) | unchecked | |
| BSE001 | 三协电机 | success | success | success | success | success (14个事件) | unchecked | |
| BSE002 | 星图测控 | success | success | success | success | success (4个事件) | unchecked | |

## 3. 招股说明书来源

### 使用的网站
- 巨潮资讯网 (cninfo.com.cn) - 主板、创业板、科创板样本
- 北京证券交易所官网 (bse.cn) - 北交所样本

### 检索路径
1. 巨潮资讯: 搜索 "股票代码 公司简称 招股说明书"
2. 北交所: 信息披露 → 搜索股票代码

### 文件筛选规则
- 确认文件标题包含 "招股说明书"
- 排除 "上市公告书"、"发行公告"、"问询回复" 等非目标文件
- 优先选择正式稿或注册稿

### 网站收集方法文档
- 文件路径: `source_notes/website_collection_method.md`
- 内容: 详细记录了巨潮资讯、北交所等网站的检索方法、文件筛选规则、链接失效处理方式

## 4. 代码说明

### 下载代码
- 文件路径: `code/03_download_pdfs/`
- 说明: 第一周采用手动下载方式，后续可补充自动化脚本

### 解析代码
- 文件路径: `code/04_parse_pdf_to_markdown/`
- 说明: 使用MinerU (pypdfium2) 将PDF解析为Markdown格式，完整解析所有页面
- 关键文件: `full_parse.py` - 完整解析脚本

### 定位代码
- 文件路径: `code/05_locate_relevant_sections/`
- 说明: 使用正则表达式匹配章节标题和关键词，定位历史沿革、股本形成、增资、股权转让等相关章节
- 关键文件: `locate.py` - 章节定位脚本

### 抽取代码
- 文件路径: `code/06_extract_pevc_info/`
- 说明: 使用规则匹配从候选文本中提取融资事件信息
- 关键文件: `extract.py` - 信息抽取脚本

### 校验代码
- 文件路径: `code/07_validate_outputs/`
- 说明: 检查JSON文件必需字段完整性
- 关键文件: `validate.py` - 输出校验脚本

### 如何运行
```bash
# 解析PDF
cd code/04_parse_pdf_to_markdown
python full_parse.py

# 定位章节
cd code/05_locate_relevant_sections
python locate.py

# 抽取信息
cd code/06_extract_pevc_info
python extract.py

# 校验输出
cd code/07_validate_outputs
python validate.py
```

## 5. JSON样例

- **文件路径**: `outputs/week1_sample_json/`
- **字段是否完整**: 基本完整，包含公司信息、融资事件、处理状态
- **是否有证据文本**: 是，每个融资事件包含evidence_text字段

### 示例JSON结构（完整字段示范 - 赛分科技）
```json
{
  "company": {
    "company_name": "苏州赛分科技股份有限公司",
    "stock_code": "688758",
    "exchange": "SSE",
    "board": "科创板",
    "listing_date": "2025-01-15",
    "prospectus_title": "赛分科技首次公开发行股票并在科创板上市招股说明书",
    "prospectus_url": "https://static.cninfo.com.cn/finalpage/2025-01-06/1222238930.PDF",
    "prospectus_version": "正式稿",
    "prospectus_date": "2025-01-06"
  },
  "financing_events": [
    {
      "event_order": 1,
      "event_date": "2015-07",
      "date_type": "协议签署日",
      "event_type": "增资",
      "disclosed_round": "未披露",
      "inferred_round": "",
      "round_inference_basis": "",
      "total_investment_amount": null,
      "currency": "CNY",
      "share_price": null,
      "pre_money_valuation": null,
      "post_money_valuation": null,
      "valuation_basis": "",
      "investors": [
        {
          "investor_original_name": "高新同华",
          "investor_short_name": "高新同华",
          "investor_type": "PE",
          "is_pevc": "yes",
          "investment_amount": null,
          "shares_acquired": null,
          "shareholding_ratio_after_event": null,
          "exit_status_before_ipo": "未退出"
        }
      ],
      "source_section": "第五节 发行人基本情况 - 三、发行人股本演变情况",
      "source_page": "",
      "evidence_text": "2015年7月签署《投资合作框架协议》...",
      "confidence": "medium"
    }
  ],
  "processing": {
    "download_status": "success",
    "parse_status": "success",
    "locate_status": "success",
    "extract_status": "success",
    "review_status": "unchecked",
    "notes": "示范样例：按任务书建议的完整JSON结构手动补充"
  }
}
```

**完整JSON文件**: `outputs/week1_sample_json/688758_苏州赛分科技_pevc_info.json`
- 包含8个融资事件、20个投资方
- 识别出A+轮、B轮、C轮融资轮次
- 未披露的信息标注为null，未编造数据

## 6. 失败案例

| 公司 | 环节 | 问题 | 当前处理 |
|------|------|------|----------|
| 无 | - | 8家公司全部成功提取到融资事件 | - |

## 7. 本周形成的规则

### 文件识别规则
- 优先选择正式稿或注册稿
- 确认文件标题包含"招股说明书"
- 排除上市公告书、发行公告等非目标文件

### 章节定位规则
- 推荐章节: 发行人基本情况、历史沿革、股本形成及变化、历次增资、历次股权转让、股东情况
- 关键词匹配: 历史沿革、股本形成、增资、股权转让、股东情况、股本演变、股权结构、投资者

### 关键词列表
- 增资、股权转让、出资、认购、入股、投资者、外部投资者、财务投资者、风险投资、私募股权、创投、创业投资、产业基金、股权投资基金、合伙企业、员工持股平台、PE、VC、投前估值、投后估值、估值、股份锁定

### JSON字段规则
- 公司信息: company_name, stock_code, exchange, board, listing_date, prospectus_title, prospectus_url, prospectus_version, prospectus_date
- 融资事件（完整结构）:
  - event_order: 事件序号
  - event_date: 事件日期
  - date_type: 协议签署日/工商变更日/股东会决议日/未说明
  - event_type: 增资/股权转让/增资及股权转让/其他
  - disclosed_round: 披露轮次（未披露时填"未披露"）
  - inferred_round: 推断轮次（AI推断时填写）
  - round_inference_basis: 推断依据
  - total_investment_amount: 投资总额（万元）
  - currency: 币种（CNY）
  - share_price: 每股价格
  - pre_money_valuation: 投前估值
  - post_money_valuation: 投后估值
  - valuation_basis: 估值依据
  - investors: 投资方数组（含investor_original_name, investor_short_name, investor_type, is_pevc, investment_amount, shares_acquired, shareholding_ratio_after_event, exit_status_before_ipo）
  - source_section: 来源章节
  - source_page: 来源页码
  - evidence_text: 证据文本（必须保留原文）
  - confidence: 置信度（high/medium/low）
- 处理状态: download_status, parse_status, locate_status, extract_status, review_status, notes

## 8. 团队成员分工

| 成员 | 负责公司 | 主要工作 |
|------|----------|----------|
| 杨苗鑫 | 三联锻造、黄山谷捷、赛分科技、三协电机 | PDF下载、解析、候选文本截取、JSON抽取 |
| 赵秉清 | 友升股份、云汉芯城、影石创新、星图测控 | PDF下载、解析、候选文本截取、JSON抽取 |

## 9. 下周计划

- 进行人工复核，验证抽取结果的准确性
- 补充完善投资方名称、融资金额等字段
- 准备组内互查
- 优化抽取规则，提高字段识别准确率
