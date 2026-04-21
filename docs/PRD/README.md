# PRD — SVJ Správa (Product Requirements Document)

> **Klonovací spec**: Tento balíček obsahuje úplnou specifikaci pro regeneraci aplikace **SVJ Správa** v novém repozitáři. Dodržením této specifikace vznikne funkčně ekvivalentní aplikace se stejnými URL, datovým modelem a UI konvencemi.

---

## Pro koho je tento PRD

Primárně pro **LLM agenta** (Claude Code nebo podobný), kterého chceš použít k regeneraci projektu v novém worktree. Sekundárně pro lidského vývojáře jako referenci.

---

## Struktura balíčku

| Soubor | Účel | Typická délka |
|---|---|---|
| [`README.md`](README.md) | **Tento soubor.** Navigace, jak balíček použít, fáze implementace. | ~200 řádků |
| [`PRD.md`](PRD.md) | Přehled, doména, tech stack, architektura, non-goals, doménový slovník. | ~400 řádků |
| [`PRD_DATA_MODEL.md`](PRD_DATA_MODEL.md) | Deterministická specifikace všech tabulek, sloupců, enumů, relací, indexů. | ~1200 řádků |
| [`PRD_MODULES.md`](PRD_MODULES.md) | Per-modul: user stories + acceptance criteria + URL routy + workflow. 14 modulů. | ~1500 řádků |
| [`PRD_UI.md`](PRD_UI.md) | Klíčové UI konvence (redestilát): layout, tabulky, formuláře, HTMX vzory. | ~400 řádků |
| [`PRD_ACCEPTANCE.md`](PRD_ACCEPTANCE.md) | Playwright test scénáře per modul + seed data instrukce. | ~500 řádků |
| `appendices/CLAUDE.md` | **Úplná** kopie backend pravidel. Čti pokud potřebuješ detail mimo PRD. | ~370 řádků |
| `appendices/UI_GUIDE.md` | **Úplná** kopie UI konvencí. Referenční zdroj pro vše UI. | ~1700 řádků |
| `appendices/README.md` | **Úplná** kopie projektové dokumentace se všemi moduly a featurami. | ~1900 řádků |

---

## Doporučený postup regenerace

### Fáze 0 — příprava (5 min)
1. **Přečti v tomto pořadí**: `PRD.md` → `PRD_DATA_MODEL.md` → `PRD_MODULES.md` → `PRD_UI.md`.
2. **Přílohy** (`appendices/`) jsou pro detail, ne pro lineární čtení. Konzultuj při implementaci konkrétního modulu nebo UI vzoru.
3. Založ nový repozitář, Python 3.9+, vytvoř virtuální prostředí.

### Fáze 1 — skeleton (1 běh agenta, ~2 h)
Regenerovatelné v jednom běhu:
- Adresářová struktura (`app/`, `app/models/`, `app/routers/`, `app/services/`, `app/templates/`, `app/static/`, `data/`, `tests/`, `docs/`)
- `requirements.txt` (viz [§ Tech stack v PRD.md](PRD.md#tech-stack))
- `app/config.py`, `app/database.py`, `app/utils.py`, `app/main.py` (lifespan + router include + exception handlers + security headers)
- **Všechny modely a enumy** dle `PRD_DATA_MODEL.md` (+ `__all__` v `app/models/__init__.py`)
- `app/templates/base.html` + sidebar + dark mode toggle dle `PRD_UI.md`
- `app/static/js/app.js` + `custom.css` + `dark-mode.css`

**Kritérium Fáze 1 hotovo**: `uvicorn app.main:app` nastartuje, `GET /` vrátí prázdný dashboard bez chyb, DB soubor vznikne, všechny tabulky v SQLite existují.

### Fáze 2 — MVP moduly (2–3 běhy, ~8 h)
Per modul jeden běh. Doporučené pořadí (respektuje závislosti):

1. **Administrace** (`/sprava`) — SvjInfo, adresy, členové výboru, číselníky, emailové šablony, zálohy. *Bez toho nepůjdou importy.*
2. **Vlastníci** (`/vlastnici`) — CRUD + import z Excelu.
3. **Jednotky** (`/jednotky`) — CRUD + propojení s vlastníky (OwnerUnit).
4. **Prostory** (`/prostory`) + **Nájemci** (`/najemci`).
5. **Dashboard** (`/`) — statistiky, poslední aktivita.

**Kritérium Fáze 2 hotovo**: smoke Playwright scénáře pro 1–5 v `PRD_ACCEPTANCE.md` projdou.

### Fáze 3 — pokročilé moduly (3–4 běhy, ~12 h)
6. **Hlasování** (`/hlasovani`) — sessions, lístky, zpracování, import.
7. **Rozesílání** (`/rozesilani`) — daňové výpisy, PDF matching, emailová rozesílka.
8. **Platby** (`/platby`) — předpisy, výpisy, vyúčtování, nesrovnalosti. Nejrozsáhlejší modul.
9. **Synchronizace** (`/synchronizace`) + **Kontrola podílů** (`/kontrola-podilu`).
10. **Vodoměry** (`/vodometry`).
11. **Nastavení** (`/nastaveni`) — SMTP profily, historie emailů.
12. **Bounces** (`/rozesilani/bounces`).

### Fáze 4 — testování a dokončení
- Spustit všechny scénáře z `PRD_ACCEPTANCE.md`.
- Zkopírovat `appendices/CLAUDE.md` a `appendices/UI_GUIDE.md` do `docs/` cílového projektu.
- Aktualizovat `README.md` dle přílohy.

---

## Jak zacházet s konvencemi

- **URL slugy, názvy tabulek, enum hodnoty, názvy sloupců** → **deterministické**, dodrž přesně co říká `PRD_DATA_MODEL.md` a `PRD_MODULES.md`.
- **Implementace routerů, šablon, služeb** → **volnost v detailech**. Řiď se user stories a acceptance criteria. Konvence v `PRD_UI.md` jsou závazné (sticky header, sort, search, export, HTMX partials...).
- **Nejasnost?** Nejdřív konzultuj `appendices/CLAUDE.md` (backend) nebo `appendices/UI_GUIDE.md` (UI), pak se rozhodni.

---

## Co tento PRD **nepokrývá**

- Autentizaci a uživatelské role (`/sprava` je otevřené, viz `docs/USER_ROLES.md` v originálu).
- Detailní algoritmy fuzzy matchingu (vlastníci, platby) — lze reimplementovat podle user stories, přesná shoda s originálem není vyžadována.
- Obsah e-mailových šablon (seedují se z defaultů, uživatel je upraví).
- Historická data — seed data pro demo jsou v `PRD_ACCEPTANCE.md`.

---

## Velikost a odhad

| Metrika | Hodnota |
|---|---:|
| Produkční kód (Python + HTML + JS/CSS) | ~56 000 LOC |
| Počet modelů | 25 |
| Počet enumů | 20+ |
| Počet tabulek | 30+ |
| Počet indexů | 87 |
| Počet routerů | 14 |
| Počet endpointů | ~120 |
| Počet testů (pytest) | 580 |
| Tech stack | FastAPI + Jinja2 + HTMX + Tailwind + SQLAlchemy + SQLite |
| Celkový čas regenerace (odhad) | 20–30 h práce LLM agenta, 3–5 běhů |

---

## Kontakt a atribuce

Původní projekt: **Martin Kočí** (martin.koci@gmail.com), 2025–2026. Tato specifikace je destilát z ~56k LOC produkčního kódu.
