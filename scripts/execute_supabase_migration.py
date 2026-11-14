#!/usr/bin/env python3
"""
Tavolara Wear — Production Migration Script to Supabase
Safely migrates:
1. The 58 authentic orders from Excel
2. The 58 order items
3. The production expense (€696.00)
Into the dedicated Tavolara Wear Supabase database (ofaycxhwnkxuckvxuieq).
"""

import sqlite3
import os
import json

LOCAL_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "tavolara_orders.db")

def escape_sql_str(val):
    if val is None:
        return "NULL"
    s = str(val).replace("'", "''")
    return f"'{s}'"

def generate_migration_sql():
    conn = sqlite3.connect(LOCAL_DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    orders = c.execute("""
        SELECT * FROM orders 
        WHERE order_number LIKE 'EXCEL-%'
        ORDER BY id ASC
    """).fetchall()

    expenses = c.execute("SELECT * FROM expenses").fetchall()

    sql_statements = []
    sql_statements.append("BEGIN;")

    # Remove temporary test order if present
    sql_statements.append("DELETE FROM order_items WHERE order_id IN (SELECT id FROM orders WHERE order_number = 'TW-2026-TEST01');")
    sql_statements.append("DELETE FROM orders WHERE order_number = 'TW-2026-TEST01';")
    sql_statements.append("DELETE FROM expenses WHERE description LIKE '%Test%' OR notes LIKE '%Test%';")

    for o in orders:
        items = c.execute("SELECT * FROM order_items WHERE order_id = ?", (o["id"],)).fetchall()
        
        # Delivery method mapping
        delivery_method = 'hand'
        
        # Payment status mapping
        payment_status = 'da_pagare'
        status = 'Ordine da pagare'

        ord_num = escape_sql_str(o["order_number"])
        ord_token = escape_sql_str(o["order_token"])
        fn = escape_sql_str(o["customer_first_name"])
        ln = escape_sql_str(o["customer_last_name"])
        email = escape_sql_str(o["customer_email"])
        phone = escape_sql_str(o["customer_phone"] or "")
        shirt_price = float(o["shirt_price"] or 25.0)
        shipping_cost = float(o["shipping_cost"] or 0.0)
        total_amount = float(o["total_amount"] or 25.0)
        payment_method = escape_sql_str(o["payment_method"] or "Bonifico bancario")
        wire_causale = escape_sql_str(o["wire_causale"] or f"TAVOLARA WEAR - {o['customer_first_name']} {o['customer_last_name']}")
        created_at = escape_sql_str(o["created_at"] or "2026-11-14 10:00:00+00")

        # Insert order with ON CONFLICT (order_number) DO UPDATE
        insert_order = f"""
        INSERT INTO orders (
            order_number, order_token, customer_first_name, customer_last_name,
            customer_email, customer_phone, delivery_method, shirt_price,
            shipping_cost, discount_amount, total_amount, payment_method,
            wire_causale, status, payment_status, privacy_accepted,
            privacy_timestamp, created_at, updated_at
        ) VALUES (
            {ord_num}, {ord_token}, {fn}, {ln},
            {email}, {phone}, '{delivery_method}', {shirt_price},
            {shipping_cost}, 0.00, {total_amount}, {payment_method},
            {wire_causale}, '{status}', '{payment_status}', TRUE,
            {created_at}::timestamptz, {created_at}::timestamptz, {created_at}::timestamptz
        )
        ON CONFLICT (order_number) DO UPDATE SET
            customer_first_name = EXCLUDED.customer_first_name,
            customer_last_name = EXCLUDED.customer_last_name,
            total_amount = EXCLUDED.total_amount
        RETURNING id;
        """
        sql_statements.append(f"""
        DO $$
        DECLARE
            v_order_id bigint;
        BEGIN
            INSERT INTO orders (
                order_number, order_token, customer_first_name, customer_last_name,
                customer_email, customer_phone, delivery_method, shirt_price,
                shipping_cost, discount_amount, total_amount, payment_method,
                wire_causale, status, payment_status, privacy_accepted,
                privacy_timestamp, created_at, updated_at
            ) VALUES (
                {ord_num}, {ord_token}, {fn}, {ln},
                {email}, {phone}, '{delivery_method}', {shirt_price},
                {shipping_cost}, 0.00, {total_amount}, {payment_method},
                {wire_causale}, '{status}', '{payment_status}', TRUE,
                {created_at}::timestamptz, {created_at}::timestamptz, {created_at}::timestamptz
            )
            ON CONFLICT (order_number) DO UPDATE SET
                total_amount = EXCLUDED.total_amount
            RETURNING id INTO v_order_id;
        """)

        for it in items:
            pname = escape_sql_str(it["product_name"] or "T-shirt Tavolara Wear")
            raw_color = (it["color"] or "").lower()
            if "navy" in raw_color or "blu" in raw_color:
                color = "Blu"
                color_code = "navy"
            else:
                color = "Bianca"
                color_code = "white"
            size = str(it["size"] or "M").upper()
            if size not in ["S", "M", "L", "XL", "XXL", "3XL"]:
                size = "M"
            qty = int(it["quantity"] or 1)
            uprice = float(it["unit_price"] or 25.0)
            tprice = float(it["total_price"] or uprice * qty)

            sql_statements.append(f"""
            DELETE FROM order_items WHERE order_id = v_order_id;
            INSERT INTO order_items (
                order_id, product_name, color, color_code, size,
                quantity, unit_price, total_price, created_at
            ) VALUES (
                v_order_id, {pname}, '{color}', '{color_code}', '{size}',
                {qty}, {uprice}, {tprice}, {created_at}::timestamptz
            );
            """)

        sql_statements.append("END $$;")

    # Sync expenses
    for ex in expenses:
        cat = escape_sql_str(ex["category"] or "magliette")
        desc = escape_sql_str(ex["description"] or "Produzione stock 58 T-shirt")
        amt = float(ex["amount"] or 696.0)
        ex_date = escape_sql_str(ex["date"] or "2026-11-14")
        supplier = escape_sql_str(ex["supplier"] or "Manifattura Tessile Tavolara")
        qty = int(ex["quantity"] or 58)
        ucost = float(ex["unit_cost"] or 12.0)
        notes = escape_sql_str(ex["notes"] or "")

        sql_statements.append(f"""
        INSERT INTO expenses (
            category_code, description, amount, date, supplier,
            quantity, unit_cost, notes, created_at, updated_at
        )
        SELECT {cat}, {desc}, {amt}, {ex_date}::date, {supplier},
               {qty}, {ucost}, {notes}, NOW(), NOW()
        WHERE NOT EXISTS (
            SELECT 1 FROM expenses WHERE description = {desc} AND amount = {amt}
        );
        """)

    sql_statements.append("COMMIT;")
    conn.close()
    return "\n".join(sql_statements)

if __name__ == "__main__":
    sql = generate_migration_sql()
    with open("scripts/supabase_migration_payload.sql", "w", encoding="utf-8") as f:
        f.write(sql)
    print("Migration SQL generated successfully. Lines:", len(sql.splitlines()))
