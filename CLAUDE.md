# SVJ Projekt — pravidla pro vývoj

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
- Při vícenásobném zanoření (seznam → detail → detail) se back URL řetězí: `?back={{ ('/aktualni/url?back=' ~ (back_url|urlencode))|urlencode }}`
- Back label se nastavuje dynamicky podle cílové URL pomocí řetězených `if/elif` s `in` nebo `.startswith()`:
  ```python
  back_label = (
      "Zpět na hromadné úpravy" if "/sprava/hromadne" in back
      else "Zpět na detail jednotky" if "/jednotky/" in back
      else "Zpět na seznam jednotek" if back.startswith("/jednotky")
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

## Filtrační bubliny

- Bubliny jsou vždy dynamické: `flex` + `flex-1` (nikdy ne `grid` ani `flex-wrap`)
- Roztahují se na celou šířku obrazovky
- Pokud existují dvě řady bublin nad sebou:
  - Klik na bublinu v prvním řádku resetuje druhý řádek na "Vše" (a obráceně)
  - Toho se dosáhne tím, že `_base` (pro řádek 1) neobsahuje parametry řádku 2 a naopak
- Rozdělené bubliny (s/bez emailu, s/bez telefonu) jsou uvnitř jednoho `flex-1` wrapperu s `<div class="w-px bg-gray-200">` oddělovačem
- Aktivní bublina má `ring-2 ring-{color}-400`
- Bubliny zobrazují počet záznamů (velký, bold) a popis (malý text pod číslem)
- **Pod každou sekcí s bublinami** vždy přidat:
  - **Vyhledávání** — textový input s HTMX debounce (`keyup changed delay:300ms`) nebo query parametrem `q`
  - **Řazení sloupců** — klikací hlavičky tabulek přes macro `sort_th` s parametry `sort` a `order`
  - Hledání a řazení se kombinují (oba parametry se zachovávají v URL)

## Tabulky a layout

- Hlavičky tabulek jsou vždy sticky: `sticky top-0 z-10` na `<thead>`
- Tabulky mají omezenou výšku s vertikálním scrollem: `max-height:calc(100vh - Xpx); overflow-y:auto`
- **Fixní header nad scrollovatelným obsahem** — pokud stránka má bubliny/filtry/search nahoře, použít flex column layout:
  ```html
  <div class="flex flex-col" style="height:calc(100vh - 3rem)">
      <div class="shrink-0"><!-- header, bubliny, search --></div>
      <div class="flex-1 overflow-y-auto min-h-0"><!-- scrollovatelný obsah --></div>
  </div>
  ```
  - `3rem` = top+bottom padding z `<main class="p-6">`
  - `min-h-0` je nutné aby flex child mohl být menší než obsah
  - Bubliny/search se NESMÍ scrollovat — musí být vždy viditelné
- Řazení kliknutím na hlavičky sloupců s indikátorem směru (šipka SVG nahoru/dolů)
- Řadící hlavičky se implementují přes Jinja2 macro `sort_th(label, col, align)` pro konzistenci
- Souhrnný řádek (`<tfoot>`) pod tabulkami kde to dává smysl (celkový podíl, plocha, procenta)
- `table-layout: fixed` s `<colgroup>` pro přesné šířky sloupců

## Detail stránka — layout

- (1) Šipka zpět: `<a href="{{ back_url }}" class="text-sm text-gray-500 hover:text-gray-700">&larr; {{ back_label }}</a>`
- (2) Titulek: `<h1 class="text-2xl font-bold text-gray-800">`
- (3) Badge pod titulem: `<div class="mt-1 flex items-center gap-2">` s `rounded-full` badge
- (4) Obsah v grid layoutu pod tím

## Formátování čísel a dat

- Tisíce se oddělují mezerou: `"{:,}".format(x).replace(",", " ")`
- Podíl v procentech na 4 desetinná místa: `"%.4f" | format(value)`
- Procenta rozdílu se znaménkem: `"{:+.2f}".format(diff_pct)`
- Barevné kódování rozdílů: červená (`text-red-600`) pro záporné, modrá (`text-blue-600`) pro kladné, zelená (`text-green-600`) pro nulu
- Datum ve formátu `dd.mm.YYYY`: `strftime('%d.%m.%Y')`
- Pomlčka `—` pro chybějící hodnoty (ne prázdný řetězec)

## Status badge barvy

- Tvar: `<span class="px-2 py-1 text-xs font-medium bg-{color}-100 text-{color}-800 rounded-full">`
- Barevná mapa: šedá = draft/neutrální, zelená = active/success, modrá = closed/info, červená = error/cancelled, žlutá = pending/warning
- Vždy `rounded-full`, nikdy `rounded`

## Prázdné stavy

- Kontejner: `text-center text-gray-500 text-sm` s paddingem
- Vždy obsahuje akční odkaz (`text-blue-600 hover:underline`) navádějící uživatele k naplnění sekce
- Pro inline prázdné stavy (uvnitř karet): `text-sm text-gray-400`

## Formulářové styly

- Inputy: `border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500`
- Primary button: `bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-medium`
- Cancel button: `bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 text-sm font-medium`
- Danger button: `bg-red-600 text-white rounded-lg hover:bg-red-700 text-sm font-medium`

## Statistiky podílů

- Porovnání podílů se zobrazuje na dashboardu i v seznamech (vlastníci, jednotky):
  - Podíly dle prohlášení (z `SvjInfo.total_shares`)
  - Podíly v evidenci (součet z tabulky)
  - Rozdíl s barevným kódováním a procentuálním vyjádřením
- V detailu vlastníka: sloupec "Podíl %" = `podil_scd / declared_shares * 100` (4 des. místa)
- `declared_shares` se předává do všech šablon kde se zobrazují podíly (včetně HTMX partials)

## Dashboard

- Statistické bubliny i modulové karty jsou plně klikací (`<a>` tag, ne `<div>` s vnořeným odkazem)
- Bublina hlasování zobrazuje seznam aktivních/konceptových hlasování se stavem (badge) a názvem (truncate + title tooltip)
- Vše dynamicky roztažené přes `flex` + `flex-1`
- Žádný text "Otevřít modul" — celá karta je klikací

## Inline editace (Upravit / Uložit / Zrušit)

Vzor se skládá ze dvou partials (info + form) a tří endpointů:

### Šablony
- **Info partial** (`partials/*_info.html`) — read-only zobrazení dat + tlačítko "Upravit":
  ```html
  <button hx-get="/entita/{id}/upravit-formular"
          hx-target="#section-id" hx-swap="innerHTML">Upravit</button>
  ```
  Po úspěšném uložení zobrazí `{% if saved %}<span class="text-green-600">Uloženo</span>{% endif %}`
- **Form partial** (`partials/*_form.html`) — editační formulář + "Uložit" a "Zrušit":
  ```html
  <form hx-post="/entita/{id}/upravit" hx-target="#section-id" hx-swap="innerHTML">
      <!-- inputy -->
      <button type="submit">Uložit</button>
      <button type="button" hx-get="/entita/{id}/info"
              hx-target="#section-id" hx-swap="innerHTML">Zrušit</button>
  </form>
  ```

### Detail stránka
- Wrapper `<div id="section-id">` obsahuje pouze `{% include %}` partials — žádný extra markup
- Nadpis sekce (`<h2>`) je VNĚ wrapperu, aby se neměnil při přepínání

### Backend endpointy (3 pro každou sekci)
| Endpoint | Účel | Vrací |
|----------|------|-------|
| `GET /{id}/upravit-formular` | Načtení formuláře | Form partial |
| `POST /{id}/upravit` | Uložení změn | Info partial s `saved=True` |
| `GET /{id}/info` | Zobrazení (cancel) | Info partial |

- POST endpoint: pro HTMX vrací partial, pro běžný request dělá `RedirectResponse`
- Pro vnořené sekce s prefixem (např. adresa trvalá/korespondenční): `/{id}/adresa/{prefix}/upravit`

### Alternativní vzor (administrace — seznam položek)
- View i form jsou na stránce oba, přepínání přes CSS `hidden` class + JS:
  ```javascript
  function toggleEdit(id) {
      document.getElementById('view-' + id).classList.toggle('hidden');
      document.getElementById('edit-' + id).classList.toggle('hidden');
  }
  ```
- Formuláře používají standardní POST (`hx-boost="false"`) s redirect po uložení

## HTMX vzory

- Na `<body>` je `hx-boost="true"` — VŠECHNY `<a href>` a `<form>` se automaticky přepínají na AJAX swap celého body
- Partial odpovědi: router vrací partial šablonu pro HTMX requesty (`HX-Request` hlavička), plnou stránku pro běžné requesty
- Rozlišovat `HX-Request` vs `HX-Boosted` — boosted navigace dostává plnou stránku
- `hx-push-url="true"` na vyhledávání a filtrech — aby se URL aktualizovala v prohlížeči
- `hx-confirm` pro destruktivní akce (smazání, odebrání)
- Hidden inputy pro přenos stavu filtrů při HTMX požadavcích
- `hx-boost="false"` je **POVINNÉ** na: formuláře stahující soubory (Excel, ZIP, PDF), formuláře s file uploadem, POST formuláře které vracejí binární data, a formuláře s `onsubmit="return confirm(...)"`
- Bez `hx-boost="false"` HTMX zachytí odpověď a pokusí se ji swapnout jako HTML — binární data tiše selžou

### Co používá HTMX partial (hx-get + hx-target) a co plain href (hx-boost)

| Prvek | Vzor | Důvod |
|-------|------|-------|
| **Filtrační bubliny** | Plain `<a href="...">` | hx-boost swapne celou stránku — bubliny se správně překreslí s aktivním stavem |
| **Řazení sloupců** | Plain `<a href="...">` | hx-boost swapne celou stránku — hlavičky se správně překreslí se šipkou |
| **Vyhledávání** | `hx-get` + `hx-target="#tbody-id"` | Jen tbody se aktualizuje, zbytek stránky zůstane |
| **Inline editace** | `hx-get`/`hx-post` + `hx-target="#section-id"` | Formulář/info se přepne bez reloadu |

### Pravidla pro partial šablony
- Partial pro hledání = **jen `<tr>` řádky** (tbody-only), NE celá tabulka
- Partial se ukládá vedle hlavní šablony (např. `voting/ballots_table.html`) nebo do `partials/`
- Hlavní šablona dělá `{% include "partial.html" %}` uvnitř `<tbody id="...">`
- Router: `if request.headers.get("HX-Request") and not request.headers.get("HX-Boosted"):` → vrátí partial
- **NEPOUŽÍVAT** Jinja2 `{% macro %}` pro sort hlavičky — macro nemá přístup k proměnným z kontextu šablony
- Sort hlavičky se implementují přes `{% for %}` cyklus s definicí sloupců v `{% set _cols = [...] %}`
- `<a>` element MUSÍ mít `href` atribut — bez něj není klikatelný

## Vyhledávání

- Hledání probíhá přes HTMX s debounce: `hx-trigger="keyup changed delay:300ms"`
- Prohledávají se všechna relevantní pole (jméno, email, telefon, RČ, IČ, číslo jednotky, adresa)
- Hledání se kombinuje s filtry (typ, sekce, vlastnictví, kontakt) — filtry se přenáší přes hidden inputy a `hx-include`
- Hidden inputy (`sort`, `order`, `stav`, `back`) jsou VEDLE search inputu, NE uvnitř tbody partial

## Jména vlastníků

- **Zobrazení**: vždy `owner.display_name` (property na modelu Owner) — formát „titul příjmení jméno"
- **DB sloupec** `name_with_titles` zůstává pro SQL dotazy (`.ilike()`, index) — nepoužívat v šablonách
- **Hledání** v Pythonu: `owner.display_name.lower()` (ne `name_with_titles`)
- **Řazení**: `owner.name_normalized` (příjmení-first, bez diakritiky, lowercase)
- **Budoucí importy**: `_build_name_with_titles()` v `excel_import.py` generuje příjmení-first formát

## Import hlasování — spoluvlastnictví (SJM)

- Párování Excel řádků na lístky probíhá přes číslo jednotky
- Pokud Excel řádek **má hlasy** → párovat na VŠECHNY lístky, jejichž vlastník sdílí tu jednotku (SJM, spoluvlastnictví)
- Pokud Excel řádek **nemá hlasy** → párovat jen na první nalezený lístek (bez rozšíření)
- Každý spoluvlastník dostane hlasy se svým vlastním `total_votes`
- Deduplikace přes `seen_ballots` — stejný lístek se nezpracuje dvakrát

## fetch() + innerHTML vs HTMX

- **`<script>` tagy v HTML vloženém přes `innerHTML` se NESPUSTÍ** — prohlížeč je ignoruje
- Pokud se obsah načítá přes `fetch()` + `el.innerHTML = html`, všechny JS funkce musí být definovány v nadřazené šabloně (té, která volá fetch)
- HTMX (`hx-get` + `hx-swap`) naopak skripty VYHODNOTÍ — proto preferovat HTMX kde to jde
- Pokud je nutné použít fetch + innerHTML (např. expandovatelné řádky v tabulce), definovat funkce v HTMX-loadované nadřazené šabloně

## SQLAlchemy vzory

- Projekt používá **SQLite** (`data/svj.db`) s `check_same_thread=False`
- `DeclarativeBase` z SQLAlchemy 2.0 pro modely, ale **legacy query API** (`db.query()`) pro všechny dotazy — nepřecházet na `select()` style
- `db.query(Model).get(id)` pro PK lookup, `.filter_by(...).first()` pro složitější dotazy
- `case()` se importuje přímo ze `sqlalchemy`, ne přes `func.case()`
- `func.coalesce(field, "")` pro seskupování NULL a prázdných řetězců (např. ownership_type)
- `func.distinct()` v agregacích pro počítání unikátních záznamů
- `joinedload()` pro eager loading relací (předchází N+1 queries)
- Číslo jednotky (`unit_number`) je INTEGER (ne string)

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

### Řazení — `SORT_COLUMNS` dictionary
- Modul-level `SORT_COLUMNS` dict mapující sort parametry na SQLAlchemy sloupce (nebo `None` pro Python-side sort)
- SQL sorty vždy s `.nulls_last()`
- Python-side sort: `items.sort(key=lambda x: ..., reverse=(order == "desc"))`

### Helper funkce v routerech
- Interní helper funkce mají prefix `_` (např. `_ballot_stats`, `_purge_counts`)
- Vrací dict, který se rozbalí do template kontextu: `**_ballot_stats(voting)`

### Dynamické formuláře
- `Form(...)` pro fixní pole. `await request.form()` + `.get()`/`.getlist()` pro dynamické názvy polí (např. `vote_5`, `update__12__field`)

## Nové moduly / entity

- Musí dodržovat VŠECHNY výše uvedené vzory od začátku:
  - Back URL navigace (router `back` param + `list_url` + šipka zpět v šabloně)
  - Dynamické bubliny (pokud mají filtry)
  - Sticky hlavičky tabulek
  - Plně klikací karty (ne vnořené odkazy)
  - Formátování čísel s mezerovým oddělovačem
  - HTMX partial odpovědi
  - Fixní header s flex column layoutem (bubliny/search se nescrollují)
- **Modul s více stránkami** (např. hlasování: detail, lístky, zpracování, neodevzdané):
  - Sdílený header jako partial (`_modul_header.html`) — stejný nadpis, bubliny, tlačítka na VŠECH stránkách
  - Aktivní bublina zvýrazněna `ring-2 ring-{color}-400`
  - Router: sdílená helper funkce pro výpočet dat bublin (volat ve všech endpointech)
  - Šablona předává `active_bubble` do partialu pro zvýraznění
- Registrace v `app/main.py` (`include_router`)
- Export modelů v `app/models/__init__.py`
- Odkaz v sidebar (`base.html`) s `active_nav` kontrolou
- Přidání do README.md (popis modulu + API endpointy)
- Odkaz v sidebaru (`base.html`): sekce Data (nahoře), Moduly (doménové funkce), Systém (admin/config). Ikona `w-4 h-4 mr-2` SVG + text label

## Akce v tabulkách — ikony místo textu

- Akční sloupce v tabulkách (stáhnout, smazat, upravit) používají **SVG ikony** místo textových odkazů
- Ikona stáhnout: modrá (`text-blue-600`), hover `hover:bg-blue-50`
- Ikona smazat: šedá → červená hover (`text-gray-400 hover:text-red-600`), `hover:bg-red-50`
- Ikona upravit: šedá → modrá hover (`text-gray-400 hover:text-blue-600`)
- Velikost ikon: `w-4 h-4`, padding `p-1`, kulaté rohy `rounded`
- Vždy `title` atribut pro tooltip (např. `title="Stáhnout"`, `title="Smazat"`)
- Dlouhé názvy souborů: `truncate` + `title` tooltip s plným názvem

## Export dat (Excel)

- Export musí vždy odrážet **aktuální filtrovaný pohled** — ne všechna data
- Filtr se přenáší přes hidden input ve formuláři: `<input type="hidden" name="filtr" value="{{ filtr }}">`
- Export endpoint aplikuje **stejnou logiku filtrování** jako zobrazovací endpoint
- Generování přes `openpyxl` (ne pandas): bold hlavička (`Font(bold=True)`), auto-width sloupců (max 45 znaků), žlutá `PatternFill` pro zvýraznění rozdílů
- Formulář exportu musí mít `hx-boost="false"` (viz HTMX vzory)
- Response: `media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"`

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

## Potvrzení destruktivních akcí

- Standardní: `onsubmit="return confirm('Česká otázka?')"` na formuláři
- Kritické operace (purge): textový input s klíčovým slovem (`DELETE`) + disabled tlačítko, které se aktivuje až po zadání

## Kolapsovatelné sekce

- `<details class="mb-6 group">` s `<summary>` obsahující chevron SVG rotovaný přes `group-open:rotate-90`
- Otevření z redirectu: query parametr + podmíněný `open` atribut: `{% if sekce == 'zalohy' %}open{% endif %}`

## Hromadný výběr (checkbox "Vybrat/Zrušit vše")

- Checkbox pro hromadné označení/odznačení se vždy jmenuje **„Vybrat/Zrušit vše"**
- Vizuálně odlišený: `bg-gray-50 border border-gray-200` (oproti běžným řádkům bez borderu)
- JS vzor: `toggleAll(checked)` nastaví všechny checkboxy, `updateSelectAll()` na každém jednotlivém checkboxu synchronizuje stav hlavního checkboxu
- Akční tlačítka (export, smazání) jsou `disabled` dokud není zaškrtnutý alespoň jeden checkbox
- Pokud se obsah (řádky s checkboxy) načítá dynamicky přes fetch/HTMX, **stav checkboxů se musí persistovat v sessionStorage**:
  - Klíč: `bulk_{field}_{value}` — unikátní pro každý kontext
  - Uložit: při každé změně checkboxu (`saveBulkChecks`)
  - Obnovit: po načtení nového HTML (`restoreBulkChecks`)
  - Select-all checkbox: synchronizovat `checked` / `indeterminate` stav po obnovení

## Service layer

- Služby jsou **plain funkce** (ne třídy), přijímají `db: Session` jako parametr od routeru
- Vrací plain dict/list (žádné custom result třídy)
- Nikdy nevytvářejí DB session — vždy přijímají z volajícího

## JavaScript

- Stránkový JS jde do `<script>` na konci `{% block content %}` — ne do separátních `.js` souborů
- Vanilla JS only (žádný jQuery, žádné external knihovny kromě HTMX)
- `/static/js/app.js` pouze pro HTMX globální handlery
- Jinja2 macro je OK pro opakující se UI struktury v rámci jedné šablony, pokud všechna data přijdou jako parametry macro

## Technologie

- Tailwind CSS z CDN (`cdn.tailwindcss.com`) — žádný build pipeline
- HTMX z CDN (`unpkg.com`)
- Custom CSS pouze pro HTMX animace (`custom.css`, ~17 řádků)
- Vše stylováno přes Tailwind utility classes

## Startup (lifespan)

- `main.py` lifespan: (1) import modelů, (2) `create_all`, (3) migrace, (4) `_ensure_indexes()`, (5) vytvoření upload/generated adresářů
- Nové funkce vyžadující adresáře: přidat do lifespan. Nové indexy: přidat do `_ensure_indexes()`

## Workflow

- Po dokončení změn: commit + push (pokud uživatel požádá)
- Po commitu: aktualizovat README.md (pokud uživatel požádá)
- Commit message v češtině, stručný, popisuje "co a proč"

## Komunikace s uživatelem

- NEPTÁT SE na přístup/implementaci, pokud je vzor již zavedený v projektu — použít existující vzor
- Pokud uživatel řekne "commit this and push" — udělat commit a push bez dalších otázek
- Pokud uživatel řekne "dokumentaci" — aktualizovat README.md bez ptaní se co přidat
- Být proaktivní: když vytvářím novou stránku/entitu, rovnou aplikovat VŠECHNA pravidla z tohoto souboru (back URL, dynamické bubliny, sticky hlavičky, formátování čísel atd.) bez čekání na připomínku
- Komunikovat stručně — co jsem udělal, ne co bych mohl udělat
- Na potvrzení se PTÁT — "Chceš commitnout?", "Chceš něco upravit?" atd. jsou v pořádku
