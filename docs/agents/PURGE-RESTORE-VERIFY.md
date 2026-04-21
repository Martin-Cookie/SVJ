# Purge/Restore/Verify Agent – Kompletní test záloh a obnovy

> Spouštěj po přidání nového modelu/tabulky, před releasem, nebo periodicky.
> Plně automatizovaný test v /tmp sandboxu — neohrozí produkční data.
> Nahrazuje i dřívější Backup Agent (statická analýza je součástí Phase 0/1).

---

## Cíl

Ověřit kompletní cyklus: **záloha → smazání dat → obnova → ověření funkčnosti**.
Odpovídá na: „Pokrývá purge VŠECHNY tabulky? Obnoví se po restore úplně všechno?"

---

## Instrukce

### Fáze 1: SPUŠTĚNÍ TESTU

```bash
.venv/bin/python scripts/purge_restore_verify.py
```

Skript (~15 sekund):
1. Sandbox v `/tmp/svj-test-<ts>/` (kopie DB, uploads, generated, `.env`)
2. `TestClient` spustí FastAPI v sandboxu
3. Projde 10 fází (viz tabulka)
4. Report: `data/purge_restore_reports/report_<ts>.md`
5. Smaže sandbox

### Fáze 2: INTERPRETACE REPORTU

Přečti report a vyhodnoť všech 10 fází:

| # | Fáze | Co ověřuje |
|---|------|-----------|
| 0 | Static purge coverage | Každá tabulka z `Base.metadata` je v `_PURGE_CATEGORIES` |
| 1 | Static backup coverage | Detekce file writes mimo povolené adresáře |
| 2 | Sandbox setup | Kopie DB + upload složek do /tmp |
| 3 | Create backup | `POST /sprava/zaloha/vytvorit` → ZIP vznikl |
| 4 | Baseline counts | Počet řádků v každé tabulce před purge |
| 5 | Purge | `POST /sprava/smazat-data` smazal všechny tabulky |
| 6 | Restore | `POST /sprava/zaloha/.../obnovit` + `hash_match` |
| 7a | Verify counts | Počty řádků po restore = baseline |
| 7b | HTTP smoke | 12 list stránek vrací 200 |
| 7c | Deep detail | 9 detail endpointů s joinedload vrací 200 |

### Fáze 3: NÁVRH FIXŮ (pokud FAIL/WARN)

Nic neopravuj — navrhni konkrétní zásahy:

| Selhání | Příčina | Fix |
|---------|---------|-----|
| Phase 0 FAIL | Nepokryté tabulky | Přidat model do `_PURGE_CATEGORIES` v `administration/_helpers.py` |
| Phase 1 WARN | File writes mimo povolené dirs | Ověřit přes Read zda cesta je v `upload_dir`/`generated_dir`/`temp_dir` |
| Phase 5 FAIL | Tabulky nevyprázdněné | Zkontrolovat `_PURGE_ORDER` a `purge_data()` implementaci |
| Phase 6 FAIL | `hash_match: False` | WAL checkpoint nebo file replacement v `restore_backup()` |
| Phase 7a FAIL | Count mismatch | Tabulky mimo `Base.metadata` nebo WAL/cache |
| Phase 7b/7c FAIL | HTTP 500 po restore | Chybí migrace v `_ALL_MIGRATIONS` nebo eager loading |

### Fáze 4: STATICKÁ ANALÝZA ZÁLOHOVACÍHO SYSTÉMU

Pokud orchestrátor vyžádá hluboký mód, po automatickém testu doplň:

1. **Obsah zálohy** — ověř že ZIP obsahuje: DB, uploads, generated, `.env`
2. **Obnovovací kód** — ověří se integrita před obnovou? Co se stane se stávajícími daty?
3. **Migrace při obnově** — `_ALL_MIGRATIONS` pokrývá všechny potřebné migrace?
4. **Edge cases** — poškozená záloha → graceful error nebo crash?

### Fáze 5: REPORT

```
## Purge/Restore/Verify Report – [datum]

**Výsledek:** PASS / FAIL
**Fáze:** X/10 PASS, Y FAIL, Z WARN
**Doba:** Xs

### Fáze
| # | Fáze | Stav | Poznámka |
|---|------|------|----------|
| 0 | Purge coverage | ... | .../... tabulek |
| 1 | Backup coverage | ... | — |
| ... | ... | ... | ... |

### Nálezy
[žádné / seznam s návrhy fixů]

### Doporučené další kroky
1. [konkrétní akce]
```

---

## Spuštění

```
Přečti PURGE-RESTORE-VERIFY.md a spusť end-to-end test zálohy a obnovy.
```

Nebo přes Claude Code subagent:
```
Spusť agenta purge-restore-verify.
```
