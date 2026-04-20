# SVJ Projekt — pravidla pro vývoj

> **UI/frontend konvence** (layout, tabulky, formuláře, tlačítka, bubliny, badge, ikony, inline editace, HTMX vzory, formátování, back URL navigace, checkboxy, kolapsovatelné sekce) jsou v **[docs/UI_GUIDE.md](docs/UI_GUIDE.md)**.
> Tento soubor definuje backend pravidla, datový model, routery, workflow a projektová specifika.

## Obsah

- [URL konvence](#url-konvence) · [Navigace a back URL](#navigace-a-back-url) · [Tabulky — povinný checklist](#tabulky--povinný-checklist) · [Procentuální vstupy](#procentuální-vstupy-kvórum-podíly) · [Statistiky podílů](#statistiky-podílů) · [Dashboard](#dashboard) · [Vyhledávání](#vyhledávání) · [Jména vlastníků](#jména-vlastníků) · [Import hlasování — SJM](#import-hlasování--spoluvlastnictví-sjm) · [SQLAlchemy vzory](#sqlalchemy-vzory) · [Router vzory](#router-vzory) · [Nové moduly / entity + Export dat](#nové-moduly--entity--export-dat) · [Mazání dat](#mazání-dat-purge) · [Upload souborů](#upload-souborů) · [Service layer](#service-layer) · [Utility funkce](#utility-funkce-apputilspy) · [JavaScript](#javascript) · [Technologie](#technologie) · [Global exception handlers](#global-exception-handlers) · [Security headers](#security-headers) · [Router packages](#router-packages) · [Startup](#startup-lifespan) · [Nasazení na USB](#nasazení-na-usb-jiný-počítač) · [Workflow](#workflow) · [Komunikace](#komunikace-s-uživatelem) · [Uživatelské role](#uživatelské-role--plán-implementace-na-konec) · [Pravidla pro práci](#pravidla-pro-práci-na-úkolech)

## URL konvence

- Všechny URL cesty používají **české slugy bez diakritiky**: `/vlastnici`, `/jednotky`, `/prostory`, `/najemci`, `/hlasovani`, `/rozesilani`, `/synchronizace`, `/sprava`, `/nastaveni`, `/platby`, `/kontrola-podilu`, `/vodometry`
- Sub-endpointy: `/nova` (create), `/smazat` (delete), `/upravit` (edit), `/pridat` (add), `/potvrdit` (confirm), `/odebrat` (remove), `/exportovat` (export), `/aktualizovat` (update)
- Nikdy nepoužívat angličtinu v URL cestách

## Navigace a back URL

> Viz **[docs/NAVIGATION.md](docs/NAVIGATION.md)** — `list_url`, `back_url`, propagace přes bubliny/HTMX, scroll pozice, back label logika.

## Tabulky — povinný checklist

> **Tento checklist platí pro datové tabulky** (desítky/stovky řádků — vlastníci, jednotky, lístky, logy). Pro malé admin seznamy (~5–15 položek, např. číselníky, emailové šablony, členové výboru) použít kompaktní layout — karty s inline edit, toggle hidden. Před implementací zvážit objem dat.

> **Při JAKÉKOLIV úpravě stránky s tabulkou (nová stránka, redesign, přidání sloupce) VŽDY zkontrolovat a doplnit VŠECHNY body:**

1. **Řaditelné sloupce** — KAŽDÝ datový sloupec musí být řaditelný kliknutím na hlavičku (šipka nahoru/dolů). Implementace přes `_cols` loop nebo `sort_th` macro, `SORT_COLUMNS` dict v routeru
2. **Hledání** — HTMX search bar s `hx-trigger="keyup changed delay:300ms"`, prohledává všechna relevantní textová pole, diacritics-insensitive přes `strip_diacritics()` z `app.utils`
3. **Klikací entity** — každý odkaz na entitu (vlastník, jednotka, lístek) musí být `<a href>`, nikdy plain text pokud existuje detail stránka. Vyžaduje lookup v routeru (např. `owner_by_email` dict)
4. **Eager loading** — klikací entity vyžadují `joinedload()` v routeru, jinak lazy loading selže nebo způsobí N+1
5. **HTMX partial** — search aktualizuje jen `<tbody>` přes partial šablonu, zbytek stránky zůstane
6. **Sticky header** — `sticky top-0 z-10` na `<thead>`, flex column layout pro fixní filtry/search nad scrollovatelným obsahem
7. **Náhledy souborů** — pokud tabulka zobrazuje soubory/přílohy (PDF, Excel, CSV), názvy MUSÍ být klikací s `target="_blank"` a `hx-boost="false"` pro náhled/stažení. Vyžaduje: (a) uložení plné cesty souboru v DB, (b) download endpoint s validací cesty v povolených adresářích, (c) `FileResponse` se správným `media_type`
8. **Export + počet záznamů** — každá stránka s datovou tabulkou MUSÍ mít v hlavičce: (a) počet záznamů (`{{ items|length }} záznamů`), (b) tlačítka ↓ Excel a ↓ CSV se stejným stylem (`bg-gray-100 text-gray-600 border-gray-200`). Export endpoint (`/exportovat/{fmt}`) přijímá `xlsx`/`csv`, respektuje aktivní filtry/bubliny/hledání. Název souboru obsahuje suffix dle filtru (viz § Export dat)

- Klikací entity vyžadují eager loading relací v routeru:
  ```python
  joinedload(Ballot.owner).joinedload(Owner.units).joinedload(OwnerUnit.unit)
  ```
- Bez eager loading `current_units` vrátí prázdný list (lazy loading selže mimo session) nebo způsobí N+1 dotazy
- Při přidání nového klikacího sloupce do tabulky VŽDY zkontrolovat, zda router má potřebný `joinedload()`
- **Tento checklist platí i při čistě vizuálních úpravách** (kompaktnější layout, přesunutí prvků) — nikdy neodeslat stránku s tabulkou bez všech 8 bodů
- **UI detaily** (sticky header CSS, sort hlavičky, ikony akcí, badge, formátování) — viz [UI_GUIDE.md](docs/UI_GUIDE.md)

## Procentuální vstupy (kvórum, podíly)

- Formulář posílá procenta jako číslo (např. `50` pro 50%)
- Databáze ukládá jako podíl 0–1 (např. `0.5`)
- **Router MUSÍ dělit vstup `/100`** při ukládání: `quorum_threshold = form_value / 100`
- Šablona MUSÍ násobit `*100` při zobrazení: `{{ (value * 100)|round(1) }}%`
- Nikdy neukládat surovou hodnotu z formuláře bez konverze

## Statistiky podílů

- Porovnání podílů se zobrazuje na dashboardu i v seznamech (vlastníci, jednotky):
  - Podíly dle prohlášení (z `SvjInfo.total_shares`)
  - Podíly v evidenci (součet z tabulky)
  - Rozdíl s barevným kódováním a procentuálním vyjádřením
- V detailu vlastníka: sloupec "Podíl %" = `podil_scd / declared_shares * 100` (4 des. místa)
- `declared_shares` se předává do všech šablon kde se zobrazují podíly (včetně HTMX partials)

## Dashboard

- 7 stat karet v jednom řádku: vlastníci, jednotky, nájemci, prostory, hlasování, rozesílání, platby
- Jednoduché karty (vlastníci, jednotky) — celá karta je `<a>` tag
- Karty se sub-odkazy (nájemci, prostory, hlasování, rozesílání, platby) — `<div>` wrapper s hlavním `<a>` a per-status linky uvnitř
- Per-status řádky: count badge + `→ název poslední kampaně` (truncate + title tooltip)
- Přehledové karty zobrazují VŽDY všechny stavy — nikdy nefiltrovat na „jen aktivní"
- Fixní header (stat karty + search) se scrollovatelnou tabulkou poslední aktivity

## Vyhledávání

- Hledání probíhá přes HTMX s debounce: `hx-trigger="keyup changed delay:300ms"`
- Prohledávají se všechna relevantní pole (jméno, email, telefon, RČ, IČ, číslo jednotky, adresa)
- Hledání se kombinuje s filtry (typ, sekce, vlastnictví, kontakt) — filtry se přenáší přes hidden inputy a `hx-include`
- Hidden inputy (`sort`, `order`, `stav`, `back`) jsou VEDLE search inputu, NE uvnitř tbody partial
- **Diakritika v SQLite**: SQLite `lower()` a `LIKE`/`ilike` nefungují s českou diakritikou (č≠Č, ř≠Ř atd.). Proto se jména **vždy hledají přes sloupec `name_normalized`** (bez diakritiky, lowercase) s normalizovaným hledaným výrazem:
  ```python
  from app.utils import strip_diacritics

  search_ascii = f"%{strip_diacritics(q)}%"
  Owner.name_normalized.like(search_ascii)  # NE ilike — name_normalized je už lowercase
  ```
- **Nikdy nepoužívat `name_with_titles.ilike(search)` jako hlavní vyhledávání jmen** — selže pro české znaky. Vždy `name_normalized.like(search_ascii)`.
- **Stejný vzor pro EmailLog**: `EmailLog.name_normalized` slouží pro diacritics-insensitive hledání v historii emailů (nastavení stránka)

## Jména vlastníků

- **Zobrazení**: vždy `owner.display_name` (property na modelu Owner) — formát „titul příjmení jméno"
- **DB sloupec** `name_with_titles` zůstává pro index — nepoužívat v šablonách ani pro vyhledávání
- **Hledání** v SQL: `Owner.name_normalized.like(search_ascii)` — viz sekce Vyhledávání výše
- **Řazení**: `owner.name_normalized` (příjmení-first, bez diakritiky, lowercase)
- **Import dat**: `build_name_with_titles()` z `app/utils.py` generuje příjmení-first formát

## Import hlasování — spoluvlastnictví (SJM)

- Párování Excel řádků na lístky probíhá přes číslo jednotky
- Pokud Excel řádek **má hlasy** → párovat na VŠECHNY lístky, jejichž vlastník sdílí tu jednotku (SJM, spoluvlastnictví)
- Pokud Excel řádek **nemá hlasy** → párovat jen na první nalezený lístek (bez rozšíření)
- Každý spoluvlastník dostane hlasy se svým vlastním `total_votes`
- Deduplikace přes `seen_ballots` — stejný lístek se nezpracuje dvakrát

## SQLAlchemy vzory

- Projekt používá **SQLite** (`data/svj.db`) s `check_same_thread=False`
- `DeclarativeBase` z SQLAlchemy 2.0 pro modely, ale **legacy query API** (`db.query()`) pro všechny dotazy — nepřecházet na `select()` style
- `db.query(Model).get(id)` pro PK lookup, `.filter_by(...).first()` pro složitější dotazy
- `case()` se importuje přímo ze `sqlalchemy`, ne přes `func.case()`
- `func.coalesce(field, "")` pro seskupování NULL a prázdných řetězců (např. ownership_type)
- `func.distinct()` v agregacích pro počítání unikátních záznamů
- `joinedload()` pro eager loading relací (předchází N+1 queries)
- Číslo jednotky (`unit_number`) je INTEGER (ne string)
- **Pozor:** `TaxDocument.unit_number` a `SyncRecord.unit_number` jsou `String(20)` (historicky z PDF/CSV). Při ORDER BY VŽDY `cast(col, Integer)`, při Python sort VŽDY `int(x)` s try/except fallback na 0

### Modely — konvence

- Enumy dědí z `(str, enum.Enum)`, členové UPPERCASE, hodnoty lowercase anglicky: `DRAFT = "draft"`
- Timestamp sloupce: editovatelné entity mají `created_at` + `updated_at` s `onupdate=utcnow`. Logy mají pouze `created_at`. Column defaults/onupdate používají `utcnow` z `app.utils`, explicitní přiřazení v routerech/services také `utcnow()`. Speciální: `Payment.notified_at` — nullable timestamp kdy bylo odesláno upozornění na nesrovnalost
- Cascade: parent→child relace `cascade="all, delete-orphan"`, child→parent plain `back_populates`
- Každý nový model/enum přidat do importů i `__all__` v `app/models/__init__.py`. Routery importují z `app.models`, nikdy z `app.models.specific_file`

### Databázové indexy

- Každý FK sloupec (`*_id`) musí mít `index=True` v modelu
- Sloupce používané ve filtrech (`status`, `group`, `module`, `import_type`) musí mít `index=True`
- **SQLAlchemy `create_all()` NEPŘIDÁ indexy na existující tabulky** — pouze na nově vytvořené
- Pro přidání indexů na existující tabulky: `CREATE INDEX IF NOT EXISTS` v `_ensure_indexes()` funkci v `main.py`
- Při přidání nového `index=True` do modelu VŽDY přidat i odpovídající `CREATE INDEX IF NOT EXISTS` do `_ensure_indexes()`

## Router vzory

> Viz **[docs/ROUTER_PATTERNS.md](docs/ROUTER_PATTERNS.md)** — boilerplate, PRG, flash zprávy, HTMX partials, TemplateResponse API, řazení, validace, duplicity, tenants dedup.

## Nové moduly / entity + Export dat

> Viz **[docs/NEW_MODULE_CHECKLIST.md](docs/NEW_MODULE_CHECKLIST.md)** — checklist nového modulu, wizard stepper, progress bar, export (Excel/CSV), filename suffix logika.

## Mazání dat (purge)

- Kategorie nejsou jen DB modely — mohou být i souborové (zálohy = ZIP soubory, historie obnovení = JSON soubor)
- Pro souborové kategorie: `_purge_counts()` počítá soubory na disku, `purge_data()` maže soubory/složky
- Pořadí mazání (`_PURGE_ORDER`) respektuje závislosti — FK reference se mažou první

## Upload souborů

- Ukládání: `{YYYYMMDD_HHMMSS}_{original_filename}` do podadresáře `settings.upload_dir`
- Podadresáře: `excel/`, `word_templates/`, `scanned_ballots/`, `tax_pdfs/`, `csv/`, `share_check/`, `contracts/`, `water_meters/`
- Zápis přes `shutil.copyfileobj(file.file, f)` + `dest.parent.mkdir(parents=True, exist_ok=True)`
- Multi-step import workflow: Upload → Mapování → Preview → Confirm. Cesta k souboru se předává jako hidden field, ne přes session
- **Dynamické mapování sloupců** pro importy vlastníků a kontaktů: `import_mapping.py` service definuje pole, auto-detekci z hlaviček a validaci. Uložené mapování v `SvjInfo.owner_import_mapping` / `contact_import_mapping` (JSON). Sdílené UI: `partials/import_mapping_fields.html` (Jinja2 macro) + `partials/import_mapping_js.html` (sdílený JS)
- **Import wizard stepper**: Všechny import workflows (vlastníci, kontakty, hlasování, zůstatky) používají sdílený kruhový `wizard_stepper.html` (stejný design jako rozesílka). Router předává kontext přes `**build_import_wizard(step)` z `app/utils.py` — vrací `wizard_steps`, `wizard_current`, `wizard_total`

## Mazání entit se soubory

- Při smazání entity s `*_path` sloupci: `try: Path(path).unlink() except Exception: pass`
- Selhání file cleanup nikdy neblokuje DB delete

## Service layer

- Služby jsou **plain funkce** (ne třídy), přijímají `db: Session` jako parametr od routeru
- Vrací plain dict/list (žádné custom result třídy)
- Nikdy nevytvářejí DB session — vždy přijímají z volajícího
- **Výjimka:** `payment_discrepancy.py` používá `@dataclass Discrepancy` místo DB modelu — nesrovnalosti se neperzistují, pouze se počítají on-the-fly z dat výpisu

## Utility funkce (`app/utils.py`)

- `strip_diacritics(text)` — odstraní diakritiku a převede na lowercase (pro vyhledávání)
- `fmt_num(value)` — formátuje čísla s oddělovači tisíců (registrován jako Jinja2 filtr `fmt_num`)
- `build_list_url(request)` — sestaví URL aktuální stránky s query parametry pro `list_url`
- `is_htmx_partial(request)` — `True` pokud request je HTMX ale NE boosted (pro partial odpovědi)
- `is_safe_path(path, allowed_dirs)` — validace cesty proti path traversal
- `UPLOAD_LIMITS` — dict centralizovaných upload limitů (`max_size_mb`, `allowed_extensions`). Klíče: `excel`, `csv`, `csv_xlsx`, `pdf`, `docx`, `backup`, `db`, `folder`
- `async validate_upload(file, max_size_mb, allowed_extensions)` — validace nahraného souboru (přípona, velikost). Volání: `await validate_upload(file, **UPLOAD_LIMITS["excel"])`
- `async validate_uploads(files, max_size_mb, allowed_extensions)` — validace seznamu souborů (vrací první chybu)
- `is_valid_email(email)` — základní regex validace emailového formátu
- `excel_auto_width(ws, max_width=45)` — auto-šířka sloupců v openpyxl worksheet (pro Excel exporty)
- `compute_eta(current, total, started_at)` — výpočet progrese (%), uplynulého času a ETA textu. Vrací dict `{pct, elapsed, eta}`
- `build_wizard_steps(step_defs, current_step, max_done, sending_step=None)` — společná logika wizard stepperu (voting + tax)
- `build_import_wizard(current_step)` — vrací wizard kontext pro import workflows (4 kroky: Nahrání → Mapování → Náhled → Výsledek)
- `build_name_with_titles(title, first_name, last_name)` — sestaví zobrazovací jméno: titul + příjmení + jméno
- `setup_jinja_filters(templates)` — registrace custom Jinja2 filtrů (aktuálně `fmt_num`) na Jinja2Templates instanci
- `utcnow()` — naive UTC datetime, náhrada za deprecated `datetime.utcnow()` (Python 3.12+)
- `flash_from_params(request, flash_map, **extra_ctx)` — čte `?flash=` z URL, vrací `(message, type)` z mapy. Šablona zprávy může mít `{placeholder}` z query params nebo extra_ctx. Použití: `flash_message, flash_type = flash_from_params(request, {"ok": ("Hotovo.", "success")})`
- `render_email_template(template_str, context)` — renderuje Jinja2 email šablonu s kontextem (pro platební upozornění). Neznámé proměnné se renderují jako prázdný řetězec
- `encode_smtp_password(plain)` / `decode_smtp_password(stored)` — Fernet šifrování/dešifrování SMTP hesel (klíč v `data/.smtp_key`). Zpětně kompatibilní s legacy base64
- `get_invalid_emails(db)` — vrací set neplatných emailů (na základě hard bounces)
- `templates` — sdílená `Jinja2Templates` instance s registrovanými filtry (singleton pro celý projekt)

## JavaScript

- Stránkový JS jde do `<script>` na konci `{% block content %}` — ne do separátních `.js` souborů. **Výjimka:** sdílený JS pro více stránek se stejnou logikou může být v Jinja2 partial (`{% include "partials/import_mapping_js.html" %}`) místo duplikace — viz import mapping
- Vanilla JS only (žádný jQuery, žádné external knihovny kromě HTMX)
- `/static/js/app.js` pro HTMX globální handlery, dark mode toggle, custom confirm modal (`svjConfirm`), focus trap + focus restore v modalech, `beforeunload` varování (`data-warn-unsaved`), scroll position save/restore, client-side sort (`sortTableCol`), auto-dismiss flash zpráv
- Jinja2 macro je OK pro opakující se UI struktury v rámci jedné šablony, pokud všechna data přijdou jako parametry macro
- **`<script>` tagy v HTML vloženém přes `innerHTML` se NESPUSTÍ** — prohlížeč je ignoruje. HTMX (`hx-swap`) naopak skripty vyhodnotí. Pokud je nutné fetch + innerHTML, definovat funkce v nadřazené šabloně.

## Technologie

- Tailwind CSS z CDN (`cdn.tailwindcss.com`) — žádný build pipeline
- HTMX z CDN (`unpkg.com`)
- Custom CSS: `custom.css` (HTMX animace), `dark-mode.css` (dark mode override)
- Vše stylováno přes Tailwind utility classes
- Dark mode — přepínač v sidebaru, detaily viz [UI_GUIDE.md § 19](docs/UI_GUIDE.md)

## Global exception handlers

- **IntegrityError** → HTTP 409 „Konflikt dat" (logged warning)
- **OperationalError** → HTTP 500 „Chyba databáze" (logged error)
- **404 Not Found** → custom `error.html` šablona
- **500 Server Error** → custom `error.html` šablona
- Handlery v `main.py`, šablona `app/templates/error.html`

## Security headers

- Middleware v `main.py` přidává bezpečnostní hlavičky ke každé odpovědi:
  - `X-Frame-Options: DENY` — prevence clickjacking
  - `X-Content-Type-Options: nosniff` — prevence MIME sniffing
  - `Referrer-Policy: strict-origin-when-cross-origin`

## Router packages

- Komplexní routery (1500+ řádků) se dělí na package: `app/routers/modul/`
- Struktura: `__init__.py` (kombinuje sub-routery), `_helpers.py` (sdílené funkce), logické sub-moduly
- `__init__.py`: vlastní `APIRouter()` + `include_router(sub_router)` pro každý sub-modul
- `main.py` import zůstává beze změny (`from app.routers import modul`)
- Příklady:
  - `owners/` — `crud.py`, `import_owners.py`, `import_contacts.py`, `_helpers.py`
  - `voting/` — `session.py`, `ballots.py`, `import_votes.py`, `_helpers.py`
  - `tax/` — `session.py`, `processing.py`, `matching.py`, `sending.py`, `_helpers.py`
  - `payments/` — `prescriptions.py`, `symbols.py`, `statements.py`, `balances.py`, `overview.py`, `settlement.py`, `discrepancies.py`, `_helpers.py`
  - `spaces/` — `crud.py`, `import_spaces.py`, `_helpers.py`
  - `tenants/` — `crud.py`, `_helpers.py`
  - `administration/` — `info.py`, `board.py`, `code_lists.py`, `backups.py`, `bulk.py`, `_helpers.py`
  - `sync/` — `session.py`, `contacts.py`, `exchange.py`, `_helpers.py`
  - `water_meters/` — `overview.py`, `import_readings.py`, `sending.py`, `_helpers.py`
- Standalone routery (ne packages): `dashboard.py`, `units.py`, `share_check.py`, `settings_page.py`, `bounces.py`

## Startup (lifespan)

- `main.py` lifespan: (1) import modelů, (2) `create_all`, (3) `_ALL_MIGRATIONS` list (28 migračních funkcí + `_ensure_indexes()` + `_seed_code_lists()` + `_seed_email_templates()` = 31 položek), (4) `recover_stuck_sending_sessions()`, (5) vytvoření upload/generated/temp adresářů
- Migrace zahrnují mj. `_migrate_svj_send_settings` (SvjInfo send_batch_size/interval/confirm/test_email), `_migrate_payment_notified_at` (Payment.notified_at sloupec) a `_migrate_dedupe_tenants` (sloučí duplicitní Tenant záznamy podle priority owner_id → RČ → IČ → jméno+typ; vítěz = nejvíce vyplněných polí, SpaceTenant vztahy se přesunou na vítěze)
- `_ALL_MIGRATIONS` se sdílí s `run_post_restore_migrations()` — po obnově zálohy se spustí stejné migrace
- Nové funkce vyžadující adresáře: přidat do lifespan. Nové indexy: přidat do `_ensure_indexes()`. Nové migrace: přidat do `_ALL_MIGRATIONS`

## Nasazení na USB (jiný počítač)

- Projekt se spouští přes `spustit.command` (macOS) — dvakrát kliknout ve Finderu
- Skript automaticky: zkontroluje Python, vytvoří `.venv`, nainstaluje závislosti, spustí aplikaci, otevře prohlížeč
- **Wheels (offline balíčky) jsou vázané na verzi Pythonu** — pokud má cílový počítač jinou verzi Pythonu, wheels nebudou fungovat a skript stáhne balíčky online
- `.venv/` se NIKDY nekopíruje na USB — obsahuje absolutní cesty a je nepřenositelná
- Skript automaticky ověří existující `.venv/` — pokud chybí uvicorn (poškozená/neúplná instalace), smaže ji a vytvoří znovu
- Skript používá `"$VENV_DIR/bin/python" -m uvicorn` místo holého `uvicorn` — zajistí správnou cestu k binárce
- Skript používá `"$VENV_DIR/bin/pip"` místo holého `pip` — zajistí instalaci do správného venv
- Požadavky na cílovém počítači: **Python 3.9+** (ověřit `python3 --version`), volitelně LibreOffice pro PDF lístky
- Pro přenos dat: zkopírovat `data/svj.db` a `data/uploads/` na USB

## Workflow

- **Odhad doby** — před začátkem úkolu sdělit uživateli odhadovaný čas (např. "Toto zabere ~5 minut"). U agentů viz tabulka v ORCHESTRATOR.md
- Po dokončení změn: commit + push (pokud uživatel požádá)
- **KONTROLNÍ BOD po každém `git push`** — push NENÍ konec úkolu. Povinný checklist před dalším krokem:
  1. Přidal jsem / změnil endpoint, feature, chování? → **README.md update**
  2. Změnil jsem konvenci, workflow, vzor? → **CLAUDE.md nebo UI_GUIDE.md update**
  3. Audit / větší dávka oprav? → **changelog sekce v README**
  Pokud ANO na kteroukoliv otázku → okamžitě druhý commit `docs: ...` + push, **bez ptaní, bez čekání na pobídku**. Pokud NE → explicitně si to v hlavě ověřit, ne přeskočit krok. Porušení tohoto pravidla = chyba, kterou uživatel nemusí hlídat
- Commit message v češtině, stručný, popisuje "co a proč"
- **Úklid po testování**: po použití Playwright (browser_navigate, browser_snapshot, browser_take_screenshot) smazat soubory v `.playwright-mcp/` — `rm -rf .playwright-mcp/*.log .playwright-mcp/*.png .playwright-mcp/*.jpeg` — a také testovací screenshoty z kořenového adresáře: `rm -f *.png *.jpeg`
- **Dokumentace — jeden zdroj pravdy**: UI vzory → `docs/UI_GUIDE.md`, backend pravidla → `CLAUDE.md`, projektová dokumentace → `README.md`. Při změně/přidání vzoru zapsat na jedno místo, z ostatních jen odkázat. Při přejmenování modulu/funkce projít VŠECHNY tři soubory

## Komunikace s uživatelem

- **UI rozhodnutí s více přístupy**: nabídnout 2–3 mockupy (přes AskUserQuestion s markdown preview) místo rovnou implementovat první nápad. Ušetří čas — přepsat template je dražší než ukázat mockup
- NEPTÁT SE na přístup/implementaci, pokud je vzor již zavedený v projektu — použít existující vzor
- Pokud uživatel řekne "commit this and push" — udělat commit a push bez dalších otázek
- Pokud uživatel řekne "dokumentaci" — aktualizovat README.md bez ptaní se co přidat
- Být proaktivní: když vytvářím novou stránku/entitu, rovnou aplikovat VŠECHNA pravidla z tohoto souboru a [UI_GUIDE.md](docs/UI_GUIDE.md) bez čekání na připomínku
- Komunikovat stručně — co jsem udělal, ne co bych mohl udělat
- Na potvrzení se PTÁT — "Chceš commitnout?", "Chceš něco upravit?" atd. jsou v pořádku
- **Po opravě chyby se VŽDY zeptat**, zda se nemá stejný problém zkontrolovat v celém projektu — stejná chyba se často opakuje na více místech
- **Prezentace nálezů a doporučení** — každý nález/doporučení MUSÍ obsahovat:
  1. **Co a kde**: stručný popis problému + kde v aplikaci (URL, stránka, akce)
  2. **Řešení**: jak to opravit (konkrétní postup, ne vágní "vylepšit")
  3. **Varianty**: pokud existuje víc přístupů, nabídnout je s pro/proti
  4. **Náročnost + čas**: odhadovaná složitost (nízká/střední/vysoká) a čas (~5 min, ~30 min, ~2 hod)
  5. **Závislosti**: závisí oprava na jiném nálezu? "Nejdřív oprav X, pak Y"
  6. **Regrese riziko**: může oprava rozbít něco jiného? (nízké/střední/vysoké)
  7. **Rozhodnutí potřeba**: 🔧 (jen opravit) vs ❓ (potřeba rozhodnutí uživatele)
  8. **Jak otestovat**: polopatický postup krok za krokem (URL → klik → očekávaný výsledek)
- **Při zápisu dat do evidence (update, exchange, import, checkbox aktualizace) VŽDY aktivně testovat všechny kombinace scénářů:**
  - 1 vlastník → 1 vlastník (přepis)
  - 1 vlastník → N vlastníků (přidání spoluvlastníků)
  - N vlastníků → 1 vlastník (odebrání spoluvlastníků)
  - N vlastníků → M vlastníků (částečná shoda, částečná výměna)
  - Reuse vlastník (už na jednotce) vs nový vlastník vs vlastník z jiné jednotky
  - Ověřit že se propisují VŠECHNA relevantní pole všem dotčeným záznamům (ownership_type, space_type, podíl, jméno)
  - Výstup analýzy scénářů nabízet uživateli při každé změně v datové logice

## Uživatelské role — plán implementace (na konec)

> Viz **[docs/USER_ROLES.md](docs/USER_ROLES.md)** — role (admin/board/auditor/owner), matice oprávnění, technické řešení, postup implementace.
> Pravidlo: **NEPOUŽÍVAT hardcoded admin logiku** — destruktivní akce přes `data-confirm`/`hx-confirm`, nové moduly navrhovat pro `require_role()`.

---

## Pravidla pro práci na úkolech

### Vždy dodržuj tento postup:

1. **Přečti CLAUDE.md** a pochop strukturu projektu
2. **Analyzuj** současný stav relevantních souborů
3. **Pokud ti něco není jasné — ZEPTEJ SE**, nedomýšlej si. Používej **AskUserQuestion** s roletovými menu a checkboxy místo volných otázek v textu — uživatel vybere z nabídky místo psaní.
4. **Ukaž strukturovaný plán** přes update_plan tool (co budeš měnit, které soubory, jak)
5. **UI změny — ukaž mockup** před implementací (ASCII wireframe současného a navrhovaného stavu):
   ```
   Současný stav:
   ┌──────────────────────────┐
   │ [jak to vypadá teď]      │
   └──────────────────────────┘

   Navrhovaný stav:
   ┌──────────────────────────┐
   │ [jak to bude vypadat]    │
   └──────────────────────────┘
   ```
6. **POČKEJ NA SCHVÁLENÍ** — neimplementuj dokud uživatel neschválí plán
6. **Implementuj** po schválení
7. **Ověř** že existující funkce stále fungují (spusť server, otestuj dotčené stránky)
8. **Otestuj rovnou přes Playwright** — NEPTAT SE, rovnou projet dotčené stránky (browser_navigate → browser_snapshot → kliknout na klíčové prvky: bubliny, export linky, search, HTMX swap). curl testuje jen HTTP status, neověří UI interakce, HTMX delay, vizuální konzistenci, ani zda tlačítka reálně něco dělají. **curl = sanity check, Playwright = skutečný test.** Pro každou stránku s daty otestovat alespoň: (a) načtení + snapshot bez chyb v konzoli, (b) kliknutí na jednu z bublin/filtrů, (c) vyplnění search (pokud existuje HTMX search), (d) kliknutí na export (ověřit stažení souboru + název). Po testování smazat soubory v `.playwright-mcp/` (screenshoty, logy, stažené soubory) a testovací screenshoty z kořene
9. **Vyžádej si potvrzení pro commit** — ukaž co se změnilo a zeptej se "Mám commitnout?"
10. **Commitni** každý úkol zvlášť s výstižnou českou commit message
11. Pokud měníš strukturu projektu → **aktualizuj CLAUDE.md**

### Na konci každého úkolu vypiš:
- Co jsi změnil (soubory + stručný popis)
- Co má uživatel otestovat (konkrétní URL a kroky)
- Jestli je potřeba restart serveru

### Při více úkolech:
- Dělej úkoly JEDEN PO DRUHÉM (ne všechny najednou)
- Po každém úkolu commitni zvlášť
- Na konci vypiš souhrnnou tabulku:

| # | Úkol | Stav | Změněné soubory | Co otestovat |
|---|------|------|-----------------|--------------|

### Striktní pravidla:
- **Piš česky**
- **Nedělej víc než je zadáno**
- **Nedomýšlej si požadavky** — radši se zeptej
- **Neměň nesouvisející kód** — i když vidíš problém, pouze ho nahlas
