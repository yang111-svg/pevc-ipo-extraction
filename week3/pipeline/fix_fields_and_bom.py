"""Fix field naming (source_page→pdf_page) in auto_jsonl and BOM in CSV files."""
import json, os, glob, csv

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 1. Fix auto_jsonl: rename source_page -> pdf_page
auto_dir = os.path.join(base, 'outputs', 'auto_jsonl')
for fpath in sorted(glob.glob(os.path.join(auto_dir, '*.jsonl'))):
    records = []
    with open(fpath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if 'source_page' in rec:
                rec['pdf_page'] = rec.pop('source_page')
            records.append(rec)
    with open(fpath, 'w', encoding='utf-8') as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + '\n')
    print(f'Fixed: {os.path.basename(fpath)} ({len(records)} records)')

# 2. Fix BOM in CSV files
csv_files = [
    os.path.join(base, 'outputs', 'logs', 'schema_validation_log.csv'),
    os.path.join(base, 'outputs', 'logs', 'cross_check_summary.csv'),
    os.path.join(base, 'evaluation', 'event_summary.csv'),
    os.path.join(base, 'evaluation', 'row_match.csv'),
    os.path.join(base, 'data', 'pdf_manifest.csv'),
]

for csv_path in csv_files:
    if not os.path.exists(csv_path):
        print(f'Skipped (not found): {csv_path}')
        continue
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        content = f.read()
    with open(csv_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'Fixed BOM: {os.path.relpath(csv_path, base)}')

print('\nDone.')
