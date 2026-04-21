# PRD — SVJ Správa

> **Klonovací spec, část 1/5 — Přehled, doména, stack.**  
> Navigace: [README](README.md) · **PRD.md** · [PRD_DATA_MODEL](PRD_DATA_MODEL.md) · [PRD_MODULES](PRD_MODULES.md) · [PRD_UI](PRD_UI.md) · [PRD_ACCEPTANCE](PRD_ACCEPTANCE.md)

---

## 1. Účel projektu

**SVJ Správa** je webová aplikace pro **Společenství vlastníků jednotek** (česká organizační forma bytového domu, zkratka SVJ). Slouží k evidenci a automatizaci administrativních úkonů, které dnes výbor SVJ typicky dělá ručně v Excelu a e-mailu.

### Cílový uživatel

**Předseda/člen výboru menšího SVJ** (20–200 jednotek). Není IT expert, používá Mac/PC s moderním prohlížečem. Aplikaci provozuje **lokálně** (Python + SQLite, bez serveru) nebo na jednoduchém VPS.

### Primární scénáře (proč to vzniklo)

1. **Hlasování per rollam** — rozeslat lístky 80 vlastníkům, sebrat naskenované odpovědi, spočítat kvórum, archivovat výsledky. V Excelu/Wordu to trvá 2 dny → aplikace to dělá za 2 hodiny.
2. **Daňové rozúčtování** — rozeslat 80 PDF výpisů s rozúčtováním daně z nemovitosti správným vlastníkům. Každý rok stejný proces: match PDF → vlastník → e-mail. Aplikace automatizuje párování a hromadnou rozesílku.
3. **Synchronizace s katastrem** — dostane aktualizovaný CSV ze Seznamu členů (SČD) a potřebuje najít rozdíly proti stávající evidenci: kdo je nový vlastník, kdo prodal, změnil jméno. Aplikace porovná a umožní výměny jedním klikem.
4. **Platby a vyúčtování** — importuje bankovní výpis z Fio, spáruje platby na předpisy podle variabilního symbolu, zobrazí dlužníky, upozorní vlastníky na nesrovnalosti, na konci roku vygeneruje vyúčtování.
5. **Vodoměry** — 2× ročně importuje odečty, porovná s loňskými stavy, rozešle přehled vlastníkům.

### Non-goals

- **Účetnictví** — aplikace **nenahrazuje účetní software**. Počítá pouze zůstatky a vyúčtování pro vlastníky, nedělá DPH, daň z příjmu, rozvahu atd.
- **Portál pro vlastníky** — aplikace je pro **výbor**, ne pro vlastníky. Vlastníci dostávají e-maily s PDF, do aplikace se nepřihlašují.
- **Víceúrovňové role a ACL** — v MVP **jedna role** (administrátor = výbor). Pozdější rozšíření je v `docs/USER_ROLES.md`.
- **Integrace s externími systémy** — žádné API s katastrem, bankou, e-mailovými marketingovými nástroji. Jen manuální CSV/Excel import a SMTP pro e-maily.
- **Mobilní aplikace** — pouze web s responzivním designem.

---

## 2. Tech stack

### Závazné volby (deterministické)

| Vrstva | Volba | Verze | Proč |
|---|---|---|---|
| **Jazyk** | Python | 3.9+ | Standard pro rychlé web aplikace s daty, Excel/PDF knihovny |
| **Web framework** | FastAPI | 0.128+ | Async, type hints, OpenAPI zdarma |
| **ASGI server** | Uvicorn | 0.39+ | Standard pro FastAPI |
| **ORM** | SQLAlchemy 2.0 | 2.0+ | Industry standard, **ale používej legacy query API** (`db.query()`), nikoli nový `select()` style |
| **Databáze** | SQLite | – | Soubor `data/svj.db`, `check_same_thread=False`, WAL mode |
| **Validace** | Pydantic | 2.12+ | Přes `pydantic-settings` pro `app/config.py` |
| **Šablony** | Jinja2 | 3.1+ | Server-side rendering |
| **CSS** | Tailwind CSS (CDN) | 3.x | Žádný build pipeline, `cdn.tailwindcss.com` |
| **Frontend interaktivita** | HTMX | 2.0+ | Server-side stav, partial swaps, žádný SPA framework |
| **Excel** | openpyxl | 3.1+ | Read/write `.xlsx` |
| **Word** | python-docx + docxtpl | 1.2 / 0.20 | Parsing předpisů, generování lístků |
| **PDF** | pdfplumber + Pillow | 0.11 / 11.3 | Extrakce textu z PDF výpisů |
| **Email** | `smtplib` + `imaplib` (stdlib) | – | SMTP pro odesílání, IMAP pro bounce check |
| **Šifrování SMTP hesel** | cryptography.fernet | – | Symetrický klíč v `data/.smtp_key` |
| **Testy** | pytest | – | In-memory SQLite, ~580 testů |
| **Volitelné externí nástroje** | LibreOffice | – | Pro konverzi DOCX → PDF (jen při generování lístků) |

### Zakázané volby (anti-vzory)

- ❌ **SQLAlchemy `select()` style** — celý projekt používá legacy `db.query()`. Nezavádět mix.
- ❌ **Alembic** — migrace jsou vlastní funkce v `main.py` (`_ALL_MIGRATIONS` list).
- ❌ **SPA framework** (React/Vue) — celé UI je server-rendered + HTMX partials.
- ❌ **jQuery** nebo libovolná JS knihovna kromě HTMX a vlastního `app.js`.
- ❌ **CSS preprocesor** nebo build pipeline — jen Tailwind CDN + dva vlastní CSS soubory.
- ❌ **Redis / Celery / background queue** — background úlohy jsou obyčejné Python thready + in-memory progress dict.
- ❌ **Anglické URL slugy** (`/owners`, `/units`) — všechny URL jsou **české bez diakritiky** (`/vlastnici`, `/jednotky`).

---

## 3. Architektura

### Vrstvová struktura

```
┌─────────────────────────────────────────────┐
│  Jinja2 templates (app/templates/)          │
│  + Tailwind CDN + HTMX + custom app.js     │
└──────────────────┬──────────────────────────┘
                   │ server-rendered HTML
                   │ + HTMX partial swaps
┌──────────────────▼──────────────────────────┐
│  FastAPI routers (app/routers/)             │
│  14 modulů, ~120 endpointů                  │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│  Services (app/services/)                   │
│  Plain funkce, přijímají db: Session        │
│  Import/export, matching, email, PDF...     │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│  Models (app/models/)                       │
│  SQLAlchemy 2.0 DeclarativeBase             │
│  25 modelů, 20+ enumů, 87 indexů            │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│  SQLite (data/svj.db)                       │
│  + data/uploads/, data/backups/,            │
│    data/generated/, data/temp/, .smtp_key   │
└─────────────────────────────────────────────┘
```

### Klíčové principy

1. **Server-rendered s HTMX partials** — žádná client-side rehydratace. HTMX vrací `<tbody>` nebo `<div>` fragmenty, které nahrazují část stránky.
2. **Plochá adresářová struktura** — jeden soubor per entitu v `models/`, jeden soubor (nebo package) per modul v `routers/`, plain funkce v `services/` (žádné třídy).
3. **Konvenční URL** — české slugy, sub-endpointy `/nova`, `/upravit`, `/smazat`, `/exportovat/{fmt}`. Viz `appendices/CLAUDE.md § URL konvence`.
4. **Wizard workflow** — všechny multi-step importy mají stejný 4-step vzor: upload → mapování → náhled → potvrzení. Sdílený stepper partial.
5. **Filtry jako bubliny** — nad každou tabulkou jsou klikací bubliny (status, typ, sekce), které filtrují + zachovávají se v URL.
6. **Back URL propagace** — odkazy na detail entity nesou `?back=...`. Detail má zpětnou šipku zpět na původní filtrovaný seznam se zachovanou scroll pozicí.
7. **Export všude** — každá datová tabulka má `↓ Excel` a `↓ CSV` v hlavičce. Export respektuje aktivní filtry a bubliny; název souboru obsahuje suffix podle filtru.
8. **Background úlohy bez fronty** — dlouhé operace (import velkého souboru, rozesílka e-mailů, PDF processing) běží v `threading.Thread`. Progress v in-memory dict. HTMX polling na `/*-stav` endpointy.
9. **Migrace v `main.py`** — při startu a po obnově zálohy se spustí `_ALL_MIGRATIONS` list funkcí. Každá migrace je idempotentní (`CREATE TABLE IF NOT EXISTS`, `ALTER TABLE ADD COLUMN` s try/except).
10. **Security headers + global exception handlers** — všechny odpovědi nesou `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`. `IntegrityError` → 409, `OperationalError` → 500, vše přes custom `error.html`.

### Adresářová struktura

```
SVJ/
├── app/
│   ├── __init__.py
│   ├── main.py                    # lifespan, middleware, router include, migrace
│   ├── config.py                  # pydantic-settings
│   ├── database.py                # engine, SessionLocal, get_db
│   ├── utils.py                   # shared helpers (viz § Utils v CLAUDE.md)
│   ├── models/
│   │   ├── __init__.py            # re-exporty + __all__
│   │   ├── common.py              # EmailLog, EmailBounce, ImportLog, ActivityLog
│   │   ├── administration.py      # SvjInfo, SvjAddress, BoardMember, CodeListItem, EmailTemplate
│   │   ├── owner.py               # Owner, Unit, OwnerUnit, Proxy
│   │   ├── voting.py              # Voting, VotingItem, Ballot, BallotVote
│   │   ├── tax.py                 # TaxSession, TaxDocument, TaxDistribution
│   │   ├── sync.py                # SyncSession, SyncRecord
│   │   ├── share_check.py         # ShareCheckSession, ShareCheckRecord, ShareCheckColumnMapping
│   │   ├── payment.py             # VariableSymbolMapping, UnitBalance, PrescriptionYear, Prescription, PrescriptionItem, BankStatement, Payment, PaymentAllocation, Settlement, SettlementItem, BankStatementColumnMapping
│   │   ├── space.py               # Space, Tenant, SpaceTenant
│   │   ├── smtp_profile.py        # SmtpProfile
│   │   └── water_meter.py         # WaterMeter, WaterReading
│   ├── routers/
│   │   ├── dashboard.py           # standalone
│   │   ├── units.py               # standalone
│   │   ├── share_check.py         # standalone
│   │   ├── settings_page.py       # standalone
│   │   ├── bounces.py             # standalone
│   │   ├── owners/                # package: __init__, crud, import_owners, import_contacts
│   │   ├── voting/                # package: __init__, session, ballots, import_votes
│   │   ├── tax/                   # package: __init__, session, processing, matching, sending
│   │   ├── sync/                  # package: __init__, session, contacts, exchange
│   │   ├── administration/        # package: __init__, info, board, code_lists, backups, bulk
│   │   ├── payments/              # package: __init__, overview, prescriptions, statements, symbols, balances, settlement, discrepancies
│   │   ├── spaces/                # package: __init__, crud, import_spaces
│   │   ├── tenants/                # package: __init__, crud
│   │   └── water_meters/           # package: __init__, overview, import_readings, sending
│   ├── services/                  # 26 modulů, plain funkce (db: Session parametr)
│   │   ├── email_service.py
│   │   ├── excel_import.py
│   │   ├── excel_export.py
│   │   ├── import_mapping.py
│   │   ├── voting_import.py
│   │   ├── prescription_import.py
│   │   ├── bank_import.py
│   │   ├── balance_import.py
│   │   ├── contact_import.py
│   │   ├── space_import.py
│   │   ├── payment_matching.py
│   │   ├── payment_overview.py
│   │   ├── payment_discrepancy.py
│   │   ├── owner_matcher.py
│   │   ├── owner_exchange.py
│   │   ├── owner_service.py
│   │   ├── csv_comparator.py
│   │   ├── share_check_comparator.py
│   │   ├── settlement_service.py
│   │   ├── pdf_extractor.py
│   │   ├── pdf_generator.py
│   │   ├── word_parser.py
│   │   ├── bounce_service.py
│   │   ├── backup_service.py
│   │   ├── code_list_service.py
│   │   └── data_export.py
│   ├── templates/
│   │   ├── base.html              # sidebar, dark mode, flash, modals
│   │   ├── error.html             # 404/500
│   │   ├── partials/              # sdílené partialy (wizard_stepper, import_mapping_fields, ...)
│   │   └── {modul}/               # per-modul šablony
│   └── static/
│       ├── js/
│       │   ├── app.js             # HTMX config, dark mode, svjConfirm, scroll restore
│       │   └── tailwind.min.js    # fallback offline kopie
│       └── css/
│           ├── custom.css         # HTMX animace, scroll margin, button disabled
│           └── dark-mode.css      # dark mode override přes `.dark` class
├── data/
│   ├── svj.db                     # SQLite (runtime, .gitignored)
│   ├── .smtp_key                  # Fernet klíč (32B, .gitignored)
│   ├── uploads/                   # excel/, word_templates/, scanned_ballots/, tax_pdfs/, csv/, share_check/, contracts/, water_meters/
│   ├── generated/                 # ballots/, exports/
│   ├── backups/                   # ZIP zálohy
│   └── temp/
├── tests/                         # pytest, in-memory SQLite
├── docs/
│   ├── CLAUDE.md → viz appendices
│   ├── UI_GUIDE.md → viz appendices
│   ├── NAVIGATION.md
│   ├── ROUTER_PATTERNS.md
│   ├── NEW_MODULE_CHECKLIST.md
│   └── DEPLOYMENT.md
├── requirements.txt
├── pyproject.toml
├── .env.example
├── spustit.command                # macOS launcher pro USB nasazení
├── pripravit_usb.sh
└── README.md
```

---

## 4. Doménový slovník

| Pojem | Význam | Kontext |
|---|---|---|
| **SVJ** | Společenství vlastníků jednotek | Organizační forma bytového domu v ČR |
| **Vlastník** (Owner) | Fyzická nebo právnická osoba vlastnící jednotku | Primární entita |
| **Jednotka** (Unit) | Byt nebo nebytová jednotka s katastrálním číslem | `unit_number` je INTEGER |
| **Prostor** (Space) | Nebytový prostor pronajímaný třetí straně (obchod, kancelář) | Odlišné od Jednotky |
| **Nájemce** (Tenant) | Osoba nebo firma pronajímající Prostor | Může být linked na Owner nebo samostatný |
| **Podíl SČD** (`podil_scd`) | Spoluvlastnický podíl v souboru společných částí domu | Float, např. 0.0234 |
| **Celkový počet podílů** (`total_shares`) | Součet podílů za celý dům, definovaný v prohlášení vlastníka | Integer v `SvjInfo` |
| **SJM** | Společné jmění manželů | Dva vlastníci sdílejí jednu jednotku, každý má lístek |
| **VL** | Výhradní vlastnictví (jeden vlastník jedna jednotka) | `ownership_type` |
| **SJVL** | Stejný jako VL, ale historicky jiný typ | `ownership_type` |
| **Podílové vlastnictví** | Více vlastníků sdílí jednotku s různými podíly | `ownership_type` |
| **Lístek** (Ballot) | Hlasovací lístek konkrétního vlastníka k hlasování | Generuje se 1 per vlastník-jednotka kombinace |
| **Per rollam** | Písemné hlasování (bez schůze) | Primární způsob hlasování |
| **Kvórum** (`quorum_threshold`) | Minimální podíl hlasů pro platnost | Float 0–1 (v DB), v UI zadávaný jako % (50.0) |
| **Plná moc** (Proxy) | Vlastník A pověřuje vlastníka B, aby hlasoval za něj | `voted_by_proxy` |
| **Předpis** (Prescription) | Měsíční částka k úhradě za jednotku (za rok) | Import z DOCX |
| **Variabilní symbol** (VS) | Identifikátor platby, mapuje se na jednotku/prostor | `variable_symbol`, typicky 10 číslic |
| **Bankovní výpis** (BankStatement) | CSV z banky s pohyby na účtu | Primárně Fio formát |
| **Platba** (Payment) | Jednotlivý pohyb z výpisu | Páruje se na Předpis přes VS |
| **Alokace** (PaymentAllocation) | Rozpad platby na více jednotek/prostorů | Pro částky zahrnující více VS |
| **Zůstatek** (UnitBalance) | Přenos nedoplatku/přeplatku z minulého roku | Per jednotka-rok |
| **Vyúčtování** (Settlement) | Roční výkaz nákladů a záloh za jednotku | PDF generated |
| **Nesrovnalost** (Discrepancy) | Platba s chybným VS, částkou nebo rozpadem | Neperzistuje, počítá se on-the-fly |
| **Vodoměr** (WaterMeter) | Měřidlo SV/TV (studená/teplá voda) | Per jednotka |
| **Odečet** (WaterReading) | Hodnota vodoměru v konkrétní datum | Import 2× ročně |
| **Daňové rozúčtování** | Rozdělení daně z nemovitosti mezi vlastníky | Modul `tax` |
| **Synchronizace** (Sync) | Porovnání CSV ze SČD s evidencí | Detekce nových vlastníků, změn jmen |
| **Kontrola podílů** (Share Check) | Porovnání podílů v Excelu s podíly v DB | Verifikační nástroj |
| **Bounce** | Vrácený e-mail (hard/soft) | IMAP check |
| **Seznam členů SČD** | Oficiální evidence z katastru nemovitostí | CSV |

---

## 5. Klíčová rozhodnutí (ADR-style)

### ADR-001: SQLite, ne PostgreSQL
**Rozhodnutí**: DB je SQLite soubor. **Proč**: aplikace běží lokálně u jednoho uživatele (předseda SVJ). Není žádná concurrent multi-user práce. SQLite umožňuje zálohovat = zkopírovat soubor, obnovit = nahradit soubor. WAL mode dává dostatečný výkon pro 200 jednotek a 10 let historie.

### ADR-002: Server-rendered + HTMX, ne SPA
**Rozhodnutí**: Žádný React/Vue. Templates + HTMX partials. **Proč**: nástroj pro 1 uživatele, žádná potřeba optimistických updatů. HTMX + Tailwind dává plně reaktivní UI za zlomek složitosti. Deployment = nakopírovat repozitář.

### ADR-003: České URL slugy
**Rozhodnutí**: `/vlastnici`, `/jednotky` místo `/owners`, `/units`. **Proč**: doména je čistě česká (katastr, zákon o SVJ). Uživatel vidí URL v prohlížeči a rozumí. Anglické URL by znamenaly mentální překlad.

### ADR-004: Vlastní migrace v `main.py`, ne Alembic
**Rozhodnutí**: `_ALL_MIGRATIONS` list funkcí volaný v lifespan a po restore. Každá migrace idempotentní. **Proč**: jednoduchost. Nikdy není víc instance, není potřeba synchronizace. Plus: migrace se musí spustit i po restore zálohy ze starší verze — Alembic tohle neřeší elegantně.

### ADR-005: Plain funkce v services, ne třídy
**Rozhodnutí**: `excel_import.import_owners(db, path, mapping, ...)`. Žádné service třídy. **Proč**: méně boilerplate. Db session předává router. Testování = zavolat funkci s in-memory sessi.

### ADR-006: `db.query()` legacy API, ne `select()`
**Rozhodnutí**: `db.query(Owner).filter(...).all()`. **Proč**: projekt vznikl v SA 1.x éře a konzistence > modernost. Migrace by si vyžádala refactor stovek dotazů bez přínosu.

### ADR-007: Background úlohy přes threading.Thread, ne Celery
**Rozhodnutí**: Dlouhé operace běží v threadu, progress v in-memory dict, HTMX polluje status endpoint. **Proč**: jedna instance, není potřeba distribuovaný broker. Pokud proces padne, uživatel spustí znovu.

### ADR-008: SMTP heslo šifrované Fernetem
**Rozhodnutí**: Heslo v DB šifrované klíčem z `data/.smtp_key`. **Proč**: kdyby uživatel commitnul DB nebo sdílel zálohu, hesla jsou chráněná. Legacy zápisy (plaintext base64) jsou zpětně kompatibilní.

### ADR-009: Dashboard = statistiky + poslední aktivita, ne KPI dashboard
**Rozhodnutí**: `/` zobrazuje 7 stat karet (vlastníci, jednotky, nájemci, prostory, hlasování, rozesílání, platby) + tabulku posledních ~20 aktivit (z `ActivityLog`). **Proč**: uživatel potřebuje vidět "co se naposledy dělo" a přejít dál. Ne grafy.

### ADR-010: Dark mode přes CSS override, ne Tailwind `dark:` variant
**Rozhodnutí**: `dark-mode.css` přebíjí Tailwind classy přes `.dark .bg-white` selektor. Toggle v sidebaru, uloženo v `localStorage`. **Proč**: Tailwind CDN nepodporuje customizaci `dark:` variantou. CSS override je jediná cesta.

---

## 6. Nefunkční požadavky

| Kategorie | Požadavek |
|---|---|
| **Výkon** | Stránka se načte do 1s při 200 jednotkách a 10 letech historie. Import 80 řádků do 10s. |
| **Bezpečnost** | Security headers (X-Frame-Options, CSP). Validace cesty pro download endpointy (path traversal prevention). SMTP heslo šifrované. Žádné XSS (Jinja2 auto-escape). |
| **Dostupnost** | Jen lokální nebo VPS. Žádné HA požadavky. |
| **Přenositelnost** | Musí běžet na macOS a Linux (Python 3.9+). Windows nemusí být supportován. USB nasazení: složka + `spustit.command`. |
| **Čeština** | UI, chyby, e-maily, exporty, URL (bez diakritiky) — **všechno v češtině**. Jediná angličtina je v kódu (identifikátory, komentáře nejsou, viz `CLAUDE.md`). |
| **Přístupnost** | Focus trap v modalech, Escape pro zavření, keyboard nav sidebaru. Ne WCAG AAA, ale základní rozumná úroveň. |
| **Odolnost** | `IntegrityError` a `OperationalError` nesmí shodit aplikaci. Flash zpráva + log. Chyba při importu nesmí zanechat nekonzistentní data (transakce). |

---

## 7. Seznam modulů

| # | Modul | URL prefix | Účel | Detaily v [PRD_MODULES.md](PRD_MODULES.md) |
|---|---|---|---|---|
| 1 | Dashboard | `/` | Přehled + poslední aktivita | § Modul 1 |
| 2 | Vlastníci | `/vlastnici` | CRUD, import z Excelu, kontakty | § Modul 2 |
| 3 | Jednotky | `/jednotky` | CRUD, propojení s vlastníky | § Modul 3 |
| 4 | Prostory | `/prostory` | CRUD nebytových prostor | § Modul 4 |
| 5 | Nájemci | `/najemci` | CRUD nájemců, propojení s prostory | § Modul 5 |
| 6 | Hlasování | `/hlasovani` | Sessions, lístky, zpracování, import | § Modul 6 |
| 7 | Rozesílání (daně) | `/rozesilani` | Import PDF, matching, e-mail rozesílka | § Modul 7 |
| 8 | Bounces | `/rozesilani/bounces` | IMAP kontrola nedoručených e-mailů | § Modul 8 |
| 9 | Synchronizace | `/synchronizace` | CSV vs evidence, výměny vlastníků | § Modul 9 |
| 10 | Kontrola podílů | `/kontrola-podilu` | Excel vs DB podíly | § Modul 10 |
| 11 | Administrace | `/sprava` | SvjInfo, členové výboru, číselníky, zálohy, purge, export | § Modul 11 |
| 12 | Nastavení | `/nastaveni` | SMTP profily, historie e-mailů | § Modul 12 |
| 13 | Platby | `/platby` | Předpisy, výpisy, vyúčtování, nesrovnalosti | § Modul 13 |
| 14 | Vodoměry | `/vodometry` | Import odečtů, přiřazení, rozesílka | § Modul 14 |

---

## 8. Next step

Pokračuj do [`PRD_DATA_MODEL.md`](PRD_DATA_MODEL.md) pro **deterministickou specifikaci všech tabulek, sloupců a enumů**. Potom [`PRD_MODULES.md`](PRD_MODULES.md) pro user stories per modul.
