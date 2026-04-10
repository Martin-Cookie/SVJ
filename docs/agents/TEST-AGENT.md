# Test Agent – Automatické testování celé aplikace

> Spouštěj po bloku změn nebo před releasem pro ověření, že aplikace funguje správně.
> Agent projde 8 fází testování a vytvoří soubor `docs/reports/TEST-REPORT.md` se souhrnem výsledků.

---

## Cíl

Automaticky otestovat celou SVJ aplikaci — pytest, Playwright smoke + funkční testy, route coverage, exporty, back URL integritu, N+1 detekci a JS errory. Na konci vytvořit `docs/reports/TEST-REPORT.md` s nálezem a prioritami.

---

## Instrukce

**NEPRAV ŽÁDNÝ KÓD. POUZE TESTUJ A REPORTUJ.**

Projdi postupně všech 8 fází níže. U každého selhání uveď:
- **Co selhalo** (test, URL, akce)
- **Severity**: CRITICAL / WARNING / INFO
- **Detail** (chybová hláška, screenshot, HTTP status)
- **Doporučení** jak to opravit

Na konci vytvoř souhrnnou tabulku a seřaď podle severity.

**Před spuštěním:** Ověř, že server běží na `http://localhost:8021`:
```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:8021/
```
Pokud neběží, spusť ho:
```bash
cd /Users/martinkoci/Projects/SVJ && source .venv/bin/activate && python -m uvicorn app.main:app --port 8021 &
```

---

## Fáze 1: PYTEST (~1 min)

Spusť existující testy:

```bash
cd /Users/martinkoci/Projects/SVJ && source .venv/bin/activate && python3 -m pytest tests/ -v --tb=short 2>&1
```

Zaznamenej:
- Celkový počet testů
- PASSED / FAILED / ERROR / SKIPPED
- U selhání: název testu + chybová hláška (stručně)
- Pokud `tests/` neexistuje nebo je prázdný → zaznamenej INFO "Žádné pytest testy"

---

## Fáze 2: ROUTE COVERAGE (~2 min)

Získej všechny GET routy z aplikace a otestuj je HTTP requestem:

```python
# Spusť jako Python skript
import requests
from app.main import app

base = "http://localhost:8021"
results = []

for route in app.routes:
    if hasattr(route, "methods") and "GET" in route.methods:
        path = route.path
        # Přeskoč routy s path parametry ({id}, {voting_id} atd.)
        if "{" in path:
            continue
        try:
            r = requests.get(f"{base}{path}", timeout=10, allow_redirects=True)
            results.append((path, r.status_code, "OK" if r.status_code < 400 else "FAIL"))
        except Exception as e:
            results.append((path, 0, str(e)))

for path, status, note in sorted(results):
    print(f"  {status}  {path}  {note}")
```

Alternativně: použij `curl` pro každou routu ručně.

Zaznamenej:
- Celkový počet GET rout
- Počet testovaných (bez path parametrů)
- HTTP status pro každou routu
- Routy s 4xx/5xx → WARNING nebo CRITICAL

---

## Fáze 3: PLAYWRIGHT SMOKE TESTY (~3 min)

Projdi 9 klíčových stránek přes Playwright (`browser_navigate` + `browser_snapshot`):

| # | URL | Co ověřit |
|---|-----|-----------|
| 1 | `/` | Dashboard se renderuje, stat karty viditelné |
| 2 | `/vlastnici` | Seznam vlastníků, tabulka s řádky (nebo prázdný stav) |
| 3 | `/jednotky` | Seznam jednotek, tabulka nebo prázdný stav |
| 4 | `/hlasovani` | Seznam hlasování |
| 5 | `/dane` | Daňové sestavy |
| 6 | `/synchronizace` | Synchronizace — taby viditelné |
| 7 | `/sprava` | Správa — karty/sekce |
| 8 | `/nastaveni` | Nastavení — formuláře/sekce |
| 9 | `/vlastnici/import` | Import wizard — stepper viditelný |

Pro každou stránku:
1. `browser_navigate(url)`
2. `browser_snapshot()` — ověř že stránka obsahuje očekávané elementy
3. Zaznamenej: ✅ OK / ❌ FAIL + důvod

---

## Fáze 4: FUNKČNÍ TESTY (~3 min)

Otestuj interaktivní prvky na vybraných stránkách:

### 4.1 Hledání (HTMX search)
- Na `/vlastnici`: napsat text do search baru, ověřit že se tabulka aktualizuje (HTMX partial swap)
- Na `/jednotky`: stejný test

### 4.2 Filtry / bubliny
- Na `/vlastnici`: kliknout na filtrační bublinu (typ vlastníka), ověřit že se URL změní a tabulka filtruje

### 4.3 Řazení sloupců
- Na `/vlastnici`: kliknout na hlavičku sloupce, ověřit že se URL změní (`?sort=...&order=...`)

### 4.4 Taby
- Na `/synchronizace`: přepnout tab, ověřit zobrazení obsahu

### 4.5 Dark mode
- Přepnout dark mode toggle v sidebaru, ověřit že se změní barvy (třída `dark` na `<html>`)

Pro každý test:
1. Proveď akci přes Playwright
2. `browser_snapshot()` — ověř výsledek
3. Zaznamenej: ✅ OK / ❌ FAIL + detail

---

## Fáze 5: JS KONZOLE — CHYBY (~1 min)

Na každé stránce z fáze 3 zkontroluj JS chyby:

```
browser_console_messages(level="error")
```

**Ignorovat known errors:**
- `tailwind is not defined` (CDN inicializace)
- `favicon.ico 404`
- `Failed to load resource` pro CDN zdroje (pokud stránka jinak funguje)

Zaznamenej:
- Stránky bez JS chyb → ✅
- Stránky s unknown JS chybami → ⚠️ WARNING + detail chyby

---

## Fáze 6: EXPORT VALIDACE (~2 min)

Otestuj export endpointy (Excel/CSV):

| # | URL | Metoda | Očekávaný content-type |
|---|-----|--------|----------------------|
| 1 | `/vlastnici/exportovat` | GET/POST | `application/vnd.openxmlformats...` |
| 2 | `/jednotky/exportovat` | GET/POST | `application/vnd.openxmlformats...` |

Pro každý export:
1. HTTP request na export URL
2. Ověř: HTTP 200, neprázdný response body, správný Content-Type
3. Ověř: filename v Content-Disposition header (bez diakritiky, obsahuje datum)

Zaznamenej:
- ✅ OK / ❌ FAIL + detail
- Pokud export endpoint neexistuje → INFO (ne všechny moduly mají export)

---

## Fáze 7: BACK URL INTEGRITA (~2 min)

Otestuj navigační řetězec Dashboard → seznam → detail → zpět:

### 7.1 Dashboard → Vlastníci
1. Na `/` klikni na kartu "Vlastníci"
2. Ověř: URL obsahuje `?back=/`
3. Ověř: stránka zobrazuje šipku zpět

### 7.2 Seznam → Detail
1. Na `/vlastnici?back=/` klikni na prvního vlastníka
2. Ověř: URL detailu obsahuje `?back=` s encoded URL seznamu
3. Ověř: šipka zpět je viditelná a má správný label

### 7.3 Zpět navigace
1. Klikni na šipku zpět
2. Ověř: vrátí se na seznam s původními parametry

### 7.4 Stejný test pro Jednotky
- Opakuj 7.1–7.3 pro `/jednotky`

Zaznamenej:
- ✅ OK / ❌ FAIL + kde se řetězec přeruší
- Chybějící `?back=` → WARNING

---

## Fáze 8: N+1 DETEKCE (~2 min)

Pro klíčové stránky se seznamem (vlastníci, jednotky, hlasování) zkontroluj počet SQL dotazů:

1. Dočasně zapni SQL logging:
   ```python
   import logging
   logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)
   ```
2. Načti stránku a spočítej SQL dotazy v logu
3. Nebo: zkontroluj v kódu routeru, zda jsou použité `joinedload()` pro relace zobrazené v tabulce

**Prahy:**
- < 20 dotazů → ✅ OK
- 20–50 dotazů → ⚠️ INFO
- \> 50 dotazů → ⚠️ WARNING "Možný N+1 problém"

Zaznamenej: počet dotazů per stránka + hodnocení

---

## Formát výstupu

Vytvoř soubor `docs/reports/TEST-REPORT.md`:

```markdown
# SVJ Test Report – [YYYY-MM-DD]

## Souhrn

| Oblast | Stav | Detail |
|--------|------|--------|
| Pytest | ✅/⚠️/❌ | X passed, Y failed |
| Route coverage | ✅/⚠️/❌ | X/Y rout OK |
| Smoke testy | ✅/⚠️/❌ | X/9 stránek OK |
| Funkční testy | ✅/⚠️/❌ | X/Y testů OK |
| JS konzole | ✅/⚠️/❌ | X stránek bez chyb |
| Exporty | ✅/⚠️/❌ | X/Y exportů OK |
| Back URL | ✅/⚠️/❌ | X/Y řetězců OK |
| N+1 detekce | ✅/⚠️/❌ | max X dotazů |

**Celkový stav: ✅ PASS / ⚠️ VAROVÁNÍ / ❌ SELHÁNÍ**

## Detaily selhání

### [Fáze X: Název]

| # | Co selhalo | Severity | Detail | Doporučení |
|---|-----------|----------|--------|------------|
| 1 | ... | CRITICAL | ... | ... |

## Doporučení

1. [Prioritní opravy]
2. [Vylepšení]
3. [Další kroky]
```

---

## Úklid po testování

Po dokončení VŽDY smazat Playwright soubory:
```bash
rm -rf .playwright-mcp/*.log .playwright-mcp/*.png .playwright-mcp/*.jpeg
rm -f *.png *.jpeg
```

---

## Spuštění

V Claude Code zadej:

```
Přečti TEST-AGENT.md a proveď kompletní testování projektu podle instrukcí. Výstupem je docs/reports/TEST-REPORT.md. Nic neopravuj, pouze testuj a reportuj.
```
