# Doc Sync Report — 2026-04-11

Read-only audit po Code Guardian commitu `c1bc83d`. Porovnání README.md, CLAUDE.md a docs/UI_GUIDE.md proti skutečnému kódu (app/routers, app/models, app/templates).

## Nálezy

| # | Soubor | Řádek | Problém | Navrhovaná oprava | Priorita |
|---|--------|-------|---------|-------------------|----------|
| 1 | README.md | 950–985 (sekce Evidence plateb API) | Chybí nový endpoint `GET /platby/vypisy/{id}/soubor` (stažení zdrojového CSV) — přidán v commit c1bc83d (`statements.py:875`). | Přidat řádek do tabulky: `GET /platby/vypisy/{id}/soubor` — Stažení původního CSV bankovního výpisu. | **H** |
| 2 | README.md | 950–985 | Chybí `GET /platby/vypisy/exportovat/{fmt}` (export seznamu výpisů, `statements.py:179`) a `GET /platby/vypisy/{id}/exportovat/{fmt}` (export detailu výpisu, `statements.py:897`). | Přidat oba endpointy do tabulky plateb. | **H** |
| 3 | README.md | 963 | `POST /platby/prehled/exportovat` — ve skutečnosti `GET /platby/prehled/exportovat/{fmt}` (overview.py:180). Podporuje `entita=prostory` parametr (rozšířeno v c1bc83d). | Změnit metodu na GET, URL s `{fmt}`, do popisu přidat: „přepínač entity jednotky/prostory, respektuje filtry". | **H** |
| 4 | README.md | 965 | `POST /platby/dluznici/exportovat` — ve skutečnosti `GET /platby/dluznici/exportovat/{fmt}` (overview.py:466). | Opravit metodu a URL formát. | **H** |
| 5 | README.md | 986–1006 (Prostory API) | Chybí HTMX endpointy pro inline editaci nájemce na detailu prostoru: `GET /prostory/{id}/najemce-formular`, `GET /prostory/{id}/najemce-info`, `POST /prostory/{id}/upravit-najemce` (`spaces/crud.py:363/385/407`). Přidány v commit 3a776c0. | Doplnit 3 řádky do tabulky. | **H** |
| 6 | README.md | 284–308 (F. Prostory a nájemci) | Chybí zmínka o inline editaci nájemce na detailu prostoru (VS, nájemné, smlouva) — funkce z commitu `3a776c0 feat: inline editace nájemce na detailu prostoru`. | Přidat bullet: „Inline editace aktuálního nájemního vztahu (VS, nájemné, číslo smlouvy, PDF) přes HTMX info/form partial vzor". | **M** |
| 7 | README.md | 717–725 (Dashboard) | Chybí endpoint `GET /exportovat/{fmt}` (`dashboard.py:490`) — export poslední aktivity/logů z dashboardu. | Přidat řádek do tabulky dashboardu. | **M** |
| 8 | CLAUDE.md | 305–309 § Export dat | OK — URL vzor `/{modul}/{id}/exportovat/{fmt}` už doplněn v c1bc83d. Ale chybí explicitní příklad `/platby/vypisy/{id}/exportovat/{fmt}` mezi existujícími příklady (matice, listky). | Rozšířit příklad o „detail výpisu plateb". | **L** |
| 9 | CLAUDE.md | 67 (Navigace, sekce Tabulky) | Bod 7 mluví o „náhledech souborů", ale nezmiňuje nový pattern přímého stažení zdrojového souboru výpisu (`/soubor` endpoint) jako referenční implementaci validace cesty. | Přidat odkaz/zmínku: `statements.py` má vzorovou implementaci download endpointu se `is_safe_path()` validací. | **L** |
| 10 | CLAUDE.md | 448–450 § Startup | „15 migračních funkcí" — správně, ale neuvádí, že v `_ALL_MIGRATIONS` je navíc `_ensure_indexes()` + `_seed_code_lists()` + `_seed_email_templates()`. Formulace dole to zmiňuje, ale čísla nesedí s `main.py:702` (15 migrací + 3 další). | Sjednotit — uvést „15 migrací + index creation + 2 seed funkce". | **L** |
| 11 | README.md | 1069 (Datový model) | EmailTemplate — README zmiňuje `subject_template`, `body_template`. V modelu to platí, ale `placeholder {rok}` — nově z `utils.render_email_template()` podporuje libovolné proměnné (nejen rok). | Zpřesnit: „placeholder `{rok}` a další kontextové proměnné přes `render_email_template()`". | **L** |
| 12 | README.md | 74 Moduly — sidebar | Sidebar má top-level položku „Import z Excelu" (`active_nav='import'`, base.html:52), README ji v popisu modulů nevyzdvihuje samostatně. | Zmínit jako zkratku k `/vlastnici/import` v úvodu Moduly. | **L** |
| 13 | docs/UI_GUIDE.md | — | Žádné nové UI vzory z c1bc83d nevyžadují update. Inline edit nájemce v detailu prostoru používá existující info/form partial vzor (§ 4) — není třeba dokumentovat samostatně. | Bez změny. | — |
| 14 | README.md | 1149 | Zmínka „Zbývá: testy, autentizace + CSRF" v auditu #4 — mezitím testy doplněny (310 testů řádek 57). Konzistence historie. | Ponechat — historická poznámka. | — |
| 15 | CLAUDE.md | 510 (Tenants helper) | `find_existing_tenant` popsán správně, odpovídá `tenants/_helpers.py:14`. Bez změny. | OK | — |
| 16 | README.md / CLAUDE.md | — | `db.rollback()` fallback v `discrepancies.py:236` (z c1bc83d) — čistě interní fix, nevyžaduje dokumentaci. | Bez změny. | — |
| 17 | README.md / CLAUDE.md | — | `_norm_module` extrakce na module-level v `dashboard.py:32` — interní refactor, nevyžaduje dokumentaci. | Bez změny. | — |

## Souhrn

- **Celkem actionable nálezů**: 12
- **High priorita**: 5 (chybějící API endpointy v README)
- **Medium priorita**: 2 (chybějící feature popis + dashboard export)
- **Low priorita**: 5 (upřesnění formulací, příklady)
- **Informativní (bez změny)**: 5

**Hlavní téma**: Sekce „API endpointy" v README.md není plně synchronizovaná s platebním modulem a recent commity. Chybí 5 endpointů v `/platby` (soubor, export výpisů, opravené metody u matice/dlužníci) a 3 HTMX endpointy v `/prostory` pro inline edit nájemce.

CLAUDE.md a UI_GUIDE.md jsou konzistentní s kódem — c1bc83d už doplnil § Export dat URL vzor. Drobná zpřesnění formulací (priorita L).
