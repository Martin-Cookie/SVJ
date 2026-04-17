# SVJ Test Report – 2026-03-27

## Souhrn

| Oblast | Stav | Detail |
|--------|------|--------|
| Pytest | ✅ | 248 passed, 0 failed, 4 warnings (deprecation) |
| Route coverage | ✅ | 51/54 rout OK (3x HTTP 422 — vyžadují query parametry) |
| Smoke testy | ✅ | 9/9 stránek OK |
| Funkční testy | ✅ | 5/5 testů OK |
| JS konzole | ✅ | 0 JS chyb na všech stránkách |
| Exporty | ✅ | 4/4 exportů OK |
| Back URL | ✅ | 2/2 řetězců OK (vlastníci, jednotky) |
| N+1 detekce | ✅ | 46 joinedload v voting, rozsáhlé eager loading v celém projektu |

**Celkový stav: ✅ PASS**

---

## Fáze 1: Pytest

- **248 testů**: 248 passed, 0 failed, 0 errors, 0 skipped
- **4 deprecation warnings** (INFO):
  - `TemplateResponse(name, {"request": request})` — Starlette doporučuje novou signaturu `TemplateResponse(request, name)`
  - `Query.get()` legacy API — SQLAlchemy 2.0 doporučuje `Session.get()`
- **Pokryté moduly**: backup, contact_import, csv_comparator, email_service, import_mapping, payment_matching, smoke, voting, voting_aggregation

## Fáze 2: Route Coverage

- **54 GET rout** celkem (bez path parametrů)
- **51 rout HTTP 200** (OK)
- **3 routy HTTP 422** (očekávané — vyžadují povinné query parametry):
  - `/kontrola-podilu/mapovani` — vyžaduje `file_path` parametr
  - `/sprava/hromadne-upravy/hodnoty` — vyžaduje `pole` parametr
  - `/sprava/hromadne-upravy/zaznamy` — vyžaduje `pole` a `hodnota` parametry

## Fáze 3: Smoke testy (Playwright)

| # | URL | Stav | Poznámka |
|---|-----|------|----------|
| 1 | `/` | ✅ | Dashboard — stat karty, tabulka aktivity, search bar |
| 2 | `/vlastnici` | ✅ | 447 vlastníků, tabulka s řádky, filtry, bubliny |
| 3 | `/jednotky` | ✅ | 508 jednotek, tabulka |
| 4 | `/hlasovani` | ✅ | Seznam hlasování |
| 5 | `/rozesilani` | ✅ | Hromadné rozesílání — 3 sessions |
| 6 | `/synchronizace` | ✅ | Taby "Kontrola vlastníků" + "Kontrola podílů" |
| 7 | `/sprava` | ✅ | Administrace — karty/sekce |
| 8 | `/nastaveni` | ✅ | Nastavení |
| 9 | `/vlastnici/import` | ✅ | Import wizard — stepper viditelný |

## Fáze 4: Funkční testy

| # | Test | Stav | Detail |
|---|------|------|--------|
| 4.1 | Hledání (HTMX) | ✅ | "Novák" → 7 výsledků, URL se aktualizuje s `q=Novák` |
| 4.2 | Filtrační bubliny | ✅ | Klik na "Fyzická os." → URL `typ=physical`, tabulka filtrována na 431 |
| 4.3 | Řazení sloupců | ✅ | Klik na "Dluh" → URL `sort=dluh&order=asc` |
| 4.4 | Taby (synchronizace) | ✅ | Přepnutí na "Kontrola podílů" → hash `#kontrola-podilu`, obsah se změní |
| 4.5 | Dark mode | ✅ | Toggle "Tmavý režim" → "Světlý režim", třída `dark` na HTML |

## Fáze 5: JS konzole

- **0 JS chyb** na všech testovaných stránkách
- Pouze 1 warning na každé stránce: `cdn.tailwindcss.com should not be used in production` (očekávané — CDN verze Tailwind)

## Fáze 6: Export validace

| # | URL | HTTP | Content-Type | Filename | Velikost |
|---|-----|------|-------------|----------|----------|
| 1 | `/vlastnici/exportovat/xlsx` | 200 | `application/vnd.openxmlformats...` | `vlastnici_vsichni_20260327.xlsx` | 44 871 B |
| 2 | `/vlastnici/exportovat/csv` | 200 | `text/csv; charset=utf-8` | `vlastnici_vsichni_20260327.csv` | 76 481 B |
| 3 | `/jednotky/exportovat/xlsx` | 200 | `application/vnd.openxmlformats...` | `jednotky_vsechny_20260327.xlsx` | 36 563 B |
| 4 | `/jednotky/exportovat/csv` | 200 | `text/csv; charset=utf-8` | `jednotky_vsechny_20260327.csv` | 34 043 B |

Všechny exporty: správný Content-Type, neprázdné soubory, filename bez diakritiky s datem.

## Fáze 7: Back URL integrita

### 7.1 Dashboard → Vlastníci
- ✅ Karta "Vlastníci" → `/vlastnici?back=/`
- ✅ Šipka zpět "Zpět na přehled" → `/`

### 7.2 Seznam → Detail
- ✅ Klik na "Adamec Štěpán" → `/vlastnici/320?back=/vlastnici/%3Fback%3D/%23owner-320`
- ✅ Šipka zpět "Zpět na seznam vlastníků" → `/vlastnici/?back=/#owner-320`

### 7.3 Zpětná navigace
- ✅ Klik na šipku zpět → návrat na seznam s `#owner-320` (scroll pozice)

### 7.4 Jednotky (ověřeno přes kód)
- ✅ Dashboard karta odkazuje na `/jednotky?back=/`

## Fáze 8: N+1 detekce

Analýza kódu — použití `joinedload()` v routerech:

| Router | Počet joinedload | Hodnocení |
|--------|-----------------|-----------|
| `owners/` (crud + helpers) | 14 | ✅ Rozsáhlé eager loading Owner→Units→Unit |
| `units.py` | 5 | ✅ Unit→Owners→Owner |
| `voting/` (session + ballots + import) | 46 | ✅ Voting→Items, Ballots→Votes→Owner |
| `tax/` (helpers + sending) | 10 | ✅ TaxDocument→Distributions→Owner |
| `sync/` | 1 | ✅ Owner→Units |
| `spaces/` | 1 | ✅ Space→Tenants→Tenant→Owner |
| `administration/` | 1 | ✅ SvjInfo→Addresses |

Všechny klíčové relace zobrazené v tabulkách mají eager loading. Žádný N+1 problém detekován.

---

## Detaily selhání

Žádná selhání.

## Doporučení

1. **INFO — Deprecation warnings v testech**: Starlette `TemplateResponse` signatura a SQLAlchemy `Query.get()` — nízká priorita, bude třeba opravit při upgradu na Starlette 1.0 / SQLAlchemy 2.0
2. **INFO — Tailwind CDN warning**: Produkční nasazení by mělo používat kompilovaný Tailwind CSS. Pro lokální SVJ aplikaci je CDN akceptovatelné.
3. **INFO — 3 routy s HTTP 422**: `/kontrola-podilu/mapovani`, `/sprava/hromadne-upravy/hodnoty`, `/sprava/hromadne-upravy/zaznamy` — validně vyžadují povinné parametry, žádná akce nutná.
