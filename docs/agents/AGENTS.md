# Přehled agentů

## Matice odpovědnosti

Každý agent má jasný záběr — žádné překryvy.

| Oblast | Agent |
|--------|-------|
| Kód, bezpečnost, výkon, testy (analýza) | Code Guardian |
| Dokumentace (CLAUDE.md, UI_GUIDE.md, README.md) | Doc Sync |
| UX, workflow, procesy | UX Optimizer |
| Funkční testování (pytest, Playwright, exporty) | Test Agent |
| Zálohy, purge, restore | Purge/Restore/Verify |
| Business logika (extrakce) | Business Logic |
| Release balíček | Release Agent |
| Cloud nasazení | Cloud Deploy |
| USB přenos | USB Deploy |

## Dostupní agenti

| Agent | Soubor | Mód | Doba |
|-------|--------|-----|------|
| **Code Guardian** | CODE-GUARDIAN.md | rychlý/hluboký | ~4/6 min |
| **Doc Sync** | DOC-SYNC.md | rychlý/hluboký | ~5/10 min |
| **UX Optimizer** | UX-OPTIMIZER.md | rychlý/hluboký | ~4/8 min |
| **Test Agent** | TEST-AGENT.md | rychlý/hluboký | ~5/12 min |
| **Purge/Restore/Verify** | PURGE-RESTORE-VERIFY.md | rychlý/hluboký | ~1 min |
| **Business Logic** | BUSINESS-LOGIC-AGENT.md | — | ~8 min |
| **Release Agent** | RELEASE-AGENT.md | — | ~5 min |
| **Cloud Deploy** | CLOUD-DEPLOY.md | — | ~5 min |
| **USB Deploy** | USB-DEPLOY.md | — | ~25 min |

## Spouštění

### Doporučeno: přes orchestrátora

```
Přečti ORCHESTRATOR.md a zkoordinuj údržbu projektu.
```

Orchestrátor zvolí agenty, mód (rychlý/hluboký) a předává kontext mezi nimi.

### Jednotlivě

| Kdy | Příkaz |
|-----|--------|
| Po bloku změn | `Přečti CODE-GUARDIAN.md a proveď audit.` |
| Sync dokumentace | `Přečti DOC-SYNC.md a synchronizuj dokumentaci.` |
| Testování | `Přečti TEST-AGENT.md a otestuj projekt.` |
| UX analýza | `Přečti UX-OPTIMIZER.md a analyzuj [celou aplikaci / modul X].` |
| Zálohy | `Přečti PURGE-RESTORE-VERIFY.md a spusť test záloh.` |
| Business logika | `Přečti BUSINESS-LOGIC-AGENT.md a extrahuj logiku.` |
| Release | `Přečti RELEASE-AGENT.md a připrav release.` |
| Cloud | `Přečti CLOUD-DEPLOY.md a analyzuj připravenost pro cloud.` |
| USB přenos | `Přečti USB-DEPLOY.md a proveď přenos. Cíl: /Volumes/USB` |

## Doporučený workflow

```
Denní práce:
  Zadávej úkoly přímo

Po bloku změn (orchestrátor = rychlá kontrola):
  1. Code Guardian (rychlý) → 2. Doc Sync (rychlý) → 3. Test Agent (rychlý)

Před vydáním (orchestrátor = kompletní průchod):
  1. Code Guardian (hluboký) → 2. Purge/Restore/Verify → 3. Doc Sync (hluboký)
  → 4. Test Agent (hluboký) → 5. Release Agent

Přenos na jiný Mac:
  USB Deploy

Jednorázově:
  Business Logic (extrakce know-how) | Cloud Deploy (analýza pro cloud)
```
