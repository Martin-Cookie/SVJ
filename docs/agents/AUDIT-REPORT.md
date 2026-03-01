# SVJ Audit Report – 2026-03-01

## Souhrn

- **CRITICAL: 8**
- **HIGH: 12**
- **MEDIUM: 22**
- **LOW: 10**

---

## Souhrnná tabulka

| # | Oblast | Soubor | Severity | Problém | Doporučení |
|---|--------|--------|----------|---------|------------|
| 1 | Bezpečnost | app/\* | CRITICAL | Žádná autentizace/autorizace — všechny endpointy veřejné | Implementovat RBAC (viz CLAUDE.md § Uživatelské role) |
| 2 | Bezpečnost | app/config.py:7 | CRITICAL | `debug: bool = True` v produkci — SQL logy, stacktrace viditelné | `debug = False` default, `.env` override pro dev |
| 3 | Bezpečnost | app/routers/tax.py:1233 | CRITICAL | Tax PDF download bez validace cesty — potenciální path traversal | Přidat `.is_relative_to()` kontrolu |
| 4 | Bezpečnost | app/routers/settings_page.py:203 | CRITICAL | File path traversal — `startswith()` místo `is_relative_to()` | Změnit na `resolved.relative_to(allowed_path)` |
| 5 | Kód | app/routers/tax.py | CRITICAL | 2107 řádků — nezvladatelný soubor | Rozdělit na 5 sub-routerů |
| 6 | Kód | tax.py + owners.py | CRITICAL | Duplikovaná ETA/progress logika (80% shoda) | Extrahovat do `services/progress_service.py` |
| 7 | Kód | voting.py + tax.py | CRITICAL | Duplikovaný wizard stepper (90% shoda) | Extrahovat do `services/wizard_service.py` |
| 8 | Testy | — | CRITICAL | Žádné testy — 0% pokrytí 13 492 řádků kódu | Vytvořit `tests/` s unit a integration testy |
| 9 | Bezpečnost | pyproject.toml | HIGH | Nepinnuté verze balíčků (`>=` místo `==`) | Vytvořit `requirements.txt` s přesnými verzemi |
| 10 | Bezpečnost | app/templates/\* | HIGH | Absence CSRF ochrany na POST formulářích | Přidat CSRFMiddleware |
| 11 | Bezpečnost | app/routers/\* | HIGH | File upload bez validace MIME typů a velikosti | Přidat magic bytes check + MAX_FILE_SIZE |
| 12 | UI | app/templates/\* | HIGH | Žádný HTMX error handler — 500 chyby se mlčky spolknou | Přidat globální `htmx:responseError` handler v app.js |
| 13 | UI | app/templates/base.html:22 | HIGH | Sidebar fixní 176px na mobilech — obsah se nevejde | Hamburger menu + responsive sidebar |
| 14 | UI | app/templates/\* | HIGH | Search inputy bez `<label>` nebo `aria-label` (~30 míst) | Přidat `aria-label` + `.sr-only` label |
| 15 | UI | app/templates/\* | HIGH | Checkbox/radio bez svázání `for`/`id` (~20+ míst) | Přidat `id` na input a `for` na label |
| 16 | Výkon | app/routers/voting.py:112 | HIGH | N+1 query — 4 vnořené smyčky s lazy loading | Agregovaný SQL dotaz místo Python loopu |
| 17 | Výkon | app/routers/owners.py:156 | HIGH | Python-side sort s lazy loading — N×2 dotazů | SQL ORDER BY místo Python sort |
| 18 | Error | app/main.py:215 | HIGH | `except Exception: pass` — tichá selhání indexů | `logger.error()` místo `pass` |
| 19 | Dokumentace | README.md | HIGH | HTMX partial endpointy nejsou dokumentovány | Přidat sekci "HTMX Partial Endpoints" |
| 20 | Kód | 6+ souborů | HIGH | Duplikovaný file upload pattern | Centralizovat do `services/file_service.py` |
| 21 | Bezpečnost | app/routers/tax.py:37 | MEDIUM | Race condition — `_processing_progress` dict není thread-safe | Přidat `threading.Lock()` |
| 22 | Bezpečnost | app/routers/\* | MEDIUM | Chybí bounds checking na numerických inputech | Přidat validaci rozsahů |
| 23 | UI | app/templates/\* | MEDIUM | Nekonzistentní button styling — 4 různé varianty | Vytvořit Jinja2 macro nebo CSS component |
| 24 | UI | app/templates/\* | MEDIUM | Nekonzistentní input padding (`py-1.5` vs `py-2`, `rounded` vs `rounded-lg`) | Sjednotit styling inputů |
| 25 | UI | app/templates/\* | MEDIUM | SVG ikony bez `aria-hidden="true"` (~50+) | Přidat `aria-hidden="true" focusable="false"` |
| 26 | UI | app/templates/\* | MEDIUM | Loading indikátory jen u 4 souborů z 99 HTMX interakcí | Přidat hx-indicator ke klíčovým operacím |
| 27 | UI | app/templates/\* | MEDIUM | Touch targets < 44px na mobilech (`py-1.5` = ~25px) | Zvýšit padding na mobilech |
| 28 | UI | app/templates/\* | MEDIUM | Heading hierarchy porušená — každá stránka začíná `<h1>` | Přidat hlavní h1 do base.html |
| 29 | UI | dark-mode.css | MEDIUM | Chybí focus ring styling v dark mode | Přidat `.dark input:focus` CSS |
| 30 | UI | app/templates/\* | MEDIUM | Error messages nepropojené s inputy přes `aria-describedby` | Přidat `aria-invalid` + `aria-describedby` |
| 31 | Výkon | app/routers/voting.py:80 | MEDIUM | N+1 v `_ballot_stats()` — lazy loading `b.votes` v cyklu | Eager load `joinedload(Voting.ballots).joinedload(Ballot.votes)` |
| 32 | Error | app/services/word_parser.py:148 | MEDIUM | `except Exception: pass` — DOCX metadata selhání ignorováno | `logger.debug()` |
| 33 | Error | app/services/contact_import.py:150 | MEDIUM | `load_workbook()` bez try/except — crash na poškozeném souboru | Přidat error handling |
| 34 | Error | app/services/email_service.py:79 | MEDIUM | SMTP connect bez timeout parametru | Přidat `timeout=10` |
| 35 | Error | app/routers/units.py:81 | MEDIUM | `int()`/`float()` parsing bez error handling — `ValueError` | Přidat try/except nebo validaci |
| 36 | Dokumentace | CLAUDE.md | MEDIUM | Import kontaktů workflow není popsán | Přidat sekci o contact import |
| 37 | Dokumentace | README.md | MEDIUM | API tabulky nekompletní — chybí HTMX partials | Doplnit nebo označit "main endpoints only" |
| 38 | Dokumentace | README.md | MEDIUM | Moduly a API endpointy jsou v oddělených sekcích — rozpojené | Sloučit do jedné sekce na modul |
| 39 | Dokumentace | README.md | MEDIUM | Chybí popis error responses v API tabulkách | Přidat odkaz na CLAUDE.md error handling |
| 40 | Dokumentace | app/services/excel_import.py | MEDIUM | Helper funkce bez docstringů a type hintů | Přidat Google-style docstrings |
| 41 | Git | data/backups/ | MEDIUM | Zálohy nejsou v .gitignore | Přidat `data/backups/` do .gitignore |
| 42 | Kód | app/routers/\* | MEDIUM | 206× hardcoded `status_code=302` | Vytvořit konstantu `REDIRECT_STATUS` |
| 43 | UI | app/templates/base.html | LOW | Flash messages bez `data-auto-dismiss` — nezavírají se automaticky | Přidat atribut |
| 44 | UI | app/templates/\* | LOW | Tabulky bez responsive card view na mobilech | Přidat alternativní mobilní layout |
| 45 | UI | app/templates/\* | LOW | Font `text-xs` (12px) na mobilních tabulkách — těžko čitelné | `text-xs sm:text-sm` |
| 46 | Dokumentace | README.md | LOW | .env setup chybí Linux/Windows cesty k LibreOffice | Přidat hints do .env.example |
| 47 | Dokumentace | README.md | LOW | USB wheels popis neúplný | Rozšířit sekci |
| 48 | Dokumentace | CLAUDE.md:316 | LOW | Uživatelské role — chybí "ZATÍM NEIMPLEMENTOVÁNO" label | Přidat upozornění |
| 49 | Dokumentace | app/routers/voting.py:261 | LOW | `traceback.print_exc()` místo `logger.exception()` | Nahradit za logging |
| 50 | Kód | app/services/excel_import.py:41 | LOW | Nepoužívaný `import re` | Smazat |
| 51 | Kód | app/services/owner_exchange.py:11 | LOW | Nepoužívaný `from difflib import SequenceMatcher` | Smazat |
| 52 | Dokumentace | docs/UI_GUIDE.md | LOW | Admin seznamy — doporučení "karty" vs realita "tabulky" | Sjednotit |

---

## Detailní nálezy

### 1. Kódová kvalita

#### 1.1 Příliš velké soubory

| Soubor | Řádky | Doporučení |
|--------|-------|------------|
| `app/routers/tax.py` | 2107 | Rozdělit na 5 sub-routerů (list, import, matching, sending, status) |
| `app/routers/administration.py` | 1339 | Rozdělit na 4 (svj_info, backups, bulk_edit, purge) |
| `app/routers/voting.py` | 1201 | Rozdělit na 3-4 (list, detail, process, import) |
| `app/routers/owners.py` | 1155 | Rozdělit na 3 (list/detail, import, contact_import) |
| `app/routers/sync.py` | 1113 | Rozdělit na 3 (list, compare, contact_preview) |

#### 1.2 Duplikace kódu

**ETA/Progress kalkulace** — `tax.py:758-791` a `owners.py:332-357` — 80% identický kód. Řešení: `services/progress_service.py` s funkcí `compute_eta(total, current, started_at)`.

**Wizard stepper** — `voting.py:40-71` a `tax.py:55-87` — 90% identický kód. Řešení: `services/wizard_service.py` s generalizovanou `build_wizard_steps()`.

**File upload** — identický pattern v 6+ souborech (timestamp, mkdir, copyfileobj). Řešení: `services/file_service.py` s `upload_file(file, subdir) -> Path`.

#### 1.3 Nepoužívané importy

- `app/services/excel_import.py:41` — `import re`
- `app/services/owner_exchange.py:11` — `from difflib import SequenceMatcher`

#### 1.4 Hardcoded hodnoty

206× `status_code=302` v 8 routerech. Doporučení: konstanta v `app/constants.py`.

---

### 2. Bezpečnost

#### 2.1 Žádná autentizace (CRITICAL)

Všechny endpointy jsou veřejně přístupné. Kdokoli s přístupem k síti může mazat data, odesílat emaily, exportovat citlivé údaje. Plán implementace rolí existuje v CLAUDE.md, ale není realizován.

#### 2.2 Debug mode zapnutý (CRITICAL)

`app/config.py:7` — `debug: bool = True`. SQL dotazy se logují na stdout, Jinja2 vrací stacktrace s kódem.

#### 2.3 Path traversal riziko (CRITICAL)

- `app/routers/tax.py:1233` — Tax PDF download kontroluje existenci souboru, ale ne zda je v povoleném adresáři
- `app/routers/settings_page.py:203` — Validace cesty přes `startswith()` místo bezpečného `is_relative_to()`

#### 2.4 Další bezpečnostní nálezy

- **CSRF** — POST formuláře bez CSRF tokenů (MEDIUM)
- **File upload** — jen kontrola přípony, ne MIME typu ani velikosti (MEDIUM)
- **Race condition** — in-memory `_processing_progress` dict bez `threading.Lock()` (MEDIUM)
- **Bounds checking** — numerické inputy bez validace rozsahů (MEDIUM)
- **SQL injection** — SQLAlchemy ORM korektně parametrizuje (OK ✓)
- **XSS** — Jinja2 autoescape zapnutý, `|safe` jen pro SVG konstanty (OK ✓)
- **.env** — správně v `.gitignore` (OK ✓)

---

### 3. Dokumentace

#### 3.1 CLAUDE.md

- Chybí popis import kontaktů workflow (caching, progress, multi-step flow)
- Sekce "Uživatelské role" by měla být jasněji označena jako "ZATÍM NEIMPLEMENTOVÁNO"
- TaxSession lifecycle není zdokumentován

#### 3.2 README.md

- API tabulky jsou nekompletní — HTMX partial endpointy chybí
- Moduly a API endpointy jsou v oddělených sekcích (duplicitní údržba)
- Chybí popis error responses
- .env setup neuvádí cesty k LibreOffice pro Linux/Windows
- USB wheels popis neúplný

#### 3.3 Komentáře v kódu

- Helper funkce v services nemají docstrings (25+)
- `traceback.print_exc()` místo loggeru v `voting.py:261`
- Žádné docstringy na router endpointech

---

### 4. UI / Šablony

#### 4.1 Konzistence

- **Tlačítka** — 4 různé CSS varianty bez jednotné konvence (175 výskytů)
- **Inputy** — nekonzistentní padding (`py-1.5` vs `py-2`), border-radius (`rounded` vs `rounded-lg`)
- **Flash messages** — bez `data-auto-dismiss` atributu (nezavírají se automaticky)

#### 4.2 HTMX

- **Žádný error handler** — 500 a network chyby se mlčky spolknou (HIGH)
- **Loading indikátory** — jen 4/99 HTMX interakcí má spinner (MEDIUM)
- **hx-target** validace — potenciálně rozbité při refaktoringu šablon

#### 4.3 Responsive design

- **Sidebar** — fixní 176px i na mobilech, obsah se nevejde (HIGH)
- **Tabulky** — žádná alternativa pro mobily (card view)
- **Touch targets** — `py-1.5` = ~25px, WCAG vyžaduje min 44px
- **Font** — `text-xs` (12px) na mobilních tabulkách

#### 4.4 Přístupnost (WCAG AA)

- **Search inputy** — bez `<label>` nebo `aria-label` (~30 míst)
- **Checkbox/radio** — bez svázání `for`/`id` (~20+ míst)
- **SVG ikony** — bez `aria-hidden="true"` (~50+)
- **Heading hierarchy** — každá stránka začíná `<h1>`, chybí globální hierarchie
- **Error messages** — nepropojené s inputy přes `aria-describedby`
- **Focus ring** — chybí v dark mode

---

### 5. Výkon

#### 5.1 N+1 dotazy

- `voting.py:112-150` — 4 vnořené smyčky s lazy loading (5 hlasování × 100 lístků × 5 položek = 2500+ dotazů)
- `voting.py:80-102` — `_ballot_stats()` iteruje `b.votes` bez eager loading
- `owners.py:156-172` — Python-side sort s lazy loading `current_units` (N×2 dotazů)
- `dashboard.py:112-150` — duplikátní query na `Voting` bez eager loading

#### 5.2 Další výkonnostní problémy

- Synchronní Excel/PDF parsing v main threadu — může blokovat desítky sekund
- Žádný rate limiting na hromadné odesílání emailů
- Žádná pagination na velkých dotazech

---

### 6. Error Handling

#### 6.1 Tichá selhání

- `app/main.py:215` — `except Exception: pass` na index creation
- `app/services/word_parser.py:148` — `except Exception: pass` na DOCX metadata
- `app/routers/sync.py:91` — `except Exception: pass` na file deletion

#### 6.2 Chybějící error handling

- `app/services/contact_import.py:150` — `load_workbook()` bez try/except
- `app/routers/units.py:81` — `int()`/`float()` parsing bez error handling
- `app/services/email_service.py:79` — SMTP bez timeout parametru
- `app/routers/owners.py:88` — `db.commit()` bez IntegrityError handling

#### 6.3 HTTP chybové stránky

- Žádná custom 404/500 stránka
- Entity not found → redirect (302) na seznam (záměr dle CLAUDE.md)

---

### 7. Git Hygiene

#### 7.1 .gitignore

Správně obsahuje: `__pycache__/`, `*.py[cod]`, `.venv/`, `.env`, `data/svj.db`, `data/uploads/`

**Chybí:** `data/backups/` (záložní ZIP soubory by neměly být v gitu)

#### 7.2 Nežádoucí soubory

- `data/backups/` — netrackováno, ale není v .gitignore
- `docs/UI_PRINCIPLES_PORTABLE.md` — potenciální duplikát UI_GUIDE.md
- `CODE-GUARDIAN.md` — audit script, netrackováno

#### 7.3 Commit kvalita

- Srozumitelné české commit messages ✓
- Commity odpovídají logickým celkům ✓

---

### 8. Testy

#### 8.1 Pokrytí

**Žádné testy neexistují.** Adresář `tests/` neexistuje. 13 492 řádků kódu bez jakéhokoli automatického testování.

#### 8.2 Kritické moduly bez testů

1. **Import/export** — Excel parsing, owner matching, data merging
2. **Email service** — SMTP selhání, timeout, batch sending
3. **Voting** — počítání hlasů, kvórum, SJM spoluvlastnictví
4. **Synchronizace** — CSV/Excel porovnání, exchange logika
5. **Business logic** — podíly SČD, daňové distribuce

#### 8.3 Doporučená struktura testů

```
tests/
├── unit/
│   ├── test_models.py
│   ├── test_services/
│   │   ├── test_email_service.py
│   │   ├── test_excel_import.py
│   │   ├── test_voting_import.py
│   │   └── test_contact_import.py
│   └── test_utils.py
├── integration/
│   ├── test_owner_workflow.py
│   ├── test_voting_workflow.py
│   └── test_sync.py
└── conftest.py
```

---

## Pozitivní aspekty

- **SQLAlchemy ORM** korektně parametrizuje SQL — žádné SQL injection riziko ✓
- **Jinja2 autoescape** zapnutý — XSS riziko minimální ✓
- **Eager loading** v core routerech (owners, units, voting) ✓
- **Back URL navigace** konzistentně implementovaná ✓
- **HTMX partial responses** správně řešeny ✓
- **Dokumentace** (CLAUDE.md 414 řádků, UI_GUIDE.md 719 řádků) — nadprůměrně detailní ✓
- **Struktura projektu** — čisté oddělení routers/services/models ✓
- **Pojmenování** — konzistentní snake_case, české slugy bez angličtiny ✓
- **Žádné TODO/FIXME/HACK** komentáře — kód je hotový ✓
- **Email HTML escaping** — plain text se automaticky escapuje ✓
- **.gitignore** — produkční data, databáze, .env nejsou commitnuty ✓

---

## Doporučený postup oprav

### Fáze 1 — CRITICAL (1 týden)

1. Nastavit `debug = False` v `config.py` (5 min)
2. Opravit path traversal — `is_relative_to()` v `settings_page.py` a `tax.py` (30 min)
3. Přidat globální HTMX error handler do `app.js` (30 min)
4. Přidat `data/backups/` do `.gitignore` (5 min)

### Fáze 2 — HIGH (2 týdny)

5. Přidat CSRF middleware (2 hod)
6. Přidat file upload validaci — MIME type + size limit (2 hod)
7. Opravit N+1 queries v voting (eager loading) (2 hod)
8. Přidat `aria-label` ke search inputům a svázat checkbox labely (3 hod)
9. Extrahovat duplikovaný kód (ETA, wizard, file upload) do services (1 den)
10. Pinnuté verze v `requirements.txt` (1 hod)

### Fáze 3 — MEDIUM (měsíc)

11. Responsive sidebar (hamburger menu)
12. Sjednotit button/input styling (macro nebo CSS component)
13. Rozdělit velké routery na sub-moduly
14. Přidat unit testy pro kritické business logic
15. Doplnit docstrings a type hints

### Fáze 4 — LOW (průběžně)

16. Flash messages auto-dismiss
17. Mobilní card view pro tabulky
18. Heading hierarchy fix
19. Dokumentace — doplnit README API tabulky
