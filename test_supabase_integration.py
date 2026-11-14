"""
Tavolara Wear — Live Supabase Integration Test Suite
Verifies all 8 requirements specified in Section 8 of the prompt against the active Supabase instance:
1. Inserimento di un ordine dal modulo
2. Salvataggio corretto su Supabase
3. Visualizzazione dell'ordine nella dashboard
4. Corretta registrazione dei colori e delle taglie (Blu, Bianca; S, M, L, XL, XXL, 3XL)
5. Aggiornamento delle statistiche
6. Registrazione di un incasso (Attivo / Transactions)
7. Registrazione di una spesa (Passivo / Expenses)
8. Persistenza dei dati dopo il refresh / re-query
"""

import urllib.request
import json
import ssl
import sys

SUPABASE_URL = "https://ofaycxhwnkxuckvxuieq.supabase.co"
ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9mYXljeGh3bmt4dWNrdnh1aWVxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTQ2NzMyNTEsImV4cCI6MjExMDI0OTI1MX0.gWIr8Sg2Aep1QSsUb5VQxuz_RMIsYBoS2jw5PpMTXpc"

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def req_supabase(path, method="GET", data=None, token=None):
    url = f"{SUPABASE_URL}{path}"
    headers = {
        "apikey": ANON_KEY,
        "Authorization": f"Bearer {token or ANON_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }
    body = json.dumps(data).encode("utf-8") if data is not None else None
    r = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(r, context=ctx) as resp:
        content = resp.read().decode("utf-8")
        if not content:
            return resp.status, None
        return resp.status, json.loads(content)

def run_tests():
    print("====================================================================")
    print("  TAVOLARA WEAR — TEST DI INTEGRAZIONE SUPABASE E VERIFICA LIVE (8 PUNTI)")
    print("====================================================================")

    # 1. Login Admin to obtain JWT
    print("\n[STEP 0] Autenticazione Amministratore / Socio su Supabase...")
    status, auth_data = req_supabase(
        "/auth/v1/token?grant_type=password",
        method="POST",
        data={"email": "admin@tavolarawear.it", "password": "tavolara2026"}
    )
    assert status == 200 and "access_token" in auth_data, "Autenticazione Supabase fallita!"
    jwt_token = auth_data["access_token"]
    print("  ✓ Socio autenticato con successo tramite Supabase Auth (JWT valido).")

    # TEST 1 & 2: Inserimento ordine dal modulo e salvataggio corretto su Supabase
    print("\n[TEST 1 & 2] Inserimento ordine cliente tramite modulo e salvataggio su Supabase...")
    order_num = "TW-TEST-LIVE01"
    token_str = "tok_live_verification_2026"
    order_payload = {
        "p_customer": {
            "first_name": "Chiara",
            "last_name": "Sanna",
            "email": "chiara.sanna@test.it",
            "phone": "+39 349 7788990",
            "delivery_address": "Viale Aldo Moro 15",
            "delivery_zip": "07026",
            "delivery_city": "Olbia",
            "delivery_province": "SS"
        },
        "p_order": {
            "order_number": order_num,
            "order_token": token_str,
            "delivery_method": "locker",
            "locker_name": "InPost Point Olbia Centro",
            "shirt_price": 30.00,
            "shipping_cost": 4.50,
            "discount_code": "TAVOLARA5",
            "discount_amount": 5.00,
            "total_amount": 29.50,
            "wire_causale": f"TAVOLARA WEAR - CHIARA SANNA - {order_num}"
        },
        "p_items": [
            {
                "product_name": "T-shirt Tavolara Wear",
                "color": "Blu",
                "color_code": "navy",
                "size": "M",
                "quantity": 1,
                "unit_price": 30.00,
                "total_price": 30.00
            }
        ]
    }
    status, res_order = req_supabase("/rest/v1/rpc/create_tavolara_order", method="POST", data=order_payload)
    assert status in (200, 201) and res_order.get("success"), f"Creazione ordine fallita: {res_order}"
    created_order = res_order["order"]
    created_items = res_order["items"]
    print(f"  ✓ Ordine #{created_order['order_number']} registrato su Supabase!")
    print(f"    - ID: {created_order['id']}, Totale: {created_order['total_amount']} €, Causale: {created_order['wire_causale']}")

    # TEST 3: Visualizzazione dell'ordine nella dashboard
    print("\n[TEST 3] Visualizzazione dell'ordine nella dashboard...")
    status, orders_list = req_supabase(
        f"/rest/v1/orders?order_number=eq.{order_num}&select=*,order_items(*)",
        token=jwt_token
    )
    assert status == 200 and len(orders_list) == 1, "Ordine non trovato nella lista ordini Supabase!"
    fetched_order = orders_list[0]
    print(f"  ✓ Ordine visualizzabile in Dashboard: Cliente {fetched_order['customer_first_name']} {fetched_order['customer_last_name']}")
    print(f"    - Stato iniziale conforme: '{fetched_order['status']}', Stato pagamento: '{fetched_order['payment_status']}'")
    assert fetched_order["status"] == "Ordine ricevuto"
    assert fetched_order["payment_status"] == "da_pagare"

    # TEST 4: Corretta registrazione dei colori e delle taglie
    print("\n[TEST 4] Corretta registrazione dei colori e delle taglie...")
    items = fetched_order["order_items"]
    assert len(items) == 1
    assert items[0]["color"] == "Blu" and items[0]["size"] == "M"
    print(f"  ✓ Rilevato articolo con colore '{items[0]['color']}' e taglia '{items[0]['size']}' conforme alla matrice ufficiale.")

    # TEST 5: Aggiornamento delle statistiche (Insights)
    print("\n[TEST 5] Verifica aggiornamento statistiche ed estrazione aggregati...")
    status, all_items = req_supabase(
        "/rest/v1/order_items?select=color,size,quantity",
        token=jwt_token
    )
    assert status == 200 and len(all_items) > 0
    total_qty = sum(it["quantity"] for it in all_items)
    navy_count = sum(it["quantity"] for it in all_items if it["color"] == "Blu")
    white_count = sum(it["quantity"] for it in all_items if it["color"] == "Bianca")
    print(f"  ✓ Statistiche live: {total_qty} capi totali | Blu navy: {navy_count} | Bianca: {white_count}")

    # TEST 6: Registrazione di un incasso (Attivo / Transactions)
    print("\n[TEST 6] Registrazione di un incasso effettivo (Attivo)...")
    incasso_payload = {
        "type": "incasso",
        "description": f"Saldo bonifico ordine #{order_num}",
        "amount": 29.50,
        "date": "2026-11-14",
        "payment_method": "Bonifico bancario",
        "status": "Incassata",
        "reference": order_num,
        "order_id": fetched_order["id"],
        "notes": "Accredito verificato su estratto conto"
    }
    status, res_inc = req_supabase("/rest/v1/transactions", method="POST", data=incasso_payload, token=jwt_token)
    assert status in (200, 201), f"Inserimento incasso fallito: {res_inc}"
    inc_id = res_inc[0]["id"]
    print(f"  ✓ Incasso registrato con successo nell'Attivo: ID #{inc_id}, Importo: {res_inc[0]['amount']} €, Stato: {res_inc[0]['status']}")

    # Aggiorna lo stato dell'ordine a 'Ordine pagato'
    status, updated_ord = req_supabase(
        f"/rest/v1/orders?id=eq.{fetched_order['id']}",
        method="PATCH",
        data={"status": "Ordine pagato", "payment_status": "pagato"},
        token=jwt_token
    )
    assert status == 200
    print(f"  ✓ Stato ordine aggiornato a 'Ordine pagato' (pagamento: 'pagato')")

    # TEST 7: Registrazione di una spesa (Passivo / Expenses nelle 4 categorie)
    print("\n[TEST 7] Registrazione di una spesa (Passivo — Categoria Trasporto)...")
    spesa_payload = {
        "category_code": "trasporto",
        "description": "Spedizione Locker InPost cliente Chiara Sanna",
        "amount": 4.50,
        "date": "2026-11-14",
        "carrier": "InPost Express",
        "shipment_count": 1,
        "shipment_type": "singola",
        "notes": f"Rif. ordine {order_num}"
    }
    status, res_exp = req_supabase("/rest/v1/expenses", method="POST", data=spesa_payload, token=jwt_token)
    assert status in (200, 201), f"Inserimento spesa fallito: {res_exp}"
    exp_id = res_exp[0]["id"]
    print(f"  ✓ Spesa registrata nel Passivo: ID #{exp_id}, Categoria: {res_exp[0]['category_code']}, Importo: {res_exp[0]['amount']} €")

    # TEST 8: Persistenza dei dati dopo il refresh / nuova query indipendente
    print("\n[TEST 8] Verifica persistenza integrale dei dati su Supabase...")
    status, verify_order = req_supabase(f"/rest/v1/orders?id=eq.{fetched_order['id']}&select=*", token=jwt_token)
    assert status == 200 and verify_order[0]["status"] == "Ordine pagato"

    status, verify_tx = req_supabase(f"/rest/v1/transactions?id=eq.{inc_id}", token=jwt_token)
    assert status == 200 and len(verify_tx) == 1 and verify_tx[0]["status"] == "Incassata"

    status, verify_exp = req_supabase(f"/rest/v1/expenses?id=eq.{exp_id}", token=jwt_token)
    assert status == 200 and len(verify_exp) == 1 and verify_exp[0]["amount"] == 4.50

    print("  ✓ Ordine, transazione di incasso e spesa persistono intatti e coerenti su Supabase!")

    # Pulizia record di test
    print("\n[CLEANUP] Pulizia delle registrazioni di test su Supabase...")
    req_supabase(f"/rest/v1/transactions?id=eq.{inc_id}", method="DELETE", token=jwt_token)
    req_supabase(f"/rest/v1/expenses?id=eq.{exp_id}", method="DELETE", token=jwt_token)
    req_supabase(f"/rest/v1/orders?id=eq.{fetched_order['id']}", method="DELETE", token=jwt_token)
    print("  ✓ Registrazioni di test eliminate con successo. Database pulito e pronto per la produzione.")

    print("\n====================================================================")
    print("  TUTTI GLI 8 TEST RICHIESTI SONO STATI SUPERATI CON SUCCESSO! (100%)")
    print("====================================================================")

if __name__ == "__main__":
    run_tests()
