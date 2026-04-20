# SVJ Audit Report -- 2026-04-20

Code Guardian -- 13. audit. Navazuje na audit z 2026-04-17. Od posledniho auditu ~20 commitu: uklid reportu, `flash_from_params()` utility, novy sloupec "Vodom." u vlastniku, novy sloupec "Smlouva od" u prostoru, slouceny sloupec Spotreba+Odchylka u vodomeru, unit testy (test_water_meters, test_utils, test_bounce_service, test_bank_import, test_owner_exchange, test_payment_discrepancy, test_prescription_import), smoke test `/vodometry`, SMTP profil v SvjInfo + thread fix, URL encoding, emoji opravy, `get_invalid_emails` utility, dark mode pro 10 sablon.

## Souhrn

- **CRITICAL**: 0
- **HIGH**: 0
- **MEDIUM**: 0
- **LOW**: 3

Vsechny MEDIUM nalezy z predchozich auditu opraveny. Zbyva 3 LOW nalezy — kozmeticke / architektonicke.

## Status predchozich nalezu (audit 2026-04-17)

| # | Puvodni severity | Problem | Status |
|---|------------------|---------|--------|
| 1 | HIGH | SMTP profil se nepredava do background threadu | **OPRAVENO** |
| 2 | HIGH | SvjInfo nema sloupec smtp_profile_id | **OPRAVENO** |
| 3 | MEDIUM | `_build_recipients()` volano 3x nezavisle | **OPRAVENO** -- `limit=1` parametr pridan, test email pouziva `_build_recipients(db, limit=1)` |
| 4 | MEDIUM | Importy z `app.models.specific_file` v routerech | **OPRAVENO** -- vsechny routery importuji z `app.models` |
| 5 | MEDIUM | Chybova zprava bez URL-encodingu | **OPRAVENO** |
| 6 | MEDIUM | Duplikovany "cache invalid emails" blok | **OPRAVENO** -- `get_invalid_emails()` v `app/utils.py` |
| 7 | MEDIUM | CLAUDE.md neaktualni pocet migraci + chybejici upload subdir | **OPRAVENO** -- `water_meters/` pridano na radek 146, pocet 30 na radku 239 |
| 8 | LOW | "Dluh" misto "Saldo" | **OPRAVENO** -- vsechny vyskyty zmeneny na "Saldo" |
| 9 | LOW | Chybejici testy pro vodometry + bounce + SmtpProfile | **OPRAVENO** -- `test_water_meters.py` (13 testu), `test_bounce_service.py` (33 testu), `test_utils.py` rozsiren |
| 10 | LOW | Emoji v bounce bublinkach | **OPRAVENO** |
| 11 | LOW | `qs()` Jinja macro duplikovano | **OPRAVENO** -- extrahovano do `partials/qs_macro.html`, obe sablony importuji |
| 12 | LOW | Soubory v `.playwright-mcp/` | **OPRAVENO** -- smazany vsechny testovaci soubory |
| 13 | LOW | `owner_update` genericky nazev | **OPRAVENO** -- prejmenovano na `owner_contact_edit` |
| 14 | LOW | SMTP hesla jako base64 | **OTEVRENO** -- architektonicke rozhodnuti pro desktop aplikaci; preneseno jako #3 |

**Skore**: 13 z 14 opraveno, 1 architektonicke rozhodnuti (base64 hesla).

## Status nalezu z tohoto auditu

Vsechny MEDIUM nalezy identifikovane behem 13. auditu byly opraveny jeste pred finalizaci reportu:

| # | Puvodni severity | Problem | Status |
|---|------------------|---------|--------|
| 1 | MEDIUM | `_build_recipients()` 3x volani | **OPRAVENO** -- `limit` parametr, test email `limit=1` |
| 2 | MEDIUM | Importy z `app.models.specific_file` (5 mist) | **OPRAVENO** |
| 3 | MEDIUM | CLAUDE.md upload dirs + pocet migraci | **OPRAVENO** |
| 4 | LOW | Dvojity DB dotaz v `water_meters/overview.py` | **OPRAVENO** -- `_build_ctx` prijima `all_meters` parametr, handler predava |
| 5 | LOW | `flash_from_params()` adoptovana jen v 1 routeru | **OTEVRENO** -- rozhodnuti: varianta B (migrovat postupne pri dalsi uprave routeru) |
| 6 | LOW | `.playwright-mcp/` soubory + backup soubor | **OPRAVENO** -- smazano, `.gitignore` pokryva `data/svj.db.backup*` |
| 7 | LOW | `owner_update` genericky nazev | **OPRAVENO** -- prejmenovano na `owner_contact_edit` |
| 8 | LOW | "Dluh" → "Saldo" v `units/detail.html` | **OPRAVENO** |
| 9 | LOW | Chybejici testy bounce service | **OPRAVENO** -- `test_bounce_service.py` (33 testu) |
| 10 | LOW | `qs()` duplikat + SMTP base64 hesla | **CASTECNE** -- qs() opraveno, SMTP hesla = architektonicke rozhodnuti |

## Souhrnna tabulka — zbyvajici nalezy

| # | Oblast | Severity | Problem | Rozhodnuti |
|---|--------|----------|---------|------------|
| 1 | Kod / Konzistence | LOW | `flash_from_params()` pouzita jen v 1 routeru z 10 | rozhodnuti: migrovat postupne |
| 2 | Bezpecnost | LOW | SMTP hesla jako base64 (ne sifrovani) | architektonicke rozhodnuti pro offline desktop app |
| 3 | Testy | LOW | SmtpProfile CRUD endpointy bez dedickeho testu (zakladni pokryti pres smoke test `/nastaveni`) | nizka priorita |

**Celkovy stav**: Projekt je v dobrem stavu. Zadne CRITICAL, HIGH ani MEDIUM nalezy. 3 LOW nalezy jsou architektonicka/konzistencni rozhodnuti s nizkym rizikem.

## Pokryti testy

**594 testu** (561 + 33 bounce service), vsechny prochazi.

| Modul | Testovaci soubor | Testu | Stav |
|-------|-----------------|-------|------|
| Vlastnici | test_contact_import, test_owner_matcher, test_owner_exchange | 20+ | Dobre |
| Hlasovani | test_voting, test_voting_aggregation | 30+ | Dobre |
| Platby | test_payment_advanced, test_payment_matching, test_payment_discrepancy, test_bank_import, test_prescription_import | 70+ | Dobre |
| Najemci | test_tenants | 10+ | Zakladni |
| Vodometry | test_water_meters | 13 | Zakladni |
| Bounce | test_bounce_service | 33 | **Dobre** |
| Utility | test_utils | 50 | Dobre |
| Import mapping | test_import_mapping | 10+ | Zakladni |
| CSV comparator | test_csv_comparator | 20+ | Dobre |
| Backup | test_backup | 10+ | Dobre |
| Email service | test_email_service | 10+ | Zakladni |
| Smoke testy | test_smoke | 16 | Pokryva vsechny URL |

### SQLAlchemy 2.0 deprecation warnings

25 warnings z `Query.get()` — legacy API. CLAUDE.md explicitne uvadi "legacy query API (db.query())" jako projektovy vzor. Pri budoucim upgrade SQLAlchemy bude treba migrovat na `db.get(Model, id)`.

---

*Aktualizovano 2026-04-20. Vsechny nalezy overeny v aktualnim kodu.*
