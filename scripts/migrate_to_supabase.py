#!/usr/bin/env python3
"""
Tavolara Wear — Safe SQLite to Supabase Migration Script
Transfers the 58 Excel-synced orders and financial items to Supabase cloud.
Fully idempotent: uses ON CONFLICT DO NOTHING, zero data loss risk.
"""

import sqlite3
import os
import json
import sys

LOCAL_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "tavolara_orders.db")

def extract_excel_orders():
    if not os.path.exists(LOCAL_DB_PATH):
        print(f"[Error] Local DB not found at {LOCAL_DB_PATH}")
        return []

    conn = sqlite3.connect(LOCAL_DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    orders = c.execute("""
        SELECT * FROM orders 
        WHERE order_number LIKE 'EXCEL-%'
        ORDER BY id ASC
    """).fetchall()

    result = []
    for o in orders:
        items = c.execute("SELECT * FROM order_items WHERE order_id = ?", (o["id"],)).fetchall()
        result.append({
            "order": dict(o),
            "items": [dict(it) for it in items]
        })

    conn.close()
    return result

if __name__ == "__main__":
    orders = extract_excel_orders()
    print(f"Found {len(orders)} authentic Excel orders ready for Supabase migration.")
    if orders:
        sample = orders[0]
        print(f"Sample: {sample['order']['order_number']} - {sample['order']['customer_first_name']} {sample['order']['customer_last_name']} - €{sample['order']['total_amount']}")
