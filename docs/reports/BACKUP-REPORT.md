# Backup Integrity Report — 2026-04-17

> Kontext: 20 commitů od posledního auditu (5. dubna). Nové modely/sloupce:
> `Owner.water_notified_at`, `WaterMeter` (meter_serial, meter_type, unit_number,
> unit_letter, unit_suffix, notified_at), `WaterReading`, migrace water email
> template v4. Nový upload podadresář `water_meters/`.

---

## Zálohovací systém

| Vlastnost | Stav |
|---|---|
| **Formát** | ZIP (deflated) |
| **Cesta** | `data/backups/` |
| **Pojmenování** | `svj_backup_YYYY-MM-DD_HHMMSS.zip` (nebo vlastní název) |
| **Obsah: DB** (`svj.db`) | OK |
| **Obsah: Uploads** (`data/uploads/` vč. water_meters) | OK |
| **Obsah: Generated** (`data/generated/`) | OK |
| **Obsah: .env** | OK |
| **Obsah: manifest.json** | OK (ale nekompletní — viz problémy) |
| **WAL checkpoint** | Ano, `PRAGMA wal_checkpoint(TRUNCATE)` před zálohou |
| **Disk space check** | Ano, vyžaduje 2x odhadované velikosti volno |
| **Auto-cleanup** | Ano, max 10 regulárních + 5 safety záloh |
| **Restore lock** | Ano, file-based lock s 10min stale timeout |

## Test vytvoření zálohy

| Metrika | Hodnota |
|---|---|
| **Záloha vytvořena** | OK |
| **Velikost** | 237.5 MB (ZIP), DB surová: 6.8 MB |
| **Celkem souborů v ZIP** | 2 997 |
| **CRC integrita** | OK |
| **Upload souborů v ZIP** | 2 994 (vč. 33 water_meters) |
| **Upload podadresáře** | csv, excel, share_check, tax_pdfs, temp, water_meters, word_templates |

## Test obnovy

### Obnova z existující zálohy (ZIP)

| Test | Výsledek |
|---|---|
| **Obnova proběhla** | OK (HTTP 302 → `?zprava=obnoveno`) |
| **Safety backup vytvořen** | OK (`_safety_svj_backup_*.zip`) |
| **DB integrita po obnově** | OK (`PRAGMA integrity_check` = ok) |
| **Migrace po obnově** | OK (`run_post_restore_migrations()` bez varování) |
| **Server funkční po obnově** | OK (dashboard, vodoměry, vlastníci — HTTP 200/307) |

### Konzistence dat po obnově

| Entita | Před | Po | Stav |
|---|---|---|---|
| Vlastníci | 518 | 518 | OK |
| Jednotky | 508 | 508 | OK |
| Hlasování | 2 | 2 | OK |
| Vodoměry | 218 | 218 | OK |
| Odečty vodoměrů | 2 587 | 2 587 | OK |
| Email šablony | 8 | 8 | OK |
| Platby | 1 460 | 1 460 | OK |
| Předpisy | 549 | 549 | OK |
| Upload water_meters | 33 souborů | 33 souborů | OK |

### Obnova z raw DB souboru

| Test | Výsledek |
|---|---|
| **Obnova proběhla** | OK |
| **Integrity check** | OK |
| **Migrace** | OK |

### Edge cases

| Test | Výsledek |
|---|---|
| **Poškozený ZIP** | Graceful error (`?chyba=neplatny`) |
| **ZIP bez svj.db** | Graceful error (`?chyba=neplatny`) |
| **Restore lock** | Funguje (file-based, 10min stale) |

---

## Nalezené problémy

| # | Problém | Severity | Soubor | Doporučení |
|---|---------|----------|--------|------------|
| 1 | **Manifest neobsahuje `water_meters` a `water_readings`** | Nízká | `app/services/backup_service.py` → `_get_table_counts()` | Přidat `"water_meters"` a `"water_readings"` do seznamu tabulek. Data se zálohují korektně (jsou v SQLite), jen manifest metadata nejsou kompletní — slouží pro informační účely. |
| 2 | **Manifest neobsahuje `smtp_profiles`** | Nízká | `app/services/backup_service.py` → `_get_table_counts()` | Přidat `"smtp_profiles"` do seznamu tabulek. Stejný dopad jako #1. |
| 3 | **Purge nemazá upload `water_meters/`** | Střední | `app/routers/administration/bulk.py` → `_CATEGORY_UPLOAD_DIRS` | Přidat `"water_meters": ["water_meters"]` do `_CATEGORY_UPLOAD_DIRS` dict. Při smazání kategorie vodoměrů zůstanou Excel soubory na disku. |
| 4 | **Lifespan nevytváří `water_meters/` upload podadresář** | Nízká | `app/main.py` → `lifespan()` řádek 1271 | Přidat `"water_meters"` do seznamu upload subdirectories. Podadresář se vytváří implicitně při prvním importu, ale chybí v explicitním seznamu. |
| 5 | **`_ensure_indexes()` nemá indexy pro water_meters/water_readings** | Nízká | `app/main.py` → `_ensure_indexes()` | Přidat indexy z modelů: `ix_water_meters_unit_id`, `ix_water_meters_unit_number`, `ix_water_meters_meter_serial`, `ix_water_meters_meter_type`, `ix_water_readings_meter_id`, `ix_water_readings_reading_date`, `ix_water_readings_import_batch`. Aktuálně se tabulky vytváří přes `create_all` (s indexy), ale při obnově starší zálohy kde tabulka již existovala bez indexů by se indexy nepřidaly. |
| 6 | **Data export (`data_export.py`) nemá kategorii pro vodoměry** | Informační | `app/services/data_export.py` | Přidat export kategorii pro water_meters/water_readings. Nesouvisí přímo se zálohami, ale s kompletností exportu dat. |

---

## Shrnutí

Zálohovací systém je **robustní a funkční**. Vytvoření zálohy, obnova ze ZIP, obnova z raw DB souboru, safety backup, rollback při chybě, restore lock, WAL checkpoint — vše funguje korektně.

Nalezené problémy jsou převážně **kosmetické** (nekompletní manifest metadata) nebo **nízké severity** (chybějící podadresář v lifespan, indexy). Jediný problém střední severity je #3 (purge nemazá water_meters upload soubory).

Všechna data vodoměrů (218 vodoměrů, 2 587 odečtů, 33 upload souborů) se **zálohují a obnovují korektně** — jsou součástí SQLite souboru a uploads adresáře.

---

## Testovací prostředí

- Datum: 2026-04-17
- Server: localhost:8000 (uvicorn)
- DB velikost: 6.8 MB (7 147 520 B)
- ZIP velikost: 237.5 MB (249 020 683 B)
- Testováno na kopii dat, produkční data nepoškozena
