# SVJ Audit Report — 2026-04-05

> Scope: celý projekt, se zaměřením na nové soubory od posledního auditu (2026-03-27)
>
> Nové commity (20 commitů v branchi `platebni-upozorneni`, merge do `main`):
> - feat: detekce nesrovnalostí v platbách, preview, checkboxy, dávkové odesílání
> - feat: sdílený progress bar `_send_progress.html` + `_send_progress_inner.html`
> - feat: scroll restore mechanismus (sessionStorage + MutationObserver)
> - fix: SJM párování, HTMX boost scroll, kompaktní layout

## Stav předchozího auditu (2026-03-27)

Z 11 nálezů předchozího auditu:

| # | Nález | Stav |
|---|-------|------|
| N1 | SMTP SSL logika duplikována v settings_page.py | **OPRAVENO** — `_create_smtp()` se nyní volá i v settings_page.py |
| N2 | Logger placement v email_service.py | **OPRAVENO** |
| N3 | Return type annotation `_create_smtp` | **OPRAVENO** |
| N4 | Temp form nepřenáší hidden fields při HTMX polling | **OPRAVENO** — app.js:228-234 nyní klonuje hidden fieldy |
| N5 | `datetime.utcnow` deprecated v 7 modelech | **OPRAVENO** — všech 44 výskytů migrováno na `utcnow()` |
| N6 | `datetime.utcnow()` v dashboard.py | **OPRAVENO** |
| N7 | Zbytkový Playwright log | **OPRAVENO** — adresář čistý |
| N8 | test_prostory.xlsx v kořeni | **OPRAVENO** — soubor odstraněn |
| N9 | Hardcoded Dropbox cesta | Přetrvává (LOW) — `pripravit_prenos.sh:22` |
| N10 | Chybějící sqlite3 kontrola | Přetrvává (LOW) — `pripravit_prenos.sh:84` |
| N11 | WHEEL_COUNT nedefinovaná | Přetrvává (LOW) — `spustit.command:137` |

**Skóre:** 8 z 11 opraveno (73 %). Zbývající 3 jsou LOW severity v deploy skriptech.

Z konsolidovaného ORCHESTRATOR reportu (2026-03-27):
- **A2** (engine.dispose) — **OPRAVENO** — nyní ve všech 4 restore endpointech v backups.py
- UX nálezy (U1–U31) — většina přetrvává, ale nejsou předmětem tohoto kódového auditu

---

## Souhrn nových nálezů

- **CRITICAL**: 0
- **HIGH**: 2
- **MEDIUM**: 6
- **LOW**: 5

## Souhrnná tabulka

| # | Oblast | Soubor | Severity | Problém | Čas | Rozhodnutí |
|---|--------|--------|----------|---------|-----|------------|
| 1 | Kód | `payments/_helpers.py:86-215` | HIGH | `_count_debtors_fast` a `compute_debt_map` — 90% duplicitní kód (130 řádků) | ~30 min | 🔧 |
| 2 | Kód | `payments/statements.py` (1653 řádků) | HIGH | Soubor překračuje 1500 řádků — nesrovnalosti by měly být samostatný sub-modul | ~45 min | 🔧 |
| 3 | Kód | `payment_discrepancy.py:200-258` | MEDIUM | Unit/space detekční logika duplikována (VS + částka kontrola) | ~20 min | 🔧 |
| 4 | Bezpečnost | `statements.py:1508` | MEDIUM | `int(x) for x in selected_ids` bez try/except — ValueError při manipulaci | ~5 min | 🔧 |
| 5 | Kód | `statements.py:1085-1119` vs `1165-1246` | MEDIUM | Trojí duplikace render email template logiky (preview, batch, test) | ~30 min | 🔧 |
| 6 | Výkon | `_helpers.py:12` | MEDIUM | In-memory `_discrepancy_progress` dict nikdy nečištěn při opuštění stránky | ~15 min | 🔧 |
| 7 | Bezpečnost | `nesrovnalosti_preview.html:275` | MEDIUM | `{{ log.body_preview\|safe }}` — stored HTML renderován bez sanitizace | ~10 min | ❓ |
| 8 | Testy | `tests/` | MEDIUM | Žádné testy pro `payment_discrepancy.py` (nový service, 390 řádků) | ~2 hod | 🔧 |
| 9 | Kód | `payment_discrepancy.py:386` vs `data_export.py:99` | LOW | Dvě různé `_fmt()` funkce se stejným názvem ale jinou logikou | ~5 min | 🔧 |
| 10 | Kód | `statements.py:1198-1202` | LOW | 5s úvodní delay implementován jako busy-wait loop (10× sleep 0.5s) | ~5 min | 🔧 |
| 11 | Kód | `_helpers.py:14-18` | LOW | Importy modelů uprostřed souboru (po `_discrepancy_progress` definici) | ~2 min | 🔧 |
| 12 | Git | `pripravit_prenos.sh:22` | LOW | Hardcoded Dropbox cesta (přetrvává z minulého auditu) | ~5 min | ❓ |
| 13 | Git | `spustit.command:137` | LOW | WHEEL_COUNT nedefinovaná (přetrvává z minulého auditu) | ~2 min | 🔧 |

Legenda: 🔧 = jen opravit, ❓ = potřeba rozhodnutí uživatele (více variant)

---

## Detailní nálezy

### 1. Kódová kvalita

#### N1 — HIGH: Duplikace `_count_debtors_fast` a `compute_debt_map` (130 řádků)

- **Co a kde:** `app/routers/payments/_helpers.py:86-151` (`_count_debtors_fast`) a `_helpers.py:154-215` (`compute_debt_map`) obsahují prakticky identický kód. Oba:
  1. Načtou PrescriptionYear a předpisy
  2. Spočítají měsíce s daty
  3. Sečtou zaplacené částky per unit
  4. Načtou opening balances
  5. Porovnají expected vs paid

  Jediný rozdíl: `_count_debtors_fast` vrací `int` (count), `compute_debt_map` vrací `dict[int, float]` (dluh per unit).

- **Řešení:** Extrahovat sdílenou funkci `_compute_debt_data(db, year)` → `dict[int, float]`, ze které obě funkce čerpají:
  ```python
  def _compute_debt_data(db, year):
      """Vrátí {unit_id: dluh} pro všechny jednotky."""
      # ... sdílená logika ...

  def _count_debtors_fast(db, year):
      return sum(1 for v in _compute_debt_data(db, year).values() if v > 0)

  def compute_debt_map(db, year):
      return {k: v for k, v in _compute_debt_data(db, year).items() if v > 0}
  ```
- **Náročnost:** nízká, ~30 min
- **Závislosti:** žádné
- **Regrese riziko:** nízké — obě funkce budou volat stejný základ
- **Jak otestovat:** Dashboard → ověřit badge dlužníků. Detail vlastníka → ověřit dluh na jednotce. Jednotky → ověřit dluh sloupec.

---

#### N2 — HIGH: `statements.py` má 1653 řádků — kandidát na rozdělení

- **Co a kde:** `app/routers/payments/statements.py` kombinuje:
  - Import CSV + seznam výpisů (řádky 1-380)
  - Detail výpisu + párování (řádky 383-1065)
  - Nesrovnalosti — preview, settings, test, batch send, progress, pause/resume/cancel (řádky 1068-1654)

  Nesrovnalostní část (586 řádků) je logicky samostatný modul.

- **Řešení:** Vytvořit `app/routers/payments/discrepancies.py` s endpointy `/nesrovnalosti/*`. V `__init__.py` přidat `include_router(discrepancies.router)`.
- **Varianty:**
  - A) Celá nesrovnalostní část → `discrepancies.py` (~586 řádků, čistý řez)
  - B) Jen background sending → `discrepancy_sending.py` (~350 řádků)
  - Doporučení: varianta A
- **Náročnost:** střední, ~45 min
- **Závislosti:** žádné
- **Regrese riziko:** nízké — mechanický přesun, URL se nemění
- **Jak otestovat:** Všechny `/platby/vypisy/{id}/nesrovnalosti/*` endpointy musí fungovat stejně.

---

#### N3 — MEDIUM: Duplikace unit/space detekce v `payment_discrepancy.py`

- **Co a kde:** `app/services/payment_discrepancy.py:200-229` (unit blok) a `231-258` (space blok) obsahují identickou logiku pro:
  - Kontrolu VS (`if expected_vs and payment.vs and payment.vs != expected_vs`)
  - Kontrolu částky s tolerancí násobků (10 řádků)
  - Přidání do `alloc_details`

- **Řešení:** Extrahovat helper `_check_target(payment, expected, expected_vs, entity_label, entity_type, disc_types, alloc_details, alloc_amount)` volaný pro unit i space.
- **Náročnost:** nízká, ~20 min
- **Závislosti:** žádné
- **Regrese riziko:** nízké
- **Jak otestovat:** Nesrovnalosti preview → ověřit detekci wrong_vs i wrong_amount pro jednotky i prostory.

---

#### N5 — MEDIUM: Trojí duplikace render email template logiky

- **Co a kde:** V `statements.py` se na 3 místech opakuje stejný vzor:
  1. `_discrepancy_base_ctx` (řádky 1115-1119) — pro náhledy
  2. `_send_discrepancy_emails_batch` (řádky 1243-1246) — pro odeslání
  3. `discrepancy_test_email` (řádky 1445-1448) — pro testovací email

  Každé místo: načte template, svj, build_email_context, render_email_template, `.replace("\n", "<br>")`.

- **Řešení:** Extrahovat helper `_render_discrepancy_email(template, disc, svj_name, month_name, year) -> (subject, body_html)` volaný ze všech 3 míst.
- **Náročnost:** nízká, ~30 min
- **Závislosti:** závisí na N2 (pokud se soubor rozděluje, helper patří do sdíleného modulu)
- **Regrese riziko:** nízké
- **Jak otestovat:** Náhled emailu v preview, testovací email, skutečné odeslání — všechny musí generovat stejný obsah.

---

#### N9 — LOW: Dvě různé `_fmt()` funkce

- **Co a kde:** `payment_discrepancy.py:386` formátuje čísla s mezerovým oddělovačem tisíců (`f"{val:,.0f}".replace(",", " ")`), `data_export.py:99` formátuje datetime a stringy. Obě se jmenují `_fmt` ale dělají něco jiného.
- **Řešení:** Přejmenovat jednu — např. `_fmt_number()` v payment_discrepancy.py, nebo použít `fmt_num()` z `app/utils.py` (registrován jako Jinja2 filtr).
- **Náročnost:** nízká, ~5 min
- **Regrese riziko:** nízké

---

#### N10 — LOW: Busy-wait loop pro úvodní delay

- **Co a kde:** `statements.py:1198-1202` — 5s úvodní prodleva implementována jako:
  ```python
  for _ in range(10):
      with _discrepancy_lock:
          if _discrepancy_progress[statement_id].get("done"):
              return
      time.sleep(0.5)
  ```
  Funkčně správné, ale zbytečně zatěžuje lock 10× za 5 sekund.

- **Řešení:** Přepsat na jednoduchý loop s delším sleep (např. 2× `time.sleep(2.5)` s check).
- **Náročnost:** nízká, ~5 min
- **Regrese riziko:** nízké

---

#### N11 — LOW: Importy uprostřed souboru

- **Co a kde:** `_helpers.py:12-13` definuje `_discrepancy_progress` a `_discrepancy_lock`, poté na řádcích 14-18 importuje modely. Standardní konvence je importy na začátku.
- **Řešení:** Přesunout `_discrepancy_progress` a `_discrepancy_lock` za importy.
- **Náročnost:** nízká, ~2 min
- **Regrese riziko:** nízké

---

### 2. Bezpečnost

#### N4 — MEDIUM: Chybějící validace `selected_ids`

- **Co a kde:** `statements.py:1508` — `selected_set = set(int(x) for x in selected_ids)`. Pokud útočník pošle non-numeric hodnotu v `selected_ids`, server vrátí 500 (ValueError).
- **Řešení:**
  ```python
  try:
      selected_set = set(int(x) for x in selected_ids if x.strip().isdigit())
  except (ValueError, TypeError):
      return RedirectResponse(...)
  ```
- **Náročnost:** nízká, ~5 min
- **Závislosti:** žádné
- **Regrese riziko:** nízké
- **Jak otestovat:** POST na `/nesrovnalosti/odeslat` s `selected_ids=abc` — měl by vrátit redirect, ne 500.

---

#### N7 — MEDIUM: `|safe` na stored HTML body_preview

- **Co a kde:** `nesrovnalosti_preview.html:275` renderuje `{{ log.body_preview|safe }}`. `body_preview` je uložen v DB jako prvních 500 znaků `body_html` (email_service.py:92). Obsah pochází z `render_email_template()` — Jinja2 rendering user-editable šablony.

  V aktuálním stavu je riziko nízké, protože:
  1. Emailové šablony edituje pouze admin
  2. Aplikace nemá autentizaci (single-user)
  3. Kontext (jméno, VS, částka) pochází z DB, ne od externího uživatele

  Ale po přidání autentizace/rolí by to bylo problém.

- **Řešení:**
  - A) Ukládat `body_preview` jako plain text (strip HTML tagů při ukládání)
  - B) Použít `bleach` nebo vlastní sanitizaci při renderování
  - C) Ponechat `|safe` s komentářem "// SECURITY: obsah pochází z admin-only šablon"
  - Doporučení: varianta A (nejčistší)
- **Náročnost:** nízká, ~10 min
- **Regrese riziko:** nízké — preview se zobrazí jako plain text místo HTML
- **Jak otestovat:** Nastavení → Email log → ověřit zobrazení body preview.

---

#### Bezpečnost — pozitivní nálezy

- **SQL injection:** Žádné f-stringy v SQL dotazech (jeden výskyt v `backup_service.py:367` používá hardcoded seznam tabulek, komentář potvrzuje)
- **XSS:** Jinja2 auto-escaping aktivní, `|safe` použit pouze na server-side SVG ikony a body_preview (viz N7)
- **File upload:** Všechny uploady validovány přes centralizovaný `validate_upload()` s `UPLOAD_LIMITS`
- **Path traversal:** `is_safe_path()` kontrola na místech kde se přijímá cesta od uživatele
- **SMTP heslo:** V `.env` souboru, který je v `.gitignore`
- **CSRF:** Není implementováno (žádný CSRF middleware), ale aplikace je single-user bez autentizace — akceptovatelné v aktuálním stavu. Po přidání autentizace bude NUTNÉ přidat CSRF ochranu.

---

### 3. Dokumentace

- **CLAUDE.md:** Aktuální, obsahuje všechny nové vzory (sdílený progress bar, `_send_progress.html`, scroll restore)
- **UI_GUIDE.md:** Aktualizován o scroll restore mechanismus (§13)
- **README.md:** Popis nesrovnalostí by měl být přidán do sekce Platby — aktuálně chybí endpoint `/nesrovnalosti`
- **Komentáře:** Nové soubory mají dobré docstringy (`payment_discrepancy.py` má modul-level i funkce-level dokumentaci)

---

### 4. UI / Šablony

#### Pozitivní nálezy
- **Konzistence:** Nesrovnalosti preview používá stejné UI vzory jako ostatní stránky (bubliny, sticky header, sort šipky, badge)
- **Progress bar:** Sdílený partial `_send_progress.html` + `_send_progress_inner.html` — správně oddělená tlačítka od polled oblasti
- **Dark mode:** Všechny nové šablony mají dark mode třídy
- **HTMX:** Správné `hx-boost="false"` na formulářích, polling interval 500ms
- **Přístupnost:** Input labels přítomny, focus management v modálech, Escape zavírá modály
- **Scroll restore:** Robustní implementace — MutationObserver + sessionStorage, pracuje správně s HTMX boost

#### Drobnosti
- Nesrovnalosti preview nemá HTMX search (hledání v tabulce) — ale tabulka je typicky malá (<50 řádků), takže přijatelné
- Chybí export dat (Excel/CSV) ze stránky nesrovnalostí — porušuje tabulkový checklist bod 8, ale může být záměrné vzhledem k malému objemu dat

---

### 5. Výkon

#### N6 — MEDIUM: Memory leak v `_discrepancy_progress`

- **Co a kde:** `_helpers.py:12` — `_discrepancy_progress: dict[int, dict] = {}` se naplní při každém spuštění odesílání. Vyčistí se pouze v polling endpointu (`statements.py:1610`) po dokončení + 3s. Pokud uživatel:
  1. Spustí odesílání
  2. Naviguje pryč (nikdy se nevrátí na polling stránku)

  Progress dict zůstane v paměti navždy. Stejný pattern existuje v `tax/sending.py` (`_sending_progress`).

- **Řešení:** Přidat TTL cleanup — v polling endpointu nebo při dalším spuštění:
  ```python
  # V polling endpointu: vyčistit stale progress (>1 hodina)
  stale = [k for k, v in _discrepancy_progress.items()
           if v.get("done") and time.monotonic() - v.get("finished_at", 0) > 3600]
  for k in stale:
      _discrepancy_progress.pop(k, None)
  ```
- **Náročnost:** nízká, ~15 min
- **Závislosti:** žádné
- **Regrese riziko:** nízké
- **Jak otestovat:** Spustit odesílání, odejít ze stránky, vrátit se po 5 minutách — progress nesmí bránit novému odeslání.

---

#### Pozitivní výkonnostní nálezy
- **N+1 dotazy:** Nový kód správně používá `joinedload()` pro eager loading
- **Indexy:** Všechny FK sloupce mají `index=True` v modelech i v `_ensure_indexes()`
- **Migrace:** Nové sloupce přidány přes `ALTER TABLE` v `_ALL_MIGRATIONS`
- **compute_nav_stats:** Efektivní — jeden kombinovaný SQL dotaz na Payment statistiky

---

### 6. Error Handling

#### Pozitivní nálezy
- **Batch sending:** Správný error handling — selhání jednoho emailu nepřeruší celou dávku, SMTP spojení se obnoví po chybě
- **CSV parsing:** Try/except s logováním a uživatelsky srozumitelnou chybovou hláškou
- **Formulářová validace:** Chybějící soubor, prázdný CSV, duplicitní výpis — vše ošetřeno s flash messages
- **Custom error pages:** 404 a 500 mají custom šablonu `error.html`

#### Problém
- **N4** (viz bezpečnost): Chybějící try/except na `int()` konverzi `selected_ids`

---

### 7. Git Hygiene

- **Commit messages:** Česky, stručné, popisné (feat/fix prefix)
- **Commit granularita:** Každý commit má jasný scope (1 feat nebo 1 fix)
- **Merge:** Použit merge commit pro feature branch `platebni-upozorneni`
- **.gitignore:** Kompletní — `.env`, `data/`, `.playwright-mcp/`, `*.png` zahrnuto
- **Žádné citlivé soubory:** V git historii ani v working tree
- **Žádné zbytkové soubory:** `.playwright-mcp/` čistý, žádné testovací soubory v kořeni

Přetrvávající LOW problémy z minulého auditu:
- **N12:** `pripravit_prenos.sh:22` — hardcoded cesta k Dropboxu
- **N13:** `spustit.command:137` — WHEEL_COUNT proměnná

---

### 8. Testy

#### N8 — MEDIUM: Chybějící testy pro payment_discrepancy.py

- **Co a kde:** `app/services/payment_discrepancy.py` (390 řádků, nový service) nemá žádné testy. Obsahuje:
  - `detect_discrepancies()` — komplexní logika s 3 typy nesrovnalostí
  - `_match_owner_by_sender()` — SJM párování
  - `build_email_context()` — generování emailového kontextu
  - Toleranci násobků (1-12 měsíců)
  - Sloučené platby (combined)

  Celkem 298 testů existuje, ale žádný nepokrývá nesrovnalosti.

- **Řešení:** Vytvořit `tests/test_payment_discrepancy.py` s testy pro:
  1. `detect_discrepancies` — wrong_vs, wrong_amount, combined
  2. `_match_owner_by_sender` — SJM párování, fallback
  3. `build_email_context` — správné formátování
  4. Edge cases: prázdné VS, nulový předpis, tolerance násobků
- **Náročnost:** střední, ~2 hod
- **Závislosti:** žádné
- **Regrese riziko:** nízké (přidání testů)
- **Jak otestovat:** `python3 -m pytest tests/test_payment_discrepancy.py -v`

#### Pozitivní testové nálezy
- 298 testů, všechny procházejí
- Pokrytí platebního párování je dobré (`test_payment_matching.py`, `test_payment_advanced.py`)
- Smoke testy pokrývají základní endpointy

---

## Doporučený postup oprav

### Etapa 0: Mechanické opravy (~25 min)
> Nulové riziko regrese. Žádné změny v logice.

| # | Co | Čas |
|---|---|-----|
| N11 | Přesunout importy v `_helpers.py` | ~2 min |
| N9 | Přejmenovat `_fmt` v `payment_discrepancy.py` | ~5 min |
| N4 | Přidat try/except na `int()` konverzi selected_ids | ~5 min |
| N10 | Zjednodušit busy-wait loop | ~5 min |

**Test:** `python3 -m pytest tests/ -v` — všech 298 testů musí projít.

---

### Etapa 1: Refaktoring duplikátů (~1.5 hod)
> Nízké riziko. Extrakce sdílených funkcí.

| # | Co | Čas |
|---|---|-----|
| N1 | Sjednotit `_count_debtors_fast` a `compute_debt_map` | ~30 min |
| N3 | Extrahovat sdílenou unit/space logiku v `payment_discrepancy.py` | ~20 min |
| N5 | Extrahovat `_render_discrepancy_email` helper | ~30 min |

**Test:** Dashboard (badge dlužníků), detail vlastníka (dluh), nesrovnalosti preview + test email.

---

### Etapa 2: Rozdělení statements.py (~45 min)
> Nízké riziko. Mechanický přesun kódu.

| # | Co | Čas |
|---|---|-----|
| N2 | Vytvořit `discrepancies.py` v `payments/` | ~45 min |

**Test:** Všechny `/platby/vypisy/{id}/nesrovnalosti/*` endpointy.

---

### Etapa 3: Bezpečnost a výkon (~25 min)

| # | Co | Čas |
|---|---|-----|
| N6 | Memory leak cleanup pro progress dicts | ~15 min |
| N7 | Sanitizace body_preview (rozhodnutí potřeba) | ~10 min |

---

### Etapa 4: Testy (~2 hod)

| # | Co | Čas |
|---|---|-----|
| N8 | Testy pro `payment_discrepancy.py` | ~2 hod |

---

## Celkový odhad

| Etapa | Čas | Riziko | Prerekvizity |
|-------|-----|--------|-------------|
| 0: Mechanické opravy | ~25 min | Nulové | — |
| 1: Refaktoring duplikátů | ~1.5 hod | Nízké | — |
| 2: Rozdělení statements.py | ~45 min | Nízké | — |
| 3: Bezpečnost a výkon | ~25 min | Nízké | — |
| 4: Testy | ~2 hod | Nulové | Etapa 1 (pro správné unit testy) |

**Celkem: ~5 hodin**
