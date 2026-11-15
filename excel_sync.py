"""
Tavolara Wear — Live Excel Synchronization Engine
Continuously links and synchronizes the brand's Excel order spreadsheet
(tavolr ordini novembredicembre2026.xlsx) with SQLite and the Web Gestionale.
"""

import os
import openpyxl
import sqlite3
import json
import ssl
import urllib.request
from datetime import datetime, timezone
from database import get_db

def read_supabase_env():
    """Safely reads Supabase credentials from local .env."""
    env_file = os.path.join(os.path.dirname(__file__), ".env")
    cfg = {
        "supabase_url": "",
        "supabase_anon_key": "",
        "supabase_admin_email": "admin@tavolarawear.it",
        "supabase_admin_password": "tavolara2026",
        "is_configured": False
    }
    if not os.path.isfile(env_file):
        return cfg
    try:
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    if k == "SUPABASE_URL":
                        cfg["supabase_url"] = v
                    elif k == "SUPABASE_ANON_KEY":
                        if "service_role" not in v.lower():
                            cfg["supabase_anon_key"] = v
                    elif k == "SUPABASE_ADMIN_EMAIL":
                        cfg["supabase_admin_email"] = v
                    elif k == "SUPABASE_ADMIN_PASSWORD":
                        cfg["supabase_admin_password"] = v
        cfg["is_configured"] = bool(cfg["supabase_url"] and cfg["supabase_anon_key"])
    except Exception as e:
        print("[Excel Sync] Errore lettura .env:", e)
    return cfg

def sync_excel_to_supabase(parsed_orders, total_turnover, total_costs, total_shirts, excel_path, mtime, filename):
    """
    Synchronizes parsed Excel orders, items, transactions (Attivo), and expenses (Passivo)
    into the cloud Supabase database for Tavolara Wear.
    """
    cfg = read_supabase_env()
    if not cfg["is_configured"]:
        return {"success": False, "message": "Supabase non configurato in .env"}

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    url_base = cfg["supabase_url"]
    anon_key = cfg["supabase_anon_key"]
    admin_email = cfg.get("supabase_admin_email", "admin@tavolarawear.it")
    admin_pwd = cfg.get("supabase_admin_password", "tavolara2026")

    # 1. Login to Supabase as admin
    auth_req = urllib.request.Request(
        f"{url_base}/auth/v1/token?grant_type=password",
        data=json.dumps({"email": admin_email, "password": admin_pwd}).encode("utf-8"),
        headers={"apikey": anon_key, "Content-Type": "application/json"}
    )
    with urllib.request.urlopen(auth_req, context=ctx) as r:
        auth_data = json.loads(r.read().decode())
    token = auth_data["access_token"]
    headers = {
        "apikey": anon_key,
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # 2. Get variants map
    v_req = urllib.request.Request(f"{url_base}/rest/v1/product_variants?select=id,color_code,size", headers=headers)
    with urllib.request.urlopen(v_req, context=ctx) as r:
        variants = json.loads(r.read().decode())
    variant_map = {(v["color_code"], v["size"]): v["id"] for v in variants}

    # 3. Clean up previous EXCEL- records
    get_old = urllib.request.Request(f"{url_base}/rest/v1/orders?order_number=like.EXCEL-*&select=id", headers=headers)
    with urllib.request.urlopen(get_old, context=ctx) as r:
        old_orders = json.loads(r.read().decode())
    old_ids = [str(o["id"]) for o in old_orders]

    if old_ids:
        ids_str = ",".join(old_ids)
        urllib.request.urlopen(urllib.request.Request(f"{url_base}/rest/v1/order_items?order_id=in.({ids_str})", headers=headers, method="DELETE"), context=ctx)
        urllib.request.urlopen(urllib.request.Request(f"{url_base}/rest/v1/transactions?order_id=in.({ids_str})", headers=headers, method="DELETE"), context=ctx)
        urllib.request.urlopen(urllib.request.Request(f"{url_base}/rest/v1/orders?id=in.({ids_str})", headers=headers, method="DELETE"), context=ctx)

    urllib.request.urlopen(urllib.request.Request(f"{url_base}/rest/v1/expenses?notes=like.*Excel-Sync*", headers=headers, method="DELETE"), context=ctx)

    now_iso = datetime.now(timezone.utc).isoformat()

    # 4. Prepare and insert orders batch
    orders_payload = []
    for o in parsed_orders:
        num = o["num"]
        order_num_str = f"EXCEL-{num:03d}"
        parts = o["cliente"].split(maxsplit=1)
        first_name = parts[0]
        last_name = parts[1] if len(parts) > 1 else ""
        clean_last = last_name.lower().replace(" ", "")
        email = f"{first_name.lower()}.{clean_last}@tavolarawear.it"
        status = "Ordine pagato" if o["is_pagato"] else "Ordine da pagare"
        payment_status = "pagato" if o["is_pagato"] else "da_pagare"
        delivery_method = "home" if o["indirizzo"] else "hand"

        orders_payload.append({
            "order_number": order_num_str,
            "order_token": order_num_str,
            "customer_first_name": first_name,
            "customer_last_name": last_name,
            "customer_email": email,
            "customer_phone": o["telefono"],
            "delivery_method": delivery_method,
            "delivery_address": o["indirizzo"],
            "delivery_zip": o["cap"],
            "delivery_city": o["citta"],
            "delivery_province": o["provincia"],
            "shirt_price": o["prezzo_unit"],
            "shipping_cost": o["sped_addeb"],
            "discount_amount": 0.0,
            "total_amount": o["incasso_prev"],
            "payment_method": "bonifico",
            "wire_causale": f"TAVOLARA WEAR - {o['cliente'].upper()} - {order_num_str}",
            "status": status,
            "payment_status": payment_status,
            "privacy_accepted": True,
            "privacy_timestamp": f"{o['date']}T10:00:00Z",
            "delivery_notes": f"[Excel-Sync] Utile riga: {o['utile']:.2f} €. {o['note']}".strip(),
            "created_at": f"{o['date']}T10:00:00Z",
            "updated_at": now_iso
        })

    post_ord = urllib.request.Request(
        f"{url_base}/rest/v1/orders",
        data=json.dumps(orders_payload).encode("utf-8"),
        headers={**headers, "Prefer": "return=representation"},
        method="POST"
    )
    with urllib.request.urlopen(post_ord, context=ctx) as r:
        created_orders = json.loads(r.read().decode())

    order_map = {o["order_number"]: o["id"] for o in created_orders}

    # 5. Prepare and insert order items & transactions (Attivo)
    items_payload = []
    tx_payload = []
    for o in parsed_orders:
        order_num_str = f"EXCEL-{o['num']:03d}"
        order_id = order_map.get(order_num_str)
        if not order_id:
            continue
        var_id = variant_map.get((o["color_code"], o["size_code"]))

        items_payload.append({
            "order_id": order_id,
            "product_id": 1,
            "variant_id": var_id,
            "product_name": "T-shirt Tavolara Wear",
            "color": "Bianca" if o["color_code"] == "white" else "Blu",
            "color_code": o["color_code"],
            "size": o["size_code"],
            "quantity": o["qty"],
            "unit_price": o["prezzo_unit"],
            "total_price": o["incasso_prev"],
            "created_at": f"{o['date']}T10:00:00Z"
        })

        tx_status = "Incassata" if o["is_pagato"] else "In attesa"
        tx_payload.append({
            "type": "incasso",
            "order_id": order_id,
            "description": f"Ordine #{o['num']} — {o['cliente']} ({o['color_label']} {o['size_code']})",
            "amount": o["incasso_prev"],
            "date": o["date"],
            "payment_method": "Bonifico bancario",
            "status": tx_status,
            "reference": order_num_str,
            "notes": f"[Excel-Sync] Utile riga: {o['utile']:.2f} €. {o['note']}".strip(),
            "created_at": f"{o['date']}T10:00:00Z",
            "updated_at": now_iso
        })

    if items_payload:
        post_items = urllib.request.Request(
            f"{url_base}/rest/v1/order_items",
            data=json.dumps(items_payload).encode("utf-8"),
            headers=headers,
            method="POST"
        )
        urllib.request.urlopen(post_items, context=ctx)

    if tx_payload:
        post_tx = urllib.request.Request(
            f"{url_base}/rest/v1/transactions",
            data=json.dumps(tx_payload).encode("utf-8"),
            headers=headers,
            method="POST"
        )
        urllib.request.urlopen(post_tx, context=ctx)

    # 6. Expenses (Passivo)
    tot_shirt_cost = sum(o["costo_magl"] for o in parsed_orders)
    exp_payload = []
    if tot_shirt_cost > 0:
        exp_payload.append({
            "category_code": "magliette",
            "description": f"Produzione stock {total_shirts} T-shirt Tavolara Wear",
            "amount": tot_shirt_cost,
            "date": parsed_orders[0]["date"],
            "quantity": total_shirts,
            "unit_cost": 12.00,
            "supplier": "Manifattura Tessile Tavolara",
            "notes": f"[Excel-Sync] Costo base magliette da foglio Excel (12 € × {total_shirts} capi)",
            "created_at": now_iso,
            "updated_at": now_iso
        })

    tot_ship_cost = sum(o["costo_sped"] for o in parsed_orders)
    if tot_ship_cost > 0:
        exp_payload.append({
            "category_code": "trasporto",
            "description": "Spese di spedizione ordini novembre-dicembre",
            "amount": tot_ship_cost,
            "date": parsed_orders[0]["date"],
            "carrier": "Corriere espresso",
            "shipment_count": len(parsed_orders),
            "shipment_type": "cumulativa",
            "notes": "[Excel-Sync] Costi spedizione aggregati dal foglio Excel",
            "created_at": now_iso,
            "updated_at": now_iso
        })

    tot_other_exp = sum(o["altre_spese"] for o in parsed_orders)
    if tot_other_exp > 0:
        exp_payload.append({
            "category_code": "prove",
            "description": "Altre spese operative e di sviluppo",
            "amount": tot_other_exp,
            "date": parsed_orders[0]["date"],
            "proof_type": "Spese varie",
            "notes": "[Excel-Sync] Altre spese dal foglio Excel",
            "created_at": now_iso,
            "updated_at": now_iso
        })

    if exp_payload:
        post_exp = urllib.request.Request(
            f"{url_base}/rest/v1/expenses",
            data=json.dumps(exp_payload).encode("utf-8"),
            headers=headers,
            method="POST"
        )
        urllib.request.urlopen(post_exp, context=ctx)

    # 7. Metadata in config
    tot_profit = round(total_turnover - total_costs, 2)
    half_profit = round(tot_profit / 2.0, 2)

    config_updates = [
        {"key": "excel_linked", "value": "1", "updated_at": now_iso},
        {"key": "excel_file_name", "value": filename, "updated_at": now_iso},
        {"key": "excel_last_mtime", "value": str(mtime), "updated_at": now_iso},
        {"key": "excel_last_synced", "value": now_iso, "updated_at": now_iso},
        {"key": "excel_rows_count", "value": str(len(parsed_orders)), "updated_at": now_iso},
        {"key": "excel_total_shirts", "value": str(total_shirts), "updated_at": now_iso},
        {"key": "excel_total_revenue", "value": f"{total_turnover:.2f}", "updated_at": now_iso},
        {"key": "excel_total_costs", "value": f"{total_costs:.2f}", "updated_at": now_iso},
        {"key": "excel_total_profit", "value": f"{tot_profit:.2f}", "updated_at": now_iso},
        {"key": "excel_partner_pala", "value": f"{half_profit:.2f}", "updated_at": now_iso},
        {"key": "excel_partner_bizz", "value": f"{half_profit:.2f}", "updated_at": now_iso}
    ]

    post_cfg = urllib.request.Request(
        f"{url_base}/rest/v1/config?on_conflict=key",
        data=json.dumps(config_updates).encode("utf-8"),
        headers={**headers, "Prefer": "resolution=merge-duplicates"},
        method="POST"
    )
    urllib.request.urlopen(post_cfg, context=ctx)

    print(f"[Excel Sync] Supabase sincronizzato con successo ({len(created_orders)} ordini)")
    return {
        "success": True,
        "orders_synced": len(created_orders),
        "expenses_synced": len(exp_payload)
    }

DEFAULT_EXCEL_PATH = os.path.join(os.path.dirname(__file__), "data", "tavolara_ordini_live.xlsx")
DOWNLOADS_PATH = os.path.expanduser("~/Downloads/tavolr ordini novembredicembre2026 2.xlsx")
FALLBACK_DOWNLOADS_PATH = os.path.expanduser("~/Downloads/tavolr ordini novembredicembre2026.xlsx")
ICLOUD_TAVOLARA_PATH = os.path.expanduser("~/Library/Mobile Documents/com~apple~CloudDocs/TAVOLARA/tavolr ordini novembredicembre2026.xlsx")

def get_live_excel_path():
    if os.environ.get("VERCEL"):
        tmp_excel = "/tmp/tavolara_ordini_live.xlsx"
        if not os.path.exists(tmp_excel) and os.path.exists(DEFAULT_EXCEL_PATH):
            try:
                import shutil
                shutil.copy2(DEFAULT_EXCEL_PATH, tmp_excel)
            except Exception:
                pass
        return tmp_excel
    return DEFAULT_EXCEL_PATH

def find_best_excel_file():
    """Finds the most recent Excel file between data folder, Downloads, iCloud, and Desktop."""
    candidates = [
        get_live_excel_path(),
        DEFAULT_EXCEL_PATH,
        DOWNLOADS_PATH,
        FALLBACK_DOWNLOADS_PATH,
        ICLOUD_TAVOLARA_PATH
    ]
    existing = [p for p in set(candidates) if os.path.exists(p)]
    if not existing:
        return None
    # Return the one with the latest modification time
    return max(existing, key=lambda p: os.path.getmtime(p))

def normalize_color(color_raw):
    if not color_raw:
        return "navy", "Blu navy"
    c = str(color_raw).strip().lower()
    if "bianc" in c or "white" in c:
        return "white", "Bianca"
    return "navy", "Blu navy"

def normalize_size(size_raw):
    if not size_raw:
        return "M"
    s = str(size_raw).strip().upper()
    if "XXL" in s or "2XL" in s:
        return "XXL"
    if "XXXL" in s or "3XL" in s:
        return "3XL"
    if "XL" in s:
        return "XL"
    if "L" in s:
        return "L"
    if "M" in s:
        return "M"
    if "S" in s:
        return "S"
    return "M"

def sync_excel_to_db(excel_path=None, force=False):
    """
    Parses the Excel file and synchronizes orders, incomes, and expenses into SQLite.
    Returns status summary with exact figures.
    """
    if not excel_path:
        excel_path = find_best_excel_file()

    if not excel_path or not os.path.exists(excel_path):
        return {
            "success": False,
            "message": "Nessun file Excel trovato da sincronizzare."
        }

    mtime = os.path.getmtime(excel_path)
    file_size = os.path.getsize(excel_path)
    filename = os.path.basename(excel_path)

    conn = get_db()
    
    # Check if already synced with same mtime unless force=True
    last_mtime_row = conn.execute("SELECT value FROM config WHERE key = 'excel_last_mtime'").fetchone()
    if not force and last_mtime_row and last_mtime_row["value"] == str(mtime):
        conn.close()
        return {
            "success": True,
            "already_synced": True,
            "message": f"Il file Excel '{filename}' è già sincronizzato e aggiornato.",
            "file": filename,
            "excel_path": excel_path
        }

    # Open workbook in read_only mode (instant read)
    try:
        wb = openpyxl.load_workbook(excel_path, read_only=True, data_only=True)
        sheet = None
        for sname in wb.sheetnames:
            if "ordin" in sname.lower():
                sheet = wb[sname]
                break
        if sheet is None:
            sheet = wb[wb.sheetnames[0]]
    except Exception as e:
        conn.close()
        return {
            "success": False,
            "message": f"Impossibile leggere il file Excel: {str(e)}"
        }

    # Auto-detect start row
    min_row_num = 10
    try:
        sample_rows = list(sheet.iter_rows(min_row=1, max_row=20, values_only=True))
        for r_idx, r in enumerate(sample_rows):
            r_str = " ".join([str(c).lower() for c in r if c is not None])
            if "cliente" in r_str or "n. ordine" in r_str or "taglia" in r_str:
                for next_idx in range(r_idx + 1, len(sample_rows)):
                    next_r = sample_rows[next_idx]
                    if len(next_r) > 2 and next_r[2] is not None and str(next_r[2]).strip() != "":
                        min_row_num = next_idx + 1
                        break
                break
    except Exception:
        min_row_num = 10

    # Read data rows from detected min_row_num up to 300
    parsed_orders = []
    consecutive_empty = 0

    for idx, r in enumerate(sheet.iter_rows(min_row=min_row_num, max_row=300, values_only=True)):
        cliente = r[2] if len(r) > 2 else None
        if cliente is not None and str(cliente).strip() != "":
            consecutive_empty = 0
            num = r[0] if len(r) > 0 and r[0] is not None else (len(parsed_orders) + 1)
            date_val = r[1] if len(r) > 1 and r[1] is not None else "2026-11-14"
            if isinstance(date_val, datetime):
                date_str = date_val.strftime("%Y-%m-%d")
            else:
                date_str = str(date_val)[:10] if date_val else "2026-11-14"

            cliente_clean = " ".join([w.capitalize() for w in str(cliente).strip().split()])
            telefono = str(r[3]).strip() if len(r) > 3 and r[3] is not None else ""
            colore_raw = r[4] if len(r) > 4 else None
            taglia_raw = r[5] if len(r) > 5 else None

            color_code, color_label = normalize_color(colore_raw)
            size_code = normalize_size(taglia_raw)

            qty = int(r[6]) if len(r) > 6 and r[6] is not None else 1
            if qty <= 0: qty = 1

            # Price and income
            incasso_prev = float(r[9]) if len(r) > 9 and r[9] is not None else 25.0
            prezzo_unit = float(r[7]) if len(r) > 7 and r[7] is not None else (incasso_prev / qty)
            sped_addeb = float(r[8]) if len(r) > 8 and r[8] is not None else 0.0

            # Costs
            costo_unit = float(r[10]) if len(r) > 10 and r[10] is not None else 12.0
            costo_magl = float(r[11]) if len(r) > 11 and r[11] is not None else (costo_unit * qty)
            costo_sped = float(r[12]) if len(r) > 12 and r[12] is not None else 0.0
            altre_spese = float(r[13]) if len(r) > 13 and r[13] is not None else 0.0
            utile = float(r[14]) if len(r) > 14 and r[14] is not None else (incasso_prev - costo_magl - costo_sped - altre_spese)

            pagato_raw = r[15] if len(r) > 15 and r[15] is not None else None
            is_pagato = str(pagato_raw).strip().lower() in ["si", "sì", "yes", "true", "1", "ok", "pagato"]

            indirizzo = str(r[16]).strip() if len(r) > 16 and r[16] is not None else ""
            cap = str(r[17]).strip() if len(r) > 17 and r[17] is not None else ""
            citta = str(r[18]).strip() if len(r) > 18 and r[18] is not None else ""
            provincia = str(r[19]).strip() if len(r) > 19 and r[19] is not None else ""
            note = str(r[24]).strip() if len(r) > 24 and r[24] is not None else ""

            parsed_orders.append({
                "num": num,
                "date": date_str,
                "cliente": cliente_clean,
                "telefono": telefono,
                "color_code": color_code,
                "color_label": color_label,
                "size_code": size_code,
                "qty": qty,
                "prezzo_unit": prezzo_unit,
                "sped_addeb": sped_addeb,
                "incasso_prev": incasso_prev,
                "costo_unit": costo_unit,
                "costo_magl": costo_magl,
                "costo_sped": costo_sped,
                "altre_spese": altre_spese,
                "utile": utile,
                "is_pagato": is_pagato,
                "indirizzo": indirizzo,
                "cap": cap,
                "citta": citta,
                "provincia": provincia,
                "note": note
            })
        else:
            consecutive_empty += 1
            if consecutive_empty >= 10:
                break

    wb.close()

    if not parsed_orders:
        conn.close()
        return {
            "success": False,
            "message": "Nessuna riga d'ordine valida trovata nel foglio 'Ordini'."
        }

    now_iso = datetime.now(timezone.utc).isoformat()

    # Synchronize into Database atomically
    with conn:
        # 1. Clear previous Excel-synced rows to prevent duplication
        conn.execute("DELETE FROM order_items WHERE order_id IN (SELECT id FROM orders WHERE order_token LIKE 'EXCEL-%')")
        conn.execute("DELETE FROM orders WHERE order_token LIKE 'EXCEL-%'")
        conn.execute("DELETE FROM incomes WHERE order_reference LIKE 'EXCEL-%'")
        conn.execute("DELETE FROM expenses WHERE notes LIKE '%[Excel-Sync]%'")

        total_turnover = 0.0
        total_costs = 0.0
        total_shirts = 0

        for o in parsed_orders:
            num = o["num"]
            order_num_str = f"EXCEL-{num:03d}"
            order_token_str = f"EXCEL-{num:03d}"

            # Split name
            parts = o["cliente"].split(maxsplit=1)
            first_name = parts[0]
            last_name = parts[1] if len(parts) > 1 else ""

            status = "Pagamento verificato" if o["is_pagato"] else "In attesa di pagamento"
            income_status = "Incassata" if o["is_pagato"] else "Confermata"

            # Insert into orders
            cur = conn.execute("""
                INSERT INTO orders (
                    order_number, order_token, customer_first_name, customer_last_name,
                    customer_email, customer_phone, delivery_method, delivery_address,
                    delivery_zip, delivery_city, delivery_province, shirt_price,
                    shipping_cost, total_amount, payment_method, wire_causale,
                    status, privacy_accepted, privacy_timestamp, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
            """, (
                order_num_str, order_token_str, first_name, last_name,
                f"{first_name.lower()}.{last_name.lower().replace(' ', '')}@tavolarawear.it",
                o["telefono"], "domicilio" if o["indirizzo"] else "a mano",
                o["indirizzo"], o["cap"], o["citta"], o["provincia"],
                o["prezzo_unit"], o["sped_addeb"], o["incasso_prev"],
                "Bonifico bancario", f"TAVOLARA WEAR - {o['cliente'].upper()} - {order_num_str}",
                status, now_iso, o["date"] + "T10:00:00", now_iso
            ))
            order_db_id = cur.lastrowid

            # Insert into order_items
            conn.execute("""
                INSERT INTO order_items (
                    order_id, product_name, color, color_name, size, quantity, unit_price, total_price
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                order_db_id, "T-shirt Tavolara Wear", o["color_code"], o["color_label"],
                o["size_code"], o["qty"], o["prezzo_unit"], o["incasso_prev"]
            ))

            # Insert into incomes (Attivo)
            inc_desc = f"Ordine #{num} — {o['cliente']} ({o['color_label']} {o['size_code']})"
            conn.execute("""
                INSERT INTO incomes (
                    description, amount, date, payment_method, order_reference,
                    order_id, status, notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                inc_desc, o["incasso_prev"], o["date"], "Bonifico bancario",
                order_num_str, order_db_id, income_status,
                f"[Excel-Sync] Utile riga: {o['utile']:.2f} €. {o['note']}".strip(),
                now_iso, now_iso
            ))

            total_turnover += o["incasso_prev"]
            total_shirts += o["qty"]

        # Aggregate Expenses from Excel:
        # A. Total Shirt Production Cost:
        tot_shirt_cost = sum(o["costo_magl"] for o in parsed_orders)
        if tot_shirt_cost > 0:
            conn.execute("""
                INSERT INTO expenses (
                    category, description, amount, date, quantity, unit_cost,
                    supplier, notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                "magliette", f"Produzione stock {total_shirts} T-shirt Tavolara Wear",
                tot_shirt_cost, parsed_orders[0]["date"], total_shirts, 12.00,
                "Manifattura Tessile Tavolara",
                f"[Excel-Sync] Costo base magliette da foglio Excel (12 € × {total_shirts} capi)",
                now_iso, now_iso
            ))
            total_costs += tot_shirt_cost

        # B. Shipping costs (if any):
        tot_ship_cost = sum(o["costo_sped"] for o in parsed_orders)
        if tot_ship_cost > 0:
            conn.execute("""
                INSERT INTO expenses (
                    category, description, amount, date, carrier, shipment_count,
                    shipment_type, notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                "trasporto", "Spese di spedizione ordini novembre-dicembre",
                tot_ship_cost, parsed_orders[0]["date"], "Corriere espresso",
                len(parsed_orders), "cumulativa",
                "[Excel-Sync] Costi spedizione aggregati dal foglio Excel",
                now_iso, now_iso
            ))
            total_costs += tot_ship_cost

        # C. Other expenses (if any):
        tot_other_exp = sum(o["altre_spese"] for o in parsed_orders)
        if tot_other_exp > 0:
            conn.execute("""
                INSERT INTO expenses (
                    category, description, amount, date, proof_type, notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                "prove", "Altre spese operative e di sviluppo",
                tot_other_exp, parsed_orders[0]["date"], "Spese varie",
                "[Excel-Sync] Altre spese dal foglio Excel",
                now_iso, now_iso
            ))
            total_costs += tot_other_exp

        # Save metadata in config table
        tot_profit = round(total_turnover - total_costs, 2)
        half_profit = round(tot_profit / 2.0, 2)

        config_updates = {
            "excel_linked": "1",
            "excel_file_path": excel_path,
            "excel_file_name": filename,
            "excel_last_mtime": str(mtime),
            "excel_last_synced": now_iso,
            "excel_rows_count": str(len(parsed_orders)),
            "excel_total_shirts": str(total_shirts),
            "excel_total_revenue": f"{total_turnover:.2f}",
            "excel_total_costs": f"{total_costs:.2f}",
            "excel_total_profit": f"{tot_profit:.2f}",
            "excel_partner_pala": f"{half_profit:.2f}",
            "excel_partner_bizz": f"{half_profit:.2f}"
        }
        for k, v in config_updates.items():
            conn.execute("""
                INSERT INTO config (key, value, updated_at) VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
            """, (k, v, now_iso))

    conn.close()

    # Synchronize to Supabase Cloud Database
    supabase_synced = False
    supabase_info = None
    try:
        sb_res = sync_excel_to_supabase(parsed_orders, total_turnover, total_costs, total_shirts, excel_path, mtime, filename)
        supabase_synced = sb_res.get("success", False)
        supabase_info = sb_res
    except Exception as sb_err:
        print("[Excel Sync] Supabase sync aviso:", sb_err)

    return {
        "success": True,
        "already_synced": False,
        "supabase_synced": supabase_synced,
        "message": f"Sincronizzazione completata con successo da '{filename}'!" + (" (Supabase Cloud aggiornato)" if supabase_synced else ""),
        "file": filename,
        "orders_synced": len(parsed_orders),
        "total_shirts": total_shirts,
        "total_revenue": total_turnover,
        "total_costs": total_costs,
        "total_profit": tot_profit,
        "pala_profit": half_profit,
        "bizz_profit": half_profit,
        "last_synced": now_iso
    }

def get_excel_sync_status():
    """Returns current live sync status and metadata."""
    conn = get_db()
    rows = conn.execute("SELECT key, value FROM config WHERE key LIKE 'excel_%'").fetchall()
    conn.close()
    cfg = {r["key"]: r["value"] for r in rows}

    active_file = find_best_excel_file()
    has_file = active_file is not None and os.path.exists(active_file)
    is_up_to_date = False

    if has_file and "excel_last_mtime" in cfg:
        curr_mtime = str(os.path.getmtime(active_file))
        is_up_to_date = (cfg["excel_last_mtime"] == curr_mtime)

    google_url = cfg.get("excel_google_drive_url", "")
    if not google_url:
        try:
            sb_cfg = read_supabase_env()
            if sb_cfg["is_configured"]:
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                sb_req = urllib.request.Request(
                    f"{sb_cfg['supabase_url']}/rest/v1/config?key=eq.excel_google_drive_url&select=value",
                    headers={"apikey": sb_cfg["supabase_anon_key"], "Authorization": f"Bearer {sb_cfg['supabase_anon_key']}"}
                )
                with urllib.request.urlopen(sb_req, context=ctx, timeout=3) as r:
                    sb_data = json.loads(r.read().decode())
                    if sb_data and len(sb_data) > 0:
                        google_url = sb_data[0].get("value", "")
        except Exception:
            pass

    return {
        "is_connected": bool(cfg.get("excel_linked") == "1"),
        "is_up_to_date": is_up_to_date,
        "file_name": cfg.get("excel_file_name", os.path.basename(active_file) if active_file else "Nessun file collegato"),
        "file_path": active_file or cfg.get("excel_file_path", ""),
        "last_synced": cfg.get("excel_last_synced", "Mai"),
        "orders_count": int(cfg.get("excel_rows_count", 0)),
        "total_shirts": int(cfg.get("excel_total_shirts", 0)),
        "total_revenue": float(cfg.get("excel_total_revenue", 0.0)),
        "total_costs": float(cfg.get("excel_total_costs", 0.0)),
        "total_profit": float(cfg.get("excel_total_profit", 0.0)),
        "google_drive_url": google_url,
        "pala_profit": float(cfg.get("excel_partner_pala", 0.0)),
        "bizz_profit": float(cfg.get("excel_partner_bizz", 0.0))
    }

def sync_google_drive_to_db(url):
    """
    Downloads spreadsheet from Google Drive / Google Sheets URL and syncs into DB.
    """
    import re
    match = re.search(r'(?:/d/|id=)([a-zA-Z0-9_-]+)', url)
    if not match:
        return {"success": False, "message": "Link Google Drive non valido. Incolla l'URL completo del foglio o file condiviso."}

    file_id = match.group(1)
    target_path = get_live_excel_path()

    urls_to_try = [
        f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=xlsx",
        f"https://drive.google.com/uc?export=download&id={file_id}"
    ]

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    last_err = None
    downloaded = False
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

    for u in urls_to_try:
        try:
            req = urllib.request.Request(u, headers=headers)
            with urllib.request.urlopen(req, context=ctx, timeout=20) as resp:
                content = resp.read()
                # Check for XLSX signature (ZIP archive starts with PK\x03\x04)
                if content.startswith(b"PK\x03\x04"):
                    with open(target_path, "wb") as f:
                        f.write(content)
                    downloaded = True
                    break
                elif b"<html" in content.lower():
                    last_err = "Assicurati che su Google Drive la condivisione sia impostata su 'Chiunque abbia il link' (visualizzatore)."
        except Exception as e:
            last_err = str(e)
            continue

    if not downloaded:
        msg = "Impossibile scaricare il file da Google Drive."
        if last_err:
            msg += f" {last_err}"
        return {"success": False, "message": msg}

    # Save to config
    conn = get_db()
    now_iso = datetime.now(timezone.utc).isoformat()
    conn.execute("""
        INSERT INTO config (key, value, updated_at) VALUES ('excel_google_drive_url', ?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
    """, (url, now_iso))
    conn.commit()
    conn.close()

    # Also persist to Supabase Cloud
    try:
        cfg = read_supabase_env()
        if cfg["is_configured"]:
            sb_url = f"{cfg['supabase_url']}/rest/v1/config?on_conflict=key"
            sb_headers = {
                "apikey": cfg["supabase_anon_key"],
                "Authorization": f"Bearer {cfg['supabase_anon_key']}",
                "Content-Type": "application/json",
                "Prefer": "resolution=merge-duplicates"
            }
            sb_payload = json.dumps([{"key": "excel_google_drive_url", "value": url, "updated_at": now_iso}]).encode("utf-8")
            sb_req = urllib.request.Request(sb_url, data=sb_payload, headers=sb_headers, method="POST")
            urllib.request.urlopen(sb_req, context=ctx)
    except Exception as e:
        print("[Excel Sync] Errore salvataggio google_drive_url su Supabase:", e)

    res = sync_excel_to_db(excel_path=target_path, force=True)
    res["google_drive_synced"] = True
    return res

def check_auto_sync():
    """
    Checks if the local Excel file has been modified on disk and triggers auto-sync.
    Can be called transparently on API requests or periodically.
    """
    active_file = find_best_excel_file()
    if not active_file or not os.path.exists(active_file):
        return False

    conn = get_db()
    row = conn.execute("SELECT value FROM config WHERE key = 'excel_last_mtime'").fetchone()
    conn.close()

    curr_mtime = str(os.path.getmtime(active_file))
    if not row or row["value"] != curr_mtime:
        # File modified on disk! Sync automatically
        res = sync_excel_to_db(excel_path=active_file, force=True)
        return res.get("success", False)
    return False

if __name__ == "__main__":
    res = sync_excel_to_db(force=True)
    print("Excel Sync Result:", res)
