# TAVOLARA WEAR — GESTIONALE FINANZIARIO & SISTEMA ORDINI

Piattaforma gestionale proprietaria completa e indipendente per **Tavolara Wear**, con estetica premium Apple Glass (iOS / macOS), dashboard finanziaria centrale per il controllo quotidiano dei soci (entrate, uscite, 4 categorie di spesa, analytics vendite e matrice taglie/colori) ed estensione per la raccolta ordini dei clienti.

---

## 🌟 CARATTERISTICHE PRINCIPALI

### 1. Dashboard Gestionale Finanziaria dei Soci (`/admin` o `/dashboard`)
- **Estetica Apple Glass & Control Center**: Superfici bianche traslucide con glassmorphism moderato, angoli arrotondati, gradienti delicati, palette blu notte, blu ghiaccio e smeraldo, animazioni e micro-interazioni fluide.
- **Le 4 Sezioni Chiave del Gestionale**:
  1. **Overview (Dashboard Principale)**:
     - 4 Hero KPI glossy: Totale Entrate, Totale Uscite, Saldo Attuale e Utile Lordo (con percentuale di margine).
     - 4 Indicatori Secondari: Magliette vendute, Ordini ricevuti, Costo medio per maglietta, Ricavo medio per ordine.
     - 4 Grafici interattivi con gradienti morbidi: Entrate e Uscite nel tempo, Andamento del saldo cumulativo, Distribuzione delle spese per categoria (Donut), Andamento vendite magliette.
     - Filtri temporali dinamici: Oggi, Settimana, Mese, Trimestre, Anno, Tutto, e Intervallo Date personalizzato.
  2. **Attivo (Entrate)**:
     - Modulo interattivo per registrare entrate (Descrizione, Importo, Data, Metodo di pagamento, Rif. Ordine, Note).
     - Tabella completa filtrabile per stato (Confermata, In attesa, Incassata), metodo di pagamento e ricerca testo.
     - Modifica ed eliminazione con feedback in tempo reale.
     - **Sincronizzazione istantanea con Ordini**: 1 click per importare ordini online confermati direttamente nell'Attivo.
  3. **Passivo (Uscite & Spese nelle 4 Categorie)**:
     - Sottosezioni e filtri dedicati per:
       - **A. Spese di Trasporto**: Spese spedizione, corrieri (GLS, BRT, DHL, Poste), spedizioni singole/cumulative, conteggio spedizioni, note.
       - **B. Spese di Imballaggio**: Buste, scatole automontanti, etichette, packaging personalizzato, quantità acquistata, costo unitario e totale.
       - **C. Spese Prove**: Campioni, prototipi, campionature, test di stampa serigrafica, modifiche e prove di produzione.
       - **D. Spese Magliette**: Acquisto stock t-shirt grezze/finite, fornitore, quantità, costo unitario, costi extra di lavorazione e serigrafia.
     - Indicatori di categoria dedicati (costo medio spedizione, costo medio imballaggio, magliette acquistate, costo unitario medio).
     - Grafico di andamento spesa della categoria nel tempo.
     - Calcolo automatico in tempo reale dell'importo durante l'inserimento.
  4. **Insights & Analytics**:
     - **Statistiche per Colore**: Magliette blu navy vs bianche vendute, percentuali e grafico a ciambella.
     - **Statistiche per Taglia**: S, M, L, XL, XXL, 3XL con indicatori Taglia Più Venduta (🏆) e Taglia Meno Venduta (⚠️).
     - **Matrice Incrociata Taglia × Colore**: Tabella incrociata (S..3XL × Blu, Bianca, Totale e %) con totale matematicamente coerente sia per riga che per colonna.
     - **Statistiche Commerciali**: Ordini totali, Clienti unici, Magliette complessive, Quantità media per ordine, Valore medio carrello (AOV), Fatturato lordo.
     - **Statistiche Economiche**: Costo complessivo produzione, Spese trasporto, Spese imballaggio, Spese prove, Costo medio per capo, Ricavo medio per capo, Margine lordo (€ e %), Utile stimato (€ e %).
     - Filtri incrociati per periodo, colore e taglia.
- **Esportazione CSV Professionale**: File con UTF-8 BOM e delimitatore punto e virgola, compatibili al 100% con Microsoft Excel, Apple Numbers e Google Sheets per Entrate, Uscite, Matrice Taglie e Report Generale.
- **Persistenza e Integrità**: Dati persistiti in SQLite in modalità WAL (`data/tavolara_orders.db`), nessun dato perso al refresh della pagina, coerenza matematica totale tra tutte le sezioni.

---

### 2. Esperienza d'acquisto Clienti (`/`)
- **Identità visiva Tavolara Wear**: Colori blu profondo e bianco, selettore taglie con stock in tempo reale, guida taglie, calcolo spedizioni (Locker, Domicilio, A mano), codici sconto (es. `TAVOLARA5`), causale bonifico bancario univoca anti-errore.

### 3. Architettura & Sicurezza
- **Zero dipendenze esterne**: Funziona con la libreria standard di Python (`http.server` multi-thread, `sqlite3` con modalità WAL ad alta concorrenza, `secrets`, `hashlib`).
- **Nessun costo mensile obbligatorio**: Architettura autosufficiente e ultra-veloce.
- **Sicurezza lato server**: Calcolo prezzi, sconti e disponibilità verificati rigorosamente sul server prima di registrare l'ordine.
- **Protezione ordini**: Ogni ordine riceve un token segreto casuale; i clienti possono visualizzare solo ed esclusivamente la ricevuta del proprio ordine, senza possibilità di enumerare gli ordini altrui.
- **Pronto per Supabase**: Include il file `supabase_schema.sql` completo di tabelle relazionali e Row-Level Security (RLS) per chi desidera migrare su Supabase.

---

## 🚀 COME AVVIARE IL SISTEMA IN LOCALE

Apri il terminale nella cartella del progetto:

```bash
cd "/Users/leonardobizzotto/Desktop/Tavolara Srl/Tavolora modulo "
python3 server.py
```

Il server si avvierà all'indirizzo:
- **Modulo d'ordine per i clienti:** `http://localhost:8080/`
- **Dashboard amministrativa:** `http://localhost:8080/admin`

---

## 🔐 CREDENZIALI AMMINISTRATORE

- **Password iniziale predefinita:** `tavolara2026`
- La password può essere modificata in qualsiasi momento direttamente dalla scheda **Sicurezza** della dashboard `/admin`.

---

## ⚙️ PRIMO AVVIO — CONFIGURAZIONE PREZZI E IBAN

Come richiesto, il sistema nasce con i prezzi **non impostati** per evitare di vendere a tariffe provvisorie.

Prima di condividere il link ai clienti:
1. Accedi a `http://localhost:8080/admin` con la password `tavolara2026`.
2. Vai nella scheda **Prezzi & Tariffe**:
   - Inserisci il prezzo ufficiale della T-shirt (es. `30.00`).
   - Inserisci il costo per la spedizione Locker (es. `4.50`).
   - Inserisci il costo per la spedizione a domicilio (es. `6.00`).
   - Inserisci il costo per la consegna a mano (es. `0.00`).
   - Clicca su **Salva Prezzi e Tariffe**.
3. Vai nella scheda **Coordinate Bancarie**:
   - Inserisci l'intestatario del conto (es. `Tavolara S.r.l.`).
   - Inserisci l'IBAN ufficiale.
   - Inserisci il nome della banca.
   - Clicca su **Salva Coordinate Bancarie**.

Una volta impostati i prezzi, il modulo clienti sarà immediatamente attivo per gli ordini!

---

## 📁 STRUTTURA DEL PROGETTO

```
.
├── database.py              # Inizializzazione e gestione SQLite con WAL mode
├── server.py                # Server HTTP REST multi-thread nativo Python
├── test_suite.py            # Suite automatizzata con i 14 test di verifica
├── supabase_schema.sql      # Schema SQL completo per eventuale deploy su Supabase Cloud con RLS
├── README.md                # Questa guida
├── data/
│   └── tavolara_orders.db   # Database SQLite degli ordini e configurazioni
└── static/
    ├── index.html           # Interfaccia pubblica per l'ordine dei clienti
    ├── admin.html           # Dashboard amministrativa per i soci
    ├── css/
    │   ├── style.css        # Stili ufficiali Tavolara Wear (responsive e mobile-first)
    │   └── admin.css        # Stili per la dashboard amministrativa
    ├── js/
    │   ├── app.js           # Logica client (navigazione a step, calcoli, foto)
    │   └── admin.js         # Logica admin (gestione ordini, filtri, CSV, stock)
    └── assets/              # Fotografie ufficiali e grafica vettoriale Tavolara Wear
        ├── print-wordmark.png
        ├── tavolara-panorama-optimized.webp
        ├── tavolara-social.jpg
        └── gallery/
            ├── navy-front-v3.webp
            ├── navy-back-v3.webp
            ├── white-front-v3.webp
            └── white-back-v3.webp
```

---

## 🧪 ESECUZIONE DEI TEST DI VERIFICA

Per verificare l'intero flusso del sistema (tutti i 14 scenari richiesti):

```bash
python3 test_suite.py
```

Tutti i 14 test vengono eseguiti automaticamente con report dettagliato.
