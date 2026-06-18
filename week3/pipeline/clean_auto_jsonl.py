"""Clean auto_jsonl: remove noise records with no meaningful data."""
import json, os, glob

auto_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'outputs', 'auto_jsonl')
files = sorted(glob.glob(os.path.join(auto_dir, '*.jsonl')))
total_before, total_after = 0, 0

for fpath in files:
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
            inv = rec.get('investor_name', '')
            amt = rec.get('subscription_amount', '')
            shares = rec.get('subscription_shares', '')
            date = rec.get('date', '')
            # Keep if: has investor_name OR has both amount+shares OR has date with amount/shares
            inv_ok = bool(inv) and inv.strip() != ''
            amt_ok = bool(amt) and str(amt).strip() != ''
            shares_ok = bool(shares) and str(shares).strip() != ''
            date_ok = bool(date) and str(date).strip() != ''

            has_data = inv_ok or (amt_ok and shares_ok) or (date_ok and (amt_ok or shares_ok))
            if has_data:
                records.append(rec)

    before = sum(1 for _ in open(fpath, 'r', encoding='utf-8'))
    total_before += before
    total_after += len(records)

    with open(fpath, 'w', encoding='utf-8') as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + '\n')

    name = os.path.basename(fpath)
    print(f'{name}: {before} -> {len(records)} records (removed {before - len(records)} noise)')

print(f'\nTotal: {total_before} -> {total_after} records ({total_before - total_after} noise removed)')
