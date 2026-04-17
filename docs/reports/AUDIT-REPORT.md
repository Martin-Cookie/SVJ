# SVJ Audit Report -- 2026-04-17

Code Guardian -- 12. audit. Navazuje na [audit z 2026-04-12](archive/AUDIT-REPORT-2026-04-12.md). Od posledniho auditu ~20 commitu: modul vodometry (rozeslika emailu, HTML tabulka, historie spotreby, vs_prumer badge, preview toggle, search filter), bounce service (IMAP SINCE fallback, smart bounce filtering, multi-profil progress bar), scroll fixes, hx-boost opravy.

## Souhrn

- **CRITICAL**: 0
- **HIGH**: 2
- **MEDIUM**: 6
- **LOW**: 6

## Status predchozich nalezu (audit 2026-04-12)

| # | Puvodni severity | Problem | Status |
|---|------------------|---------|--------|
| 1 | HIGH | Zlomene krizove odkazy v UI_GUIDE.md | **OPRAVENO** -- odkazy jiz neobsahuji "viz CLAUDE.md" bez linku |
| 2 | MEDIUM | Deprecated TemplateResponse API v ROUTER_PATTERNS.md | **OTEVRENO** -- radek 44 stale ukazuje stary vzor (ale je to "NE" priklad v dokumentaci) |
| 3 | MEDIUM | SMTP hesla jako base64 | **OTEVRENO** -- architektonicke rozhodnuti, preneseno jako #14 |
| 4 | MEDIUM | Chybejici indexy pro SmtpProfile | **OPRAVENO** -- `ix_smtp_profiles_is_default`, `ix_tax_sessions_smtp_profile_id`, `ix_bank_statements_smtp_profile_id` pridany |
| 5 | MEDIUM | `qs()` Jinja macro duplikovano | **OTEVRENO** -- stale ve 2 sablonach, preneseno jako #11 |
| 6 | MEDIUM | Soubory v `.playwright-mcp/` | **OTEVRENO** -- 12 souboru (~5 MB), preneseno jako #12 |
| 7 | LOW | `owner_update` genericky nazev | **OTEVRENO** -- preneseno jako #13 |
| 8 | LOW | Emoji v bounce bublinkach | **OTEVRENO** -- `index.html:79,84,89` stale obsahuje emoji, preneseno jako #10 |
| 9 | LOW | Chybejici testy pro SmtpProfile | **OTEVRENO** -- preneseno jako #9 |
| 10 | LOW | Dluh vs Saldo terminologie | **CASTECNE** -- `units/detail.html`, `partials/owner_units_section.html` stale "Dluh", preneseno jako #8 |
| 11 | LOW | Inline reference bez odkazu v UI_GUIDE.md | **OPRAVENO** |

**Skore**: 4 z 11 plne opraveno, 1 castecne, 6 preneseno (vesmes LOW).

## Souhrnna tabulka -- aktualni nalezy

| # | Oblast | Soubor | Severity | Problem | Cas | Rozhodnuti |
|---|--------|--------|----------|---------|-----|------------|
| 1 | Kod / Bug | `water_meters/sending.py:763` | HIGH | SMTP profil se nepredava do background threadu -- emaily jdou vzdy pres default profil | ~10 min | opravit |
| 2 | Kod / Bug | `water_meters/sending.py:627` | HIGH | `SvjInfo` nema sloupec `smtp_profile_id` -- ulozeni SMTP profilu v nastaveni rozesliky tichy noop | ~20 min | opravit |
| 3 | Vykon | `water_meters/sending.py:519,650,714` | MEDIUM | `_build_recipients()` volano 3x nezavisle (preview, test, send) -- kazde volani nacita vsechny vodomery + odecty + vlastniky | ~20 min | opravit |
| 4 | Kod / Konvence | `water_meters/sending.py:23-25` | MEDIUM | Importy primo z `app.models.administration`, `app.models.common`, `app.models.smtp_profile` misto z `app.models` (poruseni CLAUDE.md konvence) | ~5 min | opravit |
| 5 | Bezpecnost | `water_meters/sending.py:684` | MEDIUM | Chybova zprava z SMTP vlozena do redirect URL bez URL-encodingu -- muze rozbít presmerovani pri specialnich znacich | ~5 min | opravit |
| 6 | Kod / Duplikace | `water_meters/sending.py:717-724` vs `discrepancies.py:502-509` | MEDIUM | Identicky blok "cache invalid emails" duplikovan ve 2 souborech (+ podobny vzor v `tax/_helpers.py:200-209`) -- kandidat na utility funkci | ~15 min | opravit |
| 7 | Dokumentace | `CLAUDE.md:235` | MEDIUM | Pocet migraci "25" neodpovida realite -- aktualne 25 migracnich + 3 utility = 28 polozek v `_ALL_MIGRATIONS`, a chybi `water_meters` v upload subdirectories | ~5 min | opravit |
| 8 | UI / Konzistence | `units/detail.html:25,27` + `owner_units_section.html:28` | LOW | "Dluh" misto "Saldo" -- refaktoring Dluh->Saldo nedokoncen (preneseno z #10) | ~10 min | rozhodnuti |
| 9 | Testy | `tests/test_water_meters.py` neexistuje | LOW | Novy modul vodometry (4 soubory, ~2000 radku) + bounce_service (555 radku) + rozeslika emailu bez jedineho testu | ~1-2 hod | opravit |
| 10 | UI | `bounces/index.html:79,84,89` | LOW | Emoji v bublinkach -- preneseno z predchoziho auditu #8 | ~5 min | opravit |
| 11 | Kod | `voting/index.html:18` + `payments/vypisy.html:8` | LOW | `qs()` Jinja macro duplikovano -- preneseno z #5 | ~10 min | rozhodnuti |
| 12 | Git Hygiene | `.playwright-mcp/` | LOW | 12 souboru (~5 MB) -- logy, yml snapshoty, .crx soubor z testovani | ~1 min | opravit |
| 13 | Kod / UX | `owners/crud.py:773` | LOW | `owner_update` genericky nazev -- preneseno z #7 | ~15 min | rozhodnuti |
| 14 | Bezpecnost | `smtp_profile.py:18` | LOW | SMTP hesla jako base64 -- preneseno z #3 (architektonicke rozhodnuti) | ~30 min | rozhodnuti |

Legenda: opravit = jen opravit, rozhodnuti = potreba rozhodnuti uzivatele

---

## Detailni nalezy

### 1. Kodova kvalita

#### #1 SMTP profil se nepredava do background threadu rozesliky vodomeru (HIGH)

- **Co a kde**: `app/routers/water_meters/sending.py`, radky 761-763. Funkce `_send_emails_batch` prijima volitelny parametr `smtp_profile_id` (radek 350), ale pri spusteni threadu (radek 763) se predava jen 5 pozicnich argumentu -- `smtp_profile_id` zustava `None`.
- **Dsledek**: I kdyz uzivatel vybere konkretni SMTP profil v nastaveni rozesliky, vsechny emaily se posilaji pres default SMTP server (`.env` nebo `is_default` profil).
- **Reseni**: Pridat `smtp_profile_id` jako 6. argument do `threading.Thread.args`:
  ```python
  thread = threading.Thread(
      target=_send_emails_batch,
      args=(send_id, recipients, batch_size, batch_interval, confirm_batch, smtp_profile_id),
      daemon=True,
  )
  ```
  Zaroven je treba nacteni `smtp_profile_id` pred start_batch_send -- viz nalez #2.
- **Narocnost + cas**: nizka, ~10 min
- **Zavislosti**: zavisí na #2 (SvjInfo nema smtp_profile_id)
- **Regrese riziko**: nizke -- zmena se projevuje jen pri explicitnim vyberu profilu
- **Jak otestovat**: (1) Nastavit 2 SMTP profily v `/nastaveni`. (2) Na `/vodometry/rozeslat` otevrit Konfiguraci, vybrat druhy profil, Ulozit. (3) Odeslat testovaci email. (4) Zkontrolovat v email logu ze email prisel z druheho profilu.

#### #2 SvjInfo nema sloupec smtp_profile_id -- ulozeni SMTP profilu je tichy noop (HIGH)

- **Co a kde**: `app/routers/water_meters/sending.py:627` -- `svj.smtp_profile_id = int(smtp_pid) if hasattr(svj, "smtp_profile_id") else None`. Model `SvjInfo` (v `app/models/administration.py`) nema sloupec `smtp_profile_id`. Podminka `hasattr` zabrani padu, ale hodnota se nikam neulozi.
- **Dsledek**: Vyber SMTP profilu v UI se nezachova -- pri rozeslice se pouzije vzdy default.
- **Reseni**: Dve varianty:
  - **A)** Pridat `smtp_profile_id` sloupec do `SvjInfo` (model + migrace v main.py + index v `_ensure_indexes()`). Toto je konzistentni s tim, ze `SvjInfo` uz uchovava `send_batch_size`, `send_batch_interval` atd.
  - **B)** Misto globalni volby predavat smtp_profile_id per-rozesliku jako hidden field ve formulari a z formu v `start_batch_send`. Jednoduzsi, ale neuchovava nastaveni.
  - **Doporuceni**: Varianta A -- konzistentni s existujicim vzorem pro dane (`TaxSession.smtp_profile_id`).
- **Narocnost + cas**: stredni, ~20 min (model + migrace + fix v sending.py)
- **Zavislosti**: Nalez #1 zavisi na tomto -- nejdriv vyresit #2, pak #1
- **Regrese riziko**: nizke
- **Jak otestovat**: (1) Overit ze v DB existuje sloupec `smtp_profile_id` na `svj_info`. (2) Na `/vodometry/rozeslat` vybrat profil, Ulozit. (3) Obnovit stranku -- profil musi zustat vybrany. (4) Spustit rozesliku -- emaily musi jit pres vybrany profil.

#### #3 _build_recipients() volano 3x nezavisle -- performance (MEDIUM)

- **Co a kde**: `app/routers/water_meters/sending.py` -- funkce `_build_recipients(db)` je volana na radcich 519 (preview stranky), 650 (testovaci email) a 714 (zahajeni rozesliky). Kazde volani:
  - Nacita vsechny vodomery s `joinedload(readings)`
  - Nacita vsechny OwnerUnit s `joinedload(owner, unit)`
  - Pocita `compute_deviations()` pro vsechny vodomery
  - Pocita prumery a historii pro kazdy vodomer
- **Dsledek**: Pri 100+ vodomerech a 50+ vlastnicich je to 3 identicke dotazy pri kazde rozeslice (preview -> test -> odeslani). U testu staci jeden priklad, ne cely seznam.
- **Reseni**: 
  - Pro `send_test_email`: nacist jen 1 sendable prijemce (pro preview), ne vsechny
  - Pro `start_batch_send`: nelze se vyhnout plnemu volani (filtruje se dle checkboxu)
  - Alternativne: caching vysledku `_build_recipients` s klicem (napr. posledni reading timestamp)
- **Narocnost + cas**: stredni, ~20 min
- **Zavislosti**: zadne
- **Regrese riziko**: nizke
- **Jak otestovat**: Sledovat dobu nacitani `/vodometry/rozeslat` (dev tools Network tab). S velkym poctem vodomeru by melo byt viditelne zrychleni.

#### #4 Importy primo z model souboru misto z app.models (MEDIUM)

- **Co a kde**: `app/routers/water_meters/sending.py:23-25`:
  ```python
  from app.models.administration import EmailTemplate, SvjInfo
  from app.models.common import EmailLog
  from app.models.smtp_profile import SmtpProfile
  ```
  Totez v `dashboard.py:16-17` a `tax/sending.py:23`. CLAUDE.md explicitne rika: "Routery importuji z `app.models`, nikdy z `app.models.specific_file`".
- **Reseni**: Zmenit na `from app.models import EmailTemplate, SvjInfo, EmailLog, SmtpProfile`
- **Narocnost + cas**: nizka, ~5 min
- **Zavislosti**: zadne
- **Regrese riziko**: zadne -- vsechny tyto symboly jsou exportovane z `app/models/__init__.py`
- **Jak otestovat**: `python -c "from app.models import EmailTemplate, SvjInfo, EmailLog, SmtpProfile; print('OK')"`

#### #6 Duplikovany blok "cache invalid emails" (MEDIUM)

- **Co a kde**: Identicky blok kodu (~8 radku) pro nacitani neplatnych emailu (hard bounce):
  - `water_meters/sending.py:717-724`
  - `payments/discrepancies.py:502-509`
  - Podobny (ale rafinovanejsi) vzor v `tax/_helpers.py:200-209` (`_load_bounced_emails`)
- **Reseni**: Extrahovat do sdilene utility funkce v `app/utils.py`:
  ```python
  def get_invalid_emails(db: Session) -> set[str]:
      """Nacte vsechny emailove adresy vlastniku oznacenych jako email_invalid."""
      ...
  ```
  Alternativne pouzit existujici `_load_bounced_emails` z tax/_helpers.py (ktery vraci per-owner dict) a zjednodusit na prosty set.
- **Narocnost + cas**: nizka, ~15 min
- **Zavislosti**: zadne
- **Regrese riziko**: nizke
- **Jak otestovat**: Overit ze rozeslika vodomeru a nesrovnalosti platieb stale spravne vynechavaji bounced adresy.

### 2. Bezpecnost

#### #5 Chybova zprava z SMTP vlozena do redirect URL bez URL-encodingu (MEDIUM)

- **Co a kde**: `app/routers/water_meters/sending.py:684`:
  ```python
  err = result.get("error", "neznama chyba")[:100]
  return RedirectResponse(f"/vodometry/rozeslat?flash=test_fail&err={err}", status_code=302)
  ```
  Pokud SMTP server vrati chybu obsahujici `&`, `#`, `=` nebo ne-ASCII znaky, redirect URL se rozbije.
- **Dsledek**: Neni primarne XSS (Jinja2 auto-escaping na radku 604 chrani), ale muze zpusobit:
  - Ztraceny flash message (err se orizne na prvnim `&`)
  - Broken redirect (specialni znaky v URL)
- **Reseni**: `from urllib.parse import quote; return RedirectResponse(f"...&err={quote(err)}", ...)`
- **Narocnost + cas**: nizka, ~5 min
- **Zavislosti**: zadne
- **Regrese riziko**: zadne
- **Jak otestovat**: Nastavit neplatny SMTP server (napr. port 12345) a odeslat testovaci email. Chybova zprava musi byt zobrazena uplna, bez orezani.

#### #14 SMTP hesla jako base64 (LOW -- preneseno z predchoziho auditu #3)

- **Co a kde**: `app/models/smtp_profile.py:18` -- sloupec `smtp_password_b64` uklada heslo jako base64.
- **Poznamka**: Architektonicke rozhodnuti. Pro lokalni desktop aplikaci (USB distribuce) je riziko nizke -- atakujici by musel mit pristup k souboru `svj.db`. Pro servery by se doporucovalo `Fernet` sifrovani nebo OS keyring.
- Status: preneseno bez zmeny severity.

### 3. Dokumentace

#### #7 CLAUDE.md neaktualni pocet migraci a chybejici upload subdir (MEDIUM)

- **Co a kde**: `CLAUDE.md:235` uvadi "25 migracnich funkci + `_ensure_indexes()` + `_seed_code_lists()` + `_seed_email_templates()`". Ve skutecnosti:
  - 25 migracnich funkci (**spravne**)
  - + 3 utility (indexes, code lists, email templates)
  - = **28 polozek** v `_ALL_MIGRATIONS`
  - **Ale**: Chybi `water_meters` v seznamu upload subdirectories na radku 1271 v `main.py` -- `water_meters` se pouziva v `import_readings.py:112` ale neni vytvoren v lifespan. (Funkce `mkdir(parents=True, exist_ok=True)` v import_readings to resi, ale je to nekonzistentni s ostatnimi moduly.)
  - Dalsi nesrovnalost: CLAUDE.md zminuje `upload_dir` podadresare `"excel/", "word_templates/", "scanned_ballots/", "tax_pdfs/", "csv/", "share_check/", "contracts/"` ale ne `water_meters/`.
- **Reseni**:
  1. Pridat `"water_meters"` do lifespan upload subdirectories
  2. Pridat `water_meters/` do seznamu v CLAUDE.md
- **Narocnost + cas**: nizka, ~5 min
- **Regrese riziko**: zadne

### 4. UI / Sablony

#### #8 Dluh vs Saldo terminologie (LOW -- preneseno)

- **Co a kde**: `units/detail.html:25,27` zobrazi "Dluh X Kc" misto "Saldo". `partials/owner_units_section.html:28` ma hlavicku "Dluh". Refaktoring Dluh->Saldo byl proveden v `/platby/prehled` a `/platby/dluznici`, ale nedokoncen na dalsich strankach.
- Status: preneseno z predchoziho auditu #10.

#### #10 Emoji v bounce bublinkach (LOW -- preneseno)

- **Co a kde**: `app/templates/bounces/index.html:79,84,89` -- pouziva emoji znaky (cerveny, zluty, bily krouzek) misto CSS badge.
- Status: preneseno z predchoziho auditu #8.

### 5. Vykon

#### (viz #3 vyse -- `_build_recipients` volano 3x)

Dalsi mensi nalezky:

- **`bounces.py:_module_counts()`** (radek 105-114): Nacita vsechny `EmailBounce` radky s modulem do Pythonu a pocita v cyklu. Melo by pouzit `GROUP BY`:
  ```python
  from sqlalchemy import func
  rows = db.query(EmailBounce.module, func.count(EmailBounce.id)).filter(...).group_by(EmailBounce.module).all()
  ```
  Severity: LOW (maly objem dat).

- **`bounces.py:_counts()`** (radek 95-102): 4 separatni COUNT dotazy. Dalo by se sloucit do jednoho GROUP BY. Severity: LOW.

### 6. Error Handling

Zadne kriticke nalezy. Vsechny background thready (water sending, bounce check) maji spravne try/except s logovanim. SMTP reconnect pri selhani je implementovan (radky 428-434). DB rollback v pripade chyby je korektni.

Jedina poznamka: V `_send_emails_batch` (radek 451) pri selhani `notified_at` update se provede `db.rollback()`, coz muze zrusit predchozi uspesne commity v ramci davky. Nicmene kazdy uspesny email ma svuj vlastni commit (radek 449), takze data se neztrati.

### 7. Git Hygiene

#### #12 Soubory v `.playwright-mcp/` (LOW -- preneseno)

- 12 souboru (~5 MB) vcetne 4 logu, 5 YAML snapshotu, 1 CRX souboru (Playwright extension).
- `.playwright-mcp/` je v `.gitignore`, takze se nedostane do repozitare, ale zabira misto na disku.
- Backup soubor `data/svj.db.backup-pred-vodou` (5.8 MB) je v untracked stavu -- mel by byt v `.gitignore` nebo odstranen.
- **Reseni**: `rm -rf .playwright-mcp/*.log .playwright-mcp/*.yml .playwright-mcp/*.crx`

### 8. Testy

#### #9 Chybejici testy pro nove moduly (LOW -- rozsireno)

- **Vodometry**: 4 soubory (~2050 radku) -- `overview.py`, `import_readings.py`, `sending.py`, `_helpers.py`. Zadne testy.
  - Kriticke flows k testovani: `parse_techem_xls`, `parse_unit_label`, `compute_consumption`, `compute_deviations`, `_build_recipients`, `_build_email_context`
- **Bounce service**: 555 radku -- `bounce_service.py`. Zadne testy.
  - Kriticke flows: `_parse_bounce` (RFC 3464 parsing), `_match_owner`, `humanize_reason`
- **SmtpProfile**: model + endpointy. Zadne testy (preneseno z #9).
- **Celkem**: ~2600 radku noveho kritickeho kodu (IMAP, SMTP, email parsing) bez jedineho testu.
- **Doporuceni**: Prioritne otestovat `_helpers.py` funkce (pure functions, snadno testovatelne) a `_parse_bounce` (parser s mnoha edge cases).

---

## Doporuceny postup oprav

1. **#2 + #1** (HIGH) -- Pridat `smtp_profile_id` do `SvjInfo` + opravit predavani do threadu. ~30 min, blokuje funkcnost multi-SMTP profilu pro vodometry.
2. **#5** (MEDIUM) -- URL-encode chybove zpravy. ~5 min, jednoducha oprava.
3. **#4** (MEDIUM) -- Opravit importy na `from app.models`. ~5 min.
4. **#7** (MEDIUM) -- Aktualizovat CLAUDE.md + pridat `water_meters` do lifespan upload dirs. ~5 min.
5. **#6** (MEDIUM) -- Extrahovat sdilenou utility funkci pro invalid emails. ~15 min.
6. **#3** (MEDIUM) -- Optimalizovat `_build_recipients` pro test email endpoint. ~20 min.
7. **#12** (LOW) -- Smazat `.playwright-mcp/` soubory. ~1 min.
8. **#9** (LOW) -- Napsat testy pro `_helpers.py` a `bounce_service.py`. ~1-2 hod.
9. Ostatni LOW nalezy (#8, #10, #11, #13, #14) -- naplanovat do dalsich iteraci.
