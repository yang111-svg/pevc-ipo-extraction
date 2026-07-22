# -*- coding: utf-8 -*-
"""
import_to_postgres.py — 一键导入Gold数据到PostgreSQL数据库

数据库信息:
  主机: 175.27.211.229
  端口: 5433
  数据库: student
  用户: student2026
  密码: student2026
  表格前缀: ymx_ (杨苗鑫首字母)

用法:
  python import_to_postgres.py
  python import_to_postgres.py --check-only   # 仅检查连接，不导入
"""

import json
import os
import sys
from pathlib import Path

DB_CONFIG = {
    "host": "175.27.211.229",
    "port": 5433,
    "database": "student",
    "user": "student2026",
    "password": "student2026",
}

PREFIX = "ymx"  # 杨苗鑫首字母

CREATE_TABLES_SQL = f"""
-- ============================================
-- 杨苗鑫 (ymx) — PEVC IPO招股书股本变化数据
-- ============================================

-- 表1: 认缴/增资流水
CREATE TABLE IF NOT EXISTS {PREFIX}_subscription_flow (
    id SERIAL PRIMARY KEY,
    company_name VARCHAR(200) NOT NULL,
    stock_code VARCHAR(10) NOT NULL,
    event_type VARCHAR(50),
    event_date VARCHAR(20),
    event_order INTEGER,
    investor_name VARCHAR(200),
    investor_type VARCHAR(50),
    subscription_qty_wan DOUBLE PRECISION,
    subscription_qty_raw VARCHAR(100),
    subscription_amount_wan DOUBLE PRECISION,
    subscription_amount_raw VARCHAR(100),
    subscription_price DOUBLE PRECISION,
    subscription_price_raw VARCHAR(100),
    registered_capital_before DOUBLE PRECISION,
    registered_capital_after DOUBLE PRECISION,
    unit_issue_flag BOOLEAN,
    unit_issue_note TEXT,
    currency VARCHAR(10) DEFAULT 'CNY',
    pdf_page INTEGER,
    evidence_text TEXT,
    extraction_method VARCHAR(50),
    extraction_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 表2: 股权转让流水
CREATE TABLE IF NOT EXISTS {PREFIX}_share_transfer_flow (
    id SERIAL PRIMARY KEY,
    company_name VARCHAR(200) NOT NULL,
    stock_code VARCHAR(10) NOT NULL,
    event_date VARCHAR(20),
    event_order INTEGER,
    event_type VARCHAR(50),
    transferor_name VARCHAR(200),
    transferee_name VARCHAR(200),
    participant_type VARCHAR(50),
    transfer_qty_wan DOUBLE PRECISION,
    transfer_qty_raw VARCHAR(100),
    transfer_amount_wan DOUBLE PRECISION,
    transfer_amount_raw VARCHAR(100),
    transfer_price DOUBLE PRECISION,
    shareholding_before_pct DOUBLE PRECISION,
    shareholding_after_pct DOUBLE PRECISION,
    unit_issue_flag BOOLEAN,
    unit_issue_note TEXT,
    currency VARCHAR(10),
    pdf_page INTEGER,
    evidence_text TEXT,
    extraction_method VARCHAR(50),
    extraction_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 表3: 股权结构快照
CREATE TABLE IF NOT EXISTS {PREFIX}_equity_snapshot (
    id SERIAL PRIMARY KEY,
    company_name VARCHAR(200) NOT NULL,
    stock_code VARCHAR(10) NOT NULL,
    snapshot_label VARCHAR(50),
    snapshot_date VARCHAR(20),
    trigger_event TEXT,
    trigger_event_order INTEGER,
    total_shares_wan DOUBLE PRECISION,
    registered_capital_wan DOUBLE PRECISION,
    shareholder_name VARCHAR(200),
    shares_wan DOUBLE PRECISION,
    shares_raw VARCHAR(100),
    shareholding_pct DOUBLE PRECISION,
    shareholder_type VARCHAR(50),
    shareholder_category VARCHAR(50),
    capital_unit_note TEXT,
    pdf_page INTEGER,
    evidence_text TEXT,
    extraction_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 表4: Cross-check 校验
CREATE TABLE IF NOT EXISTS {PREFIX}_cross_check (
    id SERIAL PRIMARY KEY,
    company_name VARCHAR(200) NOT NULL,
    stock_code VARCHAR(10) NOT NULL,
    check_point TEXT,
    prev_snapshot_label VARCHAR(50),
    current_snapshot_label VARCHAR(50),
    prev_total_capital_wan DOUBLE PRECISION,
    flow_event_type VARCHAR(50),
    is_transfer BOOLEAN,
    flow_qty_change_wan DOUBLE PRECISION,
    flow_amount_wan DOUBLE PRECISION,
    flow_price DOUBLE PRECISION,
    expected_next_capital_wan DOUBLE PRECISION,
    pdf_disclosed_capital_wan DOUBLE PRECISION,
    difference_wan DOUBLE PRECISION,
    diff_pct DOUBLE PRECISION,
    check_result VARCHAR(30),
    per_shareholder_check TEXT,
    notes TEXT,
    evidence_pdf_page INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def load_gold(repo_dir):
    """加载 Gold 数据"""
    gold_dir = os.path.join(repo_dir, "week3", "manual_gold")
    data = {
        "subscription_flow": [],
        "share_transfer_flow": [],
        "equity_snapshot": [],
        "cross_check": [],
    }
    for fname in os.listdir(gold_dir):
        if not fname.endswith(".jsonl"):
            continue
        key = fname.replace("_gold.jsonl", "").replace(".jsonl", "")
        with open(os.path.join(gold_dir, fname), "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    data[key].append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return data


def import_data(conn, data):
    """将 Gold 数据导入数据库"""
    cur = conn.cursor()
    counts = {}

    # 1. subscription_flow
    for rec in data.get("subscription_flow", []):
        cur.execute(f"""
            INSERT INTO {PREFIX}_subscription_flow
            (company_name, stock_code, event_type, event_date, event_order,
             investor_name, investor_type,
             subscription_qty_wan, subscription_qty_raw,
             subscription_amount_wan, subscription_amount_raw,
             subscription_price, subscription_price_raw,
             registered_capital_before, registered_capital_after,
             unit_issue_flag, unit_issue_note, currency,
             pdf_page, evidence_text, extraction_method, extraction_notes)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            rec.get("company_name", ""),
            rec.get("stock_code", ""),
            rec.get("event_type"),
            rec.get("subscription_date") or rec.get("event_date"),
            rec.get("event_order"),
            rec.get("investor_name"),
            rec.get("investor_type"),
            rec.get("subscription_qty_wan"),
            rec.get("subscription_qty_raw"),
            rec.get("subscription_amount_wan"),
            rec.get("subscription_amount_raw"),
            rec.get("subscription_price"),
            rec.get("subscription_price_raw"),
            rec.get("registered_capital_before"),
            rec.get("registered_capital_after"),
            rec.get("unit_issue_flag"),
            rec.get("unit_issue_note"),
            rec.get("currency"),
            rec.get("pdf_page"),
            rec.get("evidence_text", "")[:2000],
            rec.get("extraction_method"),
            rec.get("extraction_notes"),
        ))
    counts["subscription_flow"] = len(data.get("subscription_flow", []))

    # 2. share_transfer_flow
    for rec in data.get("share_transfer_flow", []):
        cur.execute(f"""
            INSERT INTO {PREFIX}_share_transfer_flow
            (company_name, stock_code, event_date, event_order, event_type,
             transferor_name, transferee_name, participant_type,
             transfer_qty_wan, transfer_qty_raw,
             transfer_amount_wan, transfer_amount_raw,
             transfer_price, shareholding_before_pct, shareholding_after_pct,
             unit_issue_flag, unit_issue_note, currency,
             pdf_page, evidence_text, extraction_method, extraction_notes)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            rec.get("company_name", ""),
            rec.get("stock_code", ""),
            rec.get("transfer_date") or rec.get("event_date"),
            rec.get("event_order"),
            rec.get("event_type"),
            rec.get("transferor"),
            rec.get("transferee"),
            rec.get("transferor_type") or rec.get("transferee_type"),
            rec.get("transferred_registered_capital_wan") or rec.get("transferred_shares_wan"),
            rec.get("transfer_qty_raw"),
            rec.get("transfer_consideration_wan") or rec.get("transfer_amount_wan"),
            rec.get("transfer_amount_raw"),
            rec.get("transfer_price"),
            rec.get("shareholding_before_pct"),
            rec.get("shareholding_after_pct"),
            rec.get("unit_issue_flag"),
            rec.get("unit_issue_note"),
            rec.get("currency"),
            rec.get("pdf_page"),
            rec.get("evidence_text", "")[:2000],
            rec.get("extraction_method"),
            rec.get("extraction_notes"),
        ))
    counts["share_transfer_flow"] = len(data.get("share_transfer_flow", []))

    # 3. equity_snapshot
    for rec in data.get("equity_snapshot", []):
        shareholders = rec.get("shareholders", [])
        if not shareholders:
            cur.execute(f"""
                INSERT INTO {PREFIX}_equity_snapshot
                (company_name, stock_code, snapshot_label, snapshot_date,
                 trigger_event, trigger_event_order,
                 total_shares_wan, registered_capital_wan,
                 pdf_page, evidence_text, extraction_notes)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                rec.get("company_name"), rec.get("stock_code"),
                rec.get("snapshot_label"), rec.get("snapshot_date"),
                rec.get("trigger_event"), rec.get("trigger_event_order"),
                rec.get("total_shares"), rec.get("registered_capital"),
                rec.get("pdf_page"),
                rec.get("evidence_text", "")[:2000],
                rec.get("extraction_notes"),
            ))
        else:
            for sh in shareholders:
                cur.execute(f"""
                    INSERT INTO {PREFIX}_equity_snapshot
                    (company_name, stock_code, snapshot_label, snapshot_date,
                     trigger_event, trigger_event_order,
                     total_shares_wan, registered_capital_wan,
                     shareholder_name, shares_wan, shares_raw,
                     shareholding_pct, shareholder_type, shareholder_category,
                     pdf_page, evidence_text, extraction_notes)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, (
                    rec.get("company_name"), rec.get("stock_code"),
                    rec.get("snapshot_label"), rec.get("snapshot_date"),
                    rec.get("trigger_event"), rec.get("trigger_event_order"),
                    rec.get("total_shares"), rec.get("registered_capital"),
                    sh.get("shareholder_name"),
                    sh.get("shares"),
                    sh.get("shares_raw"),
                    sh.get("shareholding_pct"),
                    sh.get("shareholder_type"),
                    sh.get("shareholder_category"),
                    rec.get("pdf_page"),
                    rec.get("evidence_text", "")[:2000],
                    rec.get("extraction_notes"),
                ))
    counts["equity_snapshot"] = len(data.get("equity_snapshot", []))

    # 4. cross_check
    for rec in data.get("cross_check", []):
        cur.execute(f"""
            INSERT INTO {PREFIX}_cross_check
            (company_name, stock_code, check_point,
             prev_snapshot_label, current_snapshot_label,
             prev_total_capital_wan, flow_event_type, is_transfer,
             flow_qty_change_wan, flow_amount_wan, flow_price,
             expected_next_capital_wan, pdf_disclosed_capital_wan,
             difference_wan, diff_pct, check_result,
             per_shareholder_check, notes, evidence_pdf_page)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            rec.get("company_name"), rec.get("stock_code"),
            rec.get("cross_check_id") or rec.get("check_point"),
            rec.get("prev_snapshot_label"), rec.get("next_snapshot_label"),
            rec.get("prev_total_wan"),
            rec.get("event_type"),
            "转让" in str(rec.get("check_type", "")),
            rec.get("subscription_qty_wan_sum") or rec.get("transfer_qty_wan_sum"),
            rec.get("subscription_amount_wan_sum") or rec.get("transfer_amount_wan_sum"),
            rec.get("price"),
            rec.get("expected_next_total_wan"),
            rec.get("pdf_next_total_wan"),
            rec.get("diff_wan"),
            rec.get("diff_pct"),
            rec.get("check_status"),
            rec.get("per_shareholder_check", "")[:1000],
            rec.get("notes", "")[:1000],
            rec.get("evidence_pdf_page") or rec.get("pdf_page"),
        ))
    counts["cross_check"] = len(data.get("cross_check", []))

    conn.commit()
    cur.close()
    return counts


def main():
    try:
        import psycopg2
    except ImportError:
        print("正在安装 psycopg2...")
        import subprocess
        subprocess.run([sys.executable, "-m", "pip", "install", "psycopg2-binary"], check=True)
        import psycopg2
        print("安装完成")

    repo_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    check_only = "--check-only" in sys.argv

    print(f"连接数据库: {DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}")

    try:
        conn = psycopg2.connect(**DB_CONFIG)
        print("[OK] 数据库连接成功!")
    except Exception as e:
        print(f"[FAIL] 连接失败: {e}")
        print("\n请检查:")
        print("  1. 是否连接了学校VPN?")
        print("  2. 主机地址: 175.27.211.229")
        print("  3. 端口: 5433")
        return

    cur = conn.cursor()

    # 创建表
    print("\n创建表...")
    cur.execute(CREATE_TABLES_SQL)
    conn.commit()
    print("[OK] 4张表创建成功")

    # 检查现有数据
    cur.execute(f"SELECT COUNT(*) FROM {PREFIX}_subscription_flow")
    print(f"  当前已有 {cur.fetchone()[0]} 条记录")

    if check_only:
        print("\n--check-only 模式，跳过数据导入")
        cur.close()
        conn.close()
        return

    # 导入数据
    print("\n加载Gold数据...")
    data = load_gold(repo_dir)

    print("\n导入数据...")
    counts = import_data(conn, data)

    print("\n[OK] 导入完成!")
    print(f"  subscription_flow: {counts.get('subscription_flow', 0)} 条")
    print(f"  share_transfer_flow: {counts.get('share_transfer_flow', 0)} 条")
    print(f"  equity_snapshot: {counts.get('equity_snapshot', 0)} 条（含股东明细）")
    print(f"  cross_check: {counts.get('cross_check', 0)} 条")
    print(f"  合计: {sum(counts.values())} 条记录")

    # 验证
    print("\n验证导入:")
    cur.execute(f"""
        SELECT tablename, n_live_tup
        FROM pg_stat_user_tables
        WHERE tablename LIKE '{PREFIX}_%'
        ORDER BY tablename
    """)
    for row in cur.fetchall():
        print(f"  {row[0]}: {row[1]} 行")

    cur.close()
    conn.close()
    print("\n 所有操作完成!")


if __name__ == "__main__":
    main()
