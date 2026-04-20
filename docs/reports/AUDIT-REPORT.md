# SVJ Audit Report -- 2026-04-20

Code Guardian -- 13. audit (aktualizace). Vsechny 3 zbyvajici LOW nalezy opraveny.

## Souhrn

- **CRITICAL**: 0
- **HIGH**: 0
- **MEDIUM**: 0
- **LOW**: 0

Vsechny nalezy z predchozich auditu opraveny. Zadne otevrene problemy.

## Status predchozich nalezu (audit 2026-04-17)

| # | Puvodni severity | Problem | Status |
|---|------------------|---------|--------|
| 1 | HIGH | SMTP profil se nepredava do background threadu | **OPRAVENO** |
| 2 | HIGH | SvjInfo nema sloupec smtp_profile_id | **OPRAVENO** |
| 3 | MEDIUM | `_build_recipients()` volano 3x nezavisle | **OPRAVENO** -- `limit=1` parametr |
| 4 | MEDIUM | Importy z `app.models.specific_file` v routerech | **OPRAVENO** |
| 5 | MEDIUM | Chybova zprava bez URL-encodingu | **OPRAVENO** |
| 6 | MEDIUM | Duplikovany "cache invalid emails" blok | **OPRAVENO** -- `get_invalid_emails()` |
| 7 | MEDIUM | CLAUDE.md neaktualni pocet migraci + chybejici upload subdir | **OPRAVENO** |
| 8 | LOW | "Dluh" misto "Saldo" | **OPRAVENO** |
| 9 | LOW | Chybejici testy pro vodometry + bounce + SmtpProfile | **OPRAVENO** -- `test_smtp_profile.py` (19 testu) pridano |
| 10 | LOW | Emoji v bounce bublinkach | **OPRAVENO** |
| 11 | LOW | `qs()` Jinja macro duplikovano | **OPRAVENO** |
| 12 | LOW | Soubory v `.playwright-mcp/` | **OPRAVENO** |
| 13 | LOW | `owner_update` genericky nazev | **OPRAVENO** |
| 14 | LOW | SMTP hesla jako base64 | **OPRAVENO** -- migrace na Fernet sifrovani (cryptography) |

**Skore**: 14 z 14 opraveno.

## Status nalezu z 13. auditu

| # | Puvodni severity | Problem | Status |
|---|------------------|---------|--------|
| 1 | MEDIUM | `_build_recipients()` 3x volani | **OPRAVENO** |
| 2 | MEDIUM | Importy z `app.models.specific_file` (5 mist) | **OPRAVENO** |
| 3 | MEDIUM | CLAUDE.md upload dirs + pocet migraci | **OPRAVENO** |
| 4 | LOW | Dvojity DB dotaz v `water_meters/overview.py` | **OPRAVENO** |
| 5 | LOW | `flash_from_params()` adoptovana jen v 1 routeru | **OPRAVENO** -- migrovano do vsech 9 routeru |
| 6 | LOW | `.playwright-mcp/` soubory + backup soubor | **OPRAVENO** |
| 7 | LOW | `owner_update` genericky nazev | **OPRAVENO** |
| 8 | LOW | "Dluh" → "Saldo" v `units/detail.html` | **OPRAVENO** |
| 9 | LOW | Chybejici testy bounce service | **OPRAVENO** |
| 10 | LOW | `qs()` duplikat + SMTP base64 hesla | **OPRAVENO** |

## Souhrnna tabulka — zbyvajici nalezy

Zadne otevrene nalezy.

**Celkovy stav**: Projekt je v dobrem stavu. Vsechny nalezy ze vsech auditu opraveny.

## Pokryti testy

**580 testu**, vsechny prochazi.

| Modul | Testovaci soubor | Testu | Stav |
|-------|-----------------|-------|------|
| Vlastnici | test_contact_import, test_owner_matcher, test_owner_exchange | 20+ | Dobre |
| Hlasovani | test_voting, test_voting_aggregation | 30+ | Dobre |
| Platby | test_payment_advanced, test_payment_matching, test_payment_discrepancy, test_bank_import, test_prescription_import | 70+ | Dobre |
| Najemci | test_tenants | 10+ | Zakladni |
| Vodometry | test_water_meters | 13 | Zakladni |
| Bounce | test_bounce_service | 33 | Dobre |
| SMTP profily | test_smtp_profile | 19 | **Dobre** |
| Utility | test_utils | 50 | Dobre |
| Import mapping | test_import_mapping | 10+ | Zakladni |
| CSV comparator | test_csv_comparator | 20+ | Dobre |
| Backup | test_backup | 10+ | Dobre |
| Email service | test_email_service | 10+ | Zakladni |
| Smoke testy | test_smoke | 16 | Pokryva vsechny URL |

### SQLAlchemy 2.0 deprecation warnings

35 warnings z `Query.get()` — legacy API. CLAUDE.md explicitne uvadi "legacy query API (db.query())" jako projektovy vzor.

---

*Aktualizovano 2026-04-20. Vsechny nalezy overeny a opraveny.*
