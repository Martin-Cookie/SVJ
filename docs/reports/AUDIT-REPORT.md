# SVJ Audit Report – 2026-04-10

**Scope:** Fokus na posledních 17 commitů (od `86f6bdc` po HEAD), zejména Platby (exporty xlsx/csv, GET endpointy) a dashboard (karta Nájemci). Namátkový průřez zbytkem projektu (bezpečnost, N+1, error handling, git hygiene).

## Souhrn

- CRITICAL: **0**
- HIGH: **3**
- MEDIUM: **8**
- LOW: **6**
- Total: **17**

## Souhrnná tabulka

| # | Oblast | Soubor | Severity | Problém | Čas | Rozhodnutí |
|---|--------|--------|----------|---------|-----|------------|
| 1 | Bezpečnost / XSS | app/templates/partials/settings_email_tbody.html:42, payments/nesrovnalosti_preview.html:275 | HIGH | `body_preview\|safe` renderuje neočištěný HTML z emailů — XSS vektor přes jméno vlastníka | ~15 min | 🔧 |
| 2 | Výkon | app/routers/dashboard.py:199-200 | HIGH | `EmailLog` + `ActivityLog` načítají VŠECHNY řádky bez LIMIT — rychle eskaluje s provozem | ~30 min | ❓ |
| 3 | Výkon | app/routers/dashboard.py:109-147 | HIGH | N+1 uvnitř cyklu per voting status: 3 dotazy × každý status (až 12 dotazů jen pro 4 stavy) | ~30 min | 🔧 |
| 4 | Error handling | app/routers/dashboard.py:353-359 | MEDIUM | `except Exception: pass` tiché selhání — debtor count může tiše vrátit 0 | ~5 min | 🔧 |
| 5 | Výkon | app/routers/payments/overview.py:171-295 | MEDIUM | `matice_export` nepodporuje `entita=prostory` (export prostor chybí, přestože stránka ho má) | ~20 min | ❓ |
| 6 | Kód | app/routers/payments/overview.py:207-215 | MEDIUM | Export `matice_export` má jiné sort_fns než GET (chybí `prevod` a měsíční `m1-m12`) — nekonzistence s view | ~10 min | 🔧 |
| 7 | Kód | app/routers/payments/statements.py:194-230 | MEDIUM | Suffix v exportu není bez diakritiky — u `q` může query obsahovat diakritiku → latin-1 encode error v HTTP hlavičce | ~5 min | 🔧 |
| 8 | Konzistence | app/routers/payments/statements.py (1379 řádků) + 6 dalších | MEDIUM | Soubory přes 500 řádků; statements.py blíží se 1500 řádek threshold pro split | ~2 hod | ❓ |
| 9 | UI konzistence | app/templates/payments/vypisy.html + partials/vypisy_list.html | MEDIUM | Pattern "klikatelný filename" v detail exportu (vypis_detail.html:9) chybí v seznamu výpisů | ~10 min | 🔧 |
| 10 | Výkon | app/routers/payments/statements.py:767-786 | MEDIUM | Na GET `/vypisy/{id}` se nahrávají VŠICHNI owners + all OwnerUnit pro dropdown, pokaždé | ~20 min | 🔧 |
| 11 | Výkon | app/routers/dashboard.py:334-349 | MEDIUM | 4× samostatné dotazy na `Payment` — jde do 1 dotazu s agregací | ~15 min | 🔧 |
| 12 | Error handling | app/routers/payments/discrepancies.py:233 | LOW | `except Exception: pass` skrývá commit failure při nastavení `notified_at` — DB session může zůstat poškozená | ~10 min | 🔧 |
| 13 | Kód — duplikace | dashboard.py:199-316 vs dashboard.py:469-516 | LOW | Unified activity + search/sort logika duplicitní mezi `home()` a `dashboard_export()` | ~20 min | 🔧 |
| 14 | Bezpečnost — deps | requirements.txt | LOW | Chybí pravidelný `pip-audit` | ~10 min | ❓ |
| 15 | Kód | app/routers/payments/overview.py:234,265,484 | LOW | `", ".join(owners)` v exportu — pořadí záleží na session, nestabilní výstup | ~5 min | 🔧 |
| 16 | Dokumentace | CLAUDE.md § Export dat | LOW | Nový vzor "export z detailu entity" (vypis_detail_export) nedokumentován | ~5 min | 🔧 |
| 17 | Testy | tests/ | LOW | Žádné testy na nové exporty Platby ani Tenants dashboard kartu | ~1 hod | ❓ |

Legenda: 🔧 = jen opravit, ❓ = potřeba rozhodnutí uživatele

---

## Detailní nálezy

### 1. HIGH — XSS přes `body_preview|safe`

**1. Co a kde:** `app/templates/partials/settings_email_tbody.html:42` a `app/templates/payments/nesrovnalosti_preview.html:275` renderují `{{ email.body_preview|safe }}` / `{{ log.body_preview|safe }}`. `body_preview` je prvních 500 znaků HTML emailu (`app/services/email_service.py:92,159`), složeného z Jinja2 šablony + kontext (jméno, částka, VS). Jméno/SVJ info se do šablony vkládají standardním `{{ }}` — Jinja2 autoescape **ALE u ponechaného fragmentu uloženého v DB a rendrovaného s `|safe` už ne**.

Scénář: admin vytvoří Owner jménem `<img src=x onerror=alert(1)>`. Při rozeslání platebního upozornění se jméno dosadí do těla, uloží se `body_preview`, následně `/nastaveni/emails` nebo `/platby/nesrovnalosti` spustí XSS.

**Řešení:**
- **Varianta A (doporučeno):** Odstranit `|safe`, nechat autoescape. Vizuál ztratí `<br>` mezi řádky — nahradit CSS `white-space: pre-wrap` + v Python při ukládání místo `replace("\n","<br>")` uložit plain text.
- **Varianta B:** Použít `bleach.clean(body_html, tags=['br','b','i','p'], strip=True)` před uložením.
- **Varianta C:** Vlastní filter „escape + unescape only `<br>`".

**Náročnost:** nízká, ~15 min (A).
**Závislosti:** žádné.
**Regrese:** nízké — kosmetické.
**Jak otestovat:**
1. Vytvořit Owner jménem `<script>alert(1)</script>Test`
2. Odeslat mu payment notice
3. `/nastaveni/emails` — dialog `alert()` se NESMÍ spustit
4. Totéž `/platby/nesrovnalosti` detail

---

### 2. HIGH — Dashboard načítá celý EmailLog + ActivityLog bez LIMIT

**Co a kde:** `app/routers/dashboard.py:199-200`:
```python
recent_emails = db.query(EmailLog).order_by(EmailLog.created_at.desc()).all()
recent_activity = db.query(ActivityLog).order_by(ActivityLog.created_at.desc()).all()
```
Bez LIMIT. Po 6 měsících provozu (2000+ logů) se při každém otevření dashboardu táhne celá tabulka do paměti, v Pythonu se sorti a filtruje.

**Řešení:** Přidat `.limit(200)` (nebo `.limit(500)`). Pro plnou historii poskytnout samostatnou stránku/log viewer.

**Varianty:**
- **A:** Hard limit 200 — 2 řádky, funguje.
- **B:** Paginace HTMX „load more".
- **C:** SQL-side filtering (když uživatel zadá `q`/`modul`, do WHERE).

**Náročnost:** střední, ~30 min (A je 2 řádky, B/C větší refactor).
**Závislosti:** export endpoint (`dashboard_export`) také stahuje celou historii — zvolit vyšší/žádný limit tam.
**Regrese:** střední — uživatel ztratí search přes starou historii na dashboardu.
**Jak otestovat:**
1. Insert 2000 email logů
2. Načíst `/` → < 300 ms
3. Search `q=test` stále funguje pro top 200

---

### 3. HIGH — N+1 loop v dashboardu pro voting statusy

**Co a kde:** `app/routers/dashboard.py:109-147`. Pro každý voting status se dělá:
1. `SELECT ... votings WHERE status = ? ORDER BY updated_at DESC LIMIT 1`
2. `SELECT COUNT(*) FROM ballots WHERE voting_id = ?`
3. Subquery + `SELECT SUM(total_votes) ...`

Totéž pro `tax_sessions` (linie 159-196). Na dashboardu s 4 statusy × 2 moduly = až 16 dotazů navíc.

**Řešení:**
- **A:** Jeden SQL s GROUP BY status + subquery pro agregaci.
- **B:** Cache v paměti TTL 30 s (`functools.lru_cache` + timestamp).

**Náročnost:** střední, ~30 min (A).
**Závislosti:** žádné.
**Regrese:** nízké.
**Jak otestovat:** Zapnout `echo=True` na engine, load `/`, cíl < 20 total dotazů (aktuálně ~30-50).

---

### 4. MEDIUM — `except Exception: pass` v dashboardu

**Co a kde:** `app/routers/dashboard.py:353-359`:
```python
try:
    from app.routers.payments._helpers import _count_debtors_fast
    ...
except Exception:
    pass
```
Tiché selhání — dashboard ukáže 0 dlužníků i při chybě.

**Řešení:** `except Exception as e: logger.warning("Debtor count failed: %s", e)`. Nebo rozlišit `ImportError` (OK) od runtime chyby.

**Náročnost:** nízká, ~5 min.
**Regrese:** žádné.
**Jak otestovat:** dočasně rozbít `_count_debtors_fast`, load `/`, ověřit warning v log.

---

### 5. MEDIUM — `matice_export` nepodporuje `entita=prostory`

**Co a kde:** `app/routers/payments/overview.py:171-295`. GET `/prehled` má režim `entita=prostory` (linie 69), export endpoint parametr `entita` **nečte** — uživatel na prostorech klikne Excel → stáhne se matice jednotek.

**Řešení:** Přidat `entita: str = Query("")` + větev pro `compute_space_payment_matrix`.

**Náročnost:** střední, ~20 min.
**Regrese:** žádné.
**Jak otestovat:** `/platby/prehled?entita=prostory` → Excel musí obsahovat prostory + suffix `_prostory`.

---

### 6. MEDIUM — Nekonzistentní sort_fns GET vs export v overview

**Co a kde:** `app/routers/payments/overview.py`. GET (linie 120-131) má `prevod, m1..m12` sorty. Export (linie 207-215) ne — export při `sort=m5` tiše spadne na `cislo`.

**Řešení:** Extrahovat `_matrix_sort_fns(months_with_data)` helper, volat z obou míst.

**Náročnost:** nízká, ~10 min.
**Regrese:** nízké.
**Jak otestovat:** `/platby/prehled/exportovat/xlsx?sort=m5&order=desc` — seřazen podle května.

---

### 7. MEDIUM — Suffix exportu s diakritikou → HTTP header encode error

**Co a kde:** `statements.py:223-230`, `balances.py`, atd. Suffix dict pro whitelisted hodnoty OK, ale pokud `q` (search) obsahuje diakritiku a byl by použit do filename, latin-1 header encoding selže. Overview.py má `strip_diacritics(typ)` — jinde chybí.

**Řešení:** Všude pro user-supplied části: `strip_diacritics(value)`. CLAUDE.md § Export dat explicitně: **"Nikdy nepoužívat diakritiku v názvu"**.

**Náročnost:** nízká, ~5 min / endpoint (×~8 endpointů = 40 min).
**Regrese:** žádné.
**Jak otestovat:** `curl '/platby/vypisy/exportovat/xlsx?q=rohlíček'` bez chyby.

---

### 8. MEDIUM — Dlouhé soubory

**Co a kde:**
- `app/routers/payments/statements.py` — **1379 řádků**
- `app/routers/payments/overview.py` — 638
- `app/routers/payments/balances.py` — 615
- `app/routers/payments/discrepancies.py` — 611
- `app/routers/payments/settlement.py` — 586
- `app/routers/payments/prescriptions.py` — 553
- `app/routers/dashboard.py` — 562
- `app/routers/units.py` — 715
- `app/routers/voting/session.py` — 949

`statements.py` je největší a blíží se 1500-řádkovému threshold dle CLAUDE.md § Router packages. Kandidát na sub-split:
- `statements/list.py` (seznam + export)
- `statements/import_csv.py`
- `statements/detail.py` (GET + ruční přiřazení)
- `statements/lock.py` (zamknout/odemknout)

**Varianty:** A) preventivně teď, B) počkat na překročení limitu.
**Náročnost:** vysoká, ~2 hod/soubor.
**Regrese:** střední (velký refactor).
**Jak otestovat:** smoke test všech URL pod `/platby/vypisy/*`.

---

### 9. MEDIUM — Klikatelný filename chybí v seznamu výpisů

**Co a kde:** Commit `5b77cb8` přidal download link na filename v `vypis_detail.html:9`, ale `vypisy.html`/`partials/vypisy_list.html` (seznam) to s velkou pravděpodobností nemá. CLAUDE.md § Tabulky bod 7: "názvy souborů MUSÍ být klikací s `target="_blank"` a `hx-boost="false"`".

**Řešení:** V `partials/vypisy_list.html` obalit `{{ s.filename }}` do `<a>` na download endpoint.

**Náročnost:** nízká, ~10 min.
**Regrese:** žádné.
**Jak otestovat:** `/platby/vypisy` → klik na filename → stáhne CSV.

---

### 10. MEDIUM — Neefektivní load detail výpisu

**Co a kde:** `app/routers/payments/statements.py:767-786`. Na každý `/vypisy/{id}` GET:
```python
all_units_list = db.query(Unit).order_by(Unit.unit_number).all()
active_ous = db.query(OwnerUnit).filter(...).all()
all_owners = {o.id: o for o in db.query(Owner).all()}
```
Celý Owner + Unit + OwnerUnit pokaždé, jen kvůli dropdown pro ruční přiřazení. U 500 jednotek tisíce záznamů na refresh.

**Řešení:**
- **A:** Lazy-loaded HTMX dropdown (volá se při kliknutí)
- **B:** 1 JOIN místo 3 dotazů
- **C:** Cache v paměti TTL 60s

**Náročnost:** střední, ~20 min (B).
**Regrese:** nízké.
**Jak otestovat:** SQL profil na `/vypisy/1` → cíl < 15 dotazů.

---

### 11. MEDIUM — 4 count dotazy na Payment v dashboardu

**Co a kde:** `app/routers/dashboard.py:334-349`. `statement_count`, `matched_payments`, `unmatched_payments`, `total_income` — každé samostatný dotaz.

**Řešení:** Jedna agregace s `func.count().filter()` pro každou metriku v jednom SELECT.

**Náročnost:** nízká, ~15 min.
**Regrese:** nízké.
**Jak otestovat:** Čísla na dashboardu shodná.

---

### 12. LOW — Silent except v discrepancies send loop

**Co a kde:** `app/routers/payments/discrepancies.py:233`:
```python
try:
    payment.notified_at = utcnow()
    db.commit()
except Exception:
    logger.warning("Failed to set notified_at for payment %s", rcpt["payment_id"])
```
Warning OK, ale bez `db.rollback()` — session může zůstat poškozená pro další iterace loopu.

Ostatní `except Exception: pass` na linkách 168/183/193/221/243 jsou legitimní (smtp disconnect cleanup) — tam OK.

**Řešení:** Po except volat `db.rollback()`.

**Náročnost:** nízká, ~10 min.
**Regrese:** nízké.
**Jak otestovat:** Dočasně rozbít Payment (NOT NULL), odeslat upozornění, session konzistentní.

---

### 13. LOW — Duplicitní unified activity logika

**Co a kde:** `dashboard.py:199-316` (home) a `dashboard.py:469-516` (export) obsahují duplicitní normalizaci modulu, search filter, sort keys.

**Řešení:** Extrahovat do `_build_unified_activity(db, q, sort, order, modul="")` helper.

**Náročnost:** nízká, ~20 min.
**Regrese:** nízké.

---

### 14. LOW — Chybí `pip-audit`

**Co a kde:** Projekt bez CI; doporučeno manuálně měsíčně spouštět `pip-audit -r requirements.txt`.

**Náročnost:** nízká, ~10 min.

---

### 15. LOW — Owner name join nestable v exportu

**Co a kde:** `overview.py:234, 265, 484`. `", ".join(o.display_name for o in r["owners"])` — pořadí záleží na session. Dva stejné exporty mohou mít různé pořadí spoluvlastníků.

**Řešení:** `sorted(r["owners"], key=lambda o: o.name_normalized)`.

**Náročnost:** nízká, ~5 min.

---

### 16. LOW — CLAUDE.md — nový export vzor nedokumentován

**Co a kde:** `CLAUDE.md § Export dat` neuvádí "export z detailu entity" (URL pattern `/modul/{id}/exportovat/{fmt}`) přidaný v commitu `5b77cb8`. Pro konzistenci opětovného použití vzoru přidat příklad.

**Náročnost:** nízká, ~5 min.

---

### 17. LOW — Chybí testy na nové exporty + Tenants kartu

**Co a kde:** `tests/` nemá:
- `test_vypisy_export*` (statements list export)
- `test_vypis_detail_export*` (detail export)
- `test_matice_export*`, `test_dluznici_export*`
- `test_zustatky_export*`, `test_symboly_export*`, `test_predpisy_export*`
- Smoke test dashboard `tenants_count`, `tenants_linked`, `expiring_contracts`

**Řešení:** V `tests/test_payment_advanced.py` a `tests/test_smoke.py` přidat smoke testy (status 200 + content-type).

**Náročnost:** střední, ~1 hod (10 testů).
**Regrese:** žádné.

---

## Git Hygiene

- `.gitignore` kompletní: `data/svj.db`, `.env`, `.playwright-mcp/`, `data/purge_restore_reports/` (přidáno v `553635d`)
- `.env` existuje lokálně s `-rw-------`, v git není
- Žádné `.playwright-mcp/` artefakty v repu
- Žádné testovací PNG/JPEG v kořenovém adresáři
- Commit messages — jasné, v češtině, s `feat:`/`fix:`/`docs:`/`chore:` prefixy ✅

## Pozitiva

- Žádný SQL injection (všechny dotazy přes ORM; `_ensure_indexes` má whitelist regex `_SAFE_IDENT`)
- Žádné bare `except:` clauses
- Žádné `TODO`/`FIXME`/`HACK` komentáře
- `is_safe_path()` používán konzistentně ve všech upload handlerech
- Starlette 0.29+ TemplateResponse API dodržováno
- `body_preview` omezen na 500 znaků (limit velikosti XSS payloadu)
- `UPLOAD_LIMITS` centralizovány
- 13× `CREATE INDEX IF NOT EXISTS` v `_ensure_indexes()` — dobré pokrytí FK a filter sloupců
- SMTP heslo jen v `.env`, nikde v kódu ani DB
- Helpery `_filter_statements`, `_filter_payments`, `_compute_debtors_filtered` sdílí logiku mezi GET view, HTMX partial a export — správně DRY

## Doporučený postup oprav

1. **HIGH (nejdřív):**
   - #1 XSS `body_preview|safe` — 15 min
   - #2 Dashboard LIMIT na logy — 30 min
   - #3 N+1 voting status loop — 30 min
2. **MEDIUM (další iterace):**
   - #4, #6, #7, #11, #15 — drobné opravy, celkem ~1 hod
   - #5 export prostor matice — 20 min
   - #9 klikatelný filename — 10 min
   - #10 optimalizace detail výpisu — 20 min
   - #8 split statements.py — zvážit po překročení 1500 řádek
3. **LOW:** #12-14, #16-17 do backlogu
