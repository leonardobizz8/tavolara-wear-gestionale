"""
Tavolara Wear — Financial Management & Analytics Engine
Handles Incomes (Attivo), Expenses (Passivo with 4 categories),
Insights & Analytics (Size/Color Matrix, Commercial & Economic Metrics),
and CSV Exports.
"""

import sqlite3
import csv
import io
from datetime import datetime, timezone, timedelta
from database import get_db

VALID_EXPENSE_CATEGORIES = ["trasporto", "imballaggio", "prove", "magliette"]
VALID_INCOME_STATUSES = ["Confermata", "In attesa", "Incassata"]
SIZES_ORDER = ["S", "M", "L", "XL", "XXL", "3XL"]

def normalize_size(size_str: str) -> str:
    if not size_str:
        return "M"
    s = size_str.strip().upper()
    if s in ["XXXL", "3XL"]:
        return "3XL"
    return s

def parse_date_range(period, custom_start=None, custom_end=None):
    """
    Returns (start_str, end_str) in YYYY-MM-DD or (None, None) for 'all'.
    """
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")

    if period == "today":
        return today_str, today_str
    elif period == "week":
        start_date = (now - timedelta(days=6)).strftime("%Y-%m-%d")
        return start_date, today_str
    elif period == "month":
        start_date = now.strftime("%Y-%m-01")
        return start_date, today_str
    elif period == "quarter":
        q_month = ((now.month - 1) // 3) * 3 + 1
        start_date = f"{now.year}-{q_month:02d}-01"
        return start_date, today_str
    elif period == "year":
        start_date = f"{now.year}-01-01"
        return start_date, today_str
    elif period == "custom":
        s = (custom_start or "").strip()
        e = (custom_end or "").strip()
        return (s if s else None), (e if e else None)
    return None, None

def get_overview_data(period="all", start_date=None, end_date=None):
    """
    Computes all Overview KPIs and time-series for charts.
    """
    conn = get_db()
    s_date, e_date = parse_date_range(period, start_date, end_date)

    # Date filter fragments
    date_where_inc = " WHERE 1=1"
    inc_params = []
    if s_date:
        date_where_inc += " AND date >= ?"
        inc_params.append(s_date)
    if e_date:
        date_where_inc += " AND date <= ?"
        inc_params.append(e_date)

    date_where_exp = " WHERE 1=1"
    exp_params = []
    if s_date:
        date_where_exp += " AND date >= ?"
        exp_params.append(s_date)
    if e_date:
        date_where_exp += " AND date <= ?"
        exp_params.append(e_date)

    date_where_ord = " WHERE status != 'Annullato'"
    ord_params = []
    if s_date:
        date_where_ord += " AND created_at >= ?"
        ord_params.append(s_date + "T00:00:00")
    if e_date:
        date_where_ord += " AND created_at <= ?"
        ord_params.append(e_date + "T23:59:59")

    # Incomes totals
    inc_row = conn.execute(f"""
        SELECT 
            COALESCE(SUM(amount), 0.0) as total,
            COALESCE(SUM(CASE WHEN status = 'Incassata' THEN amount ELSE 0.0 END), 0.0) as collected,
            COALESCE(SUM(CASE WHEN status = 'Confermata' THEN amount ELSE 0.0 END), 0.0) as confirmed,
            COALESCE(SUM(CASE WHEN status = 'In attesa' THEN amount ELSE 0.0 END), 0.0) as pending,
            COUNT(*) as count
        FROM incomes
        {date_where_inc}
    """, inc_params).fetchone()

    total_incomes = float(inc_row["total"])
    incomes_collected = float(inc_row["collected"])
    incomes_confirmed = float(inc_row["confirmed"])
    incomes_pending = float(inc_row["pending"])
    incomes_count = int(inc_row["count"])

    # Expenses totals and breakdown
    exp_row = conn.execute(f"""
        SELECT 
            COALESCE(SUM(amount), 0.0) as total,
            COALESCE(SUM(CASE WHEN category = 'trasporto' THEN amount ELSE 0.0 END), 0.0) as trasporto,
            COALESCE(SUM(CASE WHEN category = 'imballaggio' THEN amount ELSE 0.0 END), 0.0) as imballaggio,
            COALESCE(SUM(CASE WHEN category = 'prove' THEN amount ELSE 0.0 END), 0.0) as prove,
            COALESCE(SUM(CASE WHEN category = 'magliette' THEN amount ELSE 0.0 END), 0.0) as magliette,
            COUNT(*) as count
        FROM expenses
        {date_where_exp}
    """, exp_params).fetchone()

    total_expenses = float(exp_row["total"])
    exp_trasporto = float(exp_row["trasporto"])
    exp_imballaggio = float(exp_row["imballaggio"])
    exp_prove = float(exp_row["prove"])
    exp_magliette = float(exp_row["magliette"])
    expenses_count = int(exp_row["count"])

    # Orders & Shirts sold
    ord_row = conn.execute(f"""
        SELECT 
            COUNT(DISTINCT orders.id) as order_count,
            COALESCE(SUM(orders.total_amount), 0.0) as order_turnover,
            COALESCE(SUM(order_items.quantity), 0) as shirts_sold
        FROM orders
        LEFT JOIN order_items ON order_items.order_id = orders.id
        {date_where_ord}
    """, ord_params).fetchone()

    total_orders_count = int(ord_row["order_count"])
    order_turnover = float(ord_row["order_turnover"])
    total_shirts_sold = int(ord_row["shirts_sold"])

    # Additional shirt purchase quantities from expenses
    shirt_purchase_row = conn.execute(f"""
        SELECT COALESCE(SUM(quantity), 0) as purchased_qty
        FROM expenses
        {date_where_exp} AND category = 'magliette'
    """, exp_params).fetchone()
    purchased_shirts_qty = int(shirt_purchase_row["purchased_qty"])

    # Mathematical KPI computations
    current_balance = round(total_incomes - total_expenses, 2)
    
    # Utile lordo (Gross Profit): Incomes - direct production costs (magliette + prove)
    direct_production_cost = exp_magliette + exp_prove
    gross_profit = round(total_incomes - direct_production_cost, 2) if total_incomes > 0 else round(-total_expenses, 2)
    gross_profit_margin = round((gross_profit / total_incomes * 100), 1) if total_incomes > 0 else 0.0

    # Costo medio per maglietta:
    if purchased_shirts_qty > 0:
        avg_shirt_cost = round(exp_magliette / purchased_shirts_qty, 2)
    elif total_shirts_sold > 0 and exp_magliette > 0:
        avg_shirt_cost = round(exp_magliette / total_shirts_sold, 2)
    else:
        avg_shirt_cost = 0.0

    # Ricavo medio per ordine:
    avg_order_revenue = round(order_turnover / total_orders_count, 2) if total_orders_count > 0 else 0.0

    # -----------------------------
    # Time Series For Charts
    # -----------------------------
    # 1. Incomes by date
    inc_by_date = {}
    rows = conn.execute(f"""
        SELECT date, SUM(amount) as sum_amt
        FROM incomes
        {date_where_inc}
        GROUP BY date ORDER BY date ASC
    """, inc_params).fetchall()
    for r in rows:
        inc_by_date[r["date"]] = float(r["sum_amt"])

    # 2. Expenses by date
    exp_by_date = {}
    rows = conn.execute(f"""
        SELECT date, SUM(amount) as sum_amt
        FROM expenses
        {date_where_exp}
        GROUP BY date ORDER BY date ASC
    """, exp_params).fetchall()
    for r in rows:
        exp_by_date[r["date"]] = float(r["sum_amt"])

    # 3. Orders / Shirts sold by date
    sales_by_date = {}
    rows = conn.execute(f"""
        SELECT substr(orders.created_at, 1, 10) as dt,
               COUNT(DISTINCT orders.id) as ords,
               COALESCE(SUM(order_items.quantity), 0) as shirts,
               COALESCE(SUM(orders.total_amount), 0.0) as rev
        FROM orders
        LEFT JOIN order_items ON order_items.order_id = orders.id
        {date_where_ord}
        GROUP BY dt ORDER BY dt ASC
    """, ord_params).fetchall()
    for r in rows:
        sales_by_date[r["dt"]] = {
            "orders": int(r["ords"]),
            "shirts": int(r["shirts"]),
            "revenue": round(float(r["rev"]), 2)
        }

    # Merge all unique dates
    all_dates = sorted(list(set(list(inc_by_date.keys()) + list(exp_by_date.keys()) + list(sales_by_date.keys()))))
    
    # If no data yet, create placeholder with today's date
    if not all_dates:
        all_dates = [datetime.now().strftime("%Y-%m-%d")]

    cashflow_timeline = []
    balance_timeline = []
    sales_timeline = []
    running_balance = 0.0

    for d in all_dates:
        inc = inc_by_date.get(d, 0.0)
        exp = exp_by_date.get(d, 0.0)
        net = round(inc - exp, 2)
        running_balance = round(running_balance + net, 2)
        
        cashflow_timeline.append({
            "date": d,
            "incomes": round(inc, 2),
            "expenses": round(exp, 2),
            "net": net
        })
        balance_timeline.append({
            "date": d,
            "balance": running_balance
        })

        sale_info = sales_by_date.get(d, {"orders": 0, "shirts": 0, "revenue": 0.0})
        sales_timeline.append({
            "date": d,
            "orders": sale_info["orders"],
            "shirts": sale_info["shirts"],
            "revenue": sale_info["revenue"]
        })

    conn.close()

    return {
        "period": period,
        "date_range": {"start": s_date, "end": e_date},
        "kpis": {
            "total_incomes": round(total_incomes, 2),
            "total_expenses": round(total_expenses, 2),
            "current_balance": current_balance,
            "gross_profit": gross_profit,
            "gross_profit_margin": gross_profit_margin,
            "total_shirts_sold": total_shirts_sold,
            "total_orders_count": total_orders_count,
            "avg_shirt_cost": avg_shirt_cost,
            "avg_order_revenue": avg_order_revenue,
            "incomes_breakdown": {
                "collected": round(incomes_collected, 2),
                "confirmed": round(incomes_confirmed, 2),
                "pending": round(incomes_pending, 2),
                "count": incomes_count
            },
            "expenses_breakdown": {
                "trasporto": round(exp_trasporto, 2),
                "imballaggio": round(exp_imballaggio, 2),
                "prove": round(exp_prove, 2),
                "magliette": round(exp_magliette, 2),
                "count": expenses_count
            }
        },
        "charts": {
            "cashflow_timeline": cashflow_timeline,
            "balance_timeline": balance_timeline,
            "expenses_by_category": {
                "labels": ["Trasporto", "Imballaggio", "Prove", "Magliette"],
                "values": [round(exp_trasporto, 2), round(exp_imballaggio, 2), round(exp_prove, 2), round(exp_magliette, 2)],
                "colors": ["#0284C7", "#F59E0B", "#8B5CF6", "#0B2545"]
            },
            "sales_timeline": sales_timeline
        }
    }

def get_incomes(search=None, status=None, sort_by="date", order="desc", period="all", start_date=None, end_date=None):
    conn = get_db()
    s_date, e_date = parse_date_range(period, start_date, end_date)

    sql = "SELECT * FROM incomes WHERE 1=1"
    params = []

    if s_date:
        sql += " AND date >= ?"
        params.append(s_date)
    if e_date:
        sql += " AND date <= ?"
        params.append(e_date)

    if status and status != "all":
        sql += " AND status = ?"
        params.append(status)

    if search and search.strip():
        term = f"%{search.strip()}%"
        sql += " AND (description LIKE ? OR order_reference LIKE ? OR payment_method LIKE ? OR notes LIKE ?)"
        params.extend([term, term, term, term])

    # Sorting
    allowed_sorts = {
        "date": "date",
        "amount": "amount",
        "description": "description",
        "status": "status",
        "id": "id"
    }
    col = allowed_sorts.get(sort_by, "date")
    direction = "ASC" if str(order).lower() == "asc" else "DESC"
    sql += f" ORDER BY {col} {direction}, id DESC"

    rows = conn.execute(sql, params).fetchall()
    incomes = [dict(r) for r in rows]

    # Compute summary
    total = sum(i["amount"] for i in incomes)
    collected = sum(i["amount"] for i in incomes if i["status"] == "Incassata")
    confirmed = sum(i["amount"] for i in incomes if i["status"] == "Confermata")
    pending = sum(i["amount"] for i in incomes if i["status"] == "In attesa")

    conn.close()

    return {
        "incomes": incomes,
        "count": len(incomes),
        "summary": {
            "total": round(total, 2),
            "collected": round(collected, 2),
            "confirmed": round(confirmed, 2),
            "pending": round(pending, 2)
        }
    }

def create_income(data):
    description = (data.get("description") or "").strip()
    if not description:
        raise ValueError("La descrizione dell'entrata è obbligatoria.")

    try:
        amount = float(data.get("amount", 0))
    except (ValueError, TypeError):
        raise ValueError("L'importo inserito non è valido.")
    if amount <= 0:
        raise ValueError("L'importo deve essere maggiore di zero.")

    date_str = (data.get("date") or "").strip()
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")

    status = (data.get("status") or "Confermata").strip()
    if status not in VALID_INCOME_STATUSES:
        status = "Confermata"

    payment_method = (data.get("payment_method") or "Bonifico bancario").strip()
    order_reference = (data.get("order_reference") or "").strip()
    order_id = data.get("order_id")
    notes = (data.get("notes") or "").strip()

    now_iso = datetime.now(timezone.utc).isoformat()

    conn = get_db()
    with conn:
        cur = conn.execute("""
            INSERT INTO incomes (
                description, amount, date, payment_method, order_reference,
                order_id, status, notes, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (description, amount, date_str, payment_method, order_reference,
              order_id, status, notes, now_iso, now_iso))
        new_id = cur.lastrowid
        row = conn.execute("SELECT * FROM incomes WHERE id = ?", (new_id,)).fetchone()
    conn.close()

    return dict(row)

def update_income(income_id: int, data: dict):
    conn = get_db()
    existing = conn.execute("SELECT * FROM incomes WHERE id = ?", (income_id,)).fetchone()
    if not existing:
        conn.close()
        raise ValueError(f"Entrata #{income_id} non trovata.")

    description = (data.get("description") or existing["description"]).strip()
    try:
        amount = float(data.get("amount", existing["amount"]))
    except (ValueError, TypeError):
        amount = existing["amount"]
    if amount <= 0:
        raise ValueError("L'importo deve essere maggiore di zero.")

    date_str = (data.get("date") or existing["date"]).strip()
    payment_method = (data.get("payment_method") or existing["payment_method"]).strip()
    order_reference = data.get("order_reference", existing["order_reference"])
    order_id = data.get("order_id", existing["order_id"])
    status = (data.get("status") or existing["status"]).strip()
    if status not in VALID_INCOME_STATUSES:
        status = existing["status"]
    notes = data.get("notes", existing["notes"])

    now_iso = datetime.now(timezone.utc).isoformat()

    with conn:
        conn.execute("""
            UPDATE incomes
            SET description = ?, amount = ?, date = ?, payment_method = ?,
                order_reference = ?, order_id = ?, status = ?, notes = ?, updated_at = ?
            WHERE id = ?
        """, (description, amount, date_str, payment_method, order_reference,
              order_id, status, notes, now_iso, income_id))
        row = conn.execute("SELECT * FROM incomes WHERE id = ?", (income_id,)).fetchone()
    conn.close()

    return dict(row)

def delete_income(income_id: int):
    conn = get_db()
    with conn:
        cur = conn.execute("DELETE FROM incomes WHERE id = ?", (income_id,))
        count = cur.rowcount
    conn.close()
    if count == 0:
        raise ValueError(f"Entrata #{income_id} non trovata.")
    return True

def sync_income_from_order(order_id: int):
    conn = get_db()
    order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if not order:
        conn.close()
        raise ValueError(f"Ordine #{order_id} non trovato.")

    # Check if already synced
    existing = conn.execute("SELECT * FROM incomes WHERE order_id = ?", (order_id,)).fetchone()
    if existing:
        conn.close()
        return dict(existing)

    status_map = {
        "Ordine pagato": "Incassata",
        "Pagamento verificato": "Incassata",
        "Spedito / Consegnato": "Incassata",
        "In preparazione": "Incassata",
        "Ordine confermato": "Confermata",
        "Ordine da pagare": "In attesa",
        "Ordine ricevuto": "In attesa",
        "In attesa di pagamento": "In attesa",
        "Nuovo ordine": "In attesa"
    }
    income_status = status_map.get(order["status"], "Confermata")
    desc = f"Ordine #{order['order_number']} — {order['customer_first_name']} {order['customer_last_name']}"
    date_str = order["created_at"][:10]
    amount = float(order["total_amount"])

    now_iso = datetime.now(timezone.utc).isoformat()
    with conn:
        cur = conn.execute("""
            INSERT INTO incomes (
                description, amount, date, payment_method, order_reference,
                order_id, status, notes, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (desc, amount, date_str, "Bonifico bancario", order["order_number"],
              order_id, income_status, f"Sincronizzato da ordine online. Consegna: {order['delivery_method']}", now_iso, now_iso))
        new_id = cur.lastrowid
        row = conn.execute("SELECT * FROM incomes WHERE id = ?", (new_id,)).fetchone()
    conn.close()

    return dict(row)

def get_expenses(category="all", search=None, sort_by="date", order="desc", period="all", start_date=None, end_date=None):
    conn = get_db()
    s_date, e_date = parse_date_range(period, start_date, end_date)

    sql = "SELECT * FROM expenses WHERE 1=1"
    params = []

    if s_date:
        sql += " AND date >= ?"
        params.append(s_date)
    if e_date:
        sql += " AND date <= ?"
        params.append(e_date)

    if category and category != "all":
        sql += " AND category = ?"
        params.append(category)

    if search and search.strip():
        term = f"%{search.strip()}%"
        sql += " AND (description LIKE ? OR carrier LIKE ? OR material_type LIKE ? OR proof_type LIKE ? OR supplier LIKE ? OR notes LIKE ?)"
        params.extend([term, term, term, term, term, term])

    allowed_sorts = {
        "date": "date",
        "amount": "amount",
        "category": "category",
        "description": "description",
        "id": "id"
    }
    col = allowed_sorts.get(sort_by, "date")
    direction = "ASC" if str(order).lower() == "asc" else "DESC"
    sql += f" ORDER BY {col} {direction}, id DESC"

    rows = conn.execute(sql, params).fetchall()
    expenses = [dict(r) for r in rows]

    total_amount = sum(e["amount"] for e in expenses)

    # Category summaries
    by_category = {
        "trasporto": round(sum(e["amount"] for e in expenses if e["category"] == "trasporto"), 2),
        "imballaggio": round(sum(e["amount"] for e in expenses if e["category"] == "imballaggio"), 2),
        "prove": round(sum(e["amount"] for e in expenses if e["category"] == "prove"), 2),
        "magliette": round(sum(e["amount"] for e in expenses if e["category"] == "magliette"), 2),
    }

    # Category specific metrics
    total_shipments = sum(e.get("shipment_count", 1) or 1 for e in expenses if e["category"] == "trasporto")
    total_packaging_items = sum(e.get("quantity", 0) or 0 for e in expenses if e["category"] == "imballaggio")
    total_shirts_purchased = sum(e.get("quantity", 0) or 0 for e in expenses if e["category"] == "magliette")
    avg_unit_cost = round(by_category["magliette"] / total_shirts_purchased, 2) if total_shirts_purchased > 0 else 0.0

    conn.close()

    return {
        "expenses": expenses,
        "count": len(expenses),
        "summary": {
            "total_amount": round(total_amount, 2),
            "by_category": by_category,
            "category_metrics": {
                "total_shipments": total_shipments,
                "total_packaging_items": total_packaging_items,
                "total_shirts_purchased": total_shirts_purchased,
                "avg_unit_cost": avg_unit_cost
            }
        }
    }

def create_expense(data: dict):
    category = (data.get("category") or "").strip().lower()
    if category not in VALID_EXPENSE_CATEGORIES:
        raise ValueError(f"Categoria spesa non valida. Scegli tra: {', '.join(VALID_EXPENSE_CATEGORIES)}.")

    description = (data.get("description") or "").strip()
    if not description:
        raise ValueError("La descrizione della spesa è obbligatoria.")

    # Calculate or retrieve amount
    try:
        amount = float(data.get("amount", 0))
    except (ValueError, TypeError):
        amount = 0.0

    # Auto-compute amount for magliette or packaging if unit_cost and quantity provided
    quantity = int(data.get("quantity", 0) or 0)
    try:
        unit_cost = float(data.get("unit_cost", 0) or 0)
    except (ValueError, TypeError):
        unit_cost = 0.0
    try:
        extra_costs = float(data.get("extra_production_costs", 0) or 0)
    except (ValueError, TypeError):
        extra_costs = 0.0

    if amount <= 0:
        if category == "magliette" and quantity > 0 and unit_cost > 0:
            amount = round(quantity * unit_cost + extra_costs, 2)
        elif category == "imballaggio" and quantity > 0 and unit_cost > 0:
            amount = round(quantity * unit_cost, 2)

    if amount <= 0:
        raise ValueError("L'importo totale della spesa deve essere maggiore di zero.")

    date_str = (data.get("date") or "").strip()
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")

    # Category fields
    carrier = (data.get("carrier") or "").strip()
    shipment_count = int(data.get("shipment_count", 1) or 1)
    shipment_type = (data.get("shipment_type") or "singola").strip()
    material_type = (data.get("material_type") or "").strip()
    proof_type = (data.get("proof_type") or "").strip()
    supplier = (data.get("supplier") or "").strip()
    notes = (data.get("notes") or "").strip()

    now_iso = datetime.now(timezone.utc).isoformat()

    conn = get_db()
    with conn:
        cur = conn.execute("""
            INSERT INTO expenses (
                category, description, amount, date, carrier, shipment_count,
                shipment_type, material_type, quantity, unit_cost, proof_type,
                supplier, extra_production_costs, notes, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (category, description, amount, date_str, carrier, shipment_count,
              shipment_type, material_type, quantity, unit_cost, proof_type,
              supplier, extra_costs, notes, now_iso, now_iso))
        new_id = cur.lastrowid
        row = conn.execute("SELECT * FROM expenses WHERE id = ?", (new_id,)).fetchone()
    conn.close()

    return dict(row)

def update_expense(expense_id: int, data: dict):
    conn = get_db()
    existing = conn.execute("SELECT * FROM expenses WHERE id = ?", (expense_id,)).fetchone()
    if not existing:
        conn.close()
        raise ValueError(f"Spesa #{expense_id} non trovata.")

    category = (data.get("category") or existing["category"]).strip().lower()
    if category not in VALID_EXPENSE_CATEGORIES:
        category = existing["category"]

    description = (data.get("description") or existing["description"]).strip()
    date_str = (data.get("date") or existing["date"]).strip()

    quantity = int(data.get("quantity", existing["quantity"]) or 0)
    try:
        unit_cost = float(data.get("unit_cost", existing["unit_cost"]) or 0)
    except (ValueError, TypeError):
        unit_cost = existing["unit_cost"]
    try:
        extra_costs = float(data.get("extra_production_costs", existing["extra_production_costs"]) or 0)
    except (ValueError, TypeError):
        extra_costs = existing["extra_production_costs"]

    try:
        amount = float(data.get("amount", existing["amount"]))
    except (ValueError, TypeError):
        amount = existing["amount"]

    if amount <= 0:
        if category == "magliette" and quantity > 0 and unit_cost > 0:
            amount = round(quantity * unit_cost + extra_costs, 2)
        elif category == "imballaggio" and quantity > 0 and unit_cost > 0:
            amount = round(quantity * unit_cost, 2)

    if amount <= 0:
        raise ValueError("L'importo totale della spesa deve essere maggiore di zero.")

    carrier = data.get("carrier", existing["carrier"])
    shipment_count = int(data.get("shipment_count", existing["shipment_count"]) or 1)
    shipment_type = data.get("shipment_type", existing["shipment_type"])
    material_type = data.get("material_type", existing["material_type"])
    proof_type = data.get("proof_type", existing["proof_type"])
    supplier = data.get("supplier", existing["supplier"])
    notes = data.get("notes", existing["notes"])

    now_iso = datetime.now(timezone.utc).isoformat()

    with conn:
        conn.execute("""
            UPDATE expenses
            SET category = ?, description = ?, amount = ?, date = ?, carrier = ?,
                shipment_count = ?, shipment_type = ?, material_type = ?,
                quantity = ?, unit_cost = ?, proof_type = ?, supplier = ?,
                extra_production_costs = ?, notes = ?, updated_at = ?
            WHERE id = ?
        """, (category, description, amount, date_str, carrier, shipment_count,
              shipment_type, material_type, quantity, unit_cost, proof_type,
              supplier, extra_costs, notes, now_iso, expense_id))
        row = conn.execute("SELECT * FROM expenses WHERE id = ?", (expense_id,)).fetchone()
    conn.close()

    return dict(row)

def delete_expense(expense_id: int):
    conn = get_db()
    with conn:
        cur = conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
        count = cur.rowcount
    conn.close()
    if count == 0:
        raise ValueError(f"Spesa #{expense_id} non trovata.")
    return True

def get_insights_data(period="all", start_date=None, end_date=None, filter_color=None, filter_size=None):
    """
    Computes all analytical views:
    - Statistics by Color (Navy vs White)
    - Statistics by Size (S, M, L, XL, XXL, 3XL) + Best/Least sold
    - Cross-Matrix Table: Size x Color x Total
    - Commercial KPIs: Orders, Unique Customers, Shirts, Avg Qty, AOV, Turnover
    - Economic KPIs: Production cost, Transport, Packaging, Proofs, Avg Shirt Cost, Avg Shirt Revenue, Gross Margin, Estimated Profit
    """
    conn = get_db()
    s_date, e_date = parse_date_range(period, start_date, end_date)

    # Base WHERE for orders
    ord_where = " WHERE orders.status != 'Annullato'"
    params = []
    if s_date:
        ord_where += " AND orders.created_at >= ?"
        params.append(s_date + "T00:00:00")
    if e_date:
        ord_where += " AND orders.created_at <= ?"
        params.append(e_date + "T23:59:59")

    # Item filters (if specified)
    item_where = ""
    if filter_color and filter_color in ["navy", "white"]:
        item_where += " AND order_items.color = ?"
        params.append(filter_color)
    if filter_size:
        norm_s = normalize_size(filter_size)
        item_where += " AND (UPPER(order_items.size) = ? OR UPPER(order_items.size) = ?)"
        params.append(norm_s)
        params.append("XXXL" if norm_s == "3XL" else norm_s)

    # 1. Commercial Aggregations
    sql_comm = f"""
        SELECT 
            COUNT(DISTINCT orders.id) as total_orders,
            COUNT(DISTINCT LOWER(orders.customer_email)) as unique_customers,
            COALESCE(SUM(order_items.quantity), 0) as shirts_sold,
            COALESCE(SUM(orders.total_amount), 0.0) as turnover,
            COALESCE(SUM(order_items.total_price), 0.0) as shirt_turnover
        FROM orders
        JOIN order_items ON order_items.order_id = orders.id
        {ord_where} {item_where}
    """
    comm_row = conn.execute(sql_comm, params).fetchone()

    total_orders = int(comm_row["total_orders"])
    unique_customers = int(comm_row["unique_customers"])
    shirts_sold = int(comm_row["shirts_sold"])
    turnover = float(comm_row["turnover"])
    shirt_turnover = float(comm_row["shirt_turnover"])

    avg_qty_per_order = round(shirts_sold / total_orders, 2) if total_orders > 0 else 0.0
    avg_order_value = round(turnover / total_orders, 2) if total_orders > 0 else 0.0

    # 2. Color Distribution (Navy vs White)
    sql_color = f"""
        SELECT 
            order_items.color,
            COALESCE(SUM(order_items.quantity), 0) as qty
        FROM orders
        JOIN order_items ON order_items.order_id = orders.id
        {ord_where}
        GROUP BY order_items.color
    """
    # For global color stats we don't apply color filter
    color_params = [p for i, p in enumerate(params) if not (filter_color and p == filter_color)]
    # Actually build clean color params from ord_where:
    clean_ord_params = []
    if s_date:
        clean_ord_params.append(s_date + "T00:00:00")
    if e_date:
        clean_ord_params.append(e_date + "T23:59:59")

    color_rows = conn.execute(sql_color, clean_ord_params).fetchall()
    navy_sold = 0
    white_sold = 0
    for cr in color_rows:
        col = (cr["color"] or "").lower()
        if col == "navy":
            navy_sold += int(cr["qty"])
        elif col == "white":
            white_sold += int(cr["qty"])

    total_color_shirts = navy_sold + white_sold
    navy_pct = round((navy_sold / total_color_shirts * 100), 1) if total_color_shirts > 0 else 0.0
    white_pct = round((white_sold / total_color_shirts * 100), 1) if total_color_shirts > 0 else 0.0

    # 3. Size Distribution & Cross Matrix
    # Query matrix data: size x color
    sql_matrix = f"""
        SELECT 
            order_items.size,
            order_items.color,
            COALESCE(SUM(order_items.quantity), 0) as qty
        FROM orders
        JOIN order_items ON order_items.order_id = orders.id
        {ord_where}
        GROUP BY order_items.size, order_items.color
    """
    matrix_rows = conn.execute(sql_matrix, clean_ord_params).fetchall()

    # Pre-populate matrix
    matrix_dict = {sz: {"navy": 0, "white": 0, "total": 0} for sz in SIZES_ORDER}
    for mr in matrix_rows:
        sz = normalize_size(mr["size"])
        col = (mr["color"] or "").lower()
        q = int(mr["qty"])
        if sz in matrix_dict:
            if col == "navy":
                matrix_dict[sz]["navy"] += q
            elif col == "white":
                matrix_dict[sz]["white"] += q
            matrix_dict[sz]["total"] += q

    # Build cross table rows
    cross_table = []
    size_stats = []
    for sz in SIZES_ORDER:
        d = matrix_dict[sz]
        pct = round((d["total"] / total_color_shirts * 100), 1) if total_color_shirts > 0 else 0.0
        cross_table.append({
            "size": sz,
            "navy": d["navy"],
            "white": d["white"],
            "total": d["total"],
            "percentage": pct
        })
        size_stats.append({
            "size": sz,
            "quantity": d["total"],
            "percentage": pct
        })

    # Best seller & Least seller size
    sorted_by_sales = sorted(cross_table, key=lambda x: x["total"], reverse=True)
    best_seller = sorted_by_sales[0] if sorted_by_sales and sorted_by_sales[0]["total"] > 0 else None
    
    # For least seller: lowest count among sizes
    least_seller = sorted_by_sales[-1] if sorted_by_sales else None

    # Cross table grand totals
    grand_total_row = {
        "size": "TOTALE",
        "navy": navy_sold,
        "white": white_sold,
        "total": total_color_shirts,
        "percentage": 100.0 if total_color_shirts > 0 else 0.0
    }

    # 4. Economic Calculations
    # Fetch expenses in date range
    exp_where = " WHERE 1=1"
    exp_params = []
    if s_date:
        exp_where += " AND date >= ?"
        exp_params.append(s_date)
    if e_date:
        exp_where += " AND date <= ?"
        exp_params.append(e_date)

    exp_res = conn.execute(f"""
        SELECT 
            COALESCE(SUM(amount), 0.0) as total_expenses,
            COALESCE(SUM(CASE WHEN category = 'trasporto' THEN amount ELSE 0.0 END), 0.0) as trasporto,
            COALESCE(SUM(CASE WHEN category = 'imballaggio' THEN amount ELSE 0.0 END), 0.0) as imballaggio,
            COALESCE(SUM(CASE WHEN category = 'prove' THEN amount ELSE 0.0 END), 0.0) as prove,
            COALESCE(SUM(CASE WHEN category = 'magliette' THEN amount ELSE 0.0 END), 0.0) as magliette,
            COALESCE(SUM(CASE WHEN category = 'magliette' THEN quantity ELSE 0 END), 0) as purchased_qty
        FROM expenses
        {exp_where}
    """, exp_params).fetchone()

    total_expenses = float(exp_res["total_expenses"])
    exp_trasporto = float(exp_res["trasporto"])
    exp_imballaggio = float(exp_res["imballaggio"])
    exp_prove = float(exp_res["prove"])
    exp_magliette = float(exp_res["magliette"])
    purchased_qty = int(exp_res["purchased_qty"])

    production_cost = round(exp_magliette + exp_prove, 2)

    # Costo medio per maglietta:
    if purchased_qty > 0:
        avg_shirt_cost = round(exp_magliette / purchased_qty, 2)
    elif total_color_shirts > 0 and exp_magliette > 0:
        avg_shirt_cost = round(exp_magliette / total_color_shirts, 2)
    else:
        avg_shirt_cost = 0.0

    # Ricavo medio per maglietta:
    avg_shirt_revenue = round(turnover / total_color_shirts, 2) if total_color_shirts > 0 else 0.0

    # Margine lordo:
    gross_margin_amount = round(turnover - production_cost, 2)
    gross_margin_pct = round((gross_margin_amount / turnover * 100), 1) if turnover > 0 else 0.0

    # Utile stimato (Total Turnover - Total Expenses, or Incomes - Expenses)
    # Check total incomes as well
    inc_res = conn.execute(f"""
        SELECT COALESCE(SUM(amount), 0.0) as total_incomes
        FROM incomes
        {exp_where}
    """, exp_params).fetchone()
    total_incomes = float(inc_res["total_incomes"])

    # If incomes recorded, use total_incomes - total_expenses, otherwise turnover - total_expenses
    base_rev = total_incomes if total_incomes > 0 else turnover
    estimated_profit = round(base_rev - total_expenses, 2)
    profit_margin_pct = round((estimated_profit / base_rev * 100), 1) if base_rev > 0 else 0.0

    # 5. Sales trend over time
    sales_trend_rows = conn.execute(f"""
        SELECT 
            substr(orders.created_at, 1, 10) as dt,
            COUNT(DISTINCT orders.id) as ords,
            COALESCE(SUM(order_items.quantity), 0) as shirts,
            COALESCE(SUM(orders.total_amount), 0.0) as rev
        FROM orders
        JOIN order_items ON order_items.order_id = orders.id
        {ord_where}
        GROUP BY dt
        ORDER BY dt ASC
    """, clean_ord_params).fetchall()

    sales_trend = []
    for r in sales_trend_rows:
        sales_trend.append({
            "date": r["dt"],
            "orders": int(r["ords"]),
            "shirts": int(r["shirts"]),
            "revenue": round(float(r["rev"]), 2)
        })

    conn.close()

    return {
        "period": period,
        "date_range": {"start": s_date, "end": e_date},
        "color_stats": {
            "navy_sold": navy_sold,
            "white_sold": white_sold,
            "total_shirts": total_color_shirts,
            "navy_percentage": navy_pct,
            "white_percentage": white_pct,
            "chart": {
                "labels": ["Blu navy", "Bianca"],
                "values": [navy_sold, white_sold],
                "colors": ["#003760", "#E2E8F0"]
            }
        },
        "size_stats": {
            "sizes": size_stats,
            "best_seller": best_seller,
            "least_seller": least_seller,
            "cross_matrix": {
                "rows": cross_table,
                "total_row": grand_total_row
            }
        },
        "commercial_stats": {
            "total_orders": total_orders,
            "unique_customers": unique_customers,
            "total_shirts_sold": shirts_sold,
            "avg_qty_per_order": avg_qty_per_order,
            "avg_order_value": avg_order_value,
            "total_revenue": round(turnover, 2),
            "sales_trend": sales_trend
        },
        "economic_stats": {
            "production_cost": production_cost,
            "transport_cost": round(exp_trasporto, 2),
            "packaging_cost": round(exp_imballaggio, 2),
            "proof_cost": round(exp_prove, 2),
            "avg_shirt_cost": avg_shirt_cost,
            "avg_shirt_revenue": avg_shirt_revenue,
            "gross_margin_amount": gross_margin_amount,
            "gross_margin_percentage": gross_margin_pct,
            "estimated_profit": estimated_profit,
            "profit_margin_percentage": profit_margin_pct
        }
    }

def export_financial_csv(export_type="all"):
    """
    Generates CSV formatted with UTF-8 BOM and ';' delimiter for full Excel/Numbers compatibility.
    """
    output = io.StringIO()
    # Write UTF-8 BOM
    output.write("\ufeff")
    writer = csv.writer(output, delimiter=";", quoting=csv.QUOTE_MINIMAL)

    conn = get_db()

    if export_type == "incomes":
        writer.writerow(["ID", "DATA", "DESCRIZIONE", "IMPORTO (€)", "METODO DI PAGAMENTO", "RIFERIMENTO ORDINE", "STATO", "NOTE"])
        rows = conn.execute("SELECT * FROM incomes ORDER BY date DESC, id DESC").fetchall()
        for r in rows:
            writer.writerow([
                r["id"],
                r["date"],
                r["description"],
                f"{r['amount']:.2f}",
                r["payment_method"],
                r["order_reference"],
                r["status"],
                r["notes"] or ""
            ])

    elif export_type == "expenses":
        writer.writerow(["ID", "DATA", "CATEGORIA", "DESCRIZIONE", "IMPORTO (€)", "DETTAGLI SPECIFICI", "NOTE"])
        rows = conn.execute("SELECT * FROM expenses ORDER BY date DESC, id DESC").fetchall()
        for r in rows:
            cat = r["category"]
            details = []
            if cat == "trasporto":
                if r["carrier"]: details.append(f"Corriere: {r['carrier']}")
                if r["shipment_count"]: details.append(f"Spedizioni: {r['shipment_count']}")
                if r["shipment_type"]: details.append(f"Tipo: {r['shipment_type']}")
            elif cat == "imballaggio":
                if r["material_type"]: details.append(f"Materiale: {r['material_type']}")
                if r["quantity"]: details.append(f"Q.tà: {r['quantity']}")
                if r["unit_cost"]: details.append(f"Unitario: {r['unit_cost']:.2f} €")
            elif cat == "prove":
                if r["proof_type"]: details.append(f"Tipo prova: {r['proof_type']}")
            elif cat == "magliette":
                if r["supplier"]: details.append(f"Fornitore: {r['supplier']}")
                if r["quantity"]: details.append(f"Q.tà: {r['quantity']}")
                if r["unit_cost"]: details.append(f"Unitario: {r['unit_cost']:.2f} €")
                if r["extra_production_costs"]: details.append(f"Extra: {r['extra_production_costs']:.2f} €")
            
            writer.writerow([
                r["id"],
                r["date"],
                cat.upper(),
                r["description"],
                f"{r['amount']:.2f}",
                " | ".join(details),
                r["notes"] or ""
            ])

    elif export_type == "insights_matrix":
        writer.writerow(["TAGLIA", "BLU NAVY", "BIANCA", "TOTALE VENDUTO", "PERCENTUALE"])
        insights = get_insights_data(period="all")
        matrix = insights["size_stats"]["cross_matrix"]
        for row in matrix["rows"]:
            writer.writerow([
                row["size"],
                row["navy"],
                row["white"],
                row["total"],
                f"{row['percentage']:.1f}%"
            ])
        tot = matrix["total_row"]
        writer.writerow([
            tot["size"],
            tot["navy"],
            tot["white"],
            tot["total"],
            f"{tot['percentage']:.1f}%"
        ])

    else:
        # Full summary export
        writer.writerow(["=== TAVOLARA WEAR — REPORT FINANZIARIO GENERALE ==="])
        writer.writerow(["Data Generazione", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
        writer.writerow([])
        
        overview = get_overview_data(period="all")
        k = overview["kpis"]
        writer.writerow(["INDICATORE", "VALORE"])
        writer.writerow(["Totale Entrate", f"{k['total_incomes']:.2f} €"])
        writer.writerow(["Totale Uscite", f"{k['total_expenses']:.2f} €"])
        writer.writerow(["Saldo Attuale", f"{k['current_balance']:.2f} €"])
        writer.writerow(["Utile Lordo", f"{k['gross_profit']:.2f} €"])
        writer.writerow(["Totale Magliette Vendute", k["total_shirts_sold"]])
        writer.writerow(["Totale Ordini Ricevuti", k["total_orders_count"]])
        writer.writerow(["Costo Medio per Maglietta", f"{k['avg_shirt_cost']:.2f} €"])
        writer.writerow(["Ricavo Medio per Ordine", f"{k['avg_order_revenue']:.2f} €"])
        writer.writerow([])

        writer.writerow(["--- SPESE PER CATEGORIA ---"])
        exp = k["expenses_breakdown"]
        writer.writerow(["Trasporto", f"{exp['trasporto']:.2f} €"])
        writer.writerow(["Imballaggio", f"{exp['imballaggio']:.2f} €"])
        writer.writerow(["Prove e Sviluppo", f"{exp['prove']:.2f} €"])
        writer.writerow(["Magliette", f"{exp['magliette']:.2f} €"])

    conn.close()
    return output.getvalue().encode("utf-8")
