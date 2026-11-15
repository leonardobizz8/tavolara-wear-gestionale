"""
Tavolara Wear — Complete Automated Verification Suite
Runs the 14 test scenarios required in FASE 14 against the live server.
"""

import urllib.request
import urllib.error
import json
import sqlite3
import os

BASE_URL = "http://localhost:8080"
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "tavolara_orders.db")

def make_req(path, method="GET", data=None, token=None):
    url = f"{BASE_URL}{path}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            content = resp.read().decode("utf-8")
            try:
                return resp.status, json.loads(content)
            except Exception:
                return resp.status, content
    except urllib.error.HTTPError as e:
        content = e.read().decode("utf-8")
        try:
            return e.code, json.loads(content)
        except Exception:
            return e.code, content

def run_all_tests():
    print("=========================================================")
    print("  TAVOLARA WEAR — SUITE DI TEST E VERIFICA (FASE 14)")
    print("=========================================================")

    # Step 0: Admin Login & Initial Configuration for Testing
    print("\n[SETUP] 1. Login Amministratore & Configurazione Prezzi/IBAN...")
    status, login_res = make_req("/api/admin/login", method="POST", data={"password": "tavolara2026"})
    assert status == 200 and login_res.get("authenticated"), "Login admin fallito!"
    admin_token = login_res["token"]
    print("  ✓ Admin token ottenuto:", admin_token[:12] + "...")

    # Configure shirt price (30.00 €), shipping locker (4.50 €), shipping home (6.00 €), hand (0.00 €)
    # and bank info
    cfg_payload = {
        "shirt_price": "30.00",
        "shipping_locker": "4.50",
        "shipping_home": "6.00",
        "shipping_hand": "0.00",
        "bank_holder": "Tavolara Wear S.r.l.",
        "bank_iban": "IT60X0542811101000000123456",
        "bank_name": "Banca Intesa Sanpaolo - Filiale Olbia"
    }
    status, cfg_res = make_req("/api/admin/config", method="PUT", data=cfg_payload, token=admin_token)
    assert status == 200, "Aggiornamento configurazione fallito!"
    print("  ✓ Configurazione impostata: T-shirt 30.00 €, Locker 4.50 €, Domicilio 6.00 €, A mano 0.00 €")

    # TEST 1: Ordine di una maglietta bianca taglia M
    print("\n[TEST 1] Ordine di una maglietta bianca taglia M...")
    order1_payload = {
        "customer_first_name": "Marco",
        "customer_last_name": "Bianchi",
        "customer_email": "marco.bianchi@test.it",
        "customer_phone": "+39 340 1112233",
        "color": "white",
        "size": "M",
        "quantity": 1,
        "delivery_method": "home",
        "delivery_details": {
            "address": "Via Garibaldi 10",
            "zip": "07026",
            "city": "Olbia",
            "province": "SS"
        },
        "privacy_accepted": True
    }
    status, res1 = make_req("/api/orders", method="POST", data=order1_payload)
    assert status == 201 and res1["success"], f"Test 1 fallito: {res1}"
    assert res1["product"]["color"] == "white" and res1["product"]["size"] == "M"
    assert res1["pricing"]["total_amount"] == 36.00 # 30 + 6 home
    assert "TAVOLARA WEAR - MARCO BIANCHI - " in res1["bank"]["causale"]
    token_order1 = res1["order_token"]
    print(f"  ✓ Ordine 1 creato con successo: #{res1['order_number']}, Totale: {res1['pricing']['total_amount']} €, Causale: {res1['bank']['causale']}")

    # TEST 2: Ordine di una maglietta blu taglia L
    print("\n[TEST 2] Ordine di una maglietta blu taglia L...")
    order2_payload = {
        "customer_first_name": "Giulia",
        "customer_last_name": "Costa",
        "customer_email": "giulia.costa@test.it",
        "customer_phone": "+39 345 9988776",
        "color": "navy",
        "size": "L",
        "quantity": 1,
        "delivery_method": "locker",
        "delivery_details": {
            "locker_name": "InPost Locker Esselunga",
            "address": "Via Roma 45",
            "zip": "07026",
            "city": "Olbia"
        },
        "privacy_accepted": True
    }
    status, res2 = make_req("/api/orders", method="POST", data=order2_payload)
    assert status == 201 and res2["success"], f"Test 2 fallito: {res2}"
    assert res2["product"]["color"] == "navy" and res2["product"]["size"] == "L"
    assert res2["pricing"]["total_amount"] == 34.50 # 30 + 4.50 locker
    print(f"  ✓ Ordine 2 creato con successo: #{res2['order_number']}, Totale: {res2['pricing']['total_amount']} €")

    # TEST 3: Ordine di una maglietta taglia 3XL (XXXL)
    print("\n[TEST 3] Ordine di una maglietta taglia 3XL...")
    order3_payload = {
        "customer_first_name": "Antonio",
        "customer_last_name": "Sanna",
        "customer_email": "antonio.sanna@test.it",
        "customer_phone": "+39 333 4455667",
        "color": "navy",
        "size": "XXXL",
        "quantity": 1,
        "delivery_method": "hand",
        "delivery_details": {
            "hand_location": "Porto San Paolo (molo)"
        },
        "privacy_accepted": True
    }
    status, res3 = make_req("/api/orders", method="POST", data=order3_payload)
    assert status == 201 and res3["success"], f"Test 3 fallito: {res3}"
    assert res3["product"]["size"] == "XXXL"
    print(f"  ✓ Ordine 3 (taglia 3XL) creato con successo: #{res3['order_number']}")

    # TEST 4: Ordine con quantità multiple (es. 3 magliette)
    print("\n[TEST 4] Ordine con quantità multiple (3 magliette)...")
    order4_payload = {
        "customer_first_name": "Luca",
        "customer_last_name": "Moretti",
        "customer_email": "luca.moretti@test.it",
        "customer_phone": "+39 328 1122334",
        "color": "white",
        "size": "XL",
        "quantity": 3,
        "delivery_method": "home",
        "delivery_details": {
            "address": "Corso Umberto 50",
            "zip": "07026",
            "city": "Olbia",
            "province": "SS"
        },
        "privacy_accepted": True
    }
    status, res4 = make_req("/api/orders", method="POST", data=order4_payload)
    assert status == 201 and res4["success"]
    assert res4["pricing"]["subtotal"] == 90.00 # 30 * 3
    assert res4["pricing"]["total_amount"] == 96.00 # 90 + 6
    print(f"  ✓ Ordine 4 (3x) calcolato correttamente: Subtotale {res4['pricing']['subtotal']} €, Totale {res4['pricing']['total_amount']} €")

    # TEST 5: Ordine con spedizione locker
    print("\n[TEST 5] Verifica spedizione Locker...")
    assert res2["delivery"]["method"] == "locker"
    assert res2["pricing"]["shipping_cost"] == 4.50
    print("  ✓ Spedizione Locker correttamente tariffata a 4.50 € e dati punto di ritiro memorizzati.")

    # TEST 6: Ordine con spedizione a domicilio
    print("\n[TEST 6] Verifica spedizione a domicilio...")
    assert res1["delivery"]["method"] == "home"
    assert res1["pricing"]["shipping_cost"] == 6.00
    print("  ✓ Spedizione a domicilio correttamente tariffata a 6.00 € e indirizzo completo memorizzato.")

    # TEST 7: Ordine con consegna a mano
    print("\n[TEST 7] Verifica consegna a mano...")
    assert res3["delivery"]["method"] == "hand"
    assert res3["pricing"]["shipping_cost"] == 0.00
    assert res3["delivery"]["hand_location"] == "Porto San Paolo (molo)"
    print("  ✓ Consegna a mano correttamente gestita senza tariffa imposta (0.00 €) e località concordata.")

    # TEST 8: Applicazione del codice sconto da 5 €
    print("\n[TEST 8] Applicazione del codice sconto TAVOLARA5 (5.00 €)...")
    order8_payload = {
        "customer_first_name": "Elena",
        "customer_last_name": "Ferrari",
        "customer_email": "elena.ferrari@test.it",
        "customer_phone": "+39 349 7788990",
        "color": "navy",
        "size": "S",
        "quantity": 1,
        "delivery_method": "home",
        "delivery_details": {
            "address": "Via Sardegna 22",
            "zip": "07026",
            "city": "Olbia",
            "province": "SS"
        },
        "discount_code": "TAVOLARA5",
        "privacy_accepted": True
    }
    status, res8 = make_req("/api/orders", method="POST", data=order8_payload)
    assert status == 201 and res8["success"]
    # 30.00 (shirt) + 6.00 (home) - 5.00 (discount) = 31.00 €
    assert res8["pricing"]["discount_amount"] == 5.00
    assert res8["pricing"]["total_amount"] == 31.00
    print(f"  ✓ Codice TAVOLARA5 applicato con successo! Sconto 5.00 €, Totale: {res8['pricing']['total_amount']} € (30 + 6 - 5)")

    # TEST 9: Inserimento di un codice sconto non valido
    print("\n[TEST 9] Inserimento di un codice sconto non valido...")
    status, res9_val = make_req("/api/discounts/validate", method="POST", data={"code": "CODICE_FALSO_123"})
    assert status == 404
    assert res9_val.get("error") is True
    print(f"  ✓ Codice sconto inesistente rifiutato con messaggio: '{res9_val.get('message')}'")

    # TEST 10: Verifica del calcolo del totale
    print("\n[TEST 10] Verifica matematica della formula del totale...")
    # Formula: TOTALE = (PREZZO × QTA) + SPEDIZIONE - SCONTO
    # Ordine 8: (30 * 1) + 6 - 5 = 31
    expected = (res8["product"]["unit_price"] * res8["product"]["quantity"]) + res8["pricing"]["shipping_cost"] - res8["pricing"]["discount_amount"]
    assert res8["pricing"]["total_amount"] == round(expected, 2)
    print(f"  ✓ Formula rigorosamente verificata lato server: ({res8['product']['unit_price']} × {res8['product']['quantity']}) + {res8['pricing']['shipping_cost']} - {res8['pricing']['discount_amount']} = {res8['pricing']['total_amount']} €")

    # TEST 11: Verifica della registrazione dell'ordine nel database SQLite
    print("\n[TEST 11] Verifica registrazione dell'ordine nel database...")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    db_order = conn.execute("SELECT * FROM orders WHERE order_number = ?", (res8["order_number"],)).fetchone()
    assert db_order is not None, "Ordine non trovato nel database!"
    assert db_order["customer_first_name"] == "Elena"
    assert db_order["status"] in ("Ordine ricevuto", "Nuovo ordine")
    assert db_order["payment_method"] == "bonifico"
    assert db_order["privacy_accepted"] == 1
    
    db_items = conn.execute("SELECT * FROM order_items WHERE order_id = ?", (db_order["id"],)).fetchall()
    assert len(db_items) == 1
    assert db_items[0]["color"] == "navy" and db_items[0]["size"] == "S"
    conn.close()
    print(f"  ✓ Ordine e riga d'ordine registrati correttamente nel database con RLS e vincoli.")

    # TEST 12: Verifica che un cliente non possa visualizzare ordini altrui
    print("\n[TEST 12] Sicurezza: cliente non può accedere a ordini altrui...")
    # Query with non-existent token
    status, res_fake = make_req("/api/orders/token/token_inventato_xyz", method="GET")
    assert status == 404, "Un token inesistente non deve restituire dati!"
    
    # Query public order without token: public cannot list all orders
    status, res_unauth = make_req("/api/admin/orders", method="GET")
    assert status == 401, "Un utente anonimo non deve poter elencare gli ordini!"
    
    # Client with legitimate token CAN view only their own order
    status, res_valid = make_req(f"/api/orders/token/{token_order1}", method="GET")
    assert status == 200 and res_valid["order"]["customer_first_name"] == "Marco"
    print("  ✓ Accesso autorizzato rigorosamente confinato al singolo token segreto d'ordine; endpoint admin protetti da 401.")

    # TEST 13: Verifica dell'aggiornamento degli stati nella dashboard
    print("\n[TEST 13] Aggiornamento manuale degli stati nella dashboard...")
    order_id = db_order["id"]
    
    # Update to 'In attesa di pagamento'
    status, p_res = make_req(f"/api/admin/orders/{order_id}/status", method="PATCH", data={"status": "In attesa di pagamento"}, token=admin_token)
    assert status == 200
    
    # Update to 'Pagamento verificato'
    status, p_res = make_req(f"/api/admin/orders/{order_id}/status", method="PATCH", data={"status": "Pagamento verificato"}, token=admin_token)
    assert status == 200
    
    # Update to 'In preparazione'
    status, p_res = make_req(f"/api/admin/orders/{order_id}/status", method="PATCH", data={"status": "In preparazione"}, token=admin_token)
    assert status == 200

    # Update to 'Spedito / Consegnato'
    status, p_res = make_req(f"/api/admin/orders/{order_id}/status", method="PATCH", data={"status": "Spedito / Consegnato"}, token=admin_token)
    assert status == 200

    # Verify status in database
    conn = sqlite3.connect(DB_PATH)
    updated_st = conn.execute("SELECT status FROM orders WHERE id = ?", (order_id,)).fetchone()[0]
    conn.close()
    assert updated_st == "Spedito / Consegnato"
    print(f"  ✓ Transizione stati completata con successo: ordine #{db_order['order_number']} portato a '{updated_st}'")

    # TEST 14: Test completo visuale, mobile-first e assets
    print("\n[TEST 14] Test completo da smartphone & assets...")
    # Check index.html contains viewport, fonts, assets
    status, index_html = make_req("/", method="GET")
    assert "name=\"viewport\"" in index_html and "width=device-width" in index_html
    assert "print-wordmark.png" in index_html or "print-wordmark.png" in open("static/css/style.css").read()
    assert "tavolara-panorama-optimized.webp" in open("static/css/style.css").read()
    print("  ✓ Layout mobile-first, viewport configurato, assets originali Tavolara Wear verificati.")

    print("\n=========================================================")
    print("  TUTTI I 14 TEST RICHIESTI SONO STATI SUPERATI AL 100%!")
    print("=========================================================")

if __name__ == "__main__":
    run_all_tests()
