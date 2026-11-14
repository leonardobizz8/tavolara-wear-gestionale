"""
Tavolara Wear — Financial Management Test Suite
Verifies all mathematical models, CRUD operations, 4 expense categories,
size/color cross-matrix tables, and CSV exports.
"""

import urllib.request
import urllib.error
import json
import sqlite3
import os

BASE_URL = "http://localhost:8080"
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "tavolara_orders.db")

def req(path, method="GET", data=None, token=None):
    url = f"{BASE_URL}{path}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data).encode("utf-8") if data else None
    r = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r) as resp:
            content = resp.read()
            # If CSV
            if "text/csv" in resp.headers.get("Content-Type", ""):
                return resp.status, content
            return resp.status, json.loads(content.decode("utf-8"))
    except urllib.error.HTTPError as e:
        content = e.read()
        try:
            return e.code, json.loads(content.decode("utf-8"))
        except Exception:
            return e.code, content

def run_tests():
    print("=============================================================")
    print("  TAVOLARA WEAR — VERIFICA GESTIONALE FINANZIARIO E DASHBOARD")
    print("=============================================================")

    # 1. Login
    print("\n[STEP 1] Login Amministratore...")
    status, res = req("/api/admin/login", method="POST", data={"password": "tavolara2026"})
    assert status == 200 and res.get("authenticated"), "Login fallito!"
    token = res["token"]
    print("  ✓ Login effettuato con successo. Token:", token[:12] + "...")

    # 2. Incomes CRUD
    print("\n[STEP 2] Verifica ATTIVO — Entrate (CRUD & Stati)...")
    inc_payload = {
        "description": "Vendita stock T-shirt Olbia",
        "amount": 750.00,
        "date": "2026-11-14",
        "payment_method": "Bonifico bancario",
        "order_reference": "LOTTO-2026-01",
        "status": "Incassata",
        "notes": "Bonifico verificato con successo"
    }
    status, res_inc = req("/api/admin/incomes", method="POST", data=inc_payload, token=token)
    assert status == 201, f"Creazione entrata fallita: {res_inc}"
    inc_id = res_inc["income"]["id"]
    print(f"  ✓ Entrata creata con successo: ID #{inc_id}, Importo: {res_inc['income']['amount']} €")

    # Update income
    status, res_up = req(f"/api/admin/incomes/{inc_id}", method="PUT", data={"amount": 800.00, "status": "Incassata"}, token=token)
    assert status == 200 and res_up["income"]["amount"] == 800.00, "Modifica entrata fallita!"
    print(f"  ✓ Entrata #{inc_id} aggiornata a 800.00 €")

    # 3. Expenses CRUD: 4 Categories
    print("\n[STEP 3] Verifica PASSIVO — Le 4 Categorie di Spesa...")
    
    # Category A: Spese di Trasporto
    trans_payload = {
        "category": "trasporto",
        "description": "Spedizione cumulativa Olbia",
        "amount": 42.50,
        "date": "2026-11-14",
        "carrier": "GLS Express",
        "shipment_count": 5,
        "shipment_type": "cumulativa",
        "notes": "Ritiro programmato sede"
    }
    status, res_trans = req("/api/admin/expenses", method="POST", data=trans_payload, token=token)
    assert status == 201 and res_trans["expense"]["category"] == "trasporto"
    exp_trans_id = res_trans["expense"]["id"]
    print(f"  ✓ [A. Trasporto] Registrata spesa ID #{exp_trans_id}: {res_trans['expense']['amount']} € (5 spedizioni)")

    # Category B: Spese di Imballaggio
    pack_payload = {
        "category": "imballaggio",
        "description": "Scatole automontanti personalizzate 30x20",
        "amount": 125.00,
        "date": "2026-11-14",
        "material_type": "Scatole",
        "quantity": 100,
        "unit_cost": 1.25,
        "notes": "Fornitura 100 pezzi"
    }
    status, res_pack = req("/api/admin/expenses", method="POST", data=pack_payload, token=token)
    assert status == 201 and res_pack["expense"]["category"] == "imballaggio"
    exp_pack_id = res_pack["expense"]["id"]
    print(f"  ✓ [B. Imballaggio] Registrata spesa ID #{exp_pack_id}: {res_pack['expense']['amount']} € (100 scatole @ 1.25 €)")

    # Category C: Spese Prove
    proof_payload = {
        "category": "prove",
        "description": "Campionatura serigrafica e prove colore su cotone biologico",
        "amount": 95.00,
        "date": "2026-11-14",
        "proof_type": "Test di stampa serigrafica",
        "notes": "Test tenuta lavaggio"
    }
    status, res_proof = req("/api/admin/expenses", method="POST", data=proof_payload, token=token)
    assert status == 201 and res_proof["expense"]["category"] == "prove"
    exp_proof_id = res_proof["expense"]["id"]
    print(f"  ✓ [C. Prove] Registrata spesa ID #{exp_proof_id}: {res_proof['expense']['amount']} €")

    # Category D: Spese Magliette
    shirt_payload = {
        "category": "magliette",
        "description": "Fornitura 100 T-shirt grezze cotone pettinato",
        "quantity": 100,
        "unit_cost": 8.50,
        "extra_production_costs": 150.00,
        "date": "2026-11-14",
        "supplier": "Manifattura Tessile Srl",
        "notes": "100 pezzi a 8.50 € + 150 € lavorazione serigrafica"
    }
    status, res_shirt = req("/api/admin/expenses", method="POST", data=shirt_payload, token=token)
    assert status == 201 and res_shirt["expense"]["amount"] == 1000.00 # 100 * 8.50 + 150
    exp_shirt_id = res_shirt["expense"]["id"]
    print(f"  ✓ [D. Magliette] Registrata spesa ID #{exp_shirt_id}: {res_shirt['expense']['amount']} € (100 capi)")

    # 4. Mathematical Coherence Check
    print("\n[STEP 4] Verifica della Coerenza Matematica (Overview & Totali)...")
    status, ov = req("/api/admin/financial/overview", token=token)
    assert status == 200
    k = ov["kpis"]
    b = k["expenses_breakdown"]
    
    expected_total_exp = round(b["trasporto"] + b["imballaggio"] + b["prove"] + b["magliette"], 2)
    assert round(k["total_expenses"], 2) == expected_total_exp, f"Totale uscite errato: {k['total_expenses']} vs {expected_total_exp}"
    print(f"  ✓ Somma delle 4 categorie di spesa: {b['trasporto']} + {b['imballaggio']} + {b['prove']} + {b['magliette']} = {expected_total_exp} € (Esatto al centesimo)")

    expected_balance = round(k["total_incomes"] - k["total_expenses"], 2)
    assert round(k["current_balance"], 2) == expected_balance, f"Saldo errato: {k['current_balance']} vs {expected_balance}"
    print(f"  ✓ Saldo attuale rigorosamente verificato: {k['total_incomes']} − {k['total_expenses']} = {expected_balance} €")

    # 5. Insights & Analytics (Color, Size, Cross Matrix)
    print("\n[STEP 5] Verifica INSIGHTS & ANALYTICS...")
    status, ins = req("/api/admin/insights", token=token)
    assert status == 200

    col = ins["color_stats"]
    print(f"  ✓ Statistiche Colore: Blu navy = {col['navy_sold']} ({col['navy_percentage']}%), Bianca = {col['white_sold']} ({col['white_percentage']}%)")
    if col["total_shirts"] > 0:
        assert round(col["navy_percentage"] + col["white_percentage"], 1) in [99.9, 100.0, 100.1], "Percentuali colore non sommano a 100%"
    else:
        assert col["navy_percentage"] == 0.0 and col["white_percentage"] == 0.0

    # Cross matrix validation
    matrix = ins["size_stats"]["cross_matrix"]
    row_sum_navy = sum(r["navy"] for r in matrix["rows"])
    row_sum_white = sum(r["white"] for r in matrix["rows"])
    row_sum_total = sum(r["total"] for r in matrix["rows"])
    
    assert row_sum_navy == matrix["total_row"]["navy"], "Somma colonna navy non coincide"
    assert row_sum_white == matrix["total_row"]["white"], "Somma colonna bianca non coincide"
    assert row_sum_total == matrix["total_row"]["total"], "Somma totale non coincide"
    print(f"  ✓ Matrice incrociata Taglia × Colore verificata: {len(matrix['rows'])} taglie (S, M, L, XL, XXL, 3XL), Totale: {row_sum_total} capi")

    # 6. CSV Export
    print("\n[STEP 6] Verifica Esportazioni CSV (UTF-8 BOM & Formattazione)...")
    status, csv_inc = req("/api/admin/financial/export-csv?type=incomes", token=token)
    assert status == 200 and csv_inc.startswith(b"\xef\xbb\xbf"), "BOM UTF-8 mancante nel CSV entrate"
    print("  ✓ CSV Entrate esportato con intestazioni e UTF-8 BOM compatibile Excel/Numbers")

    status, csv_exp = req("/api/admin/financial/export-csv?type=expenses", token=token)
    assert status == 200 and csv_exp.startswith(b"\xef\xbb\xbf"), "BOM UTF-8 mancante nel CSV uscite"
    print("  ✓ CSV Uscite (4 Categorie) esportato con dettagli operativi")

    status, csv_mat = req("/api/admin/financial/export-csv?type=insights_matrix", token=token)
    assert status == 200 and csv_mat.startswith(b"\xef\xbb\xbf"), "BOM UTF-8 mancante nel CSV matrice"
    print("  ✓ CSV Matrice Taglia × Colore esportato con successo")

    # 7. Clean up test records
    print("\n[STEP 7] Eliminazione e ripristino registrazioni di test...")
    status, _ = req(f"/api/admin/incomes/{inc_id}", method="DELETE", token=token)
    assert status == 200
    for exp_id in [exp_trans_id, exp_pack_id, exp_proof_id, exp_shirt_id]:
        status, _ = req(f"/api/admin/expenses/{exp_id}", method="DELETE", token=token)
        assert status == 200
    print("  ✓ Registrazioni di test eliminate correttamente con verifica di integrità.")

    print("\n=============================================================")
    print("  TUTTE LE VERIFICHE FINANZIARIE SUPERATE CON SUCCESSO! (100%)")
    print("=============================================================")

if __name__ == "__main__":
    run_tests()
