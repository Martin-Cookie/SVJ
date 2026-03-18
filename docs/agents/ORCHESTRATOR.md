# Orchestrátor – Koordinátor agentů

> Spouštěj místo jednotlivých agentů když nevíš co spustit jako první,
> nebo chceš provést komplexní údržbu projektu.
> Orchestrátor se tě zeptá, zanalyzuje stav projektu a navrhne plán.

---

## Cíl

Zanalyzovat aktuální stav projektu, navrhnout které agenty spustit a v jakém pořadí,
a po schválení je postupně spouštět. Mezi každým agentem čeká na tvé potvrzení.

**SÁM NIC NEOPRAVUJE. POUZE KOORDINUJE AGENTY.**

---

## Instrukce

### Fáze 1: ROZHOVOR (vždy)

Zeptej se uživatele přes AskUserQuestion:

**Otázka 1: Co potřebuješ?**
- Dokončil jsem blok změn → chci zkontrolovat projekt
- Chci zlepšit UX / procesy
- Připravuji release
- Chci zdokumentovat projekt
- Nevím, zhodnoť stav projektu a poraď

**Otázka 2: Jaký rozsah?**
- Celý projekt
- Konkrétní modul (který?)

**Otázka 3: Kolik máš času?**
- Rychlá kontrola (1–2 agenti)
- Důkladná údržba (3–5 agentů)
- Kompletní průchod (všichni relevantní agenti)

---

### Fáze 2: ANALÝZA STAVU

Než navrneš plán, rychle zkontroluj stav projektu:

```bash
# Poslední commity
git log --oneline -10

# Necommitnuté změny
git status

# Poslední audit report (pokud existuje)
cat docs/agents/AUDIT-REPORT.md 2>/dev/null | head -20

# Poslední UX report (pokud existuje)
cat docs/reports/UX-REPORT*.md 2>/dev/null | head -20

# Kdy byla naposledy synchronizovaná dokumentace
git log --oneline -1 -- CLAUDE.md README.md docs/
```

---

### Fáze 3: NÁVRH PLÁNU

Na základě odpovědí a stavu projektu navrhni plán. Vysvětli PROČ doporučuješ každého agenta a v jakém pořadí.

#### Doporučená pořadí podle situace:

**Po bloku změn:**
1. **Code Guardian** — nejdřív zjisti jestli je kód v pořádku
2. **Doc Sync** — pak synchronizuj dokumentaci s realitou
3. **Test Agent** — ověř že aplikace funguje
4. **UX Optimizer** (volitelně) — pokud se měnilo UI

**Zlepšení UX:**
1. **UX Optimizer** — analýza a návrhy
2. **Doc Sync** (po implementaci návrhů) — aktualizuj dokumentaci

**Před releasem:**
1. **Code Guardian** — audit kódu
2. **Backup Agent** — ověř zálohy
3. **Doc Sync** — dokumentace aktuální?
4. **Test Agent** — finální testování celé aplikace
5. **Release Agent** — pre-release kontrola + balíček

**Dokumentace projektu:**
1. **Business Logic Agent** — extrahuj logiku z kódu
2. **Doc Sync** — synchronizuj existující dokumentaci

**Kompletní údržba (nevím co potřebuji):**
1. **Code Guardian** — stav kódu
2. **Doc Sync** — stav dokumentace
3. **Test Agent** — stav funkčnosti aplikace
4. **UX Optimizer** — stav UX
5. **Backup Agent** — stav záloh
6. **Business Logic Agent** — stav dokumentace logiky

#### Formát návrhu:

```
## Navrhovaný plán

Na základě stavu projektu doporučuji:

| Pořadí | Agent | Důvod |
|--------|-------|-------|
| 1. | Code Guardian | 15 commitů od posledního auditu, žádný AUDIT-REPORT.md |
| 2. | Doc Sync | CLAUDE.md naposledy změněn před 3 týdny, kód se od té doby výrazně změnil |
| 3. | UX Optimizer (modul Platby) | Nové UI v posledních commitech, stojí za kontrolu |

Odhadovaný čas: ~20 minut

Chceš spustit tento plán? Nebo chceš upravit pořadí / přidat / odebrat agenta?
```

---

### Fáze 4: SPOUŠTĚNÍ (po schválení)

Po schválení plánu spouštěj agenty JEDNOHO PO DRUHÉM:

1. **Před každým agentem** oznam: "Spouštím [Agent] — [co bude dělat]"
2. **Přečti soubor agenta** a proveď jeho instrukce
3. **Po dokončení** ukaž stručný souhrn výsledků
4. **Zeptej se:** "Agent [X] dokončen. Pokračovat s [dalším agentem]?"
5. **Počkej na potvrzení** — nikdy nespouštěj dalšího agenta bez souhlasu

#### Mezi agenty:

```
╔══════════════════════════════════════════╗
║  ✅ Code Guardian dokončen               ║
║  Výsledek: 3 kritické, 7 důležité nálezy ║
║                                          ║
║  Další: Doc Sync                         ║
║  Pokračovat? (ano / přeskočit / ukončit) ║
╚══════════════════════════════════════════╝
```

---

### Fáze 5: ZÁVĚREČNÝ SOUHRN

Po dokončení všech agentů vypiš souhrnnou tabulku:

```
## Souhrn orchestrace

| # | Agent | Stav | Klíčové nálezy |
|---|-------|------|----------------|
| 1 | Code Guardian | ✅ Dokončen | 3 kritické, 7 důležitých |
| 2 | Doc Sync | ✅ Dokončen | 5 zastaralých pravidel opraveno |
| 3 | UX Optimizer | ⏭️ Přeskočen | — |

### Doporučené další kroky:
1. Opravit 3 kritické nálezy z Code Guardian
2. Po opravách spustit orchestrátora znovu pro ověření
```

---

## Dostupní agenti

| Agent | Soubor | Co dělá | Doba |
|-------|--------|---------|------|
| **Code Guardian** | docs/agents/CODE-GUARDIAN.md | Audit kódu — kvalita, bezpečnost, UI, výkon | ~6 min |
| **Doc Sync** | docs/agents/DOC-SYNC.md | Synchronizace dokumentace s realitou | ~5 min (analýza) + ~5 min (opravy) |
| **UX Optimizer** | docs/agents/UX-OPTIMIZER.md | Analýza a návrhy zlepšení UX (6 pohledů) | ~8 min |
| **Backup Agent** | docs/agents/BACKUP-AGENT.md | Kontrola integrity záloh | ~3 min |
| **Release Agent** | docs/agents/RELEASE-AGENT.md | Příprava verze (pre-release + balíček) | ~5 min |
| **Business Logic** | docs/agents/BUSINESS-LOGIC-AGENT.md | Extrakce business logiky z kódu | ~8 min |
| **Test Agent** | docs/agents/TEST-AGENT.md | Automatické testování celé aplikace (8 fází) | ~15 min |
| **Cloud Deploy** | docs/agents/CLOUD-DEPLOY.md | Analýza připravenosti pro cloud | ~5 min |

> **Task Agent** není v seznamu — ten běží automaticky při zadání úkolů.

---

## Spuštění

```
Přečti ORCHESTRATOR.md a zkoordinuj údržbu projektu. Zeptej se mě co potřebuji a navrhni plán.
```
