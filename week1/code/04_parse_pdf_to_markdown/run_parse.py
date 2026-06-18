import csv
from pathlib import Path
from datetime import datetime
import pypdfium2 as pdfium

PDF_DIR = Path("C:/Users/HP/Desktop/招股说明书PDF")
OUTPUT_DIR = Path("C:/Users/HP/Desktop/prospectus-pevc-project/outputs/week1_candidate_texts")
COMPANY_LIST = Path("C:/Users/HP/Desktop/prospectus-pevc-project/company_lists/week1_public_samples.csv")
LOG_FILE = Path("C:/Users/HP/Desktop/prospectus-pevc-project/logs/parse_log.csv")

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

companies = []
with open(COMPANY_LIST, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        companies.append(row)

print(f"共 {len(companies)} 家公司")

results = []
for company in companies:
    code = company['stock_code']
    name = company['company_name']
    
    pdf_file = None
    for f in PDF_DIR.glob(f"{code}*.pdf"):
        pdf_file = f
        break
    
    if not pdf_file:
        print(f"找不到: {code}")
        results.append({'code': code, 'status': 'fail', 'pages': 0, 'error': 'File not found'})
        continue
    
    print(f"解析: {name} ({code})")
    
    try:
        pdf = pdfium.PdfDocument(str(pdf_file))
        page_count = len(pdf)
        
        md_content = [f"# {name}\n\n", f"**股票代码**: {code}\n\n", f"**总页数**: {page_count}\n\n", "---\n\n"]
        
        keywords = ["历史沿革", "股本形成", "增资", "股权转让", "股东情况", "投资者", "融资", "股权演变"]
        md_content.append("## 关键章节\n\n")
        
        found_keywords = set()
        for i in range(min(page_count, 100)):
            page = pdf[i]
            textpage = page.get_textpage()
            text = textpage.get_text_bounded()
            
            for kw in keywords:
                if kw in text and kw not in found_keywords:
                    md_content.append(f"### 第{i+1}页 - {kw}\n\n{text[:1500]}...\n\n")
                    found_keywords.add(kw)
                    break
            
            textpage.close()
            page.close()
        
        pdf.close()
        
        output_file = OUTPUT_DIR / f"{code}_{name.split('股份')[0]}_解析结果.md"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(''.join(md_content))
        
        print(f"  成功: {page_count}页")
        results.append({'code': code, 'status': 'success', 'pages': page_count, 'error': ''})
        
    except Exception as e:
        print(f"  失败: {e}")
        results.append({'code': code, 'status': 'fail', 'pages': 0, 'error': str(e)})

print(f"\n完成: {sum(1 for r in results if r['status']=='success')}/{len(results)}")
