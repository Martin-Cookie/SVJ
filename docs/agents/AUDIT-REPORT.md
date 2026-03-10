# SVJ Audit Report -- 2026-03-10

## Souhrn

- **CRITICAL: 3** (strategicke pretrvavajici -- auth, CSRF, testy)
- **HIGH: 1** (novy -- XSS v units.py)
- **MEDIUM: 5** (3 nove, 2 pretrvavajici)
- **LOW: 6** (4 nove, 2 pretrvavajici)

**Celkem: 15 nalezu -- 3 strategicke (auth/CSRF/testy), 12 novych/pretrvavajicich k oprave**

Z 16 nalezu z predchoziho auditu (2026-03-09) bylo **10 opraveno**, 6 pretrvava.

---

## Stav predchoziho auditu (2026-03-09, 19 nalezu)

| # | Puvodni nalez | Stav |
|---|---------------|------|
| 1 | Zadna autentizace | **Pretrvava** -- plan v CLAUDE.md |
| 2 | Zadna CSRF ochrana | **Pretrvava** -- plan v CLAUDE.md |
| 3 | Zadne testy | **Pretrvava** |
| 4 | Nepouzity import `Form as FastForm` v ballots.py | **Opraveno** (commit 7af4fb0) |
| 5 | Inline importy nekompletne presunute na top-level | **Vetsinou opraveno** -- zbyva 11 inline importu (viz #9) |
| 6 | README zastaraly popis `_has_processed_ballots` | **Opraveno** (README aktualizovan v changelogu) |
| 7 | Manualni auto-width v ballots.py | **Opraveno** (commit 7af4fb0, ballots.py pouziva `excel_auto_width()`) |
| 8 | CSV oddelovac nesouhlasi s CLAUDE.md | **Opraveno** (delimiter=";", commit 7af4fb0) |
| 9 | Testovaci .xlsx soubory v .playwright-mcp | **Opraveno** (adresar je prazdny) |
| 10 | Python-side O(V*B*BV) pocitani na seznamu hlasovani | **Opraveno** (SQL agregace v commit 9c36d4d) |
| 11-15 | Inline importy (compute_eta, quote, escape, time, asyncio) | **Opraveno** (presunuto na top-level) |
| 16 | Zastarala CLAUDE-zaloha.md | **Pretrvava** -- soubor stale existuje |
| 17 | VotingStatus inline import (uz v top-level) | **Opraveno** |
| 18 | units.py inline importy | **Opraveno** (presunuto na top-level) |
| 19 | CLAUDE.md formulace build_name_with_titles | **Opraveno** (prepsan na "Import dat") |

---

## Souhrnna tabulka novych + pretrvavajicich nalezu

| # | Oblast | Soubor | Severity | Problem | Cas | Rozhodnuti |
|---|--------|--------|----------|---------|-----|------------|
| 1 | Bezpecnost | cely projekt | CRITICAL | Zadna autentizace | vice dni | Znamy, plan v CLAUDE.md |
| 2 | Bezpecnost | cely projekt | CRITICAL | Zadna CSRF ochrana | vice dni | Znamy, resit s auth |
| 3 | Testy | cely projekt | CRITICAL | Zadne testy | vice dni | Znamy |
| 4 | Bezpecnost | units.py:111,119,141-142 | HIGH | XSS v warning HTML -- uzivatelsky vstup ve f-string bez escapovani | ~15 min | 🔧 |
| 5 | Vykon | voting/session.py:347-361 | MEDIUM | Python-side iterace na voting detail (opraveno na seznamu, ne na detailu) | ~20 min | ❓ |
| 6 | Konzistence | voting/session.py:347-361 vs :54-103 | MEDIUM | Nekonzistence: seznam pouziva SQL agregaci, detail Python iteraci | ~20 min | 🔧 |
| 7 | Kod | owners.py:641,819,846 | MEDIUM | `from pathlib import Path` inline 3x -- Path uz importovan na radku 9 | ~2 min | 🔧 |
| 8 | Dokumentace | docs/CLAUDE-zaloha.md | LOW | Zastarala kopie CLAUDE.md (pretrvava z minuleho auditu) | ~2 min | 🔧 |
| 9 | Kod | owners.py:985, settings_page.py:196, administration.py:139,630,681,720,729,745,829 | LOW | Zbyvajicich 11 inline importu (smtplib, markupsafe.escape, sa_func, app.main, sqlite3) | ~10 min | 🔧/❓ |
| 10 | Kod | owners.py:127 | LOW | `force_create` cten z `await request.form()` misto `Form("")` parametru | ~5 min | 🔧 |
| 11 | Vykon | settings_page.py:89-97 | LOW | Diacritics fallback search nacte 500 EmailLog zaznamu do Pythonu | ~15 min | ❓ |
| 12 | Bezpecnost | voting/session.py:208 | LOW | Exception detail v JSON odpovedi (`type(e).__name__: {e}`) -- info leakage | ~5 min | 🔧 |
| 13 | Bezpecnost | settings_page.py:225 | LOW | SMTP exception `str(e)` zobrazena uzivateli -- moze odhalit interni detaily | ~5 min | 🔧 |
| 14 | Kod | units.py:139-146, 360-376 | LOW | Duplicitni warn_html generovani v unit_create i unit_update | ~10 min | 🔧 |

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

#### #4 XSS v warning HTML pri vytvareni/uprave jednotky (HIGH) -- NOVY

- **Co a kde**: `app/routers/units.py` -- funkce `unit_create()` (radky 111, 119, 141-142) a `unit_update()` (radky 329, 337, 362-363). Uzivatelsky vstup z form poli `floor_area` a `podil_scd` je vlozen do HTML pres f-string **bez escapovani**:
  ```python
  warnings.append("Plocha '" + floor_area.strip() + "' neni platne cislo")  # radek 111
  warn_items = "".join(f"<li>{w}</li>" for w in warnings)  # radek 141
  return HTMLResponse(content=f'{warn_html}...')  # radek 144
  ```
  Pokud utocnik odesle `<script>alert(1)</script>` jako plochu, JavaScript se spusti v prohlizeci.
- **Reseni**: Escapovat uzivatelsky vstup pred vlozenim do HTML:
  ```python
  from markupsafe import escape
  warnings.append(f"Plocha '{escape(floor_area.strip())}' neni platne cislo")
  ```
  Alternativne: pouzit Jinja2 sablonu misto inline HTML (lepsi systemove reseni).
- **Narocnost + cas**: Nizka (~15 min)
- **Regrese riziko**: Zadne
- **Jak otestovat**: Otevrit `/jednotky/nova`, zadat `<img src=x onerror=alert(1)>` do pole Plocha, odeslat formular -- alert se NESMI zobrazit

#### #12 Exception detail v JSON odpovedi (LOW) -- NOVY

- **Co a kde**: `app/routers/voting/session.py:208` -- `JSONResponse({"error": f"{type(e).__name__}: {e}"})` vraci plnou traceback informaci vcetne typu vyjimky a zpravy. Muze odhalit interni cesty k souborum, nazvy knihoven, strukturu kodu.
- **Reseni**: Nahradit genericou zpravou:
  ```python
  return JSONResponse({"error": "Nelze zpracovat nahranou sablonu."}, status_code=500)
  ```
  Detail logovat pres `logger.exception()` (uz se loguje).
- **Narocnost + cas**: Nizka (~5 min)
- **Regrese riziko**: Zadne
- **Jak otestovat**: Nahrat poskozeny .docx soubor jako sablonu hlasovani -- odpoved musi obsahovat generickou chybu, ne traceback

#### #13 SMTP exception zobrazena uzivateli (LOW) -- NOVY

- **Co a kde**: `app/routers/settings_page.py:225` -- `f"Pripojeni selhalo: {e}"`. SMTP vyjimka muze obsahovat IP adresy, porty, interni sitove informace.
- **Reseni**: Zobrazit generickou zpravu, detail logovat:
  ```python
  logger.warning("SMTP test failed: %s", e)
  smtp_test_error = "Pripojeni k SMTP serveru selhalo."
  ```
- **Narocnost + cas**: Nizka (~5 min)
- **Regrese riziko**: Zadne
- **Jak otestovat**: Zadat neplatny SMTP server v nastaveni, kliknout "Test pripojeni" -- musi zobrazit generickou zpravu

### 2. Kodova kvalita

#### #7 `from pathlib import Path` inline 3x v owners.py (MEDIUM) -- NOVY

- **Co a kde**: `app/routers/owners.py` -- `from pathlib import Path` se importuje inline na radcich 641, 819 a 846, prestoze Path je uz importovany na radku 9 (`from pathlib import Path`). Vzniklo zrejme v UX audit commitech, ktere pridaly nove funkce bez kontroly existujicich top-level importu.
- **Reseni**: Smazat 3 inline importy na radcich 641, 819, 846.
- **Narocnost + cas**: Nizka (~2 min)
- **Regrese riziko**: Zadne -- import uz je na top-level
- **Jak otestovat**: Spustit server, navigovat na `/vlastnici/import` a smazat importovany zaznam -- musi fungovat

#### #9 Zbyvajicich 11 inline importu v routerech (LOW) -- PRETRVAVA (castecne)

- **Co a kde**: Z puvodniho nalezu #5 (35+ inline importu) bylo vetsina opravena. Zbyva:

| Soubor | Radek | Import | Top-level mozny? |
|--------|-------|--------|------------------|
| owners.py | 985 | `from markupsafe import escape` | ANO |
| settings_page.py | 196 | `import smtplib` | ANO |
| administration.py | 139 | `from sqlalchemy import func as sa_func` | ANO |
| administration.py | 630,681,745,829 | `from app.main import run_post_restore_migrations` | CIRKULARNI -- legitimni |
| administration.py | 720 | `from app.database import engine` | ANO |
| administration.py | 729 | `import sqlite3` | ANO |

- **Reseni**: Presunout na top-level kde je to mozne (6 z 11). Import `app.main` nechat inline (cirkularni zavislost main -> routers -> main).
- **Narocnost + cas**: Nizka (~10 min)
- **Regrese riziko**: Nizke
- **Jak otestovat**: Spustit server, otestovat administraci a nastaveni

#### #10 `force_create` cteny pres redundantni `await request.form()` (LOW) -- NOVY

- **Co a kde**: `app/routers/owners.py:127` -- funkce `owner_create()` pouziva `Form(...)` parametry pro vsechna pole, ale `force_create` je cten separatne pres `(await request.form()).get("force_create", "")`. To je redundantni (Starlette cachuje parsed form, takze neni chyba), ale nesystemove.
- **Reseni**: Pridat `force_create: str = Form("")` do parametru funkce.
- **Narocnost + cas**: Nizka (~5 min)
- **Regrese riziko**: Nizke
- **Jak otestovat**: Vytvorit noveho vlastnika s duplicitnim jmenem, overit ze se zobrazi varovani a kliknuti na "Vytvorit i pres duplicitu" funguje

#### #14 Duplicitni warn_html generovani v units.py (LOW) -- NOVY

- **Co a kde**: `app/routers/units.py` -- identicky blok kodu pro generovani `warn_html` s validacnimi varovanimi se opakuje ve dvou funkcich:
  - `unit_create()` radky 106-142
  - `unit_update()` radky 324-363
  Vcetne stejne logiky parsovani cisiel (floor_area, podil_scd) s warnings.
- **Reseni**: Extrahovat do helper funkce `_parse_unit_fields(floor_area, podil_scd) -> (float|None, float|None, list[str])` a `_warn_html(warnings) -> str`.
- **Narocnost + cas**: Nizka (~10 min)
- **Regrese riziko**: Nizke
- **Jak otestovat**: Vytvorit a upravit jednotku s neplatnou plochou -- varovanim musi zustat stejne

### 3. Vykon

#### #5 Python-side iterace na voting detail -- nekonzistence s list (MEDIUM) -- NOVY

- **Co a kde**: `app/routers/voting/session.py:347-361` -- funkce `voting_detail()` pocita hlasy per item pomoci trojite vnorene smycky (items x ballots x votes). Pritom `voting_list()` na radcich 54-103 uz pouziva SQL agregaci (commit 9c36d4d). Na detail strance jsou data eager-loaded (radky 325-329), takze to neni N+1, ale stale je to O(I*B*V) v Pythonu.
- **Reseni**:
  - Varianta A: Pouzit stejnou SQL agregaci jako na seznamu (item_stats_q) + filtrovat na voting_id. Konzistentni pristup.
  - Varianta B: Ponechat -- data jsou eager-loaded, takze pro typicke SVJ (~5-10 bodu, ~100 listku) je to <1ms. Ale nekonzistence je codesmell.
- **Narocnost + cas**: Stredni (~20 min pro variantu A)
- **Regrese riziko**: Stredni (zmena logiky vypoctu)
- **Jak otestovat**: Overit ze vysledky na `/hlasovani/{id}` odpovidaji excelove exportu

#### #11 Diacritics fallback search v settings nacte 500 zaznamu (LOW) -- NOVY

- **Co a kde**: `app/routers/settings_page.py:89-97` -- pri hledani s diakritikou nacte az 500 EmailLog zaznamu do Pythonu a iteruje je pro diacritics-insensitive matching. U vetsi evidence (1000+ emailu) muze byt pomale.
- **Reseni**:
  - Varianta A: Pridat `name_normalized` sloupec na EmailLog a hledat SQL-side (jako u Owner)
  - Varianta B: Ponechat s limitem 500 -- pro typicke SVJ staci
- **Narocnost + cas**: Stredni (~15 min pro variantu A)
- **Regrese riziko**: Nizke
- **Jak otestovat**: Hledat v email logu ceske jmeno (s diakritikou) -- musi najit

### 4. Dokumentace

#### #8 Zastarala CLAUDE-zaloha.md (LOW) -- pretrvava

- **Co a kde**: `docs/CLAUDE-zaloha.md` stale existuje a obsahuje starsi verzi CLAUDE.md s neplatnymi referencemi (`_build_name_with_titles()` v `excel_import.py`, radek 124).
- **Reseni**: Smazat soubor -- neni referencovan nikde a obsahuje zastarale informace.
- **Narocnost + cas**: Nizka (~2 min)
- **Regrese riziko**: Zadne

---

## Pozitivni nalezy

### Bezpecnost

- Zadne SQL injection -- ORM konzistentne pouzivan ve vsech routerech
- Autoescaping v Jinja2 -- `|safe` pouzito POUZE pro template-definovane SVG sipky (ne uzivatelska data)
- HTTP security headers (X-Frame-Options: DENY, X-Content-Type-Options: nosniff, Referrer-Policy)
- Path traversal ochrana v backup restore (os.path.realpath validace)
- Upload validace (velikost + pripona) na vsech upload endpointech -- centralizovane UPLOAD_LIMITS
- `is_safe_path()` pouzivan pro download endpointy
- SMTP heslo v `.env` souboru (v .gitignore)
- Verze zavislosti pinnuty v pyproject.toml
- SQL identifier validace v `_ensure_indexes()` (regex)
- Detekce duplicit pri vytvareni vlastniku (jmeno, RC, email) -- NOVE
- Email validace pri vytvareni vlastniku (`is_valid_email`) -- NOVE

### Vykon

- 38 databazovych indexu v `_ensure_indexes()`
- **SQL agregace v `voting_list()`** -- NOVE: O(V*B*BV) Python iterace nahrazena SQL GROUP BY (commit 9c36d4d)
- SQL agregace v `_ballot_stats()` pro statusove bubliny
- WAL mode pro SQLite (concurrent reads)
- Centralizovane upload limity (UPLOAD_LIMITS)
- `has_processed_ballots` property na Voting modelu -- vsechna pouziti maji eager-loaded balloty
- Eager loading s `joinedload()` konzistentne pouzivan na vsech datovych strankach

### Kod

- Inline importy z predchoziho auditu vetsinou opraveny (35+ -> 11, z nichz 4 legitimni cirkularni)
- CSV delimiter opraven na strednik (`;`) v souladu s CLAUDE.md
- `excel_auto_width()` pouzivan konzistentne ve vsech exportech
- Centralizovane utility (compute_eta, build_wizard_steps, build_name_with_titles, UPLOAD_LIMITS, excel_auto_width)
- `strip_diacritics` jednotne pouzivan
- Top-level importy v units.py (code_list_service, recalculate_unit_votes) -- opraveno
- pdf.js verze dynamicky synchronizovana

### UI/Sablony -- NOVE pozitivni nalezy

- Focus trap v modalech (pdf-modal, confirm-modal, send-confirm-modal)
- Escape handler zavre vsechny modaly
- Focus restore pri zavreni modalu (`_modalTrigger` pattern)
- `role="dialog"` a `role="alertdialog"` na modalech, `aria-modal="true"`
- `role="alert"` na flash messages
- `aria-label="Zavrit hlasku"` na dismiss tlacitku
- `data-confirm` globalni handler nahrazuje browser `confirm()` -- pristupny custom modal
- `beforeunload` varovani pro neulozene formulare (`data-warn-unsaved`)
- HTMX loading pulse animace na search inputech
- Disable submit tlacitek behem HTMX requestu (CSS `.htmx-request`)
- Dashboard onboarding pro prazdnou evidenci
- Validace duplicit pri vytvareni vlastniku s moznosti "force create"
- SMTP test pripojeni v nastaveni

### Error handling

- Vsechny `except Exception:` maji `logger.exception()`, `logger.warning()` nebo `logger.debug()`
- Custom error stranky (404, 500, 409) s cesky textem
- IntegrityError a OperationalError maji vlastni handlery
- HTMX error handling v app.js (responseError, sendError) -- s user-friendly zpravou + "Obnovit stranku" odkazem
- Flash messages konzistentni (success/error/warning)
- Entity not found -> redirect vzor dusledne dodrzovan
- File cleanup failures logovany ale neblokuji DB operace
- SMTP `server.quit()` s except/pass -- legitimni (best-effort cleanup)

### Git hygiene

- .gitignore pokryva vsechny generovane soubory
- .playwright-mcp/ prazdny (predchozi testovaci soubory uklizeny)
- Commit messages v cestine, strucne, vystizne
- Konzistentni styl kodu

### Pristupnost -- VYLEPSENO

- Formularove inputy maji `<label>` nebo `aria-label`
- SVG ikony maji `aria-hidden="true"`
- Search inputy maji `aria-label="Hledat"`
- Modaly maji `role="dialog"` / `role="alertdialog"`, `aria-modal="true"`, `aria-labelledby` / `aria-describedby`
- Focus trap v modalech (Tab cycling)
- Focus restore po zavreni modalu
- Escape klaves zavre modaly
- Flash messages maji `role="alert"`

### Dokumentace

- CLAUDE.md ma TOC s anchor odkazy
- Router package vzor zdokumentovan
- UI_GUIDE.md jako jediny zdroj pravdy pro frontend konvence
- Tri dokumenty (CLAUDE.md, README.md, UI_GUIDE.md) vzajemne propojene
- README aktualizovany s UX audit nalezy (6 vln dokumentovanych)

---

## Otevrene polozky

### Planovane (strategicke)

| # | Nalez | Priorita | Poznamka |
|---|-------|----------|----------|
| 1 | Autentizace | CRITICAL | Plan implementace v CLAUDE.md § Uzivatelske role |
| 2 | CSRF ochrana | CRITICAL | Implementovat spolecne s autentizaci |
| 3 | Testy | CRITICAL | Zakladni test suite pro kriticke business logiku |

### Nalezy k oprave

| # | Nalez | Priorita | Odhad | Novy/Pretrvava |
|---|-------|----------|-------|----------------|
| 4 | XSS v units.py warning HTML | HIGH | ~15 min | Novy |
| 5 | Python-side iterace na voting detail (nekonzistence) | MEDIUM | ~20 min | Novy |
| 7 | `from pathlib import Path` inline 3x v owners.py | MEDIUM | ~2 min | Novy |
| 8 | Zastarala CLAUDE-zaloha.md | LOW | ~2 min | Pretrvava |
| 9 | Zbyvajicich 11 inline importu | LOW | ~10 min | Pretrvava (castecne) |
| 10 | `force_create` cten nesystemove | LOW | ~5 min | Novy |
| 11 | Diacritics fallback search v settings (500 rows) | LOW | ~15 min | Novy |
| 12 | Exception detail v JSON odpovedi | LOW | ~5 min | Novy |
| 13 | SMTP exception zobrazena uzivateli | LOW | ~5 min | Novy |
| 14 | Duplicitni warn_html kod v units.py | LOW | ~10 min | Novy |

### Ponechano (by design)

| Nalez | Stav |
|-------|------|
| Hardcoded wizard labels | By design -- ceska aplikace bez i18n |
| `from app.main import run_post_restore_migrations` inline | Legitimni -- cirkularni zavislost |

---

## Doporuceny postup oprav

1. **#4** XSS v units.py -- escapovat uzivatelsky vstup (~15 min) -- **PRIORITA: bezpecnost**
2. **#7** Smazat redundantni `from pathlib import Path` v owners.py (~2 min)
3. **#12** Nahradit exception detail generickou zpravou v voting/session.py (~5 min)
4. **#13** Nahradit SMTP exception generickou zpravou v settings_page.py (~5 min)
5. **#8** Smazat docs/CLAUDE-zaloha.md (~2 min)
6. **#14** Extrahovat duplicitni warn_html do helper funkce (~10 min)
7. **#9** Presunout zbyvajici legitimni inline importy na top-level (~10 min)
8. **#10** Pridat `force_create` jako Form parametr (~5 min)
9. **#5** Volitelne: sjednotit SQL agregaci na voting detail (~20 min)
10. **#11** Volitelne: pridat name_normalized na EmailLog (~15 min)
11. **#1-3** Strategicke: autentizace, CSRF, testy (planovat separatne)

**Celkovy odhadovany cas pro polozky 1-8: ~54 minut**
