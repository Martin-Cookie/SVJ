# SVJ Audit Report -- 2026-03-18

## Souhrn

- **CRITICAL: 2**
- **HIGH: 6**
- **MEDIUM: 12**
- **LOW: 8**

**Celkem: 28 nálezů**

---

## Souhrnná tabulka

| # | Oblast | Soubor | Severity | Problém | Čas | Rozhodnutí |
|---|--------|--------|----------|---------|-----|------------|
| 1 | Bezpečnost | celý projekt | CRITICAL | Žádná autentizace ani autorizace | ~8 hod | ❓ |
| 2 | Bezpečnost | šablony (97 formulářů) | CRITICAL | Žádná CSRF ochrana na POST formulářích | ~4 hod | ❓ |
| 3 | Bezpečnost | `app/config.py:17` | HIGH | SMTP heslo v plaintext konfiguraci (runtime paměť) | ~30 min | 🔧 |
| 4 | Kód | `app/main.py` (lifespan) | HIGH | Duplikace migrací -- lifespan vs `run_post_restore_migrations()` | ~1 hod | 🔧 |
| 5 | Výkon | více routerů | HIGH | Žádná paginace na hlavních seznamech (vlastníci, jednotky, hlasování) | ~3 hod | ❓ |
| 6 | Kód | 30+ funkcí | HIGH | Velmi dlouhé funkce (až 256 řádků) -- obtížná údržba | ~4 hod | ❓ |
| 7 | Git | `.playwright-mcp/` | HIGH | 26 souborů z testování (logy + screenshoty) nebyly po testování smazány | ~2 min | 🔧 |
| 8 | Testy | `tests/` | HIGH | Minimální testové pokrytí -- 23 testů na 10 500 řádků routerů | ~8 hod | ❓ |
| 9 | Kód | 9 routerů | MEDIUM | Duplicitní boilerplate: `Jinja2Templates` + `setup_jinja_filters` v každém routeru | ~1 hod | 🔧 |
| 10 | Kód | 20 souborů, 44 výskytů | MEDIUM | `datetime.utcnow()` je deprecated od Python 3.12 | ~1 hod | 🔧 |
| 11 | Bezpečnost | `app/templates/*.html` | MEDIUM | 6 výskytů `\|safe` filtru v šablonách (SVG ikony) | ~30 min | 🔧 |
| 12 | UI | celý projekt | MEDIUM | Žádná overflow-x ochrana tabulek na mobilech | ~2 hod | ❓ |
| 13 | Výkon | `app/services/email_service.py` | MEDIUM | Synchronní SMTP odesílání blokuje request thread | ~3 hod | ❓ |
| 14 | Error | více routerů | MEDIUM | 10+ míst s `except Exception: pass` -- tichá selhání | ~1 hod | 🔧 |
| 15 | Kód | `app/routers/administration.py:83-87` | MEDIUM | Hardcoded cesty `DATA_DIR`, `DB_PATH` místo `settings.*` | ~15 min | 🔧 |
| 16 | Dokumentace | komentáře | MEDIUM | Komplexní funkce bez docstringů (routerové endpointy) | ~2 hod | 🔧 |
| 17 | Kód | `app/services/email_service.py:72-194` | MEDIUM | Opakující se EmailLog creation pattern (4x copy-paste) | ~1 hod | 🔧 |
| 18 | Bezpečnost | `app/main.py:556-561` | MEDIUM | Monkey-patching Starlette `max_files` limitu -- křehké | ~30 min | ❓ |
| 19 | UI | šablony | MEDIUM | Přístupnost: mnoho `<input>` bez explicitního `<label for>` propojení | ~3 hod | 🔧 |
| 20 | Git | git historie | MEDIUM | Binární soubory (PNG screenshoty) v git historii z commitů 0288989, 4408941 | ~15 min | ❓ |
| 21 | Kód | `app/main.py:204-206` | LOW | `_migrate_svj_import_mappings()` používá f-string v SQL `ALTER TABLE` | ~10 min | 🔧 |
| 22 | Výkon | dashboard | LOW | Dashboard načítá všechna hlasování s `joinedload(ballots.votes)` | ~30 min | 🔧 |
| 23 | Kód | `app/routers/administration.py` | LOW | 1386 řádků -- kandidát na rozdělení do package | ~2 hod | ❓ |
| 24 | Kód | `app/routers/sync.py` | LOW | 1166 řádků -- kandidát na rozdělení do package | ~2 hod | ❓ |
| 25 | Dokumentace | `README.md` | LOW | API endpointy nejsou kompletně zdokumentovány | ~1 hod | 🔧 |
| 26 | UI | `app/templates/base.html` | LOW | CDN závislosti (Tailwind, HTMX) -- nefunguje offline | ~1 hod | ❓ |
| 27 | Kód | `app/models/owner.py:61-62` | LOW | `datetime.utcnow` jako default bez závorek -- vyhodnocuje se jednou při startu | ~5 min | 🔧 |
| 28 | Testy | `tests/conftest.py:23` | LOW | Fixture `test_engine` má `scope="session"` ale `db_session` nemá rollback isolation pro DDL | ~30 min | 🔧 |

Legenda: 🔧 = jen opravit, ❓ = potřeba rozhodnutí uživatele (více variant)

---

## Detailní nálezy

### 1. Kódová kvalita

#### N1 -- Duplicitní migrace v `main.py` (HIGH)

**Co a kde:** `app/main.py` řádky 398-480 (lifespan) a řádky 352-395 (`run_post_restore_migrations`) obsahují identický seznam migrací. Při přidání nové migrace se musí přidat na obě místa.

**Řešení:** Extrahovat společný seznam migrací do sdílené funkce `_run_all_migrations()` a volat ji z obou míst.

**Náročnost + čas:** nízká, ~1 hod
**Regrese riziko:** nízké -- čistý refaktoring
**Jak otestovat:** Spustit server (`uvicorn app.main:app`), ověřit že migrace proběhnou v logu. Pak obnovit zálohu a ověřit, že i post-restore migrace proběhnou.

---

#### N2 -- Velmi dlouhé funkce (HIGH)

**Co a kde:** 30+ funkcí má přes 50 řádků, nejhorší případy:
- `app/services/contact_import.py:125` -- `preview_contact_import()` = 256 řádků
- `app/routers/tax/processing.py:32` -- `_process_tax_files()` = 243 řádků
- `app/services/owner_exchange.py:232` -- `execute_exchange()` = 235 řádků
- `app/services/voting_import.py:188` -- `preview_voting_import()` = 216 řádků
- `app/services/csv_comparator.py:171` -- `compare_owners()` = 192 řádků
- `app/routers/voting/session.py:461` -- `generate_ballots()` = 188 řádků
- `app/routers/dashboard.py:82` -- `home()` = 172 řádků

**Řešení:** Rozdělit na menší helper funkce. Každý logický krok (validace, transformace, uložení) extrahovat. Cíl: max 80 řádků na funkci.

**Varianty:**
1. Postupný refaktoring -- jedna funkce za iteraci (bezpečnější)
2. Hromadný refaktoring -- všechny najednou (rychlejší, rizikovější)

**Náročnost + čas:** střední, ~4 hod celkem (postupně)
**Regrese riziko:** střední -- při rozdělení funkce hrozí narušení datového toku
**Jak otestovat:** Po každém refaktoringu otestovat dotčenou stránku (import, hlasování, dashboard).

---

#### N3 -- Duplicitní boilerplate v routerech (MEDIUM)

**Co a kde:** 9 routerových modulů opakuje identický vzor:
```python
templates = Jinja2Templates(directory="app/templates")
setup_jinja_filters(templates)
```
Nalezeno v: `_helpers.py` (owners, voting, tax), `dashboard.py`, `settings_page.py`, `share_check.py`, `administration.py`, `units.py`, `sync.py`.

**Řešení:** Vytvořit sdílenou instanci `templates` v `app/utils.py` nebo `app/templates_config.py` a importovat ji ve všech routerech.

**Náročnost + čas:** nízká, ~1 hod
**Regrese riziko:** nízké
**Jak otestovat:** Spustit server, projít všechny stránky.

---

#### N4 -- `datetime.utcnow()` deprecated (MEDIUM)

**Co a kde:** 44 výskytů ve 20 souborech. `datetime.utcnow()` je deprecated od Python 3.12 (bude odstraněno v budoucí verzi). Projekt cílí na Python 3.9+, ale je vhodné migrovat preventivně.

**Řešení:** Nahradit `datetime.utcnow()` za `datetime.now(timezone.utc)` (pro hodnoty s timezone) nebo zachovat stávající vzor s komentářem. SQLAlchemy modely s `default=datetime.utcnow` fungují správně (předává se callable).

**Varianty:**
1. Nahradit všechny výskyty za `datetime.now(timezone.utc)` -- čistší, ale mění datový formát (aware vs naive)
2. Ponechat a přidat `# noqa` -- minimální zásah, řeší se až při přechodu na Python 3.14+

**Náročnost + čas:** nízká, ~1 hod
**Regrese riziko:** nízké (SQLite ukládá text, nezáleží na timezone info)
**Jak otestovat:** Spustit testy: `pytest tests/`

---

#### N5 -- Hardcoded datové cesty (MEDIUM)

**Co a kde:** `app/routers/administration.py:83-87` definuje:
```python
DATA_DIR = Path("data")
DB_PATH = DATA_DIR / "svj.db"
UPLOADS_DIR = DATA_DIR / "uploads"
GENERATED_DIR = DATA_DIR / "generated"
BACKUP_DIR = DATA_DIR / "backups"
```
Tyto jsou duplicitní s `settings.database_path`, `settings.upload_dir`, `settings.generated_dir`.

**Řešení:** Nahradit za `settings.*` proměnné a přidat `settings.backup_dir` do `config.py`.

**Náročnost + čas:** nízká, ~15 min
**Regrese riziko:** nízké
**Jak otestovat:** Spustit server, otevřít Administrace > Zálohy, vytvořit a obnovit zálohu.

---

#### N6 -- Duplicitní EmailLog creation pattern (MEDIUM)

**Co a kde:** `app/services/email_service.py:72-194` -- funkce `send_email()` obsahuje 4 téměř identické bloky pro vytvoření `EmailLog` záznamu při různých chybových stavech (řádky 92-103, 119-127, 131-139, 141-150).

**Řešení:** Extrahovat helper `_create_error_log(db, to_email, to_name, subject, body_html, module, reference_id, error_msg)` a volat ho na 4 místech.

**Náročnost + čas:** nízká, ~1 hod
**Regrese riziko:** nízké
**Jak otestovat:** Poslat testovací email z Nastavení > SMTP > Test.

---

#### N7 -- Velké routery bez package struktury (LOW)

**Co a kde:**
- `app/routers/administration.py` -- 1386 řádků
- `app/routers/sync.py` -- 1166 řádků

Oba překračují hranici 1500 řádků blízkou doporučení v CLAUDE.md pro rozdělení na package.

**Řešení:** Rozdělit podle logických celků:
- `administration/` -- `svj_info.py`, `backups.py`, `purge.py`, `export.py`, `code_lists.py`, `bulk_edit.py`, `duplicates.py`
- `sync/` -- `session.py`, `compare.py`, `exchange.py`, `contacts.py`

**Náročnost + čas:** střední, ~2 hod za každý
**Regrese riziko:** nízké (čistý refaktoring, importy zůstanou beze změny díky `__init__.py`)
**Jak otestovat:** Spustit server, projít všechny stránky dotčených modulů.

---

#### N8 -- f-string v SQL ALTER TABLE (LOW)

**Co a kde:** `app/main.py:204-206`:
```python
conn.execute(text(
    f"ALTER TABLE svj_info ADD COLUMN {col_name} TEXT"
))
```
Hodnota `col_name` pochází z hardcoded tuple `("owner_import_mapping", "contact_import_mapping")`, takže riziko SQL injection je nulové. Ale vzor je nečistý.

**Řešení:** Ponechat s komentářem `# safe: col_name from hardcoded tuple` nebo nahradit za dva explicitní příkazy bez f-stringu.

**Náročnost + čas:** nízká, ~10 min
**Regrese riziko:** nízké
**Jak otestovat:** Smazat DB, spustit server, ověřit že tabulky se vytvoří.

---

#### N9 -- `datetime.utcnow` jako default ve sloupci (LOW)

**Co a kde:** `app/models/owner.py:61-62` a dalších 15 modelových souborů:
```python
created_at = Column(DateTime, default=datetime.utcnow)
```
Toto je **správný vzor** v SQLAlchemy -- `datetime.utcnow` (bez závorek) se předává jako callable a volá se při každém INSERT. **Není to chyba**, jen zmínka pro úplnost.

**Řešení:** Žádná akce nutná. Tento pattern je standardní SQLAlchemy konvence.

---

### 2. Bezpečnost

#### N10 -- Žádná autentizace (CRITICAL)

**Co a kde:** Celý projekt nemá žádnou autentizaci ani autorizaci. Všechny endpointy jsou volně přístupné komukoliv na síti. Plán implementace existuje v CLAUDE.md (sekce "Uživatelské role"), ale nebyl dosud realizován.

**Řešení:** Implementovat dle plánu v CLAUDE.md:
1. Model `User` + migrace
2. Auth service (session-based, bcrypt)
3. Login/logout stránky
4. `get_current_user` dependency
5. `require_role` helper
6. Přidat do všech routerů

**Varianty:**
1. Plná implementace dle plánu v CLAUDE.md (4 role) -- ~8 hod
2. Minimální implementace (jen admin login) -- ~3 hod
3. Odložit na později, pokud aplikace běží jen lokálně -- 0 hod

**Náročnost + čas:** vysoká, ~8 hod (plná implementace)
**Závislosti:** Žádné
**Regrese riziko:** střední -- mechanická úprava, ale dotýká se všech routerů
**Jak otestovat:** Po implementaci zkusit přístup bez přihlášení -- měl by redirect na login.

---

#### N11 -- Žádná CSRF ochrana (CRITICAL)

**Co a kde:** 97 formulářů s `method="POST"` nebo `hx-post` v šablonách, žádný nemá CSRF token. FastAPI nemá vestavěnou CSRF ochranu.

**Řešení:**
1. Přidat CSRF middleware (např. `starlette-csrf` nebo vlastní řešení)
2. Každý formulář dostane hidden `<input>` s CSRF tokenem
3. Middleware ověří token při POST

**Varianty:**
1. Knihovna `starlette-csrf` -- rychlá integrace (~2 hod)
2. Vlastní implementace (cookie double-submit) -- ~4 hod
3. Odložit -- pokud aplikace běží čistě lokálně a nemá autentizaci, CSRF je méně relevantní

**Náročnost + čas:** střední, ~4 hod
**Závislosti:** Závisí na #10 (autentizace) -- CSRF má smysl hlavně s auth
**Regrese riziko:** nízké
**Jak otestovat:** Zkusit odeslat POST formulář s neplatným/chybějícím tokenem -- měl by selhat.

---

#### N12 -- SMTP heslo v paměti (HIGH)

**Co a kde:** `app/config.py:17` -- `smtp_password` se načítá z `.env` do `settings` singletonu a zůstává v paměti po celou dobu běhu serveru. Navíc `app/routers/settings_page.py:162-163` zapisuje heslo zpět do `.env` pomocí `set_key()`.

**Řešení:** Toto je akceptovatelné pro lokální aplikaci. Pro produkční nasazení by heslo mělo být v environment proměnné (ne v .env souboru) nebo v secret manageru.

**Náročnost + čas:** nízká, ~30 min
**Regrese riziko:** nízké
**Jak otestovat:** Nastavit SMTP heslo přes formulář, ověřit že funguje odeslání emailu.

---

#### N13 -- `|safe` filtr v šablonách (MEDIUM)

**Co a kde:** 6 výskytů `|safe` filtru v Jinja2 šablonách:
- `app/templates/voting/detail.html:62`
- `app/templates/voting/ballots.html:62,73,82,90`
- `app/templates/voting/process.html:38`

Všechny se používají pro vykreslení SVG ikon (`_svg_up`, `_svg_down`). Data pochází z routeru (server-side proměnné), ne z uživatelského vstupu -- riziko XSS je tedy nízké.

**Řešení:** Nahradit `|safe` za Jinja2 `Markup()` v routeru nebo za `{% include %}` SVG partial.

**Náročnost + čas:** nízká, ~30 min
**Regrese riziko:** nízké
**Jak otestovat:** Otevřít hlasování > detail > ověřit že šipky řazení fungují.

---

#### N14 -- Monkey-patching Starlette max_files (MEDIUM)

**Co a kde:** `app/main.py:556-561`:
```python
_StarletteRequest.form.__kwdefaults__["max_files"] = 5000
```
Tento monkey-patch může selhat při aktualizaci Starlette, protože závisí na interní implementaci.

**Řešení:**
1. Počkat na oficiální konfiguraci v budoucí verzi Starlette
2. Nebo vytvořit vlastní middleware pro velké uploady
3. Nebo přejít na chunked upload (frontend posílá soubory po dávkách)

**Náročnost + čas:** nízká, ~30 min (přidat robustnější fallback)
**Regrese riziko:** nízké
**Jak otestovat:** Nahrát složku s 1000+ PDF soubory v modulu Daně.

---

### 3. Dokumentace

#### N15 -- Chybějící docstringy na endpoint funkcích (MEDIUM)

**Co a kde:** Většina routerových endpoint funkcí nemá docstring. Z 86 GET/POST endpointů má docstring jen ~10. Například:
- `app/routers/dashboard.py:82 home()` -- 172 řádků, žádný docstring
- `app/routers/sync.py:283 sync_detail()` -- 152 řádků, žádný docstring
- `app/routers/voting/session.py:461 generate_ballots()` -- 188 řádků, žádný docstring

**Řešení:** Přidat jednořádkový docstring ke každému endpointu popisující co dělá a jaká stránka se zobrazuje.

**Náročnost + čas:** nízká, ~2 hod
**Regrese riziko:** nízké
**Jak otestovat:** Není potřeba -- čistě dokumentační změna.

---

#### N16 -- Neúplná API dokumentace v README (LOW)

**Co a kde:** `README.md` neobsahuje kompletní seznam všech API endpointů. Nové moduly (kontrola podílů, hromadné rozesílání) mají jen stručný popis bez endpointů.

**Řešení:** Doplnit endpointy pro všechny moduly v README.md.

**Náročnost + čas:** nízká, ~1 hod
**Regrese riziko:** nízké
**Jak otestovat:** Porovnat README s registrovanými routami (`app.routes`).

---

### 4. UI / Šablony

#### N17 -- Chybějící responsive ochrana tabulek (MEDIUM)

**Co a kde:** Datové tabulky (vlastníci, jednotky, lístky, synchronizace) nemají `overflow-x-auto` wrapper pro horizontální scroll na mobilních zařízeních. Sidebar je responzivní (hamburger menu), ale obsah tabulek se na malých obrazovkách ořízne.

Nalezeno jen 33 výskytů responzivních tříd (`hidden sm:`, `md:`, `overflow-x-auto`) v 21 šablonách -- většina je v `base.html` (sidebar), ne v tabulkách.

**Řešení:** Obalit každý `<table>` element do `<div class="overflow-x-auto">`.

**Varianty:**
1. Přidat `overflow-x-auto` wrapper ke všem tabulkám -- ~2 hod
2. Alternativně: stack layout na mobilech (cards místo tabulek) -- ~8+ hod

**Náročnost + čas:** nízká (varianta 1), ~2 hod
**Regrese riziko:** nízké
**Jak otestovat:** Zmenšit okno prohlížeče na 375px, projít stránky s tabulkami.

---

#### N18 -- Přístupnost: `<input>` bez propojených `<label>` (MEDIUM)

**Co a kde:** Mnohé formulářové `<input>` prvky používají `placeholder` místo `<label for="...">`. WCAG AA vyžaduje explicitní propojení labelu s inputem. Výskytů je řádově 50+ ve formulářových šablonách.

**Řešení:** Přidat `id` na inputy a `for` na labely, případně přidat `aria-label` kde vizuální label není žádoucí.

**Náročnost + čas:** střední, ~3 hod
**Regrese riziko:** nízké
**Jak otestovat:** Lighthouse audit v Chrome DevTools > Accessibility.

---

#### N19 -- CDN závislosti -- offline nefunkční (LOW)

**Co a kde:** `app/templates/base.html:13-14`:
```html
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://unpkg.com/htmx.org@2.0.4"></script>
```
Aplikace je určena i pro nasazení na USB/offline počítačích (`spustit.command`), ale CDN zdroje vyžadují internet.

**Řešení:**
1. Stáhnout Tailwind standalone CLI a HTMX do `/static/js/`
2. Nebo přidat fallback: pokud CDN nedostupný, použít lokální kopii

**Varianty:**
1. Tailwind CSS build pipeline (standalone CLI) + lokální HTMX -- ~2 hod, ale mění dev workflow
2. Ponechat CDN -- funguje na většině počítačů (WiFi)

**Náročnost + čas:** nízká-střední, ~1-2 hod
**Regrese riziko:** nízké
**Jak otestovat:** Odpojit internet, načíst stránku -- měla by fungovat.

---

### 5. Výkon

#### N20 -- Žádná paginace na hlavních seznamech (HIGH)

**Co a kde:** Seznamy vlastníků (`app/routers/owners/crud.py:148`), jednotek (`app/routers/units.py`), hlasování (`app/routers/voting/session.py:37`) a synchronizací (`app/routers/sync.py:36`) načítají všechny záznamy bez paginace (`.all()`). Jedinou výjimkou je detail rozesílání (`app/routers/tax/session.py:457-463` -- paginace po 100). Seznam emailových logů má `LIMIT 100`.

Při stovkách vlastníků a tisících lístků může být výkon problematický.

**Řešení:** Přidat server-side paginaci s `LIMIT/OFFSET` a navigačním UI (předchozí/další stránka).

**Varianty:**
1. Server-side paginace (standardní) -- ~3 hod
2. Virtuální scrolling (JavaScript) -- složitější, ~6 hod
3. Ponechat bez paginace -- SVJ má typicky desítky až stovky vlastníků (možná stačí)

**Náročnost + čas:** střední, ~3 hod
**Regrese riziko:** střední -- mění URL schéma (přibude `?strana=2`)
**Jak otestovat:** Načíst seznam vlastníků s 500+ záznamy, měřit response time.

---

#### N21 -- Synchronní SMTP odesílání (MEDIUM)

**Co a kde:** `app/services/email_service.py` -- funkce `send_email()` je synchronní a blokuje request thread při odesílání. Pro jednotlivé emaily je to OK, ale hromadné rozesílání (modul Daně) může blokovat server.

Poznámka: Modul Daně (`app/routers/tax/sending.py`) řeší toto pomocí SSE (Server-Sent Events) s batch odesíláním, takže hlavní problém je zmírněn.

**Řešení:** Pro budoucí rozšíření zvážit background task (FastAPI `BackgroundTasks` nebo Celery).

**Náročnost + čas:** střední, ~3 hod
**Regrese riziko:** střední
**Jak otestovat:** Odeslat hromadný email 50+ příjemcům, ověřit že UI neblokuje.

---

#### N22 -- Dashboard eager loading hlasování (LOW)

**Co a kde:** `app/routers/dashboard.py:107`:
```python
.options(joinedload(Voting.ballots).joinedload(Ballot.votes))
```
Dashboard načítá VŠECHNA hlasování se VŠEMI lístky a hlasy pro výpočet statistik. Pro SVJ s mnoha hlasováními to může být pomalé.

**Řešení:** Místo eager loading použít aggregační dotaz:
```python
db.query(Voting.id, func.count(Ballot.id)).join(Ballot).group_by(Voting.id)
```

**Náročnost + čas:** nízká, ~30 min
**Regrese riziko:** nízké
**Jak otestovat:** Načíst dashboard s 20+ hlasováními, změřit response time.

---

### 6. Error Handling

#### N23 -- Tichá selhání s `except Exception: pass` (MEDIUM)

**Co a kde:** 10+ míst v kódu zachytává všechny výjimky a tiše je ignoruje:
- `app/services/email_service.py:189` -- SMTP quit
- `app/routers/voting/session.py:290` -- metadata extraction
- `app/routers/tax/sending.py:669,725` -- SMTP cleanup

Většina z nich je v cleanup kódu (file delete, SMTP disconnect) kde tiché selhání je legitimní. Ale některé by měly alespoň logovat.

**Řešení:** Nahradit `pass` za `logger.debug("...", exc_info=True)` u všech `except Exception: pass` bloků, aby se chyby zaznamenaly alespoň na debug úrovni.

**Náročnost + čas:** nízká, ~1 hod
**Regrese riziko:** nízké
**Jak otestovat:** Spustit server s `DEBUG=true`, ověřit logy.

---

### 7. Git Hygiene

#### N24 -- Soubory z testování v `.playwright-mcp/` (HIGH)

**Co a kde:** Adresář `.playwright-mcp/` obsahuje 26 souborů (22 logů + 4 PNG screenshoty) z Playwright testování, které nebyly smazány po testování.

```
.playwright-mcp/console-2026-03-18T*.log (22 souborů)
.playwright-mcp/verify_d5.png (127 KB)
.playwright-mcp/verify_d6.png (101 KB)
.playwright-mcp/verify_dr10.png (107 KB)
.playwright-mcp/verify_dr6.png (47 KB)
```

**Řešení:** Smazat: `rm -rf .playwright-mcp/*.log .playwright-mcp/*.png`

**Náročnost + čas:** nízká, ~2 min
**Regrese riziko:** nízké
**Jak otestovat:** `ls .playwright-mcp/` -- měl by být prázdný nebo neexistovat.

---

#### N25 -- Binární soubory v git historii (MEDIUM)

**Co a kde:** Git historie obsahuje PNG screenshoty z commitů:
- `0288989` -- `after_back.png`, `before_scroll.png`, `detail_page.png`, `send_page_top.png`
- Tyto soubory byly odstraněny z HEAD ale zůstávají v git objects

**Řešení:**
1. Nechat -- screenshoty v historii nezpůsobují problém (git gc je komprimuje)
2. Nebo `git filter-branch` / BFG cleaner -- riskantní, přepisuje historii

**Náročnost + čas:** nízká, ~15 min (pokud se rozhodne přepsat historii)
**Regrese riziko:** vysoké při přepsání historie (force push)
**Jak otestovat:** `git rev-list --objects --all -- '*.png' | wc -l`

---

### 8. Testy

#### N26 -- Minimální testové pokrytí (HIGH)

**Co a kde:** Projekt má pouze 23 testů ve 5 souborech (518 řádků testů) pro 10 500 řádků routerů a 5 183 řádků služeb. Pokrytí odhadem pod 5%.

**Pokryté oblasti:**
- Smoke testy (app starts, dashboard loads) -- 3 testy
- Email service (name_normalized) -- 5 testů
- Import mapping (auto-detect, validate) -- 8 testů
- Contact import (preview) -- 3 testy
- Voting aggregation -- 3 testy (+ 1 test fixture)

**Nepokryté kritické oblasti:**
- Import vlastníků z Excelu
- Synchronizace (CSV porovnání, výměna vlastníků)
- Hlasování (generování lístků, zpracování hlasů, kvórum)
- Hromadné rozesílání (matching, sending)
- Záloha/obnova
- Kontrola podílů
- Administrace (CRUD operace)
- Export dat

**Řešení:** Prioritně přidat integration testy pro:
1. Import vlastníků -- vytvoření Owner+Unit+OwnerUnit z Excel dat
2. Hlasování -- celý workflow od vytvoření po uzavření
3. Záloha/obnova -- backup + restore + ověření dat

**Náročnost + čas:** vysoká, ~8+ hod
**Regrese riziko:** nízké (přidávání testů nerozbije existující kód)
**Jak otestovat:** `pytest tests/ -v`

---

#### N27 -- Test engine isolation (LOW)

**Co a kde:** `tests/conftest.py:23` -- `test_engine` má `scope="session"` (sdílený přes všechny testy), ale `db_session` používá transakční rollback. To je správný vzor pro DML operace, ale DDL operace (CREATE TABLE, ALTER TABLE) se v SQLite nerollbackují, protože SQLite auto-commituje DDL.

**Řešení:** Pro testy s DDL operacemi (migrace, schema změny) vytvořit separátní fixture s čistou DB.

**Náročnost + čas:** nízká, ~30 min
**Regrese riziko:** nízké
**Jak otestovat:** `pytest tests/ -v --tb=long`

---

#### N28 -- Zastaralý import warning v testech (LOW)

**Co a kde:** Pytest výstup ukazuje:
```
PendingDeprecationWarning: Please use `import python_multipart` instead.
```
Knihovna `python-multipart` je v dependencies, Starlette ji importuje přes starý název.

**Řešení:** Aktualizovat `starlette` / `fastapi` na nejnovější verzi kde je warning opraven.

**Náročnost + čas:** nízká, ~10 min
**Regrese riziko:** nízké-střední (záleží na kompatibilitě nových verzí)
**Jak otestovat:** `pytest tests/ -W error::PendingDeprecationWarning`

---

## Doporučený postup oprav

### Fáze 1 -- Okamžité (CRITICAL + snadné HIGH)
1. **N24** -- Smazat soubory z `.playwright-mcp/` (~2 min) 🔧
2. **N21** -- f-string v SQL (komentář) (~10 min) 🔧

### Fáze 2 -- Krátkodobé (HIGH)
3. **N4** -- Refaktoring duplikovaných migrací (~1 hod) 🔧
4. **N5** -- Hardcoded cesty -> settings (~15 min) 🔧
5. **N6** -- Refaktoring nejdelších funkcí -- začít s top 5 (~2 hod)

### Fáze 3 -- Střednědobé (MEDIUM)
6. **N9** -- Sdílená `templates` instance (~1 hod)
7. **N14** -- Logging místo `pass` v except blocích (~1 hod)
8. **N17** -- `overflow-x-auto` na tabulkách (~2 hod)
9. **N10** -- `datetime.utcnow()` migrace (~1 hod)
10. **N15** -- Docstringy na endpointech (~2 hod)

### Fáze 4 -- Strategické (vyžaduje rozhodnutí)
11. **N1** -- Autentizace a autorizace (~8 hod) ❓
12. **N2** -- CSRF ochrana (~4 hod) ❓
13. **N20** -- Paginace (~3 hod) ❓
14. **N26** -- Testové pokrytí (~8+ hod, průběžně) ❓
15. **N7/N8** -- Rozdělení velkých routerů (~4 hod) ❓

### Poznámky
- Nálezy N1 (autentizace) a N2 (CSRF) jsou CRITICAL z bezpečnostního hlediska, ale pokud aplikace běží pouze lokálně (localhost), jejich priorita je nižší
- Nález N20 (paginace) závisí na velikosti dat -- pro typické SVJ s desítkami vlastníků není kritický
- Testové pokrytí (N26) by mělo růst průběžně s každou novou funkcionalitou
