# Orchestrátor – Koordinátor agentů

> Spouštěj místo jednotlivých agentů když nevíš co spustit jako první,
> nebo chceš provést komplexní údržbu projektu.

---

## Cíl

Zanalyzovat stav projektu, navrhnout které agenty spustit, v jakém pořadí a módu,
a postupně je spouštět s **předáváním kontextu** mezi nimi.

**SÁM NIC NEOPRAVUJE. POUZE KOORDINUJE AGENTY.**

---

## Fáze 1: ROZHOVOR

Zeptej se uživatele přes AskUserQuestion:

**Otázka 1: Co potřebuješ?**
- Dokončil jsem blok změn → zkontrolovat projekt
- Chci zlepšit UX / procesy
- Připravuji release
- Chci zdokumentovat projekt
- Nevím, zhodnoť stav a poraď

**Otázka 2: Jaký rozsah?**
- Celý projekt
- Konkrétní modul (který?)

**Otázka 3: Kolik máš času?**
- Rychlá kontrola (1–2 agenti, rychlý mód)
- Důkladná údržba (3–5 agentů, hluboký mód)
- Kompletní průchod (všichni, hluboký mód)

---

## Fáze 2: ANALÝZA STAVU

```bash
git log --oneline -10
git status
cat docs/reports/AUDIT-REPORT.md 2>/dev/null | head -20
cat docs/reports/UX-REPORT.md 2>/dev/null | head -20
git log --oneline -1 -- CLAUDE.md README.md docs/
```

---

## Fáze 3: NÁVRH PLÁNU

Na základě odpovědí a stavu navrhni plán. Urči **mód** pro každého agenta (rychlý/hluboký).

### Scénáře:

**Po bloku změn:**
1. Code Guardian (rychlý) → 2. Doc Sync → 3. Test Agent (rychlý)
4. UX Optimizer (volitelně, pokud se měnilo UI)

**Zlepšení UX:**
1. UX Optimizer → 2. Doc Sync (po implementaci návrhů)

**Před releasem:**
1. Code Guardian (hluboký) → 2. Purge/Restore/Verify (hluboký) → 3. Doc Sync → 4. Test Agent (hluboký) → 5. Release Agent

**Dokumentace:**
1. Business Logic Agent → 2. Doc Sync

**Kompletní údržba:**
1. Code Guardian (hluboký) → 2. Doc Sync → 3. Test Agent (hluboký) → 4. UX Optimizer → 5. Purge/Restore/Verify → 6. Business Logic Agent

### Formát návrhu:

```
## Navrhovaný plán

| # | Agent | Mód | Důvod | Kontext z předchozího |
|---|-------|-----|-------|----------------------|
| 1 | Code Guardian | hluboký | 15 commitů od auditu | — |
| 2 | Test Agent | rychlý | Smoke test po auditu | Nálezy z Code Guardian |
| 3 | Doc Sync | — | CLAUDE.md 3 týdny staré | — |

Odhadovaný čas: ~20 minut
Chceš spustit? Nebo upravit?
```

---

## Fáze 4: SPOUŠTĚNÍ (po schválení)

### 4.1 Pravidlo předávání kontextu

Po dokončení každého agenta **extrahuj klíčové nálezy** (max 5–8 bodů) a předej je dalšímu agentovi jako vstupní kontext. Agent je použije k zaměření své práce.

**Co předávat:**

| Z agenta | Dalšímu | Jaký kontext |
|----------|---------|-------------|
| Code Guardian | Test Agent | Soubory s problémy → zaměřit smoke testy na tyto stránky |
| Code Guardian | Doc Sync | Přejmenované/smazané funkce → ověřit že nejsou v dokumentaci |
| Test Agent | UX Optimizer | Stránky kde selhaly testy → zaměřit UX analýzu |
| Test Agent | Code Guardian | Chybějící testy → doplnit do sekce "Testy" |
| UX Optimizer | Doc Sync | Nové UI vzory → ověřit že jsou v UI_GUIDE.md |
| Purge/Restore/Verify | Release Agent | PASS/FAIL status záloh |
| Business Logic | Doc Sync | Nově zdokumentované procesy → křížové odkazy |

### 4.2 Postup spouštění

Pro každého agenta:

1. **Oznam**: `Spouštím [Agent] v [rychlém/hlubokém] módu.`
2. **Předej kontext** (pokud existuje):
   ```
   Kontext z předchozích agentů:
   - Code Guardian: N+1 v app/routers/voting.py:145, chybějící index na payments.status
   - Test Agent: /platby vrací 500 při prázdné DB
   → Zaměř se na tyto oblasti.
   ```
3. **Přečti soubor agenta** a proveď jeho instrukce
4. **Extrahuj klíčové nálezy** (max 8 bodů) pro další agenty
5. **Vypiš souhrn**:

```
╔══════════════════════════════════════════════════╗
║  Code Guardian dokončen (hluboký mód)            ║
║  Výsledek: 2 CRITICAL, 5 HIGH, 3 MEDIUM         ║
║                                                  ║
║  Kontext pro další agenty:                       ║
║  - N+1 v voting.py:145                           ║
║  - SQL injection risk v sync/import.py:89        ║
║  - 3 moduly bez testů: tax, spaces, water_meters ║
║                                                  ║
║  Další: Test Agent (rychlý mód)                  ║
║  Pokračovat? (ano / přeskočit / ukončit)         ║
╚══════════════════════════════════════════════════╝
```

6. **Počkej na potvrzení** — nikdy nespouštěj dalšího bez souhlasu

---

## Fáze 5: ZÁVĚREČNÝ SOUHRN

```
## Souhrn orchestrace

| # | Agent | Mód | Stav | Klíčové nálezy |
|---|-------|-----|------|----------------|
| 1 | Code Guardian | hluboký | dokončen | 2 CRITICAL, 5 HIGH |
| 2 | Test Agent | rychlý | dokončen | 580/580 pytest, 2 route failures |
| 3 | Doc Sync | — | dokončen | 5 zastaralých pravidel opraveno |

### Křížové nálezy (nalezené díky předávání kontextu):
- Code Guardian flagoval N+1 v voting → Test Agent potvrdil pomalé načítání /hlasovani
- Test Agent našel 500 na /platby → Code Guardian to nedetekoval (přidat do dalšího auditu)

### Doporučené další kroky:
1. Opravit 2 CRITICAL nálezy
2. Po opravách spustit orchestrátora znovu (rychlá kontrola)
```

---

## Dostupní agenti

| Agent | Soubor | Co dělá | Mód | Doba |
|-------|--------|---------|-----|------|
| **Code Guardian** | CODE-GUARDIAN.md | Audit kódu, bezpečnosti, výkonu | rychlý/hluboký | ~4/6 min |
| **Doc Sync** | DOC-SYNC.md | Synchronizace dokumentace s realitou | rychlý/hluboký | ~5/10 min |
| **UX Optimizer** | UX-OPTIMIZER.md | Analýza a návrhy UX zlepšení (6 pohledů) | rychlý/hluboký | ~4/8 min |
| **Purge/Restore/Verify** | PURGE-RESTORE-VERIFY.md | End-to-end test: záloha → purge → restore → verify | rychlý/hluboký | ~1 min |
| **Release Agent** | RELEASE-AGENT.md | Pre-release kontrola + balíček | — | ~5 min |
| **Business Logic** | BUSINESS-LOGIC-AGENT.md | Extrakce business logiky z kódu | — | ~8 min |
| **Test Agent** | TEST-AGENT.md | Pytest + route coverage + Playwright (6 fází) | rychlý/hluboký | ~5/12 min |
| **Cloud Deploy** | CLOUD-DEPLOY.md | Analýza připravenosti pro cloud | — | ~5 min |
| **USB Deploy** | USB-DEPLOY.md | Přenos aplikace na jiný Mac | — | ~25 min |

---

## Spuštění

```
Přečti ORCHESTRATOR.md a zkoordinuj údržbu projektu. Zeptej se mě co potřebuji a navrhni plán.
```
