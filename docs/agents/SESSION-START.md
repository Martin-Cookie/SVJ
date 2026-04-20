# Session Start Agent — Orientace na začátku nové session

> Spouštěj na začátku každé nové Claude Code session.
> Agent zkontroluje stav projektu, ukáže přehled a zeptá se co chceš dělat.

---

## Cíl

Rychle se zorientovat v projektu po startu nové session — co se naposledy dělalo,
jaký je stav kódu a dokumentace, a co chce uživatel dělat dál.

---

## Instrukce

### Krok 1: PŘEČTI PRAVIDLA

```bash
cat CLAUDE.md | head -50
```

Pochop o jaký projekt jde, jaký stack používá, jaká platí pravidla.

### Krok 2: ZKONTROLUJ STAV

Spusť automaticky (bez čekání na zadání):

```bash
# Posledních 10 commitů
git log --oneline -10

# Necommitnuté změny
git status

# Aktuální větev
git branch --show-current

# Existující reporty
ls -la docs/reports/AUDIT-REPORT.md docs/reports/UX-REPORT.md docs/reports/TEST-REPORT.md docs/reports/BACKUP-REPORT.md docs/agents/BUSINESS-LOGIC.md docs/agents/BUSINESS-SUMMARY.md 2>/dev/null

# Poslední změna dokumentace
git log --oneline -1 -- CLAUDE.md README.md docs/
```

### Krok 3: VYPIŠ PŘEHLED

```
╔══════════════════════════════════════════════════════╗
║  📋 Projekt: [název]                                 ║
║  🌿 Větev: [aktuální branch]                         ║
║                                                      ║
║  📝 Posledních 5 commitů:                            ║
║     • [commit 1]                                     ║
║     • [commit 2]                                     ║
║     • [commit 3]                                     ║
║     • [commit 4]                                     ║
║     • [commit 5]                                     ║
║                                                      ║
║  ⚠️  Necommitnuté změny: [ano/ne + stručně co]       ║
║                                                      ║
║  📊 Reporty:                                         ║
║     AUDIT-REPORT:    [✅ existuje / ❌ chybí]         ║
║     UX-REPORT:       [✅ existuje / ❌ chybí]         ║
║     BUSINESS-LOGIC:  [✅ existuje / ❌ chybí]         ║
║                                                      ║
║  📅 Dokumentace naposledy změněna: [datum + co]       ║
╚══════════════════════════════════════════════════════╝
```

### Krok 4: ZEPTEJ SE

Přes AskUserQuestion nabídni:

**Co chceš dnes dělat?**
- 🆕 Nový úkol
- 🐛 Opravit bug
- 🔄 Pokračovat v rozpracovaném
- 🎯 Spustit orchestrátora (koordinace agentů)
- 📋 Spustit konkrétního agenta
- 🔍 Podívat se na kód (jen prohlížet)

Pokud uživatel vybere "Spustit konkrétního agenta", nabídni seznam:

**Kterého agenta?**
- Code Guardian (audit kódu)
- Doc Sync (synchronizace dokumentace)
- UX Optimizer (analýza UX)
- Backup Agent (kontrola záloh)
- Release Agent (příprava verze)
- Business Logic (extrakce logiky)
- Cloud Deploy (analýza pro cloud)

---

## Spuštění

```
Přečti SESSION-START.md a proveď orientaci v projektu.
```

Nebo zkráceně při startu session:

```
start
```

(Claude pozná že má přečíst SESSION-START.md podle klíčového slova)
