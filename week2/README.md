# Week 2: 三表抽取 —— 认缴流量 + 股权结构存量 + Cross-check

## 本周目标

对8家公共样本完成"三表抽取"，确保每个数字可回到PDF原文，通过Pydantic schema和数值cross-check复核。

## 完成内容

### 1. 基础设施

- **Pydantic Schema** (`schemas/extraction_models.py`): 定义 SubscriptionFlow 和 EquitySnapshot 两个模型
- **三级校验脚本** (`scripts/validate_jsonl.py`): Schema + 业务规则 + Cross-check
- **JSONL→Excel 转换脚本** (`scripts/jsonl_to_excel.py`): 生成认缴流量/股权结构存量/Cross-check 三表

### 2. 8家公司数据

| 板块 | 代码 | 公司 | 认缴记录 | 快照 | 状态 |
|------|------|------|---------|------|------|
| 主板 | 001282 | 芜湖三联锻造 | 1 | 2 | OK |
| 主板 | 603418 | 上海友升铝业 | 13 | 3 | OK |
| 创业板 | 301581 | 黄山谷捷 | 6 | 3 | OK |
| 创业板 | 301563 | 云汉芯城 | 8 | 2 | OK |
| 科创板 | 688758 | 苏州赛分科技 | 8 | 2 | OK |
| 科创板 | 688775 | 影石创新 | 34 | 3 | OK |
| 北交所 | 920100 | 常州三协电机 | 18 | 10 | OK |
| 北交所 | 920116 | 中科星图测控 | 6 | 4 | OK |

### 3. 校验结果

- Schema 校验: 118/126 PASS
- 业务规则: 117/121 PASS
- Cross-check: 87/112 PASS

### 4. 输出文件

- JSONL: `outputs/jsonl/*.jsonl` (8文件, 126条记录)
- Excel: `outputs/excel/*_三表.xlsx` (16文件，含简版和全名版)

## 运行方式

```bash
# Schema校验
python ../scripts/validate_jsonl.py --input-dir outputs/jsonl --output-dir logs

# JSONL转Excel
python ../scripts/jsonl_to_excel.py --input-dir outputs/jsonl --output-dir outputs/excel
```
