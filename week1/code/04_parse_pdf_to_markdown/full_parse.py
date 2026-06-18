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
print("开始完整解析所有页面...\n")

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
        
        # 完整解析所有页面
        md_content = []
        md_content.append(f"# {name}\n\n")
        md_content.append(f"**股票代码**: {code}\n\n")
        md_content.append(f"**总页数**: {page_count}\n\n")
        md_content.append("---\n\n")
        
        for i in range(page_count):
            page = pdf[i]
            textpage = page.get_textpage()
            text = textpage.get_text_bounded()
            
            if text.strip():
                md_content.append(f"## 第{i+1}页\n\n")
                md_content.append(f"{text}\n\n")
            
            textpage.close()
            page.close()
            
            # 每50页显示进度
            if (i + 1) % 50 == 0:
                print(f"  进度: {i+1}/{page_count} 页")
        
        pdf.close()
        
        output_file = OUTPUT_DIR / f"{code}_{name.split('股份')[0]}_完整解析.md"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(''.join(md_content))
        
        print(f"  ✓ 完成: {page_count}页 -> {output_file.name}\n")
        results.append({'code': code, 'status': 'success', 'pages': page_count, 'error': ''})
        
    except Exception as e:
        print(f"  ✗ 失败: {e}\n")
        results.append({'code': code, 'status': 'fail', 'pages': 0, 'error': str(e)})

# 更新企业清单
rows = []
with open(COMPANY_LIST, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    fieldnames = reader.fieldnames
    for row in reader:
        for r in results:
            if row['stock_code'] == r['code']:
                row['parse_status'] = r['status']
        rows.append(row)

with open(COMPANY_LIST, 'w', encoding='utf-8', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print("✓ 企业清单已更新")

# 更新日志
log_exists = LOG_FILE.exists()
with open(LOG_FILE, 'a', encoding='utf-8', newline='') as f:
    writer = csv.writer(f)
    if not log_exists:
        writer.writerow(['company_name', 'stock_code', 'file_name', 'parser', 'parse_time', 'page_count', 'markdown_path', 'status', 'error_message'])
    
    for company in companies:
        for r in results:
            if company['stock_code'] == r['code']:
                writer.writerow([
                    company['company_name'],
                    r['code'],
                    f"{r['code']}_IPO招股说明书.pdf",
                    'MinerU (pypdfium2) - 完整解析',
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    r['pages'],
                    f"outputs/week1_candidate_texts/{r['code']}_{company['company_name'].split('股份')[0]}_完整解析.md",
                    r['status'],
                    r['error']
                ])

print("✓ 解析日志已更新")
print(f"\n完成！成功: {sum(1 for r in results if r['status']=='success')}/{len(results)}")
