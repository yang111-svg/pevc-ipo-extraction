# Week 5 — 批量扩展 + 事件分类定义 + Cross-check数字校验 + 定量评估

## 本周工作概述

根据老师反馈和本周任务要求，完成以下工作：

### 1. 8家公司批量处理

| 公司 | 股票代码 | 页数 | 定位章节 | 候选事件 | 高质量 |
|------|----------|:---:|:---:|:---:|:---:|
| 三联锻造 | 001282 | 476 | 11 | 115 | 44 |
| 云汉芯城 | 301563 | 443 | 17 | 154 | 60 |
| 黄山谷捷 | 301581 | 343 | 10 | 112 | 46 |
| 友升股份 | 603418 | 398 | 14 | 172 | 63 |
| 赛分科技 | 688758 | 468 | 15 | 120 | 48 |
| 影石创新 | 688775 | 555 | 15 | 103 | 37 |
| 三协电机 | 920100 | 382 | 12 | 92 | 45 |
| 星图测控 | 920116 | 365 | 10 | 72 | 38 |

**方法**: PDF → Markdown文本 → 代码正则定位章节 → 规则提取候选事件 → 质量分级(high/medium/low)

### 2. 事件分类定义（人工定义，明确规则）

参照CVC数据抽取文档的经验，为每个事件类型定义了：
- 判定标准
- 关键词列表
- 典型场景
- 注意事项

详见 `outputs/event_categories.json`

### 3. Cross-check 含完整数字

黄山谷捷 cross-check 示例（`outputs/黄山谷捷_cross_check_detailed.xlsx`）:

| 校验点 | 上一时点 | 当前 | 事件类型 | 变化量 | 预期 | PDF | 差额 | 结果 |
|--------|:---:|:---:|------|:---:|:---:|:---:|:---:|:---:|
| t1→t2(转让) | 1000 | 1000 | 股权转让 | 0 | 1000 | 1000 | 0 | trans_ok |
| t3→t4(增资) | 1200 | 1714.2857 | 增资 | +514.2857 | 1714.2857 | 1714.2857 | 0 | ok |

### 4. 定量评估

| 指标 | 当前值 | 说明 |
|------|:---:|------|
| 平均 Recall | ~0.35 | high_quality_matched / gold_total |
| 平均 Precision | ~0.45 | matched / auto_candidates |
| 目标 Recall | >0.80 | 需继续优化章节定位和候选过滤 |

### 5. 文件结构

```
week5/
├── README.md
├── batch_pipeline.py              ← 批量处理8家公司
├── generate_crosscheck_and_eval.py ← Cross-check + 定量评估
├── outputs/
│   ├── event_categories.json      ← 事件分类定义
│   ├── evaluation_report.json     ← 定量评估报告
│   ├── summary.json               ← 8家汇总
│   ├── 黄山谷捷_cross_check_detailed.xlsx
│   └── {stock_code}_{company}/
│       ├── chapters.json
│       ├── candidates.json
│       ├── core_sections.txt
│       ├── gold_vs_auto.json
│       └── {stock_code}_{company}_三表.xlsx
```

### 6. 技术推进

参照刘宇轩同学的V4技术路径:

| 杨苗鑫Week5 |
|--------|----------|------------|
 | ✅ 全量Markdown正则表格扫描 | ✅ PyMuPDF+代码定位 (MinerU ready) |
 | ✅ 星图测控7股东100% | ✅ 规则提取候选事件 || ✅ 8家Excel含3_schema_cross_check | ✅ 含完整数字(上一时点/变化量/预期/PDF/差额) |
 | 事件分类 | 16类 | 6大类(含判定标准+关键词+典型场景+注意事项) |
 | 温度参数 | T=0.0 | Prompt设置为确定性输出 |
