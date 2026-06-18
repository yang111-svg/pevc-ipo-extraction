# PE/VC上市前投资信息抽取项目

> IPO招股说明书股本变化事件提取 —— 从PDF到结构化数据的完整流水线

## 项目简介

本项目利用AI工具和程序化流程，从A股上市公司招股说明书中识别并提取其上市前PE/VC投资相关信息及股本变化事件，形成一套**来源可追溯、代码可运行、日志可检查、结果可复核、流程可扩展**的数据处理流水线。

项目围绕8家覆盖主板、创业板、科创板、北交所的A股IPO公司展开，历时三周逐步深化：

- **Week 1**: 跑通PDF→Markdown→JSON最小闭环，完成PE/VC信息初版提取
- **Week 2**: 重构为认缴流量+股权结构存量+Cross-check三表体系，引入Pydantic Schema校验
- **Week 3**: 建立人工Gold Standard，完成7步自动化流水线，系统化评估与错误分析

## 仓库结构

```
招股说明书——项目/
├── README.md                          # 本文件：项目总览
├── .gitignore
├── PEVC_招股说明书项目_学生任务书.md    # 四周任务书（含评分标准）
│
├── company_lists/                     # 企业清单
│   └── week1_public_samples.csv       # 8家公共样本（含来源、状态）
│
├── source_notes/                      # 数据来源与获取方法
│   ├── data_sources.md                # 各公司招股书来源
│   ├── prospectus_download_method.md  # PDF下载方法
│   ├── website_collection_method.md   # 网站检索方法
│   └── version_rules.md               # 招股书版本规则
│
├── schemas/                           # 共享数据模型
│   └── extraction_models.py           # Pydantic模型（SubscriptionFlow, EquitySnapshot, CrossCheck）
│
├── scripts/                           # 共享工具脚本
│   ├── validate_jsonl.py              # 三级校验：Schema + 业务规则 + Cross-check
│   └── jsonl_to_excel.py             # JSONL→Excel三表转换
│
├── logs/                              # 汇总日志
│   ├── download_log.csv               # 下载日志
│   ├── parse_log.csv                  # 解析日志
│   ├── locate_log.csv                 # 章节定位日志
│   ├── extraction_log.csv             # 提取日志
│   ├── validation_log.csv             # 校验日志
│   └── error_cases.md                 # 失败案例记录
│
├── review/                            # 互审记录
│   ├── week3_intra_group_review.csv
│   ├── week4_inter_group_review_given.csv
│   └── week4_inter_group_review_received.csv
│
├── weekly_reports/                    # 周报
│   ├── week1.md
│   └── week2.md
│
├── presentation/                      # 最终汇报材料
│
├── week1/                             # 第一周：最小闭环
│   ├── README.md
│   ├── code/                          # 7步代码（01-07）
│   ├── outputs/candidate_texts/       # Markdown解析文件（24个）
│   └── outputs/sample_json/          # PEVC提取JSON（8个）
│
├── week2/                             # 第二周：三表体系
│   ├── outputs/jsonl/                 # 认缴流量+股权快照JSONL（8个）
│   ├── outputs/excel/                 # 三表Excel（8×2=16个）
│   └── logs/                          # Schema校验+Cross-check日志
│
└── week3/                             # 第三周：完整流水线+Gold Standard
    ├── README.md
    ├── data/                          # 8份PDF招股说明书+清单
    ├── pipeline/                      # 7步流水线脚本
    │   ├── parse_pdf.py               # Step 1: PDF文本解析
    │   ├── locate_sections.py         # Step 2: 章节定位
    │   ├── extract_candidates.py      # Step 3: 候选事件切块
    │   ├── extract_with_rules.py      # Step 4a: 规则提取
    │   ├── extract_with_llm.py        # Step 4b: LLM提取
    │   ├── validate_schema.py         # Step 5: Pydantic Schema校验
    │   ├── run_cross_check.py         # Step 6: Cross-check校验
    │   ├── compare_to_gold.py         # Step 7: 与Gold对比
    │   └── rule_coverage.md           # 规则覆盖率分析
    ├── prompts/                       # LLM Prompt工程
    ├── manual_gold/                   # 人工Gold Standard（73+8+25+18条）
    ├── evaluation/                    # 自动vs人工对比评估
    └── outputs/                       # 自动提取输出
```

## 8家样本公司

| 证券代码 | 公司简称 | 公司全称 | 板块 | PDF文件名 |
|----------|----------|----------|------|----------|
| 001282 | 三联锻造 | 芜湖三联锻造股份有限公司 | 主板 | `001282_三联锻造.pdf` |
| 603418 | 友升股份 | 上海友升铝业股份有限公司 | 主板 | `603418_友升股份.pdf` |
| 301563 | 云汉芯城 | 云汉芯城（上海）互联网科技股份有限公司 | 创业板 | `301563_云汉芯城.pdf` |
| 301581 | 黄山谷捷 | 黄山谷捷股份有限公司 | 创业板 | `301581_黄山谷捷.pdf` |
| 688758 | 赛分科技 | 苏州赛分科技股份有限公司 | 科创板 | `688758_赛分科技.pdf` |
| 688775 | 影石创新 | 影石创新科技股份有限公司 | 科创板 | `688775_影石创新.pdf` |
| 920100 | 三协电机 | 常州三协电机股份有限公司 | 北交所 | `920100_三协电机.pdf` |
| 920116 | 星图测控 | 中科星图测控技术股份有限公司 | 北交所 | `920116_星图测控.pdf` |

## 处理流程

```
企业清单构建 → 招股书来源确认 → PDF下载 → PDF解析(MinerU/pdfplumber)
    → 章节定位 → 候选文本截取 → 融资事件提取(规则+LLM)
    → Pydantic Schema校验 → Cross-check数值校验 → 人工复核
    → 自动vs人工对比评估 → 错误分析
```

## 第三周核心成果

### 人工Gold Standard（可审计基准答案）

| 数据类型 | 记录数 | 说明 |
|----------|--------|------|
| subscription_flow | 73条 | 增资/设立出资/整体变更流量记录 |
| share_transfer_flow | 8条 | 股权转让记录 |
| equity_snapshot | 25个时点 | 股权结构快照 |
| cross_check | 18条 | 跨表数值校验 |

每条记录含PDF页码、原文证据和提取备注。

### 自动提取流水线评估

- **8家公司全部覆盖**，全流水线可运行
- 自动提取 vs 人工Gold匹配率：**82.9%**（617/744字段级匹配）
- 规则提取预估覆盖率：78-92%（不同公司差异较大）
- Pydantic Schema校验 + Cross-check数值校验

### 已知限制

1. 规则提取无法区分增资和股权转让，建议配合LLM使用
2. PDF解析质量对后续流程影响较大
3. 扩展到多公司时，章节定位和PDF格式多样性是主要瓶颈
4. 见 `week3/manual_gold/manual_review_queue.csv`（11项待人工复核）

## 环境准备

```bash
pip install pdfplumber PyMuPDF pydantic openai
```

## 快速开始

详见各周目录下的 README：

- **Week 1**: `week1/README.md` — PDF解析 + 候选文本截取 + 初版JSON提取
- **Week 2**: `weekly_reports/week2.md` — Schema重构 + Excel三表 + Cross-check
- **Week 3**: `week3/README.md` — 完整7步流水线 + Gold Standard + 评估

### Week 3 一键运行

```bash
cd week3/pipeline
python parse_pdf.py --input-dir ../data --output-dir ../outputs/logs && \
python locate_sections.py --input-dir ../outputs/logs --output-dir ../outputs/logs && \
python extract_candidates.py --input-dir ../outputs/logs --output-dir ../outputs/raw_llm_outputs && \
python extract_with_rules.py --input-dir ../outputs/raw_llm_outputs --output-dir ../outputs/auto_jsonl && \
python validate_schema.py --input-dir ../outputs/auto_jsonl --output-dir ../outputs/logs && \
python run_cross_check.py --input-dir ../outputs/auto_jsonl --output-dir ../outputs/logs && \
python compare_to_gold.py --auto-dir ../outputs/auto_jsonl --gold-dir ../manual_gold --output-dir ../evaluation
```

## 核心交付物

- [x] 8家公司全部覆盖（主板×2, 创业板×2, 科创板×2, 北交所×2）
- [x] 人工Gold Standard（4类数据，含页码和原文证据）
- [x] 自动化提取流水线（7步可运行脚本）
- [x] Pydantic Schema校验（带字段级类型检查）
- [x] 带数字的Cross-check（股本一致性校验）
- [x] 自动结果与人工Gold对比（row_match + event_summary）
- [x] Prompt工程文档（system/user prompt + 变体对比 + 敏感性分析）
- [x] 规则覆盖率分析
- [x] 失败样本和人工复核队列
- [x] 错误分析报告（8个核心问题）
- [x] 标注索引（annotation_index.csv）

## 团队成员

- 杨苗鑫 (yang111-svg)
- 赵秉清

## 项目周期

2026年6月 — 4周项目
