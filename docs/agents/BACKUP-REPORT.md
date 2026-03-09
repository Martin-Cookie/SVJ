# Backup Integrity Report -- 2026-03-09

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
- **Service**: `/Users/martinkoci/Projects/SVJ/app/services/backup_service.py` (365 radku)
- **Router**: `/Users/martinkoci/Projects/SVJ/app/routers/administration.py` (radky 539-605)
- **Template**: `/Users/martinkoci/Projects/SVJ/app/templates/administration/backups.html`
- **Post-restore migrace**: `/Users/martinkoci/Projects/SVJ/app/main.py` (radky 309-351)

### Proces vytvoreni zalohy (`create_backup`)

1. **Kontrola diskoveho prostoru** -- `_check_disk_space()` overuje, ze na disku je alespon 2x odhadovana velikost dat volneho mista. Pokud ne, vyhodi `OSError`.
2. **WAL checkpoint** -- pred zalohovanim provede `PRAGMA wal_checkpoint(TRUNCATE)` na SQLite databazi, cimz se vsechna cekajici data z WAL souboru zapisi do hlavniho DB souboru. Pri selhani pokracuje s warningem.
3. **Tvorba ZIP**:
   - `svj.db` -- databaze (ulozena jako `svj.db` v rootu ZIP)
   - `uploads/` -- vsechny upload soubory (Excel, PDF, CSV, DOCX) zachovane s relativnimi cestami
   - `generated/` -- generovane soubory (hlasovaci listky PDF apod.)
   - `.env` -- konfiguracni soubor (SMTP hesla, debug rezim), pokud existuje
   - `manifest.json` -- metadata (cas vytvoreni, verze aplikace, nazev DB souboru)
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
- Obnovi POUZE databazi, NE uploads/generated

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

4. **Rollback** (`_rollback_from_safety`):
   - Pokud obnova selze (exception), automaticky se obnovi data z pojistne zalohy
   - Pokud i rollback selze, loguje KRITICKE chybu (data mohou byt v nekonzistentnim stavu)

5. **Zip Slip ochrana** (`_restore_directory_from_zip`):
   - `os.path.realpath()` + kontrola, ze extrahrovany soubor zustava v cilovem adresari
   - Prevence path traversal utoku pres zmanipulovane cesty v ZIP archivu

6. **Post-restore migrace** (`run_post_restore_migrations`):
   - `engine.dispose()` -- ukonci vsechna stavajici DB spojeni
   - `Base.metadata.create_all()` -- vytvori chybejici tabulky (pokud zaloha je ze starsi verze)
   - Spusti vsechny migracni funkce (pridani sloupcu, indexu, seed dat)
   - Kazda migrace je obalena try/except, selhani jedne neblokuje ostatni
   - Vraci seznam warninqu pokud nektere migrace selhaly

7. **Restore log** -- JSON soubor (`data/backups/restore_log.json`), prezije obnovu DB. Kazdy zaznam obsahuje: timestamp, source, method, safety_backup.

8. **Potvrzovaci dialog** -- UI vyzaduje potvrzeni pres `data-confirm` / `svjConfirm()` pred kazdou obnovou

---

## Edge cases

### Poskozena zaloha
- **ZIP**: `zipfile.is_zipfile()` + `zf.testzip()` detekuji poskozen ZIP archiv i jednotlive soubory. Pokud CRC nesouhlasi, obnova se odmitne PRED jakoukoli zmenou dat.
- **DB soubor**: Zadna validace integrity SQLite souboru. Poskozeny `svj.db` bude zapsany a `run_post_restore_migrations()` muze selhat.
- **Slozka**: Kontrola existence `svj.db`, ale bez validace obsahu.

### Diskovy prostor
- **Pred zalohovanim**: Kontrola `2x odhadovana velikost < volne misto`
- **Pred obnovenim**: Safety backup spotrebuje dalsi misto, ale neni explicitne kontrolovan diskovy prostor pred obnovenim (spoliha se na kontrolu uvnitr `create_backup`)

### USB / jiny pocitac
- Zalohy jsou portabilni ZIP soubory -- prenositelne mezi pocitaci
- `.env` soubor je soucasti zalohy -- umozni obnoveni SMTP konfigurace
- Post-restore migrace zajisti kompatibilitu starsi DB se soucasnym kodem
- Cesty jsou relativni (krom `config.py` kde jsou absolutni k `__file__`)

### Soubehy
- File-based restore lock prevence soubezneho spusteni
- Lock ma 10minutovy timeout pro pripad, ze proces spadne uprostred obnovy
- Lock obsahuje PID a timestamp v JSON formatu

### Ztrata dat pri obnove
- Existujici uploads/ a generated/ adresare se SMAZOU (`shutil.rmtree`) pred obnovenim novych
- Pokud zaloha neobsahuje uploads/ slozku, puvodni soubory se ztrati (adresare se vytvori prazdne)
- Safety backup toto pokryva -- je mozne se vratit zpet

### Obnova DB souboru bez rollbacku
- Endpoint `backup_restore_db_file` vytvori safety backup, ale pokud `file.write()` selze, NEPROVEDE rollback z safety backupu (na rozdil od `restore_backup` a `restore_from_directory`)

---

## Nalezene problemy

| # | Problem | Severity | Doporuceni |
|---|---------|----------|------------|
| 1 | **DB file restore bez rollbacku** -- endpoint `backup_restore_db_file` (radek 705-740) vytvori safety backup, ale pri selhani zapisu NEPROVEDE automaticky rollback. Pouze loguje exception a presmeruje s chybou. Data mohou zustat v nekonzistentnim stavu (castecne zapsany soubor). | HIGH | Pridat rollback logiku (`_rollback_from_safety`) do except bloku, shodne s `restore_backup` a `restore_from_directory`. |
| 2 | **Zadna validace integrity SQLite pri obnove z DB souboru** -- endpoint `backup_restore_db_file` prijme libovolny `.db` soubor bez overeni, ze je platna SQLite databaze. Poskozeny nebo nevalidni soubor zpusobi selhani migrace a aplikace muze byt nefunkcni. | HIGH | Pridat `sqlite3.connect(path); conn.execute("PRAGMA integrity_check"); conn.close()` po zapisu DB souboru, pred `run_post_restore_migrations()`. |
| 3 | **Parameter mismatch v `validate_upload`** -- `UPLOAD_LIMITS` pouziva klic `extensions`, ale `validate_upload()` ma parametr `allowed_extensions`. Volani `validate_upload(file, **UPLOAD_LIMITS["backup"])` by melo vyhodit `TypeError` za behu. | CRITICAL | Prejmenovat parametr `allowed_extensions` na `extensions` ve funkci `validate_upload()` a `validate_uploads()` v `app/utils.py`, nebo prejmenovat klic v `UPLOAD_LIMITS`. POZN: Toto postihuje VSECHNY upload validace v aplikaci, ne jen backup. |
| 4 | **Temp ZIP neni smazan pri ValueError** -- v `backup_restore` (radky 652-702) se `upload_temp.zip` maze ve `finally` bloku, ale jen pokud `temp_path.is_file()`. Pokud `restore_backup` vyhodi `ValueError` pred smazanim a presmeruje s chybou, temp soubor se smaze spravne (je ve finally). Toto je OK. | LOW | Zadna akce nutna -- finally blok pokryva vsechny cesty. |
| 5 | **WAL checkpoint warning neni propagan** -- pokud WAL checkpoint selze (radek 86), zaznamena se jen warning do logu. Zaloha muze byt neuplna (nezachyti posledni pending zapisy). Uzivatel o tom nevi. | MEDIUM | Logovat warning do manifest.json nebo zobrazit upozorneni uzivateli. |
| 6 | **Auto-cleanup muze smazat safety backup** -- `cleanup_old_backups(keep_count=10)` se spousti po KAZDEM `create_backup`, vcetne safety backupu. Pokud uz existuje 10+ zaloh, nova safety zaloha zpusobi smazani nejstarsi. Pri castem restore muze dojit k tomu, ze dulezite stare zalohy se ztrati. | MEDIUM | Safety backup by mel byt oznaceny (prefix `_safety_`) a vyjmut z auto-cleanup, nebo zvysit `keep_count`. |
| 7 | **Manifest app_version je hardcoded "1.0"** -- `manifest.json` v zaloze obsahuje `"app_version": "1.0"` (radek 109), nemeni se s vyvojem aplikace. Neni mozne zjistit, z jake verze kodu zaloha pochazi. | LOW | Nacitat verzi z `pyproject.toml` nebo konfiguracniho souboru. |
| 8 | **Slozka restore neloguje safety backup** -- `backup_restore_folder` (radek 801) zavola `log_restore()` bez `safety_backup` parametru, i kdyz `restore_from_directory` safety backup vytvari. | LOW | Pridat sledovani safety backupu shodne s ostatnimi restore endpointy (pomoci `set()` diff pred/po restore). |
| 9 | **Engine.dispose() timing pri restore** -- `run_post_restore_migrations()` vola `engine.dispose()` AZ PO obnove databaze. Behem obnovy (zapisu noveho `svj.db`) mohou existujici DB spojeni cist/zapisovat do souboru, ktery je prave prepisovan. To muze vest k poskozeni dat nebo SQLite locku. | MEDIUM | Volat `engine.dispose()` PRED zahajenim obnovy, ne az po ni. Alternativne pouzit exclusive lock na DB soubor behem obnovy. |
| 10 | **Zadne automaticke zalohy** -- system nema scheduled/periodicke zalohovani. Zalohy vznikaji pouze rucne akci uzivatele nebo jako safety backup pred obnovenim. | LOW | Implementovat periodicke zalohovani (napr. pri startu aplikace, pokud posledni zaloha je starsi nez X dni). |

---

## Doporuceni

### Kriticka (opravit okamzite)

1. **Opravit parameter mismatch** (#3) -- `validate_upload` nefunguje spravne s `**UPLOAD_LIMITS`. Prekejmenovat `allowed_extensions` -> `extensions` nebo naopak. Toto postihuje VSECHNY upload operace v aplikaci.

### Vysoka priorita

2. **Pridat rollback do DB file restore** (#1) -- sjednotit chovani se zbylymi restore metodami.
3. **Pridat SQLite integrity check** (#2) -- po nahrani `svj.db` souboru overit `PRAGMA integrity_check` pred spustenim migraci.
4. **Engine dispose pred obnovou** (#9) -- presunout `engine.dispose()` pred zapis noveho DB souboru.

### Stredni priorita

5. **Safety backup ochrana** (#6) -- oznacit safety backupy prefixem a vyjmout z auto-cleanup.
6. **WAL checkpoint feedback** (#5) -- informovat uzivatele o neuspesnem WAL checkpoint.

### Nizka priorita

7. **Dynamicka verze v manifestu** (#7) -- nacitat z `pyproject.toml`.
8. **Slozka restore safety log** (#8) -- doplnit `safety_backup` do log_restore volani.
9. **Automaticke zalohy** (#10) -- volitelna funkce pro periodicke zalohovani.

---

## Shrnuti

Zaalohovaci system SVJ aplikace je **solidne navrzeny** s nasledujicimi silnymi strankami:
- Kompletni obsah zalohy (DB + uploads + generated + .env + manifest)
- WAL checkpoint pred zalohou
- CRC integritni kontrola ZIP archivu
- Safety backup + automaticky rollback pri selhani (u ZIP a slozka metod)
- Zip Slip ochrana
- File-based restore lock proti soubehu
- Post-restore migrace pro kompatibilitu starich zaloh
- Restore log prezivajici obnovu DB
- Potvrzovaci dialogy v UI
- Kontrola diskoveho prostoru

Hlavni rizikova oblast je **obnova z DB souboru** (endpoint `backup_restore_db_file`), ktery nema rollback a nevaliduje integritu SQLite souboru. Take je nutne opravit parameter mismatch v `validate_upload`, ktery postihuje vsechny upload operace.
