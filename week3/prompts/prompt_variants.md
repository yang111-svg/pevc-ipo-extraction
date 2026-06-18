# Prompt Variants -- 变体对比

## Variant A：简洁版 Prompt

### 设计思路
使用最精简的指令，仅包含核心任务描述和输出格式要求，不提供示例。

### Prompt 内容

从以下招股说明书文本中提取所有股本变化事件（增资、股权转让、减资、设立出资）。
输出JSON数组，每条记录包含：record_type, company_name, stock_code, investor_name,
subscription_qty_wan(万股), subscription_amount_wan(万元), subscription_price(元/股),
subscription_date, event_type, evidence_text。

公司：{company_name}，代码：{stock_code}

文本：
{text}

### 预期特点
- **速度**：快（token数少，推理开销低）
- **精度**：较低（缺少示例和详细规则，LLM可能对边界情况判断不一致）
- **适用场景**：快速扫描、大规模初筛、对精度要求不高的场景

---

## Variant B：详细版 Prompt（带 Few-Shot 示例）

### 设计思路
在完整规则定义的基础上，提供2-3个典型示例（few-shot），帮助LLM理解输出期望。

### Prompt 内容

你是一个专业的金融信息提取助手。请从招股说明书文本中提取所有股本变化事件。

## 事件类型
- 增资：投资者向公司新增出资，公司注册资本增加
- 股权转让（出让）：股东将股权转让给他人（出让方）
- 股权转让（受让）：投资者从他人处受让股权（受让方）
- 减资：公司减少注册资本
- 设立出资：公司设立时创始股东初始出资

## 输出格式
JSON数组，字段：record_type("subscription_flow"), company_name, stock_code,
investor_name, subscription_qty_wan(万股), subscription_amount_wan(万元),
subscription_price(元/股), subscription_date(YYYY-MM-DD), event_type, evidence_text

## 单位要求
股数统一为万股，金额统一为万元。原文为"元"需除以10000，原文为"亿元"需乘以10000。

## 示例

### 示例1：增资
输入：2019年3月，XX投资以货币方式向公司增资2,000万元，认购新增注册资本150万股。
输出：
[{
  "record_type": "subscription_flow",
  "company_name": "XX科技股份有限公司",
  "stock_code": "688XXX",
  "investor_name": "XX投资",
  "subscription_qty_wan": 150,
  "subscription_amount_wan": 2000,
  "subscription_price": 13.33,
  "subscription_date": "2019-03",
  "event_type": "增资",
  "evidence_text": "2019年3月，XX投资以货币方式向公司增资2,000万元，认购新增注册资本150万股。"
}]

### 示例2：股权转让
输入：2020年6月，张三将其持有的公司100万股股权（对应出资额500万元）以800万元的价格转让给李四。
输出：
[
  {
    "record_type": "subscription_flow",
    "company_name": "XX科技股份有限公司",
    "stock_code": "688XXX",
    "investor_name": "张三",
    "subscription_qty_wan": 100,
    "subscription_amount_wan": 800,
    "subscription_price": 8.0,
    "subscription_date": "2020-06",
    "event_type": "股权转让（出让）",
    "evidence_text": "2020年6月，张三将其持有的公司100万股股权（对应出资额500万元）以800万元的价格转让给李四。"
  },
  {
    "record_type": "subscription_flow",
    "company_name": "XX科技股份有限公司",
    "stock_code": "688XXX",
    "investor_name": "李四",
    "subscription_qty_wan": 100,
    "subscription_amount_wan": 800,
    "subscription_price": 8.0,
    "subscription_date": "2020-06",
    "event_type": "股权转让（受让）",
    "evidence_text": "2020年6月，张三将其持有的公司100万股股权（对应出资额500万元）以800万元的价格转让给李四。"
  }
]

### 示例3：设立出资
输入：2015年1月，公司设立，发起人王五出资500万元，认购500万股。
输出：
[{
  "record_type": "subscription_flow",
  "company_name": "XX科技股份有限公司",
  "stock_code": "688XXX",
  "investor_name": "王五",
  "subscription_qty_wan": 500,
  "subscription_amount_wan": 500,
  "subscription_price": 1.0,
  "subscription_date": "2015-01",
  "event_type": "设立出资",
  "evidence_text": "2015年1月，公司设立，发起人王五出资500万元，认购500万股。"
}]

## 注意事项
- 同一笔股权转让，出让方和受让方分别生成记录
- evidence_text必须包含原文证据
- 仅提取明确描述的事件，不要推测

公司：{company_name}，代码：{stock_code}

文本：
{text}

### 预期特点
- **速度**：慢（token数多，推理开销高）
- **精度**：较高（有示例引导，LLM对格式和边界情况理解更准确）
- **适用场景**：高精度提取、标注质量要求高的场景、模型能力较弱的场景

---

## 对比总结

| 维度 | Variant A（简洁版） | Variant B（详细版） |
|------|---------------------|---------------------|
| Prompt 长度 | ~200 tokens | ~800 tokens |
| 推理速度 | 快 | 慢 |
| 格式遵从度 | 中等 | 高 |
| 事件分类准确率 | 中等 | 高 |
| 单位转换准确率 | 中等 | 高 |
| Token 成本 | 低 | 高（约3-4倍） |
| 适用模型 | GPT-4 / Claude等强模型 | 所有模型（含较弱模型） |

---

## 实际对比结果

> 请在此填写实际测试结果。

### 测试配置
- **测试样本数量**：（待填写）
- **测试模型**：（待填写）
- **测试文本来源**：（待填写）

### 结果数据

| 指标 | Variant A | Variant B | 差异 |
|------|-----------|-----------|------|
| 提取事件总数 | | | |
| 正确事件数 | | | |
| 准确率 (Precision) | | | |
| 召回率 (Recall) | | | |
| F1 Score | | | |
| 平均推理时间 (s) | | | |
| 平均 Token 消耗 | | | |
| 格式错误次数 | | | |

### 典型错误对比

### 结论