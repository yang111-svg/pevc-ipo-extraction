# Week 3：完整流水线 + Gold Standard + 交叉校验与错误分析

**作者**: 杨苗鑫  
**日期**: 2026-06-17  
**本周目标**: 建立人工Gold Standard，完成自动化流水线，系统化评估自动提取质量，回答8个核心问题

---

## 一、本周完成内容

### 1. 人工Gold Standard（可审计基准答案）

对8家公司的招股说明书PDF进行逐页人工标注，建立包含PDF页码和原文证据的gold standard：

| 数据类型 | 记录数 | 说明 |
|----------|--------|------|
| subscription_flow_gold | 73条 | 增资/设立出资/整体变更流量记录 |
| share_transfer_flow_gold | 8条 | 股权转让记录（含零对价、代持还原） |
| equity_snapshot_gold | 25个时点 | 关键时点股权结构快照 |
| cross_check_gold | 18条 | 带数字的跨表校验 |

每条记录包含：
- `pdf_page`: PDF页码
- `evidence_text`: 原文证据
- `calculated_fields`: 标注计算字段
- 不确定记录纳入 `manual_review_queue.csv`（11条，全部已复核解决）

### 2. 自动化提取流水线（7步）

```text
PDF文本解析(parse_pdf.py) → 章节定位(locate_sections.py)
  → 候选事件切块(extract_candidates.py)
  → 规则提取(extract_with_rules.py) / LLM提取(extract_with_llm.py)
  → Pydantic Schema校验(validate_schema.py)
  → 数值Cross-check(run_cross_check.py)
  → 自动vs人工对比(compare_to_gold.py)
```

- 规则提取: 零API成本，<10秒完成8家公司初筛
- LLM提取: 支持OpenAI兼容API，temperature=0.0

### 3. 自动vs人工对比评估

| 指标 | 数值 |
|------|------|
| 总体字段级匹配率 | 82.9% (617/744) |
| 最佳字段 | price_per_share (100%), total_capital_after (100%), subscription_shares (93.8%) |
| 最差字段 | investor_name (20.3%) — 规则无法精确识别投资者名称 |
| 最佳公司 | 001282三联锻造 (95.8%) |
| 最差公司 | 688775影石创新 (62.5%) — 投资者数量多，名称匹配困难 |

### 4. 问题发现与解决

- **MRQ_001**: 云汉芯城t0总股本4599 vs 4598差异（舍入误差，已修正）
- **MRQ_003**: 影石创新投资者计数23 vs 24家（分组计数错误，已修正）
- **MRQ_004**: 友升股份有限公司/股份公司单位混淆（已在cross_check中区分registered_capital vs total_shares）
- 修复PDF manifest中603418 section_start_page标注
- 修复compare_to_gold公司名称匹配算法
- 去除CSV文件UTF-8 BOM
- 自动JSONL去重（去除106条重复记录）

---

## 二、8个核心问题回答摘要

（详见 `evaluation/error_analysis.md`）

1. **规则稳定提取**: 增资事件覆盖率约78-92%，格式规整的公司可达100%
2. **需要LLM/人工**: 股权转让（零对价）、代持还原、吸收合并、整体变更
3. **主要漏抽**: 股权转让出让方(4-7%)、小额增资(3-6%)、设立出资(3-4%)
4. **主要误抽**: 转让误判为增资、存量表数据误抽为流量事件
5. **单位错误发现**: Pydantic校验 + Cross-check数量级检查 + 价格反向验证
6. **增资vs转让区分**: 关键词规则层 → LLM语义层 → Cross-check校验层三层架构
7. **Cross-check失败处理**: 分级处理（precision_issue → review_needed → fail → LLM重试）
8. **50家扩展瓶颈**: PDF解析质量 > 章节定位覆盖 > 事件类型多样性 > API成本

---

## 三、下周计划（Week 4）

- 完成组间检查（抽查其他三组各10家公司）
- 完善最终presentation
- 补充week4周报
