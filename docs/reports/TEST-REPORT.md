# SVJ Test Report — 2026-04-17

> Kontext: 20 commitů od posledního testu (5. dubna). Hlavní změny: modul vodoměry (rozesílka, preview, historie, vs_prumer), bounce service (IMAP, multi-profil), scroll opravy.
> Server: `http://localhost:8000` (port 8021 obsazen ghost procesem)

## Souhrn

| Oblast | Stav | Detail |
|--------|------|--------|
| Pytest | ✅ | 336 passed, 0 failed, 25 warnings (legacy SQLAlchemy) |
| Route coverage | ✅ | 59/62 rout OK (3x 422 = očekávané — chybí povinné query parametry) |
| Smoke testy | ✅ | 9/9 stránek OK + 3 bonusové (vodometry, bounces) |
| Funkční testy | ✅ | 5/5 testů OK (search, filtry, řazení, taby, dark mode) |
| JS konzole | ✅ | 0 JS chyb na 12 testovaných stránkách (1 known warning: Tailwind CDN) |
| Exporty | ✅ | 16/16 exportů OK (XLSX + CSV pro 8 modulů) |
| Back URL | ✅ | 2/2 navigačních řetězců OK (vlastníci, jednotky) |
| N+1 detekce | ✅ | 181 joinedload volání, všechny list stránky < 200ms |

**Celkový stav: ✅ PASS s drobnými varováními**

---

## Fáze 1: Pytest

```
336 passed, 25 warnings in 13.11s
```

- Všech 336 testů prošlo
- 25 warnings = `LegacyAPIWarning` pro `Query.get()` (SQLAlchemy 2.0 deprecation) — nemá vliv na funkčnost
- Pokrytí: `test_backup.py`, `test_import.py`, `test_models.py`, `test_payment_advanced.py`, `test_purge.py`, `test_sync.py`, `test_voting.py`

---

## Fáze 2: Route coverage

Testováno 62 GET rout bez path parametrů:

| Status | Počet | Detail |
|--------|-------|--------|
| 200 | 59 | Všechny hlavní stránky |
| 422 | 3 | Očekávané — vyžadují query parametry |

**Routy s 422 (INFO, ne chyba):**
- `/kontrola-podilu/mapovani` — vyžaduje upload context
- `/sprava/hromadne-upravy/hodnoty` — vyžaduje field parametr
- `/sprava/hromadne-upravy/zaznamy` — vyžaduje field parametr

---

## Fáze 3: Playwright smoke testy

| # | URL | Stav | Detail |
|---|-----|------|--------|
| 1 | `/` | ✅ | Dashboard — stat karty, tabulka aktivity |
| 2 | `/vlastnici` | ✅ | 453 vlastníků, tabulka s řádky |
| 3 | `/jednotky` | ✅ | 508 jednotek |
| 4 | `/hlasovani` | ✅ | Seznam hlasování |
| 5 | `/dane` | ✅ | Hromadné rozesílání |
| 6 | `/synchronizace` | ✅ | Kontroly — sessions viditelné |
| 7 | `/sprava` | ✅ | Administrace — sekce viditelné |
| 8 | `/nastaveni` | ✅ | Nastavení — formuláře |
| 9 | `/vlastnici/import` | ✅ | Import wizard |
| 10 | `/vodometry` | ✅ | 218 vodoměrů, bubliny, search |
| 11 | `/vodometry/rozeslat` | ✅ | Rozesílka odečtů |
| 12 | `/rozesilani/bounces` | ✅ | Nedoručené emaily |

---

## Fáze 4: Funkční testy

| # | Test | Stav | Detail |
|---|------|------|--------|
| 4.1a | Hledání `/vlastnici?q=novak` | ✅ | 7 výsledků, HTMX partial swap funguje |
| 4.1b | Hledání `/jednotky?q=10` | ✅ | 22 výsledků |
| 4.2 | Filtry `/vlastnici?typ=physical` | ✅ | 434 fyzických osob (z 453 celkem) |
| 4.3 | Řazení `/vlastnici?sort=name&order=desc` | ✅ | Z→A pořadí (Zvěřina, Zubčeková) |
| 4.4 | Synchronizace — sessions | ✅ | 5 sessions s řaditelnými sloupci |
| 4.5 | Dark mode toggle | ✅ | `dark` třída na `<html>` se přepíná, text tlačítka se mění |

---

## Fáze 5: JS konzole

| # | Stránka | JS errors | Warnings |
|---|---------|-----------|----------|
| 1 | `/` | 0 | 1 (Tailwind CDN) |
| 2 | `/vlastnici` | 0 | 1 |
| 3 | `/jednotky` | 0 | 1 |
| 4 | `/hlasovani` | 0 | 1 |
| 5 | `/dane` | 0 | 1 |
| 6 | `/synchronizace` | 0 | 1 |
| 7 | `/sprava` | 0 | 1 |
| 8 | `/nastaveni` | 0 | 1 |
| 9 | `/vlastnici/import` | 0 | 1 |
| 10 | `/vodometry` | 0 | 1 |
| 11 | `/vodometry/rozeslat` | 0 | 1 |
| 12 | `/rozesilani/bounces` | 0 | 1 |

**Všechny stránky: 0 JS chyb.** Jediný warning na všech stránkách: `cdn.tailwindcss.com should not be used in production` (known, CDN dev mode).

---

## Fáze 6: Exporty

| # | Modul | XLSX | CSV | Filename | Datum v názvu |
|---|-------|------|-----|----------|---------------|
| 1 | Vlastníci | ✅ 45 KB | ✅ 77 KB | `vlastnici_vsichni_20260417` | ✅ |
| 2 | Jednotky | ✅ 37 KB | ✅ 34 KB | `jednotky_vsechny_20260417` | ✅ |
| 3 | Hlasování (id=1) | ✅ 18 KB | — | `hlasovani_1_vsechny_20260417` | ✅ |
| 4 | Předpisy (id=1) | ✅ 30 KB | ✅ 33 KB | `predpisy_2026_vse_20260417` | ✅ |
| 5 | Symboly | ✅ 19 KB | ✅ 33 KB | `symboly_vsechny_20260417` | ✅ |
| 6 | Výpisy | ✅ 5 KB | ✅ 538 B | `vypisy_vse_20260417` | ✅ |
| 7 | Nájemci | ✅ 7 KB | ✅ 2 KB | `najemci_vsichni_20260417` | ✅ |
| 8 | Prostory | ✅ 7 KB | ✅ 2 KB | `prostory_vse_20260417` | ✅ |
| 9 | Vodoměry | ✅ 20 KB | ✅ 17 KB | `vodometry_vsechny` | ⚠️ **chybí** |

---

## Fáze 7: Back URL integrita

### 7.1 Dashboard → Vlastníci → Detail → Zpět

| Krok | URL | Back param | Stav |
|------|-----|------------|------|
| Dashboard karta | `/vlastnici?back=/` | ✅ `back=/` | ✅ |
| Seznam → back arrow | `← Přehled` → `/` | ✅ | ✅ |
| Seznam → detail | `/vlastnici/429?back=/vlastnici/...#owner-429` | ✅ encoded | ✅ |
| Detail → back arrow | `← Zpět na seznam vlastníků` → `/vlastnici/?back=/#owner-429` | ✅ se scroll | ✅ |

### 7.2 Dashboard → Jednotky → Detail → Zpět

| Krok | URL | Back param | Stav |
|------|-----|------------|------|
| Dashboard karta | `/jednotky?back=/` | ✅ `back=/` | ✅ |
| Seznam → detail | `/jednotky/1?back=/jednotky/...#unit-1` | ✅ encoded | ✅ |
| Detail → back arrow | `← Zpět na seznam jednotek` → `/jednotky/?back=/#unit-1` | ✅ se scroll | ✅ |

**Oba navigační řetězce jsou kompletní a funkční.**

---

## Fáze 8: N+1 detekce

### Eager loading analýza kódu

| Modul | joinedload volání | Stav |
|-------|-------------------|------|
| `owners/crud.py` | 15 | ✅ |
| `units.py` | 10 | ✅ |
| `voting/session.py` | 20 | ✅ |
| `tenants/crud.py` | 14 | ✅ |
| `spaces/crud.py` | 11 | ✅ |
| `water_meters/overview.py` | 7 | ✅ (contains_eager + joinedload) |

**Celkem 181 joinedload volání across 25 router souborů.**

### Response time benchmarks

| Stránka | Čas | Velikost | Stav |
|---------|-----|----------|------|
| `/vlastnici/` | 83ms | 809 KB | ✅ |
| `/jednotky/` | 115ms | 805 KB | ✅ |
| `/hlasovani/` | 17ms | 45 KB | ✅ |
| `/najemci/` | 12ms | 70 KB | ✅ |
| `/prostory/` | 11ms | 73 KB | ✅ |
| `/vodometry/` | 100ms | 458 KB | ✅ |
| `/platby/symboly` | 50ms | 1.4 MB | ✅ |
| `/platby/vypisy` | 18ms | 39 KB | ✅ |
| `/platby/predpisy` | 191ms | 677 KB | ✅ |
| `/platby/zustatky` | 100ms | 232 KB | ✅ |
| `/synchronizace/` | 10ms | 44 KB | ✅ |

**Všechny list stránky pod 200ms. Žádný N+1 problém detekován.**

---

## Detaily nálezů

### WARNING

| # | Co | Kde | Severity | Detail | Doporučení |
|---|-----|-----|----------|--------|------------|
| 1 | Chybí datum v export filename | `/vodometry/exportovat/{fmt}` | WARNING | Filename `vodometry_vsechny.xlsx` bez `_20260417` suffixu | Přidat `_{date.today().strftime('%Y%m%d')}` do filename — sjednotit s ostatními moduly |
| 2 | Chybí "Zobrazeno: X" counter | `/vodometry/` | WARNING | Tabulková stránka s 218 řádky nemá počítadlo záznamů | Přidat `Zobrazeno: {{ meters\|length }} vodoměrů` pod tabulku — povinný bod 8 z tabulkového checklistu |
| 3 | Chybí "- SVJ Správa" v title | `/vodometry/`, `/vodometry/rozeslat` | WARNING | Page title je jen "Vodoměry" resp. "Rozesílka odečtů vodoměrů" | Sjednotit title pattern: `{% block title %}Vodoměry - SVJ Správa{% endblock %}` |
| 4 | Chybí "- SVJ Správa" v title | Všechny `/platby/*` stránky (8 stránek) | WARNING | Tituly jsou např. "Předpisy 2026", "Variabilní symboly" bez suffixu | Sjednotit title pattern ve všech platby šablonách |

### INFO

| # | Co | Kde | Severity | Detail |
|---|-----|-----|----------|--------|
| 5 | Prázdné jméno v title | `/vlastnici/429` | INFO | Title je `- SVJ Správa` (prázdné jméno) — pravděpodobně právnická osoba s jiným display_name |
| 6 | SQLAlchemy legacy warnings | Pytest | INFO | 25x `LegacyAPIWarning` pro `Query.get()` — projekt záměrně používá legacy API |
| 7 | Route 422 bez parametrů | 3 routy | INFO | `/kontrola-podilu/mapovani`, `/sprava/hromadne-upravy/hodnoty`, `/sprava/hromadne-upravy/zaznamy` — vyžadují kontext, ne chyba |
| 8 | HTMX search nerefrešuje counter | `/vlastnici` | INFO | Při HTMX partial search se "Zobrazeno: X" neaktualizuje (counter je mimo tbody) — full reload counter aktualizuje |

---

## Doporučení

### Priorita 1 — opravit (~10 min celkem)
1. **Vodometry export filename** — přidat datum do názvu souboru (`_YYYYMMDD` suffix)
2. **Vodometry "Zobrazeno" counter** — přidat počítadlo pod tabulku

### Priorita 2 — konzistence (~15 min celkem)
3. **Title suffix "- SVJ Správa"** — sjednotit ve vodometry šablonách (2 stránky) a platby šablonách (8 stránek)

### Priorita 3 — vylepšení (nízká)
4. **HTMX search counter update** — zahrnout counter do HTMX partial response (platí pro všechny moduly, ne jen vodometry)
5. **SQLAlchemy legacy warnings** — postupná migrace z `Query.get()` na `Session.get()` (pouze kosmetické)

---

## Srovnání s předchozím testem (2026-04-12)

| Metrika | 12.4. | 17.4. | Změna |
|---------|-------|-------|-------|
| Pytest testy | 336 | 336 | = |
| Pytest failures | 0 | 0 | = |
| GET routy | ~55 | 62 | +7 nových (vodometry, bounces) |
| Route failures | 0 | 0 | = |
| JS chyby | 0 | 0 | = |
| Průměrný response time | — | < 100ms | ✅ |
| Nové moduly od testu | — | vodometry rozesílka, bounce service | +2 |
