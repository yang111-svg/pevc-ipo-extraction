# -*- coding: utf-8 -*-
"""
parse_pdf.py - PDF文本解析脚本

从 data/ 目录下读取PDF招股说明书，逐页提取文本，
输出为 txt 文件（每页一个段落，保留页码信息）。

依赖: pdfplumber 或 PyMuPDF (fitz)
用法:
    python parse_pdf.py --input-dir ../data --output-dir ../outputs/logs
    python parse_pdf.py --input-dir ../data --output-dir ../outputs/logs --company 友升股份
"""

import argparse
import csv
import logging
import os
import re
import sys
from pathlib import Path

# 尝试导入 PDF 解析库
try:
    import pdfplumber
    BACKEND = "pdfplumber"
except ImportError:
    try:
        import fitz  # PyMuPDF
        BACKEND = "pymupdf"
    except ImportError:
        print("错误: 需要安装 pdfplumber 或 PyMuPDF (fitz)")
        print("  pip install pdfplumber")
        print("  或: pip install PyMuPDF")
        sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    encoding="utf-8",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 核心解析函数
# ---------------------------------------------------------------------------

def extract_text_pdfplumber(pdf_path):
    """使用 pdfplumber 逐页提取文本。

    Returns:
        [{"page": int, "text": str}, ...]
    """
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            # 清理多余空白
            text = re.sub(r"\s+", " ", text).strip()
            pages.append({"page": i, "text": text})
    return pages


def extract_text_pymupdf(pdf_path):
    """使用 PyMuPDF 逐页提取文本。

    Returns:
        [{"page": int, "text": str}, ...]
    """
    pages = []
    doc = fitz.open(pdf_path)
    for i in range(len(doc)):
        text = doc[i].get_text("text")
        text = re.sub(r"\s+", " ", text).strip()
        pages.append({"page": i + 1, "text": text})
    doc.close()
    return pages


def extract_text(pdf_path):
    """根据可用后端提取PDF文本。"""
    if BACKEND == "pdfplumber":
        return extract_text_pdfplumber(pdf_path)
    else:
        return extract_text_pymupdf(pdf_path)


# ---------------------------------------------------------------------------
# 文件发现
# ---------------------------------------------------------------------------

def find_pdfs(input_dir, company=None):
    """在 input_dir 中查找PDF文件。

    优先读取 pdf_manifest.csv 获取结构化信息；
    若不存在则扫描目录下所有 .pdf 文件。

    Returns:
        [{"pdf_path": str, "company": str, "stock_code": str}, ...]
    """
    manifest_path = os.path.join(input_dir, "pdf_manifest.csv")
    results = []

    if os.path.isfile(manifest_path):
        logger.info("从 pdf_manifest.csv 读取PDF清单")
        with open(manifest_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                pdf_file = row.get("pdf_path", "").strip()
                company_name = row.get("company_name", "").strip()
                stock_code = row.get("stock_code", "").strip()
                if not pdf_file:
                    continue
                # 支持绝对路径或相对于 input_dir 的路径
                if not os.path.isabs(pdf_file):
                    pdf_file = os.path.join(input_dir, pdf_file)
                if company and company not in company_name:
                    continue
                if os.path.isfile(pdf_file):
                    results.append({
                        "pdf_path": pdf_file,
                        "company": company_name,
                        "stock_code": stock_code,
                    })
                else:
                    logger.warning("PDF文件不存在: %s", pdf_file)
    else:
        logger.info("未找到 pdf_manifest.csv，扫描目录下的PDF文件")
        for fname in sorted(os.listdir(input_dir)):
            if fname.lower().endswith(".pdf"):
                pdf_path = os.path.join(input_dir, fname)
                results.append({
                    "pdf_path": pdf_path,
                    "company": Path(fname).stem,
                    "stock_code": "",
                })

    logger.info("共找到 %d 个PDF文件待处理", len(results))
    return results


# ---------------------------------------------------------------------------
# 输出写入
# ---------------------------------------------------------------------------

def write_output(pages, output_dir, company, stock_code):
    """将提取的页面文本写入txt文件。

    格式: 每页一个段落，以 [第X页] 开头。
    """
    os.makedirs(output_dir, exist_ok=True)

    # 构造文件名
    if stock_code:
        filename = "{}_{}_parsed.txt".format(stock_code, company)
    else:
        filename = "{}_parsed.txt".format(company)
    filename = re.sub(r'[\\/:*?"<>|]', '_', filename)
    output_path = os.path.join(output_dir, filename)

    with open(output_path, "w", encoding="utf-8") as f:
        for page_info in pages:
            f.write("[第{}页]\n".format(page_info["page"]))
            f.write(page_info["text"])
            f.write("\n\n")

    logger.info("已写入: %s (%d 页)", output_path, len(pages))
    return output_path


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="PDF文本解析 - 从招股说明书PDF中提取逐页文本"
    )
    parser.add_argument(
        "--input-dir",
        type=str,
        default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data"),
        help="PDF文件所在目录 (默认: ../data)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "outputs", "logs"),
        help="输出txt文件目录 (默认: ../outputs/logs)",
    )
    parser.add_argument(
        "--company",
        type=str,
        default=None,
        help="可选: 指定公司名称进行过滤 (如: 友升股份)",
    )
    args = parser.parse_args()

    logger.info("使用PDF解析后端: %s", BACKEND)
    logger.info("输入目录: %s", os.path.abspath(args.input_dir))
    logger.info("输出目录: %s", os.path.abspath(args.output_dir))

    # 查找PDF文件
    pdf_list = find_pdfs(args.input_dir, args.company)
    if not pdf_list:
        logger.warning("未找到任何PDF文件")
        sys.exit(0)

    # 逐个解析
    output_files = []
    for item in pdf_list:
        logger.info("正在解析: %s (%s)", item["company"], item["pdf_path"])
        try:
            pages = extract_text(item["pdf_path"])
            output_path = write_output(
                pages, args.output_dir, item["company"], item["stock_code"]
            )
            output_files.append(output_path)
        except Exception as e:
            logger.error("解析失败 %s: %s", item["pdf_path"], e)

    logger.info("完成! 共处理 %d 个文件, 生成 %d 个txt文件", len(pdf_list), len(output_files))


if __name__ == "__main__":
    main()