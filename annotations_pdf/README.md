# annotations_pdf — PDF 关键页批注索引

> **PDF 原文证据标注与可视化**  
> 将 Gold Standard 抽取记录反向链接到招股书 PDF 原文，逐页标注关键证据。

---

## 📁 目录结构

```
annotations_pdf/
├── README.md                          # 本文件
├── 关键页索引.csv                      # （自动生成）所有标注页的 CSV 索引
│
├── 001282_三联锻造/                    # 按「股票代码_公司简称」命名的子目录
│   ├── 001282_三联锻造_关键页批注.pdf   # 带红色边框+便签的批注 PDF
│   ├── 001282_三联锻造_p36.png          # 每个关键页的 PNG 截图
│   ├── 001282_三联锻造_p37.png
│   └── ...
│
├── 301563_云汉芯城/
│   ├── 301563_云汉芯城_关键页批注.pdf
│   ├── 301563_云汉芯城_p60.png
│   └── ...
│
├── 301581_黄山谷捷/
├── 603418_友升股份/
├── 688758_赛分科技/
├── 688775_影石创新/
├── 920100_三协电机/
└── 920116_星图测控/
```

---

## 🚀 生成批注文件

### 1. 安装依赖

```bash
pip install pymupdf
```

### 2. 运行脚本

```bash
cd pevc-ipo-extraction
python scripts/build_annotations_pdf.py
```

### 3. 脚本执行流程

| 步骤 | 说明 |
|------|------|
| **[1/5] 加载 Gold 记录** | 读取 `week3/manual_gold/subscription_flow_gold.jsonl`、`equity_snapshot_gold.jsonl`、`share_transfer_flow_gold.jsonl`、`cross_check_gold.jsonl` |
| **[2/5] 按公司分组** | 将记录按 `stock_code` 分组，仅保留有 `pdf_page` 字段的记录 |
| **[3/5] 匹配源 PDF** | 在 `week3/data/` 中按股票代码匹配招股书 PDF |
| **[4/5] 生成批注** | 逐公司生成带红框+便签的批注 PDF，同时导出 PNG 截图 |
| **[5/5] 写 CSV 索引** | 汇总所有标注记录写入 `关键页索引.csv` |

---

## 📄 批注样式说明

每个关键页上有两种标注：

### 🔴 红色矩形边框
- 内缩 20px 围绕整页
- 视觉标记：「此页包含 Gold 抽取证据」

### 🟡 黄色便签批注
- 位于页面左上角 (36, 36)
- 内容包含：
  - 记录类型（增资/股权变动、股权快照、交叉验证）
  - 投资方/股东信息
  - 股数、金额、价格
  - 事件日期
  - 证据文本摘要
  - 来源文件及行号

---

## 📋 索引 CSV 字段

| 列名 | 说明 | 示例 |
|------|------|------|
| `股票代码` | 6 位股票代码 | `920100` |
| `公司` | 公司全称 | `常州三协电机股份有限公司` |
| `PDF页码` | PDF 原始页码 (1-based) | `30` |
| `记录类型` | 数据类型 | `subscription_flow` / `equity_snapshot` / `cross_check` |
| `事件类型` | 事件子类型 | `增资` / `股权转让（受让）` |
| `日期` | 事件日期 | `2004-12-01` |
| `主体名称` | 投资方/快照标签/核查ID | `朱南保` |
| `证据摘要` | evidence_text 截断 (≤100 字) | `深圳三协第一次增资，注册资本由50万元...` |
| `来源文件` | 来源 JSONL 文件名 | `subscription_flow_gold.jsonl` |
| `JSONL行号` | 在原 JSONL 中的行号 | `42` |
| `是否有截图` | 是否成功导出 PNG | `是` / `否` |

---

## 🔍 使用场景

### 人工复核
打开 `{股票代码}_{公司简称}_关键页批注.pdf`，每个被标注的页面都有：
- 🔴 红色边框 → 快速定位关键页
- 🟡 便签内容 → 无需翻阅 Gold 文件即可对照原文

### Peer Review
直接查看 `关键页索引.csv` 了解全量覆盖情况，按需打开 PNG 截图核对。

### GitHub 预览
PNG 截图在 GitHub Web 界面可直接查看，无需下载 PDF。

---

## 📊 数据覆盖

| 数据类型 | 总记录数 | 有页码记录 | 覆盖率 |
|----------|---------|-----------|--------|
| `subscription_flow_gold` | 73 | 73 | 100% |
| `equity_snapshot_gold` | 25 | 21 | 84% |
| `share_transfer_flow_gold` | 8 | 8 | 100% |
| `cross_check_gold` | 18 | 18 | 100% |
| **合计** | **124** | **120** | **96.8%** |

> 注：`equity_snapshot_gold` 中 4 条记录缺少 `pdf_page`，在 `extraction_notes` 中有章节定位信息。

---

## 🔗 相关文件

| 路径 | 用途 |
|------|------|
| `week3/data/*.pdf` | 源招股书 PDF |
| `week3/manual_gold/*_gold.jsonl` | Gold 抽取记录（含 `pdf_page`） |
| `week3/manual_gold/annotation_index.csv` | 人工标注索引 |
| `week3/manual_gold/manual_review_queue.csv` | 复核队列 |
| `scripts/build_annotations_pdf.py` | 批注生成脚本 |
| `week2/outputs/jsonl/*.jsonl` | 自动化抽取记录（无 `pdf_page`，不直接用于批注） |

---

*Last updated: 2026-06-19 | Annotator: yang111-svg*
