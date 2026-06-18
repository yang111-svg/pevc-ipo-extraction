# -*- coding: utf-8 -*-
"""
validate_schema.py - Schema校验脚本

使用 Pydantic 模型校验 auto_jsonl 中的提取结果，
输出校验日志到 CSV 文件。

用法:
    python validate_schema.py --input-dir ../outputs/auto_jsonl --output-dir ../outputs/logs
"""

import argparse
import csv
import json
import logging
import os
import re
import sys
from datetime import datetime

# 尝试导入 Pydantic
try:
    from pydantic import BaseModel, Field, ValidationError, field_validator
    HAS_PYDANTIC = True
except ImportError:
    HAS_PYDANTIC = False

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    encoding="utf-8",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic 模型定义
# ---------------------------------------------------------------------------

if HAS_PYDANTIC:
    # 尝试从上级 schemas 模块导入
    _schemas_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "schemas"
    )
    if os.path.isfile(os.path.join(_schemas_path, "extraction_models.py")):
        sys.path.insert(0, os.path.dirname(_schemas_path))
        try:
            from schemas.extraction_models import CapitalChangeEvent
            logger.info("从 schemas/extraction_models.py 导入 CapitalChangeEvent")
        except ImportError:
            # 内联定义
            HAS_IMPORTED = False
    else:
        HAS_IMPORTED = False

    if not HAS_IMPORTED or not HAS_PYDANTIC:
        class CapitalChangeEvent(BaseModel):
            """股本变化事件提取模型（内联定义）。"""
            event_index: int = Field(default=0, description="事件序号")
            section: str = Field(default="", description="所属章节")
            source_page: int = Field(default=0, description="来源页码")
            investor_name: str = Field(default="", description="投资者名称")
            subscription_amount: str = Field(default="", description="认缴金额")
            subscription_shares: str = Field(default="", description="认缴股数")
            price_per_share: str = Field(default="", description="每股价格")
            date: str = Field(default="", description="事件日期")
            total_capital_after: str = Field(default="", description="变更后总股本")
            raw_text: str = Field(default="", description="原始文本")
            extraction_method: str = Field(default="", description="提取方法")
            confidence: str = Field(default="", description="置信度")

            @field_validator("date")
            @classmethod
            def validate_date(cls, v):
                if v and v.strip():
                    # 简单校验日期格式
                    if not re.search(r"\d{4}", v):
                        raise ValueError("日期格式不正确: {}".format(v))
                return v

            @field_validator("subscription_amount", "subscription_shares", "price_per_share")
            @classmethod
            def validate_numeric_str(cls, v):
                if v and v.strip():
                    cleaned = v.replace(",", "").replace(" ", "")
                    if not re.match(r"^[\d.]+$", cleaned):
                        raise ValueError("数值格式不正确: {}".format(v))
                return v
else:
    # 无 Pydantic 时使用简单字典校验
    CapitalChangeEvent = None


# ---------------------------------------------------------------------------
# 校验逻辑
# ---------------------------------------------------------------------------

def validate_with_pydantic(record):
    """使用 Pydantic 模型校验单条记录。

    Returns:
        (is_valid, errors_list)
    """
    try:
        CapitalChangeEvent(**record)
        return True, []
    except ValidationError as e:
        errors = []
        for err in e.errors():
            field = " -> ".join(str(loc) for loc in err["loc"])
            msg = err["msg"]
            errors.append("{}: {}".format(field, msg))
        return False, errors


def validate_simple(record):
    """不使用 Pydantic 的简单校验。

    Returns:
        (is_valid, errors_list)
    """
    errors = []
    required_fields = ["investor_name", "date"]
    for field in required_fields:
        val = record.get(field, "")
        if not val or not val.strip():
            errors.append("{}: 缺失必填字段".format(field))

    # 校验日期格式
    date_val = record.get("date", "")
    if date_val and date_val.strip():
        if not re.search(r"\d{4}", date_val):
            errors.append("date: 日期格式不正确")

    # 校验数值字段
    for num_field in ["subscription_amount", "subscription_shares", "price_per_share"]:
        val = record.get(num_field, "")
        if val and val.strip():
            cleaned = val.replace(",", "").replace(" ", "")
            if not re.match(r"^[\d.]+$", cleaned):
                errors.append("{}: 数值格式不正确".format(num_field))

    return len(errors) == 0, errors


def validate_record(record):
    """校验单条记录。"""
    if HAS_PYDANTIC and CapitalChangeEvent:
        return validate_with_pydantic(record)
    else:
        return validate_simple(record)


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Schema校验 - 校验提取结果的字段格式和完整性"
    )
    parser.add_argument(
        "--input-dir",
        type=str,
        default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "outputs", "auto_jsonl"),
        help="JSONL文件目录 (默认: ../outputs/auto_jsonl)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "outputs", "logs"),
        help="校验日志输出目录 (默认: ../outputs/logs)",
    )
    args = parser.parse_args()

    logger.info("输入目录: %s", os.path.abspath(args.input_dir))
    logger.info("输出目录: %s", os.path.abspath(args.output_dir))
    logger.info("使用Pydantic: %s", HAS_PYDANTIC)

    # 查找所有 _auto.jsonl 文件
    jsonl_files = sorted([
        f for f in os.listdir(args.input_dir)
        if f.endswith(".jsonl")
    ])

    if not jsonl_files:
        logger.warning("未找到任何 .jsonl 文件")
        sys.exit(0)

    logger.info("找到 %d 个JSONL文件", len(jsonl_files))

    os.makedirs(args.output_dir, exist_ok=True)

    # 汇总校验结果
    all_results = []

    for jsonl_file in jsonl_files:
        source_name = jsonl_file.replace("_auto.jsonl", "")
        logger.info("正在校验: %s", source_name)

        jsonl_path = os.path.join(args.input_dir, jsonl_file)

        try:
            with open(jsonl_path, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, start=1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError as e:
                        all_results.append({
                            "source": source_name,
                            "line": line_num,
                            "status": "json_error",
                            "errors": "JSON解析错误: {}".format(str(e)),
                            "field": "",
                            "value": "",
                        })
                        continue

                    is_valid, errors = validate_record(record)

                    if is_valid:
                        all_results.append({
                            "source": source_name,
                            "line": line_num,
                            "status": "pass",
                            "errors": "",
                            "field": "",
                            "value": "",
                        })
                    else:
                        for err in errors:
                            parts = err.split(":", 1)
                            field = parts[0] if len(parts) > 1 else ""
                            msg = parts[1] if len(parts) > 1 else err
                            all_results.append({
                                "source": source_name,
                                "line": line_num,
                                "status": "fail",
                                "errors": msg.strip(),
                                "field": field.strip(),
                                "value": str(record.get(field.strip(), ""))[:100],
                            })

        except Exception as e:
            logger.error("校验失败 %s: %s", jsonl_file, e)

    # 写入CSV
    output_path = os.path.join(args.output_dir, "schema_validation_log.csv")
    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["source", "line", "status", "field", "errors", "value"])
        writer.writeheader()
        writer.writerows(all_results)

    # 统计
    total = len(all_results)
    passed = sum(1 for r in all_results if r["status"] == "pass")
    failed = total - passed

    logger.info("校验完成! 总计: %d, 通过: %d, 失败: %d", total, passed, failed)
    logger.info("校验日志已写入: %s", output_path)


if __name__ == "__main__":
    main()