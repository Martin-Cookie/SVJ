# Purge/Restore/Verify Agent – End-to-end test zálohy a obnovy

> Spouštěj po přidání nového modelu/tabulky, před releasem, nebo když chceš
> ověřit že mazání dat a zálohování pokrývá všechny entity.
> Agent spustí plně automatizovaný test v /tmp sandboxu (neohrozí produkční data).

---

## Cíl

Automaticky ověřit kompletní cyklus: **vytvoření zálohy → smazání všech dat → obnova ze zálohy → ověření funkčnosti**. Na rozdíl od Backup Agent (statická analýza + ruční kroky) běží tento agent plně automaticky a měří reálný výsledek.

Odpovídá na otázku: „Pokrývá `_PURGE_CATEGORIES` VŠECHNY tabulky? A obnoví se po purge+restore úplně všechno?"

---

## Instrukce

### Fáze 1: SPUŠTĚNÍ TESTU

Spusť skript:

```bash
.venv/bin/python scripts/purge_restore_verify.py
```

Skript:
1. Vytvoří sandbox v `/tmp/svj-test-<timestamp>/` (kopie `data/svj.db`, uploads, generated, `.env`)
2. Přes `TestClient` spustí FastAPI aplikaci v sandboxu
3. Postupně projde 10 fází (viz níže)
4. Vypíše cestu k markdown reportu v `data/purge_restore_reports/report_<ts>.md`
5. Smaže sandbox

**Doba běhu: ~15 sekund** (u prázdné DB může být kratší).

### Fáze 2: INTERPRETACE REPORTU

Přečti report a vyhodnoť všech 10 fází:

| # | Fáze | Co ověřuje |
|---|------|-----------|
| 0 | Static purge coverage | Každá tabulka z `Base.metadata` je v `_PURGE_CATEGORIES` |
| 1 | Static backup coverage | Grep `open/mkdir/shutil` mimo povolené adresáře (detekce „osamělých" file write sites) |
| 2 | Sandbox setup | Kopie DB + upload složek do /tmp |
| 3 | Create backup | `POST /sprava/zaloha/vytvorit` → ZIP vznikl |
| 4 | Baseline counts | Počet řádků v každé tabulce před purge |
| 5 | Purge | `POST /sprava/smazat-data` smazal všechny tabulky (kromě backups/restore_log) |
| 6 | Restore | `POST /sprava/zaloha/.../obnovit` + `hash_match` svj.db souboru |
| 7a | Verify counts | Počty řádků po restore = baseline |
| 7b | HTTP smoke | 12 list stránek vrací 200 |
| 7c | Deep detail | 9 detail endpointů s joinedload vrací 200 |

### Fáze 3: NÁVRH FIXŮ (pokud FAIL/WARN)

Nic sám neopravuj — navrhni konkrétní zásahy podle typu selhání:

- **Phase 0 FAIL** (nepokryté tabulky) → chybí model v `_PURGE_CATEGORIES` v `app/routers/administration/_helpers.py`. Uveď které tabulky a do které kategorie patří.
- **Phase 1 WARN** (podezřelé file writes) → pro každý hit ověř přes Read, zda cesta skončí v `settings.upload_dir`/`generated_dir`/`temp_dir` (bezpečné) nebo mimo (reálná mezera v zálohování). Buď navrhni whitelist v `check_backup_coverage()` nebo opravu kódu.
- **Phase 5 FAIL** (tabulky nevyprázdněné) → `_PURGE_CATEGORIES` kategorii zná, ale `purge_data()` ji nemaže. Zkontroluj `_PURGE_ORDER` a implementaci.
- **Phase 6 FAIL** (`hash_match: False`) → restore nepřepsal svj.db správně. Typicky WAL checkpoint nebo file replacement race condition v `restore_backup()`.
- **Phase 7a FAIL** (count mismatch) → data po restore neodpovídají baseline. Zkontroluj zda nejsou tabulky mimo `Base.metadata` nebo WAL/cache problémy.
- **Phase 7b/7c FAIL** (HTTP 500) → router vrací 500 po restore. Typicky chybí migrace v `_ALL_MIGRATIONS` nebo eager loading.

### Fáze 4: REPORT UŽIVATELI

```
## Purge/Restore/Verify Report – [datum]

**Výsledek:** PASS / FAIL
**Fáze:** X/10 PASS, Y FAIL, Z WARN
**Doba:** Xs
**Report:** data/purge_restore_reports/report_<ts>.md

### Fáze
| # | Fáze | Stav | Poznámka |
|---|------|------|----------|
| 0 | Purge coverage | ✅ | 38/38 tabulek |
| 1 | Backup coverage | ✅ | — |
| … | … | … | … |

### Nálezy
[žádné / seznam s návrhy fixů]

### Doporučené další kroky
1. [konkrétní akce]
```

---

## Vztah k ostatním agentům

- **Backup Agent** (`BACKUP-AGENT.md`) — statická analýza + ruční kontrola zálohovacího systému
- **Purge/Restore/Verify** (tento) — automatizovaný end-to-end test
- **Test Agent** (`TEST-AGENT.md`) — širší funkční testy aplikace

Doporučené pořadí před releasem: **Backup Agent → Purge/Restore/Verify → Test Agent**.

---

## Spuštění

V Claude Code zadej:

```
Přečti PURGE-RESTORE-VERIFY.md a spusť end-to-end test zálohy a obnovy.
```

Nebo přímo přes Claude Code subagent (`.claude/agents/purge-restore-verify.md`):

```
Spusť agenta purge-restore-verify.
```
