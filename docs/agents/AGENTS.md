# Přehled agentů

## Automatický (vždy aktivní)
| Agent | Kde | Popis |
|-------|-----|-------|
| **Task Agent** | V CLAUDE.md | Řídí postup práce na úkolech — plán, schválení, commit, report |

## Ruční spouštění

### Po bloku změn
| Agent | Příkaz |
|-------|--------|
| **Doc Sync** | `Přečti DOC-SYNC.md a proveď synchronizaci dokumentace s aktuálním stavem projektu.` |
| **Code Guardian** | `Přečti CODE-GUARDIAN.md a proveď audit projektu. Výstupem je docs/reports/AUDIT-REPORT.md. Nic neopravuj, pouze reportuj.` |
| **Test Agent** | `Přečti TEST-AGENT.md a proveď kompletní testování projektu. Výstupem je docs/reports/TEST-REPORT.md. Nic neopravuj, pouze testuj a reportuj.` |

### Před vydáním verze
| Agent | Příkaz |
|-------|--------|
| **Test Agent** | `Přečti TEST-AGENT.md a proveď kompletní testování projektu. Výstupem je docs/reports/TEST-REPORT.md. Nic neopravuj, pouze testuj a reportuj.` |
| **Release Agent** | `Přečti RELEASE-AGENT.md a připrav release. Nejdřív proveď pre-release kontrolu, pak po schválení připrav balíček.` |
| **Backup Agent** | `Přečti BACKUP-AGENT.md a proveď kontrolu integrity zálohovacího systému. Testuj na kopiích dat.` |

### Přenos na jiný Mac
| Agent | Příkaz |
|-------|--------|
| **USB Deploy** | `Přečti docs/agents/USB-DEPLOY.md a proveď přenos aplikace na USB. Cíl: /Volumes/NAZEV_USB` |

### Jednorázově / podle potřeby
| Agent | Příkaz | Kdy |
|-------|--------|-----|
| **Business Logic** | `Přečti BUSINESS-LOGIC-AGENT.md a proveď extrakci business logiky. Nic neopravuj.` | Před přepisem, onboarding, dokumentace |
| **Cloud Deploy** | `Přečti CLOUD-DEPLOY.md a analyzuj připravenost pro nasazení do cloudu.` | Až budeš chtít na internet |

## Doporučený workflow

```
Denní práce:
  Zadávej úkoly → Task Agent se postará automaticky

Po větším bloku změn:
  1. Doc Sync (aktualizuj dokumentaci)
  2. Code Guardian (audit kódu)
  3. Test Agent (otestuj aplikaci)
  4. Oprav nalezené problémy

Před vydáním:
  1. Code Guardian (audit kódu)
  2. Backup Agent (ověř zálohy)
  3. Doc Sync (dokumentace aktuální?)
  4. Test Agent (finální testování)
  5. Release Agent (kontrola + tag)

Přenos na jiný Mac:
  1. USB Deploy Agent (příprava + troubleshooting)

Jednorázově:
  - Business Logic Agent (extrakce know-how)
  - Cloud Deploy (analýza pro cloud)
```
