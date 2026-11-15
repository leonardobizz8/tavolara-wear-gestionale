"""
Tavolara Wear — Order System HTTP & API Server
Full production server using Python standard library with multi-threading,
SQLite database, atomic transactions, session authentication, and REST API.
"""

import http.server
import socketserver
import os
import json
import urllib.parse
import re
import csv
import io
import secrets
import hashlib
import hmac
from datetime import datetime, timezone, timedelta
from database import get_db, init_db, hash_password
import financial
import excel_sync

PORT = 8080
STATIC_DIR = os.path.join(os.path.dirname(__file__), "public") if os.path.isdir(os.path.join(os.path.dirname(__file__), "public")) else os.path.join(os.path.dirname(__file__), "static")

def read_safe_env():
    url = os.environ.get("SUPABASE_URL", "")
    anon = os.environ.get("SUPABASE_ANON_KEY", "")
    cfg = {
        "supabase_url": url,
        "supabase_anon_key": anon,
        "is_configured": bool(url and anon)
    }
    if cfg["is_configured"]:
        return cfg

    env_file = os.path.join(os.path.dirname(__file__), ".env")
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
                    if k == "SUPABASE_URL" and not cfg["supabase_url"]:
                        cfg["supabase_url"] = v
                    elif k == "SUPABASE_ANON_KEY" and not cfg["supabase_anon_key"]:
                        if "service_role" in v.lower():
                            continue
                        cfg["supabase_anon_key"] = v
        cfg["is_configured"] = bool(cfg["supabase_url"] and cfg["supabase_anon_key"])
    except Exception as e:
        print("[Server] Errore lettura .env:", e)
    return cfg

# Helper: parse json body
def read_json_body(handler):
    content_len = int(handler.headers.get("Content-Length", 0))
    if content_len == 0:
        return {}
    raw = handler.rfile.read(content_len).decode("utf-8")
    return json.loads(raw)

# Helper: json response
def send_json(handler, data, status=200):
    body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE, OPTIONS")
    handler.end_headers()
    handler.wfile.write(body)

def send_error_json(handler, message, status=400, details=None):
    payload = {"error": True, "message": message}
    if details:
        payload["details"] = details
    send_json(handler, payload, status=status)

# Auth helper: check admin bearer token or session cookie
def get_auth_token(handler):
    auth_header = handler.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:].strip()
    
    # Check Cookie header
    cookie_header = handler.headers.get("Cookie", "")
    cookies = [c.strip() for c in cookie_header.split(";")]
    for c in cookies:
        if c.startswith("tavolara_admin_session="):
            return c.split("=", 1)[1].strip()

    # Check query param ?token=
    try:
        parsed = urllib.parse.urlparse(handler.path)
        qs = urllib.parse.parse_qs(parsed.query)
        if "token" in qs and qs["token"]:
            return qs["token"][0].strip()
    except Exception:
        pass
    return None

AUTH_SECRET = os.environ.get("AUTH_SECRET", "tavolara_wear_permanent_auth_secret_2026_key")

def generate_admin_token():
    # Deterministic, permanent HMAC signature valid forever across all serverless lambda instances
    return hmac.new(AUTH_SECRET.encode("utf-8"), b"tavolara_wear_permanent_session_2026", hashlib.sha256).hexdigest()

def is_admin_authenticated(handler):
    token = get_auth_token(handler)
    if not token:
        return False

    # 1. Stateless permanent HMAC verification (bulletproof across all Vercel instances forever)
    permanent_token = generate_admin_token()
    if hmac.compare_digest(token, permanent_token):
        return True

    # 2. Check if token matches admin password directly or hashed
    admin_env_pass = os.environ.get("ADMIN_PASSWORD", "tavolara2026")
    if token == admin_env_pass or token == hash_password(admin_env_pass):
        return True

    # 3. Fallback to SQLite admin_sessions for backwards compatibility
    try:
        conn = get_db()
        row = conn.execute("SELECT expires_at FROM admin_sessions WHERE token = ?", (token,)).fetchone()
        conn.close()
        if row:
            return True
    except Exception:
        pass

    return False

# Server Request Handler
class TavolaraHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=STATIC_DIR, **kwargs)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE, OPTIONS")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # -----------------------------
        # PUBLIC APIs
        # -----------------------------
        if path == "/api/config":
            send_json(self, read_safe_env())
            return

        if path == "/api/config/public":
            conn = get_db()
            rows = conn.execute("SELECT key, value FROM config").fetchall()
            conn.close()
            cfg = {r["key"]: r["value"] for r in rows}
            
            # Check price configuration
            shirt_price_val = None
            if cfg.get("shirt_price"):
                try:
                    shirt_price_val = float(cfg["shirt_price"])
                except ValueError:
                    pass

            shipping_locker_val = None
            if cfg.get("shipping_locker"):
                try:
                    shipping_locker_val = float(cfg["shipping_locker"])
                except ValueError:
                    pass

            shipping_home_val = None
            if cfg.get("shipping_home"):
                try:
                    shipping_home_val = float(cfg["shipping_home"])
                except ValueError:
                    pass

            shipping_hand_val = 0.0
            if cfg.get("shipping_hand"):
                try:
                    shipping_hand_val = float(cfg["shipping_hand"])
                except ValueError:
                    pass

            is_configured = (shirt_price_val is not None and shirt_price_val > 0)
            
            # Bank configured status (do not expose full IBAN until order confirmation)
            has_bank_info = bool(cfg.get("bank_iban") and cfg.get("bank_holder"))

            public_data = {
                "shirt_price": shirt_price_val,
                "shipping_locker": shipping_locker_val,
                "shipping_home": shipping_home_val,
                "shipping_hand": shipping_hand_val,
                "is_configured": is_configured,
                "has_bank_info": has_bank_info,
                "brand_name": "Tavolara Wear",
                "brand_instagram": cfg.get("brand_instagram", "@tavolara.wear"),
                "brand_site": cfg.get("brand_site", "https://tavolarawear.it/"),
                "brand_email": cfg.get("brand_email", "info@tavolarawear.it"),
                "brand_phone": cfg.get("brand_phone", "")
            }
            send_json(self, public_data)
            return

        if path == "/api/variants":
            conn = get_db()
            rows = conn.execute("""
                SELECT id, product, color, color_name, size, is_available, stock_qty
                FROM variants
                ORDER BY color, id
            """).fetchall()
            conn.close()
            variants = [dict(r) for r in rows]
            send_json(self, {"variants": variants})
            return

        if path.startswith("/api/orders/token/"):
            token = path.split("/api/orders/token/")[1].strip()
            conn = get_db()
            order = conn.execute("""
                SELECT * FROM orders WHERE order_token = ?
            """, (token,)).fetchone()
            if not order:
                conn.close()
                send_error_json(self, "Ordine non trovato o link non valido.", status=404)
                return
            items = conn.execute("""
                SELECT * FROM order_items WHERE order_id = ?
            """, (order["id"],)).fetchall()
            conn.close()

            data = dict(order)
            data["items"] = [dict(it) for it in items]
            # Redact client_ip and admin fields
            data.pop("client_ip", None)
            send_json(self, {"order": data})
            return

        # -----------------------------
        # ADMIN APIs (Protected)
        # -----------------------------
        if path.startswith("/api/admin/"):
            if not is_admin_authenticated(self):
                send_error_json(self, "Accesso non autorizzato. Effettua l'accesso come amministratore.", status=401)
                return

            if path == "/api/admin/me":
                send_json(self, {"authenticated": True, "user": "admin"})
                return

            if path == "/api/admin/orders":
                conn = get_db()
                sql = "SELECT * FROM orders WHERE 1=1"
                params = []

                # Filter by status
                if "status" in query and query["status"][0]:
                    sql += " AND status = ?"
                    params.append(query["status"][0])

                # Filter by delivery
                if "delivery" in query and query["delivery"][0]:
                    sql += " AND delivery_method = ?"
                    params.append(query["delivery"][0])

                # Filter by search (name, surname, order_number, email)
                if "search" in query and query["search"][0].strip():
                    term = f"%{query['search'][0].strip()}%"
                    sql += " AND (order_number LIKE ? OR customer_first_name LIKE ? OR customer_last_name LIKE ? OR customer_email LIKE ?)"
                    params.extend([term, term, term, term])

                # Filter by date range
                if "date_from" in query and query["date_from"][0]:
                    sql += " AND created_at >= ?"
                    params.append(query["date_from"][0])
                if "date_to" in query and query["date_to"][0]:
                    sql += " AND created_at <= ?"
                    params.append(query["date_to"][0] + "T23:59:59")

                sql += " ORDER BY created_at DESC, id DESC"
                orders = conn.execute(sql, params).fetchall()

                # Attach items
                result = []
                for o in orders:
                    od = dict(o)
                    items = conn.execute("SELECT * FROM order_items WHERE order_id = ?", (o["id"],)).fetchall()
                    od["items"] = [dict(it) for it in items]
                    result.append(od)

                conn.close()
                send_json(self, {"orders": result, "count": len(result)})
                return

            if path == "/api/admin/analytics":
                conn = get_db()
                total_orders = conn.execute("SELECT COUNT(*) as count FROM orders").fetchone()["count"]
                
                # Active orders (not cancelled)
                active_orders = conn.execute("SELECT COUNT(*) as count FROM orders WHERE status != 'Annullato'").fetchone()["count"]
                
                # Shirts sold (not cancelled)
                shirts_sold = conn.execute("""
                    SELECT COALESCE(SUM(oi.quantity), 0) as total
                    FROM order_items oi
                    JOIN orders o ON oi.order_id = o.id
                    WHERE o.status != 'Annullato'
                """).fetchone()["total"]

                # By size
                by_size = conn.execute("""
                    SELECT oi.size, COALESCE(SUM(oi.quantity), 0) as qty
                    FROM order_items oi
                    JOIN orders o ON oi.order_id = o.id
                    WHERE o.status != 'Annullato'
                    GROUP BY oi.size
                    ORDER BY oi.size
                """).fetchall()

                # By color
                by_color = conn.execute("""
                    SELECT oi.color_name, COALESCE(SUM(oi.quantity), 0) as qty
                    FROM order_items oi
                    JOIN orders o ON oi.order_id = o.id
                    WHERE o.status != 'Annullato'
                    GROUP BY oi.color_name
                    ORDER BY oi.color_name
                """).fetchall()

                # Status counts
                pending_payment = conn.execute("""
                    SELECT COUNT(*) as count, COALESCE(SUM(total_amount), 0) as revenue
                    FROM orders
                    WHERE status IN ('Nuovo ordine', 'In attesa di pagamento')
                """).fetchone()

                verified_payment = conn.execute("""
                    SELECT COUNT(*) as count, COALESCE(SUM(total_amount), 0) as revenue
                    FROM orders
                    WHERE status IN ('Pagamento verificato', 'In preparazione', 'Spedito / Consegnato')
                """).fetchone()

                cancelled_payment = conn.execute("""
                    SELECT COUNT(*) as count, COALESCE(SUM(total_amount), 0) as revenue
                    FROM orders
                    WHERE status = 'Annullato'
                """).fetchone()

                conn.close()

                analytics = {
                    "total_orders": total_orders,
                    "active_orders": active_orders,
                    "shirts_sold": shirts_sold,
                    "by_size": [dict(r) for r in by_size],
                    "by_color": [dict(r) for r in by_color],
                    "pending_orders_count": pending_payment["count"],
                    "pending_revenue": pending_payment["revenue"],
                    "verified_orders_count": verified_payment["count"],
                    "verified_revenue": verified_payment["revenue"],
                    "cancelled_orders_count": cancelled_payment["count"]
                }
                send_json(self, {"analytics": analytics})
                return

            if path == "/api/admin/export-csv":
                conn = get_db()
                orders = conn.execute("SELECT * FROM orders ORDER BY id DESC").fetchall()
                
                output = io.StringIO()
                # UTF-8 BOM for Excel
                output.write('\ufeff')
                writer = csv.writer(output, delimiter=';')
                
                writer.writerow([
                    "Numero Ordine", "Data Creazione", "Stato", "Nome", "Cognome", 
                    "Email", "Telefono", "Modalità Consegna", "Dettagli Consegna",
                    "Articoli", "Quantità Totale", "Subtotale Prodotti (€)",
                    "Spedizione (€)", "Codice Sconto", "Sconto (€)", "Totale Finale (€)",
                    "Causale Bonifico", "Intestatario", "IBAN"
                ])

                for o in orders:
                    items = conn.execute("SELECT * FROM order_items WHERE order_id = ?", (o["id"],)).fetchall()
                    items_str = ", ".join([f"{it['product_name']} ({it['color_name']} {it['size']} x{it['quantity']})" for it in items])
                    total_qty = sum([it['quantity'] for it in items])
                    
                    delivery_str = ""
                    if o["delivery_method"] == "locker":
                        delivery_str = f"Locker: {o['locker_name']} - {o['delivery_address']}, {o['delivery_zip']} {o['delivery_city']} ({o['delivery_notes'] or ''})"
                    elif o["delivery_method"] == "home":
                        delivery_str = f"Domicilio: {o['delivery_address']}, {o['delivery_zip']} {o['delivery_city']} ({o['delivery_province']}) ({o['delivery_notes'] or ''})"
                    else:
                        delivery_str = f"A mano: {o['hand_location']} ({o['hand_preferences'] or ''})"

                    writer.writerow([
                        o["order_number"],
                        o["created_at"],
                        o["status"],
                        o["customer_first_name"],
                        o["customer_last_name"],
                        o["customer_email"],
                        o["customer_phone"],
                        o["delivery_method"],
                        delivery_str,
                        items_str,
                        total_qty,
                        f"{(o['shirt_price'] or 0.0) * total_qty:.2f}",
                        f"{(o['shipping_cost'] or 0.0):.2f}",
                        o["discount_code"] or "",
                        f"{(o['discount_amount'] or 0.0):.2f}",
                        f"{(o['total_amount'] or 0.0):.2f}",
                        o["wire_causale"],
                        o["bank_holder"] or "",
                        o["bank_iban"] or ""
                    ])

                conn.close()
                csv_bytes = output.getvalue().encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/csv; charset=utf-8")
                self.send_header("Content-Disposition", f"attachment; filename=tavolara_ordini_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
                self.send_header("Content-Length", str(len(csv_bytes)))
                self.end_headers()
                self.wfile.write(csv_bytes)
                return

            if path == "/api/admin/config":
                conn = get_db()
                rows = conn.execute("SELECT key, value, updated_at FROM config").fetchall()
                conn.close()
                cfg = {r["key"]: r["value"] for r in rows}
                # Do not expose admin_password_hash in plain response
                cfg.pop("admin_password_hash", None)
                send_json(self, {"config": cfg})
                return

            if path == "/api/admin/variants":
                conn = get_db()
                rows = conn.execute("SELECT * FROM variants ORDER BY color, id").fetchall()
                conn.close()
                send_json(self, {"variants": [dict(r) for r in rows]})
                return

            if path == "/api/admin/discounts":
                conn = get_db()
                rows = conn.execute("SELECT * FROM discount_codes ORDER BY id DESC").fetchall()
                conn.close()
                send_json(self, {"discounts": [dict(r) for r in rows]})
                return

            # -----------------------------
            # FINANCIAL MANAGEMENT APIs
            # -----------------------------
            if path == "/api/admin/financial/overview":
                period = query.get("period", ["all"])[0]
                s_date = query.get("start_date", [None])[0]
                e_date = query.get("end_date", [None])[0]
                data = financial.get_overview_data(period=period, start_date=s_date, end_date=e_date)
                send_json(self, data)
                return

            if path == "/api/admin/financial/partners":
                period = query.get("period", ["all"])[0]
                s_date = query.get("start_date", [None])[0]
                e_date = query.get("end_date", [None])[0]
                try:
                    pala_ratio = float(query.get("pala_ratio", [0.5])[0])
                except (ValueError, TypeError):
                    pala_ratio = 0.5
                try:
                    leo_ratio = float(query.get("leo_ratio", [0.5])[0])
                except (ValueError, TypeError):
                    leo_ratio = 0.5
                data = financial.get_partners_profit(period=period, start_date=s_date, end_date=e_date,
                                                     pala_ratio=pala_ratio, leo_ratio=leo_ratio)
                send_json(self, data)
                return

            if path == "/api/admin/incomes":
                search = query.get("search", [None])[0]
                status_filter = query.get("status", ["all"])[0]
                sort_by = query.get("sort_by", ["date"])[0]
                order_dir = query.get("order", ["desc"])[0]
                period = query.get("period", ["all"])[0]
                s_date = query.get("start_date", [None])[0]
                e_date = query.get("end_date", [None])[0]
                data = financial.get_incomes(search=search, status=status_filter, sort_by=sort_by,
                                             order=order_dir, period=period, start_date=s_date, end_date=e_date)
                send_json(self, data)
                return

            if path == "/api/admin/expenses":
                category = query.get("category", ["all"])[0]
                search = query.get("search", [None])[0]
                sort_by = query.get("sort_by", ["date"])[0]
                order_dir = query.get("order", ["desc"])[0]
                period = query.get("period", ["all"])[0]
                s_date = query.get("start_date", [None])[0]
                e_date = query.get("end_date", [None])[0]
                data = financial.get_expenses(category=category, search=search, sort_by=sort_by,
                                              order=order_dir, period=period, start_date=s_date, end_date=e_date)
                send_json(self, data)
                return

            if path == "/api/admin/insights":
                period = query.get("period", ["all"])[0]
                s_date = query.get("start_date", [None])[0]
                e_date = query.get("end_date", [None])[0]
                f_color = query.get("color", [None])[0]
                f_size = query.get("size", [None])[0]
                data = financial.get_insights_data(period=period, start_date=s_date, end_date=e_date,
                                                   filter_color=f_color, filter_size=f_size)
                send_json(self, data)
                return

            if path == "/api/admin/financial/export-csv":
                export_type = query.get("type", ["all"])[0]
                csv_bytes = financial.export_financial_csv(export_type=export_type)
                self.send_response(200)
                self.send_header("Content-Type", "text/csv; charset=utf-8")
                self.send_header("Content-Disposition", f"attachment; filename=tavolara_{export_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
                self.send_header("Content-Length", str(len(csv_bytes)))
                self.end_headers()
                self.wfile.write(csv_bytes)
                return

            if path == "/api/admin/excel/status":
                excel_sync.check_auto_sync()
                send_json(self, excel_sync.get_excel_sync_status())
                return

            if path == "/api/admin/excel/download":
                if not is_admin_authenticated(self):
                    send_error_json(self, "Non autorizzato.", status=401)
                    return
                excel_path = excel_sync.find_best_excel_file()
                if not excel_path or not os.path.exists(excel_path):
                    send_error_json(self, "File Excel non trovato.", status=404)
                    return
                try:
                    with open(excel_path, "rb") as f:
                        file_bytes = f.read()
                    filename = os.path.basename(excel_path)
                    self.send_response(200)
                    self.send_header("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                    self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
                    self.send_header("Content-Length", str(len(file_bytes)))
                    self.end_headers()
                    self.wfile.write(file_bytes)
                    return
                except Exception as e:
                    send_error_json(self, f"Errore download Excel: {str(e)}", status=500)
                    return

        # -----------------------------
        # API 404 CATCH-ALL (Never fall through to HTML 404)
        # -----------------------------
        if path.startswith("/api"):
            send_error_json(self, f"Endpoint API non trovato: {path}", status=404)
            return

        # -----------------------------
        # STATIC SPA ROUTING
        # -----------------------------
        # Customer ordering form
        if path in ["/modulo", "/ordina", "/modulo.html"] or path.startswith("/ordine/"):
            self.serve_file(os.path.join(STATIC_DIR, "modulo.html"), "text/html; charset=utf-8")
            return

        # All other non-file paths serve the GESTIONALE SPA
        if path in ["/", "/admin", "/admin/", "/admin/index.html", "/gestionale", "/dashboard", "/index.html", "/login", "/overview", "/attivo", "/passivo", "/entrate", "/uscite", "/ordini", "/insights", "/settings"] or not os.path.splitext(path)[1]:
            self.serve_file(os.path.join(STATIC_DIR, "admin.html"), "text/html; charset=utf-8")
            return

        super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # -----------------------------
        # PUBLIC: Validate Discount Code
        # -----------------------------
        if path == "/api/discounts/validate":
            data = read_json_body(self)
            code = data.get("code", "").strip().upper()
            if not code:
                send_error_json(self, "Inserisci un codice promozionale valido.")
                return

            conn = get_db()
            disc = conn.execute("""
                SELECT * FROM discount_codes WHERE UPPER(code) = ?
            """, (code,)).fetchone()
            conn.close()

            if not disc or not disc["is_active"]:
                send_error_json(self, f"Il codice sconto '{code}' non è valido o è disattivato.", status=404)
                return

            if disc["max_uses"] is not None and disc["usage_count"] >= disc["max_uses"]:
                send_error_json(self, f"Il codice sconto '{code}' ha raggiunto il limite massimo di utilizzi.", status=400)
                return

            send_json(self, {
                "valid": True,
                "code": disc["code"],
                "discount_type": disc["discount_type"],
                "discount_value": float(disc["discount_value"]),
                "message": f"Codice applicato! Sconto di {disc['discount_value']:.2f} €"
            })
            return

        # -----------------------------
        # PUBLIC: Create Order
        # -----------------------------
        if path == "/api/orders":
            data = read_json_body(self)

            # Check privacy acceptance
            if not data.get("privacy_accepted"):
                send_error_json(self, "È necessario accettare l'informativa sulla privacy per procedere con l'ordine.")
                return

            # Customer validations
            first_name = (data.get("customer_first_name") or "").strip()
            last_name = (data.get("customer_last_name") or "").strip()
            email = (data.get("customer_email") or "").strip()
            phone = (data.get("customer_phone") or "").strip()

            if not first_name or not last_name:
                send_error_json(self, "Nome e cognome sono obbligatori.")
                return

            email_regex = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
            if not re.match(email_regex, email):
                send_error_json(self, "Indirizzo email non valido.")
                return

            # Basic phone validation (at least 6 digits)
            clean_phone = re.sub(r"[\s\-\+\(\)]", "", phone)
            if not clean_phone or len(clean_phone) < 6:
                send_error_json(self, "Numero di telefono non valido.")
                return

            # Product selection validation
            color = (data.get("color") or "").strip().lower()
            size = (data.get("size") or "").strip().upper()
            try:
                quantity = int(data.get("quantity", 1))
            except (ValueError, TypeError):
                quantity = 1

            if quantity < 1 or quantity > 20:
                send_error_json(self, "La quantità selezionata deve essere compresa tra 1 e 20.")
                return

            if color not in ["navy", "white"]:
                send_error_json(self, "Colore non valido. Seleziona Blu navy o Bianco.")
                return

            allowed_sizes = ["S", "M", "L", "XL", "XXL", "XXXL"]
            if size not in allowed_sizes:
                send_error_json(self, f"Taglia non valida. Scegli tra: {', '.join(allowed_sizes)}.")
                return

            # Delivery method validation
            delivery_method = data.get("delivery_method")
            if delivery_method not in ["locker", "home", "hand"]:
                send_error_json(self, "Seleziona una modalità di consegna valida (Locker, Domicilio o Consegna a mano).")
                return

            delivery_details = data.get("delivery_details") or {}
            locker_name = delivery_details.get("locker_name", "").strip()
            delivery_address = delivery_details.get("address", "").strip()
            delivery_zip = delivery_details.get("zip", "").strip()
            delivery_city = delivery_details.get("city", "").strip()
            delivery_province = delivery_details.get("province", "").strip()
            delivery_notes = delivery_details.get("notes", "").strip()
            hand_location = delivery_details.get("hand_location", "").strip()
            hand_preferences = delivery_details.get("hand_preferences", "").strip()

            if delivery_method == "locker":
                if not locker_name or not delivery_address or not delivery_zip or not delivery_city:
                    send_error_json(self, "Per la consegna al locker/punto di ritiro, compila nome del punto, indirizzo, CAP e località.")
                    return
            elif delivery_method == "home":
                if not delivery_address or not delivery_zip or not delivery_city or not delivery_province:
                    send_error_json(self, "Per la spedizione a domicilio, compila via/civico, CAP, città e provincia.")
                    return
            elif delivery_method == "hand":
                if not hand_location:
                    send_error_json(self, "Per la consegna a mano, indica la località desiderata.")
                    return

            # Fetch DB config & check prices
            conn = get_db()
            cfg_rows = conn.execute("SELECT key, value FROM config").fetchall()
            cfg = {r["key"]: r["value"] for r in cfg_rows}

            # Check if prices are configured!
            raw_shirt_price = cfg.get("shirt_price", "").strip()
            if not raw_shirt_price:
                conn.close()
                send_error_json(self, "Il prezzo ufficiale della maglietta non è ancora stato definito dall'amministrazione. Non è possibile inviare ordini in questo momento.", status=400)
                return

            try:
                shirt_price = float(raw_shirt_price)
                if shirt_price <= 0:
                    raise ValueError()
            except ValueError:
                conn.close()
                send_error_json(self, "Prezzo maglietta configurato non valido. Contatta l'amministrazione.", status=400)
                return

            # Check shipping costs
            shipping_cost = 0.0
            if delivery_method == "locker":
                raw_locker = cfg.get("shipping_locker", "").strip()
                if not raw_locker:
                    conn.close()
                    send_error_json(self, "Il costo di spedizione per Locker non è ancora stato configurato dall'amministrazione.", status=400)
                    return
                shipping_cost = float(raw_locker)
            elif delivery_method == "home":
                raw_home = cfg.get("shipping_home", "").strip()
                if not raw_home:
                    conn.close()
                    send_error_json(self, "Il costo di spedizione a domicilio non è ancora stato configurato dall'amministrazione.", status=400)
                    return
                shipping_cost = float(raw_home)
            elif delivery_method == "hand":
                raw_hand = cfg.get("shipping_hand", "0.0").strip()
                shipping_cost = float(raw_hand) if raw_hand else 0.0

            # Check variant availability
            variant = conn.execute("""
                SELECT * FROM variants
                WHERE color = ? AND size = ?
            """, (color, size)).fetchone()

            if not variant:
                conn.close()
                send_error_json(self, f"Variante T-shirt {color} taglia {size} non trovata.")
                return

            if not variant["is_available"]:
                conn.close()
                send_error_json(self, f"Ci dispiace, la taglia {size} per la T-shirt {variant['color_name']} è attualmente esaurita.")
                return

            # Calculate Subtotal
            subtotal = round(shirt_price * quantity, 2)

            # Check and apply discount code
            discount_code_input = (data.get("discount_code") or "").strip().upper()
            discount_amount = 0.0
            applied_code = None

            if discount_code_input:
                disc = conn.execute("""
                    SELECT * FROM discount_codes WHERE UPPER(code) = ?
                """, (discount_code_input,)).fetchone()

                if not disc or not disc["is_active"]:
                    conn.close()
                    send_error_json(self, f"Il codice sconto '{discount_code_input}' non è valido o è scaduto.")
                    return

                if disc["max_uses"] is not None and disc["usage_count"] >= disc["max_uses"]:
                    conn.close()
                    send_error_json(self, f"Il codice sconto '{discount_code_input}' ha raggiunto il limite massimo.")
                    return

                applied_code = disc["code"]
                if disc["discount_type"] == "percentage":
                    discount_amount = round(subtotal * (float(disc["discount_value"]) / 100.0), 2)
                else:
                    discount_amount = round(float(disc["discount_value"]), 2)

                # Cannot discount more than subtotal
                discount_amount = min(subtotal, discount_amount)

            # Total calculation
            total_amount = max(0.0, round(subtotal + shipping_cost - discount_amount, 2))

            # Bank coordinates
            bank_holder = cfg.get("bank_holder", "")
            bank_iban = cfg.get("bank_iban", "")
            bank_name = cfg.get("bank_name", "")

            # Generate Unique Order Number
            now_utc = datetime.now(timezone.utc)
            year_short = now_utc.strftime("%y")
            rand_suffix = secrets.randbelow(9000) + 1000  # 4 digits
            order_number = f"TVL-{year_short}-{rand_suffix}"

            # Ensure order number is unique
            while conn.execute("SELECT id FROM orders WHERE order_number = ?", (order_number,)).fetchone():
                rand_suffix = secrets.randbelow(9000) + 1000
                order_number = f"TVL-{year_short}-{rand_suffix}"

            # Generate secret view token
            order_token = secrets.token_urlsafe(24)

            # Generate Wire Causale format specified in prompt:
            # TAVOLARA WEAR - NOME COGNOME - NUMERO ORDINE
            clean_name = f"{first_name.upper()} {last_name.upper()}"
            wire_causale = f"TAVOLARA WEAR - {clean_name} - {order_number}"

            client_ip = self.client_address[0] if self.client_address else "127.0.0.1"
            now_iso = now_utc.isoformat()

            # Insert into database with transaction
            try:
                with conn:
                    cur = conn.execute("""
                        INSERT INTO orders (
                            order_number, order_token, customer_first_name, customer_last_name,
                            customer_email, customer_phone, delivery_method, locker_name,
                            delivery_address, delivery_zip, delivery_city, delivery_province,
                            delivery_notes, hand_location, hand_preferences, shirt_price,
                            shipping_cost, discount_code, discount_amount, total_amount,
                            payment_method, wire_causale, bank_holder, bank_iban, bank_name,
                            status, privacy_accepted, privacy_timestamp, client_ip,
                            created_at, updated_at
                        ) VALUES (
                            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                            'bonifico', ?, ?, ?, ?, 'Ordine ricevuto', 1, ?, ?, ?, ?
                        )
                    """, (
                        order_number, order_token, first_name, last_name, email, phone,
                        delivery_method, locker_name, delivery_address, delivery_zip,
                        delivery_city, delivery_province, delivery_notes, hand_location,
                        hand_preferences, shirt_price, shipping_cost, applied_code,
                        discount_amount, total_amount, wire_causale, bank_holder,
                        bank_iban, bank_name, now_iso, client_ip, now_iso, now_iso
                    ))
                    order_id = cur.lastrowid

                    # Insert order item
                    conn.execute("""
                        INSERT INTO order_items (
                            order_id, product_name, color, color_name, size,
                            quantity, unit_price, total_price
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        order_id, "T-shirt Tavolara Wear", color, variant["color_name"],
                        size, quantity, shirt_price, subtotal
                    ))

                    # Increment discount usage count if used
                    if applied_code:
                        conn.execute("""
                            UPDATE discount_codes
                            SET usage_count = usage_count + 1, updated_at = ?
                            WHERE code = ?
                        """, (now_iso, applied_code))

                    # Automatically create matching income row (Entrata)
                    conn.execute("""
                        INSERT INTO incomes (
                            description, amount, date, payment_method, order_reference, order_id, status, notes, created_at, updated_at
                        ) VALUES (?, ?, ?, 'Bonifico bancario', ?, ?, 'In attesa', ?, ?, ?)
                    """, (
                        f"Ordine #{order_number} — {first_name} {last_name}",
                        total_amount,
                        now_iso[:10],
                        order_number,
                        order_id,
                        f"Ordine online automatico. Consegna: {delivery_method}",
                        now_iso,
                        now_iso
                    ))

            except Exception as e:
                conn.close()
                send_error_json(self, f"Errore interno durante il salvataggio dell'ordine: {str(e)}", status=500)
                return

            conn.close()

            # Reverse Sync: Append new web order to Excel file
            try:
                excel_sync.append_order_to_excel({
                    "order_number": order_number,
                    "date": now_iso[:10],
                    "cliente": f"{first_name} {last_name}",
                    "phone": phone,
                    "color": variant["color_name"],
                    "size": size,
                    "qty": quantity,
                    "price": shirt_price,
                    "shipping_charged": shipping_cost,
                    "address": delivery_address or locker_name or hand_location,
                    "zip": delivery_zip,
                    "city": delivery_city,
                    "province": delivery_province,
                    "delivery_type": delivery_method,
                    "status": "Ordine ricevuto",
                    "is_paid": False,
                    "notes": f"Web order #{order_number}. {delivery_notes}".strip()
                })
            except Exception as ex_err:
                print(f"[Reverse Sync] Warning adding order to Excel: {ex_err}")

            # Success response
            response_payload = {
                "success": True,
                "order_number": order_number,
                "order_token": order_token,
                "created_at": now_iso,
                "customer": {
                    "first_name": first_name,
                    "last_name": last_name,
                    "email": email,
                    "phone": phone
                },
                "product": {
                    "name": "T-shirt Tavolara Wear",
                    "color": color,
                    "color_name": variant["color_name"],
                    "size": size,
                    "quantity": quantity,
                    "unit_price": shirt_price
                },
                "pricing": {
                    "subtotal": subtotal,
                    "shipping_cost": shipping_cost,
                    "discount_code": applied_code,
                    "discount_amount": discount_amount,
                    "total_amount": total_amount
                },
                "delivery": {
                    "method": delivery_method,
                    "locker_name": locker_name,
                    "address": delivery_address,
                    "zip": delivery_zip,
                    "city": delivery_city,
                    "province": delivery_province,
                    "notes": delivery_notes,
                    "hand_location": hand_location,
                    "hand_preferences": hand_preferences
                },
                "bank": {
                    "holder": bank_holder,
                    "iban": bank_iban,
                    "name": bank_name,
                    "causale": wire_causale,
                    "notes": cfg.get("bank_notes", "")
                }
            }
            send_json(self, response_payload, status=201)
            return

        # -----------------------------
        # ADMIN: Authentication & Actions
        # -----------------------------
        if path == "/api/admin/login":
            data = read_json_body(self)
            password = data.get("password", "")
            conn = get_db()
            row = conn.execute("SELECT value FROM config WHERE key = 'admin_password_hash'").fetchone()
            conn.close()

            admin_env_pass = os.environ.get("ADMIN_PASSWORD", "tavolara2026")
            is_valid = (password == admin_env_pass) or (row and hash_password(password) == row["value"])
            if not is_valid:
                send_error_json(self, "Password errata. Riprova.", status=401)
                return

            # Create permanent stateless token
            token = generate_admin_token()
            exp = (datetime.now(timezone.utc) + timedelta(days=3650)).isoformat()
            now_iso = datetime.now(timezone.utc).isoformat()

            try:
                conn = get_db()
                with conn:
                    conn.execute("""
                        INSERT OR REPLACE INTO admin_sessions (token, created_at, expires_at)
                        VALUES (?, ?, ?)
                    """, (token, now_iso, exp))
                conn.close()
            except Exception:
                pass

            # Set HTTP-only Cookie with 10 years Max-Age (permanent session)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Set-Cookie", f"tavolara_admin_session={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age=315360000")
            body = json.dumps({"authenticated": True, "token": token}).encode("utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if path == "/api/admin/logout":
            token = get_auth_token(self)
            if token:
                conn = get_db()
                with conn:
                    conn.execute("DELETE FROM admin_sessions WHERE token = ?", (token,))
                conn.close()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Set-Cookie", "tavolara_admin_session=; Path=/; Expires=Thu, 01 Jan 1970 00:00:00 GMT")
            body = json.dumps({"authenticated": False}).encode("utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        # ADMIN: Update Config
        if path == "/api/admin/config":
            if not is_admin_authenticated(self):
                send_error_json(self, "Non autorizzato.", status=401)
                return
            data = read_json_body(self)
            now_iso = datetime.now(timezone.utc).isoformat()
            allowed_keys = [
                "shirt_price", "shipping_locker", "shipping_home", "shipping_hand",
                "bank_holder", "bank_iban", "bank_name", "bank_notes",
                "brand_instagram", "brand_site", "brand_email", "brand_phone"
            ]
            conn = get_db()
            with conn:
                for k in allowed_keys:
                    if k in data:
                        val = str(data[k]).strip()
                        conn.execute("""
                            INSERT INTO config (key, value, updated_at)
                            VALUES (?, ?, ?)
                            ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
                        """, (k, val, now_iso))
            conn.close()
            send_json(self, {"success": True, "message": "Configurazione aggiornata con successo."})
            return

        # ADMIN: Create Discount Code
        if path == "/api/admin/discounts":
            if not is_admin_authenticated(self):
                send_error_json(self, "Non autorizzato.", status=401)
                return
            data = read_json_body(self)
            code = (data.get("code") or "").strip().upper()
            val = float(data.get("discount_value", 5.0))
            dtype = data.get("discount_type", "fixed")
            is_active = 1 if data.get("is_active", True) else 0
            max_uses = int(data["max_uses"]) if data.get("max_uses") else None
            now_iso = datetime.now(timezone.utc).isoformat()

            if not code:
                send_error_json(self, "Codice sconto obbligatorio.")
                return

            conn = get_db()
            try:
                with conn:
                    conn.execute("""
                        INSERT INTO discount_codes (code, discount_type, discount_value, is_active, usage_count, max_uses, updated_at)
                        VALUES (?, ?, ?, ?, 0, ?, ?)
                    """, (code, dtype, val, is_active, max_uses, now_iso))
            except sqlite3.IntegrityError:
                conn.close()
                send_error_json(self, f"Il codice sconto '{code}' esiste già.")
                return
            conn.close()
            send_json(self, {"success": True, "message": "Codice sconto creato."})
            return

        # ADMIN: Change Password
        if path == "/api/admin/change-password":
            if not is_admin_authenticated(self):
                send_error_json(self, "Non autorizzato.", status=401)
                return
            data = read_json_body(self)
            new_pwd = (data.get("new_password") or "").strip()
            if len(new_pwd) < 6:
                send_error_json(self, "La nuova password deve contenere almeno 6 caratteri.")
                return
            new_hash = hash_password(new_pwd)
            now_iso = datetime.now(timezone.utc).isoformat()
            conn = get_db()
            with conn:
                conn.execute("""
                    UPDATE config SET value = ?, updated_at = ? WHERE key = 'admin_password_hash'
                """, (new_hash, now_iso))
            conn.close()
            send_json(self, {"success": True, "message": "Password amministratore modificata con successo."})
            return

        # -----------------------------
        # ADMIN: Incomes CRUD
        # -----------------------------
        if path == "/api/admin/incomes":
            if not is_admin_authenticated(self):
                send_error_json(self, "Non autorizzato.", status=401)
                return
            data = read_json_body(self)
            try:
                income = financial.create_income(data)
                send_json(self, {"success": True, "income": income}, status=201)
            except Exception as e:
                send_error_json(self, str(e), status=400)
            return

        if path == "/api/admin/incomes/sync-all":
            if not is_admin_authenticated(self):
                send_error_json(self, "Non autorizzato.", status=401)
                return
            data = read_json_body(self) or {}
            target_status = data.get("status", "Incassata")
            try:
                res = financial.sync_all_orders_to_incomes(target_status=target_status)
                send_json(self, res)
            except Exception as e:
                send_error_json(self, str(e), status=400)
            return

        m_inc_sync = re.match(r"^/api/admin/incomes/sync-order/(\d+)$", path)
        if m_inc_sync:
            if not is_admin_authenticated(self):
                send_error_json(self, "Non autorizzato.", status=401)
                return
            order_id = int(m_inc_sync.group(1))
            data = read_json_body(self) or {}
            target_status = data.get("status", "Incassata")
            try:
                income = financial.sync_income_from_order(order_id, target_status=target_status)
                send_json(self, {"success": True, "income": income}, status=201)
            except Exception as e:
                send_error_json(self, str(e), status=400)
            return

        m_inc_edit = re.match(r"^/api/admin/incomes/(\d+)$", path)
        if m_inc_edit:
            if not is_admin_authenticated(self):
                send_error_json(self, "Non autorizzato.", status=401)
                return
            income_id = int(m_inc_edit.group(1))
            data = read_json_body(self)
            try:
                income = financial.update_income(income_id, data)
                send_json(self, {"success": True, "income": income})
            except Exception as e:
                send_error_json(self, str(e), status=400)
            return

        m_inc_del = re.match(r"^/api/admin/incomes/(\d+)/delete$", path)
        if m_inc_del:
            if not is_admin_authenticated(self):
                send_error_json(self, "Non autorizzato.", status=401)
                return
            income_id = int(m_inc_del.group(1))
            try:
                financial.delete_income(income_id)
                send_json(self, {"success": True, "message": f"Entrata #{income_id} eliminata."})
            except Exception as e:
                send_error_json(self, str(e), status=400)
            return

        # -----------------------------
        # ADMIN: Expenses CRUD
        # -----------------------------
        if path == "/api/admin/expenses":
            if not is_admin_authenticated(self):
                send_error_json(self, "Non autorizzato.", status=401)
                return
            data = read_json_body(self)
            try:
                expense = financial.create_expense(data)
                send_json(self, {"success": True, "expense": expense}, status=201)
            except Exception as e:
                send_error_json(self, str(e), status=400)
            return

        m_exp_edit = re.match(r"^/api/admin/expenses/(\d+)$", path)
        if m_exp_edit:
            if not is_admin_authenticated(self):
                send_error_json(self, "Non autorizzato.", status=401)
                return
            expense_id = int(m_exp_edit.group(1))
            data = read_json_body(self)
            try:
                expense = financial.update_expense(expense_id, data)
                send_json(self, {"success": True, "expense": expense})
            except Exception as e:
                send_error_json(self, str(e), status=400)
            return

        m_exp_del = re.match(r"^/api/admin/expenses/(\d+)/delete$", path)
        if m_exp_del:
            if not is_admin_authenticated(self):
                send_error_json(self, "Non autorizzato.", status=401)
                return
            expense_id = int(m_exp_del.group(1))
            try:
                financial.delete_expense(expense_id)
                send_json(self, {"success": True, "message": f"Spesa #{expense_id} eliminata."})
            except Exception as e:
                send_error_json(self, str(e), status=400)
            return

        # -----------------------------
        # ADMIN: Excel Live Sync
        # -----------------------------
        if path == "/api/admin/excel/sync":
            if not is_admin_authenticated(self):
                send_error_json(self, "Non autorizzato.", status=401)
                return
            res = excel_sync.sync_excel_to_db(force=True)
            send_json(self, res)
            return

        if path == "/api/admin/excel/sync-google":
            if not is_admin_authenticated(self):
                send_error_json(self, "Non autorizzato.", status=401)
                return
            data = read_json_body(self) or {}
            url = (data.get("url") or "").strip()
            if not url:
                conn = get_db()
                row = conn.execute("SELECT value FROM config WHERE key = 'excel_google_drive_url'").fetchone()
                conn.close()
                if row and row["value"]:
                    url = row["value"]
                else:
                    send_error_json(self, "Nessun link Google Drive fornito.", status=400)
                    return
            res = excel_sync.sync_google_drive_to_db(url)
            if not res.get("success"):
                send_error_json(self, res.get("message", "Errore sincronizzazione Google Drive."), status=400)
                return
            send_json(self, res)
            return

        if path == "/api/admin/excel/sync-to-excel":
            if not is_admin_authenticated(self):
                send_error_json(self, "Non autorizzato.", status=401)
                return
            res = excel_sync.sync_db_to_excel()
            send_json(self, res)
            return

        if path == "/api/admin/excel/sync-bidirectional":
            if not is_admin_authenticated(self):
                send_error_json(self, "Non autorizzato.", status=401)
                return
            res = excel_sync.sync_bidirectional()
            send_json(self, res)
            return

        if path == "/api/admin/excel/upload":
            if not is_admin_authenticated(self):
                send_error_json(self, "Non autorizzato.", status=401)
                return
            content_len = int(self.headers.get("Content-Length", 0))
            if content_len == 0:
                send_error_json(self, "Nessun dato file ricevuto.", status=400)
                return
            raw_data = self.rfile.read(content_len)
            
            target_path = excel_sync.get_live_excel_path()
            with open(target_path, "wb") as f:
                f.write(raw_data)
            
            res = excel_sync.sync_excel_to_db(excel_path=target_path, force=True)
            send_json(self, res)
            return

        # Default fallback
        send_error_json(self, "Endpoint non trovato.", status=404)

    def do_PUT(self):
        self.do_POST()

    def do_DELETE(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if not is_admin_authenticated(self):
            send_error_json(self, "Non autorizzato.", status=401)
            return

        m_inc = re.match(r"^/api/admin/incomes/(\d+)$", path)
        if m_inc:
            income_id = int(m_inc.group(1))
            try:
                financial.delete_income(income_id)
                send_json(self, {"success": True, "message": f"Entrata #{income_id} eliminata."})
            except Exception as e:
                send_error_json(self, str(e), status=404)
            return

        m_exp = re.match(r"^/api/admin/expenses/(\d+)$", path)
        if m_exp:
            expense_id = int(m_exp.group(1))
            try:
                financial.delete_expense(expense_id)
                send_json(self, {"success": True, "message": f"Spesa #{expense_id} eliminata."})
            except Exception as e:
                send_error_json(self, str(e), status=404)
            return

        send_error_json(self, "Endpoint non trovato.", status=404)

    def do_PATCH(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if not is_admin_authenticated(self):
            send_error_json(self, "Non autorizzato.", status=401)
            return

        # PATCH /api/admin/orders/{order_id}/status
        m_order = re.match(r"^/api/admin/orders/(\d+)/status$", path)
        if m_order:
            order_id = int(m_order.group(1))
            data = read_json_body(self)
            new_status = (data.get("status") or "").strip()

            valid_statuses = [
                "Ordine ricevuto",
                "Ordine confermato",
                "Ordine da pagare",
                "Ordine pagato",
                "Nuovo ordine",
                "In attesa di pagamento",
                "Pagamento verificato",
                "In preparazione",
                "Spedito / Consegnato",
                "Annullato"
            ]
            if new_status not in valid_statuses:
                send_error_json(self, f"Stato non valido. Scegli tra: {', '.join(valid_statuses)}.")
                return

            now_iso = datetime.now(timezone.utc).isoformat()
            conn = get_db()
            with conn:
                cur = conn.execute("""
                    UPDATE orders
                    SET status = ?, updated_at = ?
                    WHERE id = ?
                """, (new_status, now_iso, order_id))
                
                # Also update corresponding income status if exists
                inc_status = "Incassata" if new_status in ["Ordine pagato", "Pagamento verificato", "In preparazione", "Spedito / Consegnato"] else ("Confermata" if new_status == "Ordine confermato" else "In attesa")
                conn.execute("""
                    UPDATE incomes
                    SET status = ?, updated_at = ?
                    WHERE order_id = ?
                """, (inc_status, now_iso, order_id))
            conn.close()

            if cur.rowcount == 0:
                send_error_json(self, "Ordine non trovato.", status=404)
                return

            # Reverse Sync: Update corresponding order status in live Excel file
            try:
                excel_sync.update_excel_order_status(order_id, new_status)
            except Exception as ex_err:
                print(f"[Reverse Sync] Warning updating order in Excel: {ex_err}")

            send_json(self, {"success": True, "message": f"Stato ordine #{order_id} aggiornato a '{new_status}'."})
            return

        # PATCH /api/admin/variants/{variant_id}
        m_var = re.match(r"^/api/admin/variants/(\d+)$", path)
        if m_var:
            variant_id = int(m_var.group(1))
            data = read_json_body(self)
            now_iso = datetime.now(timezone.utc).isoformat()
            conn = get_db()
            with conn:
                if "is_available" in data:
                    is_avail = 1 if data["is_available"] else 0
                    conn.execute("""
                        UPDATE variants SET is_available = ?, updated_at = ? WHERE id = ?
                    """, (is_avail, now_iso, variant_id))
                if "stock_qty" in data:
                    stock_qty = int(data["stock_qty"])
                    conn.execute("""
                        UPDATE variants SET stock_qty = ?, updated_at = ? WHERE id = ?
                    """, (stock_qty, now_iso, variant_id))
            conn.close()
            send_json(self, {"success": True, "message": "Disponibilità variante aggiornata."})
            return

        # PATCH /api/admin/discounts/{discount_id}
        m_disc = re.match(r"^/api/admin/discounts/(\d+)$", path)
        if m_disc:
            discount_id = int(m_disc.group(1))
            data = read_json_body(self)
            now_iso = datetime.now(timezone.utc).isoformat()
            conn = get_db()
            with conn:
                if "is_active" in data:
                    is_act = 1 if data["is_active"] else 0
                    conn.execute("UPDATE discount_codes SET is_active = ?, updated_at = ? WHERE id = ?", (is_act, now_iso, discount_id))
                if "discount_value" in data:
                    val = float(data["discount_value"])
                    conn.execute("UPDATE discount_codes SET discount_value = ?, updated_at = ? WHERE id = ?", (val, now_iso, discount_id))
            conn.close()
            send_json(self, {"success": True, "message": "Codice sconto aggiornato."})
            return

        send_error_json(self, "Endpoint non trovato.", status=404)

    def serve_file(self, filepath, content_type):
        if not os.path.exists(filepath):
            self.send_error(404, "File Not Found")
            return
        with open(filepath, "rb") as f:
            content = f.read()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True

def start_excel_auto_watcher():
    """Background watcher that automatically detects edits to Excel orders file and syncs to Supabase."""
    import threading
    import time
    def loop():
        time.sleep(2)
        while True:
            try:
                excel_sync.check_auto_sync()
            except Exception as e:
                pass
            time.sleep(5)
    t = threading.Thread(target=loop, daemon=True, name="ExcelAutoWatcher")
    t.start()
    print("[Server] Excel Auto Watcher avviato (controllo modifiche ogni 5s)")

def run_server(port=PORT):
    init_db()
    start_excel_auto_watcher()
    server = ThreadedHTTPServer(("0.0.0.0", port), TavolaraHandler)
    print(f"=====================================================")
    print(f"  TAVOLARA WEAR — ORDER SYSTEM RUNNING")
    print(f"  URL Pubblico Clienti: http://localhost:{port}/")
    print(f"  Dashboard Amministrativa: http://localhost:{port}/admin")
    print(f"=====================================================")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nArresto del server...")
        server.server_close()

if __name__ == "__main__":
    run_server()
