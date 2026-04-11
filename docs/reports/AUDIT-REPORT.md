# SVJ Audit Report – 2026-04-11

Code Guardian — 10. audit. Zaměřeno zejména na 7 dnešních commitů (fuzzy matcher, tax rematch, bounces layout, email_invalid auto-reset, voting index refactor, 3 stránky /platby — sjednocení bublin). Také kompletní průchod všech 8 oblastí dle `docs/agents/CODE-GUARDIAN.md`.

## Souhrn

- **CRITICAL**: 0
- **HIGH**: 2
- **MEDIUM**: 6
- **LOW**: 5

## Souhrnná tabulka

| # | Oblast | Soubor | Severity | Problém | Čas | Rozhodnutí |
|---|--------|--------|----------|---------|-----|------------|
| 1 | Výkon / Kód | `app/routers/tax/processing.py:67` | HIGH | N^2 lookup v `_prepare_owner_lookup`: pro každý `OwnerUnit` iteruje seznam `owner_dicts` (`next(...)`). U větších SVJ zbytečně pomalé — mapa `{id: dict}` je triviální fix. | ~5 min | 🔧 |
| 2 | UI / Kód | `app/templates/payments/vypisy.html:37,52` | HIGH | Nečitelný `_back\|replace('&back=', 'back=') if _back and not _base.endswith('?') and not _base.endswith('&')` — za určitých kombinací `_base`/`back` generuje dvojitý `?` nebo chybějící oddělovač. Kanonický vzor (`/vlastnici`) používá přímočaře `{{ _base }}...&back=`. | ~15 min | 🔧 |
| 3 | UI / Kód | `app/templates/voting/index.html:25,30,35,40,45` | MEDIUM | `_sort_suffix[1:]` slicing trik místo čistého ternary — křehké, pokud se `_sort_suffix` přepíše. Refaktor na `sort_qs = ('sort=' ~ current_sort ~ '&') if ...`. | ~10 min | 🔧 |
| 4 | Výkon | `app/routers/tax/processing.py:395` (`tax_recompute_scores`) | MEDIUM | Pro každou `dist` se volá `match_name([single_dict])` 2×+ (celá fráze + části). U 300 dokumentů × 2 distribucí × 3 kandidátů = ~1 800 volání `match_name`. Lokální optimalizace: precomputovat normalizaci. | ~20 min | 🔧 |
| 5 | Bezpečnost (XSS) | `app/templates/voting/{detail,ballots,process}.html` | MEDIUM | `(_svg_up if ... else _svg_down)\|safe` — vzor `\|safe` u opakovaných sort šipek je snadné přehlédnout při copy-paste. Aktuálně bezpečné (konstantní string), ale refaktor do partialu je bezpečnější. | ~10 min | ❓ |
| 6 | Error handling | `app/services/backup_service.py:385` | MEDIUM | `conn.execute(f"SELECT COUNT(*) FROM {table}")` — i když z whitelistu (komentář potvrzuje), f-string v SQL je anti-pattern a špatný vzor pro budoucnost. | ~10 min | 🔧 |
| 7 | Kód | `app/routers/tax/processing.py:84` + voting/session.py | MEDIUM | `except Exception as e:` — proměnná `e` nepoužitá (jen `logger.exception`). Opakuje se v modulu. Standardizovat. | ~5 min | 🔧 |
| 8 | Dokumentace | `docs/reports/` | MEDIUM | 17 report souborů — staré ORCHESTRATOR/UX/TEST reporty z března. Chybí retention policy. | ~5 min | ❓ |
| 9 | Kód / UX | `app/routers/owners/crud.py:707-744` | LOW | Endpoint `owner_update` přijímá pouze kontakty, ale název je generický. Zvažit přejmenování na `owner_update_contact`. | ~15 min | ❓ |
| 10 | UI | `app/templates/bounces/_table.html:27-32` | LOW | Hardcoded emoji v badge (`🔴 HARD`, `🟡 SOFT`) — nekonzistentní s UI_GUIDE.md. | ~10 min | ❓ |
| 11 | Dokumentace | `app/services/owner_matcher.py:39` | LOW | `_stem_czech_surname` chybí vysvětlení proč `len(word)-len(s) >= 3` (ochrana před prázdným kmenem). | ~5 min | 🔧 |
| 12 | Kód | `app/routers/dashboard.py:279` | LOW | Proměnná `_group_key_counts` s underscore prefixem pro lokální dict je nezvyklá konvence. | ~2 min | 🔧 |
| 13 | Testy | `tests/test_owner_matcher.py` neexistuje | LOW | Dnes rozšířené TITLE_PATTERNS (arch., M.B.A., LL.M.) nemají žádný test. Fuzzy matcher je kritický pro tax distribuci. | ~30 min | 🔧 |

Legenda: 🔧 = jen opravit, ❓ = potřeba rozhodnutí uživatele

## Detailní nálezy

### 1. Kódová kvalita

#### #1 N^2 lookup v `_prepare_owner_lookup` (HIGH)

- **Co a kde**: `app/routers/tax/processing.py:67` — v cyklu `for ou in owner_units` se volá `next((o for o in owner_dicts if o["id"] == ou.owner_id), None)`. Při 100 vlastnících a 300 OU = 30 000 iterací při každém novém tax session uploadu.
- **Řešení**: před cyklem vytvořit `owner_by_id = {o["id"]: o for o in owner_dicts}`, uvnitř `owner_by_id.get(ou.owner_id)`.
- **Náročnost**: nízká, ~5 min.
- **Regrese**: nízké — čistý refaktor, identický výstup.
- **Test**: `/dane/nova` → nahrát PDF balíček → ověřit že všichni vlastníci na jednotce dostanou distribuci (žádný missing match). Spustit `pytest tests/test_voting*.py` pro jistotu.

#### #3 `_sort_suffix[1:]` string slicing trik (MEDIUM)

- **Co a kde**: `app/templates/voting/index.html:25,30,35,40,45` — pět odkazů používá `{{ _sort_suffix[1:] }}{% if _sort_suffix %}&{% endif %}stav=...`. Trik funguje, ale při čtení nepochopitelný.
- **Řešení**: nahradit vzorem `_sort_qs = ('sort=' ~ current_sort ~ '&') if current_sort and current_sort != 'created_desc' else ''` a pak `{{ _base }}{{ _sort_qs }}stav=...`.
- **Náročnost**: nízká, ~10 min.
- **Regrese**: nízké — URL se nemění.
- **Test**: `/hlasovani?sort=name` → kliknout na bubliny → URL musí obsahovat `sort=name&stav=active`.

#### #7 Nepoužitá proměnná v except (MEDIUM)

- **Co a kde**: `app/routers/tax/processing.py:84`, `voting/session.py:227,290,305` — `except Exception as e:` ale `e` se nikde nepoužívá.
- **Řešení**: `except Exception:` bez `as e` tam, kde následuje pouze `logger.exception(...)`.
- **Čas**: ~5 min.
- **Regrese**: nulové.

#### #12 `_group_key_counts` konvence (LOW)

- `app/routers/dashboard.py:279` — lokální dict s `_` prefixem. Underscore prefix je rezervován pro module-private funkce, ne lokální proměnné. Přejmenovat.

### 2. Bezpečnost

#### #5 `|safe` SVG šipky v sort hlavičkách (MEDIUM)

- **Co a kde**: `app/templates/voting/{detail,ballots,process}.html` — 5 míst `{{ (_svg_up if ... else _svg_down)|safe }}`. Data jsou statické řetězce v `{% set %}` v téže šabloně → **aktuálně XSS-safe**. Ale vzor je křehký.
- **Řešení**: přesunout SVG do `app/templates/partials/_sort_icon.html` bez `|safe`, volat přes `{% include %}` s proměnnou `direction`.
- **Varianty**: (a) ponechat + komentář; (b) refaktor na partial; (c) Jinja macro `{{ sort_arrow(order) }}`.
- **Náročnost**: nízká, ~10 min.
- **Test**: `/hlasovani/{id}` → kliknout na sloupec v tabulce lístků → šipka musí být vidět a obracet se.

#### #6 F-string v SQL (MEDIUM, low risk)

- **Co a kde**: `app/services/backup_service.py:385`. Tabulka z hardcoded whitelistu — injection nemožná, ale vzor špatný.
- **Řešení**: přidat `assert table in tables` a obalit identifikátor: `f'SELECT COUNT(*) FROM "{table}"'`.
- **Čas**: ~10 min.

**Bezpečnostní check — další oblasti OK:**
- SMTP heslo v `.env` (správně), `.env` v `.gitignore` ✓
- `HTMLResponse(f"...")` — žádný výskyt ✓
- File upload validace přes `UPLOAD_LIMITS` ✓
- Global security headers middleware v `main.py` ✓
- Authentizace — plánováno na konec (per CLAUDE.md), audit ji nevyžaduje

### 3. Dokumentace

#### #8 Balast v `docs/reports/` (MEDIUM)

- **Co a kde**: 17 souborů — `ORCHESTRATOR-REPORT-2026-03-19.md` … `UX-REPORT-v4.md`, `PREHLED-KOMPLET.md`, `TEST-REPORT.md`.
- **Řešení**: založit `docs/reports/archive/` a přesunout vše starší než 2 týdny; ponechat aktuální `AUDIT-REPORT.md`.
- **Varianty**: (a) archive složka; (b) smazat úplně; (c) gitignore + lokální only.
- **Čas**: ~5 min.

#### #11 Docstring `_stem_czech_surname` (LOW)

- `app/services/owner_matcher.py:39` — minimální docstring, nevyjasňuje ochranu proti krátkému kmeni.

#### CLAUDE.md / README.md / UI_GUIDE.md kontrola

- **CLAUDE.md**: aktuální, obsahuje všechny recentní vzory (bubliny, sort, wizard stepper, back URL, export filename).
- **README.md**: nedávné changelogy z dnešních commitů jsou zapracované.
- **UI_GUIDE.md**: kanonický vzor bubliny+sort container je popsán (§ 14?), platí pro /vlastnici, /hlasovani a nově /platby/vypisy.

### 4. UI / Šablony

#### #2 Křehký `_back` replace pattern v `vypisy.html` (HIGH)

- **Co a kde**: `app/templates/payments/vypisy.html:37,52` — dvakrát `{{ _back|replace('&back=', 'back=') if _back and not _base.endswith('?') and not _base.endswith('&') else _back }}`.

  Rozbor 4 kombinací:
  - `_base` končí `?` (žádný `q`) a `_back = '&back=/x'` → vrací `_back` → výsledek `...?&back=/x` → **nadbytečný `&` za `?`**.
  - `_base` končí `&` (má `q`) a `_back = '&back=/x'` → vrací `_back` → výsledek `...q=xxx&&back=/x` → **`&&`**.
  - Naopak bez back → pattern nedělá nic.

  Prohlížeč URL toleruje, ale vzor je nečitelný a odchyluje se od kanonického vzoru `/vlastnici`.
- **Řešení**: unifikovat — stavět filter querystring v routeru a předat do šablony jako `filter_qs` (string), v šabloně pak čistě `{{ _base }}&{{ filter_qs }}&back={{ back_url|urlencode }}`. Alternativa: macro `{{ build_url('/platby/vypisy', q=q, rok=rok, stav=stav, back=back_url) }}`.
- **Náročnost**: střední, ~15 min.
- **Regrese**: **středně vysoké** — potřeba otestovat všechny kombinace (bez rok, s rok, bez back, s back, bez q, s q).
- **Test**: `/platby/vypisy` → kliknout na „Všechny roky", 2024, 🔓 Otevřené, 🔒 Zamčené. Pak `/platby/vypisy?back=/` a zopakovat. URL v každém kliknutí musí být čistá (žádné `??`, `&&`).

#### #10 Emoji v bounce badges (LOW)

- `bounces/_table.html:27-32` — nahradit `🔴 HARD` → `<span class="w-2 h-2 rounded-full bg-red-500 inline-block mr-1"></span>HARD`.

### 5. Výkon

#### #4 `tax_recompute_scores` opakované `match_name` (MEDIUM)

- **Co a kde**: `app/routers/tax/processing.py:395-447`. Pro každou distribuci se volá `match_name([owner_dict])` 2×+ na různé varianty kandidátského jména. `match_name` → `normalize_for_matching` → regex + `strip_diacritics` + stemming = ~10 ms per call. U 300 dokumentů × 2 dist × 3 candidates ≈ 1 800 volání ≈ 18 s.
- **Řešení**: precompute normalizovaných kandidátů per dokument; `match_name` cachovat na úrovni smyčky. Alternativně volat `match_name(doc.extracted_owner_name, [owner_dict], threshold=0.0)` jen jednou, místo 3×.
- **Čas**: ~20 min.
- **Test**: `/dane/{id}/prepocitat-skore` u sessions s 300+ dokumenty → response < 3s.

#### N+1 check — rest OK

- `_prepare_owner_lookup` používá `joinedload(OwnerUnit.unit)` ✓
- `_propagate_assignments` batch dotazy přes `in_()` ✓
- voting index ve smyčce `voting_stats[voting.id]` — stats precomputed v routeru ✓

### 6. Error Handling

- Globální handlery (`IntegrityError`, `OperationalError`, 404, 500) v `main.py` ✓
- Custom `error.html` šablona ✓
- Flash messages přes query param (per CLAUDE.md) ✓
- `except Exception: pass` u file cleanups (bounce, word_parser) je ospravedlněné „best-effort"

### 7. Git Hygiene

- `.gitignore` kompletní ✓
- `.playwright-mcp/` prázdný ✓, žádné PNG/JPEG v kořenu ✓
- `git status` čistý ✓
- Commit messages kvalitní (české, konvenční prefixy `fix(ui)`, `feat(dane)`, `docs:`)
- `data/svj.db` 6,1 MB — **není v gitu** (správně) ✓
- `docs/reports/` — viz #8

### 8. Testy

- **Existující**: 14 test souborů — voting, voting_aggregation, payment_advanced, payment_matching, contact_import, tenants, backup, email_service, csv_comparator, import_mapping, smoke.
- **Chybí (#13)**:
  - `tests/test_owner_matcher.py` — **kritický**. Dnes rozšířené `TITLE_PATTERNS` (arch., M.B.A., LL.M., akad., MgA.) nemají žádný test. Regrese by nikdo nezachytil.
  - Test pro `tax/processing.py::tax_recompute_scores` (nový endpoint)
  - Test pro `_propagate_assignments` / `_propagate_emails` helpery
- **Doporučení**: přidat `test_owner_matcher.py` s 8-10 kejsy (PhD, M.B.A., arch., SJM prefix, spoluvlastnictví, stem overlap rejection). ~30 min.

## Doporučený postup oprav

### Fáze 1 — rychlé winy (~45 min)

1. **#1** N^2 lookup → dict (5 min)
2. **#7** Odstranit nepoužité `as e` (5 min)
3. **#11** Docstring `_stem_czech_surname` (5 min)
4. **#12** `_group_key_counts` rename (2 min)
5. **#8** Archivace `docs/reports/` (5 min, vyžaduje rozhodnutí)
6. **#2** `vypisy.html` refaktor `_back` patternu (15 min, nejvyšší HIGH)

### Fáze 2 — cleanup (~55 min)

7. **#3** `_sort_suffix[1:]` refaktor (10 min)
8. **#4** `tax_recompute_scores` optimalizace (20 min)
9. **#5** SVG sort šipky do partialu (10 min)
10. **#6** Backup f-string SQL whitelist assert (10 min)
11. **#13** `test_owner_matcher.py` (30 min)

### Fáze 3 — nice-to-have

12. **#10** Emoji → SVG dots (10 min)
13. **#9** `owner_update` rename — skip pro teď (breaking change bez přínosu)

## Celkový verdikt

**Kód je zdravý**, 0 CRITICAL nálezů. Obsahuje 2 HIGH problémy, které stojí za opravu ještě dnes:

- **#2 `vypisy.html` — křehký `_back` replace pattern** generuje lehce nevalidní URL a odchyluje se od kanonického vzoru `/vlastnici`. Refaktor ~15 min, ale potřeba důkladný test 4 kombinací.
- **#1 N^2 lookup v tax processing** — triviální ~5 min fix.

Dnešních 7 commitů je čistých:
- `owner_matcher.py` TITLE_PATTERNS dobře strukturované, ale bez testu (#13)
- `tax/processing.py::tax_recompute_scores` správně zamyká READY+ status a správně porovnává `old + 0.001`
- `owners/crud.py` email_invalid reset logika správná (`email_changed and new_email and owner.email_invalid`)
- `bounces/_table.html` stacked layout konzistentní
- `voting/index.html` refactor funkční, ale trik s `[1:]` je čitelnostní regrese (#3)
- `payments/vypisy.html` refactor funkční, ale `_back` pattern je křehký (#2)

Bezpečnost OK (žádná SQL injection, `|safe` XSS je statické, hesla v `.env`, security headers). Dokumentace aktuální. Hlavní slabina = chybějící testy pro fuzzy matcher po dnešních změnách.

**Doporučení**: opravit #1 a #2 dnes (20 min), #13 přidat do dalšího týdne, zbytek plánovat na příští audit.
