# -*- coding: utf-8 -*-
"""
parse_with_mineru.py — 使用 MinerU 将 PDF 转换为 Markdown

相比 parse_pdf.py (pdfplumber/PyMuPDF) 的改进:
  - 保留表格结构 (Markdown table)
  - 识别标题层级 (H1/H2/H3 对应 # ## ###)
  - 图片提取到独立目录
  - 页码信息和文本块边界保留

依赖: MinerU (pip install mineru[all])
用法:
    python parse_with_mineru.py --input-dir ../data --output-dir ../outputs/mineru_md
    python parse_with_mineru.py --input-dir ../data --output-dir ../outputs/mineru_md --company 黄山谷捷
"""

import argparse
import json
import logging
import os
import re
import subprocess
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    encoding="utf-8",
)
logger = logging.getLogger(__name__)

# MinerU 可执行文件路径
MINERU_BIN = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "..", "..", "..", "D:", "mineru_env", "Scripts", "mineru.exe",
)
# 如果相对路径不可用，尝试绝对路径
if not os.path.exists(MINERU_BIN):
    MINERU_BIN = r"D:\mineru_env\Scripts\mineru.exe"
if not os.path.exists(MINERU_BIN):
    MINERU_BIN = "mineru"  # fallback to PATH

# MinerU 后端选择: pipeline (本地, free, 需 RAM) 或 vlm-http-client (云端, 需 API)
DEFAULT_BACKEND = "pipeline"


def find_pdfs(input_dir, company=None):
    """扫描目录下的 PDF 文件"""
    results = []
    for fname in sorted(os.listdir(input_dir)):
        if fname.lower().endswith(".pdf"):
            pdf_path = os.path.join(input_dir, fname)
            # 提取股票代码和公司名
            m = re.match(r"^(\d{6})_(.+)\.pdf$", fname)
            if m:
                stock_code, company_name = m.group(1), m.group(2)
            else:
                stock_code = ""
                company_name = Path(fname).stem
            if company and company not in company_name:
                continue
            results.append({
                "pdf_path": pdf_path,
                "company": company_name,
                "stock_code": stock_code,
            })
    logger.info("找到 %d 个 PDF 文件", len(results))
    return results


def parse_pdf_with_mineru(pdf_path, output_dir, backend=DEFAULT_BACKEND,
                          start_page=None, end_page=None):
    """调用 MinerU CLI 将 PDF 转为 Markdown

    Args:
        pdf_path: PDF 文件路径
        output_dir: 输出目录（MinerU 会在其下创建以文件名为名的子目录）
        backend: MinerU 后端
        start_page: 起始页（0-indexed）
        end_page: 终止页（0-indexed, 不含）

    Returns:
        (markdown_path, output_subdir) 或 (None, None) 即失败
    """
    cmd = [
        MINERU_BIN,
        "-p", pdf_path,
        "-o", output_dir,
        "-b", backend,
    ]
    if start_page is not None:
        cmd.extend(["-s", str(start_page)])
    if end_page is not None:
        cmd.extend(["-e", str(end_page)])

    logger.info("执行: %s", " ".join(cmd))
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3600,  # 1 hour timeout for large PDFs
        )
        if result.returncode != 0:
            logger.error("MinerU 返回非零: %d", result.returncode)
            # 打印最后 500 个字符的错误信息
            err_tail = result.stderr[-500:] if len(result.stderr) > 500 else result.stderr
            logger.error("MinerU stderr: %s", err_tail)
            return None, None

        # MinerU 在 output_dir 下创建 <stem>/<stem>.md
        stem = Path(pdf_path).stem
        md_path = os.path.join(output_dir, stem, f"{stem}.md")
        if os.path.exists(md_path):
            logger.info("Markdown 已生成: %s", md_path)
            return md_path, os.path.join(output_dir, stem)
        else:
            logger.error("未找到输出的 Markdown 文件: %s", md_path)
            return None, None

    except subprocess.TimeoutExpired:
        logger.error("MinerU 超时 (1h)")
        return None, None
    except Exception as e:
        logger.error("MinerU 执行失败: %s", e)
        return None, None


def main():
    parser = argparse.ArgumentParser(
        description="使用 MinerU 将招股书 PDF 转为 Markdown"
    )
    parser.add_argument(
        "--input-dir",
        type=str,
        default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data"),
        help="PDF 目录",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "outputs", "mineru_md"),
        help="Markdown 输出目录",
    )
    parser.add_argument(
        "--company",
        type=str,
        default=None,
        help="指定公司名称",
    )
    parser.add_argument(
        "--backend",
        type=str,
        default=DEFAULT_BACKEND,
        help="MinerU 后端",
    )
    parser.add_argument(
        "--start-page",
        type=int,
        default=None,
        help="起始页 (0-indexed)",
    )
    parser.add_argument(
        "--end-page",
        type=int,
        default=None,
        help="终止页 (0-indexed, 不含)",
    )
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    pdfs = find_pdfs(args.input_dir, args.company)

    for item in pdfs:
        logger.info("处理: %s (%s)", item["company"], item["stock_code"])
        md_path, out_dir = parse_pdf_with_mineru(
            item["pdf_path"],
            args.output_dir,
            backend=args.backend,
            start_page=args.start_page,
            end_page=args.end_page,
        )
        if md_path:
            logger.info("  -> Markdown: %s", md_path)
            logger.info("  -> 资源目录: %s", out_dir)
        else:
            logger.warning("  -> 处理失败")


if __name__ == "__main__":
    main()
