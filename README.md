# TAVOLARA WEAR — SISTEMA DI RACCOLTA ORDINI ONLINE

Sistema completo e indipendente di raccolta ordini per **Tavolara Wear**, progettato come naturale estensione del sito ufficiale ([tavolarawear.it](https://tavolarawear.it/)).

---

## 🌟 CARATTERISTICHE PRINCIPALI

### 1. Esperienza d'acquisto Premium & Mobile-First
- **Identità visiva ufficiale**: Palette cromatica originale (`#003760`, `#14243b`, `#164e6b`), tipografia editoriale (`Georgia` + `Arial`), logo originale e sfondo panoramico dell'Isola di Tavolara.
- **Flusso guidato a step logici**:
  1. *Selezione Prodotto*: Colori (Blu navy e Bianco), anteprima fotografica fronte/retro, selettore visivo delle taglie (S, M, L, XL, 2XL, 3XL) con stock in tempo reale, guida taglie interattiva fedele al sito ufficiale, selettore quantità.
  2. *Dati & Consegna*: Campi cliente validati (Nome, Cognome, Email, Telefono) e 3 modalità di consegna:
     - **Locker / Punto di ritiro** (InPost, FermoPoint, ecc.)
     - **Spedizione a domicilio** (con indirizzo, CAP, città, provincia e note per il corriere)
     - **Consegna a mano** (località concordata e contatto diretto)
  3. *Riepilogo & Codice Sconto*: Calcolo automatico in tempo reale, codice promozionale (iniziale `TAVOLARA5` con 5 € di sconto), consenso GDPR privacy.
  4. *Schermata Dedicata Bonifico Bancario*: Coordinate bancarie complete, causale univoca generata in automatico nel formato richiesto (`TAVOLARA WEAR - NOME COGNOME - NUMERO ORDINE`), pulsanti di copia rapida e rassicurazione sulla verifica manuale dell'accredito.

### 2. Dashboard Amministrativa Privata (`/admin`)
- **Gestione completa degli ordini**: Tabella in tempo reale con filtri per stato, consegna, data e barra di ricerca istantanea per nome, cognome, numero d'ordine ed email.
- **6 Stati dell'ordine**:
  1. *Nuovo ordine*
  2. *In attesa di pagamento*
  3. *Pagamento verificato*
  4. *In preparazione*
  5. *Spedito / Consegnato*
  6. *Annullato*
- **Aggiornamento stati con 1 click**: I soci possono aggiornare lo stato di ogni ordine direttamente dal menu a tendina.
- **Statistiche & Magazzino**: Totale capi venduti, spaccato analitico per taglia e colore, totale incassi verificati e in attesa.
- **Matrice disponibilità taglie/colori**: Possibilità di attivare/disattivare qualsiasi taglia (es. contrassegnare una variante esaurita) con switch istantaneo, senza modificare codice.
- **Configurazione dinamica**: Modifica del prezzo t-shirt, costi spedizione locker e domicilio, coordinate bancarie (IBAN, intestatario, banca) e codici sconto.
- **Esportazione CSV**: File CSV formattato con UTF-8 BOM e delimitatore punto e virgola, compatibile al 100% con Microsoft Excel e Google Sheets.

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
