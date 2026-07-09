"""
Pydantic 模型定义 -- 用于 LLM 提取结果的校验与结构化输出。

四种记录类型:
  - SubscriptionFlow   : 认缴/增资流水
  - TransferFlow        : 股权转让流水
  - EquitySnapshot      : 股权结构时刻快照
  - EventCrossCheck     : 流量-存量交叉校验

相比之前版本的改进:
  - 新增 TransferFlow，独立处理股权转让（出让方/受让方各一条）
  - EquitySnapshot 增加快照事件锚点（关联的增资/转让事件）
  - 新增 EventCrossCheck 用于流量存量自检
  - 所有金额/股数统一增加 raw_value + raw_unit 字段记录原文
  - 增加 unit_issue_flag 标记易混淆的单位问题 (如 78 vs 780)
  - 增加 cross_check 相关字段
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# 枚举定义
# ---------------------------------------------------------------------------

class RecordType(str, Enum):
    SUBSCRIPTION_FLOW = "subscription_flow"
    TRANSFER_FLOW = "transfer_flow"
    EQUITY_SNAPSHOT = "equity_snapshot"
    CROSS_CHECK = "cross_check"


class EventType(str, Enum):
    """股本变化事件类型"""
    CAPITAL_INCREASE = "增资"
    EQUITY_TRANSFER_OUT = "股权转让（出让）"
    EQUITY_TRANSFER_IN = "股权转让（受让）"
    CAPITAL_DECREASE = "减资"
    FOUNDING_CONTRIBUTION = "设立出资"
    ABSORPTION_MERGER = "吸收合并"
    CAPITAL_RESERVE_CONVERSION = "资本公积转增股本"
    SHARE_REFORM = "股份制改造/整体变更"


class InvestorType(str, Enum):
    """投资者类型"""
    FOUNDER = "创始人/创始人控制"
    PE = "PE/私募股权投资基金"
    VC = "VC/风险投资"
    ANGEL = "天使投资"
    STRATEGIC = "产业资本/战略投资者"
    GOV_GUIDANCE = "政府引导基金"
    ESOP = "员工持股平台"
    INDIVIDUAL = "个人投资者"
    CORP = "企业法人"
    STATE_OWNED = "国有资本"
    OTHER = "其他"


class Currency(str, Enum):
    CNY = "CNY"
    USD = "USD"
    HKD = "HKD"
    OTHER = "其他"


# ---------------------------------------------------------------------------
# SubscriptionFlow —— 认缴/增资流水
# ---------------------------------------------------------------------------

class SubscriptionFlow(BaseModel):
    """单条认缴/增资/减资/设立出资记录"""

    record_type: str = Field(
        default="subscription_flow",
        description='固定为 "subscription_flow"',
    )
    company_name: str = Field(
        ...,
        description="公司全称",
    )
    stock_code: str = Field(
        ...,
        description="股票代码（如 301581）",
    )
    event_type: str = Field(
        ...,
        description="事件类型: 增资/减资/设立出资/吸收合并/资本公积转增股本/股份制改造",
        examples=["增资", "设立出资", "吸收合并"],
    )
    event_date: Optional[str] = Field(
        None,
        description="事件日期，优先 YYYY-MM-DD，次优 YYYY-MM 或 YYYY",
        examples=["2018-06-15", "2018-06", "2018"],
    )
    event_order: Optional[int] = Field(
        None,
        description="事件在整个股本变化时间线中的序号（从1开始），用于排序和交叉检验",
    )

    # --- 投资者信息 ---
    investor_name: str = Field(
        ...,
        description="投资者/股东全称（原文）",
    )
    investor_type: Optional[str] = Field(
        None,
        description="投资者类型: 创始人/PE/VC/天使/产业资本/政府引导基金/员工持股平台/个人/企业法人/国有资本/其他",
    )

    # --- 股份/出资信息 ---
    subscription_qty_wan: Optional[float] = Field(
        None,
        description="认购/出资股数，单位：万股",
    )
    subscription_qty_raw: Optional[str] = Field(
        None,
        description="原文中的股数原始值和单位，用于复核（如'780万股'、'15,000,000股'）",
    )
    subscription_amount_wan: Optional[float] = Field(
        None,
        description="认购/出资金额，单位：万元",
    )
    subscription_amount_raw: Optional[str] = Field(
        None,
        description="原文中的金额原始值和单位，用于复核（如'1,500万元'、'1.5亿元'）",
    )
    subscription_price: Optional[float] = Field(
        None,
        description="每股认购价格，单位：元/股",
    )
    subscription_price_raw: Optional[str] = Field(
        None,
        description="原文中的价格原始值和单位（如'12.5元/股'）",
    )

    # --- 注册资本变化 ---
    registered_capital_before: Optional[float] = Field(
        None,
        description="本次增资前注册资本，单位：万元",
    )
    registered_capital_after: Optional[float] = Field(
        None,
        description="本次增资后注册资本，单位：万元",
    )

    # --- 单位问题标记 ---
    unit_issue_flag: Optional[bool] = Field(
        None,
        description="是否存在单位歧义（如股 vs 万股、元 vs 万元），需要人工复核",
    )
    unit_issue_note: Optional[str] = Field(
        None,
        description="单位歧义的详细说明",
    )

    # --- 证据与溯源 ---
    currency: Optional[str] = Field(
        None,
        description="货币: CNY/USD/HKD/其他",
    )
    pdf_page: Optional[int] = Field(
        None,
        description="事件在PDF中的页码（从1开始）",
    )
    evidence_text: Optional[str] = Field(
        None,
        description="招股书原文证据片段（建议长度 100-500 字）",
    )
    extraction_method: Optional[str] = Field(
        None,
        description="提取方式: rule_based/llm_extracted/llm_verified/manual",
    )
    extraction_notes: Optional[str] = Field(
        None,
        description="提取备注（事件特殊情况、歧义说明等）",
    )

    @field_validator("record_type")
    @classmethod
    def validate_record_type(cls, v: str) -> str:
        if v != RecordType.SUBSCRIPTION_FLOW.value:
            raise ValueError(
                f'record_type 必须为 "{RecordType.SUBSCRIPTION_FLOW.value}"，实际为 "{v}"'
            )
        return v

    @field_validator("event_type")
    @classmethod
    def validate_event_type(cls, v: str) -> str:
        valid = {e.value for e in EventType}
        if v not in valid:
            raise ValueError(
                f"event_type 必须为以下之一: {valid}，实际为 \"{v}\""
            )
        return v


# ---------------------------------------------------------------------------
# TransferFlow —— 股权转让流水（独立类型）
# ---------------------------------------------------------------------------

class TransferFlow(BaseModel):
    """单条股权转让记录

    注意: 每笔股权转让生成两条 TransferFlow 记录:
      - 一条 event_type="股权转让（出让）"，描述转让方
      - 一条 event_type="股权转让（受让）"，描述受让方
    """

    record_type: str = Field(
        default="transfer_flow",
        description='固定为 "transfer_flow"',
    )
    company_name: str = Field(
        ...,
        description="公司全称",
    )
    stock_code: str = Field(
        ...,
        description="股票代码",
    )
    event_date: Optional[str] = Field(
        None,
        description="转让日期",
    )
    event_order: Optional[int] = Field(
        None,
        description="事件序号",
    )

    # --- 转让方 / 受让方 ---
    event_type: str = Field(
        ...,
        description="股权转让（出让）或 股权转让（受让）",
    )
    transferor_name: Optional[str] = Field(
        None,
        description="出让方名称（event_type为出让时填写）",
    )
    transferee_name: Optional[str] = Field(
        None,
        description="受让方名称（event_type为受让时填写）",
    )
    participant_type: Optional[str] = Field(
        None,
        description="参与方类型: 创始人/PE/VC/天使/产业资本/政府引导基金/员工持股平台/个人/企业法人/国有资本/其他",
    )

    # --- 转让标的 ---
    transfer_qty_wan: Optional[float] = Field(
        None,
        description="转让股数，单位：万股",
    )
    transfer_qty_raw: Optional[str] = Field(
        None,
        description="原文中的转让股数原始值",
    )
    transfer_amount_wan: Optional[float] = Field(
        None,
        description="转让价款，单位：万元",
    )
    transfer_amount_raw: Optional[str] = Field(
        None,
        description="原文中的转让价款原始值",
    )
    transfer_price: Optional[float] = Field(
        None,
        description="每股转让价格，单位：元/股",
    )

    # --- 转让前后持股 ---
    shareholding_before_pct: Optional[float] = Field(
        None,
        description="转让前持股比例 (%)",
    )
    shareholding_after_pct: Optional[float] = Field(
        None,
        description="转让后持股比例 (%)",
    )

    # --- 单位标记 ---
    unit_issue_flag: Optional[bool] = Field(
        None,
        description="是否存在单位歧义",
    )
    unit_issue_note: Optional[str] = Field(
        None,
        description="单位歧义说明",
    )

    # --- 配对标识 ---
    paired_transfer_id: Optional[str] = Field(
        None,
        description="配对转让记录的ID（出让和受让配对）",
    )

    # --- 证据 ---
    currency: Optional[str] = Field(None, description="货币")
    pdf_page: Optional[int] = Field(None, description="PDF 页码")
    evidence_text: Optional[str] = Field(None, description="原文证据")
    extraction_method: Optional[str] = Field(None, description="提取方式")
    extraction_notes: Optional[str] = Field(None, description="提取备注")

    @field_validator("record_type")
    @classmethod
    def validate_record_type(cls, v: str) -> str:
        if v != RecordType.TRANSFER_FLOW.value:
            raise ValueError(
                f'record_type 必须为 "{RecordType.TRANSFER_FLOW.value}"，实际为 "{v}"'
            )
        return v


# ---------------------------------------------------------------------------
# ShareholderDetail —— 单个股东信息
# ---------------------------------------------------------------------------

class ShareholderDetail(BaseModel):
    """单个股东在某一时刻的持股信息"""

    shareholder_name: str = Field(
        ...,
        description="股东全称（原文）",
    )
    shares_wan: Optional[float] = Field(
        None,
        description="持股数量，单位：万股",
    )
    shares_raw: Optional[str] = Field(
        None,
        description="原文持股数量原始值",
    )
    shareholding_pct: Optional[float] = Field(
        None,
        description="持股比例 (%)",
    )
    shareholder_type: Optional[str] = Field(
        None,
        description="股东类型",
    )
    shareholder_category: Optional[str] = Field(
        None,
        description="股东类别: 控股股东/实际控制人/一致行动人/持股5%以上/发起人/其他",
    )


# ---------------------------------------------------------------------------
# EquitySnapshot —— 股权快照
# ---------------------------------------------------------------------------

class EquitySnapshot(BaseModel):
    """某一时刻的股权结构快照"""

    record_type: str = Field(
        default="equity_snapshot",
        description='固定为 "equity_snapshot"',
    )
    company_name: str = Field(..., description="公司全称")
    stock_code: str = Field(..., description="股票代码")
    snapshot_label: str = Field(
        ...,
        description="时刻标签，如 t0（设立时）、t1（第一次变更后）等",
    )
    snapshot_date: Optional[str] = Field(
        None,
        description="快照对应日期",
    )

    # --- 快照对应的触发事件 ---
    trigger_event: Optional[str] = Field(
        None,
        description="触发此次快照的事件描述（如'XX增资完成后'、'IPO发行前'等）",
    )
    trigger_event_order: Optional[int] = Field(
        None,
        description="关联的 SubscriptionFlow.event_order",
    )

    # --- 公司层面 ---
    total_shares_wan: Optional[float] = Field(
        None,
        description="公司总股本，单位：万股",
    )
    registered_capital_wan: Optional[float] = Field(
        None,
        description="注册资本，单位：万元",
    )
    capital_unit_note: Optional[str] = Field(
        None,
        description="注册资本单位说明（如'元'而原文为'780万元'）——用于标记单位混淆风险",
    )

    # --- 股东列表 ---
    shareholders: list[ShareholderDetail] = Field(
        default_factory=list,
        description="股东列表",
    )
    shareholder_count: Optional[int] = Field(
        None,
        description="股东总数（供 cross-check）",
    )

    # --- 流量-存量交叉校验 ---
    flow_to_stock_check: Optional[str] = Field(
        None,
        description="流量与存量交叉校验结果: matched/mismatch/not_applicable",
    )
    flow_to_stock_note: Optional[str] = Field(
        None,
        description="交叉校验差异说明（如'总股本与上期快照+本期增资差XX万元'）",
    )

    # --- 证据 ---
    pdf_page: Optional[int] = Field(None, description="PDF 页码")
    evidence_text: Optional[str] = Field(None, description="原文证据")
    extraction_notes: Optional[str] = Field(None, description="提取备注")

    @field_validator("record_type")
    @classmethod
    def validate_record_type(cls, v: str) -> str:
        if v != RecordType.EQUITY_SNAPSHOT.value:
            raise ValueError(
                f'record_type 必须为 "{RecordType.EQUITY_SNAPSHOT.value}"，实际为 "{v}"'
            )
        return v


# ---------------------------------------------------------------------------
# EventCrossCheck —— 流量-存量交叉校验
# ---------------------------------------------------------------------------

class EventCrossCheck(BaseModel):
    """流量-存量交叉校验记录

    用于验证: 上一期快照 + 本期增资事件 = 本期快照
    """

    record_type: str = Field(
        default="cross_check",
        description='固定为 "cross_check"',
    )
    company_name: str = Field(..., description="公司全称")
    stock_code: str = Field(..., description="股票代码")
    check_point: str = Field(
        ...,
        description="校验点描述（如't1快照 vs t0快照 + 第一次增资'）",
    )
    previous_snapshot_label: str = Field(
        ...,
        description="上期快照标签（如 t0）",
    )
    current_snapshot_label: str = Field(
        ...,
        description="本期快照标签（如 t1）",
    )
    flow_events: list[str] = Field(
        default_factory=list,
        description="两期之间的股本变化事件 event_order 列表",
    )
    flow_total_change_wan: Optional[float] = Field(
        None,
        description="流量合计变化量，单位：万股",
    )
    stock_change_wan: Optional[float] = Field(
        None,
        description="存量变化量（本期总股本-上期总股本），单位：万股",
    )
    difference_wan: Optional[float] = Field(
        None,
        description="差异 = 流量合计 - 存量变化，单位：万股",
    )
    check_result: str = Field(
        ...,
        description="校验结果: ok（匹配）/ gap（有缺口）/ unverified（无法校验）",
    )
    check_note: Optional[str] = Field(
        None,
        description="校验说明",
    )

    @field_validator("record_type")
    @classmethod
    def validate_record_type(cls, v: str) -> str:
        if v != RecordType.CROSS_CHECK.value:
            raise ValueError(
                f'record_type 必须为 "{RecordType.CROSS_CHECK.value}"，实际为 "{v}"'
            )
        return v
