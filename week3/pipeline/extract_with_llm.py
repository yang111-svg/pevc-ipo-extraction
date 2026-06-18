# -*- coding: utf-8 -*-
"""
extract_with_llm.py - LLM提取脚本（框架）

读取候选事件文本，调用 OpenAI API 进行结构化信息提取。
支持从 ../prompts/ 目录读取 system_prompt.md 和 user_prompt_template.md。
若未配置 API key，则使用模拟模式输出。

用法:
    python extract_with_llm.py --input-dir ../outputs/raw_llm_outputs --output-dir ../outputs/auto_jsonl
    python extract_with_llm.py --input-dir ../outputs/raw_llm_outputs --output-dir ../outputs/auto_jsonl --model gpt-4o
"""

import argparse
import json
import logging
import os
import re
import sys
from datetime import datetime

# 尝试导入 openai
try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    encoding="utf-8",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Prompt 加载
# ---------------------------------------------------------------------------

def load_prompt(prompt_path):
    """加载 prompt 文件内容。"""
    if os.path.isfile(prompt_path):
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    else:
        logger.warning("Prompt文件不存在: %s，使用默认prompt", prompt_path)
        return None


def get_default_system_prompt():
    """默认的 system prompt。"""
    return (
        "你是一个专业的金融文档信息提取助手。"
        "你的任务是从招股说明书的文本中提取股本变化事件的结构化信息。"
        "请严格按照指定的JSON Schema格式输出。"
        "如果无法从文本中提取某个字段，请输出空字符串。"
    )


def get_default_user_template():
    """默认的 user prompt 模板。"""
    return (
        "请从以下招股说明书文本中提取股本变化事件信息。\n\n"
        "## 待提取文本\n"
        "{text}\n\n"
        "## 输出要求\n"
        "请以JSON格式输出，包含以下字段:\n"
        "- investor_name: 投资者/股东名称\n"
        "- subscription_amount: 认缴金额（数字）\n"
        "- subscription_shares: 认缴股数（数字）\n"
        "- price_per_share: 每股价格（数字）\n"
        "- date: 事件日期\n"
        "- total_capital_after: 变更后总股本\n"
        "- event_type: 事件类型（增资/减资/转让/整体变更等）\n"
        "- summary: 事件摘要（一句话）"
    )


# ---------------------------------------------------------------------------
# LLM 调用
# ---------------------------------------------------------------------------

def call_llm(client, model, system_prompt, user_message, temperature=0.0):
    """调用 OpenAI API。"""
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=temperature,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content
        return content
    except Exception as e:
        logger.error("LLM调用失败: %s", e)
        return None


def mock_llm_extract(text):
    """模拟LLM提取（无API key时使用）。"""
    # 简单的模拟提取
    event = {
        "investor_name": "",
        "subscription_amount": "",
        "subscription_shares": "",
        "price_per_share": "",
        "date": "",
        "total_capital_after": "",
        "event_type": "",
        "summary": text[:100] + "..." if len(text) > 100 else text,
    }

    # 尝试提取日期
    date_match = re.search(r"(\d{4})\s*年\s*(\d{1,2})\s*月", text)
    if date_match:
        event["date"] = "{}年{}月".format(date_match.group(1), date_match.group(2))

    # 尝试提取公司名
    company_match = re.search(
        r"([\u4e00-\u9fff\w]+(?:有限公司|股份有限公司|有限责任公司))", text
    )
    if company_match:
        event["investor_name"] = company_match.group(1)

    return event


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="LLM提取 - 使用大语言模型从候选事件中提取结构化信息"
    )
    parser.add_argument(
        "--input-dir",
        type=str,
        default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "outputs", "raw_llm_outputs"),
        help="候选事件文件目录 (默认: ../outputs/raw_llm_outputs)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "outputs", "auto_jsonl"),
        help="JSONL输出目录 (默认: ../outputs/auto_jsonl)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-4o-mini",
        help="OpenAI模型名称 (默认: gpt-4o-mini)",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.0,
        help="生成温度 (默认: 0.0)",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        default=False,
        help="强制使用模拟模式（不调用API）",
    )
    args = parser.parse_args()

    logger.info("输入目录: %s", os.path.abspath(args.input_dir))
    logger.info("输出目录: %s", os.path.abspath(args.output_dir))
    logger.info("模型: %s", args.model)

    # 加载 prompts
    prompts_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "prompts"
    )
    system_prompt = load_prompt(os.path.join(prompts_dir, "system_prompt.md"))
    if not system_prompt:
        system_prompt = get_default_system_prompt()

    user_template = load_prompt(os.path.join(prompts_dir, "user_prompt_template.md"))
    if not user_template:
        user_template = get_default_user_template()

    logger.info("System prompt: %d 字符", len(system_prompt))
    logger.info("User template: %d 字符", len(user_template))

    # 初始化 OpenAI client
    api_key = os.environ.get("OPENAI_API_KEY", "")
    base_url = os.environ.get("OPENAI_BASE_URL", "")

    use_mock = args.mock or not HAS_OPENAI or not api_key

    if use_mock:
        logger.info("使用模拟模式（不调用API）")
        client = None
    else:
        logger.info("使用 OpenAI API (base_url: %s)", base_url or "default")
        client_kwargs = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url
        client = OpenAI(**client_kwargs)

    # 查找候选文件
    candidate_files = sorted([
        f for f in os.listdir(args.input_dir)
        if f.endswith("_candidates.json")
    ])

    if not candidate_files:
        logger.warning("未找到任何 _candidates.json 文件")
        sys.exit(0)

    logger.info("找到 %d 个候选文件", len(candidate_files))

    os.makedirs(args.output_dir, exist_ok=True)

    for cand_file in candidate_files:
        source_name = cand_file.replace("_candidates.json", "")
        logger.info("正在处理: %s", source_name)

        try:
            cand_path = os.path.join(args.input_dir, cand_file)
            with open(cand_path, "r", encoding="utf-8") as f:
                candidates = json.load(f)

            # 输出文件名（加 llm 前缀区分）
            output_filename = "{}_llm_auto.jsonl".format(
                re.sub(r'[\\/:*?"<>|]', '_', source_name)
            )
            output_path = os.path.join(args.output_dir, output_filename)

            event_count = 0
            with open(output_path, "w", encoding="utf-8") as out_f:
                for cand in candidates:
                    text = cand["text"]
                    section = cand.get("section", "")
                    source_page = cand.get("source_page", 0)
                    candidate_index = cand.get("index", 0)

                    if use_mock:
                        # 模拟模式
                        llm_result = mock_llm_extract(text)
                    else:
                        # 调用LLM
                        user_message = user_template.format(text=text)
                        raw_response = call_llm(
                            client, args.model,
                            system_prompt, user_message,
                            temperature=args.temperature,
                        )
                        if raw_response:
                            try:
                                llm_result = json.loads(raw_response)
                            except json.JSONDecodeError:
                                logger.warning(
                                    "JSON解析失败，使用模拟提取 (候选 %d)",
                                    candidate_index,
                                )
                                llm_result = mock_llm_extract(text)
                        else:
                            llm_result = mock_llm_extract(text)

                    # 构造完整事件记录
                    event = {
                        "event_index": candidate_index,
                        "section": section,
                        "source_page": source_page,
                        "investor_name": llm_result.get("investor_name", ""),
                        "subscription_amount": llm_result.get("subscription_amount", ""),
                        "subscription_shares": llm_result.get("subscription_shares", ""),
                        "price_per_share": llm_result.get("price_per_share", ""),
                        "date": llm_result.get("date", ""),
                        "total_capital_after": llm_result.get("total_capital_after", ""),
                        "event_type": llm_result.get("event_type", ""),
                        "summary": llm_result.get("summary", ""),
                        "raw_text": text[:500],
                        "extraction_method": "llm_{}".format(args.model),
                        "confidence": "high",
                        "model": args.model,
                    }

                    out_f.write(json.dumps(event, ensure_ascii=False) + "\n")
                    event_count += 1

            logger.info("  提取 %d 条事件 -> %s", event_count, output_path)

        except Exception as e:
            logger.error("处理失败 %s: %s", cand_file, e)

    logger.info("全部完成!")


if __name__ == "__main__":
    main()