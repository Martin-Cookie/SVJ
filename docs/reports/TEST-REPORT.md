# SVJ Test Report — 2026-04-12

## Souhrn

| Oblast | Stav | Detail |
|--------|------|--------|
| Pytest | ✅ | 336 passed, 0 failed, 24 warnings (legacy API) |
| Route coverage | ✅ | 52/55 testovatelnych rout OK (3 FAIL = ocekavane 422) |
| Smoke testy | ✅ | 9/9 stranek OK |
| Funkcni testy | ✅ | 5/5 testu OK |
| JS konzole | ✅ | 0 JS chyb na vsech strankach |
| Exporty | ✅ | 6/6 exportu OK |
| Back URL | ✅ | 2/2 retezcu OK |
| N+1 detekce | ⚠️ | 13 routeru bez joinedload pri >5 queries |

**Celkovy stav: ✅ PASS s informacnimi nalezy**

---

## Faze 1: Pytest

- **Vysledek:** 336 passed, 0 failed
- **Warnings:** 24x `LegacyAPIWarning` — `Query.get()` deprecated v SQLAlchemy 2.0
- **Cas:** 3.66s

| Severity | Detail | Doporuceni |
|----------|--------|------------|
| INFO | 24x `db.query(Model).get(id)` pouziva legacy API | Postupne nahradit za `db.get(Model, id)` — neni urgentni |

---

## Faze 2: Route Coverage

- **Celkem rout:** 137
- **Testovanych (bez path params):** 55
- **Preskocenych (path params):** 82
- **OK:** 52
- **FAIL:** 3

| # | Routa | HTTP | Severity | Detail |
|---|-------|------|----------|--------|
| 1 | `/kontrola-podilu/mapovani` | 422 | INFO | Vyzaduje POST data (formular) — ocekavane chovani |
| 2 | `/sprava/hromadne-upravy/hodnoty` | 422 | INFO | Vyzaduje query parametry — ocekavane chovani |
| 3 | `/sprava/hromadne-upravy/zaznamy` | 422 | INFO | Vyzaduje query parametry — ocekavane chovani |

Vsechny 3 FAILy jsou endpointy ktere ocekavaji POST data nebo povinne query parametry — legitimni HTTP 422 odpovedi.

---

## Faze 3: Playwright Smoke Testy

| # | URL | Titul stranky | Stav |
|---|-----|---------------|------|
| 1 | `/` | Prehled - SVJ Sprava | ✅ Stat karty, tabulka, navigace |
| 2 | `/vlastnici/` | Vlastnici - SVJ Sprava | ✅ 447 vlastniku v tabulce |
| 3 | `/jednotky/` | Jednotky - SVJ Sprava | ✅ Tabulka, bubliny |
| 4 | `/hlasovani/` | Hlasovani per rollam - SVJ Sprava | ✅ 2 hlasovani, bubliny stavu |
| 5 | `/dane/` | Hromadne rozesilaní - SVJ Sprava | ✅ Seznam sessi |
| 6 | `/synchronizace/` | Kontroly - SVJ Sprava | ✅ Sekce viditelne |
| 7 | `/sprava/` | Administrace - SVJ Sprava | ✅ Karty/sekce |
| 8 | `/nastaveni/` | Nastaveni - SVJ Sprava | ✅ Formulare/sekce |
| 9 | `/vlastnici/import` | Import z Excelu - SVJ Sprava | ✅ Wizard stepper |

**Konzolove chyby:** 0 na vsech strankach. Jediny warning = Tailwind CDN produkce (ocekavane).

---

## Faze 4: Funkcni Testy

| # | Test | Stav | Detail |
|---|------|------|--------|
| 1 | Hledani — `/vlastnici` | ✅ | HTMX search "nov" filtrovalo 447 → 94 radku |
| 2 | Filtry/bubliny — `/vlastnici?typ=legal` | ✅ | Filtr na pravnicke osoby: 447 → 19 radku |
| 3 | Razeni sloupcu — `/vlastnici?sort=email&order=asc` | ✅ | URL se zmenila, tabulka prerazena |
| 4 | Taby — `/synchronizace` | ✅ | Sekce viditelne, obsah se prepina |
| 5 | Dark mode toggle | ✅ | Trida `dark` pridana/odebrana na `<html>`, tlacitko meni label |

---

## Faze 5: JS Konzole — Chyby

| # | Stranka | JS chyby | Warningy |
|---|---------|----------|----------|
| 1 | `/` | 0 | 1 (Tailwind CDN) |
| 2 | `/vlastnici/` | 0 | 1 (Tailwind CDN) |
| 3 | `/jednotky/` | 0 | 1 (Tailwind CDN) |
| 4 | `/hlasovani/` | 0 | 1 (Tailwind CDN) |
| 5 | `/dane/` | 0 | 1 (Tailwind CDN) |
| 6 | `/synchronizace/` | 0 | 1 (Tailwind CDN) |
| 7 | `/sprava/` | 0 | 1 (Tailwind CDN) |
| 8 | `/nastaveni/` | 0 | 1 (Tailwind CDN) |
| 9 | `/vlastnici/import` | 0 | 1 (Tailwind CDN) |

**Zadne JS chyby na zadne strance.**

---

## Faze 6: Export Validace

| # | Endpoint | HTTP | Content-Type | Filename | Stav |
|---|----------|------|--------------|----------|------|
| 1 | `/vlastnici/exportovat/xlsx` | 200 | `application/vnd.openxml...` | `vlastnici_vsichni_20260412.xlsx` | ✅ |
| 2 | `/vlastnici/exportovat/csv` | 200 | `text/csv; charset=utf-8` | `vlastnici_vsichni_20260412.csv` | ✅ |
| 3 | `/jednotky/exportovat/xlsx` | 200 | `application/vnd.openxml...` | `jednotky_vsechny_20260412.xlsx` | ✅ |
| 4 | `/jednotky/exportovat/csv` | 200 | `text/csv; charset=utf-8` | `jednotky_vsechny_20260412.csv` | ✅ |
| 5 | `/najemci/exportovat/xlsx` | 200 | OK | — | ✅ |
| 6 | `/prostory/exportovat/xlsx` | 200 | OK | — | ✅ |

Vsechny exporty funguji, filenames obsahuji datum a suffix dle filtru.

---

## Faze 7: Back URL Integrita

### 7.1 Vlastnici
| Krok | Ocekavani | Stav |
|------|-----------|------|
| Seznam → Detail | `/vlastnici/348?back=/vlastnici/%23owner-348` | ✅ back s scroll anchor |
| Detail → Zpet | `← Zpet na seznam vlastniku` → `/vlastnici/#owner-348` | ✅ sipka + scroll |
| Detail → Jednotka | `/jednotky/441?back=/vlastnici/348%3Fback%3D...` | ✅ vnoreny back |

### 7.2 Jednotky
| Krok | Ocekavani | Stav |
|------|-----------|------|
| Seznam → Detail | `/jednotky/1?back=/jednotky/%23unit-1` | ✅ back s scroll anchor |
| Detail → Zpet | `← Zpet na seznam jednotek` → `/jednotky/#unit-1` | ✅ sipka + scroll |
| Detail → Vlastnik | `/vlastnici/1?back=/jednotky/1%3Fback%3D...` | ✅ vnoreny back |

**Oba navigacni retezce funguji spravne vcetne vnorenych back URL.**

---

## Faze 8: N+1 Detekce

### Prehled joinedload pokryti v routerech

| Router | db.query() | joinedload() | .all() | Hodnoceni |
|--------|-----------|-------------|--------|-----------|
| payments/statements.py | 48 | 10 | 15 | ✅ Pokryto |
| tax/sending.py | 45 | 20 | 18 | ✅ Pokryto |
| owners/crud.py | 42 | 15 | 8 | ✅ Pokryto |
| **dashboard.py** | **31** | **0** | **13** | ⚠️ **Bez joinedload** |
| units.py | 24 | 10 | 4 | ✅ Pokryto |
| voting/session.py | 24 | 20 | 8 | ✅ Pokryto |
| spaces/crud.py | 24 | 11 | 3 | ✅ Pokryto |
| **settings_page.py** | **23** | **0** | **7** | ⚠️ **Bez joinedload** |
| **payments/discrepancies.py** | **18** | **0** | **3** | ⚠️ **Bez joinedload** |
| **share_check.py** | **16** | **0** | **8** | ⚠️ **Bez joinedload** |
| **sync/contacts.py** | **14** | **0** | **4** | ⚠️ **Bez joinedload** |
| **payments/_helpers.py** | **13** | **0** | **5** | ⚠️ **Bez joinedload** |
| **spaces/import_spaces.py** | **13** | **0** | **3** | ⚠️ **Bez joinedload** |
| **payments/overview.py** | **12** | **0** | **4** | ⚠️ **Bez joinedload** |
| **tax/matching.py** | **11** | **0** | **1** | ⚠️ **Bez joinedload** |
| **administration/code_lists.py** | **11** | **0** | **1** | ⚠️ **Bez joinedload** |
| **owners/import_owners.py** | **8** | **0** | **2** | ⚠️ **Bez joinedload** |
| **sync/_helpers.py** | **8** | **0** | **4** | ⚠️ **Bez joinedload** |

**13 routeru s >5 queries a 0 joinedload.** Nektere z nich nemusi byt problematicke (helpery, importy, settings pracuji s jednoducymi queries bez relaci), ale `dashboard.py` (31 queries, 0 joinedload) a `payments/overview.py` (12 queries, 0 joinedload) by mohly benefitovat z eager loading.

| Severity | Router | Doporuceni |
|----------|--------|------------|
| INFO | `dashboard.py` | 31 queries bez joinedload — zvazit eager loading pro stat karty pokud zobrazuji relacni data |
| INFO | `settings_page.py` | 23 queries — pravdepodobne OK, nastaveni pracuji s jednoducymi modely |
| INFO | `payments/overview.py` | 12 queries — zkontrolovat zda prehled nepouziva lazy-loaded relace |
| INFO | `payments/discrepancies.py` | Service vraci dataclass, ne ORM — joinedload nerelevantni |

---

## Doporuceni

### Priorita 1 — Nizka (informacni)
1. **Legacy API warnings** (24x) — `db.query(Model).get(id)` → `db.get(Model, id)` postupne. Neni urgentni, ale SQLAlchemy 2.0 to oznacuje jako deprecated.

### Priorita 2 — Nizka (optimalizace)
2. **Dashboard joinedload** — `dashboard.py` ma 31 queries bez jedineho joinedload. Pokud stat karty nebo tabulka posledni aktivity pristupuji k relacim (vlastnik → jednotky, hlasovani → lístky), muze dochazet k N+1.
3. **Payments overview** — podobny scenar, 12 queries bez eager loading.

### Priorita 3 — Zadna akce nutna
4. **3 routy s HTTP 422** — `/kontrola-podilu/mapovani`, `/sprava/hromadne-upravy/hodnoty`, `/sprava/hromadne-upravy/zaznamy` — ocekavane chovani (vyzaduji POST/parametry).
5. **Tailwind CDN warning** — jediny JS warning na vsech strankach, ocekavane pro dev prostredi.

---

## Zaver

Aplikace je v **stabilnim stavu**. Vsech 336 pytest testu prochazi, vsechny klicove stranky se renderuji bez chyb, HTMX interakce (search, filtry, razeni, dark mode) funguji spravne, exporty vracuji spravne soubory, a navigacni retezce (back URL) jsou konzistentni. Jedine nalezy jsou informacniho charakteru (legacy API warnings, potencialni N+1 optimalizace v dashboard routeru).
