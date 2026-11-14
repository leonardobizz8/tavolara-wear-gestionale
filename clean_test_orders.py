"""
Tavolara Wear — Script di pulizia ordini di test.
Cancella solo gli ordini di test mantenendo intatta la configurazione e le disponibilità.
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "tavolara_orders.db")

def clear_test_orders():
    conn = sqlite3.connect(DB_PATH)
    with conn:
        conn.execute("DELETE FROM order_items WHERE order_id IN (SELECT id FROM orders WHERE order_token NOT LIKE 'EXCEL-%');")
        conn.execute("DELETE FROM orders WHERE order_token NOT LIKE 'EXCEL-%';")
        conn.execute("UPDATE discount_codes SET usage_count = 0;")
    conn.close()
    print("✓ Tutti gli ordini di test sono stati rimossi. Gli ordini reali sincronizzati da Excel sono preservati!")

if __name__ == "__main__":
    clear_test_orders()
