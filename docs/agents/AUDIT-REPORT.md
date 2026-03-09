# SVJ Audit Report -- 2026-03-09

## Souhrn

- **CRITICAL: 3** (vsechny existujici strategicke -- auth, CSRF, testy)
- **HIGH: 1** (novy)
- **MEDIUM: 7** (5 novych, 2 pretrvavajici)
- **LOW: 8** (vsechny nove)

**Celkem: 19 nalezu -- 3 strategicke (auth/CSRF/testy), 16 novych k oprave**

### Stav predchoziho auditu (2026-03-08/09, 28 nalezu)

| # | Puvodni nalez | Stav |
|---|---------------|------|
| 1 | Zadna autentizace | Pretrvava -- plan v CLAUDE.md |
| 2 | Zadna CSRF ochrana | Pretrvava -- plan v CLAUDE.md |
| 3 | Zadne testy | Pretrvava |
| 4-18 | CRITICAL/HIGH/MEDIUM nalezy | **Vsechny opraveny** |
| 19-28 | LOW nalezy | **Opraveny** (krome #24 by design) |
| 21 | Inline importy presunute na top-level | **CASTECNE** -- viz novy nalez #5 |

---

## Souhrnna tabulka

| # | Oblast | Soubor | Severity | Problem | Cas | Rozhodnuti |
|---|--------|--------|----------|---------|-----|------------|
| 1 | Bezpecnost | cely projekt | CRITICAL | Zadna autentizace | vice dni | Znamy, plan v CLAUDE.md |
| 2 | Bezpecnost | cely projekt | CRITICAL | Zadna CSRF ochrana | vice dni | Znamy, resit s auth |
| 3 | Testy | cely projekt | CRITICAL | Zadne testy | vice dni | Znamy |
| 4 | Kod | ballots.py:394 | HIGH | Nepouzity import `Form as FastForm` zustava v kodu | ~2 min | 🔧 |
| 5 | Kod | 8 souboru | MEDIUM | Inline importy nebyly presunute na top-level (audit #21 nedokoncen) | ~15 min | 🔧 |
| 6 | Dokumentace | README.md:399,834 | MEDIUM | README odkazuje na `_has_processed_ballots` v _helpers.py -- presunuto na model | ~5 min | 🔧 |
| 7 | Kod | ballots.py:542-544 | MEDIUM | Manualni auto-width misto centralizovane `excel_auto_width()` | ~5 min | 🔧 |
| 8 | Konzistence | 3 soubory | MEDIUM | CSV export pouziva carku (default), ale CLAUDE.md vyzaduje strednik | ~10 min | ❓ |
| 9 | Git | .playwright-mcp/ | MEDIUM | 7 testovacich .xlsx souboru zbyva v adresari | ~1 min | 🔧 |
| 10 | Vykon | voting/session.py:60-88 | MEDIUM | O(V*B*BV) Python-side pocitani na seznamu hlasovani | ~30 min | ❓ |
| 11 | Kod | sending.py:599, processing.py:275, owners.py:507 | LOW | `compute_eta` importovano inline 3x misto top-level | ~5 min | 🔧 |
| 12 | Kod | session.py:179,187,287,295; owners.py:485,530,554,618 | LOW | `from urllib.parse import quote` importovano inline 8x | ~5 min | 🔧 |
| 13 | Kod | tax/session.py:555 | LOW | `from html import escape` importovano inline | ~2 min | 🔧 |
| 14 | Kod | tax/session.py:223,339 | LOW | `import time as _time` inline 2x (uz je v utils.py) | ~2 min | 🔧 |
| 15 | Kod | tax/sending.py:484 | LOW | `import asyncio` inline v jedinem miste pouziti | ~2 min | 🔧 |
| 16 | Dokumentace | docs/CLAUDE-zaloha.md | LOW | Zastarala kopie CLAUDE.md odkazuje na neexistujici `_build_name_with_titles()` | ~5 min | 🔧 |
| 17 | Kod | voting/import_votes.py:238 | LOW | `from app.models import VotingStatus` inline -- VotingStatus uz je v top-level importu | ~2 min | 🔧 |
| 18 | Kod | units.py:38,59,202,222,264,341 | LOW | `code_list_service` a `recalculate_unit_votes` importovane inline 6x v units.py | ~5 min | 🔧 |
| 19 | Dokumentace | CLAUDE.md:127 | LOW | CLAUDE.md referuje `build_name_with_titles()` v sekci "Budouci importy" jako `excel_import.py` funkce -- uz je v utils.py | ~2 min | 🔧 |

Legenda: 🔧 = jen opravit, ❓ = potreba rozhodnuti uzivatele (vice variant)

---

## Detailni nalezy

### 1. Bezpecnost

#### #1 Zadna autentizace (CRITICAL) -- pretrvava
- **Co a kde**: Vsechny endpointy jsou pristupne bez prihlaseni. Kazdy na siti muze mazat data, menit vlastniky, odesilat emaily.
- **Reseni**: Implementovat dle planu v CLAUDE.md § Uzivatelske role
- **Narocnost**: Vysoka (~2-3 dny)
- **Regrese riziko**: Stredni (nova vrstva autorizace muze rozbiti existujici flow)
- **Jak otestovat**: Zkusit pristoupit na `/vlastnici` bez prihlaseni -- melo by presmerovat na login

#### #2 Zadna CSRF ochrana (CRITICAL) -- pretrvava
- **Co a kde**: POST formulare nemaji CSRF tokeny. Utocnik muze vytvorit stranku, ktera odesle POST na SVJ aplikaci.
- **Reseni**: Implementovat spolecne s autentizaci (session-based CSRF token)
- **Narocnost**: Stredni (~4 hodiny, soucast auth)
- **Zavislosti**: Nejdriv #1 (autentizace)
- **Regrese riziko**: Nizke

#### #3 Zadne testy (CRITICAL) -- pretrvava
- **Co a kde**: Adresar `tests/` neexistuje. Zadne unit testy, zadne integration testy.
- **Reseni**: Vytvorit zakladni test suite pro kriticke business logiku (import, hlasovani, synchronizace)
- **Narocnost**: Vysoka (~2 dny pro zakladni pokryti)
- **Regrese riziko**: Zadne (pridavame nove soubory)

### 2. Kodova kvalita

#### #4 Nepouzity import `Form as FastForm` (HIGH)
- **Co a kde**: `app/routers/voting/ballots.py:394` -- `from fastapi import Form as FastForm` je importovano inline v `bulk_reset_ballots()`, ale nikde pouzito. Funkce pouziva `await request.form()` misto Form dependency.
- **Reseni**: Smazat radek 394 (`from fastapi import Form as FastForm`)
- **Narocnost + cas**: Nizka (~2 min)
- **Regrese riziko**: Zadne -- import neni pouzit
- **Jak otestovat**: Spustit server, POST na `/hlasovani/{id}/listky/hromadny-reset` -- musi fungovat stejne

#### #5 Inline importy nebyly kompletne presunute na top-level (MEDIUM)
- **Co a kde**: Predchozi audit #21 oznacil inline importy jako "OPRAVENO (presunuto na top-level ve vsech souborech)". Ve skutecnosti zustava **35+ inline importu** v routerech:
  - `from app.services.code_list_service import get_all_code_lists` -- 6x inline v `units.py`, `owners.py`
  - `from app.services.owner_exchange import recalculate_unit_votes` -- 4x inline v `units.py`, `owners.py`, `administration.py`, `sync.py`
  - `from urllib.parse import quote` -- 8x inline v `owners.py`, `tax/session.py`
  - `from app.utils import compute_eta` -- 3x inline v `sending.py`, `processing.py`, `owners.py`
  - `from html import escape` -- 1x v `tax/session.py:555`
  - `import time as _time` -- 2x v `tax/session.py:223,339`
  - `import asyncio` -- 1x v `tax/sending.py:484`
  - `from app.models import VotingStatus` -- 1x v `import_votes.py:238` (uz je v top-level importu)
  - `from app.models import EmailTemplate` -- 1x v `tax/session.py:144`
  - `from app.services.owner_service import ...` -- 3x v `administration.py`, `owners.py`
  - `from app.services.contact_import import ...` -- 2x v `owners.py`
- **Reseni**: Presunout na top-level. Nektere mohou byt legitimni (cirkularni zavislosti) -- overit:
  - `code_list_service`, `owner_exchange`, `compute_eta`, `quote`, `escape`, `asyncio`, `time` -- **zadna cirkularni zavislost**, mohou byt na top-level
  - `from app.database import SessionLocal` v `administration.py` -- legitimni (pouziti v threadu), ale muze byt top-level
  - `from app.main import run_post_restore_migrations` v `administration.py` -- potencialni cirkularni (main → routers → main)
- **Narocnost + cas**: Stredni (~15 min)
- **Regrese riziko**: Nizke (zmena mista importu)
- **Jak otestovat**: Spustit server, navigovat na vsechny moduly -- vsechny stranky musi fungovat

#### #7 Manualni auto-width misto centralizovane `excel_auto_width()` (MEDIUM)
- **Co a kde**: `app/routers/voting/ballots.py:542-544` -- v `export_not_submitted()` je rucne napsana auto-width logika identicky s `excel_auto_width()` z `utils.py`. Vsechny ostatni exporty uz pouzivaji centralizovanou funkci.
- **Reseni**: Nahradit radky 542-544 volanim `excel_auto_width(ws)` a pridat import z `app.utils`
- **Narocnost + cas**: Nizka (~5 min)
- **Regrese riziko**: Zadne
- **Jak otestovat**: Exportovat neodevzdane listky na `/hlasovani/{id}/neodevzdane/exportovat` -- sloupce musi mit spravnou sirku

#### #10 O(V*B*BV) Python-side pocitani na seznamu hlasovani (MEDIUM)
- **Co a kde**: `app/routers/voting/session.py:60-88` -- v `voting_list()` se pro kazde hlasovani iteruje pres vsechny listky a jejich hlasy v Pythonu (O(items * ballots * votes)). Pri vetsi evidenci (50+ hlasovani, 100+ listku) muze byt pomalat.
- **Reseni**:
  - Varianta A: SQL agregace pomoci GROUP BY (jako `_ballot_stats()`) -- rychlejsi, ale slozitejsi implementace
  - Varianta B: Ponechat -- pro typicke SVJ (~2-5 hlasovani) je to zanedbatelne
- **Narocnost + cas**: Stredni (~30 min pro variantu A)
- **Regrese riziko**: Stredni (zmena logiky vypoctu)
- **Jak otestovat**: Overit shodu vysledku na `/hlasovani` se stavajicimi daty

### 3. Dokumentace

#### #6 README odkazuje na neexistujici `_has_processed_ballots` (MEDIUM)
- **Co a kde**:
  - `README.md:399` -- directory tree uvadi `_helpers.py # _voting_wizard, _ballot_stats, _has_processed_ballots`
  - `README.md:834` -- changelog uvadi `Extrahovan _has_processed_ballots() helper`
  - Funkce byla presunuta jako property na model `Voting.has_processed_ballots` v poslednim auditu
- **Reseni**: Aktualizovat README -- nahradit `_has_processed_ballots` za `Voting.has_processed_ballots` v popisu, opravit directory tree
- **Narocnost + cas**: Nizka (~5 min)
- **Regrese riziko**: Zadne
- **Jak otestovat**: Precist README a overit ze souhlasi s kodem

#### #16 Zastarala kopie CLAUDE-zaloha.md (LOW)
- **Co a kde**: `docs/CLAUDE-zaloha.md` obsahuje starsi verzi CLAUDE.md. Odkazuje na `_build_name_with_titles()` v `excel_import.py` (radek 124), ale funkce se presunula do `utils.py` jako `build_name_with_titles()`.
- **Reseni**: Bud smazat `CLAUDE-zaloha.md` (pokud neni potreba) nebo aktualizovat
- **Narocnost + cas**: Nizka (~5 min)
- **Regrese riziko**: Zadne

#### #19 CLAUDE.md referuje `build_name_with_titles` jako funkci z excel_import (LOW)
- **Co a kde**: `CLAUDE.md:127` -- "Budouci importy: `build_name_with_titles()` z `app/utils.py` generuje prijmeni-first format" -- text je aktualizovany na spravne umisteni, ale stale je v sekci "Budouci importy" v kontextu Jmen vlastniku, coz muze byt matouci. Funkce uz neni "budouci" import ale aktualni utility.
- **Reseni**: Preformulovat na "Import dat: `build_name_with_titles()` z `app/utils.py`..."
- **Narocnost + cas**: Nizka (~2 min)
- **Regrese riziko**: Zadne

### 4. Konzistence

#### #8 CSV export pouziva carku misto stredniku (MEDIUM)
- **Co a kde**: CLAUDE.md:239 specifikuje "CSV: UTF-8 s BOM, strednik jako oddelovac". Ale vsechny CSV exporty pouzivaji `csv.writer(buf)` s defaultnim oddelovacem (carka):
  - `app/routers/owners.py:427`
  - `app/routers/units.py:551`
  - `app/services/data_export.py:323`
- **Reseni**:
  - Varianta A: Zmenit `csv.writer(buf, delimiter=';')` ve vsech exportech -- soulad s CLAUDE.md
  - Varianta B: Zmenit CLAUDE.md na carku -- carky jsou standardnejsi pro CSV
  - Poznamka: BOM (`utf-8-sig`) je spravne vsude pouzit
- **Narocnost + cas**: Nizka (~10 min)
- **Regrese riziko**: Nizke (zmena formatu exportu)
- **Jak otestovat**: Exportovat vlastniky CSV na `/vlastnici/exportovat/csv`, otevrit v textovem editoru -- overit oddelovac

### 5. Vykon

#### #10 -- viz sekce Kodova kvalita

### 6. Error handling

Zadne nove nalezy. Existujici error handling je robustni:
- Vsechny `except Exception:` maji logovani
- Custom error stranky (404, 500, 409) funguji
- HTMX error handling v app.js
- Entity not found → redirect vzor dodrzovan

### 7. Git hygiene

#### #9 Testovaci soubory v .playwright-mcp/ (MEDIUM)
- **Co a kde**: 7 Excel souboru zustava v `.playwright-mcp/` adresari z testovani:
  - `hlasovani-1-generated-20260309-054307.xlsx`
  - `hlasovani-1-processed-20260309-054337.xlsx`
  - `hlasovani-2-20260309-053253.xlsx`
  - `hlasovani-2-20260309-053303.xlsx`
  - `hlasovani-2-vsechny-20260309.xlsx`
  - `neodevzdane-1-20260309.xlsx`
  - `vlastnici-20260309.xlsx`
- **Reseni**: `rm -rf .playwright-mcp/*.xlsx` (CLAUDE.md explicitne rika ze se maji mazat po testovani)
- **Narocnost + cas**: Nizka (~1 min)
- **Regrese riziko**: Zadne
- **Jak otestovat**: `ls .playwright-mcp/` -- musi byt prazdny

### 8. Testy

#### #3 -- viz sekce Bezpecnost (pretrvava)

### Inline importy -- detailni prehled (#5, #11-#18)

| Soubor | Radek | Import | Top-level mozny? |
|--------|-------|--------|------------------|
| units.py | 38,59,222,264 | code_list_service.get_all_code_lists | ANO |
| units.py | 202,341 | owner_exchange.recalculate_unit_votes | ANO |
| owners.py | 485,530,554,618 | urllib.parse.quote | ANO |
| owners.py | 507 | app.utils.compute_eta | ANO |
| owners.py | 493,638 | services.contact_import | ANO |
| owners.py | 735 | models.owner.OwnerUnit | ANO (uz importovan pres app.models) |
| owners.py | 829,1062,1292,1321 | code_list_service.get_all_code_lists | ANO |
| owners.py | 1055 | services.owner_service.merge_owners | ANO |
| owners.py | 1282 | owner_exchange.recalculate_unit_votes | ANO |
| tax/session.py | 144 | models.EmailTemplate | ANO |
| tax/session.py | 179,187,287,295 | urllib.parse.quote | ANO |
| tax/session.py | 223,339 | time as _time | ANO |
| tax/session.py | 555 | html.escape | ANO |
| tax/sending.py | 484 | asyncio | ANO |
| tax/sending.py | 599 | utils.compute_eta | ANO |
| tax/processing.py | 275 | utils.compute_eta | ANO |
| tax/matching.py | 95,125 | urllib.parse.urlparse | ANO |
| voting/import_votes.py | 238 | models.VotingStatus | ANO (uz v top-level) |
| voting/ballots.py | 394 | fastapi.Form as FastForm | SMAZAT (nepouzity) |
| administration.py | 553,631,682,725,805 | database.SessionLocal | ANO |
| administration.py | 1258 | owner_exchange.recalculate_unit_votes | ANO |
| administration.py | 1285,1313,1341 | owner_service.* | ANO |
| sync.py | 631 | models.OwnerType | ANO |
| sync.py | 830 | owner_exchange.recalculate_unit_votes | ANO |
| share_check.py | 107 | urllib.parse.urlencode | ANO |
| main.py | 259-260,294 | models.* | Legitimni (funkce volanejsou v lifespan, ne v modulovem scope) |
| share_check_comparator.py | 357 | models.Unit | Legitimni (lazy import kvuli minimalizaci zavislosti) |

---

## Otevrene polozky

### Planovane (strategicke)

| # | Nalez | Priorita | Poznamka |
|---|-------|----------|----------|
| 1 | Autentizace | CRITICAL | Plan implementace v CLAUDE.md § Uzivatelske role |
| 2 | CSRF ochrana | CRITICAL | Implementovat spolecne s autentizaci |
| 3 | Testy | CRITICAL | Zakladni test suite pro kriticke business logiku |

### Nove nalezy k oprave

| # | Nalez | Priorita | Odhad |
|---|-------|----------|-------|
| 4 | Nepouzity import FastForm | HIGH | ~2 min |
| 5 | Inline importy nekompletne presunute | MEDIUM | ~15 min |
| 6 | README zastaraly popis _has_processed_ballots | MEDIUM | ~5 min |
| 7 | Manualni auto-width v ballots.py | MEDIUM | ~5 min |
| 8 | CSV oddelovac nesouhlasi s CLAUDE.md | MEDIUM | ~10 min |
| 9 | Testovaci .xlsx soubory v .playwright-mcp | MEDIUM | ~1 min |
| 10 | Python-side O(V*B*BV) pocitani na seznamu hlasovani | MEDIUM | ~30 min |
| 11-18 | LOW nalezy (inline importy, dokumentace) | LOW | ~25 min celkem |

### Ponechano (by design)

| # | Nalez (z predchoziho auditu) | Stav |
|---|------|------|
| 24 (puvodni) | Hardcoded wizard labels | By design — ceska aplikace bez i18n |

---

## Pozitivni nalezy

### Bezpecnost
- Zadne SQL injection -- ORM konzistentne pouzivan ve vsech routerech
- Autoescaping v Jinja2 -- zadne `|safe` s uzivatelskymi daty
- HTTP security headers (X-Frame-Options: DENY, X-Content-Type-Options: nosniff, Referrer-Policy)
- Path traversal ochrana v backup restore (os.path.realpath validace)
- Upload validace (velikost + pripona) na vsech upload endpointech -- centralizovane UPLOAD_LIMITS
- `is_safe_path()` pouzivan pro download endpointy
- SMTP heslo v `.env` souboru (v .gitignore)
- Verze zavislosti pinnuty v pyproject.toml (zadna known vulnerability)
- SQL identifier validace v `_ensure_indexes()` (regex)
- `unidecode` zavislost kompletne odstranena -- nahrazena `strip_diacritics()`

### Vykon
- 38 databazovych indexu v `_ensure_indexes()`
- SQL agregace v `_ballot_stats()` misto Python-side pocitani
- WAL mode pro SQLite (concurrent reads)
- Optimalizovany rebuild jednoho radku v `update_recipient_email()`
- Centralizovane upload limity (UPLOAD_LIMITS)
- `has_processed_ballots` property na Voting modelu -- vsechna pouziti maji eager-loaded balloty

### Kod
- Refaktorovane dlouhe funkce (update_recipient_email 206→95, apply_selected_updates 263→130)
- Centralizovane utility (compute_eta, build_wizard_steps, build_name_with_titles, UPLOAD_LIMITS, excel_auto_width)
- `has_processed_ballots` presunuto z helper funkce na model property
- `build_wizard_steps` sdileny mezi voting a tax moduly
- `strip_diacritics` jednotne pouzivan misto `unidecode`
- pdf.js verze dynamicky synchronizovana
- JS error handling v toggleEmailSelect (disable, rollback, catch)
- Escape handler ma typeof safety checks

### Error handling
- Vsechny `except Exception:` maji `logger.exception()` nebo `logger.warning()`
- Custom error stranky (404, 500, 409) s cesky textem
- IntegrityError a OperationalError maji vlastni handlery
- HTMX error handling v app.js (responseError, sendError)
- Flash messages konzistentni (success/error/warning)
- Entity not found → redirect vzor dusledne dodrzovan
- Starlette monkey-patching s try/except fallback

### Git hygiene
- .gitignore pokryva vsechny generovane soubory vcetne .playwright-mcp/
- Commit messages v cestine, strucne, vystizne
- Konzistentni styl kodu

### Pristupnost
- Formularove inputy maji `<label>` nebo `aria-label`
- SVG ikony maji `aria-hidden="true"`
- Search input ma `aria-label="Hledat"`

### Dokumentace
- CLAUDE.md ma TOC s anchor odkazy
- Router package vzor zdokumentovan
- UI_GUIDE.md jako jediny zdroj pravdy pro frontend konvence
- Tri dokumenty (CLAUDE.md, README.md, UI_GUIDE.md) vzajemne propojene

---

## Doporuceny postup oprav

1. **#9** Smazat testovaci soubory v .playwright-mcp (~1 min)
2. **#4** Smazat nepouzity import FastForm v ballots.py (~2 min)
3. **#7** Nahradit manualni auto-width za `excel_auto_width(ws)` (~5 min)
4. **#6** Aktualizovat README -- opravit reference na _has_processed_ballots (~5 min)
5. **#8** Rozhodnout: zmenit CSV oddelovac na strednik nebo zmenit CLAUDE.md (~10 min)
6. **#5** Presunout inline importy na top-level ve vsech souborech (~15 min)
7. **#11-18** Opravit zbyle LOW nalezy (~25 min)
8. **#10** Volitelne: optimalizovat Python-side pocitani na seznamu hlasovani (~30 min)
9. **#19** Opravit CLAUDE.md formulaci pro build_name_with_titles (~2 min)
10. **#1-3** Strategicke: autentizace, CSRF, testy (planovat separatne)
