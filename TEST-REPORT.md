# SVJ Test Report -- 2026-03-19

## Souhrn

| Oblast | Stav | Detail |
|--------|------|--------|
| Pytest | OK | 23 passed, 0 failed, 2 warnings (DeprecationWarning) |
| Route coverage | OK | 33/36 rout OK (3 vyzaduji query parametry = ocekavane) |
| Smoke testy | OK | 9/9 stranek OK |
| Funkcni testy | OK | 5/5 testu OK |
| JS konzole | OK | 9/9 stranek bez neocekavanych chyb |
| Exporty | OK | 7/7 exportu OK |
| Back URL | OK | 4/4 retezcu OK |
| N+1 detekce | OK | joinedload() konzistentne pouzivan |

**Celkovy stav: OK -- PASS**

---

## Faze 1: Pytest

**Vysledek: 23 passed, 0 failed, 0 error, 0 skipped**

Vsechny testy prosly:
- `test_contact_import.py` -- 3 testy (preview invalid file, error dict, read-only mode)
- `test_email_service.py` -- 5 testu (name_normalized, diacritics, search)
- `test_import_mapping.py` -- 7 testu (auto-detect, validate mapping, build context)
- `test_smoke.py` -- 3 testy (app starts, owners package routes, dashboard loads)
- `test_voting_aggregation.py` -- 3 testy (basic, empty, null votes)

**Varovani (2x):** `DeprecationWarning: The 'name' is not the first parameter anymore` v `test_smoke.py` -- Starlette `TemplateResponse` API se zmenilo, doporucen novy format `TemplateResponse(request, name)`.

| # | Co | Severity | Detail | Doporuceni |
|---|-----|----------|--------|------------|
| 1 | DeprecationWarning TemplateResponse | INFO | Starlette ocekava `TemplateResponse(request, name)` misto `TemplateResponse(name, {"request": request})` | Aktualizovat volani TemplateResponse na novy format. Nizka priorita -- funkcne nema vliv |

---

## Faze 2: Route Coverage

**Vysledek: 33/36 rout OK, 3 routy vyzaduji povinne query parametry (ocekavane)**

Vsechny GET routy bez path parametru otestovany HTTP requestem:

| Status | Pocet | Routy |
|--------|-------|-------|
| 200 OK | 33 | Vsechny hlavni stranky |
| 422 (ocekavane) | 3 | `/kontrola-podilu/mapovani`, `/sprava/hromadne-upravy/hodnoty`, `/sprava/hromadne-upravy/zaznamy` |

Routy s 422 jsou HTMX partial endpointy vyzadujici povinne query parametry (`file_path`, `filename`, `pole`). Toto je ocekavane chovani -- nejsou urceny pro prime volani.

Celkem GET rout v aplikaci: 76 (37 bez path parametru, 39 s path parametry preskocenych).

---

## Faze 3: Playwright Smoke Testy

**Vysledek: 9/9 stranek OK**

| # | URL | Titul | Stav | Poznamka |
|---|-----|-------|------|----------|
| 1 | `/` | Prehled - SVJ Sprava | OK | Dashboard, 4 stat karty (447 vlastniku, 508 jednotek, 2 hlasovani, 2 rozeslani), tabulka aktivity |
| 2 | `/vlastnici` | Vlastnici - SVJ Sprava | OK | Tabulka s 447 vlastniky, search bar, filtracni bubliny |
| 3 | `/jednotky` | Jednotky - SVJ Sprava | OK | Tabulka s 508 jednotkami, search bar, filtracni bubliny |
| 4 | `/hlasovani` | Hlasovani per rollam - SVJ Sprava | OK | 2 hlasovani se stavovymi bublinami, wizard steppery, vysledkove tabulky |
| 5 | `/dane` | Hromadne rozeslani - SVJ Sprava | OK | 2 rozeslani kampane, stavove bubliny, wizard steppery |
| 6 | `/synchronizace` | Kontroly - SVJ Sprava | OK | 2 taby (Kontrola vlastniku, Kontrola podilu), historie kontrol, upload formular |
| 7 | `/sprava` | Administrace - SVJ Sprava | OK | 7 admin karet (Info SVJ, Ciselniky, Zalohy, Export, Hromadne upravy, Duplicity, Smazat data) |
| 8 | `/nastaveni` | Nastaveni - SVJ Sprava | OK | Formulare a sekce |
| 9 | `/vlastnici/import` | Import z Excelu - SVJ Sprava | OK | Import wizard (vlastniku + kontaktu), historie importu |

---

## Faze 4: Funkcni Testy

**Vysledek: 5/5 testu OK**

| # | Test | Stav | Detail |
|---|------|------|--------|
| 1 | Hledani na `/vlastnici` | OK | HTMX search "Koci" -- vyfiltrovano na Koci Martin. URL aktualizovana na `?q=Ko%C4%8D%C3%AD&sort=name&order=asc` |
| 2 | Hledani na `/jednotky` | OK | HTMX search "Koci" -- vyfiltrovano 9 jednotek vlastnenych Kocim. URL aktualizovana |
| 3 | Filtry/bubliny na `/vlastnici` | OK | Klik na "Fyzicka os." -- URL zmenena na `?typ=physical`, tabulka vyfiltrovana |
| 4 | Razeni sloupcu na `/vlastnici` | OK | Razeni podle jmena sestupne -- prvni radek "Zverina Bohumir" (Z) |
| 5 | Dark mode | OK | Prepinac funguje, trida `dark` na `<html>` elementu se pridava/odebira |

Poznamka k tabum na `/synchronizace`: Prepnuti "Kontrola vlastniku" -> "Kontrola podilu" funguje, zobrazeni obsahu se aktualizuje.

---

## Faze 5: JS Konzole -- Chyby

**Vysledek: 9/9 stranek bez neocekavanych JS chyb**

Na vsech 9 strankach z Faze 3 byla zkontrolovana JS konzole. Jedina chyba na kazde strance:

- `ReferenceError: tailwind is not defined` -- **Known error** (CDN inicializace Tailwind). Na vsech strankach, funkcne nema vliv.
- `Failed to load resource: 404 (Not Found) favicon.ico` -- Pouze na dashboardu. **Known error**, nema vliv na funkcnost.

**Zadne neocekavane JS chyby nalezeny.**

---

## Faze 6: Export Validace

**Vysledek: 7/7 exportu OK**

| # | URL | HTTP | Content-Type | Filename | Velikost |
|---|-----|------|-------------|----------|----------|
| 1 | `/vlastnici/exportovat/xlsx` | 200 | application/vnd.openxmlformats-officedocument.spreadsheetml.sheet | vlastnici_vsichni_20260319.xlsx | 44 621 B |
| 2 | `/vlastnici/exportovat/csv` | 200 | text/csv; charset=utf-8 | vlastnici_vsichni_20260319.csv | 75 255 B |
| 3 | `/jednotky/exportovat/xlsx` | 200 | application/vnd.openxmlformats-officedocument.spreadsheetml.sheet | jednotky_vsechny_20260319.xlsx | 36 572 B |
| 4 | `/jednotky/exportovat/csv` | 200 | text/csv; charset=utf-8 | jednotky_vsechny_20260319.csv | 34 056 B |
| 5 | `/hlasovani/2/exportovat` | 200 | application/vnd.openxmlformats-officedocument.spreadsheetml.sheet | hlasovani_2_vsechny_20260319.xlsx | 19 934 B |
| 6 | `/hlasovani/1/exportovat` | 200 | application/vnd.openxmlformats-officedocument.spreadsheetml.sheet | hlasovani_1_vsechny_20260319.xlsx | 18 105 B |
| 7 | `/dane/1/exportovat` | 200 | application/vnd.openxmlformats-officedocument.spreadsheetml.sheet | rozeslani_1_20260319_054630.xlsx | 5 857 B |

Vsechny exporty:
- Vraceni HTTP 200
- Spravny Content-Type (xlsx/csv)
- Filename bez diakritiky, obsahuje datum YYYYMMDD
- Neprazdne response body (tisice bajtu)

---

## Faze 7: Back URL Integrita

**Vysledek: 4/4 navigacnich retezcu OK**

### 7.1 Dashboard -> Vlastnici
- Karta Vlastnici na dashboardu: link `/vlastnici?back=/` -- **OK**
- Stranka vlastniku zobrazuje sipku zpet "Zpet na prehled" s linkem na `/` -- **OK**

### 7.2 Seznam Vlastnici -> Detail Vlastnika
- Odkaz na detail vlastnika obsahuje `?back=/vlastnici/%3Fback%3D/%23owner-429` -- **OK**
- Detail vlastnika zobrazuje sipku zpet "Zpet na seznam vlastniku" -- **OK**

### 7.3 Zpetna navigace
- Klik na sipku zpet vraci na seznam s puvodnimi parametry + hash pro scroll pozici -- **OK**

### 7.4 Dashboard -> Jednotky -> Detail Jednotky
- Karta Jednotky na dashboardu: link `/jednotky?back=/` -- **OK**
- Detail jednotky 9 zobrazuje sipku zpet s odkazem `/jednotky/?back=/#unit-23` -- **OK**
- Detail jednotky zobrazuje klikaci vlastniky (Koci Martin, Kocova Jana) s korektnimi back URL -- **OK**

---

## Faze 8: N+1 Detekce

**Vysledek: OK -- joinedload() konzistentne pouzivan ve vsech klicovych routerech**

Analyza kodu routeru pro pouziti eager loadingu:

| Router | joinedload() pouziti | Hodnoceni |
|--------|---------------------|-----------|
| `owners/_helpers.py` | `joinedload(Owner.units).joinedload(OwnerUnit.unit)` | OK |
| `owners/crud.py` | 7x joinedload pro Owner.units/OwnerUnit.unit | OK |
| `units.py` | `joinedload(Unit.owners).joinedload(OwnerUnit.owner)` | OK |
| `voting/session.py` | Komplexni eager loading Voting->Ballots->Owner->Units | OK |
| `voting/ballots.py` | Komplexni eager loading Ballot->Owner->Units, Ballot->Votes | OK |
| `voting/import_votes.py` | Full eager loading pro vsechny relace | OK |
| `tax/session.py` | `joinedload(TaxDocument.distributions).joinedload(TaxDistribution.owner)` | OK |
| `tax/sending.py` | 8x joinedload pro TaxDocument/TaxDistribution/Owner | OK |
| `dashboard.py` | `joinedload(Voting.ballots).joinedload(Ballot.votes)` | OK |
| `administration.py` | joinedload pro SvjInfo, Unit.owners, Owner.units | OK |
| `sync.py` | `joinedload(Owner.units)` | OK |

**Zadne N+1 problemy nalezeny.** Vsechny routery ktere zobrazuji relace v sablonach pouzivaji korektni eager loading.

---

## Doporuceni

### Nizka priorita (INFO)

1. **DeprecationWarning v TemplateResponse** -- Starlette zmenilo API pro `TemplateResponse`. Aktualni format `TemplateResponse(name, {"request": request})` bude v budoucnu deprecated. Doporuceno aktualizovat na `TemplateResponse(request, name)`. Cas: ~30 min (mechanicka zmena ve vsech routerech).

2. **Chybejici favicon.ico** -- Dashboard vraci 404 pro favicon.ico. Doporuceno pridat favicon soubor do `/static/` nebo pridat `<link rel="icon">` tag. Cas: ~5 min.

3. **3 HTMX partial routy vraceni 422 bez query parametru** -- Toto je ocekavane chovani, ale mohlo by byt vylepseno pridanim defaultnich hodnot pro query parametry. Nizka priorita.

### Pozitivni nalezy

- Vsechny klicove stranky se renderuji korektne
- HTMX search funguje spravne vcetne diakritiky (Koci -> Koci Martin)
- Filtrace, razeni, taby a dark mode funguje bez problemu
- Vsechny exporty (7x) vraceni spravne formatovane soubory
- Back URL retezec je konzistentni a propaguje se spravne (vcetne hash pro scroll pozici)
- Zadne neocekavane JS chyby
- Konzistentni pouziti joinedload() pro prevenci N+1 problemu
- 23 pytest testu pokryva klicove sluzby (import, email, mapping, voting aggregation, smoke)

---

## Statistiky

- **Cas testovani**: ~15 min
- **Testovanych stranek**: 9 (Playwright) + 36 (HTTP) = 45
- **Testovanych exportu**: 7
- **Pytest testu**: 23
- **GET rout v aplikaci**: 76 (37 testovanych primo, 39 s path parametry)
- **Nalezenych problemu**: 0 CRITICAL, 0 WARNING, 3 INFO
