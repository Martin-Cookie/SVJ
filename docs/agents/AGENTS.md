# Přehled agentů SVJ

## Koordinace

| Agent | Spuštění | Co dělá |
|-------|----------|---------|
| **Orchestrátor** | `Přečti ORCHESTRATOR.md a zkoordinuj údržbu projektu.` | Zeptá se co potřebuješ, zanalyzuje stav, navrhne plán agentů s módem (rychlý/hluboký), spouští je postupně s předáváním kontextu. Sám nic neopravuje. |
| **Session Start** | `Přečti SESSION-START.md a proveď orientaci v projektu.` | Orientace na začátku session — git stav, reporty, co dál. |

## Analytičtí agenti (nic neopravují, pouze reportují)

| Agent | Soubor | Mód | Doba | Výstup | Co dělá |
|-------|--------|-----|------|--------|---------|
| **Code Guardian** | CODE-GUARDIAN.md | rychlý/hluboký | ~4/6 min | `docs/reports/AUDIT-REPORT.md` | Audit kódu, bezpečnosti, výkonu, error handlingu, git hygieny, testů |
| **Test Agent** | TEST-AGENT.md | rychlý/hluboký | ~5/12 min | `docs/reports/TEST-REPORT.md` | Pytest, route coverage, Playwright smoke + funkční testy, exporty, back URL |
| **UX Optimizer** | UX-OPTIMIZER.md | rychlý/hluboký | ~4/8 min | `docs/reports/UX-REPORT.md` | Analýza UX z 6 pohledů (uživatel, business, designer, performance, error, data quality) |
| **Doc Sync** | DOC-SYNC.md | rychlý/hluboký | ~5/10 min | opravy v CLAUDE.md, UI_GUIDE.md, README.md | Synchronizace dokumentace s kódem — zastaralé, chybějící, duplikáty, křížové odkazy |
| **Business Logic** | BUSINESS-LOGIC-AGENT.md | — | ~8 min | `docs/BUSINESS-LOGIC.md` + `docs/BUSINESS-SUMMARY.md` | Extrakce business procesů, pravidel, datového modelu, edge cases, integrací |
| **Purge/Restore/Verify** | PURGE-RESTORE-VERIFY.md | rychlý/hluboký | ~1 min | `data/purge_restore_reports/report_*.md` | Automatický end-to-end test: záloha → purge → restore → ověření. Nahrazuje i dřívější Backup Agent. |

## Akční agenti (provádějí změny)

| Agent | Soubor | Doba | Co dělá |
|-------|--------|------|---------|
| **Release Agent** | RELEASE-AGENT.md | ~5 min | Pre-release kontrola, changelog, git tag, ZIP balíček |
| **USB Deploy** | USB-DEPLOY.md | ~25 min | Přenos na jiný Mac: příprava zdrojového Macu, setup cílového, verifikace, troubleshooting |
| **Cloud Deploy** | CLOUD-DEPLOY.md | ~5 min | Analýza připravenosti pro cloud, doporučení platformy (VPS/PaaS/Docker), příprava nasazení |

## Matice odpovědnosti (bez překryvů)

| Oblast | Agent |
|--------|-------|
| Kód, bezpečnost, výkon, testy (analýza) | Code Guardian |
| Funkční testování (pytest, Playwright, exporty) | Test Agent |
| UX, workflow, procesy | UX Optimizer |
| Dokumentace (CLAUDE.md, UI_GUIDE.md, README.md) | Doc Sync |
| Zálohy, purge, restore | Purge/Restore/Verify |
| Business logika (extrakce) | Business Logic |
| Release balíček | Release Agent |
| Cloud nasazení | Cloud Deploy |
| USB přenos | USB Deploy |

## Doporučené scénáře

| Situace | Agenti (pořadí) |
|---------|-----------------|
| **Po bloku změn** | Code Guardian (rychlý) → Doc Sync (rychlý) → Test Agent (rychlý) |
| **Před releasem** | Code Guardian (hluboký) → P/R/V → Doc Sync (hluboký) → Test Agent (hluboký) → Release Agent |
| **Zlepšení UX** | UX Optimizer → Doc Sync |
| **Dokumentace** | Business Logic → Doc Sync |
| **Kompletní údržba** | Code Guardian → Doc Sync → Test Agent → UX Optimizer → P/R/V → Business Logic |
| **Nevím co dělat** | Spustit orchestrátora — zeptá se a navrhne plán |
