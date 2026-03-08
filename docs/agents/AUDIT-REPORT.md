# SVJ Audit Report -- 2026-03-08

## Souhrn
- **CRITICAL: 4** (2 existujici, 2 nove)
- **HIGH: 5**
- **MEDIUM: 9**
- **LOW: 10**

**Celkem: 28 nalezu**

### Stav predchoziho auditu (2026-03-08 post-refaktor, 26 nalezu)

| # | Puvodni nalez | Stav |
|---|---------------|------|
| 1 | Zadna autentizace | Zustava -- plan v CLAUDE.md |
| 2 | Zadna CSRF ochrana | Zustava -- plan v CLAUDE.md |
| 3 | Zadne testy | Zustava |
| 4 | Path traversal v backup restore | **OPRAVENO** (administration.py:779-783 -- validace `os.path.realpath`) |
| 5 | N+1 query v tax/sending.py:232 | **OPRAVENO** (joinedload pouzit na r.62-68) |
| 6 | Hardcoded upload size limits | Zustava (12 mist) |
| 7 | README directory tree zastaraly | **OPRAVENO** (README:388-408 aktualizovan) |
| 8 | File attachment bez error handling | Zustava (email_service.py:56-58) |
| 9 | Duplicitni `_build_name_*()` funkce | Zustava |
| 10 | Hardcoded multipart limits (5000) | Zustava (main.py:494) |
| 11 | Chybi dokumentace router package vzoru | Zustava |
| 12 | .gitignore chybi .playwright-mcp/ a data/svj.db* | **OPRAVENO** |
| 13 | int() cast bez try/except v _helpers.py:137 | Zustava |
| 14 | File read jen UnicodeDecodeError v sync.py | Zustava |
| 15 | _send_emails_batch() 132 radku | Zustava |
| 16 | Debug mode bez produkcni ochrany | Zustava |
| 17-26 | LOW nalezy | Vetsina zustava |

---

## Souhrnna tabulka

| # | Oblast | Soubor | Severity | Problem | Stav |
|---|--------|--------|----------|---------|------|
| 1 | Bezpecnost | cely projekt | CRITICAL | Zadna autentizace -- vsechny endpointy pristupne bez prihlaseni | Znamy, plan v CLAUDE.md |
| 2 | Bezpecnost | cely projekt | CRITICAL | Zadna CSRF ochrana na POST formularich | Znamy, resit s auth |
| 3 | Testy | cely projekt | CRITICAL | Zadne testy -- adresar tests/ neexistuje | Znamy |
| 4 | Kod | sending.py:317,355 | CRITICAL | `TaxDocument.original_filename` neexistuje -- **AttributeError za behu** | **NOVY** |
| 5 | Logika | _helpers.py:198 | HIGH | `is_completed` kontroluje `SendStatus.READY` misto `COMPLETED` -- zavadejici nazev a potencialne spatna logika | **NOVY** |
| 6 | Robustnost | _helpers.py:137 | HIGH | `int(unit_number)` bez try/except -- pad pri neciselnem cislu jednotky | Existujici |
| 7 | Robustnost | email_service.py:56-58 | HIGH | File attachment `open()` bez try/except -- pad pri chybejicim souboru | Existujici |
| 8 | Konfigurace | 12 souboru | HIGH | Hardcoded upload size limits (10/50/100/200 MB) rozptyleno po routerech | Existujici |
| 9 | Zavislosti | pyproject.toml:25 | HIGH | `aiosmtplib` v zavislosti ale nikde nepouzit -- zbytecna zavislost | **NOVY** |
| 10 | Duplikaty | processing.py:272, sending.py:610, owners.py:490 | MEDIUM | 3x duplikovana ETA/progress funkce (stejny vzor formatovani casu) | **NOVY** |
| 11 | Struktura | sending.py:165-370 | MEDIUM | `update_recipient_email()` ma 206 radku -- kandidat na rozdeleni | **NOVY** |
| 12 | Struktura | sync.py:631-893 | MEDIUM | `apply_selected_updates()` ma 263 radku -- nejdelsi funkce v projektu | Existujici |
| 13 | Dokumentace | CLAUDE.md | MEDIUM | Chybi dokumentace router package vzoru (voting/, tax/ jako packages) | Existujici |
| 14 | Robustnost | sync.py:188-194 | MEDIUM | CSV cteni odchytava jen `UnicodeDecodeError`, ne `IOError`/`PermissionError` | Existujici |
| 15 | Konfigurace | main.py:493-495 | MEDIUM | Monkey-patching `_StarletteRequest.__kwdefaults__` -- krehke, muze se rozbít pri upgrade Starlette | Existujici |
| 16 | Bezpecnost | config.py:7 | MEDIUM | `debug: bool = False` -- zadna explicitni ochrana proti zapnuti v produkci | Existujici |
| 17 | Bezpecnost | main.py:243 | MEDIUM | `_ensure_indexes()` pouziva f-string v SQL (`f"CREATE INDEX..."`) -- jen s internimi konstantami, ale nesplnuje best practice | Existujici |
| 18 | JS | app.js:87 | MEDIUM | pdf.js worker hardcoded na konketni verzi CDN (3.11.174) -- neni synchronizovano s knihovnou v base.html | **NOVY** |
| 19 | Pojmenovani | voting/_helpers.py:28 | LOW | `_has_processed_ballots` -- spis model metoda | Info |
| 20 | Duplikaty | voting/_helpers, tax/_helpers | LOW | Paralelni wizard patterns (mohlo by byt spolecne) | Info |
| 21 | Styl | owners.py:374+ | LOW | Inline importy (csv, io, BytesIO, openpyxl) v exportnich funkcich | Info |
| 22 | Zavislosti | owner_matcher.py:10 | LOW | `from unidecode import unidecode` -- cely modul mohl pouzit `strip_diacritics()` z utils | Info |
| 23 | Konfigurace | settings_page.py | LOW | Hardcoded pagination limit | Info |
| 24 | Konfigurace | tax/_helpers.py:53 | LOW | Hardcoded wizard labels | Info |
| 25 | Dokumentace | CLAUDE.md | LOW | Chybi TOC (Table of Contents) | Info |
| 26 | Testy | cely projekt | LOW | Chybi pytest.ini, CI/CD workflow, GitHub Actions | Info |
| 27 | JS | app.js:77-83 | LOW | Escape handler vola `confirmCancel()`, `closePdfModal()`, `closeSendConfirmModal()` -- pad pokud funkce neexistuje na strance bez modalu | **NOVY** |
| 28 | JS | app.js:506-518 | LOW | `toggleEmailSelect()` pouziva raw `fetch()` bez HTMX -- chybi loading indikator a error handling | **NOVY** |

---

## Detailni nalezy

### 1. Kodova kvalita

#### #4 CRITICAL: `TaxDocument.original_filename` neexistuje

**Soubor:** `app/routers/tax/sending.py:317,355`

**Popis:** V endpointu `update_recipient_email()` se na radcich 317 a 355 pouziva `rd.document.original_filename` resp. `doc.original_filename`. Model `TaxDocument` v `app/models/tax.py` tento sloupec NEMA -- obsahuje pouze `filename`. Kod `rd.document.original_filename or rd.document.filename or ""` vyustí v `AttributeError` pri kazdem volani tohoto code path (inline editace emailu u ownera s vice dokumenty).

**Doporuceni:** Nahradit `rd.document.original_filename or rd.document.filename` za `rd.document.filename` na obou mistech. Alternativne pridat sloupec `original_filename` do modelu TaxDocument.

```python
# sending.py:317 -- oprava
"filename": rd.document.filename or "",
# sending.py:355 -- oprava
"filename": doc.filename or "",
```

#### #10 MEDIUM: 3x duplikovana ETA/progress funkce

**Soubory:**
- `app/routers/tax/processing.py:272` -- `_progress_eta()`
- `app/routers/tax/sending.py:610` -- `_sending_eta()`
- `app/routers/owners.py:490` -- `_contact_progress_ctx()`

**Popis:** Vsechny tri funkce pocitaji ETA z progress dictu stejnym zpusobem: elapsed/current => per_item => remaining => format min/s. Kod je copy-paste s drobnymy odlisnostmi v klicich dictu.

**Doporuceni:** Extrahovat spolecnou utility funkci `compute_eta(elapsed, current, total)` do `app/utils.py`.

#### #11 MEDIUM: Prilis dlouhe funkce

**Nejhorsi kandidati (>100 radku):**

| Funkce | Soubor | Radky |
|--------|--------|-------|
| `apply_selected_updates` | sync.py | 263 |
| `preview_contact_import` | contact_import.py | 220 |
| `preview_voting_import` | voting_import.py | 216 |
| `update_recipient_email` | sending.py | 206 |
| `generate_ballots` | voting/session.py | 188 |
| `tax_detail` | tax/session.py | 177 |
| `home` (dashboard) | dashboard.py | 166 |
| `sync_detail` | sync.py | 152 |
| `import_owners_from_excel` | excel_import.py | 143 |
| `_process_tax_files` | processing.py | 238 |
| `_send_emails_batch` | sending.py | 132 |

**Doporuceni:** Prioritne refaktorovat `apply_selected_updates` (263 radku) a `update_recipient_email` (206 radku) -- rozdelit na sub-funkce pro jednotlive scenare.

#### #22 LOW: `unidecode` vs `strip_diacritics`

**Soubor:** `app/services/owner_matcher.py:10`

**Popis:** `owner_matcher.py` importuje `unidecode` z externiho balicku, zatimco projekt ma vlastni `strip_diacritics()` v `app/utils.py` ktery dela totez (normalize + remove combining marks). Dve ruzne implementace pro stejny ucel.

**Doporuceni:** `owner_matcher.py` pouziva `unidecode` pro specificke ucely (stemming ceskych prijmeni), kde presny ASCII prevod muze byt dulezity. Ponechat, ale zvazit konsolidaci.

### 2. Bezpecnost

#### #1 CRITICAL: Zadna autentizace (existujici)

**Popis:** Vsechny endpointy jsou pristupne bez prihlaseni. Zadny middleware, zadna session, zadne heslo. Plan implementace roli je v CLAUDE.md, ale zatim neimplementovan.

#### #2 CRITICAL: Zadna CSRF ochrana (existujici)

**Popis:** POST formulare nemaji CSRF tokeny. Libovolna externi stranka muze submitnout formular na localhost server.

**Poznamka:** Pro lokalni desktop aplikaci (bezi na localhost) je riziko nizsi nez pro verejne deployovanou aplikaci. Ale pokud uzivatel navstivi skodlivou stranku, utoce muze provest akce na SVJ serveru.

#### #16 MEDIUM: Debug mode

**Soubor:** `app/config.py:7`

**Popis:** `debug: bool = False` je spravne vypnuty defaultne. Ale neni zadna ochrana proti jeho nechtenymu zapnuti v `.env` souboru, coz by zapnulo SQL echo.

#### #17 MEDIUM: f-string v SQL pro index vytvareni

**Soubor:** `app/main.py:243`

**Popis:** `f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table} ({column})"` pouziva f-string. Data pochazi z konstantniho `_INDEXES` listu, NE z uzivatelskeho vstupu, takze to neni SQL injection. Ale je to nesplneni best practice (pouzivat parametrizovane dotazy) a mohlo by se stat problematickym pri pridavani novych indexu.

### Pozitivni bezpecnostni nalezy:
- Zadne SQL injection -- ORM konzistentne pouzivan ve vsech routerech
- Autoescaping v Jinja2 -- zadne `|safe` s uzivatelskymy daty
- HTTP security headers (X-Frame-Options: DENY, X-Content-Type-Options: nosniff)
- Path traversal opraveno v backup restore (os.path.realpath validace)
- Upload validace (velikost + pripona) na vsech upload endpointech
- `is_safe_path()` pouzivan pro download endpointy
- SMTP heslo v `.env` souboru (v .gitignore)
- Verze zavislosti pinnuty v pyproject.toml

### 3. Dokumentace

#### #13 MEDIUM: Chybi dokumentace router package vzoru

**Soubor:** `CLAUDE.md`

**Popis:** CLAUDE.md popisuje jednotlive routery jako soubory, ale `voting/` a `tax/` jsou nyni packages s `__init__.py`, `_helpers.py`, a vice sub-moduly. Vzor jak organizovat router jako package (sdilene helpers, `_processing_lock`, `_sending_progress`) neni zdokumentovan.

#### #25 LOW: Chybi TOC v CLAUDE.md

**Popis:** CLAUDE.md ma ~370 radku bez obsahu. Navigace je obtizna.

### Stav dokumentace:
- README.md -- **aktualni**, directory tree opraven, endpointy popsany
- CLAUDE.md -- **vetsinou aktualni**, chybi package vzor
- UI_GUIDE.md -- neauditovan v tomto pruchodu (mimo scope)

### 4. UI / Sablony

#### #18 MEDIUM: pdf.js verze nesynchronizovana

**Soubory:** `app/static/js/app.js:87`, `app/templates/base.html:17`

**Popis:** V `app.js` je hardcoded worker URL:
```javascript
pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
```
Zatimco v `base.html`:
```html
<script src="https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js"></script>
```
Aktualne jsou verze shodne (3.11.174), ale pri upgrade hlavni knihovny v base.html se worker v app.js muze zapomenout. Worker a knihovna MUSI byt ve stejne verzi.

**Doporuceni:** Bud dynamicky vytahat verzi z `pdfjsLib.version`, nebo extrahovat verzi do spolecne promenne.

#### #27 LOW: Escape handler vola neexistujici funkce

**Soubor:** `app/static/js/app.js:77-83`

**Popis:** Globalní Escape handler vola `confirmCancel()`, `closePdfModal()`, `closeSendConfirmModal()`. Na strankach kde tyto modaly neexistuji (napr. vlastnici, jednotky) se funkce vola, ale diky implementaci (early return na `!modal || modal.classList.contains('hidden')`) to nezpusobi chybu -- `confirmCancel` a `closePdfModal` jsou definovane globalne a kontroluji existenci elementu. Avsak `closeSendConfirmModal` taky kontroluje `if (!modal) return`, takze je to bezpecne.

#### #28 LOW: toggleEmailSelect pouziva raw fetch

**Soubor:** `app/static/js/app.js:506-518`

**Popis:** `toggleEmailSelect()` pouziva raw `fetch()` API misto HTMX. Chybi:
- Loading indikator behem pozadavku
- Error handling (co kdyz server vrati 500?)
- Retry logika

**Doporuceni:** Prevest na HTMX interakci (hx-post + hx-target + hx-swap), nebo pridat `.catch()` handler s uzivatelskymy chybovym hlasenim.

### Pristupnost:
- Vsechny formularove inputy maji `<label>` nebo `aria-label` -- **OK**
- SVG ikony maji `aria-hidden="true"` -- **OK**
- Search input ma `aria-label="Hledat"` -- **OK**
- Checkbox "select all" chybi `aria-label` -- drobny nedostatek

### 5. Vykon

#### #5 HIGH (zmeneno z predchoziho auditu): Logicka chyba `is_completed`

**Soubor:** `app/routers/tax/_helpers.py:198`

**Popis:**
```python
is_completed = doc.session.send_status == SendStatus.READY if doc.session.send_status else False
```
Promenna `is_completed` kontroluje stav `READY`, ne `COMPLETED`. V kontextu pouziti (matching page) to znamena "session je pripravena k odeslani" a ovlada zobrazeni/skryti editacnich tlacitek. Nazev `is_completed` je zavadejici a muze vest k chybam pri budouci uprave. V `session.py:461` je stejna logika:
```python
is_completed = session.send_status and session.send_status.value == "ready"
```

**Doporuceni:** Prejmenovar na `is_locked` nebo `is_ready_or_beyond`, prip. pridat stav `COMPLETED` do kontroly:
```python
is_locked = session.send_status in (SendStatus.READY, SendStatus.SENDING, SendStatus.PAUSED, SendStatus.COMPLETED)
```

#### Vykonove pozitivni nalezy:
- N+1 v sending.py opraven (joinedload na r.62-68)
- 38 databazovych indexu v `_ensure_indexes()`
- SQL agregace v `_ballot_stats()` misto Python-side pocitani
- WAL mode pro SQLite (concurrent reads)
- Optimalizovany rebuild jednoho radku v `update_recipient_email()` (r.290-370)

### 6. Error handling

#### #6 HIGH: int() cast bez try/except

**Soubor:** `app/routers/tax/_helpers.py:137`

```python
unit = db.query(Unit).filter_by(unit_number=int(unit_number)).first()
```

**Popis:** `unit_number` je string ze sloupce `TaxDocument.unit_number` (VARCHAR). Pokud obsahuje neciselnou hodnotu (napr. "12A", ""), `int()` vyhodi `ValueError`. Funkce `_find_coowners` je volana z matching.py a sending.py.

**Doporuceni:**
```python
try:
    unit_num = int(unit_number)
except (ValueError, TypeError):
    return [owner_id]
unit = db.query(Unit).filter_by(unit_number=unit_num).first()
```

#### #7 HIGH: File attachment open() bez try/except

**Soubor:** `app/services/email_service.py:56-58`

```python
if not path.exists():
    continue
with open(path, "rb") as f:
    part = MIMEApplication(f.read(), ...)
```

**Popis:** TOCTOU (Time-of-check-to-time-of-use): soubor muze byt smazan mezi `exists()` a `open()`. Take muze selhat na `PermissionError`. Pokud se to stane v ramci batch odeslani, pada cely email pro daneho prijemce.

**Doporuceni:** Obalit `open()` v `try/except (IOError, OSError)` s logovanim a pokracovanim.

#### #14 MEDIUM: CSV cteni odchytava jen UnicodeDecodeError

**Soubor:** `app/routers/sync.py:188-194`

**Popis:** Cyklus zkousejici ruzna kodovani chyta pouze `UnicodeDecodeError`. `IOError`, `PermissionError` nebo jiny filesystem error neni odchycen a zpusobi 500 chybu.

### Pozitivni nalezy error handling:
- Vsechny `except Exception:` maji `logger.exception()` nebo `logger.warning()` -- zadne ticha selhani
- Custom error stranky (404, 500, 409) s cesky textem
- IntegrityError a OperationalError maji vlastni handlery
- HTMX error handling v app.js (responseError, sendError) -- uzivatel vidi cesky text
- Flash messages konzistentni (success/error/warning)
- "Entity not found => redirect" vzor dusledne dodrzovan

### 7. Git hygiene

#### Stav .gitignore:
```
__pycache__/     OK
*.py[cod]        OK
.venv/           OK
data/svj.db      OK
data/svj.db-shm  OK  (opraveno od posledniho auditu)
data/svj.db-wal  OK  (opraveno od posledniho auditu)
data/uploads/    OK
.env             OK
.playwright-mcp/ OK  (opraveno od posledniho auditu)
*.png            OK
```

#### Commit kvalita:
- Commit messages v cestine, strucne, vystiznne -- **OK**
- Posledni commity: `cb529da`, `317987b`, `7571e9a` -- dobre popisuji "co a proc"

#### Untracked soubory:
Git status ukazuje:
- `.playwright-mcp/console-*.log` -- 9 logovych souboru, ale adresar je v .gitignore, takze se necommitnou
- `data/svj.db-shm`, `data/svj.db-wal` -- jsou v .gitignore

### 8. Testy

#### #3 CRITICAL: Zadne testy

**Popis:** Adresar `tests/` neexistuje. Zadne unit testy, zadne integration testy. Projekt ma `pytest` a `httpx` v dev zavislosti, ale nic neni implementovano.

**Rizikove oblasti bez testu:**
- `owner_exchange.py` (235 radku, manipulace s vlastniky) -- nejslozitejsi business logika
- `voting_import.py` (216 radku preview, vice scenaru SJM)
- `_send_emails_batch()` (background thread, soubeznnost)
- `_build_recipients()` (deduplikace, status aggregace)
- `_find_coowners()` (cas overlap, int() cast)
- CSV/Excel import/parsovani

**Doporuceni:** Zacit s testy pro:
1. `_build_recipients()` -- ruzne kombinace owneru, externich prijemcu, statusu
2. `_find_coowners()` -- edge cases (neciselna jednotka, prazdny rok)
3. `owner_exchange.py` -- scenare 1->1, 1->N, N->1, N->M
4. Email service -- mock SMTP, validace message building

---

## Nove nalezy specificke pro rozesliku (sending.py, app.js, send.html)

### Rozeslika -- pozitivni nalezy:
- Checkbox state persistence v sessionStorage (prezije HTMX page swap)
- Scroll position save/restore pri navigaci
- Background thread s proper locking (`_sending_lock`)
- Batch sending s pauzou, pokracovanim, zrusenim
- Server restart recovery (`recover_stuck_sending_sessions`)
- Optimalizovany rebuild jednoho radku (ne cela tabulka)
- Dual email podpora (primary + secondary s checkboxy)
- Test email gateway s validaci pred ostrym odeslanim
- Confirmation modal pred odeslanim s detaily (pocet, predmet)

### Rozeslika -- problemy:
1. **#4 CRITICAL**: `original_filename` neexistuje na TaxDocument -- crash pri inline email edit
2. **#5 HIGH**: `is_completed` kontroluje `READY` misto `COMPLETED`
3. **#11 MEDIUM**: `update_recipient_email` ma 206 radku
4. **#28 LOW**: `toggleEmailSelect` pouziva raw fetch bez error handling

---

## Doporuceny postup oprav

### Faze 1 -- Kriticke (hned)
1. **#4** Opravit `original_filename` na `filename` v sending.py:317,355 -- zpusobuje crash
2. **#5** Opravit/prejmenovar `is_completed` logiku v _helpers.py a session.py

### Faze 2 -- Dulezite
3. **#6** Pridat try/except na int() cast v `_find_coowners`
4. **#7** Pridat try/except na file open v email_service.py
5. **#9** Odstranit nepouzitou zavislost `aiosmtplib`
6. **#14** Rozsirit exception handling v sync.py CSV cteni

### Faze 3 -- Udrzba
7. **#8** Upload limits centralizovat do config.py
8. **#10** Konsolidovat 3 ETA/progress funkce do spolecne utility
9. **#13** Zdokumentovat router package vzor v CLAUDE.md
10. **#18** Synchronizovat pdf.js verzi mezi base.html a app.js
11. **#28** Pridat error handling do toggleEmailSelect()

### Faze 4 -- Strategicke (planovani)
12. **#1, #2** Autentizace + CSRF -- implementovat dle planu v CLAUDE.md
13. **#3** Napsat testy pro kriticke business logiku
14. **#11, #12** Refaktorovat prilis dlouhe funkce
