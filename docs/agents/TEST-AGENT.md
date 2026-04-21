# Test Agent – Automatické testování aplikace

> Spouštěj po bloku změn nebo před releasem.
> Výstup: `docs/reports/TEST-REPORT.md`.
> N+1 a výkonové problémy kontroluje Code Guardian, ne tento agent.

---

## Cíl

Otestovat SVJ aplikaci: pytest, route coverage, Playwright smoke + funkční testy, exporty, back URL integrita. Výstup: `docs/reports/TEST-REPORT.md`.

---

## Instrukce

**NEPRAV ŽÁDNÝ KÓD. POUZE TESTUJ A REPORTUJ.**

### Rychlý vs. hluboký mód

- **Rychlý**: Fáze 1 (pytest) + Fáze 2 (route coverage) + Fáze 3 (smoke testy)
- **Hluboký**: Všech 6 fází

Orchestrátor řekne který mód. Bez instrukce = hluboký.

**Před spuštěním** — ověř že server běží na `http://localhost:8021`:
```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:8021/
```
Pokud neběží:
```bash
cd /Users/martinkoci/Projects/SVJ && source .venv/bin/activate && python -m uvicorn app.main:app --port 8021 &
```

---

## Fáze 1: PYTEST (~1 min)

```bash
cd /Users/martinkoci/Projects/SVJ && source .venv/bin/activate && python3 -m pytest tests/ -v --tb=short 2>&1
```

Zaznamenej: celkový počet, PASSED/FAILED/ERROR/SKIPPED, u selhání název + chyba.

---

## Fáze 2: ROUTE COVERAGE (~2 min)

Získej všechny GET routy bez path parametrů, otestuj HTTP requestem:

```bash
# Pro každou routu bez {parametr}:
curl -s -o /dev/null -w "%{http_code}" http://localhost:8021/cesta
```

Zaznamenej: celkový počet GET rout, testované (bez path params), HTTP status, 4xx/5xx → WARNING/CRITICAL.

---

## Fáze 3: PLAYWRIGHT SMOKE TESTY (~3 min)

Projdi 9 stránek přes `browser_navigate` + `browser_snapshot`:

| # | URL | Co ověřit |
|---|-----|-----------|
| 1 | `/` | Dashboard, stat karty |
| 2 | `/vlastnici` | Tabulka vlastníků |
| 3 | `/jednotky` | Tabulka jednotek |
| 4 | `/hlasovani` | Seznam hlasování |
| 5 | `/rozesilani` | Rozesílání |
| 6 | `/synchronizace` | Taby viditelné |
| 7 | `/sprava` | Karty/sekce |
| 8 | `/nastaveni` | Formuláře/sekce |
| 9 | `/vlastnici/import` | Import wizard stepper |

Na každé stránce zároveň zkontroluj `browser_console_messages(level="error")`.
Ignorovat: `tailwind is not defined`, `favicon.ico 404`, CDN resource errors.

---

## Fáze 4: FUNKČNÍ TESTY (~3 min)

### 4.1 Hledání (HTMX search)
- `/vlastnici`: napsat text do search, ověřit HTMX partial swap
- `/jednotky`: stejný test

### 4.2 Filtry / bubliny
- `/vlastnici`: kliknout na bublinu, ověřit filtraci + URL změnu

### 4.3 Řazení sloupců
- `/vlastnici`: kliknout na hlavičku sloupce, ověřit `?sort=...&order=...`

### 4.4 Taby
- `/synchronizace`: přepnout tab, ověřit obsah

### 4.5 Dark mode
- Toggle v sidebaru, ověřit třídu `dark` na `<html>`

---

## Fáze 5: EXPORT VALIDACE (~2 min)

Otestuj export endpointy:

| URL | Očekávání |
|-----|-----------|
| `/vlastnici/exportovat/xlsx` | 200, neprázdný, správný Content-Type |
| `/jednotky/exportovat/xlsx` | 200, neprázdný, správný Content-Type |

Ověř: HTTP 200, Content-Disposition s filename bez diakritiky.

---

## Fáze 6: BACK URL INTEGRITA (~2 min)

### 6.1 Dashboard → Vlastníci → Detail → Zpět
1. `/` → klik karta Vlastníci → URL obsahuje `?back=/`
2. Klik na vlastníka → URL detailu má `?back=` s encoded seznamem
3. Klik šipka zpět → návrat na seznam s parametry

### 6.2 Stejný test pro Jednotky

Zaznamenej kde se řetězec přeruší.

---

## Úklid po testování

```bash
rm -rf .playwright-mcp/*.log .playwright-mcp/*.png .playwright-mcp/*.jpeg
rm -f *.png *.jpeg
```

---

## Formát výstupu

Vytvoř `docs/reports/TEST-REPORT.md`:

```markdown
# SVJ Test Report – [YYYY-MM-DD]

## Souhrn

| Oblast | Stav | Detail |
|--------|------|--------|
| Pytest | .../... | X passed, Y failed |
| Route coverage | .../... | X/Y rout OK |
| Smoke testy | .../... | X/9 stránek OK |
| JS konzole | .../... | X stránek bez chyb |
| Funkční testy | .../... | X/Y testů OK |
| Exporty | .../... | X/Y exportů OK |
| Back URL | .../... | X/Y řetězců OK |

**Celkový stav: PASS / VAROVÁNÍ / SELHÁNÍ**

## Detaily selhání

| # | Fáze | Co selhalo | Severity | Detail | Doporučení |
|---|------|-----------|----------|--------|------------|
| 1 | ... | ... | ... | ... | ... |

## Doporučení
1. [prioritní opravy]
2. [vylepšení]
```

---

## Spuštění

```
Přečti TEST-AGENT.md a otestuj projekt. Výstup: docs/reports/TEST-REPORT.md. Nic neopravuj.
```
