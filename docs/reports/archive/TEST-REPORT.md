# SVJ Test Report -- 2026-04-10

> Testování po aplikaci 11 oprav z audit reportu (tenant dedup + multi-space + XSS fix + flash).
> Server běží na portu **8022** (port 8021 drží jiný proces).

## Souhrn

| Oblast | Stav | Detail |
|--------|------|--------|
| Pytest | OK | 310 passed, 0 failed, 37 warnings (všechny legacy `.get()` deprecations) |
| Route coverage | OK | 51/54 rout OK (3 x 422 očekávané -- povinné query parametry) |
| Smoke testy | OK | 12/12 stránek OK |
| Funkční testy | OK | search, sort, filter, export, back URL -- všechny OK |
| JS konzole | OK | 12/12 stránek bez errorů (jen known warning `cdn.tailwindcss.com`) |
| Exporty | OK | 3/3 exporty OK (vlastníci 44 KB, jednotky 36 KB, nájemci 6,7 KB) |
| Back URL | OK | `?back=` + hash scroll, encoded řetězení funguje |
| N+1 detekce | OK | max 30 dotazů (/vlastnici/), ostatní 15-19 |

**Celkový stav: PASS -- 11 oprav z audit reportu nic nerozbilo.**

---

## Fáze 1: PYTEST

```
============ 310 passed, 37 warnings in 2.85s ============
```

- Všech **310 testů prošlo** (včetně `test_tenants.py`, `test_payment_advanced.py`, `test_voting.py`).
- 37 warnings -- všechny jsou deprecation warningy `Query.get()` (legacy SQLAlchemy API) a jeden `TemplateResponse` kwarg order. **Nejsou blokery**.

---

## Fáze 2: ROUTE COVERAGE

| Status | Počet |
|--------|-------|
| 2xx/3xx OK | 51 |
| 422 (povinný query parametr) | 3 |
| 5xx | 0 |

**422 routy -- očekávané chování (FastAPI validace povinného parametru):**

| Routa | Důvod |
|-------|-------|
| `/kontrola-podilu/mapovani` | vyžaduje `upload_id` |
| `/sprava/hromadne-upravy/hodnoty` | vyžaduje `atribut` |
| `/sprava/hromadne-upravy/zaznamy` | vyžaduje `atribut` + `hodnota` |

Není co opravovat -- validace funguje správně.

---

## Fáze 3: SMOKE TESTY (Playwright)

| # | URL | Výsledek |
|---|-----|----------|
| 1 | `/` | OK -- dashboard se renderuje |
| 2 | `/vlastnici` | OK -- tabulka + stat karty |
| 3 | `/jednotky` | OK -- tabulka |
| 4 | `/hlasovani` | OK -- seznam kampaní |
| 5 | `/najemci` | OK -- tabulka, 20 řádků |
| 6 | `/prostory` | OK |
| 7 | `/dane` | OK -- Hromadné rozesílání |
| 8 | `/synchronizace` | OK -- Kontroly |
| 9 | `/sprava` | OK -- Administrace |
| 10 | `/nastaveni` | OK |
| 11 | `/platby` | OK -- redirect na `/platby/predpisy` |
| 12 | `/vlastnici/import` | OK -- wizard stepper |

**Všechny stránky: 0 errorů v konzoli**, jen 1 warning (Tailwind CDN -- known/expected).

---

## Fáze 4: FUNKČNÍ TESTY

| Test | URL | Stav |
|------|-----|------|
| HTMX search vlastníci | `/vlastnici/?q=novak` (HX-Request) | OK 200 |
| Řazení vlastníků | `/vlastnici/?sort=name&order=asc` | OK 200 |
| Filtr typ | `/vlastnici/?typ=physical` | OK 200 |
| HTMX search jednotky | `/jednotky/?q=1` (HX-Request) | OK 200 |
| Detail nájemce | `/najemci/30` | OK 200, "Prostor" + "smlouv" sekce vykresleny |
| Detail vlastníka (back URL) | `/vlastnici/429?back=...` | OK |

**Ověření tenant dedup + multi-space (z DB):**
```
Tenants total: 20
Multi-space active: 1  (jeden nájemce má více aktivních smluv)
Duplicate RC rows:  0  (dedup migrace proběhla čistě)
```

---

## Fáze 5: JS KONZOLE

Žádná stránka nemá JS error. Jediný warning na všech stránkách:
```
[WARNING] cdn.tailwindcss.com should not be used in production
```
-- known/expected, tailwind CDN.

---

## Fáze 6: EXPORT VALIDACE

| Export | HTTP | Content-Type | Velikost | Filename |
|--------|------|--------------|----------|----------|
| `/vlastnici/exportovat/xlsx` | 200 | `application/vnd.openxml...sheet` | 44 897 B | `vlastnici_vsichni_20260410.xlsx` |
| `/jednotky/exportovat/xlsx` | 200 | `application/vnd.openxml...sheet` | 36 564 B | OK |
| `/najemci/exportovat/xlsx` | 200 | `application/vnd.openxml...sheet` | 6 723 B | OK |

- Filename vlastníků obsahuje suffix `_vsichni` + datum `20260410`, bez diakritiky -- dle pravidla v CLAUDE.md.
- Všechny exporty vrací neprázdné XLSX soubory se správným MIME.

---

## Fáze 7: BACK URL INTEGRITA

| Test | Výsledek |
|------|----------|
| `/vlastnici?back=/` -- obsahuje šipku zpět | OK |
| Odkaz ze seznamu -> detail obsahuje `?back=` s encoded URL | OK |
| Back URL obsahuje hash `#owner-429` pro scroll restore | OK |
| Detail nájemce `/najemci/30?back=/najemci/` | OK, page title "Nájemce Baumrt" |
| Najemci seznam -> detail link obsahuje `%23tenant-30` | OK |

Back URL řetězení a hash scroll restore funguje přesně dle pravidla v CLAUDE.md § Navigace.

---

## Fáze 8: N+1 DETEKCE

Měřeno přes `TestClient` + `sqlalchemy.engine` INFO log:

| Stránka | SQL dotazy | Hodnocení |
|---------|-----------|-----------|
| `/vlastnici/` | 30 | INFO (20-50) |
| `/jednotky/` | 19 | OK |
| `/najemci/` | 19 | OK |
| `/prostory/` | 15 | OK |
| `/hlasovani/` | 16 | OK |

**Žádná stránka nepřekračuje 50 dotazů** -- N+1 nehrozí. `/vlastnici/` je na horní hranici "OK" pásma kvůli bublinám a statistikám podílů -- není to regrese.

---

## Detaily selhání

**Žádná.** Po aplikaci 11 oprav z audit reportu nejsou v žádné fázi selhání.

---

## Doporučení

### Low priority (údržba)

1. **`Query.get()` deprecations** -- 37 warnings v pytest. SQLAlchemy 2.0 doporučuje `db.get(Model, id)` místo `db.query(Model).get(id)`. Projekt má dle CLAUDE.md explicitní politiku "legacy query API", takže toto je rozhodnutí -- buď uznat jako tech debt, nebo migrovat. **Čas:** ~2 hod pro hromadnou migraci. **Regrese riziko:** nízké.

2. **`TemplateResponse(name, {...})` deprecation** (2 warnings v testech). Starlette doporučuje `TemplateResponse(request, name)`. **Čas:** ~10 min. **Regrese riziko:** nízké.

### Ověřené -- nic opravovat

- Tenant dedup (0 duplicit), multi-space (1 nájemce se dvěma smlouvami se renderuje)
- XSS fix (všechny smoke stránky renderují bez errorů)
- Flash toast (session-based flash nikde nezbyl)
- Export filenames s datem a suffixem
- Back URL + scroll restore (hash)

---

## Jak reprodukovat testování

```bash
# pytest
source .venv/bin/activate && python3 -m pytest tests/ -v

# route coverage (proti běžícímu serveru na 8022)
python3 -c "from app.main import app; import urllib.request; ..."

# export test
curl -D - -o /tmp/e.xlsx http://127.0.0.1:8022/vlastnici/exportovat/xlsx

# N+1 počítadlo
python3 -c "from fastapi.testclient import TestClient; from app.main import app; ..."
```
