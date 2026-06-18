# Week 3: IPO招股说明书股本变化提取项目

## 项目概述

本项目围绕8家A股IPO公司的招股说明书，建立了一套**可信、可复核、可扩展**的IPO招股说明书股本变化事件提取方法。项目包含：
- **人工Gold Standard**: 可审计的人工标注基准答案（含PDF页码和原文证据）
- **自动化提取流水线**: 从PDF到结构化JSONL的可运行代码
- **Schema校验与Cross-check**: 带数字的Pydantic结构校验和股本一致性校验
- **自动vs人工对比**: 系统化评估自动提取质量

## 仓库结构

```
week3/
├── README.md                          # 本文件：项目说明和运行指南
├── data/
│   ├── pdf_manifest.csv               # PDF文件清单（含8家公司信息）
│   └── *.pdf                          # 8家IPO招股说明书PDF
├── manual_gold/
│   ├── subscription_flow_gold.jsonl   # 人工gold：增资/设立出资/整体变更（73条）
│   ├── share_transfer_flow_gold.jsonl # 人工gold：股权转让（8条）
│   ├── equity_snapshot_gold.jsonl     # 人工gold：股权结构快照（25个时点）
│   ├── cross_check_gold.jsonl         # 人工gold：跨表校验结果（18条）
│   ├── annotation_index.csv           # 标注索引：所有gold记录的证据页码
│   └── manual_review_queue.csv        # 人工复核队列：11个待决问题
├── pipeline/
│   ├── parse_pdf.py                   # Step 1: PDF文本解析
│   ├── locate_sections.py             # Step 2: 章节定位
│   ├── extract_candidates.py          # Step 3: 候选事件切块
│   ├── extract_with_rules.py          # Step 4a: 规则提取
│   ├── extract_with_llm.py            # Step 4b: LLM提取
│   ├── validate_schema.py             # Step 5: Pydantic Schema校验
│   ├── run_cross_check.py             # Step 6: Cross-check校验
│   ├── compare_to_gold.py             # Step 7: 与Gold对比
│   └── rule_coverage.md               # 规则覆盖率分析
├── prompts/
│   ├── system_prompt.md               # LLM System Prompt
│   ├── user_prompt_template.md        # LLM User Prompt模板
│   ├── prompt_variants.md             # Prompt变体对比（Variant A vs B）
│   └── prompt_sensitivity.md          # Prompt敏感性分析
├── schemas/
│   └── extraction_models.py           # Pydantic数据模型定义
├── outputs/
│   ├── auto_jsonl/                    # 自动提取JSONL输出
│   ├── auto_excel/                    # Excel查看版
│   ├── logs/                          # 运行日志、sections、candidates
│   └── raw_llm_outputs/               # LLM原始输出
└── evaluation/
    ├── error_analysis.md              # 错误分析报告（回答8个核心问题）
    ├── row_match.csv                  # 自动vs人工逐行对比
    └── event_summary.csv              # 字段级匹配率汇总
```

## 8家样本公司

| 证券代码 | 公司简称 | PDF文件名 |
|----------|----------|----------|
| 603418 | 友升股份 | `603418_友升股份.pdf` |
| 301563 | 云汉芯城 | `301563_云汉芯城.pdf` |
| 301581 | 黄山谷捷 | `301581_黄山谷捷.pdf` |
| 688758 | 赛分科技 | `688758_赛分科技.pdf` |
| 688775 | 影石创新 | `688775_影石创新.pdf` |
| 920100 | 三协电机 | `920100_三协电机.pdf` |
| 920116 | 星图测控 | `920116_星图测控.pdf` |
| 001282 | 三联锻造 | `001282_三联锻造.pdf` |

## 环境准备

### 1. 安装依赖

```bash
pip install pdfplumber PyMuPDF pydantic openai
```

### 2. 配置LLM API（可选）

若使用LLM提取（`extract_with_llm.py`），需设置环境变量：

```bash
export OPENAI_API_KEY="your-api-key"
export OPENAI_BASE_URL="https://api.openai.com/v1"  # 可选，默认OpenAI
```

若不配置API key，LLM提取脚本会自动降级为模拟模式（`--mock`）。

## 快速开始：完整流水线

从仓库根目录运行以下命令：

### Step 1: PDF文本解析

```bash
cd pipeline
python parse_pdf.py --input-dir ../data --output-dir ../outputs/logs
```

输出：`../outputs/logs/{stock_code}_{company}_parsed.txt`（每页一个段落+页码标记）

### Step 2: 章节定位

```bash
python locate_sections.py --input-dir ../outputs/logs --output-dir ../outputs/logs
```

输出：`../outputs/logs/{source}_sections.json` 和 `_sections.txt`

### Step 3: 候选事件切块

```bash
python extract_candidates.py --input-dir ../outputs/logs --output-dir ../outputs/raw_llm_outputs
```

输出：`../outputs/raw_llm_outputs/{source}_candidates.json`

### Step 4a: 规则提取

```bash
python extract_with_rules.py --input-dir ../outputs/raw_llm_outputs --output-dir ../outputs/auto_jsonl
```

输出：`../outputs/auto_jsonl/{source}_auto.jsonl`

### Step 4b: LLM提取（可选，需API key）

```bash
python extract_with_llm.py --input-dir ../outputs/raw_llm_outputs --output-dir ../outputs/auto_jsonl --model gpt-4o-mini
```

输出：`../outputs/auto_jsonl/{source}_llm_auto.jsonl`

### Step 5: Schema校验

```bash
python validate_schema.py --input-dir ../outputs/auto_jsonl --output-dir ../outputs/logs
```

输出：`../outputs/logs/schema_validation_log.csv`

### Step 6: Cross-check校验

```bash
python run_cross_check.py --input-dir ../outputs/auto_jsonl --output-dir ../outputs/logs
```

输出：`../outputs/logs/cross_check_summary.csv`

### Step 7: 与Gold对比

```bash
python compare_to_gold.py --auto-dir ../outputs/auto_jsonl --gold-dir ../manual_gold --output-dir ../evaluation
```

输出：`../evaluation/row_match.csv` 和 `../evaluation/event_summary.csv`

## 一键运行

```bash
cd pipeline
python parse_pdf.py --input-dir ../data --output-dir ../outputs/logs && \
python locate_sections.py --input-dir ../outputs/logs --output-dir ../outputs/logs && \
python extract_candidates.py --input-dir ../outputs/logs --output-dir ../outputs/raw_llm_outputs && \
python extract_with_rules.py --input-dir ../outputs/raw_llm_outputs --output-dir ../outputs/auto_jsonl && \
python validate_schema.py --input-dir ../outputs/auto_jsonl --output-dir ../outputs/logs && \
python run_cross_check.py --input-dir ../outputs/auto_jsonl --output-dir ../outputs/logs && \
python compare_to_gold.py --auto-dir ../outputs/auto_jsonl --gold-dir ../manual_gold --output-dir ../evaluation
```

## 人工Gold Standard说明

### 数据来源
人工Gold Standard基于PDF回源复核，每条记录标注了：
- `pdf_page`: PDF页码（从1开始）
- `evidence_text`: 招股说明书原文证据片段
- `extraction_notes`: 提取备注和计算说明

### 三条线分离
- **人工Gold**: `manual_gold/` 目录，纯人工标注+复核
- **自动输出**: `outputs/auto_jsonl/` 目录，代码/LLM自动生成
- **对比评估**: `evaluation/` 目录，自动结果 vs 人工Gold差异

### 证据要求
每条记录必须可回溯到PDF页码和原文。标注了 `calculated` 的字段表示该值非PDF直接披露，而是从其他数据计算得出。

## 已知问题和限制

### 待人工复核的问题（见 `manual_review_queue.csv`）
1. **301563 云汉芯城**: 增资流量570万元 vs 总股本变动770万元，差额200万元待查
2. **688775 影石创新**: 2019年增资各投资者加总与PDF披露存在差异
3. **001282 三联锻造**: equity_snapshot有重复t0记录需去重

### 流程限制
- 规则提取无法区分增资和股权转让，建议配合LLM使用
- PDF解析质量对后续流程影响较大，建议建立多后端fallback机制
- 扩展到50+公司时，章节定位和PDF格式多样性是主要瓶颈

## 核心交付物清单

按照第三周验收标准，本仓库提交了以下交付物：

- [x] 8家公司全部覆盖
- [x] 人工Gold（subscription_flow, share_transfer_flow, equity_snapshot, cross_check）
- [x] 自动流水线（7步可运行脚本）
- [x] Pydantic Schema校验
- [x] 带数字的Cross-check
- [x] 自动结果与人工Gold对比
- [x] Prompt文档（system_prompt, user_prompt_template, prompt_variants, prompt_sensitivity）
- [x] 规则覆盖率分析（rule_coverage.md）
- [x] 失败样本和人工复核队列（manual_review_queue.csv）
- [x] 错误分析报告（error_analysis.md，回答8个核心问题）
- [x] 标注索引（annotation_index.csv）

## 模型和参数

- **规则提取**: 无模型，纯正则表达式
- **LLM提取**: 支持OpenAI兼容API，默认模型 `gpt-4o-mini`
  - temperature: 0.0
  - max_tokens: 4096 (默认)
  - System prompt: 见 `prompts/system_prompt.md`
  - User prompt template: 见 `prompts/user_prompt_template.md`
  - Prompt变体对比: 见 `prompts/prompt_variants.md`
  - 敏感性分析: 见 `prompts/prompt_sensitivity.md`

## 作者

杨苗鑫 (yang111-svg)
Week 3 提交日期: 2026-06-17
