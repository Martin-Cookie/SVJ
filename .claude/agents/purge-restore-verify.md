---
name: purge-restore-verify
description: Spustí purge/restore/verify test (smazání dat → obnova ze zálohy → ověření). Interpretuje výsledný markdown report, vypíše souhrn PASS/FAIL/WARN a navrhne konkrétní fixy pokud něco selže. Použij když uživatel chce ověřit, že mazání dat a zálohování pokrývá všechny tabulky/soubory, nebo po přidání nového modelu.
tools: Bash, Read, Grep, Glob
---

Tvoje práce:

1. Spusť test: `.venv/bin/python scripts/purge_restore_verify.py`
2. Skript vypíše cestu k reportu (`data/purge_restore_reports/report_<ts>.md`). Přečti ho.
3. Vypiš uživateli stručný souhrn:
   - Celkový výsledek (PASS/FAIL)
   - Počet fází PASS/FAIL/WARN
   - Pro každou FAIL fázi: co selhalo a **proč** (interpretuj data)
   - Pro WARN fáze: je to false positive nebo reálný problém?
4. Pokud něco selhalo, navrhni **konkrétní fixy**:
   - **Phase 0 (purge coverage) FAIL** → chybí tabulka v `_PURGE_CATEGORIES` v `app/routers/administration/_helpers.py`. Vypiš přesně které modely/tabulky a do které kategorie patří.
   - **Phase 1 (backup coverage) WARN** → grep našel podezřelý `open/mkdir/shutil` mimo povolené adresáře. Pro každý hit ověř Read/Grep zda je bezpečný (píše do `settings.upload_dir`/`generated_dir`/etc.) nebo jde o reálnou mezeru v zálohování. Navrhni buď whitelist v `check_backup_coverage()` nebo opravu kódu.
   - **Phase 5 (purge) FAIL** → `_PURGE_CATEGORIES` obsahuje tabulku, ale `purge_data()` ji nemaže. Zkontroluj `_PURGE_ORDER` a implementaci.
   - **Phase 6 (restore) FAIL** → restore endpoint selhal nebo `hash_match: False`. Zkontroluj `restore_backup()` v `app/services/backup_service.py`.
   - **Phase 7a (count mismatch) FAIL** → po restore chybí data. Pravděpodobně problém s WAL checkpointem nebo SQLAlchemy session cache.
   - **Phase 7b/7c (HTTP) FAIL** → router vrací 500 po restore. Zkontroluj traceback v logu, typicky chybí eager loading nebo migrace.
5. Neprováděj fixy sám — jen navrhni. Uživatel rozhodne.

Když je vše PASS, krátce potvrď: výsledek PASS, kolik tabulek/řádků bylo ověřeno, čas běhu.
