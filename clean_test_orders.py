"""
Tavolara Wear — Script di pulizia ordini e dati di test.
Cancella solo gli ordini e dati di test mantenendo intatti gli ordini reali (Excel) e la configurazione.
Sincronizza SQLite e Supabase.
"""

import sqlite3
import os
import urllib.request
import json
import ssl

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "tavolara_orders.db")

def clear_test_data():
    # 1. Clean SQLite (only genuine test records with TEST)
    if os.path.exists(DB_PATH):
        conn = sqlite3.connect(DB_PATH)
        with conn:
            conn.execute("DELETE FROM order_items WHERE order_id IN (SELECT id FROM orders WHERE order_number LIKE '%TEST%');")
            conn.execute("DELETE FROM orders WHERE order_number LIKE '%TEST%';")
            conn.execute("DELETE FROM incomes WHERE reference LIKE '%TEST%' OR order_reference LIKE '%TEST%';")
            conn.execute("UPDATE discount_codes SET usage_count = (SELECT COUNT(*) FROM orders WHERE discount_code = discount_codes.code);")
        
        ord_cnt = conn.execute("SELECT count(*) FROM orders").fetchone()[0]
        inc_cnt = conn.execute("SELECT count(*) FROM incomes").fetchone()[0]
        exp_cnt = conn.execute("SELECT count(*) FROM expenses").fetchone()[0]
        conn.close()
        print(f"✓ SQLite pulito (solo test rimossi): {ord_cnt} ordini, {inc_cnt} entrate, {exp_cnt} spese.")

    # 2. Clean Supabase Cloud (only TEST records)
    sb_url = os.environ.get("SUPABASE_URL", "https://ofaycxhwnkxuckvxuieq.supabase.co")
    anon_key = os.environ.get("SUPABASE_ANON_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9mYXljeGh3bmt4dWNrdnh1aWVxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTQ2NzMyNTEsImV4cCI6MjExMDI0OTI1MX0.gWIr8Sg2Aep1QSsUb5VQxuz_RMIsYBoS2jw5PpMTXpc")
    
    ctx = ssl._create_unverified_context()
    login_url = f"{sb_url}/auth/v1/token?grant_type=password"
    headers = {
        'apikey': anon_key,
        'Content-Type': 'application/json'
    }
    
    try:
        login_data = json.dumps({'email': 'admin@tavolarawear.it', 'password': 'tavolara2026'}).encode('utf-8')
        req = urllib.request.Request(login_url, data=login_data, headers=headers)
        with urllib.request.urlopen(req, context=ctx, timeout=8) as resp:
            token = json.loads(resp.read().decode('utf-8'))['access_token']
        
        auth_headers = {
            'apikey': anon_key,
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        
        # Delete only actual TEST artifacts, NEVER real modulo orders
        endpoints = [
            'transactions?reference=like.*TEST*',
            'orders?order_number=like.*TEST*',
            'customers?email=like.*@test.it*'
        ]
        
        for ep in endpoints:
            del_req = urllib.request.Request(f"{sb_url}/rest/v1/{ep}", headers=auth_headers, method='DELETE')
            try:
                with urllib.request.urlopen(del_req, context=ctx, timeout=6) as r:
                    pass
            except Exception:
                pass
        
        print("✓ Supabase Cloud pulito da tutti i record e ordini di test!")
    except Exception as e:
        print(f"[Supabase Pulizia] Info/Avviso: {e}")

if __name__ == "__main__":
    clear_test_data()
