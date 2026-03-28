# Backup Integrity Report -- 2026-03-27

## Zalohovaci system

- **Format**: ZIP archiv (ZIP_DEFLATED komprese)
- **Obsah**: DB (svj.db) ++ | Uploads ++ | Generated ++ | .env ++ | manifest.json ++
- **Cesta**: `data/backups/` (relativne k rootu projektu)
- **Pojmenovani**: `svj_backup_YYYY-MM-DD_HHMMSS.zip` (nebo vlastni nazev, sanitizovany)
- **Auto-cleanup**: max 10 zaloh, nejstarsi se automaticky mazou
- **Velikost**: celkova velikost vsech zaloh zobrazena v UI

---

## Analyza zalohovaciho kodu

### Soubory

- **Service**: `app/services/backup_service.py` (415 radku)
- **Router**: `app/routers/administration/backups.py` (384 radku)
- **Helpers**: `app/routers/administration/_helpers.py` (cesty DB_PATH, UPLOADS_DIR atd.)
- **Post-restore migrace**: `app/main.py` (`run_post_restore_migrations`, radky 546-577)

### Proces vytvoreni zalohy (`create_backup`)

1. **Kontrola diskoveho prostoru** -- `_check_disk_space()` overuje, ze na disku je alespon 2x odhadovana velikost dat volneho mista. Pokud ne, vyhodi `OSError`.
2. **WAL checkpoint** -- pred zalohovanim provede `PRAGMA wal_checkpoint(TRUNCATE)` na SQLite databazi, cimz se vsechna cekajici data z WAL souboru zapisi do hlavniho DB souboru. Pri selhani pokracuje s warningem.
3. **Tvorba ZIP**:
   - `svj.db` -- databaze (ulozena jako `svj.db` v rootu ZIP)
   - `uploads/` -- vsechny upload soubory (Excel, PDF, CSV, DOCX) zachovane s relativnimi cestami
   - `generated/` -- generovane soubory (hlasovaci listky PDF apod.)
   - `.env` -- konfiguracni soubor (SMTP hesla, debug rezim), pokud existuje
   - `manifest.json` -- metadata: cas vytvoreni, verze aplikace, nazev DB, velikost DB, pocty zaznamu v klicovych tabulkach
4. **Auto-cleanup** -- po vytvoreni zalohy zavola `cleanup_old_backups()` (ponecha max 10 nejnovejsich ZIP souboru)

### Router endpoint (`/sprava/zaloha/vytvorit`)

- Kontroluje, ze v DB jsou nejaka data (soucet zaznamu v 8 hlavnich tabulkach). Pokud je vse prazdne, presmeruje s chybou `prazdna`.
- Umoznuje vlastni pojmenovani zalohy (sanitizace: jen alfanumericke znaky, `-`, `_`, `.`)
- Loguje aktivitu do `ActivityLog`

### Sprava zaloh

| Endpoint | Popis |
|----------|-------|
| `GET /sprava/zalohy` | Stranka se seznamem zaloh a historii obnov |
| `POST /sprava/zaloha/vytvorit` | Vytvoreni nove zalohy |
| `GET /sprava/zaloha/{filename}/stahnout` | Stazeni zalohy (FileResponse) |
| `POST /sprava/zaloha/{filename}/smazat` | Smazani zalohy |
| `POST /sprava/zaloha/{filename}/prejmenovat` | Prejmenovani zalohy |
| `POST /sprava/zaloha/{filename}/obnovit` | Obnova z existujici zalohy |
| `POST /sprava/zaloha/obnovit` | Obnova z nahraneho ZIP |
| `POST /sprava/zaloha/obnovit-soubor` | Obnova z nahraneho svj.db souboru |
| `POST /sprava/zaloha/obnovit-slozku` | Obnova ze slozky (webkitdirectory) |

---

## Analyza obnovovaciho kodu

### 4 metody obnovy

#### 1. Obnova z existujici zalohy (`backup_restore_existing`)
- Vybere ZIP ze seznamu existujicich zaloh
- Zavola `restore_backup()` service funkci
- Validace: `is_safe_path()` proti path traversal

#### 2. Obnova z nahraneho ZIP (`backup_restore`)
- Upload ZIP souboru pres formular
- Validace: `validate_upload()` (max 200 MB, pripona `.zip`)
- Ulozi do `data/backups/upload_temp.zip`, po obnove smaze

#### 3. Obnova z DB souboru (`backup_restore_db_file`)
- Upload samotneho `svj.db` souboru
- Validace: `validate_upload()` (max 200 MB, pripona `.db`)
- SQLite integrity check po zapisu + rollback pri selhani
- Obnovi POUZE databazi, NE uploads/generated
- Jako jediny endpoint vola `engine.dispose()` PRED zapisem DB

#### 4. Obnova ze slozky (`backup_restore_folder`)
- Vyber slozky pres `webkitdirectory` atribut (Finder/File manager)
- Vsechny soubory se nahraji do temp adresare
- Hledani `svj.db` primo nebo o uroven hloubeji (Safari rozbaluje do podslozky)
- Limit 500 MB
- Path traversal ochrana: `os.path.realpath()` kontrola

### Bezpecnostni mechanismy pri obnove

1. **Restore lock** -- file-based zamek (`data/backups/.restore_lock`) brani soubeznemu spusteni dvou obnov. Stale locky (starsi 10 minut) se automaticky odstranuji.

2. **Safety backup** -- pred kazdou obnovou se automaticky vytvori pojistna zaloha aktualniho stavu. Pokud obnova selze, provede se rollback z teto pojistne zalohy.

3. **ZIP validace** (`restore_backup`):
   - `zipfile.is_zipfile()` -- overi, ze soubor je platny ZIP
   - Kontrola pritomnosti `svj.db` v archivu
   - `zf.testzip()` -- CRC integritni kontrola vsech souboru v archivu
   - Vsechny 3 kontroly probehnou PRED vytvorenim safety backupu

4. **SQLite integrity check** -- po zapisu DB souboru se overuje `PRAGMA integrity_check`:
   - V `restore_backup()` pres `_verify_db_integrity()`
   - V `restore_from_directory()` pres `_verify_db_integrity()`
   - V `backup_restore_db_file` primo v endpointu s rollbackem

5. **Rollback** (`_rollback_from_safety`):
   - Pokud obnova selze (exception), automaticky se obnovi data z pojistne zalohy
   - Pokud i rollback selze, loguje KRITICKE chybu (data mohou byt v nekonzistentnim stavu)
   - Poznámka: rollback NEOBNOVI `.env` soubor

6. **Zip Slip ochrana** (`_restore_directory_from_zip`):
   - `os.path.realpath()` + kontrola, ze extrahovany soubor zustava v cilovem adresari
   - Prevence path traversal utoku pres zmanipulovane cesty v ZIP archivu

7. **Post-restore migrace** (`run_post_restore_migrations`):
   - `engine.dispose()` -- ukonci vsechna stavajici DB spojeni
   - `Base.metadata.create_all()` -- vytvori chybejici tabulky (pokud zaloha je ze starsi verze)
   - Spusti vsech 13 migracnich funkci (sloupce, indexy, seed data)
   - Kazda migrace je obalena try/except, selhani jedne neblokuje ostatni
   - Vraci seznam warningu pokud nektere migrace selhaly

8. **Restore log** -- JSON soubor (`data/backups/restore_log.json`), prezije obnovu DB. Kazdy zaznam obsahuje: timestamp, source, method, safety_backup.

---

## Test vytvoreni zalohy

- **Datum testu**: 2026-03-27
- **Endpoint**: `POST /sprava/zaloha/vytvorit` s `filename=test_integrity_check`
- **Vysledek**: HTTP 302 redirect na `/sprava/zalohy?zprava=vytvoreno`
- **Velikost zalohy**: 152 428 018 bytu (145 MB)
- **Obsah ZIP** (1815 souboru):
  - `svj.db`: 4 898 816 B (komprimovano na 1 180 665 B)
  - `uploads/`: 1812 souboru (podadresare: csv, excel, share_check, tax_pdfs, temp, word_templates)
  - `.env`: pritomen (199 B, 7 SMTP klicu)
  - `manifest.json`: pritomen s table counts
  - `generated/`: prazdny (zadne generovane soubory v tomto okamziku)
- **CRC integrita**: OK (vsechny soubory prosly `zf.testzip()`)
- **SQLite integrita**: `PRAGMA integrity_check` = "ok"
- **Pocty zaznamu v DB z manifestu**:
  - owners: 512, units: 508, owner_units: 744, votings: 2
  - tax_sessions: 3, email_logs: 468, payments: 973
  - prescription_years: 1, prescriptions: 549, settlements: 530
- **Pocty zaznamu v DB primo** (38 tabulek, vsechny sedi s manifestem + doplnkove tabulky)
- **Stazeni**: `GET /sprava/zaloha/test_integrity_check.zip/stahnout` = HTTP 200
- **Smazani**: `POST /sprava/zaloha/test_integrity_check.zip/smazat` = HTTP 302 (soubor smazan)

---

## Zmeny oproti predchozi kontrole (2026-03-09)

### Opravene problemy z predchoziho reportu

| # | Problem | Stav |
|---|---------|------|
| 1 | DB file restore bez rollbacku | OPRAVENO -- endpoint `backup_restore_db_file` nyni ma rollback v `except` bloku (radky 294-300) |
| 2 | Zadna validace SQLite pri DB file restore | OPRAVENO -- pridana `PRAGMA integrity_check` validace (radky 266-278) s rollbackem pri selhani |
| 3 | Parameter mismatch `validate_upload` | BYL FALSE POSITIVE -- `UPLOAD_LIMITS` i `validate_upload()` pouzivaji `allowed_extensions`, zadny nesoulad |

### Pretrvavajici problemy

Problemy #5-#10 z predchoziho reportu nebyly reseny (nizsi priorita).

---

## Edge cases

### Poskozena zaloha
- **ZIP**: `zipfile.is_zipfile()` + `zf.testzip()` detekuji poskozeny ZIP archiv i jednotlive soubory. Obnova se odmitne PRED jakoukoli zmenou dat. **OK**
- **DB soubor**: Nyni validovan pres `PRAGMA integrity_check` s rollbackem. **OK**
- **Slozka**: `restore_from_directory` vola `_verify_db_integrity()` po zapisu DB. **OK**

### Diskovy prostor
- **Pred zalohovanim**: Kontrola `2x odhadovana velikost < volne misto`. **OK**
- **Pred obnovenim**: Safety backup spotrebuje dalsi misto. Kontrola diskoveho prostoru probehne uvnitr `create_backup` (safety backup). **OK** (neprime, ale funkcni)

### Soubehy
- File-based restore lock prevence soubezneho spusteni. **OK**
- Lock ma 10minutovy timeout. **OK**
- `upload_temp.zip` je chraneny restore lockem proti kolizi. **OK**

### Ztrata dat pri obnove
- Existujici `uploads/` a `generated/` adresare se SMAZOU (`shutil.rmtree`) pred obnovenim novych. **Ocekavane chovani**
- Safety backup pokryva moznost navratu. **OK**

---

## Nalezene problemy

| # | Problem | Severity | Doporuceni |
|---|---------|----------|------------|
| 1 | **Engine.dispose() chybi pred ZIP/slozka restore** -- `restore_backup()` a `restore_from_directory()` prepisuji `svj.db` BEZ predchoziho `engine.dispose()`. Aktivni DB spojeni z connection poolu mohou cist/zapisovat do souboru behem prepisu. Endpoint `backup_restore_db_file` toto dela spravne (radek 258). `run_post_restore_migrations()` vola `engine.dispose()` az PO obnove. | HIGH | Pridat `engine.dispose()` pred volanim `restore_backup()` a `restore_from_directory()` v endpointech `backup_restore_existing`, `backup_restore`, a `backup_restore_folder`. |
| 2 | **Rollback neobnovi `.env` soubor** -- `_rollback_from_safety()` obnovi DB, uploads a generated, ale NE `.env`. Pokud obnova selze po prepisu `.env` (teoreticky posledni krok, takze malo pravdepodobne), puvodni `.env` se ztrati. | LOW | Pridat obnovu `.env` do `_rollback_from_safety()` pokud je v safety ZIP. |
| 3 | **WAL checkpoint warning neni propagovan** -- pokud WAL checkpoint selze (radek 86 v service), zaznamena se jen warning do logu. Zaloha muze byt neuplna (nezachyti posledni pending zapisy). Uzivatel o tom nevi. | MEDIUM | Logovat warning do manifest.json nebo zobrazit upozorneni uzivateli. |
| 4 | **Auto-cleanup muze smazat stare dulezite zalohy** -- `cleanup_old_backups(keep_count=10)` se spousti po KAZDEM `create_backup`, vcetne safety backupu. Pri castem restore muze dojit k tomu, ze uzivatelske zalohy se ztrati na ukor safety backupu. | MEDIUM | Safety backup by mel byt oznaceny (prefix `_safety_`) a vyjmut z auto-cleanup, nebo zvysit `keep_count`. |
| 5 | **Manifest app_version je hardcoded "1.0"** -- `manifest.json` v zaloze obsahuje `"app_version": "1.0"` (radek 109), nemeni se s vyvojem aplikace. Neni mozne zjistit, z jake verze kodu zaloha pochazi. | LOW | Nacitat verzi z `pyproject.toml` nebo konfiguracniho souboru. |
| 6 | **Slozka restore neloguje safety backup** -- `backup_restore_folder` (radek 363) zavola `log_restore()` bez `safety_backup` parametru, i kdyz `restore_from_directory` safety backup vytvari. | LOW | Pridat sledovani safety backupu shodne s ostatnimi restore endpointy (pomoci `set()` diff pred/po restore). |
| 7 | **Manifest nesleduje vsechny tabulky** -- `_get_table_counts` sleduje 12 tabulek z celkovych 38. Chybi napr. `spaces`, `tenants`, `board_members`, `code_list_items`, `activity_logs`, `ballots`, `ballot_votes`. | LOW | Pridat dalsi tabulky do seznamu v `_get_table_counts`, nebo dynamicky cist vsechny tabulky z `sqlite_master`. |
| 8 | **Zadne automaticke zalohy** -- system nema scheduled/periodicke zalohovani. Zalohy vznikaji pouze rucne akci uzivatele nebo jako safety backup pred obnovenim. | LOW | Implementovat periodicke zalohovani (napr. pri startu aplikace, pokud posledni zaloha je starsi nez X dni). |

---

## Doporuceni

### Vysoka priorita

1. **Pridat `engine.dispose()` pred ZIP/slozka restore** (#1) -- do endpointu `backup_restore_existing` (pred `restore_backup`), `backup_restore` (pred `restore_backup`), a `backup_restore_folder` (pred `restore_from_directory`). Jednoradkova zmena na 3 mistech. Narocnost: nizka (~5 min). Regrese riziko: nizke.

### Stredni priorita

2. **Safety backup ochrana** (#4) -- oznacit safety backupy prefixem a vyjmout z auto-cleanup.
3. **WAL checkpoint feedback** (#3) -- informovat uzivatele o neuspesnem WAL checkpoint.

### Nizka priorita

4. **Rollback .env** (#2), **manifest verze** (#5), **slozka safety log** (#6), **manifest tabulky** (#7), **automaticke zalohy** (#8).

---

## Shrnuti

Zaalohovaci system SVJ aplikace je **solidne navrzeny** s nasledujicimi silnymi strankami:

- Kompletni obsah zalohy (DB + uploads + generated + .env + manifest s table counts)
- WAL checkpoint pred zalohou
- CRC integritni kontrola ZIP archivu
- SQLite integrity check po obnove (vsechny 4 metody)
- Safety backup + automaticky rollback pri selhani (vsechny 4 metody)
- Zip Slip ochrana
- File-based restore lock proti soubehu
- Path traversal ochrana na download i folder restore
- Post-restore migrace pro kompatibilitu starsich zaloh (13 migraci)
- Restore log prezivajici obnovu DB
- Kontrola diskoveho prostoru pred zalohovanim
- 4 metody obnovy (existujici ZIP, nahrany ZIP, DB soubor, slozka)

**Oproti predchozi kontrole (2026-03-09) byly opraveny 2 HIGH priority problemy** (rollback a SQLite validace v DB file restore). Jeden z "CRITICAL" nalezu (#3) byl false positive.

**Hlavni zbyva riziko**: `engine.dispose()` se nevola pred obnovenim v 3 ze 4 restore endpointu (chybi u ZIP a slozka metod). Endpoint `backup_restore_db_file` to dela spravne. Oprava je trivialni (1 radek na 3 mistech).

Celkove hodnoceni: **dobry stav** s jednim HIGH priority nalezem k oprave.
