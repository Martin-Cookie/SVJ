# SVJ Test Report -- 2026-04-05

## Souhrn

| Oblast | Stav | Detail |
|--------|------|--------|
| Pytest | ✅ | 298 passed, 0 failed, 35 warnings |
| Route coverage | ⚠️ | 51/54 rout OK, 3x HTTP 422 |
| Smoke testy | ✅ | 9/9 stranek OK |
| Funkcni testy | ✅ | 5/5 testu OK |
| JS konzole | ✅ | 0 JS chyb na vsech strankach |
| Exporty | ✅ | 4/4 exportu OK |
| Back URL | ✅ | 2/2 retezcu OK |
| N+1 detekce | ✅ | joinedload pouzit ve vsech klicovych routerech |

**Celkovy stav: ✅ PASS (s drobnymi varovanimi)**

---

## Faze 1: Pytest

- **Celkovy pocet testu:** 298
- **Vysledek:** 298 PASSED, 0 FAILED, 0 ERROR, 0 SKIPPED
- **Warnings:** 35 (vsechny `LegacyAPIWarning` -- `Query.get()` je legacy od SQLAlchemy 2.0)
- **Cas:** 2.64s

### Varovani (INFO)

| # | Typ | Detail | Severity |
|---|-----|--------|----------|
| 1 | LegacyAPIWarning | `db.query(Model).get(id)` pouzivan na ~10 mistech v routerech a testech | INFO |

**Doporuceni:** Zvazit migraci na `db.get(Model, id)` pri budoucim refactoringu. Neni urgentni.

---

## Faze 2: Route Coverage

- **Celkem GET rout (bez path parametru):** 54
- **OK (HTTP 200):** 51
- **FAIL (HTTP 422):** 3

### Selhani

| # | URL | HTTP | Severity | Detail | Doporuceni |
|---|-----|------|----------|--------|------------|
| 1 | `/kontrola-podilu/mapovani` | 422 | INFO | Endpoint vyzaduje query parametry (soubor) | Ocekavane chovani -- endpoint neni urcen pro primy pristup |
| 2 | `/sprava/hromadne-upravy/hodnoty` | 422 | INFO | Endpoint vyzaduje query parametry (pole, hodnota) | Ocekavane chovani -- HTMX partial endpoint |
| 3 | `/sprava/hromadne-upravy/zaznamy` | 422 | INFO | Endpoint vyzaduje query parametry | Ocekavane chovani -- HTMX partial endpoint |

**Poznamka:** Vsechny 3 selhani jsou HTMX partial endpointy, ktere vyzaduji parametry. Toto je ocekavane chovani, ne skutecna chyba.

---

## Faze 3: Playwright Smoke Testy

| # | URL | Titul stranky | Vysledek |
|---|-----|---------------|----------|
| 1 | `/` | Prehled - SVJ Sprava | ✅ Dashboard, stat karty, sidebar |
| 2 | `/vlastnici` | Vlastnici - SVJ Sprava | ✅ Tabulka, 447 vlastniku, bubliny, search |
| 3 | `/jednotky` | Jednotky - SVJ Sprava | ✅ Tabulka, bubliny, search |
| 4 | `/hlasovani` | Hlasovani per rollam - SVJ Sprava | ✅ 2 hlasovani, wizard steppery, vysledky |
| 5 | `/dane` | Hromadne rozesilani - SVJ Sprava | ✅ 3 kampane, wizard steppery, bubliny |
| 6 | `/synchronizace` | Kontroly - SVJ Sprava | ✅ Taby (vlastnici/podily), historie, upload |
| 7 | `/sprava` | Administrace - SVJ Sprava | ✅ 7 karet (Info, Ciselniky, Zalohy, Export, Hromadne, Duplicity, Smazat) |
| 8 | `/nastaveni` | Nastaveni - SVJ Sprava | ✅ Formulare, sekce |
| 9 | `/vlastnici/import` | Import z Excelu - SVJ Sprava | ✅ Wizard stepper, upload formulare, historie |

---

## Faze 4: Funkcni Testy

| # | Test | Stranka | Vysledek | Detail |
|---|------|---------|----------|--------|
| 1 | Hledani (HTMX search) | `/vlastnici` | ✅ | Zadani "Nov" vyfiltrovalo vlastniky (Novak, Novotna, Novosad atd.), URL se aktualizovala s `?q=Nov` |
| 2 | Filtry / bubliny | `/vlastnici?typ=legal` | ✅ | Filtr "Pravnicka os." zobrazil 16 zaznamu, tabulka spravne filtrovana |
| 3 | Razeni sloupcu | `/vlastnici?sort=podil&order=desc` | ✅ | Stranka se nacetla s parametry razeni |
| 4 | Taby | `/synchronizace` | ✅ | Dva taby (Kontrola vlastniku, Kontrola podilu) zobrazeny |
| 5 | Dark mode | `/` | ✅ | Prepnuti na "Tmavy rezim" zmenilo tlacitko na "Svetly rezim", zpet funguje |

---

## Faze 5: JS Konzole

| # | Stranka | JS chyby | JS varovani | Vysledek |
|---|---------|----------|-------------|----------|
| 1 | `/` | 0 | 1 (Tailwind CDN) | ✅ |
| 2 | `/vlastnici` | 0 | 1 (Tailwind CDN) | ✅ |
| 3 | `/jednotky` | 0 | 1 (Tailwind CDN) | ✅ |
| 4 | `/hlasovani` | 0 | 1 (Tailwind CDN) | ✅ |
| 5 | `/dane` | 0 | 1 (Tailwind CDN) | ✅ |
| 6 | `/synchronizace` | 0 | 1 (Tailwind CDN) | ✅ |
| 7 | `/sprava` | 0 | 1 (Tailwind CDN) | ✅ |
| 8 | `/nastaveni` | 0 | 1 (Tailwind CDN) | ✅ |
| 9 | `/vlastnici/import` | 0 | 1 (Tailwind CDN) | ✅ |
| 10 | `/platby` | 0 | 1 (Tailwind CDN) | ✅ |

**Poznamka:** Jedine varovani je `cdn.tailwindcss.com should not be used in production` -- ocekavane, projekt pouziva Tailwind z CDN.

---

## Faze 6: Export Validace

| # | Endpoint | Format | HTTP | Content-Type | Filename | Velikost | Vysledek |
|---|----------|--------|------|--------------|----------|----------|----------|
| 1 | `/vlastnici/exportovat/xlsx` | Excel | 200 | `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` | `vlastnici_vsichni_20260405.xlsx` | 44 861 B | ✅ |
| 2 | `/vlastnici/exportovat/csv` | CSV | 200 | `text/csv; charset=utf-8` | `vlastnici_vsichni_20260405.csv` | 76 455 B | ✅ |
| 3 | `/jednotky/exportovat/xlsx` | Excel | 200 | `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` | `jednotky_vsechny_20260405.xlsx` | 36 564 B | ✅ |
| 4 | `/jednotky/exportovat/csv` | CSV | 200 | `text/csv; charset=utf-8` | `jednotky_vsechny_20260405.csv` | 34 043 B | ✅ |

**Overeno:** Spravny Content-Type, neprazdny obsah, nazvy souboru bez diakritiky s datem, suffix `_vsichni`/`_vsechny` pro nefiltrovany export.

---

## Faze 7: Back URL Integrita

### 7.1 Dashboard -> Vlastnici
- Dashboard (`/`) obsahuje odkaz `/vlastnici?back=/` ✅
- Dashboard obsahuje odkaz `/jednotky?back=/` ✅

### 7.2 Seznam -> Detail
- Vlastnici seznam: odkazy na detail obsahuji `?back=` s encoded URL seznamu ✅
  - Priklad: `/vlastnici/109?back=/vlastnici/%3Fq%3DNov%26sort%3Dname%26order%3Dasc...`
- Detail vlastnika: zobrazuje "Zpet" sipku ✅

### 7.3 Zpetna navigace
- Detail vlastnika (`/vlastnici/109?back=/vlastnici/`) -- "Zpet" link pritomen ✅
- Detail jednotky (`/jednotky/105?back=/jednotky/`) -- "Zpet" link pritomen ✅

### 7.4 Jednotky
- Stejny vzor jako vlastnici -- back URL retezec funguje ✅

---

## Faze 8: N+1 Detekce

### Analyza kodu

Kontrola `joinedload()` pouziti v klicovych routerech:

| Router | joinedload pouziti | Hodnoceni |
|--------|-------------------|-----------|
| `owners/_helpers.py` | `joinedload(Owner.units).joinedload(OwnerUnit.unit)` | ✅ OK |
| `owners/crud.py` | 8x joinedload pro detail, edit, seznam | ✅ OK |
| `units.py` | `joinedload(Unit.owners).joinedload(OwnerUnit.owner)` | ✅ OK |
| `voting/ballots.py` | 20+ joinedload pro ballot, owner, votes, items | ✅ OK |
| `voting/session.py` | Kompletni eager loading pro vsechny endpointy | ✅ OK |
| `tax/session.py` | Kompletni eager loading documents, distributions, owners | ✅ OK |
| `payments/statements.py` | joinedload pro unit, space, owner, allocations | ✅ OK |
| `payments/symbols.py` | joinedload pro unit, space | ✅ OK |
| `payments/settlement.py` | joinedload pro unit, owners, items | ✅ OK |
| `spaces/crud.py` | joinedload pro tenants, owner | ✅ OK |
| `tenants/crud.py` | joinedload pro owner, spaces | ✅ OK |
| `sync/session.py` | joinedload pro owner.units | ✅ OK |

**Zaver:** Vsechny klicove routery pouzivaji `joinedload()` pro relace zobrazene v tabulkach. Zadny zjevny N+1 problem nebyl nalezen.

---

## Doporuceni

### Nizka priorita (INFO)

1. **SQLAlchemy LegacyAPIWarning** -- `db.query(Model).get(id)` je oznacen jako legacy v SQLAlchemy 2.0. Zvazit migraci na `db.get(Model, id)` pri budoucim refactoringu. Dotcene soubory: `statements.py`, `payment_discrepancy.py`, testy.

2. **HTMX partial endpointy vracejici 422** -- Tri endpointy (`/kontrola-podilu/mapovani`, `/sprava/hromadne-upravy/hodnoty`, `/sprava/hromadne-upravy/zaznamy`) vraceji 422 pri primem pristupu. Toto je ocekavane chovani, ale lze zvazit graceful fallback (redirect na nadrazenou stranku).

3. **Tailwind CDN warning** -- Produkci se doporucuje build pipeline misto CDN. Neni urgentni pro interni nastroj.
