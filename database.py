"""
Database management for Tavolara Wear Order System.
SQLite with WAL mode, parameterized queries, and ACID transactions.
"""

import sqlite3
import os
import json
import hashlib
import secrets
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "tavolara_orders.db")

def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn

def hash_password(password: str, salt: str = "tavolara_salt_2026") -> str:
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()

def init_db():
    conn = get_db()
    with conn:
        # Table: config
        conn.execute("""
            CREATE TABLE IF NOT EXISTS config (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TEXT
            );
        """)

        # Table: variants (Stock and availability)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS variants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product TEXT NOT NULL,
                color TEXT NOT NULL,
                color_name TEXT NOT NULL,
                size TEXT NOT NULL,
                is_available INTEGER NOT NULL DEFAULT 1,
                stock_qty INTEGER DEFAULT 50,
                updated_at TEXT NOT NULL
            );
        """)

        # Table: discount_codes
        conn.execute("""
            CREATE TABLE IF NOT EXISTS discount_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                discount_type TEXT NOT NULL DEFAULT 'fixed',
                discount_value REAL NOT NULL DEFAULT 5.0,
                is_active INTEGER NOT NULL DEFAULT 1,
                usage_count INTEGER NOT NULL DEFAULT 0,
                max_uses INTEGER,
                updated_at TEXT NOT NULL
            );
        """)

        # Table: orders
        conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_number TEXT UNIQUE NOT NULL,
                order_token TEXT UNIQUE NOT NULL,
                customer_first_name TEXT NOT NULL,
                customer_last_name TEXT NOT NULL,
                customer_email TEXT NOT NULL,
                customer_phone TEXT NOT NULL,
                delivery_method TEXT NOT NULL,
                locker_name TEXT,
                delivery_address TEXT,
                delivery_zip TEXT,
                delivery_city TEXT,
                delivery_province TEXT,
                delivery_notes TEXT,
                hand_location TEXT,
                hand_preferences TEXT,
                shirt_price REAL,
                shipping_cost REAL,
                discount_code TEXT,
                discount_amount REAL DEFAULT 0.0,
                total_amount REAL,
                payment_method TEXT NOT NULL DEFAULT 'bonifico',
                wire_causale TEXT NOT NULL,
                bank_holder TEXT,
                bank_iban TEXT,
                bank_name TEXT,
                status TEXT NOT NULL DEFAULT 'Nuovo ordine',
                privacy_accepted INTEGER NOT NULL DEFAULT 1,
                privacy_timestamp TEXT NOT NULL,
                client_ip TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)

        # Table: order_items
        conn.execute("""
            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
                product_name TEXT NOT NULL,
                color TEXT NOT NULL,
                color_name TEXT NOT NULL,
                size TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                unit_price REAL NOT NULL,
                total_price REAL NOT NULL
            );
        """)

        # Table: admin_sessions
        conn.execute("""
            CREATE TABLE IF NOT EXISTS admin_sessions (
                token TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL
            );
        """)

        # Seed initial config if not exists
        default_configs = {
            "shirt_price": "",          # Pending admin definition
            "shipping_locker": "",      # Pending admin definition
            "shipping_home": "",        # Pending admin definition
            "shipping_hand": "0.00",    # Hand delivery default
            "bank_holder": "",          # Pending bank details
            "bank_iban": "",            # Pending bank details
            "bank_name": "",            # Pending bank details
            "bank_notes": "Effettua il bonifico con l'importo esatto e indica la causale generata. L'ordine sarà preparato e spedito dopo la verifica dell'accredito.",
            "admin_password_hash": hash_password("tavolara2026"),
            "brand_phone": "+39 340 000 0000",
            "brand_email": "info@tavolarawear.it",
            "brand_instagram": "@tavolara.wear"
        }
        now_iso = datetime.now(timezone.utc).isoformat()
        for k, v in default_configs.items():
            conn.execute("""
                INSERT OR IGNORE INTO config (key, value, updated_at)
                VALUES (?, ?, ?)
            """, (k, v, now_iso))

        # Seed initial variants if empty
        row = conn.execute("SELECT COUNT(*) as count FROM variants").fetchone()
        if row["count"] == 0:
            variants = [
                ("T-shirt Tavolara Wear", "navy", "Blu navy", "S"),
                ("T-shirt Tavolara Wear", "navy", "Blu navy", "M"),
                ("T-shirt Tavolara Wear", "navy", "Blu navy", "L"),
                ("T-shirt Tavolara Wear", "navy", "Blu navy", "XL"),
                ("T-shirt Tavolara Wear", "navy", "Blu navy", "XXL"),
                ("T-shirt Tavolara Wear", "navy", "Blu navy", "XXXL"),
                ("T-shirt Tavolara Wear", "white", "Bianca", "S"),
                ("T-shirt Tavolara Wear", "white", "Bianca", "M"),
                ("T-shirt Tavolara Wear", "white", "Bianca", "L"),
                ("T-shirt Tavolara Wear", "white", "Bianca", "XL"),
                ("T-shirt Tavolara Wear", "white", "Bianca", "XXL"),
                ("T-shirt Tavolara Wear", "white", "Bianca", "XXXL"),
            ]
            for p, c, cn, s in variants:
                conn.execute("""
                    INSERT INTO variants (product, color, color_name, size, is_available, stock_qty, updated_at)
                    VALUES (?, ?, ?, ?, 1, 50, ?)
                """, (p, c, cn, s, now_iso))

        # Seed initial discount code: TAVOLARA5 (-5.00 €)
        conn.execute("""
            INSERT OR IGNORE INTO discount_codes (code, discount_type, discount_value, is_active, usage_count, max_uses, updated_at)
            VALUES ('TAVOLARA5', 'fixed', 5.0, 1, 0, NULL, ?)
        """, (now_iso,))

    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully at:", DB_PATH)
