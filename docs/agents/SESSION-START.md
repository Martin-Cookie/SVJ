# Session Start – Orientace na začátku session

> Spouštěj na začátku každé nové Claude Code session.

---

## Instrukce

### Krok 1: STAV PROJEKTU

```bash
git log --oneline -10
git status
git branch --show-current
ls -la docs/reports/AUDIT-REPORT.md docs/reports/UX-REPORT.md docs/reports/TEST-REPORT.md docs/reports/BACKUP-REPORT.md docs/reports/BUSINESS-LOGIC-AUDIT.md docs/BUSINESS-LOGIC.md 2>/dev/null
git log --oneline -1 -- CLAUDE.md README.md docs/
```

### Krok 2: PŘEHLED

```
╔══════════════════════════════════════════════════════╗
║  Projekt: SVJ                                        ║
║  Větev: [branch] | Stav: [čistý / X změn]           ║
║                                                      ║
║  Posledních 5 commitů:                               ║
║     • [commit 1–5]                                   ║
║                                                      ║
║  Reporty:                                            ║
║     AUDIT / UX / TEST / BACKUP / BUSINESS-LOGIC      ║
║                                                      ║
║  Dokumentace naposledy: [commit]                      ║
╚══════════════════════════════════════════════════════╝
```

### Krok 3: CO DÁL?

Zeptej se: **Co chceš dnes dělat?**

Pokud uživatel neví nebo chce údržbu → navrhni spustit orchestrátora:
```
Přečti ORCHESTRATOR.md a zkoordinuj údržbu projektu.
```

---

## Spuštění

```
Přečti SESSION-START.md a proveď orientaci v projektu.
```
