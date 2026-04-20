# SVJ Audit Report -- 2026-04-20

Code Guardian -- 13. audit. Navazuje na audit z 2026-04-17. Od posledniho auditu ~15 commitu: uklid reportu, `flash_from_params()` utility, novy sloupec "Vodom." u vlastniku, novy sloupec "Smlouva od" u prostoru, slouceny sloupec Spotreba+Odchylka u vodomeru, unit testy (test_water_meters, test_utils), smoke test `/vodometry`, SMTP profil v SvjInfo + thread fix, URL encoding, emoji opravy, `get_invalid_emails` utility.

## Souhrn

- **CRITICAL**: 0
- **HIGH**: 0
- **MEDIUM**: 3
- **LOW**: 7

## Status predchozich nalezu (audit 2026-04-17)

| # | Puvodni severity | Problem | Status |
|---|------------------|---------|--------|
| 1 | HIGH | SMTP profil se nepredava do background threadu | **OPRAVENO** -- `sending.py:761` nyni predava `smtp_profile_id` jako 6. argument |
| 2 | HIGH | SvjInfo nema sloupec smtp_profile_id | **OPRAVENO** -- sloupec pridan v modelu (`administration.py:31`) + migrace `_migrate_bounce_smtp_profile` |
| 3 | MEDIUM | `_build_recipients()` volano 3x nezavisle | **OTEVRENO** -- stale 3 volani na radcich 519, 652, 716; preneseno jako #1 |
| 4 | MEDIUM | Importy z `app.models.specific_file` v routerech | **CASTECNE** -- `water_meters/sending.py` opraveno, ale 5 mist stale porusuje konvenci; preneseno jako #2 |
| 5 | MEDIUM | Chybova zprava bez URL-encodingu | **OPRAVENO** -- `sending.py:686` pouziva `quote(err)` |
| 6 | MEDIUM | Duplikovany "cache invalid emails" blok | **OPRAVENO** -- `get_invalid_emails()` extrahovano do `app/utils.py:189`, pouzito v `discrepancies.py` i `sending.py`. Pozn.: `tax/_helpers.py` ma odlisnou `_load_bounced_emails` (per-owner dict z EmailBounce tabulky) -- jiny semanticky ucel, neni duplikat |
| 7 | MEDIUM | CLAUDE.md neaktualni pocet migraci + chybejici upload subdir | **CASTECNE** -- `water_meters/` pridano do lifespan (`main.py:1290`), ale: (a) CLAUDE.md radek 146 stale neobsahuje `water_meters/` v seznamu upload podadresaru, (b) pocet migraci v CLAUDE.md je 27 ale skutecnost je 30; preneseno jako #3 |
| 8 | LOW | "Dluh" misto "Saldo" | **CASTECNE** -- `owner_units_section.html` opraveno na "Saldo", ale `units/detail.html:25,27` stale zobrazuje "Dluh"; preneseno jako #8 |
| 9 | LOW | Chybejici testy pro vodometry + bounce + SmtpProfile | **CASTECNE** -- pridany testy `test_water_meters.py` (197 radku, 13 testu) a `test_utils.py` (119 radku, 15 testu). Bounce service a SmtpProfile stale bez testu; preneseno jako #9 |
| 10 | LOW | Emoji v bounce bublinkach | **OPRAVENO** -- `bounces/index.html` jiz neobsahuje emoji znaky |
| 11 | LOW | `qs()` Jinja macro duplikovano | **OTEVRENO** -- stale v `voting/index.html:18` a `payments/vypisy.html:8`; preneseno jako #10 |
| 12 | LOW | Soubory v `.playwright-mcp/` | **ZLEPSENO** -- z 12 souboru (~5 MB) na 2 soubory (~32 KB). Stale pritomne `snap1.md`, `snap2.md`; preneseno jako #6 |
| 13 | LOW | `owner_update` genericky nazev | **OTEVRENO** -- preneseno jako #7 |
| 14 | LOW | SMTP hesla jako base64 | **OTEVRENO** -- architektonicke rozhodnuti; preneseno jako #10 |

**Skore**: 5 z 14 plne opraveno, 4 castecne/zlepseno, 5 preneseno beze zmeny.

## Souhrnna tabulka -- aktualni nalezy

| # | Oblast | Soubor | Severity | Problem | Cas | Rozhodnuti |
|---|--------|--------|----------|---------|-----|------------|
| 1 | Vykon | `water_meters/sending.py:519,652,716` | MEDIUM | `_build_recipients()` volano 3x nezavisle -- preview, test, send (preneseno z #3) | ~20 min | opravit |
| 2 | Kod / Konvence | `dashboard.py:16-17`, `import_readings.py:20`, `discrepancies.py:96`, `tax/sending.py:23` | MEDIUM | Importy z `app.models.specific_file` misto z `app.models` (preneseno z #4, rozsireno) | ~5 min | opravit |
| 3 | Dokumentace | `CLAUDE.md:146,236` | MEDIUM | (a) Upload podadresar `water_meters/` chybi v seznamu, (b) pocet migraci 27 neodpovida realite 30 | ~5 min | opravit |
| 4 | Vykon | `water_meters/overview.py:154` | LOW | `_build_ctx()` nacita VSECHNY vodomery separatnim dotazem pro bubble counts, i kdyz `_filter_meters()` uz nactena filtrovanou sadu | ~15 min | opravit |
| 5 | Kod / Konzistence | 1 router vs 9 routeru | LOW | `flash_from_params()` pouzita jen ve `water_meters/overview.py`, 9 dalsich routeru pouziva manualni flash vzor | ~30 min | rozhodnuti |
| 6 | Git Hygiene | `.playwright-mcp/` | LOW | 2 soubory (snap1.md, snap2.md) z testovani -- smazat (preneseno z #12) | ~1 min | opravit |
| 7 | Kod / UX | `owners/crud.py:782` | LOW | `owner_update` genericky nazev endpointu (preneseno z #13) | ~15 min | rozhodnuti |
| 8 | UI / Konzistence | `units/detail.html:25,27` | LOW | "Dluh" misto "Saldo" -- zbyvajici misto z nedokonceneho refaktoringu (preneseno z #8) | ~5 min | rozhodnuti |
| 9 | Testy | — | LOW | Bounce service (~555 radku) a SmtpProfile stale bez testu; vodoměry maji zakladni pokryti (preneseno z #9) | ~1-2 hod | opravit |
| 10 | Kod / Konvence | Dva nezavisle nalezy | LOW | (a) `qs()` macro duplikovano v 2 sablonach (preneseno z #11), (b) SMTP hesla jako base64 (preneseno z #14) | ~10+30 min | rozhodnuti |

Legenda: opravit = jen opravit, rozhodnuti = potreba rozhodnuti uzivatele

---

## Detailni nalezy

### 1. Kodova kvalita

#### #2 Importy z app.models.specific_file misto z app.models (MEDIUM -- preneseno, rozsireno)

- **Co a kde**: CLAUDE.md explicitne rika: "Routery importuji z `app.models`, nikdy z `app.models.specific_file`". Poruseni na 5 mistech:
  - `app/routers/dashboard.py:16` — `from app.models.voting import Ballot, BallotStatus, BallotVote`
  - `app/routers/dashboard.py:17` — `from app.models.tax import TaxDocument, TaxSession, TaxDistribution, EmailDeliveryStatus`
  - `app/routers/water_meters/import_readings.py:20` — `from app.models.administration import SvjInfo`
  - `app/routers/payments/discrepancies.py:96` — `from app.models.smtp_profile import SmtpProfile` (uvnitr funkce)
  - `app/routers/tax/sending.py:23` — `from app.models.smtp_profile import SmtpProfile`
- **Poznamka**: V minulem auditu bylo nahlaseno 3 mista v `water_meters/sending.py` -- ty jsou opraveny. Zbyvajici 5 mist pretrva. Navic `app/main.py` ma vice takych importu (radky 416, 417, 557, 937, 1129, 1145, 1162), ale CLAUDE.md konvence se explicitne vztahuje na "routery", ne na `main.py` (kde importy v migracich jsou akceptovatelne).
- **Reseni**: Zmenit vsech 5 importu na `from app.models import ...`. Vsechny symboly jsou exportovane z `app/models/__init__.py`.
- **Narocnost + cas**: nizka, ~5 min
- **Zavislosti**: zadne
- **Regrese riziko**: zadne
- **Jak otestovat**: `python -m pytest tests/ -x` — vsechny testy musi projit.

#### #5 flash_from_params() adoptovana jen v 1 z 10 routeru (LOW -- novy)

- **Co a kde**: Nova utility `flash_from_params()` (pridana v commitu ef17d65) je pouzita jen v `water_meters/overview.py`. Dalsich 9 routeru pouziva manualni vzor:
  - `payments/prescriptions.py:378-380`
  - `payments/settlement.py:142-143, 222-223`
  - `payments/discrepancies.py:357`
  - `payments/symbols.py:96-97`
  - `payments/balances.py:162-163`
  - `payments/statements.py:699-701`
  - `settings_page.py:140`
  - `water_meters/import_readings.py:80-81`
  - `water_meters/sending.py:593`
  - `administration/backups.py:71`
- **Dsledek**: Nekonzistence — dva ruzne vzory pro stejnou operaci. Manualni vzor je vice kodu a nachylnejsi k chybam (zapomenute typy, chybejici defaulty).
- **Reseni**: Dve varianty:
  - **A)** Postupne migrovat vsechny routery na `flash_from_params()` (vic prace, ale jednotny vzor)
  - **B)** Nechat koexistovat — `flash_from_params` je doporuceny pro nove kody, stare se nemigruji
  - **Doporuceni**: Varianta B (pragmaticke) — migrovat jen pri pristi uprave daneho routeru
- **Narocnost + cas**: A) stredni, ~30 min; B) zadna
- **Zavislosti**: zadne
- **Regrese riziko**: nizke
- **Jak otestovat**: Otevrit dotcenou stranku, vyvolat flash zpravu (napr. import, smazani), overit ze se zobrazi spravne.

#### #7 owner_update genericky nazev (LOW -- preneseno z #13)

- **Co a kde**: `app/routers/owners/crud.py:782` — funkce `owner_update` je genericky nazev ktery nerika co updatuje. Ostatni endpointy v modulu maji specifictejsi nazvy (`owner_identity_update`, `owner_contact_update`, `owner_merge`).
- Status: preneseno bez zmeny severity.

### 2. Bezpecnost

Zadne nove nalezy. Predchozi nalezy #1 (SMTP thread) a #5 (URL encoding) opraveny.

SMTP hesla jako base64 (#14) — architektonicke rozhodnuti pro desktop aplikaci. Preneseno jako soucast #10.

### 3. Dokumentace

#### #3 CLAUDE.md neaktualni udaje (MEDIUM -- preneseno, rozsireno)

- **Co a kde**: Dva nesoulady v `CLAUDE.md`:
  1. **Radek 146**: Upload podadresare neobsahuji `water_meters/`. Seznam: `excel/, word_templates/, scanned_ballots/, tax_pdfs/, csv/, share_check/, contracts/`. Pritom `main.py:1290` jiz `water_meters` vytvari a modul ho pouziva.
  2. **Radek 236**: Uvadi "27 migracnich funkci" ale `_ALL_MIGRATIONS` v `main.py` obsahuje **27 migracnich funkci + 3 utility = 30 polozek celkem**. Posledni 3 pridane migrace (`water email template v3`, `water email template v4`, `bounce smtp_profile_name`) nejsou v poctu zohledneny.
- **Reseni**:
  1. Pridat `water_meters/` do seznamu na radku 146
  2. Aktualizovat pocet na radku 236 na 30 (nebo "27 migracnich + 3 utility = 30 polozek")
- **Narocnost + cas**: nizka, ~5 min
- **Zavislosti**: zadne
- **Regrese riziko**: zadne
- **Jak otestovat**: Vizualni kontrola CLAUDE.md vs skutecny stav (`main.py` radky 1195-1226 a 1290).

### 4. UI / Sablony

#### #8 "Dluh" misto "Saldo" v units/detail.html (LOW -- preneseno)

- **Co a kde**: `app/templates/units/detail.html:25,27` — zobrazuje "Dluh X Kc" misto "Saldo". Refaktoring Dluh→Saldo byl proveden na ostatnich strankach (vcetne `owner_units_section.html` ktera nyni rika "Saldo"), ale `units/detail.html` zustava s puvodni terminologii.
- **Reseni**: Zmenit "Dluh" na "Saldo" v obou radcich (25 a 27). Badge barvy zustanou stejne (zluty pro kladne, cerveny pro zaporne saldo).
- **Narocnost + cas**: nizka, ~5 min
- **Regrese riziko**: zadne (jen textova zmena)

### 5. Vykon

#### #1 _build_recipients() volano 3x nezavisle (MEDIUM -- preneseno z #3)

- **Co a kde**: `app/routers/water_meters/sending.py` — funkce `_build_recipients(db)` je volana na radcich:
  - 519 (preview stranky)
  - 652 (testovaci email)
  - 716 (zahajeni rozesliky)
  Kazde volani nacita vsechny vodomery, odecty, vlastniky a pocita odchylky.
- **Reseni**: Pro `send_test_email` (radek 652): nacist jen 1 sendable prijemce, ne vsechny. Staci omezit dotaz na `LIMIT 1`. Pro `preview` a `send` nelze zjednodusit (oba potrebuji kompletni seznam).
- **Narocnost + cas**: nizka, ~20 min
- **Zavislosti**: zadne
- **Regrese riziko**: nizke
- **Jak otestovat**: Odeslat testovaci email z `/vodometry/rozeslat` — musi fungovat identicky jako pred zmenou.

#### #4 Dvojity dotaz v water_meters/overview.py (LOW -- novy)

- **Co a kde**: `app/routers/water_meters/overview.py` — handler `water_meters_overview`:
  1. Radek 199: vola `_filter_meters(db, ...)` ktery nacte filtrované vodomery s readings + unit + owner (plny dotaz s JOIN a eager loading)
  2. Radek 201: vola `_build_ctx(request, meters, db)` ktery na radku 154 provede **DALSI** `db.query(WaterMeter).options(joinedload(WaterMeter.readings)).all()` — nacte VSECHNY vodomery znovu pro bubble counts a odchylky
  Celkem 2 separatni plne dotazy na kazdy page load.
- **Dsledek**: Pri 100+ vodomerech je to zbytecna zatez. Navic odchylky se pocitaji z `all_loaded` (vsechny vodomery), ale v sablone se zobrazi jen pro filtrovane — nekonzistence.
- **Reseni**: Refaktorovat `_build_ctx` aby prijimal `all_meters` jako parametr. V handleru volat `_filter_meters(db, ...)` pro vsechny (bez filtru) jednou, pak filtrovat v Pythonu. Nebo oddelit bubble counts do separatni lehke funkce (jen `COUNT + GROUP BY` bez eager loading).
- **Narocnost + cas**: stredni, ~15 min
- **Zavislosti**: zadne
- **Regrese riziko**: nizke
- **Jak otestovat**: Nacist `/vodometry` — bubble counts a tabulka musi odpovidat. Kliknout na bublinu (napr. "SV") — filtr musi fungovat, pocty zustanou.

### 6. Error Handling

Zadne nove nalezy. Exception handling v novem kodu je korektni — vsechny `except Exception:` bloky v `sending.py` maji `logger.warning()` nebo `logger.error()`. Background thread ma spravne try/except s DB rollback.

### 7. Git Hygiene

#### #6 Soubory v .playwright-mcp/ (LOW -- preneseno, zlepseno)

- **Co a kde**: `.playwright-mcp/` obsahuje 2 soubory (`snap1.md`, `snap2.md`, celkem ~32 KB) z testovani. V predchozim auditu to bylo 12 souboru / ~5 MB — vyznamne zlepseni.
- **Dalsi poznamka**: Soubor `data/svj.db.backup-pred-vodou` (5.8 MB) je v untracked stavu. `.gitignore` neobsahuje vzor pro `data/*.backup*` ani `data/svj.db.*` (mimo `-shm` a `-wal`). Soubor se do repozitare nedostane (neni staged), ale mel by byt v `.gitignore` nebo odstranen.
- **Reseni**: `rm -rf .playwright-mcp/snap*.md` a bud smazat `data/svj.db.backup-pred-vodou` nebo pridat `data/svj.db.backup*` do `.gitignore`.
- **Narocnost + cas**: nizka, ~1 min

### 8. Testy

#### #9 Chybejici testy pro bounce service a SmtpProfile (LOW -- preneseno, castecne zlepseno)

- **Co a kde**: Od posledniho auditu pribyly:
  - `tests/test_water_meters.py` — 13 testu pro `parse_unit_label`, `normalize_unit_label`, `compute_consumption`, `compute_deviations` + 5 smoke testu pro endpoints. **Dobre pokryti helperu.**
  - `tests/test_utils.py` — 15 testu pro `flash_from_params`, `strip_diacritics`, `fmt_num`, `is_valid_email`. **Dobre pokryti utility funkci.**
  - `tests/test_smoke.py` — pridan `/vodometry` do parametrizovanych smoke testu.
  Stale chybi:
  - **Bounce service** (`app/services/bounce_service.py`, ~555 radku) — `_parse_bounce`, `_match_owner`, `humanize_reason`. Kriticke funkce pro IMAP bounce parsing.
  - **SmtpProfile** — model + CRUD endpointy bez testu.
- **Celkovy stav testu**: 382 testu, vsechny prochazi (15.36s). Zadne failures, 25 deprecation warnings (SQLAlchemy 2.0 `Query.get()`).
- **Doporuceni**: Prioritne otestovat `_parse_bounce` a `humanize_reason` z bounce_service (pure functions, snadno testovatelne). SmtpProfile CRUD testy nizsi priorita.

#### Celkove pokryti modulu

| Modul | Testy | Stav |
|-------|-------|------|
| Vlastnici (owners) | test_contact_import, test_owner_matcher | Zakladni |
| Hlasovani (voting) | test_voting, test_voting_aggregation | Dobre |
| Platby (payments) | test_payment_advanced, test_payment_matching | Dobre |
| Najemci (tenants) | test_tenants | Zakladni |
| Vodometry (water_meters) | test_water_meters | **Nove** — zakladni |
| Utility (utils) | test_utils | **Nove** — dobre |
| Import mapping | test_import_mapping | Zakladni |
| CSV comparator | test_csv_comparator | Dobre |
| Backup | test_backup | Dobre |
| Email service | test_email_service | Zakladni |
| Smoke testy | test_smoke | 16 URL testu |
| Bounce service | — | **Chybi** |
| SmtpProfile | — | **Chybi** |
| Synchronizace | — | Chybi |
| Dane (tax) | — | Chybi |
| Share check | — | Chybi |
| Spaces (prostory) | — | Chybi |

### Drobne nalezky (neni v souhrnne tabulce)

#### qs() macro duplikovano ve 2 sablonach (LOW -- preneseno z #11)

- `app/templates/voting/index.html:18` a `app/templates/payments/vypisy.html:8` — stejna `{% macro qs(pairs) %}` logika.
- Status: preneseno, nizka priorita. Mozne reseni: extrahovat do partials.

#### SMTP hesla jako base64 (LOW -- preneseno z #14)

- `app/models/smtp_profile.py:18` — base64 obfuskace misto sifrovani.
- Status: architektonicke rozhodnuti pro desktop aplikaci, preneseno bez zmeny.

#### SQLAlchemy 2.0 deprecation warnings

- 25 warnings z `Query.get()` — legacy API ktera bude odstranena v SQLAlchemy 3.0. CLAUDE.md explicitne uvadi "legacy query API (db.query())" jako projektovy vzor, takze to neni bug, ale pri budoucim upgrade SQLAlchemy bude treba migrovat na `db.get(Model, id)`.

---

## Doporuceny postup oprav

1. **#3** (MEDIUM) -- Aktualizovat CLAUDE.md: upload podadresare + pocet migraci. ~5 min.
2. **#2** (MEDIUM) -- Opravit importy na `from app.models` v 5 souborech. ~5 min.
3. **#1** (MEDIUM) -- Optimalizovat `_build_recipients` pro test email (LIMIT 1). ~20 min.
4. **#6** (LOW) -- Smazat `.playwright-mcp/` soubory + resit backup soubor. ~1 min.
5. **#4** (LOW) -- Refaktorovat dvojity dotaz v overview.py. ~15 min.
6. **#8** (LOW) -- Zmenit "Dluh" na "Saldo" v units/detail.html. ~5 min.
7. **#9** (LOW) -- Napsat testy pro bounce_service.py. ~1-2 hod.
8. Ostatni LOW nalezy (#5, #7, #10) -- naplanovat do dalsich iteraci nebo migrovat postupne.
