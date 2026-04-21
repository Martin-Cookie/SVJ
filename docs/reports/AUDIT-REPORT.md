# SVJ Audit Report -- 2026-04-21

Code Guardian -- 14. audit (hluboky mod, kompletni pruchod).

## Souhrn

- **CRITICAL**: 0
- **HIGH**: 3
- **MEDIUM**: 8
- **LOW**: 5

## Souhrnna tabulka

| # | Oblast | Soubor | Severity | Problem | Cas | Rozhodnuti |
|---|--------|--------|----------|---------|-----|------------|
| 1 | Vykon | app/routers/sync/session.py:208 | HIGH | N+1: Owner.units bez joinedload(OwnerUnit.unit) | ~5 min | fix |
| 2 | Testy | tests/ | HIGH | Dashboard, payments, tax -- kriticke moduly bez testu | ~2 hod | fix |
| 3 | Bezpecnost | app/ | HIGH | Zadna autentizace -- vsechny endpointy verejne | planovane | varianty |
| 4 | Kod | app/services/ | MEDIUM | 5 funkci >150 radku (payment_discrepancy, voting_import, payment_matching, space_import, excel_import) | ~1 hod | fix |
| 5 | Kod | app/main.py | MEDIUM | 1459 radku -- nejdelsi soubor, kombinuje startup + migrace | ~30 min | fix |
| 6 | Bezpecnost | app/templates/water_meters/send.html:263 | MEDIUM | XSS: preview.body\|safe -- admin-editable sablona | ~10 min | varianty |
| 7 | Error | app/services/email_service.py:325 | MEDIUM | Tichy fail: ulozeni do Sent slozky selze bez logu | ~5 min | fix |
| 8 | Error | app/services/bounce_service.py:77 | MEDIUM | Skryte preskoceni SMTP profilu s neplatnym heslem | ~5 min | fix |
| 9 | Vykon | app/routers/owners/crud.py:257-289 | MEDIUM | 4-5 count dotazu kde staci 2 | ~15 min | fix |
| 10 | Vykon | app/routers/units.py:489-505 | MEDIUM | Duplicitni count dotazy | ~10 min | fix |
| 11 | Kod | app/services/import_mapping.py:17 vs voting_import.py:176 | MEDIUM | Duplicitni read_excel_headers() | ~5 min | fix |
| 12 | Kod | app/database.py:1 | LOW | Nepouzity import text | ~1 min | fix |
| 13 | Kod | app/templates/partials/ | LOW | Nekonzistentni prefix _ u 3 partialu z 50+ | ~10 min | fix |
| 14 | Kod | app/main.py:1422-1423 | LOW | Hardcoded limity (500MB, 5000 souboru) | ~5 min | fix |
| 15 | Vykon | app/routers/administration/backups.py:224 | LOW | Backup ZIP cely v pameti (risk pro >100MB) | ~20 min | varianty |
| 16 | Kod | app/main.py:50+ | LOW | Zakomentovane migracni bloky (dokumentacni charakter) | ~10 min | fix |

## Detailni nalezy

### 1. Kodova kvalita

**#4 Dlouhe funkce (>150 radku)**
- Co a kde: `detect_discrepancies()` 246r, `preview_voting_import()` 216r, `compute_candidates()` 215r, `import_spaces_from_excel()` 198r, `import_owners_from_excel()` 180r
- Reseni: Extract-method refactoring -- rozdelit na helper funkce
- Narocnost: stredni ~1 hod celkem
- Regrese riziko: nizke (pokud se zachova API)
- Jak otestovat: pytest tests/ -- vsechny testy musi projit po refactoringu

**#5 Prilis velke soubory**
- Co a kde: main.py 1459r, statements.py 1392r, sending.py 1260r, import_mapping.py 1204r, session.py 949r
- Reseni: main.py -- oddelit migrace do app/migrations.py. Ostatni uz jsou packages.
- Narocnost: stredni ~30 min pro main.py
- Regrese riziko: nizke

**#11 Duplicitni read_excel_headers()**
- Co a kde: import_mapping.py:17 vs voting_import.py:176
- Reseni: Smazat z voting_import.py, pouzivat verzi z import_mapping
- Narocnost: nizka ~5 min
- Regrese riziko: nizke

**#12 Nepouzity import**
- Co a kde: app/database.py:1 -- `from sqlalchemy import text` se nepouziva
- Reseni: Smazat
- Narocnost: nizka ~1 min

**#13 Nekonzistentni prefix _ u partialu**
- Co a kde: 3 soubory (_send_progress_inner.html, _sort_icon.html) maji prefix, 50+ ne
- Reseni: Sjednotit -- bud vsechny s _ nebo bez
- Narocnost: nizka ~10 min

**#14 Hardcoded limity**
- Co a kde: app/main.py:1422-1423 -- 500MB, 5000 souboru
- Reseni: Presunout do app/config.py (settings)
- Narocnost: nizka ~5 min

**#16 Zakomentovane migracni bloky**
- Co a kde: app/main.py radky 50, 1005, 1135, 1151, 1207, 1309
- Reseni: Prevest do docstrings nebo smazat (historie je v gitu)
- Narocnost: nizka ~10 min

### 2. Bezpecnost

**#3 Chybejici autentizace**
- Co a kde: Cela aplikace -- zadny login, vsechny endpointy verejne
- Reseni: Planovano v docs/USER_ROLES.md (admin/board/auditor/owner)
- Varianty: (A) Session + login form, (B) OAuth/SSO, (C) Basic auth pro cloud deploy
- Narocnost: vysoka ~2-3 dny
- Regrese riziko: vysoke -- ovlivni vsechny endpointy
- Poznamka: Pro lokalni/USB nasazeni je to OK (jednouzivatelska aplikace). Kriticke az pro cloud.

**#6 XSS v email preview**
- Co a kde: app/templates/water_meters/send.html:263 -- `{{ preview.body|safe }}`
- Reseni: preview.body pochazi z render_email_template() s admin-editable sablonami. Riziko je interni (admin).
- Varianty: (A) Nechat (interni nastroj), (B) Sanitizovat pres bleach/html_sanitize
- Narocnost: nizka ~10 min pro variantu B
- Regrese riziko: nizke

### 3. Vykon

**#1 N+1 v sync/session.py**
- Co a kde: app/routers/sync/session.py:208 -- `joinedload(Owner.units)` ale chybi `.joinedload(OwnerUnit.unit)`
- Reseni: Pridat `.joinedload(OwnerUnit.unit)` do options chain
- Narocnost: nizka ~5 min
- Regrese riziko: nizke
- Jak otestovat: GET /synchronizace -- musi se nacist bez N+1 (mene SQL dotazu v logu)

**#9 Duplicitni count dotazy v owner_list**
- Co a kde: app/routers/owners/crud.py:257-289 -- 4-5 separatnich COUNT dotazu
- Reseni: Konsolidovat do 1-2 agregovanych dotazu s GROUP BY
- Narocnost: stredni ~15 min
- Jak otestovat: GET /vlastnici -- musi vracet spravne pocty

**#10 Duplicitni count dotazy v unit_list**
- Co a kde: app/routers/units.py:489-505 -- 3-4 separatnich dotazu
- Reseni: Konsolidovat
- Narocnost: nizka ~10 min

**#15 Backup ZIP v pameti**
- Co a kde: app/routers/administration/backups.py:224,282 -- `await file.read()` cely ZIP
- Reseni: Pro typicke pouziti (<50MB) je to OK. Pro vetsi: streaming pres shutil.copyfileobj
- Narocnost: stredni ~20 min
- Regrese riziko: stredni

### 4. Error Handling

**#7 Tichy fail email Sent folder**
- Co a kde: app/services/email_service.py:325 -- `except Exception: pass`
- Reseni: Pridat `logger.warning("Failed to save to Sent folder: %s", e)`
- Narocnost: nizka ~5 min
- Regrese riziko: nizke

**#8 Skryte preskoceni SMTP profilu**
- Co a kde: app/services/bounce_service.py:77 -- password decrypt failure -> continue bez logu
- Reseni: Pridat `logger.warning("Skipping SMTP profile %s: password decrypt failed", profile.id)`
- Narocnost: nizka ~5 min
- Regrese riziko: nizke

### 5. Git Hygiena

- .gitignore: kompletni, vsechny kriticke vzory pokryty
- .playwright-mcp/: prazdny adresar, OK
- Commit messages: srozumitelne, cesky, konzistentni
- Status: CISTE

### 6. Testy

**#2 Kriticke moduly bez testu**
- Co a kde: Chybi testy pro routery: dashboard, owners CRUD, units CRUD, payments CRUD, tax sending, settings_page, sync, spaces, share_check, administration
- Services bez testu: backup_service, balance_import, data_export, excel_export, excel_import, owner_service, payment_overview, pdf_extractor, pdf_generator, settlement_service, share_check_comparator, space_import, voting_import, word_parser
- Reseni: Pridat alespon smoke testy pro kriticke moduly (dashboard, payments, tax)
- Narocnost: vysoka ~2 hod pro zakladni pokryti
- Regrese riziko: nizke (pridavame testy, nemerime kod)

## Doporuceny postup oprav

1. **HIGH #1**: N+1 v sync/session.py -- 5 min fix
2. **HIGH #2**: Zakladni testy pro dashboard/payments/tax -- 2 hod
3. **HIGH #3**: Autentizace -- planovano, az pro cloud deploy
4. **MEDIUM #7,#8**: Logging do tichych except bloku -- 10 min
5. **MEDIUM #6**: XSS v email preview -- rozhodnuti uzivatele
6. **MEDIUM #9,#10**: Konsolidace count dotazu -- 25 min
7. **MEDIUM #11**: Smazat duplicitni read_excel_headers -- 5 min
8. **MEDIUM #4,#5**: Refactoring dlouhych funkci/souboru -- pristi iterace
9. **LOW**: Drobnosti (importy, limity, komentare) -- pristi iterace
