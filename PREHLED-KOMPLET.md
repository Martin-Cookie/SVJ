# Kompletní přehled — Agenti, Skills, MCP servery

---

## Agenti (10)

### Vstupní body

| # | Agent | Soubor | SVJ | RAEL | Popis | Příkaz |
|---|-------|--------|:---:|:----:|-------|--------|
| 1 | **Session Start** | SESSION-START.md | ✅ | ✅ | Orientace na začátku nové session — zkontroluje stav projektu (git log, git status, reporty), ukáže přehled a zeptá se co chceš dělat. | `Přečti SESSION-START.md a proveď orientaci v projektu.` |
| 2 | **Orchestrátor** | ORCHESTRATOR.md | ✅ | ✅ | Koordinátor agentů — zeptá se co potřebuješ, zanalyzuje stav, navrhne které agenty spustit a v jakém pořadí. Čeká na potvrzení před každým krokem. | `Přečti ORCHESTRATOR.md a zkoordinuj údržbu projektu.` |

### Automatický

| # | Agent | Soubor | SVJ | RAEL | Popis | Rozdíly SVJ/RAEL |
|---|-------|--------|:---:|:----:|-------|-------------------|
| 3 | **Task Agent** | CLAUDE.md | ✅ | ✅ | Řídí postup práce — plán, mockupy, schválení, potvrzení commitu, report. Aktivuje se automaticky při zadání úkolu. | SVJ: `spusť server`, commit zvlášť. RAEL: `npm run dev`, commit+push, 3 jazyky (cs/en/sw) |

### Analytičtí agenti (nic neopravují, pouze reportují)

| # | Agent | Soubor | SVJ | RAEL | Popis | Kdy spustit | Příkaz |
|---|-------|--------|:---:|:----:|-------|-------------|--------|
| 4 | **Code Guardian** | CODE-GUARDIAN.md | ✅ | ✅ | Audit kódu — kvalita, bezpečnost, UI, výkon, testy, git hygiena. | Po bloku změn | `Přečti CODE-GUARDIAN.md a proveď audit projektu. Výstupem je AUDIT-REPORT.md. Nic neopravuj, pouze reportuj.` |
| 5 | **Doc Sync** | DOC-SYNC.md | ✅ | ✅ | Synchronizace CLAUDE.md, UI_GUIDE.md a README.md s realitou. Najde zastaralé, chybějící a rozporné info. | Po bloku změn | `Přečti DOC-SYNC.md a proveď synchronizaci dokumentace s aktuálním stavem projektu.` |
| 6 | **UX Optimizer** | UX-OPTIMIZER.md | ✅ | ✅ | Analýza procesů z 6 pohledů: uživatel, business analytik, UI designer, performance, error recovery, data quality. Včetně ASCII mockupů. | Zlepšení UX | `Přečti UX-OPTIMIZER.md a analyzuj [celou aplikaci / proces X]. Výstupem je UX-REPORT.md. Nic neopravuj.` |
| 7 | **Business Logic** | BUSINESS-LOGIC-AGENT.md | ✅ | ✅ | Extrakce business logiky z kódu — procesy, pravidla, datový model, edge cases, integrace. Dva výstupy: technický + srozumitelný. | Dokumentace, onboarding | `Přečti BUSINESS-LOGIC-AGENT.md a proveď extrakci business logiky. Nic neopravuj.` |
| 8 | **Backup Agent** | BACKUP-AGENT.md | ✅ | ✅ | Kontrola integrity záloh — ověří že záloha jde vytvořit i obnovit. Testuje na kopiích dat. | Před změnami DB | `Přečti BACKUP-AGENT.md a proveď kontrolu integrity zálohovacího systému. Testuj na kopiích dat.` |
| 9 | **Cloud Deploy** | CLOUD-DEPLOY.md | ✅ | ✅ | Analýza připravenosti pro nasazení na internet — bezpečnost, platforma, konfigurace. | Nasazení na internet | `Přečti CLOUD-DEPLOY.md a analyzuj připravenost projektu pro nasazení do cloudu. Navrhni nejlepší variantu.` |

### Akční agent (provádí změny)

| # | Agent | Soubor | SVJ | RAEL | Popis | Kdy spustit | Příkaz |
|---|-------|--------|:---:|:----:|-------|-------------|--------|
| 10 | **Release Agent** | RELEASE-AGENT.md | ✅ | ✅ | Příprava verze — pre-release kontrola, changelog, git tag, balíček. | Před vydáním | `Přečti RELEASE-AGENT.md a připrav release. Nejdřív proveď pre-release kontrolu, pak po schválení připrav balíček.` |

#### Rozdíly Release Agenta:

| | SVJ | RAEL |
|---|-----|------|
| Build | pytest | `npm run build` + `npm run lint` |
| DB test | SQLAlchemy migrace | Prisma seed na čisté DB |
| Balíček | USB ZIP + `spustit.command` | Git tag + push |
| Kontrola | Všechny stránky | Všechny stránky + všechny role + dark mode + lokalizace |

---

## Dokumentace projektu

| Soubor | SVJ | RAEL | Popis |
|--------|:---:|:----:|-------|
| CLAUDE.md | ✅ | ✅ | Backend pravidla + Task Agent (odlišné per projekt) |
| docs/UI_GUIDE.md | ✅ | ✅ | UI konvence (SVJ: HTMX/Jinja2, RAEL: React/Next.js) |
| docs/UI_PRINCIPLES_PORTABLE.md | ✅ | ❌ | Přenositelné UI principy (jen FastAPI stack) |
| docs/SPEC-payment-import.md | ❌ | ✅ | Specifikace importu plateb |
| README.md | ✅ | ✅ | Projektová dokumentace |
| PROJECT_SPEC.md | ❌ | ✅ | Specifikace projektu |
| AGENTS.md | ✅ | ✅ | Přehled agentů |

---

## Skills (7 — globální, fungují v obou projektech)

| Skill | Popis | Kdy se aktivuje |
|-------|-------|-----------------|
| **docx** | Tvorba Word dokumentů | Při práci s .docx soubory |
| **pdf** | Tvorba a úprava PDF | Při práci s .pdf soubory |
| **pptx** | Tvorba prezentací | Při práci s .pptx soubory |
| **xlsx** | Tvorba spreadsheetů | Při práci s .xlsx soubory |
| **frontend-design** | Kvalitní UI design | Při tvorbě webových komponent |
| **product-self-knowledge** | Znalosti o Anthropic produktech | Při dotazech na Claude/API |
| **skill-creator** | Tvorba nových skills | Při vytváření vlastních skills |

### Plugin

| Plugin | Popis |
|--------|-------|
| **Superpowers** | Brainstorming, TDD, plánování, debugging, code review, subagenti |

---

## MCP servery (4)

| MCP server | SVJ | RAEL | Scope | Popis |
|------------|:---:|:----:|-------|-------|
| **Context7** | ✅ | ✅ | Built-in | Dokumentace knihoven |
| **Playwright** | ✅ | ✅ | User (globální) | Testování UI v prohlížeči |
| **SQLite** | ✅ | ✅ | Lokální per projekt | Přímý přístup k DB |
| **GitHub** | ✅ | ✅ | Lokální per projekt | GitHub issues, PR, commity |

### Cesty k databázím

| Projekt | SQLite cesta | GitHub repo |
|---------|-------------|-------------|
| SVJ | `data/svj.db` | `Martin-Cookie/SVJ` |
| RAEL | `prisma/dev.db` | `Martin-Cookie/rael-school` |

---

## Tech stack porovnání

| | SVJ | RAEL |
|---|-----|------|
| **Backend** | FastAPI + Python | Next.js 14 + TypeScript |
| **Frontend** | Jinja2 + HTMX + Vanilla JS | React + TypeScript |
| **CSS** | Tailwind CSS (CDN) | Tailwind CSS |
| **Databáze** | SQLite + SQLAlchemy | SQLite + Prisma |
| **Lokalizace** | Čeština | cs / en / sw |
| **Dark mode** | CSS override (dark-mode.css) | Tailwind `dark:` třídy |
| **Deploy** | Lokálně + USB | Lokálně (npm run dev) |
| **Git workflow** | Commit lokálně, push ručně | Commit + push po každém úkolu |

---

## Doporučený workflow

```
Start nové session:
  → Session Start (orientace + co chceš dělat)

Nevím co spustit:
  → Orchestrátor (navrhne plán agentů)

Denní práce:
  → Zadávej úkoly → Task Agent automaticky

Po bloku změn:
  1. Code Guardian (audit)
  2. Doc Sync (dokumentace)
  3. UX Optimizer (volitelně, pokud se měnilo UI)

Zlepšení UX:
  → UX Optimizer (celá aplikace nebo konkrétní modul)

Před releasem:
  1. Code Guardian
  2. Backup Agent
  3. Doc Sync
  4. Release Agent

Dokumentace:
  1. Business Logic Agent
  2. Doc Sync

Nasazení do cloudu:
  → Cloud Deploy
```

---

## Zkratky Claude Code

| Zkratka | Co dělá |
|---------|---------|
| **Tab** | Zapne deep thinking |
| **Shift+Tab** | Přepne bypass/accept/plan mode |
| **#** | Přidá memory |
| **@soubor** | Přidá soubor do kontextu |
| **/clear** | Vyčistí konverzaci |
| **/exit** | Ukončí session |
| **/mcp** | Správa MCP serverů |
| **/remote-control** | Ovládání z telefonu |
| **/config** | Nastavení (Remote Control pro všechny session) |

---

## Remote Control (ovládání z telefonu)

```bash
# Jednorázově
/remote-control

# Trvale pro všechny session
/config → "Enable Remote Control for all sessions" → true
```

Naskenuj QR kód telefonem → otevře se session v Claude appce.
MacBook musí být zapnutý a terminál otevřený.
