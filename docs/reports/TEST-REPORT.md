# SVJ Test Report -- 2026-04-21

> Test Agent -- hluboky mod. Kontext: 2 commity od posledniho auditu (refactor agentu).

## Souhrn

| Oblast | Stav | Detail |
|--------|------|--------|
| Pytest | PASS | 580/580 passed, 35 warnings |
| Route coverage | PASS | 13/13 hlavnich rout OK (200) |
| Smoke testy | PASS | 9/9 stranek OK, 0 JS errors |
| JS konzole | PASS | 0 errors na vsech 9 strankach |
| Funkcni testy | PASS | 3/3 (hledani, razeni, dark mode) |
| Exporty | PASS | 4/4 (vlastnici+jednotky xlsx/csv) |
| Back URL | PASS | 3/3 (dashboard->seznam->detail->zpet) |

**Celkovy stav: PASS**

## Faze 1: Pytest

- 580 testu PASSED
- 0 FAILED, 0 ERROR, 0 SKIPPED
- 35 LegacyAPIWarning (db.query().get() deprecated) -- neblokovane
- Cas: 18.23s

## Faze 2: Route coverage

| Route | Status | Poznamka |
|-------|--------|----------|
| / | 200 | OK |
| /vlastnici | 307->200 | Trailing slash redirect |
| /jednotky | 307->200 | Trailing slash redirect |
| /hlasovani | 307->200 | Trailing slash redirect |
| /rozesilani | 307->200 | Trailing slash redirect |
| /synchronizace | 307->200 | Trailing slash redirect |
| /sprava | 307->200 | Trailing slash redirect |
| /nastaveni | 307->200 | Trailing slash redirect |
| /platby | 302->200 | Redirect na /platby/predpisy (zamerne) |
| /kontrola-podilu | 307->200 | Trailing slash redirect |
| /vodometry | 307->200 | Trailing slash redirect |
| /najemci | 307->200 | Trailing slash redirect |
| /prostory | 307->200 | Trailing slash redirect |
| /vlastnici/import | 200 | OK |

Sub-stranky: /vlastnici/kontakty/import (404 -- route neexistuje), /vlastnici/vymena (422 -- vyzaduje POST)

## Faze 3: Smoke testy (Playwright)

| # | Stranka | Vysledek | JS errors |
|---|---------|----------|-----------|
| 1 | Dashboard | OK -- 7 stat karet (452 vlastniku, 508 jednotek, 20 najemcu...) | 0 |
| 2 | Vlastnici | OK -- 452 vlastniku v tabulce | 0 |
| 3 | Jednotky | OK -- 508 jednotek v tabulce | 0 |
| 4 | Hlasovani | OK -- 2 sessions | 0 |
| 5 | Rozesilani | OK -- 5 sessions | 0 |
| 6 | Synchronizace | OK -- 2 taby viditelne | 0 |
| 7 | Sprava | OK -- 7 admin karet | 0 |
| 8 | Nastaveni | OK -- formulare + email log | 0 |
| 9 | Import wizard | OK -- stepper pritomen | 0 |

## Faze 4: Funkcni testy

| Test | Vysledek | Detail |
|------|----------|--------|
| Hledani (HTMX) | OK | "a" -> 441/452, "novak" -> 10/452. Partial swap funguje. |
| Razeni sloupcu | OK | 9 razitelnych sloupcu, URL se aktualizuje (?sort=&order=) |
| Dark mode | OK | Toggle prida/odebere class "dark" na html |

## Faze 5: Export validace

| Endpoint | Status | Content-Type | Velikost |
|----------|--------|-------------|----------|
| /vlastnici/exportovat/xlsx | 200 | application/vnd.openxmlformats... | 46 KB |
| /jednotky/exportovat/xlsx | 200 | application/vnd.openxmlformats... | 37 KB |
| /vlastnici/exportovat/csv | 200 | text/csv; charset=utf-8 | 78 KB |
| /jednotky/exportovat/csv | 200 | text/csv; charset=utf-8 | 34 KB |

Poznamka: /hlasovani/exportovat a /platby/exportovat neexistuji (404) -- tyto moduly nemaji export.

## Faze 6: Back URL integrita

| Krok | Vysledek | Detail |
|------|----------|--------|
| Dashboard -> Vlastnici | OK | /vlastnici?back=/ |
| Seznam -> Detail | OK | /vlastnici/514?back=/vlastnici/%3Fback%3D/%23owner-514 |
| Detail -> Zpet | OK | /vlastnici/?back=/#owner-514 (scroll anchor zachovan) |

## Doporuceni

1. 35x LegacyAPIWarning (`db.query().get()`) -- migrace na `db.get()` v pristi iteraci
2. /vlastnici/kontakty/import (404) -- overit zda route existuje nebo aktualizovat test
3. Export pro hlasovani/platby -- zvazit pridani
