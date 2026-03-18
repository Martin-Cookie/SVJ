# SVJ Audit Report -- 2026-03-18

## Souhrn

- **CRITICAL: 3** (strategicke pretrvavajici -- auth, CSRF, testy)
- **HIGH: 0**
- **MEDIUM: 4** (2 nove, 2 pretrvavajici)
- **LOW: 7** (4 nove, 3 pretrvavajici)

**Celkem: 14 nalezu -- 3 strategicke (auth/CSRF/testy), 11 novych/pretrvavajicich k oprave**

Z 14 nalezu z predchoziho auditu (2026-03-10) bylo **8 opraveno**, 6 pretrvava.

---

## Stav predchoziho auditu (2026-03-10, 14 nalezu)

| # | Puvodni nalez | Stav |
|---|---------------|------|
| 1 | Zadna autentizace | **Pretrvava** -- plan v CLAUDE.md |
| 2 | Zadna CSRF ochrana | **Pretrvava** -- plan v CLAUDE.md |
| 3 | Zadne testy | **Pretrvava** |
| 4 | XSS v units.py warning HTML | **Opraveno** (commit 05b75ce -- `_parse_numeric_fields` pouziva `escape()`, extrahovano do helperu) |
| 5 | Python-side iterace na voting detail (nekonzistence) | **Pretrvava** -- stale O(I*B*V) v Pythonu na detail strance |
| 7 | `from pathlib import Path` inline 3x v owners.py | **Opraveno** (commit 6beb757 -- Path je na radku 12 top-level, zadne inline importy) |
| 8 | Zastarala CLAUDE-zaloha.md | **Opraveno** (soubor smazan) |
| 9 | Zbyvajicich 11 inline importu | **Castecne opraveno** -- smtplib, sqlite3 presunute na top-level; `_sa_func` zustava inline:91 v administration.py; `app.main` inline legitimni |
| 10 | `force_create` cten nesystemove | **Opraveno** (commit 6beb757 -- `force_create: str = Form("")` na radku 115) |
| 11 | Diacritics fallback search v settings (500 rows) | **Pretrvava** -- beze zmeny |
| 12 | Exception detail v JSON odpovedi | **Opraveno** (commit 6beb757 -- genericka zprava "Nelze zpracovat nahranou sablonu." na radku 208) |
| 13 | SMTP exception zobrazena uzivateli | **Opraveno** (commit 6beb757 -- genericka zprava "Pripojeni k SMTP serveru selhalo." na radku 229, detail logovan) |
| 14 | Duplicitni warn_html kod v units.py | **Opraveno** (commit 05b75ce -- extrahovano do `_parse_numeric_fields()` a `_build_warn_html()`) |

---

## Souhrnna tabulka novych + pretrvavajicich nalezu

| # | Oblast | Soubor | Severity | Problem | Cas | Rozhodnuti |
|---|--------|--------|----------|---------|-----|------------|
| 1 | Bezpecnost | cely projekt | CRITICAL | Zadna autentizace | vice dni | Znamy, plan v CLAUDE.md |
| 2 | Bezpecnost | cely projekt | CRITICAL | Zadna CSRF ochrana | vice dni | Znamy, resit s auth |
| 3 | Testy | cely projekt | CRITICAL | Zadne testy | vice dni | Znamy |
| 4 | Vykon | voting/session.py:347-361 | MEDIUM | Python-side iterace na voting detail (nekonzistence se seznamem) | ~20 min | Pretrvava |
| 5 | Kod | import_mapping.py:6-7 | MEDIUM | Duplicitni `from __future__ import annotations` | ~1 min | 🔧 |
| 6 | Kod | import_mapping.py:9 | MEDIUM | Nepouzity import `json` | ~1 min | 🔧 |
| 7 | Kod | owner_import_mapping.html + contact_import_mapping.html | MEDIUM | Duplicitni JS funkce (collectMapping, updateStats, submitMapping, reloadMapping) | ~20 min | 🔧/❓ |
| 8 | Vykon | contact_import.py:150 | LOW | `load_workbook` bez `read_only=True` -- nacte cely workbook do pameti | ~2 min | 🔧 |
| 9 | Bezpecnost | contact_import.py:161 | LOW | Exception detail `str(e)` v error dict -- potencialni info leakage | ~5 min | 🔧 |
| 10 | Kod | administration.py:91 | LOW | `from sqlalchemy import func as _sa_func` inline misto top-level | ~5 min | 🔧/❓ |
| 11 | Vykon | settings_page.py:89-97 | LOW | Diacritics fallback search nacte 500 EmailLog zaznamu do Pythonu | ~15 min | Pretrvava |
| 12 | Kod | owners.py (1604 radku) | LOW | Router presahuje 1500 radku -- kandidat na rozdeleni do package | ~1 hod | ❓ |
| 13 | Kod | owners.py:681 | LOW | `str(e)` v contact import error ukladan do progress dict | ~5 min | 🔧 |
| 14 | Dokumentace | README.md | LOW | Chybi popis novych import mapping endpointu a import_mapping service | ~10 min | 🔧 |

Legenda: 🔧 = jen opravit, ❓ = potreba rozhodnuti uzivatele (vice variant)

---

## Detailni nalezy

### 1. Bezpecnost

#### #1 Zadna autentizace (CRITICAL) -- pretrvava

- **Co a kde**: Vsechny endpointy jsou pristupne bez prihlaseni. Kazdy na siti muze mazat data, menit vlastniky, odesilat emaily.
- **Reseni**: Implementovat dle planu v CLAUDE.md § Uzivatelske role
- **Narocnost**: Vysoka (~2-3 dny)
- **Regrese riziko**: Stredni (nova vrstva autorizace muze rozbit existujici flow)
- **Jak otestovat**: Zkusit pristoupit na `/vlastnici` bez prihlaseni -- melo by presmerovat na login

#### #2 Zadna CSRF ochrana (CRITICAL) -- pretrvava

- **Co a kde**: POST formulare nemaji CSRF tokeny. Utocnik muze vytvorit stranku, ktera odesle POST na SVJ aplikaci.
- **Reseni**: Implementovat spolecne s autentizaci (session-based CSRF token)
- **Narocnost**: Stredni (~4 hodiny, soucast auth)
- **Zavislosti**: Nejdriv #1 (autentizace)
- **Regrese riziko**: Nizke

#### #3 Zadne testy (CRITICAL) -- pretrvava

- **Co a kde**: Adresar `tests/` neexistuje. Zadne unit testy, zadne integration testy.
- **Reseni**: Vytvorit zakladni test suite pro kriticke business logiku (import, hlasovani, synchronizace). Novy import_mapping.py service je idealnim kandidatem -- cista business logika, zadne IO zavislosti v auto_detect/validate funkcich.
- **Narocnost**: Vysoka (~2 dny pro zakladni pokryti)
- **Regrese riziko**: Zadne (pridavame nove soubory)

#### #9 Exception detail v contact_import error dict (LOW) -- NOVY

- **Co a kde**: `app/services/contact_import.py:161` -- `f"Nepodařilo se otevřít Excel soubor: {e}"` obsahuje plnou exception zpravu vcetne potencialnich interních cest k souborum. Tento error dict se vraci z `preview_contact_import()` a mohl by se zobrazit uzivateli.
- **Reseni**: Nahradit generickou zpravou, detail logovat:
  ```python
  logger.warning("Failed to open Excel: %s", e)
  "error": "Nepodařilo se otevřít Excel soubor."
  ```
- **Varianty**: Zadne -- jednoznacna oprava
- **Narocnost + cas**: Nizka (~5 min)
- **Zavislosti**: Zadne
- **Regrese riziko**: Zadne
- **Jak otestovat**: Nahrat poskozeny .xlsx soubor jako import kontaktu -- odpoved nesmí obsahovat interni cestu/exception detail

#### #13 `str(e)` v contact import progress error (LOW) -- NOVY

- **Co a kde**: `app/routers/owners.py:681` -- `_contact_import_progress[file_key]["error"] = str(e)` uklada plnou exception zpravu. Prestoze je pouzita jen pro interni presmerovani (radek 753-754 presmeruje na generickou stranku), je to potencialni info leakage, pokud by se template v budoucnu zmenil.
- **Reseni**: Logovat detail, ulozit generickou zpravu:
  ```python
  logger.exception("Contact import failed for %s", file_key)
  _contact_import_progress[file_key]["error"] = "Zpracování selhalo"
  ```
- **Narocnost + cas**: Nizka (~5 min)
- **Zavislosti**: Zadne
- **Regrese riziko**: Zadne
- **Jak otestovat**: Vyvolat chybu v contact importu -- error page musi zobrazit generickou zpravu

### 2. Kodova kvalita

#### #5 Duplicitni `from __future__ import annotations` v import_mapping.py (MEDIUM) -- NOVY

- **Co a kde**: `app/services/import_mapping.py:6-7` -- `from __future__ import annotations` je importovano 2x za sebou. Funkcne neovlivnuje (Python ignoruje duplikat), ale indikuje chybu pri merge/copy-paste.
- **Reseni**: Smazat radek 7 (duplikat).
- **Varianty**: Zadne -- jednoznacna oprava
- **Narocnost + cas**: Nizka (~1 min)
- **Zavislosti**: Zadne
- **Regrese riziko**: Zadne
- **Jak otestovat**: `python -c "import app.services.import_mapping"` -- nesmí vyhodit chybu

#### #6 Nepouzity import `json` v import_mapping.py (MEDIUM) -- NOVY

- **Co a kde**: `app/services/import_mapping.py:9` -- `import json` neni nikde v souboru pouzit (zadne `json.` volani). Vzniklo zrejme pri refaktoringu, kdy JSON logika zustala v routeru.
- **Reseni**: Smazat `import json` na radku 9.
- **Varianty**: Zadne -- jednoznacna oprava
- **Narocnost + cas**: Nizka (~1 min)
- **Zavislosti**: Zadne
- **Regrese riziko**: Zadne
- **Jak otestovat**: Spustit server, import vlastniku/kontaktu -- musi fungovat

#### #7 Duplicitni JS funkce v mapping sablonach (MEDIUM) -- NOVY

- **Co a kde**: `app/templates/owners/owner_import_mapping.html` (radky 116-176) a `app/templates/owners/contact_import_mapping.html` (radky 113-173) obsahuji **totozne JS funkce**: `reloadMapping()`, `collectMapping()`, `updateStats()`, `submitMapping()`, a event listener registraci. Jediny rozdil je v `start_row` default hodnote (2 vs 7) a `action` URL.
- **Reseni**:
  - Varianta A: Extrahovat JS do `/static/js/import-mapping.js` s konfigurovatelnym `startRowDefault` a `actionUrl` parametrem. Sablona preda data pres `data-` atributy nebo globalni promennou.
  - Varianta B: Ponechat -- 60 radku JS v kazde sablone je jeste akceptovatelne a projekt nezakazuje inline JS (naopak CLAUDE.md § JavaScript: "strankovy JS jde do `<script>` na konci {% block content %}")
- **Narocnost + cas**: Nizka (~20 min pro variantu A)
- **Zavislosti**: Zadne
- **Regrese riziko**: Nizke
- **Jak otestovat**: Otevrit `/vlastnici/import`, nahrat Excel, overit ze mapping stranka funguje; stejne pro kontakty

#### #10 `from sqlalchemy import func as _sa_func` inline v administration.py (LOW) -- pretrvava (castecne)

- **Co a kde**: `app/routers/administration.py:91` -- import zustava inline (ne na top-level). Ostatni inline importy z minuleho auditu (#9) byly opraveny: `smtplib` presunuto na radek 2, `sqlite3` na radek 6, `markupsafe.escape` presunuto na top-level v owners.py radek 18.
- **Reseni**: Presunout na top-level pred `logger`. Zbyva jen tento 1 import + 4x legitimni cirkularni `from app.main import run_post_restore_migrations` (radky 630, 681, 743, 827).
- **Narocnost + cas**: Nizka (~5 min)
- **Zavislosti**: Zadne -- musi byt az po importu `BoardMember` modelu (radek 79)
- **Regrese riziko**: Nizke -- testovat sortirovani clenu vyboru
- **Jak otestovat**: Spustit server, otevrit `/sprava` -- clenove vyboru musi byt serazeni (predseda nahore)

#### #12 owners.py presahuje 1500+ radku (LOW) -- NOVY

- **Co a kde**: `app/routers/owners.py` ma 1604 radku. CLAUDE.md § Router packages rika: "Komplexni routery (1500+ radku) se deli na package". Soubor obsahuje tri logicke celky: (1) CRUD vlastniku (seznam, detail, vytvareni, uprava, mazani, merge, export), (2) import vlastniku (upload, mapping, preview, confirm), (3) import kontaktu (upload, mapping, preview, confirm).
- **Reseni**:
  - Varianta A: Rozdelit na `app/routers/owners/` package s `__init__.py`, `crud.py`, `import_owners.py`, `import_contacts.py`, `_helpers.py`. Stejny vzor jako `voting/` a `tax/`.
  - Varianta B: Ponechat -- 1604 je temer na hranici (1500+) a dalsi rust se neocekava (import mapping je hotovy).
- **Narocnost + cas**: Stredni (~1 hod pro variantu A)
- **Zavislosti**: Zadne
- **Regrese riziko**: Nizke (pouze presun kodu, zadna zmena logiky)
- **Jak otestovat**: Otestovat vsechny import a CRUD operace na `/vlastnici`

### 3. Vykon

#### #4 Python-side iterace na voting detail (MEDIUM) -- pretrvava

- **Co a kde**: `app/routers/voting/session.py:347-361` -- funkce `voting_detail()` pocita hlasy per item pomoci trojite vnorene smycky (items x ballots x votes). Na seznamu hlasovani (`voting_list()`) je uz SQL agregace (commit 9c36d4d). Na detail strance jsou data eager-loaded, takze to neni N+1, ale stale je to O(I*B*V) v Pythonu a nekonzistentni pristup.
- **Reseni**:
  - Varianta A: Pouzit stejnou SQL agregaci jako na seznamu + filtrovat na voting_id
  - Varianta B: Ponechat -- pro typicke SVJ (~5-10 bodu, ~100 listku) je to <1ms
- **Narocnost + cas**: Stredni (~20 min pro variantu A)
- **Regrese riziko**: Stredni (zmena logiky vypoctu)
- **Jak otestovat**: Overit ze vysledky na `/hlasovani/{id}` odpovidaji excelove exportu

#### #8 `load_workbook` bez `read_only=True` v contact_import.py (LOW) -- NOVY

- **Co a kde**: `app/services/contact_import.py:150` -- `wb = load_workbook(file_path, data_only=True)` chybi `read_only=True`. Vsechny ostatni Excel importy v projektu pouzivaji `read_only=True` (excel_import.py:191, import_mapping.py:25, voting_import.py:190, share_check_comparator.py:58). Bez `read_only=True` openpyxl nacte cely workbook do pameti vcetne stylu, komentaru a formul, coz pro velke soubory (~1000+ radku) muze zvysit pamet a cas.
- **Reseni**: Pridat `read_only=True`:
  ```python
  wb = load_workbook(file_path, read_only=True, data_only=True)
  ```
  **Pozor**: `read_only` mode pouziva `iter_rows` lazy loading, takze pristup k bunkam pres `cell.column` (radek 180) musi byt overen -- ale `values_only=False` + `iter_rows` funguje i v read_only modu.
- **Narocnost + cas**: Nizka (~2 min)
- **Zavislosti**: Zadne
- **Regrese riziko**: Nizke -- overit ze `cell.column` vraci spravne hodnoty v read_only modu
- **Jak otestovat**: Importovat kontakty z Excelu -- vsechna pole se musi spravne naprovazovat

#### #11 Diacritics fallback search v settings nacte 500 zaznamu (LOW) -- pretrvava

- **Co a kde**: `app/routers/settings_page.py:89-97` -- pri hledani s diakritikou nacte az 500 EmailLog zaznamu do Pythonu a iteruje je.
- **Reseni**:
  - Varianta A: Pridat `name_normalized` sloupec na EmailLog
  - Varianta B: Ponechat s limitem 500 -- pro typicke SVJ staci
- **Narocnost + cas**: Stredni (~15 min pro variantu A)
- **Regrese riziko**: Nizke
- **Jak otestovat**: Hledat v email logu ceske jmeno (s diakritikou) -- musi najit

### 4. Dokumentace

#### #14 Chybi popis novych import mapping endpointu v README.md (LOW) -- NOVY

- **Co a kde**: README.md nepopisuje nove endpointy pro dynamicke mapovani sloupcu (`/vlastnici/import/mapovani`, `/vlastnici/import-kontaktu/mapovani`) a novou service `import_mapping.py`. Tyto funkce jsou dost vyznamne -- dynamicke mapovani sloupcu pro import je hlavni nova feature od posledniho auditu.
- **Reseni**: Pridat do README.md sekce Vlastnici popis novych endpointu a kratky popis `import_mapping.py` service.
- **Narocnost + cas**: Nizka (~10 min)
- **Zavislosti**: Zadne
- **Regrese riziko**: Zadne
- **Jak otestovat**: Precist README.md -- musi obsahovat popis import mapping workflow

---

## Pozitivni nalezy

### Bezpecnost

- **Path traversal ochrana na vsech novych import endpointech** -- vsech 8 novych POST endpointu v owners.py s `file_path` parametrem validuje `is_safe_path()` (radky 577, 624, 778, 815, 920, 971, 1013)
- Zadne SQL injection -- ORM konzistentne pouzivan ve vsech novych funkcich
- Autoescaping v Jinja2 -- nove sablony nepouzivaji `|safe` na uzivatelska data
- XSS v units.py opraveno -- `escape()` z markupsafe pouzito v `_parse_numeric_fields()` (radek 33, 41)
- Upload validace na novych import endpointech (validate_upload s UPLOAD_LIMITS)
- SMTP exception genericke zpravy (opraveno v predchozim auditu)
- JSON parsing error v voting session.py opraveno -- genericka zprava

### Novy kod -- kvalitni vzory

- **import_mapping.py** -- cista architektura:
  - Sdilena logika pro owner i contact mapping (DRY princip)
  - Auto-detekce sloupcu s scoring systemem (exact match > contains > reverse contains)
  - Saved mapping s fallbackem na auto-detekci
  - Validace mapping dictu (`validate_owner_mapping`, `validate_contact_mapping`)
  - Helper `build_mapping_context()` pro sjednoceni template kontextu
  - Docstringy na vsech public funkcich
- **excel_import.py refaktoring** -- dynamicke mapovani:
  - `_build_field_map()` pro extrakci field->column mapy
  - `_cell()`, `_cell_int()`, `_cell_float()` safe accessors
  - `_parse_row()` centralizovany parsing jednoho radku
  - `_describe_skip_error()` detailni chybove zpravy pro preskocene radky
  - Backward compatible -- `DEFAULT_OWNER_MAPPING` zachovava puvodni chovani
- **contact_import.py refaktoring** -- stejny pattern jako excel_import
- **Sdileny Jinja2 macro** `import_mapping_fields.html` -- barvy, badge, dropdown rendering
- **Import stepper** partial `import_stepper.html` -- konzistentni vizualni indikace kroku
- **PDF parser fix** -- `_extract_name_from_sp_line()` nyni zvlada oba formaty (zkraceny "SP 2 3108/..." i plny "Spoluvlastnicky podil 4: ...")
- **Ciselniky redesign** -- kolapsovatelne karty s ikonami, accordion vzor (jen 1 otevreny), inline edit, data-confirm mazani

### Vykon

- 38 databazovych indexu v `_ensure_indexes()` (beze zmeny)
- SQL agregace v `voting_list()` (predchozi oprava)
- WAL mode pro SQLite
- Eager loading s `joinedload()` konzistentne
- Migrace `_migrate_svj_import_mappings()` spravne v lifespan i v `run_post_restore_migrations()`

### Error handling

- Vsechny `except Exception:` maji loggovani
- Custom error stranky (404, 500, 409)
- Entity not found -> redirect vzor dusledne dodrzovan v novych endpointech
- Contact import background thread s try/finally db.close()
- Excel open error v contact_import.py zachycen a vracen jako user-friendly error

### UI/Sablony -- NOVE pozitivni nalezy

- Ciselniky: accordion vzor (jen 1 kategorie otevrena), smooth scroll do detailu
- Ciselniky: inline edit s Escape handlerem, usage count badge
- Import mapping: barevne kodovani stavu (saved=modra, auto=zelena, required-missing=cervena)
- Import mapping: real-time stats bar s pocitadlem nalezeni/chybejicich poli
- Import mapping: sheet selector + start_row nastaveni pro flexibilni formaty
- Import mapping: save checkbox pro ulozeni mapovani pro pristi import
- Destruktivni import varovani se zobrazuje jen kdyz existuji data (`owner_count > 0`)
- `aria-hidden="true"` na vsech SVG ikonach v cislenikovem redesignu

### Git hygiene

- .playwright-mcp/ prazdny
- Zadne screenshoty v korenovem adresari
- Commit messages v cestine, strucne, vystizne
- 5 commitu od posledniho auditu -- logicke celky (parser fix, mapping feature, ciselniky redesign)

### Dokumentace

- CLAUDE.md aktualni -- obsahuje vsechny moduly a konvence
- UI_GUIDE.md jako jediny zdroj pravdy pro frontend
- CLAUDE-zaloha.md smazana (opraveno z predchoziho auditu)

---

## Otevrene polozky

### Planovane (strategicke)

| # | Nalez | Priorita | Poznamka |
|---|-------|----------|----------|
| 1 | Autentizace | CRITICAL | Plan implementace v CLAUDE.md § Uzivatelske role |
| 2 | CSRF ochrana | CRITICAL | Implementovat spolecne s autentizaci |
| 3 | Testy | CRITICAL | Zakladni test suite -- import_mapping.py je idealnim kandidatem |

### Nalezy k oprave

| # | Nalez | Priorita | Odhad | Novy/Pretrvava |
|---|-------|----------|-------|----------------|
| 5 | Duplicitni `from __future__` v import_mapping.py | MEDIUM | ~1 min | Novy |
| 6 | Nepouzity import `json` v import_mapping.py | MEDIUM | ~1 min | Novy |
| 7 | Duplicitni JS v mapping sablonach | MEDIUM | ~20 min | Novy |
| 4 | Python-side iterace na voting detail | MEDIUM | ~20 min | Pretrvava |
| 8 | `load_workbook` bez `read_only=True` v contact_import | LOW | ~2 min | Novy |
| 9 | Exception detail v contact_import error dict | LOW | ~5 min | Novy |
| 10 | `_sa_func` inline import v administration.py | LOW | ~5 min | Pretrvava |
| 13 | `str(e)` v contact import progress error | LOW | ~5 min | Novy |
| 11 | Diacritics fallback search v settings (500 rows) | LOW | ~15 min | Pretrvava |
| 12 | owners.py 1604 radku -- kandidat na package | LOW | ~1 hod | Novy |
| 14 | Chybi popis mapping v README.md | LOW | ~10 min | Novy |

### Ponechano (by design)

| Nalez | Stav |
|-------|------|
| Hardcoded wizard labels | By design -- ceska aplikace bez i18n |
| `from app.main import run_post_restore_migrations` inline (4x) | Legitimni -- cirkularni zavislost main -> routers -> main |
| Inline JS v sablonach | By design -- CLAUDE.md § JavaScript: "strankovy JS jde do `<script>` na konci" |

---

## Doporuceny postup oprav

1. **#5 + #6** Smazat duplicitni import a nepouzity `json` v import_mapping.py (~2 min) -- trivial fix
2. **#8** Pridat `read_only=True` do contact_import.py:150 (~2 min) -- vykonnostni fix
3. **#9** Nahradit exception detail v contact_import.py generickou zpravou (~5 min)
4. **#13** Nahradit `str(e)` v owners.py:681 generickou zpravou (~5 min)
5. **#10** Presunout `_sa_func` import na top-level v administration.py (~5 min)
6. **#7** Volitelne: extrahovat duplicitni JS z mapping sablon (~20 min)
7. **#4** Volitelne: sjednotit SQL agregaci na voting detail (~20 min)
8. **#12** Volitelne: rozdelit owners.py na package (~1 hod)
9. **#14** Aktualizovat README.md s popisem import mapping (~10 min)
10. **#11** Volitelne: pridat name_normalized na EmailLog (~15 min)
11. **#1-3** Strategicke: autentizace, CSRF, testy (planovat separatne)

**Celkovy odhadovany cas pro polozky 1-5: ~19 minut**
**Celkovy odhadovany cas pro polozky 1-9: ~70 minut**
