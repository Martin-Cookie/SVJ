# SVJ Audit Report – 2026-04-10 (Re-audit)

> **Scope**: verifikace 11 oprav z předchozího auditu (commity `18b7200`, `7a9ea3e`, `894f750`) + lehký sweep celého projektu.
> **Základní otázky**: (1) jsou staré HIGH/MEDIUM pryč? (2) nezavlekly opravy regrese? (3) jsou nové problémy?
> **Testy**: všech 310 testů projde (`.venv/bin/python -m pytest -q` → `310 passed, 37 warnings`).
> **Server**: `:8022` odpovídá 200 na `/`, `/najemci/`, `/prostory/`, `/vlastnici/`.

## Souhrn

- CRITICAL: 0
- HIGH: 0
- MEDIUM: 2
- LOW: 5

## Verifikace předchozích nálezů

| # | Původní nález | Severita | Stav | Poznámka |
|---|---------------|----------|------|----------|
| 1 | `find_existing_tenant` — silent match podle jména | HIGH | **OPRAVENO** | `tenant_create` teď sbírá `duplicates` + vyžaduje `force_create=1` checkbox (`app/routers/tenants/crud.py:80-109`) — stejný vzor jako owners |
| 2 | `tenant_create` tichá zpětná vazba při duplicitě | HIGH | **OPRAVENO** | Vrací `_create_form.html` s `duplicates` listem (`crud.py:104-109`); HTMX i non-HTMX sdílejí stejnou cestu |
| 3 | Mrtvý `active_rel` v detail contextu | MEDIUM | **OPRAVENO** | `tenant_detail` už předává jen `active_rels` (řádek 669), žádný `active_rel` single (`app/routers/tenants/crud.py`) |
| 4 | `active_space_rels` volané 2× v sort | MEDIUM | **OPRAVENO** | `rels_cache = {t.id: t.active_space_rels for t in tenants}` v `_filter_tenants` (`_helpers.py:127`), sort i `rent` čtou z cache |
| 5 | Migrace skipuje záznamy bez dedup klíče tiše | MEDIUM | **OPRAVENO** | Přidán `logger.info("_migrate_dedupe_tenants: přeskočeno %d Tenantů …")` (`app/main.py:656-660`) |
| 6 | Sort "space" bere jen první prostor bez vysvětlení | MEDIUM | **OPRAVENO** | Tooltipy na `sort_th`: "Řazeno dle nejnižšího čísla prostoru nájemce" a "Součet nájemného ze všech aktivních smluv" (`list.html:126-127`) |
| 7 | Dedup v `spaces/crud.py` bez ID fields — bez feedbacku | MEDIUM | **OPRAVENO** | Flash `tenant_reused` při reuse (`crud.py:147,233`); detail prostoru ukazuje warning toast (`crud.py:837-842`); komentář nad `find_existing_tenant` voláním |
| 8 | Parsing "Jméno Příjmení" obrácený (LOW, pre-existing) | LOW | **ČÁSTEČNĚ** | Placeholder ve formuláři nastaven na "Příjmení Jméno" (`spaces/partials/_create_form.html:50`) + komentář v kódu. Netvoří se dvě pole, ale očekávání je teď explicitní |
| 9 | XSS přes `HTMLResponse(f"…{existing.display_name}")` | LOW→HIGH (XSS) | **OPRAVENO** | `HTMLResponse` nahrazen `Response(status_code=204, headers={"HX-Redirect": …})` (`crud.py:131`). Žádný surový f-string s user inputem |
| 10 | Reporty v rootu repozitáře | LOW | **OPRAVENO** | Commit `894f750` přesunul `AUDIT-REPORT.md`, `BACKUP-REPORT.md`, `TEST-REPORT.md`, `UX-REPORT.md`, `PREHLED-KOMPLET.md`, `SESSION-START.md` do `docs/reports/` |
| 11 | `align-top` s prázdným místem (UX, LOW) | LOW | **PONECHÁNO** | Design rozhodnutí — původní doporučení byla varianta (a) zachovat. Bez akce |
| 12 | Chybí testy nových flows | LOW | **OPRAVENO** | `tests/test_tenants.py` (197 řádků, 12 testů): resolved props, active_space_rels, dedup helper, duplicate warning, XSS-safe, migrace idempotence |
| 13 | CLAUDE.md / README bez nového vzoru | LOW | **OPRAVENO** | Sekce `### Tenants — dedup helper a resolved properties` v `CLAUDE.md § Router vzory` (dle diffu commitu 18b7200) |

**Výsledek verifikace: 11/11 HIGH+MEDIUM nálezů z předchozího auditu je skutečně opraveno. 310 pytest testů projde.**

---

## Nové nálezy (po refaktoringu)

### Souhrnná tabulka

| # | Oblast | Soubor | Severity | Problém | Čas | Rozhodnutí |
|---|--------|--------|----------|---------|-----|------------|
| A1 | Git hygiene | `.playwright-mcp/` | MEDIUM | 24 souborů (`console-*.log`, `page-*.yml`) ze staršího testování v ignored adresáři — plýtvá místem, matoucí při dalším Playwright runu | ~1 min | 🔧 |
| A2 | Testy | `tests/test_tenants.py:162, 180` | MEDIUM | `DeprecationWarning` ze Starlette: `TemplateResponse(name, {"request": …})` má novou API `TemplateResponse(request, name)`. Varování jen v nových testech — jinde v projektu už bude stejný problém, ale tiskne se jen v testech (používajících TestClient) | ~10 min | 🔧 |
| A3 | Kód (UI — mrtvý kód) | `app/templates/tenants/partials/_row.html:2` | LOW | `{% set asr = active_rels[0] if active_rels else None %}` — proměnná `asr` nikde v šabloně nepoužitá (zbytek po přechodu na stacked layout) | ~1 min | 🔧 |
| A4 | Kód (UX) | `app/routers/spaces/crud.py:131-136` | LOW | Parsing `tenant_name` pořád jeden split bez validace; placeholder pomáhá, ale neexistuje UI varování pokud user napíše jen "Jan" (pak `last_name="Jan"`, `first_name=None`) nebo obráceně. Dedup přes `name_normalized` pak matchuje podle "jan" a může vtáhnout jmenovce | ~15 min | ❓ |
| A5 | Výkon / model | `app/models/space.py:167-177` | LOW | `active_space_rel` (single) stále volá `self.active_space_rels` (rebuilduje list). Triviální, použit už jen v 2 místech (`Tenant.active_space_rel` property). `rels_cache` v seznamu řešeno, ale detail stránky volá property přímo | ~5 min | 🔧 |
| A6 | Konzistence | `app/routers/tenants/_helpers.py:132-134` | LOW | Sort klíč `rent` = součet (`sum(sr.monthly_rent ...)`), klíč `space` = jen první (`rels[0].space_number`). Nekonzistentní — uživatel vidí "Nájemné" jako součet (viz tooltip), ale "Prostor" jako první. Je to záměrné (a zdůvodněné tooltipem), jen uvažte sjednocení | ~10 min | ❓ |
| A7 | Dokumentace | `CLAUDE.md` § Tenants dedup | LOW | Sekce zmiňuje `find_existing_tenant`, ale NEzmiňuje, že v `spaces/crud.py` se dedup děje BEZ RČ/IČ (jen jméno) — jiný kontrakt, než u `tenants/crud.py`. Při reuse v dalších modulech může zmást | ~5 min | 🔧 |

Legenda: 🔧 = jen opravit, ❓ = potřeba rozhodnutí uživatele

---

## Detailní nálezy

### A1. `.playwright-mcp/` obsahuje zbytky po testování (MEDIUM)

**Co a kde**: `ls .playwright-mcp/` → 12× `console-*.log` + 12× `page-*.yml` z `2026-04-10T10:53-54`. Dle CLAUDE.md § Workflow: „po použití Playwright smazat soubory v `.playwright-mcp/`". Commit 894f750 přesunul reporty, ale adresář neuklidil.

**Řešení**:
```
rm -rf .playwright-mcp/*.log .playwright-mcp/*.yml .playwright-mcp/*.png .playwright-mcp/*.jpeg
```
Plus ověřit, že `.playwright-mcp/` je v `.gitignore` (rychlá kontrola `git check-ignore .playwright-mcp/`).

**Náročnost**: nízká, ~1 min. **Regrese**: žádné. **Jak otestovat**: `ls .playwright-mcp/` → prázdné.

### A2. Starlette TemplateResponse deprecation warnings (MEDIUM)

**Co a kde**: `tests/test_tenants.py::test_tenant_create_shows_duplicates_warning` a `test_tenant_create_no_xss_in_duplicate_warning` tisknou:
```
DeprecationWarning: The `name` is not the first parameter anymore.
Replace `TemplateResponse(name, {"request": request})` by `TemplateResponse(request, name)`.
```
Jde o volání `templates.TemplateResponse("tenants/partials/_create_form.html", {"request": request, …})`. Celý projekt používá starou signaturu — teď se na to rozsvítí díky novým testům. Starlette ≥ 0.29 (cílová verze pro FastAPI 0.115+) toto API odstraní.

**Řešení**: masový rewrite přes projekt na `TemplateResponse(request, "…", {"…": …})`. Lze pomocí `grep -r "templates.TemplateResponse(\"" app/routers/ | wc -l` → počet volání a ripgrep-replace.

**Varianty**: (a) hromadný rewrite teď (~30-60 min, ~100 volání); (b) odložit, připnout Starlette verzi v `requirements.txt` (~2 min, ale dluh). Doporučuji (a) — je to mechanická úprava a odstraní warning z testů.

**Náročnost**: střední, ~30-60 min. **Regrese**: nízké (API je kompatibilní zpětně, jen deprecated). **Jak otestovat**: `pytest -q` → 0 warnings od TemplateResponse.

### A3. Mrtvá proměnná `asr` v `_row.html` (LOW)

**Co a kde**: `app/templates/tenants/partials/_row.html:2`:
```jinja
{% set active_rels = tenant.active_space_rels %}
{% set asr = active_rels[0] if active_rels else None %}
```
Proměnná `asr` se nikde dál v šabloně nepoužívá (grep nenašel). Zbytek po refaktoringu na stacked layout (commit 64acbe9).

**Řešení**: smazat řádek 2.

**Náročnost**: nízká, ~1 min. **Regrese**: žádné. **Jak otestovat**: `/najemci/` — layout identický.

### A4. Parsing `tenant_name` v `spaces/crud.py` stále křehký (LOW)

**Co a kde**: `app/routers/spaces/crud.py:131-134`:
```python
parts = tenant_name.split()
last_name = parts[0] if parts else None
first_name = " ".join(parts[1:]) if len(parts) > 1 else None
```
User napíše "Novák" → `last_name="Novák"`, `first_name=None`. Placeholder hinter "Příjmení Jméno" pomáhá, ale nic nebrání chybě. Dedup pak matchuje přes `name_normalized="novák"`, což může vtáhnout jmenovce.

**Varianty**:
- (a) Rozdělit na dvě pole `last_name` + `first_name` (vzor z owners). Nejčistší, ~15 min.
- (b) Validovat `len(parts) >= 2` a zobrazit chybu „Zadejte příjmení i jméno". Rychlejší, ~5 min.
- (c) Ponechat (pre-existing, nízký dopad).

**Regrese**: nízké u (a)/(b). **Jak otestovat**: `/prostory/novy` → zadat jen „Novák" → očekávaná validace nebo dvě pole.

### A5. `Space.active_space_rel` property rebuild při každém volání (LOW)

**Co a kde**: `app/models/space.py:167-170`:
```python
@property
def active_space_rel(self):
    rels = self.active_space_rels  # nový list + sort pokaždé
    return rels[0] if rels else None
```
Řešeno v `_filter_tenants` přes `rels_cache`, ale volání v detail šablonách a jiných průchodech stále rebuilduje. Zanedbatelné pro běžný dataset (≤100 prostor), ale zbytečné.

**Řešení**: ponechat (YAGNI) nebo `@functools.cached_property` — pozor, s SQLAlchemy expire/refresh má `cached_property` rizika. Doporučuji ponechat + komentář že se volá opakovaně.

**Náročnost**: nízká, ~5 min.

### A6. Nekonzistence `sort="space"` vs `sort="rent"` (LOW)

**Co a kde**: `_helpers.py:133-134`:
```python
"space": lambda t: (rels_cache[t.id][0].space.space_number if rels_cache[t.id] else 0),
"rent":  lambda t: sum((sr.monthly_rent or 0) for sr in rels_cache[t.id]),
```
`space` sort bere jen první prostor, `rent` sčítá přes všechny. Obojí je logické a zdůvodněné tooltipy, ale asymetrie může zmást.

**Řešení**: (a) ponechat (doporučeno) — tooltipy jsou explicitní. (b) `space` jako tuple všech čísel pro sekundární řazení: `tuple(sr.space.space_number for sr in rels)`. **Nedoporučuji měnit** — nemá praktický rozdíl.

### A7. CLAUDE.md nezdokumentuje dva různé kontrakty `find_existing_tenant` (LOW)

**Co a kde**: CLAUDE.md § "Tenants — dedup helper …" popisuje prioritu `owner_id → RČ → IČ → jméno`. Nezmiňuje, že `spaces/crud.py:140-145` volá helper **jen se jménem** (bez RČ/IČ) jako úmyslný inline UX kompromis. Další vývojář tuto nuance snadno přehlédne.

**Řešení**: do CLAUDE.md přidat větu: „V `spaces/crud.py` (rychlé vytvoření prostoru s nájemcem) se `find_existing_tenant` volá jen se jménem — reuse je indikován flash `tenant_reused` a uživatel má možnost opravit přiřazení."

**Náročnost**: nízká, ~5 min.

---

## Lehký sweep ostatních oblastí (bez nálezů)

- **Bezpečnost**: `.env` ignorovaný, žádné hesla v kódu, SQLAlchemy ORM (žádné f-stringy v SQL), security headers v `main.py` middleware (ověřeno dle CLAUDE.md § Security headers). CSRF záměrně nepoužíván (plán rolí, interní deployment).
- **Git status**: čistý (`git status --short` = prázdný).
- **Screenshoty v rootu**: žádné `*.png`/`*.jpeg`.
- **Tests pass**: 310/310.
- **Server up**: `:8022` OK na `/`, `/najemci/`, `/prostory/`, `/vlastnici/`. `:8021` se v tomto auditu vůbec nezkoušel (user poznamenal, že ho drží cizí proces).
- **HTMX error handling**: nedetekován nový problém.
- **Performance**: `_filter_tenants` má správný `joinedload(Tenant.spaces).joinedload(SpaceTenant.space)` + `seen_ids` dedup — N+1 vyřešeno.
- **Error handling**: `_migrate_dedupe_tenants` má `try/finally` s `db.close()`, migrace loguje merged i skipped počty.

---

## Regresní riziko nově aplikovaných oprav

- **HIGH #1+#2+#9 fix** (tenant_create + force_create + XSS): **nízké** — pokryto 3 novými testy (`test_tenant_create_shows_duplicates_warning`, `test_tenant_create_force_create_bypasses_check`, `test_tenant_create_no_xss_in_duplicate_warning`). HTMX i non-HTMX větve sdílejí jednu response cestu.
- **MEDIUM #4 fix** (rels_cache): **nízké** — pokryto `test_tenant_active_space_rels_sorted`. Cache je lokální v listu, nemění data.
- **MEDIUM #5 fix** (logging skipped): **žádné** — jen `logger.info()`.
- **MEDIUM #7 fix** (tenant_reused flash): **nízké** — nová flash větev, ostatní flash hodnoty netknuté.
- **Tenant dedup migrace** (`_migrate_dedupe_tenants`): **střední — SLEDOVAT** — idempotence je pokrytá testem, ale migrace se spouští pokaždé na startu a mění produkční data. Doporučuji sledovat počet merged v logu po nejbližším restartu.

---

## Doporučený postup oprav

1. **Rychlé úklidy** (~10 min): A1 (`.playwright-mcp/`), A3 (mrtvý `asr`), A7 (CLAUDE.md doplnění).
2. **A2 Starlette rewrite** (~30-60 min): hromadné přepsání `TemplateResponse(name, ctx)` → `TemplateResponse(request, name, ctx)`. Oddělený commit, pokrývá celý projekt.
3. **A4 parsing `tenant_name`** (~15 min): rozdělit na 2 pole nebo přidat validaci. Rozhodnutí s uživatelem (varianta a/b/c).
4. **A5, A6**: ponechat (YAGNI / záměrné), doplnit komentáře v kódu.

---

_Vygenerováno: Code Guardian re-audit 2026-04-10, fokus na verifikaci commitů 18b7200, 7a9ea3e, 894f750 + lehký sweep._
