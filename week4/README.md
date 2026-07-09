# Week 4 — 改进的 PDF 章节定位与股本变化提取

## 改进概述

基于第三周老师反馈，本周做了以下核心改进：

### 1. MinerU 替代 pdfplumber/PyMuPDF

| 对比维度 | Week 3 (pdfplumber) | Week 4 (MinerU) |
|---|---|---|
| 文本提取 | 逐页提取纯文本 | 解析为结构化 Markdown |
| 表格保留 | 丢失表格格式 | Markdown table 完整保留 |
| 标题识别 | 正则猜测 | 利用 # ## ### 层级结构 |
| 图片处理 | 无 | 自动提取到独立目录 |

### 2. 代码定位章节，不再全文塞给 LLM

**Week 3 做法**: 把整个"历史沿革"章节的文本全量发给 LLM → 噪声重、上下文溢出、结果不稳定

**Week 4 做法**:
1. MinerU 转 PDF 为 Markdown
2. `locate_sections_markdown.py` 解析 Markdown 标题树，精确定位目标章节
3. 只提取目标章节的文本块和表格
4. 按章节分组发送给 LLM，每次只处理一个子章节

### 3. Schema 完善

新增/改进的模型:
- `TransferFlow` — 独立的股权转让记录类型（出让方/受让方各一条）
- `EquitySnapshot` — 增加快照事件锚点、流量存量校验字段
- `EventCrossCheck` — 专门的交叉校验记录类型
- 所有数值字段增加 `_raw` 字段保留原文值
- 新增 `unit_issue_flag` 标记单位歧义（如黄山谷捷 78/780 问题）

### 4. System Prompt 优化

- 增加"黄山谷捷专题"：出资额 vs 股数的单位说明
- 明确的单位转换规则表
- 证据长度要求（50-500字）
- 不确定性处理规则

## 文件结构

```
week4/
├── README.md                          ← 本文件
├── parse_with_mineru.py               ← 调用 MinerU 转 PDF → Markdown
├── locate_sections_markdown.py        ← 基于 Markdown 标题树的章节定位
├── extract_candidates_rules.py        ← 规则-based 候选事件提取
├── extract_with_llm_v2.py             ← LLM 增强提取（按章节分批）
├── validate_and_crosscheck.py         ← 校验 + 流量存量 cross-check
├── prompts/
│   ├── system_prompt_v2.md            ← 改进的 System Prompt
│   └── user_prompt_template_v2.md     ← 改进的 User Prompt 模板
└── outputs/                           ← 输出目录
    ├── sections/                      ← 章节定位结果
    ├── candidates/                    ← 候选事件
    ├── auto_jsonl/                    ← 自动抽取结果
    └── validation/                    ← 校验报告
```

## 使用方法

### Step 1: PDF → Markdown

```bash
cd week4
python parse_with_mineru.py --input-dir ../data --company 黄山谷捷
```

### Step 2: 章节定位

```bash
python locate_sections_markdown.py --md-dir ../outputs/mineru_md
```

### Step 3: 候选提取

```bash
python extract_candidates_rules.py --sections-dir ../outputs/sections
```

### Step 4: LLM 提取

```bash
python extract_with_llm_v2.py --candidates-dir ../outputs/candidates
```

### Step 5: 校验

```bash
python validate_and_crosscheck.py --auto-dir ../outputs/auto_jsonl
```

## 黄山谷捷 (301581) 注意事项

1. **出资额 vs 股数混淆**: 黄山谷捷历史沿革中以"万元出资额"为单位，需特别注意与"万股"的区别
2. **关键争议**: 78万元出资额转让（还是780万元？）→ unit_issue_flag
3. **吸收合并**: 涉及吸收合并事件，现有 schema 已支持
4. **11/110 单位口径**: 另一关键争议点，需人工复核

## 依赖

```
mineru[all]     # PDF → Markdown
pymupdf         # 页面计数
pydantic        # Schema 校验
```
