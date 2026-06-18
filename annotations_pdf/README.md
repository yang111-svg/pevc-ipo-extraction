# PDF原文证据标注索引

本目录为招股说明书PDF原文的标注证据映射中心。每一条人工gold记录均可在对应PDF中找到原文支撑。

## 证据追溯方式

每条gold记录包含两个关键字段：

- `pdf_page`: PDF页码（从1开始），指向招股说明书中对应内容所在页
- `evidence_text`: 从PDF原文中提取的证据文本片段

标注者可通过 `annotation_index.csv`（位于 `manual_gold/`）浏览全部gold记录的证据位置索引。

## 如何复核一条记录

1. 打开对应公司的PDF文件（`data/{stock_code}_{company}.pdf`）
2. 跳转到 `pdf_page` 字段指定的页码
3. 在页面中搜索 `evidence_text` 中的关键句或数字
4. 核对提取的数值（金额、股数、价格、日期）是否与PDF原文一致

## 量化证据覆盖

| 数据类型 | 记录总数 | 含pdf_page | 含evidence_text | 覆盖率 |
|----------|----------|-----------|-----------------|--------|
| subscription_flow_gold | 73 | 73 | 73 | 100% |
| share_transfer_flow_gold | 8 | 8 | 8 | 100% |
| equity_snapshot_gold | 25 | 21 | 25 | 84% (page) / 100% (text) |
| cross_check_gold | 18 | 18 | 18 | 100% |

> 注：equity_snapshot有4条早期记录的pdf_page来自数据推断('source': 'week3_manual_gold'但未单独标注page字段)，这些记录的evidence_text和extraction_notes中包含章节位置信息。

## 标注质量

- **calculated_fields**: PDF未直接披露、通过其他数据计算得出的字段均已标注 `[calculated: field_name]`
- **不确定记录**: 11条存在疑问或不一致的记录已纳入 `manual_review_queue.csv`（全部已复核并解决）
- **抽样回源验证**: 已完成20%抽样回源验证（约21/106条），覆盖全部8家公司和3种数据类型

## PDF批注截图说明

由于8份PDF合计约64MB，不适合在GitHub仓库中存储完整批注截图。取而代之的是：
1. `manual_gold/annotation_index.csv`: 每条记录的PDF页码索引
2. 每条gold记录中的 `evidence_text`: 可直接文本检索的原文证据
3. `manual_gold/manual_review_queue.csv`: 所有存疑记录的复核过程

如需逐页PDF批注截图，可在本地通过以下方式生成：
```bash
# 使用pdfplumber提取指定页码
python -c "
import pdfplumber
pdf = pdfplumber.open('data/603418_友升股份.pdf')
page = pdf.pages[43]  # 0-indexed, pdf_page=44 → index=43
print(page.extract_text())
"
```
