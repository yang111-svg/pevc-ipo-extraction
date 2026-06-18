# PE/VC上市前投资信息抽取项目：四周任务书

> 适用对象：四个研究生小组，每组2名学生。  
> 分组方向：主板组、创业板组、科创板组、北交所组。  
> 提交平台：GitHub。  
> 项目周期：4周。  
> 每周提交时间：周五，以 GitHub Pull Request 为准。  
> 当前阶段成果边界：本月不要求提交完整PE/VC数据库，但必须提交企业清单、数据来源、全过程代码、日志、样本JSON、互查记录和最终汇报。

---

## 1. 项目背景与总目标

本项目目标是利用AI工具和程序化流程，从上市公司招股说明书中识别并提取其上市前PE/VC投资相关信息，形成可复核、可扩展、可继续全量化的数据处理流程。

招股说明书通常包含企业设立、历次增资、股权转让、外部投资者进入、发行前股东结构、估值、股份锁定、退出安排等信息。项目的核心不是简单下载PDF，也不是让AI直接通读整本招股书，而是训练大家完成如下完整链条：

```text
企业清单构建
    ↓
招股说明书来源确认
    ↓
PDF下载与文件识别
    ↓
PDF解析为Markdown或文本
    ↓
目录识别与相关章节定位
    ↓
关键词检索与候选文本截取
    ↓
融资事件与投资方信息抽取
    ↓
结构化JSON输出
    ↓
字段校验与异常记录
    ↓
人工复核与小组互查
    ↓
问题总结与后续全量扩展方案
```

项目最终希望形成一套可以继续扩展到所有上市公司的流程。四周内重点考核流程是否清楚、代码是否可复现、来源是否可靠、日志是否完整、错误是否被记录、结果是否可复核。

---

## 2. 分组与研究范围

| 组别 | 负责市场 | 说明 |
|---|---|---|
| A组 | 主板 | 包括上交所主板、深交所主板。企业清单需要明确交易所与板块。 |
| B组 | 创业板 | 深交所创业板。重点关注创业板招股书披露结构与历史沿革章节。 |
| C组 | 科创板 | 上交所科创板。重点关注科创企业融资历史、机构投资者和估值披露。 |
| D组 | 北交所 | 北京证券交易所上市公司。可记录上市前新三板挂牌、定增、外部投资者进入等路径信息。 |

每组2名学生。组内成员可以分工，但每名学生都必须有GitHub提交记录、日志记录和互查贡献。

---

## 3. 本月不要求与必须要求

### 3.1 本月不要求

本月不要求提交完整的PE/VC投资数据库，也不要求上传全部PDF或全部Markdown解析文件。

具体来说，本月不要求：

```text
1. 不要求完成所有上市公司的PE/VC数据抽取。
2. 不要求把所有原始PDF上传到GitHub。
3. 不要求把所有解析后的Markdown文件上传到GitHub。
4. 不要求保证每家公司都能成功提取完整投资事件。
5. 不要求完成投资机构标准化匹配。
6. 不要求强行判断A轮、B轮、C轮等融资轮次。
```

### 3.2 本月必须要求

本月必须提交：

```text
1. 企业清单 company_list.csv。
2. 企业清单来源说明。
3. 招股说明书获取方法。
4. 下载、解析、定位、抽取、校验代码。
5. 运行日志。
6. 失败案例。
7. 第一周公共样本的最小闭环结果。
8. 第三周组内互查记录。
9. 第四周组间检查记录。
10. 最终presentation。
```

---

## 4. GitHub提交规范

### 4.1 仓库结构

每组一个GitHub仓库，建议命名为：

```text
team-mainboard
team-chinext
team-star
team-bse
```

每组仓库必须采用以下结构：

```text
team-xxx/
  README.md

  company_lists/
    week1_public_samples.csv
    week2_2025_company_list.csv
    week3_extended_company_list.csv

  source_notes/
    data_sources.md
    prospectus_download_method.md
    website_collection_method.md
    version_rules.md

  code/
    01_build_company_list/
    02_fetch_prospectus_urls/
    03_download_pdfs/
    04_parse_pdf_to_markdown/
    05_locate_relevant_sections/
    06_extract_pevc_info/
    07_validate_outputs/

  outputs/
    week1_sample_json/
    week1_candidate_texts/
    week2_sample_outputs/
    week3_sample_outputs/

  logs/
    download_log.csv
    parse_log.csv
    locate_log.csv
    extraction_log.csv
    validation_log.csv
    error_cases.md

  review/
    week3_intra_group_review.csv
    week4_inter_group_review_given.csv
    week4_inter_group_review_received.csv

  weekly_reports/
    week1.md
    week2.md
    week3.md
    week4.md

  presentation/
    final_presentation.pptx
    final_presentation.pdf
```

### 4.2 GitHub Pull Request要求

每周五每组提交一个Pull Request。PR标题格式固定：

```text
[Week 1][主板组] 公共样本最小闭环提交
[Week 2][创业板组] 2025年样本与市场级流程提交
[Week 3][科创板组] 历史年份扩展与组内互查提交
[Week 4][北交所组] 组间检查与最终汇报提交
```

PR说明必须包括：

```markdown
## 本周提交内容

### 1. 企业清单
- 文件路径：
- 样本范围：
- 数据来源：

### 2. 代码
- 新增脚本：
- 修改脚本：
- 如何运行：

### 3. 日志
- 下载日志：
- 解析日志：
- 定位日志：
- 抽取/校验日志：

### 4. 样本结果
- JSON样例路径：
- 候选文本路径：
- 人工复核路径：

### 5. 主要问题
- 问题1：
- 问题2：
- 问题3：

### 6. 需要老师确认的问题
- 问题1：
```

### 4.3 禁止事项

```text
1. 禁止只交微信群文字总结。
2. 禁止只交截图。
3. 禁止最后一天一次性上传、没有过程记录。
4. 禁止把公告、问询回复、上市公告书误当作招股说明书。
5. 禁止把整本招股书直接扔给大模型后不做定位和复核。
6. 禁止编造未披露的融资轮次、估值或投资方类型。
7. 禁止只提交结果、不提交代码和日志。
```

---

## 5. 企业清单 company_list.csv 字段

每组必须维护企业清单。建议字段如下：

```csv
sample_id,company_name,stock_code,exchange,board,listing_date,ipo_year,source_platform,source_page_url,prospectus_title,prospectus_url,prospectus_version,prospectus_date,download_status,parse_status,locate_status,extract_status,review_status,notes
```

字段说明：

| 字段 | 说明 |
|---|---|
| sample_id | 样本编号，例如 MB001、GEM001、STAR001、BSE001。 |
| company_name | 公司名称。尽量使用招股说明书披露的发行人全称。 |
| stock_code | 股票代码。 |
| exchange | SSE / SZSE / BSE。 |
| board | 主板 / 创业板 / 科创板 / 北交所。 |
| listing_date | 上市日期。必须说明来源。 |
| ipo_year | 上市年份。第二周必须为2025。 |
| source_platform | 上交所、深交所、北交所、巨潮资讯、中证网等。 |
| source_page_url | 企业list或披露文件来源页。 |
| prospectus_title | 招股说明书标题。 |
| prospectus_url | 招股说明书链接。 |
| prospectus_version | 正式稿 / 注册稿 / 申报稿 / 招股意向书等。 |
| prospectus_date | 招股说明书披露日期。 |
| download_status | success / fail / duplicate / wrong_file。 |
| parse_status | success / partial / fail。 |
| locate_status | success / partial / fail。 |
| extract_status | success / partial / fail / not_required。 |
| review_status | unchecked / pass / revise / fail。 |
| notes | 异常说明。 |

---

## 6. 第一周公共样本

第一周所有组处理同一批公共样本。下面8家公司覆盖主板、创业板、科创板、北交所，每个板块2家公司。

> 注意：以下样本为公共训练样本。学生提交前必须自行到交易所、巨潮资讯或法定信息披露平台复核上市日期、招股说明书版本和下载链接。若链接失效，以交易所或巨潮资讯检索结果为准，并在 `source_notes/data_sources.md` 中说明替换原因。

| sample_id | 板块 | 公司简称 | 公司全称 | 股票代码 | 建议检索入口 | 训练目的 |
|---|---|---|---|---|---|---|
| MB001 | 主板 | 天和磁材 | 包头天和磁材科技股份有限公司 | 603072 | 上交所IPO信息专区，检索“603072 天和磁材 招股说明书” | 主板样本；检查历史沿革、增资、股权转让信息。 |
| MB002 | 主板 | 友升股份 | 上海友升铝业股份有限公司 | 603418 | 上交所IPO信息专区，检索“603418 友升股份 招股说明书” | 主板样本；检查企业清单、文件版本和章节定位。 |
| GEM001 | 创业板 | 黄山谷捷 | 黄山谷捷股份有限公司 | 301581 | 深交所/巨潮资讯，检索“301581 黄山谷捷 招股说明书” | 创业板样本；适合练习正式招股说明书与上市公告书区分。 |
| GEM002 | 创业板 | 云汉芯城 | 云汉芯城（上海）互联网科技股份有限公司 | 301563 | 深交所/巨潮资讯，检索“301563 云汉芯城 招股说明书” | 创业板样本；适合练习外部投资者和股东结构识别。 |
| STAR001 | 科创板 | 赛分科技 | 苏州赛分科技股份有限公司 | 688758 | 上交所IPO信息专区，检索“688758 赛分科技 招股说明书” | 科创板样本；适合练习多轮融资和股权演变字段。 |
| STAR002 | 科创板 | 影石创新 | 影石创新科技股份有限公司 | 688775 | 上交所IPO信息专区，检索“688775 影石创新 招股说明书” | 科创板样本；适合练习VC/PE投资方识别与证据保留。 |
| BSE001 | 北交所 | 三协电机 | 常州三协电机股份有限公司 | 920100 | 北交所/法定信息披露平台/巨潮资讯，检索“920100 三协电机 招股说明书” | 北交所样本；适合练习私募基金股东、创业投资企业和发行前股东结构识别。 |
| BSE002 | 北交所 | 大鹏工业 | 哈尔滨岛田大鹏工业股份有限公司 | 920091 | 北交所/巨潮资讯，检索“920091 大鹏工业 招股说明书” | 北交所样本；适合练习北交所历史审核、多版本招股书识别。 |

> 说明：三协电机用于替代原备选样本“星图测控”。三协电机招股书中有较清晰的私募基金/创业投资股东披露，作为第一周北交所正样本更合适。

### 第一周样本处理要求

每组必须对8家公司完成以下事项：

```text
1. 建立公共样本 company_list。
2. 找到并记录每家公司的招股说明书来源。
3. 下载PDF或记录可下载URL。
4. 判断文件是否为目标招股说明书。
5. 解析PDF为Markdown或文本。
6. 提取目录或章节标题。
7. 定位至少一个与融资历史、股权演变、历次增资、股权转让、股东情况相关的章节。
8. 截取候选文本。
9. 至少完成4家公司结构化JSON输出。
10. 每名学生至少完整负责2家公司。
```

第一周最低合格线：每组至少展示1家公司从PDF到结构化JSON的完整闭环。完整目标：8家公司全部跑完候选文本定位，至少4家公司输出JSON。

---

## 7. 建议JSON结构

第一周输出JSON时，不追求完美，但必须有层级结构、证据文本和来源位置。

```json
{
  "company": {
    "company_name": "",
    "stock_code": "",
    "exchange": "",
    "board": "",
    "listing_date": "",
    "prospectus_title": "",
    "prospectus_url": "",
    "prospectus_version": "",
    "prospectus_date": ""
  },
  "financing_events": [
    {
      "event_order": 1,
      "event_date": "",
      "date_type": "协议签署日/工商变更日/股东会决议日/未说明",
      "event_type": "增资/股权转让/增资及股权转让/其他",
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
          "investor_original_name": "",
          "investor_short_name": "",
          "investor_type": "VC/PE/产业资本/自然人/员工持股平台/政府基金/其他/无法判断",
          "is_pevc": "yes/no/uncertain",
          "investment_amount": null,
          "shares_acquired": null,
          "shareholding_ratio_after_event": null,
          "exit_status_before_ipo": "未退出/部分退出/全部退出/无法判断"
        }
      ],
      "source_section": "",
      "source_page": "",
      "evidence_text": "",
      "confidence": "high/medium/low"
    }
  ],
  "processing": {
    "download_status": "success/partial/fail",
    "parse_status": "success/partial/fail",
    "locate_status": "success/partial/fail",
    "extract_status": "success/partial/fail",
    "review_status": "unchecked/pass/revise/fail",
    "notes": ""
  }
}
```

重要要求：

```text
1. 招股书没有披露的信息，不得编造。
2. 未披露融资轮次时，disclosed_round 填“未披露”。
3. 如果AI推断融资轮次，必须填写 inferred_round 和 round_inference_basis。
4. 投资总额、每股价格、投前估值、投后估值必须分开。
5. 投资方原始名称必须保留。
6. 每条融资事件必须有 evidence_text。
7. 每条融资事件必须尽量记录 source_section 或 source_page。
```

---

## 8. 每周分阶段目标与提交要求

## Week 1：统一样本、跑通最小闭环

### 8.1 Week 1目标

第一周不是追求数量，而是跑通从PDF到结构化JSON的最小闭环。所有组处理同一批8个公共样本，目的是统一字段、统一流程、统一证据标准。

本周要回答的问题：

```text
1. 企业清单如何建立？
2. 招股说明书从哪里下载？
3. 如何判断文件是不是目标招股说明书？
4. PDF如何解析为Markdown或文本？
5. 融资历史通常出现在哪些章节？
6. 如何截取候选文本？
7. 如何让AI输出JSON？
8. 如何校验JSON是否合格？
9. 失败样本如何记录？
```

### 8.2 Week 1必须提交

```text
company_lists/week1_public_samples.csv
source_notes/data_sources.md
source_notes/prospectus_download_method.md
code/03_download_pdfs/
code/04_parse_pdf_to_markdown/
code/05_locate_relevant_sections/
code/06_extract_pevc_info/
code/07_validate_outputs/
outputs/week1_candidate_texts/
outputs/week1_sample_json/
logs/download_log.csv
logs/parse_log.csv
logs/locate_log.csv
logs/extraction_log.csv
logs/validation_log.csv
logs/error_cases.md
weekly_reports/week1.md
```

### 8.3 Week 1周报模板

```markdown
# Week 1：公共样本最小闭环报告

## 1. 本周目标
- 目标：处理8个公共样本，跑通至少1家公司从PDF到JSON的完整闭环。
- 实际完成：

## 2. 公共样本处理情况
| sample_id | 公司 | 下载 | 解析 | 章节定位 | 候选文本 | JSON输出 | 人工复核 | 问题 |
|---|---|---|---|---|---|---|---|---|

## 3. 招股说明书来源
- 使用的网站：
- 检索路径：
- 文件筛选规则：

## 4. 代码说明
- 下载代码：
- 解析代码：
- 定位代码：
- 抽取代码：
- 校验代码：
- 如何运行：

## 5. JSON样例
- 文件路径：
- 字段是否完整：
- 是否有证据文本：

## 6. 失败案例
| 公司 | 环节 | 问题 | 当前处理 |
|---|---|---|---|

## 7. 本周形成的规则
- 文件识别规则：
- 章节定位规则：
- 关键词列表：
- JSON字段规则：
```

### 8.4 Week 1验收标准

| 项目 | 要求 |
|---|---|
| 公共样本清单 | 8家公司完整列出，含来源。 |
| 下载与来源 | 至少能说明招股书从哪里获取。 |
| PDF解析 | 至少部分样本完成Markdown或文本解析。 |
| 章节定位 | 能定位历史沿革、股本形成、历次增资、股权转让等章节。 |
| JSON输出 | 至少1家公司完整闭环；建议至少4家公司输出JSON。 |
| 日志 | 必须记录失败样本和失败原因。 |
| GitHub | 必须通过PR提交，不能只交文字总结。 |

---

## Week 2：按市场专攻，只做2025年样本，形成市场级处理流程

### 8.5 Week 2目标

第二周开始按市场分工。每组负责一个市场，只处理2025年上市公司。目标是从第一周的公共样本实验进入市场级小规模批处理。

| 组别 | Week 2范围 |
|---|---|
| 主板组 | 2025年主板上市公司。 |
| 创业板组 | 2025年创业板上市公司。 |
| 科创板组 | 2025年科创板上市公司。 |
| 北交所组 | 2025年北交所上市公司。 |

本周核心不是最终数据数量，而是形成本市场的企业list、来源规则、下载规则、解析规则和章节定位规则。

### 8.6 Week 2必须提交

```text
company_lists/week2_2025_company_list.csv
source_notes/2025_company_list_source.md
source_notes/prospectus_download_method.md
source_notes/version_rules.md
code/01_build_company_list/
code/02_fetch_prospectus_urls/
code/03_download_pdfs/
code/04_parse_pdf_to_markdown/
code/05_locate_relevant_sections/
code/06_extract_pevc_info/
code/07_validate_outputs/
outputs/week2_sample_outputs/
logs/download_log.csv
logs/parse_log.csv
logs/locate_log.csv
logs/extraction_log.csv
logs/validation_log.csv
logs/error_cases.md
weekly_reports/week2.md
```

### 8.7 Week 2企业list要求

每组必须提交本板块2025年上市公司的完整清单。清单必须说明：

```text
1. 2025年上市公司数量。
2. 企业名单从哪里获得。
3. 是否使用交易所官方入口。
4. 是否用巨潮资讯或其他平台交叉核对。
5. 招股说明书链接如何获取。
6. 如何排除上市公告书、发行公告、问询回复、提示性公告等非目标文件。
```

### 8.8 Week 2周报模板

```markdown
# Week 2：2025年样本与市场级流程报告

## 1. 本组负责板块
- 板块：
- 2025年上市公司数量：
- 企业list来源：

## 2. 企业清单获取方法
- 使用网站：
- 检索路径：
- 是否代码抓取：
- 是否人工核对：
- 交叉核对来源：

## 3. 招股说明书获取方法
- 主要来源：
- 文件筛选规则：
- 文件版本规则：
- 如何排除非目标文件：

## 4. 批处理流程
- 企业list构建：
- 招股书链接获取：
- PDF下载：
- PDF解析：
- 章节定位：
- JSON抽取：
- 校验：

## 5. 本市场披露特点
- 常见章节名称：
- 常见关键词：
- 常见表格：
- 与公共样本相比的变化：

## 6. 失败案例
| 公司 | 环节 | 问题 | 当前处理 |
|---|---|---|---|

## 7. 本周形成的市场规则
- 企业list规则：
- 招股书版本规则：
- 章节定位规则：
- 抽取字段规则：
```

### 8.9 Week 2验收标准

| 项目 | 权重 |
|---|---:|
| 2025企业list完整性 | 25% |
| 来源说明清楚 | 20% |
| 招股书链接和版本识别 | 20% |
| 代码可运行 | 20% |
| 日志和失败案例 | 15% |

---

## Week 3：扩展到前几年，检验可扩展性，并做组内互查

### 8.10 Week 3目标

第三周的核心不是简单多做几年，而是测试第二周形成的方法是否能迁移到前几年。

每组至少向前扩展两个年份：

```text
2024年样本
2023年样本
```

如果某板块某年样本较少，则全量处理；如果样本很多，每年至少选10家公司，并说明抽样规则。建议每组至少扩展20家公司。

本周要回答的问题：

```text
1. 2025年的企业list代码能否用于2024、2023？
2. 交易所网页结构或披露入口是否变化？
3. 招股书文件命名是否变化？
4. 历史年份的招股书版本是否更复杂？
5. 章节标题是否发生变化？
6. 关键词定位是否仍然有效？
7. 失败最多的是下载、解析、定位还是抽取？
8. 组内互查发现了哪些问题？
```

### 8.11 Week 3必须提交

```text
company_lists/week3_extended_company_list.csv
source_notes/year_extension_method.md
source_notes/scalability_issues.md
code/本周修改过的脚本
outputs/week3_sample_outputs/
logs/week3_download_log.csv
logs/week3_parse_log.csv
logs/week3_locate_log.csv
logs/week3_extraction_log.csv
logs/week3_validation_log.csv
logs/week3_error_cases.md
review/week3_intra_group_review.csv
weekly_reports/week3.md
```

### 8.12 组内互查要求

每组2名学生，必须互查。互查不是代做，而是检查对方样本、来源、代码和日志是否可信。

每名学生至少检查同组另一名学生负责的10个样本。如果样本不足10个，则全量检查。

组内互查内容：

```text
1. 企业是否属于本板块。
2. 上市年份是否正确。
3. 上市日期是否有来源。
4. 招股说明书链接是否正确。
5. 文件版本是否正确。
6. 是否误把公告、问询回复、上市公告书当作招股说明书。
7. 代码是否能复现下载、解析或定位步骤。
8. 日志是否记录失败原因。
9. 章节定位是否合理。
10. JSON是否保留证据文本和来源位置。
```

### 8.13 Week 3组内互查表模板

```csv
reviewer,reviewee,company_name,stock_code,board,ipo_year,listing_date_check,prospectus_url_check,version_check,code_reproducible,section_location_reasonable,json_has_evidence,main_problem,review_comment,fix_status
```

### 8.14 Week 3周报模板

```markdown
# Week 3：历史年份扩展与组内互查报告

## 1. 扩展样本
- 扩展年份：
- 扩展企业数量：
- 企业来源：
- 抽样规则：

## 2. 可扩展性测试
- 2025年代码是否能直接用于前几年：
- 哪些地方需要修改：
- 是网页结构变化，还是文件命名变化：
- 是招股书结构变化，还是关键词规则变化：

## 3. 组内互查
| 检查人 | 被检查人 | 检查样本数 | 主要问题 | 是否已修改 |
|---|---|---:|---|---|

## 4. 本组发现的共同问题
- 企业list问题：
- 招股书版本问题：
- PDF解析问题：
- 章节定位问题：
- 字段设计问题：
- 证据保留问题：

## 5. 本组认为的板块特有问题
- 本板块特有披露结构：
- 本板块常见关键词：
- 本板块难点：

## 6. 下周组间检查准备
- 准备开放给其他组检查的样本：
- 需要其他组重点检查的问题：
```

### 8.15 Week 3验收标准

| 项目 | 权重 |
|---|---:|
| 历史年份企业list | 20% |
| 代码迁移能力 | 25% |
| 组内互查认真程度 | 25% |
| 可扩展性问题总结 | 20% |
| GitHub过程记录 | 10% |

---

## Week 4：组间检查、共同问题总结与presentation

### 8.16 Week 4目标

第四周每组抽查其他三个小组的样本。每组从另外三个小组各抽查10家公司，一共抽查30家公司。检查完成后，每组总结共同问题、板块特有问题，并完成最终presentation。

### 8.17 组间检查安排

| 检查对象 | 每组需检查数量 |
|---|---:|
| 其他组1 | 10家公司 |
| 其他组2 | 10家公司 |
| 其他组3 | 10家公司 |
| 合计 | 30家公司 |

样本必须由检查组自己从被检查组的 `company_lists/` 中抽取，不能由被检查组指定“最好看的样本”。

### 8.18 组间检查内容

```text
1. company_list是否完整。
2. 企业是否属于对应板块。
3. 企业是否属于对应年份。
4. 上市日期是否有可靠来源。
5. 招股说明书来源是否正确。
6. 招股说明书版本是否合适。
7. 是否误用了上市公告书、发行公告、问询回复。
8. 下载代码是否能复现。
9. PDF解析代码是否能复现。
10. 章节定位规则是否清楚。
11. 日志是否能解释失败样本。
12. JSON样例是否保留证据文本和来源位置。
13. 该板块总结是否有样本证据支持。
```

### 8.19 组间检查表模板

```csv
reviewer_group,reviewed_group,company_name,stock_code,board,ipo_year,listing_date_check,prospectus_url_check,version_check,download_code_reproducible,parse_code_reproducible,section_location_reasonable,json_has_evidence,main_problem,problem_type,review_comment
```

`problem_type` 统一使用以下分类：

```text
company_list_error
wrong_board
wrong_year
wrong_listing_date
wrong_prospectus_version
broken_url
download_failure
parse_failure
section_location_failure
field_definition_problem
pevc_definition_problem
evidence_missing
log_missing
code_not_reproducible
other
```

### 8.20 Week 4必须提交

```text
review/week4_inter_group_review_given.csv
review/week4_inter_group_review_received.csv
logs/final_error_summary.md
source_notes/final_source_summary.md
weekly_reports/week4.md
presentation/final_presentation.pptx
presentation/final_presentation.pdf
```

### 8.21 Week 4最终presentation要求

每组10分钟，最多12页PPT。

PPT结构固定：

```text
1. 本组负责板块与样本范围
2. 企业list来源和获取方法
3. 2025年样本处理流程
4. 向前几年扩展后的变化
5. 本组代码流程图
6. 本组最成功的一个案例
7. 本组最典型的失败案例
8. 组内互查发现的问题
9. 组间检查中别人指出的问题
10. 本组认为的共同问题
11. 本组认为的板块特有问题
12. 下一阶段如何扩大到全量
```

### 8.22 共同问题与板块特有问题总结模板

```markdown
# 共同问题与板块特有问题总结

## 1. 共同问题
| 问题类型 | 表现 | 例子 | 可能原因 | 改进方案 |
|---|---|---|---|---|

## 2. 板块特有问题
| 板块 | 特有问题 | 例子 | 对流程的影响 | 改进方案 |
|---|---|---|---|---|

## 3. 数据来源问题
- 哪些来源稳定：
- 哪些来源容易混入错误文件：
- 哪些来源需要人工复核：

## 4. 代码可扩展性问题
- 可复用部分：
- 需要板块定制部分：
- 下一阶段需要重写部分：

## 5. 下一阶段全量化建议
- 企业list全量化：
- 招股书下载全量化：
- 章节定位全量化：
- PE/VC抽取全量化：
- 人工复核抽样方案：
```

### 8.23 Week 4验收标准

| 项目 | 权重 |
|---|---:|
| 组间检查质量 | 25% |
| 共同问题总结 | 20% |
| 板块特有问题总结 | 20% |
| presentation质量 | 20% |
| GitHub记录完整性 | 15% |

---

## 9. 推荐关键词与章节

### 9.1 推荐章节

```text
发行人基本情况
历史沿革
股本形成及变化
历次增资
历次股权转让
股东情况
实际控制人
主要股东
发行前股本结构
上市前投资者情况
发行人设立以来股本演变情况
股份锁定承诺
对赌协议
特殊投资条款
```

### 9.2 推荐关键词

```text
增资
股权转让
出资
认购
入股
投资者
外部投资者
财务投资者
风险投资
私募股权
创投
创业投资
产业基金
股权投资基金
合伙企业
员工持股平台
投前估值
投后估值
估值
每股价格
认购价格
持股比例
股份锁定
退出
对赌
特殊投资条款
```

---

## 10. 日志要求

### 10.1 download_log.csv

```csv
company_name,stock_code,prospectus_url,file_name,download_time,status,file_size,error_message
```

### 10.2 parse_log.csv

```csv
company_name,stock_code,file_name,parser,parse_time,page_count,markdown_path,status,error_message
```

### 10.3 locate_log.csv

```csv
company_name,stock_code,matched_keyword,source_section,start_position,end_position,candidate_text_path,status,error_message
```

### 10.4 extraction_log.csv

```csv
company_name,stock_code,candidate_text_path,model_name,prompt_version,json_path,status,error_message
```

### 10.5 validation_log.csv

```csv
company_name,stock_code,json_path,validation_status,missing_fields,type_errors,logic_errors,review_required
```

### 10.6 error_cases.md

```markdown
# 失败案例记录

## 案例1
- 公司：
- 股票代码：
- 环节：下载 / 解析 / 定位 / 抽取 / 校验 / 复核
- 问题表现：
- 可能原因：
- 已尝试方法：
- 当前状态：
- 后续建议：
```

---

## 11. 个人贡献记录

虽然不要求每名学生单独提交个人规划，但必须能够看到个人贡献。

每名学生至少需要：

```text
1. 每周至少有一次commit或PR comment。
2. 至少负责若干家公司样本处理。
3. 第三周完成组内互查。
4. 第四周参与组间检查。
5. 最终presentation中承担一部分讲解。
```

个人贡献可以通过以下方式体现：

```text
GitHub commit
Pull Request comment
Issue comment
review表中的 reviewer 字段
weekly_report 中的实际完成内容
presentation讲解分工
```

---

## 12. 总评分建议

| 维度 | 分值 | 说明 |
|---|---:|---|
| GitHub过程记录 | 15 | 是否按周提交，是否有commit、PR、日志和文档。 |
| 企业list与来源 | 15 | 企业清单是否完整，来源是否清楚，链接是否可追溯。 |
| 代码完整性 | 20 | 是否覆盖list、下载、解析、定位、抽取、校验。 |
| 样本闭环质量 | 15 | 第一周公共样本是否跑通，JSON是否有证据。 |
| 扩展性测试 | 10 | 第三周是否发现历史年份迁移问题。 |
| 互查质量 | 15 | 组内互查和组间检查是否认真、具体、有证据。 |
| 最终presentation | 10 | 是否讲清楚共同问题、板块差异和下一阶段方案。 |

---

## 13. 最后提醒

本项目不是比谁交的数据最多，而是看谁能够把一件复杂的数据研究任务拆清楚、做扎实、留下可复核证据。

请每组始终坚持：

```text
来源可追溯
代码可运行
日志可检查
错误可定位
结果可复核
流程可扩展
```

