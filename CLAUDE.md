# SVJ Projekt — pravidla pro vývoj

> **UI/frontend konvence** (layout, tabulky, formuláře, tlačítka, bubliny, badge, ikony, inline editace, HTMX vzory, formátování, back URL navigace, checkboxy, kolapsovatelné sekce) jsou v **[docs/UI_GUIDE.md](docs/UI_GUIDE.md)**.
> Tento soubor definuje backend pravidla, datový model, routery, workflow a projektová specifika.

## Obsah

- [URL konvence](#url-konvence) · [Navigace a back URL](#navigace-a-back-url) · [Tabulky — povinný checklist](#tabulky--povinný-checklist) · [Procentuální vstupy](#procentuální-vstupy-kvórum-podíly) · [Statistiky podílů](#statistiky-podílů) · [Dashboard](#dashboard) · [Vyhledávání](#vyhledávání) · [Jména vlastníků](#jména-vlastníků) · [Import hlasování — SJM](#import-hlasování--spoluvlastnictví-sjm) · [SQLAlchemy vzory](#sqlalchemy-vzory) · [Router vzory](#router-vzory) · [Nové moduly / entity](#nové-moduly--entity) · [Export dat](#export-dat-excel--csv) · [Mazání dat](#mazání-dat-purge) · [Upload souborů](#upload-souborů) · [Service layer](#service-layer) · [Utility funkce](#utility-funkce-apputilspy) · [JavaScript](#javascript) · [Technologie](#technologie) · [Global exception handlers](#global-exception-handlers) · [Router packages](#router-packages) · [Startup](#startup-lifespan) · [Nasazení na USB](#nasazení-na-usb-jiný-počítač) · [Workflow](#workflow) · [Komunikace](#komunikace-s-uživatelem) · [Uživatelské role](#uživatelské-role--plán-implementace-na-konec) · [Pravidla pro práci](#pravidla-pro-práci-na-úkolech)

## URL konvence

- Všechny URL cesty používají **české slugy bez diakritiky**: `/vlastnici`, `/jednotky`, `/hlasovani`, `/dane`, `/synchronizace`, `/sprava`, `/nastaveni`
- Sub-endpointy: `/nova` (create), `/smazat` (delete), `/upravit` (edit), `/pridat` (add), `/potvrdit` (confirm), `/odebrat` (remove), `/exportovat` (export), `/aktualizovat` (update)
- Nikdy nepoužívat angličtinu v URL cestách

## Navigace a back URL

- Každý odkaz z dashboardu na seznam/modul musí obsahovat `?back=/`
- Každý odkaz ze seznamu na detail musí obsahovat `?back={{ list_url|urlencode }}`
- `list_url` se vždy buduje v routeru z `request.url` (path + query), aby zachytil všechny filtry:
  ```python
  list_url = str(request.url.path)
  if request.url.query:
      list_url += "?" + str(request.url.query)
  ```
- Parametr `back` se musí propagovat přes:
  - filtrační bubliny (v query string proměnných `_base`, `_base2`, `_ubase` atd.)
  - HTMX hledání a filtry (hidden input `<input type="hidden" name="back">` + přidání `[name='back']` do `hx-include`)
  - řadící odkazy v hlavičkách sloupců
  - `_back` helper proměnná v šabloně: `{% set _back = "&back=" ~ (back_url|default('')|urlencode) if back_url else "" %}`
- Detailová stránka vždy přijímá `back` query parametr a zobrazuje šipku zpět
- **Detailová stránka s vlastními filtry/bublinami** (např. sync compare, voting ballots): bubliny a sort odkazy musí propagovat `back` stejně jako na seznamových stránkách — jinak se po kliknutí na filtr/řazení ztratí šipka zpět
- **HTMX inline edit partials (`upravit-formular`, `info`) NEPOTŘEBUJÍ `back` parametr** — swapují obsah uvnitř stránky, uživatel neodchází. Back URL řeší nadřazená detail stránka, ne vnořené partials
- Při vícenásobném zanoření (seznam → detail → detail) se back URL řetězí: `?back={{ ('/aktualni/url?back=' ~ (back_url|urlencode))|urlencode }}`
- Back label se nastavuje dynamicky podle cílové URL pomocí řetězených `if/elif` s `in` nebo `.startswith()`:
  ```python
  back_label = (
      "Zpět na hromadné úpravy" if "/sprava/hromadne" in back
      else "Zpět na detail jednotky" if "/jednotky/" in back
      else "Zpět na seznam jednotek" if back.startswith("/jednotky")
      else "Zpět na porovnání" if "/synchronizace/" in back
      else "Zpět na hlasovací lístek" if "/hlasovani/" in back
      else "Zpět na nastavení" if back.startswith("/nastaveni")
      else "Zpět na seznam vlastníků"
  )
  ```
- `list_url` = URL aktuální stránky s query parametry (pro odkazy na detail, teče dopředu). `back_url` = příchozí `back` parametr (pro šipku zpět, teče dozadu). Nikdy nezaměňovat
- Pokud stránka má expandovatelné řádky (např. hromadné úpravy), back URL musí obsahovat i identifikátor rozbalené položky (např. `&hodnota=SJM`)
- Cílová stránka pak automaticky rozbalí odpovídající řádek pomocí skriptu:
  ```javascript
  var hodnota = new URLSearchParams(window.location.search).get('hodnota');
  if (hodnota) { /* najít a kliknout na řádek s data-hodnota == hodnota */ }
  ```
- **Obnova scroll pozice při návratu** — viz [UI_GUIDE.md § 13](docs/UI_GUIDE.md). Shrnutí: řádky mají `id`, back URL obsahuje `#hash`, stránka volá `scrollIntoView`
- **Kontrola při přidání `<a href>` na entitu** — VŽDY ověřit 3 věci: (1) odkaz má `?back=`, (2) router předává `list_url` do kontextu, (3) cílová stránka má odpovídající `back_label` větev

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

- Klikací entity vyžadují eager loading relací v routeru:
  ```python
  joinedload(Ballot.owner).joinedload(Owner.units).joinedload(OwnerUnit.unit)
  ```
- Bez eager loading `current_units` vrátí prázdný list (lazy loading selže mimo session) nebo způsobí N+1 dotazy
- Při přidání nového klikacího sloupce do tabulky VŽDY zkontrolovat, zda router má potřebný `joinedload()`
- **Tento checklist platí i při čistě vizuálních úpravách** (kompaktnější layout, přesunutí prvků) — nikdy neodeslat stránku s tabulkou bez všech 7 bodů
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

- 4 stat karty v jednom řádku: vlastníci, jednotky, hlasování, rozesílání
- Jednoduché karty (vlastníci, jednotky) — celá karta je `<a>` tag
- Karty se sub-odkazy (hlasování, rozesílání) — `<div>` wrapper s hlavním `<a>` a per-status linky uvnitř
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
- Timestamp sloupce: editovatelné entity mají `created_at` + `updated_at` s `onupdate=datetime.utcnow`. Logy mají pouze `created_at`. Vždy `datetime.utcnow`
- Cascade: parent→child relace `cascade="all, delete-orphan"`, child→parent plain `back_populates`
- Každý nový model/enum přidat do importů i `__all__` v `app/models/__init__.py`. Routery importují z `app.models`, nikdy z `app.models.specific_file`

### Databázové indexy

- Každý FK sloupec (`*_id`) musí mít `index=True` v modelu
- Sloupce používané ve filtrech (`status`, `group`, `module`, `import_type`) musí mít `index=True`
- **SQLAlchemy `create_all()` NEPŘIDÁ indexy na existující tabulky** — pouze na nově vytvořené
- Pro přidání indexů na existující tabulky: `CREATE INDEX IF NOT EXISTS` v `_ensure_indexes()` funkci v `main.py`
- Při přidání nového `index=True` do modelu VŽDY přidat i odpovídající `CREATE INDEX IF NOT EXISTS` do `_ensure_indexes()`

## Router vzory

### Boilerplate
- Každý router: `router = APIRouter()` + `templates = Jinja2Templates(directory="app/templates")`
- Žádné prefixy na `APIRouter()` — všechny prefixy v `main.py` přes `include_router(prefix=...)`
- Každý `TemplateResponse` musí obsahovat `"active_nav": "module_key"` pro zvýraznění sidebaru

### POST-Redirect-GET (PRG)
- Všechny POST endpointy po mutaci: `RedirectResponse(url, status_code=302)` pro non-HTMX requesty
- Pro HTMX requesty: vrací partial šablonu místo redirectu
- Vždy `status_code=302`, nikdy 303 nebo 301

### Entity not found → redirect
- Když `db.query(Model).get(id)` vrátí `None`: `RedirectResponse("/seznam", status_code=302)`
- Nikdy `HTTPException(404)` — uživatel je tiše přesměrován na seznam

### Flash zprávy
- Předávají se jako `flash_message` + `flash_type` (`"error"`, `"warning"`, nebo default zelená) v kontextu šablony
- Pro zprávy přes redirect: query parametry (např. `?chyba=prazdna`)
- Projekt NEPOUŽÍVÁ session-based flash messaging

### HTMX partial odpovědi
- Router rozlišuje HX-Request vs HX-Boosted — boosted navigace dostává plnou stránku:
  ```python
  from app.utils import is_htmx_partial

  if is_htmx_partial(request):
      return templates.TemplateResponse("partial.html", ctx)
  return templates.TemplateResponse("full_page.html", ctx)
  ```
- Partial = jen `<tr>` řádky (tbody-only), hlavní šablona dělá `{% include "partial.html" %}` uvnitř `<tbody id="...">`

### Řazení — `SORT_COLUMNS` dictionary
- Modul-level `SORT_COLUMNS` dict mapující sort parametry na SQLAlchemy sloupce (nebo `None` pro Python-side sort)
- SQL sorty vždy s `.nulls_last()`
- Python-side sort: `items.sort(key=lambda x: ..., reverse=(order == "desc"))`

### Helper funkce v routerech
- Interní helper funkce mají prefix `_` (např. `_ballot_stats`, `_purge_counts`)
- Vrací dict, který se rozbalí do template kontextu: `**_ballot_stats(voting)`
- Typické helpery: `voting.has_processed_ballots` (model property), `_voting_wizard(voting, step)` / `_tax_wizard(...)` (wizard stepper kontext)
- Validační funkce v service vrstvě: `validate_mapping(mapping)` → `str | None` (chybová zpráva nebo None)

### Dynamické formuláře
- `Form(...)` pro fixní pole. `await request.form()` + `.get()`/`.getlist()` pro dynamické názvy polí (např. `vote_5`, `update__12__field`)

## Nové moduly / entity

- Musí dodržovat VŠECHNY vzory od začátku:
  - Back URL navigace (router `back` param + `list_url` + šipka zpět v šabloně)
  - UI vzory z [UI_GUIDE.md](docs/UI_GUIDE.md) (bubliny, sticky hlavičky, formátování, badge, ikony, inline editace)
  - HTMX partial odpovědi
- **Modul s více stránkami** (např. hlasování: detail, lístky, zpracování, neodevzdané):
  - Sdílený header jako partial (`_modul_header.html`) — stejný nadpis, bubliny, tlačítka na VŠECH stránkách
  - Aktivní bublina zvýrazněna `ring-2 ring-{color}-400`
  - Router: sdílená helper funkce pro výpočet dat bublin (volat ve všech endpointech)
  - Šablona předává `active_bubble` do partialu pro zvýraznění
- **Wizard stepper** — vícekrokový workflow (hlasování, rozesílání):
  - Router helper `_voting_wizard(voting, current_step)` vrací dict s `wizard_steps`, `wizard_current`, `wizard_label`
  - Router helper `_tax_wizard(...)` vrací dict s `wizard_steps`, `wizard_current`, `wizard_total` (bez `wizard_label`)
  - Plná varianta: `partials/wizard_stepper.html` — samostatný stepper nad obsahem
  - Kompaktní varianta: `partials/wizard_stepper_compact.html` — inline v kartě na seznamu
  - Stavy kroků: `done` (zelená), `active` (zelená), `current+done` (tmavší zelená s ring efektem), `pending` (šedá), `sending` (oranžová pulzace)
- Registrace v `app/main.py` (`include_router`)
- Export modelů v `app/models/__init__.py`
- Odkaz v sidebar (`base.html`) s `active_nav` kontrolou
- Přidání do README.md (popis modulu + API endpointy)
- Odkaz v sidebaru (`base.html`): sekce Moduly (doménové funkce), Systém (admin/config). Ikona `w-4 h-4 mr-2` SVG + text label

## Export dat (Excel + CSV)

- Export musí vždy odrážet **aktuální filtrovaný pohled** — ne všechna data
- Filtr se přenáší přes hidden input ve formuláři: `<input type="hidden" name="filtr" value="{{ filtr }}">`
- Export endpoint aplikuje **stejnou logiku filtrování** jako zobrazovací endpoint
- **Excel**: generování přes `openpyxl` (ne pandas): bold hlavička (`Font(bold=True)`), auto-width sloupců (max 45 znaků), žlutá `PatternFill` pro zvýraznění rozdílů. Response: `media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"`
- **CSV**: UTF-8 s BOM (`\ufeff` na začátku), středník jako oddělovač. Response: `media_type="text/csv; charset=utf-8"`, filename `{modul}_YYYYMMDD.csv`
- **Název souboru musí odrážet aktivní filtr/bublinu**:
  - Formát: `{modul}_{suffix}_{YYYYMMDD}.{fmt}` (s ID entity: `{modul}_{id}_{suffix}_{YYYYMMDD}`)
  - Suffix = český popis aktivního filtru bez diakritiky. Bez filtru = `_vsichni` / `_vsechny` / `_vse`
  - Suffixový dict se definuje přímo v export endpointu: `typ_labels = {"physical": "fyzicke", "legal": "pravnicke"}`
  - Logika: vzít **první neprázdný filtr** (priorita: typ → kontakt → stav → vlastnictví → sekce → hledání), přidat odpovídající suffix
  - Příklady: `vlastnici_fyzicke_20260309.xlsx`, `jednotky_sekce_A_20260309.csv`, `hlasovani_1_nezpracovane_20260309.xlsx`, `porovnani_rozdily_20260309.xlsx`
  - **Nikdy nepoužívat diakritiku v názvu** — HTTP `Content-Disposition` header kóduje latin-1
  - **Při přidání nového exportu s bublinami/filtry VŽDY přidat suffix logiku** — uživatel musí z názvu souboru poznat, co exportoval
- **Upload limity**: centralizované v `UPLOAD_LIMITS` dict v `app/utils.py`. Volání: `validate_upload(file, **UPLOAD_LIMITS["excel"])`. Při přidání nového uploadu přidat klíč do `UPLOAD_LIMITS`
- Formulář exportu musí mít `hx-boost="false"` (viz [UI_GUIDE.md § 14](docs/UI_GUIDE.md))

## Mazání dat (purge)

- Kategorie nejsou jen DB modely — mohou být i souborové (zálohy = ZIP soubory, historie obnovení = JSON soubor)
- Pro souborové kategorie: `_purge_counts()` počítá soubory na disku, `purge_data()` maže soubory/složky
- Pořadí mazání (`_PURGE_ORDER`) respektuje závislosti — FK reference se mažou první

## Upload souborů

- Ukládání: `{YYYYMMDD_HHMMSS}_{original_filename}` do podadresáře `settings.upload_dir`
- Podadresáře: `excel/`, `word_templates/`, `scanned_ballots/`, `tax_pdfs/`, `csv/`
- Zápis přes `shutil.copyfileobj(file.file, f)` + `dest.parent.mkdir(parents=True, exist_ok=True)`
- Multi-step import workflow: Upload → Preview → Confirm. Cesta k souboru se předává jako hidden field, ne přes session

## Mazání entit se soubory

- Při smazání entity s `*_path` sloupci: `try: Path(path).unlink() except Exception: pass`
- Selhání file cleanup nikdy neblokuje DB delete

## Service layer

- Služby jsou **plain funkce** (ne třídy), přijímají `db: Session` jako parametr od routeru
- Vrací plain dict/list (žádné custom result třídy)
- Nikdy nevytvářejí DB session — vždy přijímají z volajícího

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
- `build_name_with_titles(title, first_name, last_name)` — sestaví zobrazovací jméno: titul + příjmení + jméno
- `setup_jinja_filters(templates)` — registrace custom Jinja2 filtrů (aktuálně `fmt_num`) na Jinja2Templates instanci

## JavaScript

- Stránkový JS jde do `<script>` na konci `{% block content %}` — ne do separátních `.js` souborů
- Vanilla JS only (žádný jQuery, žádné external knihovny kromě HTMX)
- `/static/js/app.js` pro HTMX globální handlery + dark mode toggle
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

## Router packages

- Komplexní routery (1500+ řádků) se dělí na package: `app/routers/modul/`
- Struktura: `__init__.py` (kombinuje sub-routery), `_helpers.py` (sdílené funkce), logické sub-moduly
- `__init__.py`: vlastní `APIRouter()` + `include_router(sub_router)` pro každý sub-modul
- `main.py` import zůstává beze změny (`from app.routers import modul`)
- Příklady:
  - `voting/` — `session.py`, `ballots.py`, `import_votes.py`, `_helpers.py`
  - `tax/` — `session.py`, `processing.py`, `matching.py`, `sending.py`, `_helpers.py`

## Startup (lifespan)

- `main.py` lifespan: (1) import modelů, (2) `create_all`, (3) migrace (6 migračních funkcí), (4) `_ensure_indexes()`, (5) `_seed_code_lists()`, (6) `_seed_email_templates()`, (7) `recover_stuck_sending_sessions()`, (8) vytvoření upload/generated/temp adresářů
- Nové funkce vyžadující adresáře: přidat do lifespan. Nové indexy: přidat do `_ensure_indexes()`

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
- **Po pushi VŽDY rovnou aktualizovat README.md** — neptyat se, rovnou zapsat změny do README a commitnout+pushnout
- Commit message v češtině, stručný, popisuje "co a proč"
- **Úklid po testování**: po použití Playwright (browser_navigate, browser_snapshot, browser_take_screenshot) smazat soubory v `.playwright-mcp/` — `rm -rf .playwright-mcp/*.log .playwright-mcp/*.png .playwright-mcp/*.jpeg`
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

> Implementovat až budou hotové všechny moduly. Role je ortogonální vrstva — přidá se mechanicky bez předělávání existujícího kódu.

### Role

| Role | Popis | Typický uživatel |
|------|-------|------------------|
| **admin** | Plný přístup ke všemu | Předseda SVJ, správce |
| **board** | Správa dat, ne destruktivní systémové operace | Člen výboru |
| **auditor** | Read-only přístup ke všem datům | Kontrolní orgán |
| **owner** | Přístup pouze ke svým údajům a hlasování | Jednotlivý vlastník |

### Matice oprávnění

| Modul / Akce | admin | board | auditor | owner |
|--------------|-------|-------|---------|-------|
| Dashboard — přehled | celý | celý | celý | jen své jednotky |
| Vlastníci — seznam, detail | CRUD | CRUD | read | jen svůj profil |
| Jednotky — seznam, detail | CRUD | CRUD | read | jen své jednotky |
| Hlasování — správa (CRUD) | ano | ano | ne | ne |
| Hlasování — zobrazení výsledků | ano | ano | ano | jen svá hlasování |
| Hlasování — online hlas (budoucí) | — | — | — | ano |
| Hromadné rozesílání — správa | ano | ano | read | jen své dokumenty |
| Synchronizace — import/výměna | ano | ano | ne | ne |
| Kontrola podílu | ano | ano | read | ne |
| Administrace — info SVJ, výbor | ano | read | read | ne |
| Administrace — zálohy, smazání dat | ano | ne | ne | ne |
| Administrace — hromadné úpravy | ano | ano | ne | ne |
| Administrace — číselníky | ano | ano | ne | ne |
| Export dat | ano | ano | ano | ne |
| Správa uživatelů | ano | ne | ne | ne |

### Technické řešení

- **Autentizace:** session-based (cookie), `bcrypt`/`passlib` pro hesla
- **Model:** `User (id, username, password_hash, role: UserRole, owner_id: FK → Owner nullable, is_active, created_at)`
- **Autorizace:** FastAPI `Depends(get_current_user)` + helper `require_role("admin", "board")`
- **Šablony:** `current_user` v kontextu, sidebar podmíněný dle role, destruktivní tlačítka skrytá

### Nové soubory

- `app/models/user.py` — User model + UserRole enum
- `app/routers/auth.py` — login/logout/správa uživatelů
- `app/services/auth_service.py` — hash, verify, session
- `app/templates/auth/login.html`, `users.html`

### Postup implementace

1. Model `User` + migrace + seed admin účtu
2. Auth service (hash, verify, session middleware)
3. Login/logout stránky
4. `get_current_user` dependency + `require_role` helper
5. Přidat do všech routerů (mechanicky)
6. Sidebar podmíněný dle role
7. Skrýt destruktivní tlačítka v šablonách
8. Správa uživatelů (admin panel)
9. Owner self-service (volitelné, až bude potřeba)

### Pravidlo pro průběžný vývoj

- **NEPOUŽÍVAT hardcoded admin logiku** rozsekanou po šablonách (např. `{% if is_admin %}`)
- Destruktivní akce řešit přes `hx-confirm` / `onsubmit="return confirm()"` — to zůstane i po přidání rolí
- Nové moduly navrhovat tak, aby šly snadno obalit `require_role()` dependency

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
8. **Nabídni otestování** — po implementaci se zeptej uživatele: "Chceš otestovat? (konkrétní URL a kroky)". Testovat přes Playwright (browser_navigate + browser_snapshot/screenshot). Po testování smazat soubory v `.playwright-mcp/` (screenshoty, logy)
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
