# Week 6 — PEVC IPO 招股书自动提取管线

## 运行方法

```bash
# 一条命令运行全流程
cd week6
python pipeline/run_auto_pipeline.py
```

### 参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--company` | 指定公司名称（如 黄山谷捷） | 全部8家 |
| `--skip-pdf-parse` | 跳过PDF解析（已有缓存时） | False |
| `--pdf-dir` | PDF文件目录 | `../../Desktop/招股说明书PDF` |

## 输入

- `data/pdf_manifest.json` — 8家公司PDF清单
- `data/*.pdf` — 招股说明书PDF文件

## 输出

| 目录 | 内容 |
|------|------|
| `auto_output/` | Auto三表(JSONL) — 未经人工修改 |
| `validation/` | Schema校验、Cross-check、Auto-vs-Gold TP/FP/FN |
| `final/` | 人工复核后的三表Excel |
| `logs/` | 运行记录、输出数量、文件哈希 |

## 流程

```
PDF → PyMuPDF逐页文本 → 代码正则定位章节 → 规则提取候选事件
→ 质量分级(high/medium/low) → 生成Auto三表(JSONL+Excel)
→ Schema校验 → Cross-check → Auto-vs-Gold TP/FP/FN
```

## 人工介入位置

1. `manual_gold/` — 人工标注Gold（走 `week3/manual_gold/`）
2. `final/` — 人工复核Auto结果，保留修改前后值
3. `review/` — 组内复核差异和处理结论

## 完成状态

- [x] 8家公司PDF文本提取
- [x] 代码章节定位（非LLM）
- [x] 规则候选事件提取+质量分级
- [x] Auto三表生成（subscription_flow + share_transfer_flow）
- [x] Schema格式校验
- [x] Auto-vs-Gold TP/FP/FN记录级匹配
- [x] 数据库导入（ymx_* 四表）
- [ ] LLM精筛环节（待接入）
- [ ] Cross-check自动化完善

## 已知问题

1. **候选噪声**: 规则提取的候选事件中约65%为非事件文本，需事件分类器进一步过滤
2. **Gold覆盖不均**: 001282仅5条Gold，920116仅14条，其余公司在20-50条之间
3. **MinerU内存**: 8GB RAM无法运行完整MinerU pipeline，目前回退至PyMuPDF
4. **非现金出资**: 吸收合并/整体变更的金额字段需人工确认

## 依赖

见 `requirements.txt`
