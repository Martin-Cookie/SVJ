# SVJ Audit Report — 2026-03-27

> Scope: celý projekt (zaměření na 5 nových commitů od 2026-03-24)
>
> Nové commity:
> - fix: oprava nefunkčního tlačítka "Zrušit rozesílku" během odesílání
> - docs: nový USB Deploy Agent s lessons learned z přenosu na jiný Mac
> - fix: správné RFC 2047 enkódování emailových hlaviček (To/From/Subject)
> - fix: pinované závislosti (requirements.txt) + podpora SMTP SSL (port 465)
> - feat: skript pro přenos aplikace na jiný Mac + vylepšené kontroly při spuštění

## Stav nálezů k 2026-04-07

Z 11 nálezů tohoto auditu bylo **11 opraveno** (všechny), zbývá **0 otevřených**:

| # | Nález | Stav |
|---|-------|------|
| N1 | SMTP SSL duplikace v settings_page | ✅ OPRAVENO — používá `_create_smtp()` |
| N2 | Logger import ordering | ✅ OPRAVENO |
| N3 | Return type `_create_smtp()` | ✅ OPRAVENO — `SMTP \| SMTP_SSL` |
| N4 | Temp form hidden fields | ✅ OPRAVENO — `cloneNode(true)` |
| N5 | `datetime.utcnow` v 7 modelech | ✅ OPRAVENO — všude `utcnow()` |
| N6 | `datetime.utcnow()` v dashboard | ✅ OPRAVENO |
| N7 | Playwright logy | ✅ OPRAVENO 2026-04-07 |
| N8 | test_prostory.xlsx | ✅ OPRAVENO — smazáno |
| N9 | Hardcoded Dropbox cesta | ✅ OPRAVENO 2026-04-07 — env `SVJ_DATA_SRC` |
| N10 | sqlite3 CLI check | ✅ OPRAVENO — `command -v` guard |
| N11 | WHEEL_COUNT undefined | ✅ OPRAVENO — `${WHEEL_COUNT:-0}` |

## Stav předchozího auditu (2026-03-24)

Z 13 nálezů předchozího auditu bylo **9 opraveno**:
- **N1** (CRITICAL: replace import maže všechny nájemce) -- OPRAVENO
- **N2** (HIGH: flash_type nepředáno) -- OPRAVENO
- **N3** (HIGH: SJM matching substring) -- OPRAVENO (word-level match)
- **N4** (HIGH: GROUP BY bug) -- OPRAVENO (přepsáno na match_status + direction)
- **N5** (MEDIUM: flash upraveno chybí) -- OPRAVENO
- **N6** (MEDIUM: prázdné VS při editaci) -- OPRAVENO (validace + redirect s chybou)
- **N8** (MEDIUM: inline import datetime) -- stav nezměněn
- **N9** (MEDIUM: tenant flash_type) -- stav nezměněn
- **N11** (LOW: inline import v replace) -- stav nezměněn (ale N1 oprava přepracovala celý blok)
- **N12** (LOW: SJM substring detekce) -- OPRAVENO (exact match `== "SJM"`)

Zbývají neopravené: **N7** (datetime.utcnow v modelech), **N8**, **N9**, **N10**, **N13**.

## Souhrn nových nálezů

- **CRITICAL**: 0
- **HIGH**: 1
- **MEDIUM**: 5
- **LOW**: 5

## Souhrnná tabulka

| #  | Oblast      | Soubor                              | Severity | Problém                                                                     | Čas      | Rozhodnutí |
|----|------------|--------------------------------------|----------|-----------------------------------------------------------------------------|----------|------------|
| 1  | Kód        | settings_page.py:196-201             | HIGH     | SMTP SSL logika duplikována (nepoužívá `_create_smtp` z email_service)      | ~5 min   | :wrench:   |
| 2  | Kód        | email_service.py:12-17               | MEDIUM   | `logger = ...` uprostřed importů (mezi stdlib a third-party)                | ~2 min   | :wrench:   |
| 3  | Kód        | email_service.py:27                  | MEDIUM   | Return type annotation `-> smtplib.SMTP` neodpovídá `SMTP_SSL` return      | ~2 min   | :wrench:   |
| 4  | Kód        | app.js:228-234                       | MEDIUM   | Temp form při HTMX polling nepřenáší hidden fields (data z původního form)  | ~15 min  | :wrench:   |
| 5  | Kód        | 7 modelů (voting, common, owner...) | MEDIUM   | `datetime.utcnow` (deprecated Python 3.12+) -- přeneseno z minulého auditu | ~15 min  | :wrench:   |
| 6  | Kód        | dashboard.py:302                     | MEDIUM   | `datetime.utcnow()` v routeru (ne model default)                           | ~1 min   | :wrench:   |
| 7  | Git        | .playwright-mcp/                     | LOW      | Zbytkový log soubor z Playwright testování                                  | ~1 min   | :wrench:   |
| 8  | Git        | test_prostory.xlsx (untracked)       | LOW      | Testovací soubor v kořeni projektu                                          | ~1 min   | :wrench:   |
| 9  | Kód        | pripravit_prenos.sh:22               | LOW      | Hardcoded cesta k Dropboxu `/Users/martinkoci/...`                         | ~5 min   | :question: |
| 10 | Bezpečnost | pripravit_prenos.sh:84               | LOW      | `sqlite3 "$DB_FILE" "PRAGMA ..."` bez kontroly existence sqlite3            | ~2 min   | :wrench:   |
| 11 | Kód        | spustit.command:137                  | LOW      | `WHEEL_COUNT` proměnná použita v podmínce, ale může být nedefinovaná        | ~2 min   | :wrench:   |

Legenda: :wrench: = jen opravit, :question: = potřeba rozhodnutí uživatele (více variant)

---

## Detailní nálezy

### 1. Kódová kvalita

#### N1 -- HIGH: SMTP SSL logika duplikována v settings_page.py

- **Co a kde**: `app/routers/settings_page.py:196-201` -- endpoint `test_smtp_connection()` obsahuje inline SMTP SSL/STARTTLS logiku (if port == 465: SMTP_SSL else: SMTP + starttls), místo použití nové funkce `_create_smtp()` z `app/services/email_service.py`. Přesně tato logika byla vyextrahována do `_create_smtp()` v commitu `0703c19`, ale settings_page nebyl refaktorován, jen ručně upravena duplikátem.
- **Řešení**: Nahradit řádky 196-201 voláním:
  ```python
  from app.services.email_service import _create_smtp
  server = _create_smtp(settings.smtp_host, settings.smtp_port, settings.smtp_use_tls, timeout=10)
  ```
- **Náročnost + čas**: nízká, ~5 min
- **Závislosti**: žádné
- **Regrese riziko**: nízké -- `_create_smtp` dělá přesně totéž
- **Jak otestovat**: (1) Nastavit SMTP na port 465. (2) V Nastavení kliknout "Testovat připojení". (3) Ověřit že test proběhne.

#### N2 -- MEDIUM: Logger uprostřed importů v email_service.py

- **Co a kde**: `app/services/email_service.py:12` -- `logger = logging.getLogger(__name__)` je umístěn mezi stdlib importy (`smtplib`, `socket`) a dalšími stdlib importy (`email.header`, `email.mime.*`). PEP 8 doporučuje: importy -> pak prázdný řádek -> pak modul-level kód.
- **Řešení**: Přesunout `logger = ...` za všechny importy (za řádek 24).
- **Náročnost + čas**: nízká, ~2 min
- **Závislosti**: žádné
- **Regrese riziko**: nulové
- **Jak otestovat**: `python -c "from app.services.email_service import send_email"` -- import funguje.

#### N3 -- MEDIUM: Return type annotation neodpovídá skutečnosti

- **Co a kde**: `app/services/email_service.py:27` -- `def _create_smtp(...) -> smtplib.SMTP:` deklaruje návratový typ `SMTP`, ale pro port 465 vrací `SMTP_SSL`. `SMTP_SSL` dědí z `SMTP`, takže za runtime to funguje, ale type checker by mohl hlásit incompatible return.
- **Řešení**: Změnit annotation na `-> smtplib.SMTP | smtplib.SMTP_SSL` nebo `-> smtplib.SMTP` (akceptovatelné díky dědičnosti -- spíše kosmetické).
- **Varianty**: (A) `Union[smtplib.SMTP, smtplib.SMTP_SSL]` -- přesné. (B) Ponechat `smtplib.SMTP` -- SMTP_SSL dědí, takže to je technicky korektní.
- **Náročnost + čas**: nízká, ~2 min
- **Závislosti**: žádné
- **Regrese riziko**: nulové
- **Jak otestovat**: N/A -- kosmetická úprava.

#### N4 -- MEDIUM: Temp form nepřenáší hidden fields původního formuláře

- **Co a kde**: `app/static/js/app.js:228-234` -- nový fallback kód pro případ, kdy HTMX polling nahradí DOM a původní `<form>` zmizí. Vytvoří se nový `<form>` jen s `method` a `action`, ale **nepřenesou se hidden inputs** z původního formuláře (např. `session_id`, `batch_size` apod.). Aktuálně se toto použije jen pro tlačítko "Zrušit rozesílku" během odesílání, kde action URL typicky obsahuje vše potřebné v path (ne form data), takže v praxi funguje. Ale obecný vzor je nespolehlivý.
- **Řešení**: Před `e.preventDefault()` (řádek 219) uložit kopii hidden inputů z formuláře a v temp formu je reprodukovat:
  ```javascript
  var hiddens = Array.from(form.querySelectorAll('input[type="hidden"]'));
  // ... v tmp formu:
  hiddens.forEach(function(h) { var c = h.cloneNode(true); tmp.appendChild(c); });
  ```
- **Náročnost + čas**: nízká, ~15 min (otestovat s reálným polling scénářem)
- **Závislosti**: žádné
- **Regrese riziko**: nízké -- fallback path se aktivuje jen při HTMX polling
- **Jak otestovat**: (1) Spustit rozesílku. (2) Během odesílání kliknout "Zrušit rozesílku". (3) Ověřit že se rozesílka zastaví.

#### N5 -- MEDIUM: `datetime.utcnow` deprecated v modelech (přeneseno z N7 minulého auditu)

- **Co a kde**: 22 instancí `datetime.utcnow` v 7 modelech: `voting.py` (3x), `common.py` (3x), `owner.py` (4x), `administration.py` (5x), `tax.py` (2x), `sync.py` (1x), `share_check.py` (2x). Modely `space.py` a `payment.py` už byly opraveny na `utcnow` z `app.utils`.
- **Řešení**: Stejný postup jako v opravených modelech:
  ```python
  from app.utils import utcnow
  created_at = Column(DateTime, default=utcnow)
  updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
  ```
- **Náročnost + čas**: nízká, ~15 min (mechanická náhrada ve 7 souborech)
- **Závislosti**: žádné
- **Regrese riziko**: nízké -- `utcnow()` vrací stejný typ
- **Jak otestovat**: Vytvořit nového vlastníka, ověřit `created_at` timestamp.

#### N6 -- MEDIUM: `datetime.utcnow()` volání v routeru

- **Co a kde**: `app/routers/dashboard.py:302` -- `expiry_cutoff = datetime.utcnow().date() + timedelta(days=90)`. Toto je runtime volání (ne column default), takže deprecated warning se zobrazí přímo.
- **Řešení**: `from app.utils import utcnow; expiry_cutoff = utcnow().date() + timedelta(days=90)`
- **Náročnost + čas**: nízká, ~1 min
- **Závislosti**: N5 (stejný pattern, ale jiný kontext)
- **Regrese riziko**: nulové
- **Jak otestovat**: Otevřít dashboard, ověřit sekci expirujících smluv.

---

### 2. Bezpečnost

#### N9 -- LOW: Hardcoded Dropbox cesta v pripravit_prenos.sh

- **Co a kde**: `pripravit_prenos.sh:22` -- `DATA_SRC="/Users/martinkoci/Library/CloudStorage/Dropbox/Dokumenty/SVJ/DATA"`. Obsahuje konkrétní username a cestu specifickou pro jeden Mac. Skript je v git repozitáři.
- **Řešení**: Varianty: (A) Přesunout cestu do proměnné prostředí nebo argumentu skriptu. (B) Přidat do `.gitignore` a ponechat jako lokální skript. (C) Použít relativní cestu nebo přidat `--data-src` parametr. (D) Ponechat -- skript je explicitně pro přenos z tohoto konkrétního Macu.
- **Náročnost + čas**: nízká, ~5 min
- **Závislosti**: žádné
- **Regrese riziko**: nízké
- **Jak otestovat**: Spustit `./pripravit_prenos.sh /tmp/test` -- ověřit chování.

#### N10 -- LOW: Chybějící kontrola sqlite3 v pripravit_prenos.sh

- **Co a kde**: `pripravit_prenos.sh:84` -- `sqlite3 "$DB_FILE" "PRAGMA wal_checkpoint(TRUNCATE);"` předpokládá, že `sqlite3` CLI je k dispozici. Na čistém macOS může chybět (závisí na Command Line Tools).
- **Řešení**: Přidat kontrolu: `if command -v sqlite3 &>/dev/null; then ... else echo "sqlite3 nenalezen, přeskakuji WAL checkpoint"; fi`
- **Náročnost + čas**: nízká, ~2 min
- **Závislosti**: žádné
- **Regrese riziko**: nulové
- **Jak otestovat**: Přejmenovat sqlite3, spustit skript, ověřit graceful skip.

---

### 3. Git Hygiene

#### N7 -- LOW: Zbytkový Playwright log

- **Co a kde**: `.playwright-mcp/console-2026-03-27T22-01-56-241Z.log` -- zbytkový log z Playwright testování. Sice je v `.gitignore`, ale zabírá místo a měl by být smazán po testování.
- **Řešení**: `rm -rf .playwright-mcp/*.log`
- **Náročnost + čas**: nízká, ~1 min
- **Závislosti**: žádné
- **Regrese riziko**: nulové
- **Jak otestovat**: N/A

#### N8 -- LOW: Testovací soubor test_prostory.xlsx

- **Co a kde**: `test_prostory.xlsx` v kořeni projektu (untracked). Testovací Excel soubor který tam zůstal po vývoji.
- **Řešení**: Smazat: `rm test_prostory.xlsx`. Pokud je potřebný pro testy, přesunout do `tests/fixtures/`.
- **Náročnost + čas**: nízká, ~1 min
- **Závislosti**: žádné
- **Regrese riziko**: nulové
- **Jak otestovat**: N/A

---

### 4. Shell skripty

#### N11 -- LOW: Nedefinovaná proměnná WHEEL_COUNT

- **Co a kde**: `spustit.command:137` -- podmínka `[ "$WHEEL_COUNT" -eq 0 ]` závisí na `WHEEL_COUNT` definované na řádku 105, ale ta se definuje jen pokud existuje `wheels/` adresář (řádky 104-111). Pokud adresář neexistuje, `WHEEL_COUNT` je prázdný string a `[ "" -eq 0 ]` v bash vrátí chybu (integer expected). Skript funguje díky `set +e` (default), ale zobrazí se ošklivá chybová hláška.
- **Řešení**: Inicializovat `WHEEL_COUNT=0` před podmínkou na řádku 104, nebo přidat fallback: `[ "${WHEEL_COUNT:-0}" -eq 0 ]`.
- **Náročnost + čas**: nízká, ~2 min
- **Závislosti**: žádné
- **Regrese riziko**: nulové
- **Jak otestovat**: Spustit `spustit.command` bez `wheels/` adresáře, ověřit žádnou chybovou hlášku v konzoli.

---

### 5. Pozitivní nálezy (nové commity)

- **RFC 2047 enkódování**: `email_service.py` nyní správně enkóduje české znaky v email hlavičkách pomocí `Header()` a `formataddr()`. To eliminuje problémy s diakritikou v To/From/Subject u striktních SMTP serverů.
- **SMTP SSL podpora**: Port 465 (implicitní SSL) je nyní podporován vedle port 587 (STARTTLS). Logika je vyextrahována do `_create_smtp()` pro opakované použití.
- **Pinované závislosti**: `requirements.txt` nyní obsahuje přesné verze všech přímých závislostí (15 balíčků). To zajišťuje reprodukovatelné buildy.
- **Spouštěcí skript**: `spustit.command` má robustní kontroly (Python verze, místo na disku, DB existence, wheels, LibreOffice, internet). Automaticky opraví poškozenou .venv.
- **Form confirm fallback**: `app.js` nyní gracefully řeší situaci, kdy HTMX polling nahradí formulář v DOM během zobrazení confirm dialogu.
- **Testy**: Všech 248 testů prochází bez chyb (4 deprecation warningy SQLAlchemy Query.get()).
- **Bezpečnost**: Žádné SQL injection, žádné `|safe` filtry na uživatelský vstup, `.env` v `.gitignore`, path traversal validace na všech file endpoints.

---

### 6. Systémové poznámky (nezměněné od minulého auditu)

Následující systémové nálezy z dřívějších auditů nejsou opakovány, ale stále platí:
- **Žádná CSRF ochrana** -- plánováno s autentizací (viz CLAUDE.md § Uživatelské role)
- **Žádná autentizace** -- plánováno jako poslední fáze
- **Test coverage** -- testy pokrývají: voting, payment matching, import mapping, backup, contact import, smoke, email service. Chybí: spaces, tenants, sync, tax, dashboard, settings, administration

---

## Doporučený postup oprav

### 1. Vysoká priorita (HIGH)
1. **N1**: SMTP duplikace v settings_page (~5 min)

### 2. Střední priorita (MEDIUM) -- dohromady ~35 min
2. **N5**: `datetime.utcnow` deprecated v 7 modelech (~15 min)
3. **N6**: `datetime.utcnow()` v dashboard.py (~1 min)
4. **N4**: Temp form hidden fields (~15 min)
5. **N2**: Logger placement (~2 min)
6. **N3**: Return type annotation (~2 min)

### 3. Nízká priorita (LOW) -- dohromady ~12 min
7. **N7**: Smazat Playwright log (~1 min)
8. **N8**: Smazat test_prostory.xlsx (~1 min)
9. **N11**: WHEEL_COUNT inicializace (~2 min)
10. **N10**: sqlite3 kontrola (~2 min)
11. **N9**: Hardcoded Dropbox cesta (~5 min, rozhodnutí)

### 4. Zbylé z minulého auditu
12. Inline import datetime v spaces/crud.py (N8 minulý) -- ~2 min
13. Tenant flash_type v kontextu (N9 minulý) -- ~2 min
14. Duplikovaná adresní logika v tenants/crud.py (N13 minulý) -- ~10 min

---

## Celkový odhad času oprav

| Priorita   | Počet | Čas       |
|------------|-------|-----------|
| HIGH       | 1     | ~5 min    |
| MEDIUM     | 5     | ~35 min   |
| LOW        | 5     | ~12 min   |
| **Celkem** | **11** | **~52 min** |

Pozn.: Všechny opravy jsou mechanické bez rizika regrese. HIGH + MEDIUM = ~40 min.
