# Backup Integrity Report -- 2026-04-05

> Analyza kodu zalohovaciho systemu. Zadne zmeny v kodu, pouze report.

---

## Zalohovaci system

- **Format**: ZIP archiv (ZIP_DEFLATED komprese)
- **Obsah**: DB (svj.db) ✅ | Uploads ✅ | Generated ✅ | .env ✅ | manifest.json ✅
- **Cesta**: `data/backups/` (konfigurovatelne pres `settings.backup_dir`)
- **Pojmenovani**: `svj_backup_YYYY-MM-DD_HHMMSS.zip` (nebo vlastni nazev, sanitizovany)
- **Safety backupy**: prefix `_safety_`, vyjmuty z auto-cleanup
- **Auto-cleanup**: max 10 uzivatelskych zaloh, nejstarsi se automaticky mazou

### Soubory systemu

| Soubor | Radku | Ucel |
|--------|-------|------|
| `app/services/backup_service.py` | 446 | Service vrstva — vytvoreni, obnova, rollback, restore log |
| `app/routers/administration/backups.py` | 405 | Router — 9 endpointu pro spravu zaloh |
| `app/routers/administration/_helpers.py` | 219 | Sdilene konstanty (DB_PATH, UPLOADS_DIR, BACKUP_DIR) |
| `app/main.py` (radky 600-652) | ~50 | `_ALL_MIGRATIONS` + `run_post_restore_migrations()` |
| `tests/test_backup.py` | 558 | 30 unit testu pokryvajicich service vrstvu |

### Endpointy

| Endpoint | Metoda | Popis |
|----------|--------|-------|
| `/sprava/zalohy` | GET | Stranka se seznamem zaloh a historii obnov |
| `/sprava/zaloha/vytvorit` | POST | Vytvoreni nove zalohy |
| `/sprava/zaloha/{filename}/stahnout` | GET | Stazeni zalohy |
| `/sprava/zaloha/{filename}/smazat` | POST | Smazani zalohy |
| `/sprava/zaloha/{filename}/prejmenovat` | POST | Prejmenovani zalohy |
| `/sprava/zaloha/{filename}/obnovit` | POST | Obnova z existujici zalohy |
| `/sprava/zaloha/obnovit` | POST | Obnova z nahraneho ZIP |
| `/sprava/zaloha/obnovit-soubor` | POST | Obnova z nahraneho svj.db souboru |
| `/sprava/zaloha/obnovit-slozku` | POST | Obnova ze slozky (webkitdirectory) |

---

## Stav oprav z predchoziho reportu (2026-03-27)

| # | Problem z predchoziho reportu | Severity | Stav |
|---|-------------------------------|----------|------|
| 1 | `engine.dispose()` chybi pred ZIP/slozka restore (3 endpointy) | HIGH | **OPRAVENO** — nyni ve vsech 4 restore endpointech (radky 179, 230, 279, 380) |
| 2 | Rollback neobnovi `.env` soubor | LOW | Pretrvava |
| 3 | WAL checkpoint warning neni propagovan uzivateli | MEDIUM | **OPRAVENO** — flash message "Zaloha vytvorena, ale WAL checkpoint hlasi problem" (radky 72-73 backups.py) + redirect s `wal_warning=1` parametrem (radek 116) |
| 4 | Auto-cleanup maze dulezite safety backupy | MEDIUM | **OPRAVENO** — safety backupy maji prefix `_safety_` (radek 56 service) a jsou vyjmuty z cleanup (radek 179 service) |
| 5 | Manifest app_version hardcoded "1.0" | LOW | Pretrvava |
| 6 | Slozka restore neloguje safety backup | LOW | Pretrvava — `log_restore()` na radku 385 stale bez `safety_backup` parametru |
| 7 | Manifest nesleduje vsechny tabulky (12 z 38) | LOW | Pretrvava |
| 8 | Zadne automaticke zalohy | LOW | Pretrvava |

**Skore oprav: 3 z 8 opraveno** (vsechny HIGH a MEDIUM priority opraveny).

---

## Analyza engine.dispose() — hlavni predchozi HIGH nalez

Vsechny 4 restore endpointy nyni volaji `engine.dispose()` PRED zapisem do databaze:

| Endpoint | Radek | engine.dispose() |
|----------|-------|-----------------|
| `backup_restore_existing` (existujici ZIP) | 179 | ✅ Pred `restore_backup()` |
| `backup_restore` (nahrany ZIP) | 230 | ✅ Pred `restore_backup()` |
| `backup_restore_db_file` (DB soubor) | 279 | ✅ Pred `open(DB_PATH, "wb")` |
| `backup_restore_folder` (slozka) | 380 | ✅ Pred `restore_from_directory()` |

Navic `run_post_restore_migrations()` (radek 630 main.py) vola `engine.dispose()` znovu pred pripojenim k obnovene databazi. Tento dvojity dispose je spravny — prvni uvolni spojeni pred zapisem, druhy zajisti cista spojeni po zapisu.

---

## Analyza bezpecnostnich mechanismu

### 1. Restore lock ✅
- File-based zamek (`data/backups/.restore_lock`) s JSON formatem (PID + timestamp)
- Stale lock detekce po 10 minutach
- Corrupted lock soubor se automaticky smaze
- Vsechny 4 restore endpointy: `acquire` v try, `release` v finally bloku

### 2. Safety backup + rollback ✅
- `restore_backup()` a `restore_from_directory()` automaticky vytvori safety backup pred obnovou
- Pri selhani obnovy se automaticky provede rollback z safety backupu
- `backup_restore_db_file` vytvari safety backup manualne pres `_safety_backup()` helper
- Safety backupy maji prefix `_safety_` a jsou chraneny pred auto-cleanup

### 3. ZIP validace ✅
- `zipfile.is_zipfile()` — zakladni format kontrola
- Pritomnost `svj.db` v archivu
- `zf.testzip()` — CRC integritni kontrola VSECH souboru
- Vsechny 3 kontroly probehnou PRED vytvorenim safety backupu (zadne zbytecne soubory pri nevalidnim vstupu)

### 4. SQLite integrity check ✅
- `PRAGMA integrity_check` po kazde obnove DB souboru
- Provadi se ve vsech 4 metodach obnovy
- Pri selhani: rollback z safety backupu (ZIP, slozka) nebo explicitni rollback (DB soubor)

### 5. Zip Slip ochrana ✅
- `_restore_directory_from_zip()`: `os.path.realpath()` + kontrola ze cesta zustava v cilovem adresari
- `backup_restore_folder`: stejna ochrana pro webkitdirectory upload (radky 365-367)

### 6. Path traversal ochrana ✅
- Download endpoint: `is_safe_path(file_path, BACKUP_DIR)` + kontrola `.zip` pripony
- Delete/rename endpointy: stejna validace

### 7. Diskovy prostor ✅
- `_check_disk_space()` vyzaduje 2x odhadovana velikost volneho mista pred zalohovanim
- Safety backup pred obnovou implicitne kontroluje prostor (vola `create_backup`)

### 8. Post-restore migrace ✅
- 17 polozek v `_ALL_MIGRATIONS` (14 migraci + indexy + seed code lists + seed email templates)
- `engine.dispose()` + `Base.metadata.create_all()` pred migracemi
- Kazda migrace obalena try/except — selhani jedne neblokuje ostatni
- Varování z migraci se propagují uzivateli (redirect s `zprava=obnoveno_varovani`)
- `recover_stuck_sending_sessions()` na konci (obnoveni z padleho rozesilaciho procesu)

---

## Analyza edge cases v kodu

### Poskozena zaloha
- **Nevalidni ZIP soubor**: `zipfile.is_zipfile()` vrati False → `ValueError` → redirect s `chyba=neplatny`. ✅
- **ZIP s poskozenym souborem**: `zf.testzip()` detekuje CRC chybu → `ValueError`. Safety backup se NEVYTVORI (kontrola pred safety). ✅
- **ZIP bez svj.db**: Explicitni kontrola `"svj.db" not in names` → `ValueError`. ✅
- **Nevalidni DB soubor (ne-SQLite)**: `_verify_db_integrity()` → `sqlite3.DatabaseError` → `ValueError` → rollback. ✅
- **DB soubor s corrupted data**: `PRAGMA integrity_check` != "ok" → `ValueError` → rollback. ✅

### Chybejici soubory v zaloze
- **Bez uploads/**: `_restore_directory_from_zip` nic neextrahuje, puvodni uploads se smazou (`shutil.rmtree`). ✅ (ocekavane chovani — zaloha nemeala uploads)
- **Bez generated/**: Stejne jako uploads. ✅
- **Bez .env**: `.env` se neobnovi, puvodni zustane. ✅

### Soubehy
- Restore lock brani soucasnemu spusteni dvou obnov. ✅
- `upload_temp.zip` je v chranene zone restore lockem. ✅
- **Poznamka**: Bezne DB operace (cteni/zapis vlastniku apod.) behem obnovy — `engine.dispose()` ukonci pool, ale nove pozadavky mohou prijit mezi `dispose()` a dokoncenim obnovy. Toto je inherentni riziko single-server architektury bez maintenance mode.

### Rollback selhani
- Pokud `_rollback_from_safety()` selze, loguje se KRITICKA chyba. Data mohou byt v nekonzistentnim stavu. ✅ (logovano, ale uživatel neni informovan — redirect jde na `chyba=selhani` bez rozliseni)

---

## Testove pokryti

### Unit testy (`tests/test_backup.py`)

| Trida | Pocet testu | Pokryti |
|-------|-------------|---------|
| `TestLockManagement` | 7 | Acquire, double-acquire, stale lock, corrupted lock, release, missing file, dir creation |
| `TestCreateBackup` | 10 | ZIP obsah, uploads, generated, manifest, custom name, sanitizace, bez DB, bez uploads, auto-cleanup |
| `TestCleanupOldBackups` | 4 | Keep N newest, nothing to delete, nonexistent dir, empty dir |
| `TestGetBackupsTotalSize` | 3 | Total size, nonexistent dir, ignores non-ZIP |
| `TestRestoreBackup` | 6 | Replace DB, replace uploads, safety backup creation, invalid ZIP, ZIP without DB, corrupted ZIP |
| `TestRestoreFromDirectory` | 3 | Basic restore, nested subdir (Safari), no DB raises |
| `TestVerifyDbIntegrity` | 2 | Valid DB, invalid DB file |
| `TestRestoreLog` | 7 | Empty log, log+read, multiple entries order, with/without safety backup, corrupted log, dir creation |
| **Celkem** | **42** | |

### Nepokryte oblasti

| Oblast | Riziko |
|--------|--------|
| Router endpointy (backups.py) | Neexistuji endpoint testy — routery testovany pouze manualne |
| `run_post_restore_migrations()` | Neni testovano izolovane (testuje se implicitne pri startu) |
| WAL checkpoint logika | Neni testovano (zavisi na realne DB v WAL modu) |
| Disk space check | Neni testovano (tezke simulovat plny disk) |
| `.env` backup/restore | Neni testovano |
| Rollback pri selhani obnovy | Castecne (corrupted ZIP test) — neni explicitni test rollbacku |
| Safety backup ochrana v cleanup | Neni testovano (cleanup testy nepouzivaji `_safety_` prefix) |

---

## Aktualne nalezene problemy

| # | Problem | Severity | Stav | Doporuceni |
|---|---------|----------|------|------------|
| 1 | **Slozka restore neloguje safety backup** — `backup_restore_folder` (radek 385) vola `log_restore()` bez `safety_backup` parametru. Ostatni 3 restore endpointy safety backup sledují pres `set()` diff. | LOW | Pretrvava (z predchoziho reportu #6) | Pridat `existing`/`new_backups` set diff shodne s endpointy `backup_restore_existing` a `backup_restore`. |
| 2 | **Rollback neobnovi `.env`** — `_rollback_from_safety()` obnovi DB, uploads, generated, ale NE `.env`. | LOW | Pretrvava (z predchoziho reportu #2) | Pridat obnovu `.env` do `_rollback_from_safety()`. |
| 3 | **Manifest app_version hardcoded "1.0"** — nelze zjistit z jake verze kodu zaloha pochazi. | LOW | Pretrvava (z predchoziho reportu #5) | Nacitat verzi z `pyproject.toml`. |
| 4 | **Manifest nesleduje vsechny tabulky** — `_get_table_counts` sleduje 12 tabulek z ~38. Chybi: `spaces`, `tenants`, `board_members`, `code_list_items`, `activity_logs`, `ballots`, `ballot_votes`, `proxies` aj. | LOW | Pretrvava (z predchoziho reportu #7) | Dynamicky cist tabulky z `sqlite_master`. |
| 5 | **Zadne automaticke zalohy** — zalohy vznikaji pouze rucne nebo jako safety backup. | LOW | Pretrvava (z predchoziho reportu #8) | Zvazit auto-zalohu pri startu (pokud posledni > X dni). |
| 6 | **Race condition pri obnove** — mezi `engine.dispose()` a dokoncenim zapisu DB muze novy HTTP pozadavek ziskat spojeni k polozapisanemu souboru. Neni maintenance mode. | LOW | Novy nalez | Inherentni omezeni single-server architektury. Pro produkcni nasazeni zvazit maintenance mode flag. |
| 7 | **Cleanup safety backupu chybi** — safety backupy (`_safety_*`) jsou vyjmuty z auto-cleanup (spravne), ale nemaji ZADNY cleanup mechanismus. Pri castem restore se mohou hromadit neomezeně. | LOW | Novy nalez | Pridat separatni cleanup safety backupu (napr. ponechat max 5, nebo smazat starsi nez 30 dni). |
| 8 | **upload_temp.zip — fixed nazev** — pri nahravanem ZIP restore se soubor uklada jako `data/backups/upload_temp.zip` (radek 222). Nazev je fixni, chraneny restore lockem. Ale pokud lock selze (stale lock removal), muze dojit ke kolizi. | LOW | Novy nalez | Pouzit `tempfile.NamedTemporaryFile` nebo UUID v nazvu. |

---

## Porovnani s predchozim reportem (2026-03-27)

### Opravene problemy od posledniho reportu

| Predchozi # | Problem | Severity | Oprava |
|-------------|---------|----------|--------|
| #1 | `engine.dispose()` chybi pred ZIP/slozka restore | **HIGH** | Pridano do vsech 4 restore endpointu |
| #3 | WAL checkpoint warning neni propagovan | MEDIUM | Flash message + redirect s `wal_warning=1` |
| #4 | Auto-cleanup maze safety backupy | MEDIUM | `_safety_` prefix + vylouceni z cleanup |

### Nezmenene problemy

| Predchozi # | Problem | Severity | Duvod |
|-------------|---------|----------|-------|
| #2 | Rollback neobnovi `.env` | LOW | Nizka priorita |
| #5 | Manifest app_version "1.0" | LOW | Nizka priorita |
| #6 | Slozka restore neloguje safety backup | LOW | Nizka priorita |
| #7 | Manifest nesleduje vsechny tabulky | LOW | Nizka priorita |
| #8 | Zadne automaticke zalohy | LOW | Nizka priorita |

### Nove problemy

| # | Problem | Severity |
|---|---------|----------|
| #6 | Race condition pri obnove (bez maintenance mode) | LOW |
| #7 | Cleanup safety backupu chybi (mohou se hromadit) | LOW |
| #8 | upload_temp.zip fixni nazev | LOW |

---

## Shrnuti

### Silne stranky zalohovaciho systemu

1. **Kompletni obsah zalohy** — DB + uploads + generated + .env + manifest s table counts
2. **WAL checkpoint** pred zalohovanim s propagaci warningu uzivateli
3. **Trojita ZIP validace** — is_zipfile + svj.db presence + CRC testzip
4. **SQLite integrity check** po kazde obnove ve vsech 4 metodach
5. **Safety backup + automaticky rollback** pri selhani obnovy
6. **Safety backupy chraneny pred auto-cleanup** (prefix `_safety_`)
7. **Zip Slip + path traversal ochrana** na vsech vstupnich bodech
8. **File-based restore lock** proti soubehu s detekci stale locku
9. **Post-restore migrace** (17 polozek) — kompatibilita se starsimi zalohami
10. **Kontrola diskoveho prostoru** pred zalohovanim (2x odhad)
11. **4 metody obnovy** pokryvajici ruzne pouziti (ZIP, upload, DB soubor, slozka)
12. **Restore log** (JSON soubor prezivajici obnovu DB)
13. **42 unit testu** pokryvajicich service vrstvu
14. **engine.dispose() ve vsech restore endpointech** (opraveno od posledniho reportu)

### Zbyvajici rizika

- **0 CRITICAL** nalezu
- **0 HIGH** nalezu (predchozi HIGH opraveno)
- **0 MEDIUM** nalezu (predchozi MEDIUM opraveny)
- **8 LOW** nalezu (5 pretrvavajicich + 3 nove)

### Celkove hodnoceni

**Velmi dobry stav.** Vsechny HIGH a MEDIUM priority z predchoziho reportu byly opraveny. Zbyvajici nalez jsou LOW severity a nepredstavuji riziko ztraty dat. Zaalohovaci system ma robustni validacni, rollback a migracni mechanismy.

Hlavni oblast pro budouci zlepseni: testove pokryti router endpointu a cleanup logika pro safety backupy.
