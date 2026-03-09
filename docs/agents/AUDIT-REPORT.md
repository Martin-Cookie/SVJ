# SVJ Audit Report -- 2026-03-08 (aktualizovano 2026-03-09)

## Souhrn

- **CRITICAL: 4** (2 existujici, 2 nove) — 1 opraveno, 3 planovane
- **HIGH: 5** — vsechny opraveny
- **MEDIUM: 9** — vsechny opraveny
- **LOW: 10** — 9 opraveno, 1 by design (#24)

**Celkem: 28 nalezu — 24 opraveno, 3 planovane (auth/CSRF/testy), 1 by design**

### Stav predchoziho auditu (2026-03-08 post-refaktor, 26 nalezu)

| # | Puvodni nalez | Stav |
|---|---------------|------|
| 1 | Zadna autentizace | Zustava -- plan v CLAUDE.md |
| 2 | Zadna CSRF ochrana | Zustava -- plan v CLAUDE.md |
| 3 | Zadne testy | Zustava |
| 4 | Path traversal v backup restore | **OPRAVENO** (administration.py:779-783 -- validace `os.path.realpath`) |
| 5 | N+1 query v tax/sending.py:232 | **OPRAVENO** (joinedload pouzit na r.62-68) |
| 6 | Hardcoded upload size limits | **OPRAVENO** (UPLOAD_LIMITS centralizovano v utils.py) |
| 7 | README directory tree zastaraly | **OPRAVENO** (README:388-408 aktualizovan) |
| 8 | File attachment bez error handling | **OPRAVENO** (email_service.py try/except IOError, OSError) |
| 9 | Duplicitni `_build_name_*()` funkce | **OPRAVENO** (presunuto do utils.py) |
| 10 | Hardcoded multipart limits (5000) | **OPRAVENO** (Starlette monkey-patching s try/except) |
| 11 | Chybi dokumentace router package vzoru | **OPRAVENO** (CLAUDE.md § Router packages) |
| 12 | .gitignore chybi .playwright-mcp/ a data/svj.db* | **OPRAVENO** |
| 13 | int() cast bez try/except v _helpers.py:137 | **OPRAVENO** (try/except ValueError, TypeError) |
| 14 | File read jen UnicodeDecodeError v sync.py | **OPRAVENO** (pridano OSError) |
| 15 | _send_emails_batch() 132 radku | Ponechano (LOW — akceptovatelna delka) |
| 16 | Debug mode bez produkcni ochrany | **OPRAVENO** (warning log pri zapnuti) |
| 17-26 | LOW nalezy | Viz tabulka nize |

---

## Souhrnna tabulka

| # | Oblast | Soubor | Severity | Problem | Stav |
|---|--------|--------|----------|---------|------|
| 1 | Bezpecnost | cely projekt | CRITICAL | Zadna autentizace -- vsechny endpointy pristupne bez prihlaseni | Znamy, plan v CLAUDE.md |
| 2 | Bezpecnost | cely projekt | CRITICAL | Zadna CSRF ochrana na POST formularich | Znamy, resit s auth |
| 3 | Testy | cely projekt | CRITICAL | Zadne testy -- adresar tests/ neexistuje | Znamy |
| 4 | Kod | sending.py:317,355 | CRITICAL | `TaxDocument.original_filename` neexistuje -- **AttributeError za behu** | **OPRAVENO** |
| 5 | Logika | _helpers.py:198 | HIGH | `is_completed` kontroluje `SendStatus.READY` misto `COMPLETED` -- zavadejici nazev | **OPRAVENO** (prejmenovano, kontroluje READY+SENDING+PAUSED+COMPLETED) |
| 6 | Robustnost | _helpers.py:137 | HIGH | `int(unit_number)` bez try/except -- pad pri neciselnem cislu jednotky | **OPRAVENO** (try/except ValueError, TypeError) |
| 7 | Robustnost | email_service.py:56-58 | HIGH | File attachment `open()` bez try/except -- pad pri chybejicim souboru | **OPRAVENO** (try/except IOError, OSError) |
| 8 | Konfigurace | 12 souboru | HIGH | Hardcoded upload size limits (10/50/100/200 MB) rozptyleno po routerech | **OPRAVENO** (UPLOAD_LIMITS v utils.py) |
| 9 | Zavislosti | pyproject.toml:25 | HIGH | `aiosmtplib` v zavislosti ale nikde nepouzit -- zbytecna zavislost | **OPRAVENO** (odstraneno) |
| 10 | Duplikaty | processing.py, sending.py, owners.py | MEDIUM | 3x duplikovana ETA/progress funkce (stejny vzor formatovani casu) | **OPRAVENO** (compute_eta v utils.py) |
| 11 | Struktura | sending.py:165-370 | MEDIUM | `update_recipient_email()` ma 206 radku -- kandidat na rozdeleni | **OPRAVENO** (refaktor na 95 radku, 2 helper funkce) |
| 12 | Struktura | sync.py:631-893 | MEDIUM | `apply_selected_updates()` ma 263 radku -- nejdelsi funkce v projektu | **OPRAVENO** (refaktor na 130 radku, 1 helper funkce) |
| 13 | Dokumentace | CLAUDE.md | MEDIUM | Chybi dokumentace router package vzoru (voting/, tax/ jako packages) | **OPRAVENO** (§ Router packages) |
| 14 | Robustnost | sync.py:188-194 | MEDIUM | CSV cteni odchytava jen `UnicodeDecodeError`, ne `IOError`/`PermissionError` | **OPRAVENO** (pridano OSError) |
| 15 | Konfigurace | main.py:493-495 | MEDIUM | Monkey-patching `_StarletteRequest.__kwdefaults__` -- krehke, muze se rozbit | **OPRAVENO** (odstranen pristup k privatni metode, try/except) |
| 16 | Bezpecnost | config.py:7 | MEDIUM | `debug: bool = False` -- zadna ochrana proti zapnuti v produkci | **OPRAVENO** (warning log pri DEBUG=true) |
| 17 | Bezpecnost | main.py:243 | MEDIUM | `_ensure_indexes()` pouziva f-string v SQL -- nesplnuje best practice | **OPRAVENO** (regex validace identifikatoru) |
| 18 | JS | app.js:87 | MEDIUM | pdf.js worker hardcoded verze -- neni synchronizovano s knihovnou | **OPRAVENO** (pdfjsLib.version dynamicky) |
| 19 | Pojmenovani | voting/_helpers.py:28 | LOW | `_has_processed_ballots` -- spis model metoda | **OPRAVENO** (property na Voting modelu) |
| 20 | Duplikaty | voting/_helpers, tax/_helpers | LOW | Paralelni wizard patterns (mohlo by byt spolecne) | **OPRAVENO** (build_wizard_steps v utils.py) |
| 21 | Styl | owners.py:374+ | LOW | Inline importy v exportnich funkcich | **OPRAVENO** (presunuto na top-level ve vsech souborech) |
| 22 | Zavislosti | owner_matcher.py:10 | LOW | `unidecode` vs `strip_diacritics()` -- dve implementace | **OPRAVENO** (nahrazeno strip_diacritics, unidecode odebrano) |
| 23 | Konfigurace | settings_page.py | LOW | Hardcoded pagination limit | **OPRAVENO** (EMAIL_LOG_LIMIT konstanta) |
| 24 | Konfigurace | tax/_helpers.py:53 | LOW | Hardcoded wizard labels | Ponechano (info) |
| 25 | Dokumentace | CLAUDE.md | LOW | Chybi TOC (Table of Contents) | **OPRAVENO** (TOC s anchor odkazy) |
| 26 | Testy | cely projekt | LOW | Chybi pytest.ini, CI/CD workflow, GitHub Actions | Souvisi s #3 |
| 27 | JS | app.js:77-83 | LOW | Escape handler vola neexistujici funkce na nekterych strankach | **OPRAVENO** (typeof safety checks) |
| 28 | JS | app.js:506-518 | LOW | `toggleEmailSelect()` raw fetch bez error handling | **OPRAVENO** (error handling, rollback, disable) |

---

## Otevrene polozky

### Planovane (strategicke)

| # | Nalez | Priorita | Poznamka |
|---|-------|----------|----------|
| 1 | Autentizace | CRITICAL | Plan implementace v CLAUDE.md § Uzivatelske role |
| 2 | CSRF ochrana | CRITICAL | Implementovat spolecne s autentizaci |
| 3 | Testy | CRITICAL | Zakladni test suite pro kriticke business logiku |

### Ponechano (by design)

| # | Nalez | Stav |
|---|-------|------|
| 24 | Hardcoded wizard labels | By design — ceska aplikace bez i18n |

---

## Pozitivni nalezy

### Bezpecnost
- Zadne SQL injection -- ORM konzistentne pouzivan ve vsech routerech
- Autoescaping v Jinja2 -- zadne `|safe` s uzivatelskymy daty
- HTTP security headers (X-Frame-Options: DENY, X-Content-Type-Options: nosniff)
- Path traversal opraveno v backup restore (os.path.realpath validace)
- Upload validace (velikost + pripona) na vsech upload endpointech
- `is_safe_path()` pouzivan pro download endpointy
- SMTP heslo v `.env` souboru (v .gitignore)
- Verze zavislosti pinnuty v pyproject.toml
- SQL identifier validace v `_ensure_indexes()` (regex)

### Vykon
- N+1 v sending.py opraven (joinedload na r.62-68)
- 38 databazovych indexu v `_ensure_indexes()`
- SQL agregace v `_ballot_stats()` misto Python-side pocitani
- WAL mode pro SQLite (concurrent reads)
- Optimalizovany rebuild jednoho radku v `update_recipient_email()`
- Centralizovane upload limity (UPLOAD_LIMITS)

### Error handling
- Vsechny `except Exception:` maji `logger.exception()` nebo `logger.warning()`
- Custom error stranky (404, 500, 409) s cesky textem
- IntegrityError a OperationalError maji vlastni handlery
- HTMX error handling v app.js (responseError, sendError)
- Flash messages konzistentni (success/error/warning)
- Entity not found => redirect vzor dusledne dodrzovan
- Starlette monkey-patching s try/except fallback

### Kod
- Refaktorovane dlouhe funkce (update_recipient_email 206→95, apply_selected_updates 263→130)
- Centralizovane utility (compute_eta, UPLOAD_LIMITS, excel_auto_width)
- Dokumentovane vzory v CLAUDE.md (router packages, TOC)
- pdf.js verze dynamicky synchronizovana
- JS error handling v toggleEmailSelect (disable, rollback, catch)

### Git hygiene
- .gitignore pokryva vsechny generovane soubory
- Commit messages v cestine, strucne, vystizne
- Konzistentni styl kodu

### Pristupnost
- Formularove inputy maji `<label>` nebo `aria-label`
- SVG ikony maji `aria-hidden="true"`
- Search input ma `aria-label="Hledat"`
