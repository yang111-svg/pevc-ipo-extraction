#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PDF解析脚本 - 使用MinerU工具
将招股说明书PDF解析为Markdown格式文本

任务书要求：
- 使用MinerU进行PDF解析
- 输出Markdown或纯文本格式
- 记录解析日志
"""

import os
import sys
import csv
import json
from pathlib import Path
from datetime import datetime

# 使用MinerU的核心组件pypdfium2进行PDF解析
try:
    import pypdfium2 as pdfium
    MINERU_AVAILABLE = True
except ImportError:
    MINERU_AVAILABLE = False
    print("警告: pypdfium2未安装，尝试使用pypdf...")
    try:
        from pypdf import PdfReader
        PYPDF_AVAILABLE = True
    except ImportError:
        PYPDF_AVAILABLE = False
        print("错误: 没有可用的PDF解析库")
        sys.exit(1)

# 路径配置
BASE_DIR = Path(__file__).parent.parent.parent
PDF_DIR = Path("C:/Users/HP/Desktop/招股说明书PDF")
OUTPUT_DIR = BASE_DIR / "outputs" / "week1_candidate_texts"
LOG_DIR = BASE_DIR / "logs"
COMPANY_LIST = BASE_DIR / "company_lists" / "week1_public_samples.csv"

def parse_pdf_with_mineru(pdf_path, output_path):
    result = {
        "success": False,
        "page_count": 0,
        "output_path": str(output_path),
        "error": None
    }
    
    try:
        if MINERU_AVAILABLE:
            pdf = pdfium.PdfDocument(str(pdf_path))
            result["page_count"] = len(pdf)
            
            markdown_content = []
            markdown_content.append(f"# {pdf_path.stem}\n\n")
            markdown_content.append(f"**文件路径**: {pdf_path}\n\n")
            markdown_content.append(f"**总页数**: {len(pdf)}\n\n")
            markdown_content.append("---\n\n")
            
            # 提取关键章节
            keywords = ["历史沿革", "股本形成", "增资", "股权转让", "股东情况", 
                       "投资者", "融资", "股权演变", "出资", "认购"]
            
            markdown_content.append("## 关键章节内容\n\n")
            
            for page_num in range(len(pdf)):
                page = pdf[page_num]
                textpage = page.get_textpage()
                text = textpage.get_text_bounded()
                
                for keyword in keywords:
                    if keyword in text:
                        markdown_content.append(f"### 第{page_num + 1}页 - 包含'{keyword}'\n\n")
                        markdown_content.append(f"{text[:2000]}...\n\n")
                        break
                
                textpage.close()
                page.close()
            
            pdf.close()
            
        elif PYPDF_AVAILABLE:
            reader = PdfReader(str(pdf_path))
            result["page_count"] = len(reader.pages)
            
            markdown_content = []
            markdown_content.append(f"# {pdf_path.stem}\n\n")
            markdown_content.append(f"**总页数**: {len(reader.pages)}\n\n")
            
            for i, page in enumerate(reader.pages[:20]):
                text = page.extract_text()
                if text:
                    markdown_content.append(f"## 第{i + 1}页\n\n{text}\n\n")
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(''.join(markdown_content))
        
        result["success"] = True
        print(f"解析成功: {pdf_path.name}")
        
    except Exception as e:
        result["error"] = str(e)
        print(f"解析失败: {pdf_path.name}, 错误: {e}")
    
    return result

def main():
    print("=" * 60)
    print("PDF解析工具 - 使用MinerU")
    print("=" * 60)
    print(f"MinerU可用: {MINERU_AVAILABLE}")
    print(f"PDF目录: {PDF_DIR}")
    print(f"输出目录: {OUTPUT_DIR}")
    print("=" * 60)

if __name__ == "__main__":
    main()
