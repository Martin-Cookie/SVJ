# Doc Sync Agent – Synchronizace dokumentace s realitou projektu

> Spouštěj po větším bloku změn, ideálně společně s CODE-GUARDIAN auditem.
> Agent projde projekt, porovná stav kódu s dokumentací a navrhne opravy.

---

## Cíl

Zajistit že CLAUDE.md, docs/UI_GUIDE.md a README.md přesně odpovídají aktuálnímu stavu projektu **a vzájemně si neodporují**. Zastaralá nebo duplicitní dokumentace je horší než žádná — vede k chybným rozhodnutím.

Konkrétně:
1. **Aktualizovat** zastaralé informace (smazané/přejmenované soubory, změněné vzory)
2. **Doplnit** chybějící dokumentaci nových funkcí
3. **Pročistit duplikáty** — stejná informace nesmí být ve dvou souborech (jeden odkazuje na druhý)
4. **Ověřit křížové odkazy** — všechny `§` a `[odkaz]` vedou na existující sekce

---

## Instrukce

### Fáze 1: ANALÝZA (nic neměň)

Projdi celý projekt a porovnej skutečný stav kódu s dokumentací. Vytvoř report rozdílů.

### Fáze 2: PLÁN OPRAV

Ukaž strukturovaný plán přes update_plan tool:
- Co smazat (zastaralé)
- Co přidat (chybějící)
- Co upravit (nepřesné)

### Fáze 3: IMPLEMENTACE (až po schválení)

Po schválení plánu proveď opravy. Commitni jako: `docs: synchronizace dokumentace s aktuálním stavem projektu`

---

## 1. CLAUDE.md — Backend pravidla

### 1.1 Zastaralá pravidla
- Projdi KAŽDOU sekci CLAUDE.md
- Pro každé pravidlo/vzor ověř že odpovídající kód stále existuje a funguje tak jak je popsáno
- Hledej:
  - Zmínky o smazaných/přejmenovaných souborech, funkcích, modelech, routerech
  - Vzory kódu které se v projektu už nepoužívají
  - Konfigurační hodnoty které se změnily
  - Moduly/endpointy které byly odstraněny nebo přesunuty
  - Enum hodnoty které se změnily

### 1.2 Chybějící pravidla
- Projdi VŠECHNY soubory v `app/routers/`, `app/models/`, `app/services/`, `app/templates/`
- Najdi vzory které se opakují v kódu ale NEJSOU zdokumentované v CLAUDE.md:
  - Nové helper funkce používané napříč moduly
  - Nové konvence pojmenování
  - Nové datové modely nebo sloupce
  - Nové router vzory nebo middleware
  - Nové Jinja2 filtry nebo makra
  - Specifické workaroundy s komentářem `# POZOR` / `# HACK` / `# WORKAROUND`
- Zkontroluj jestli sekce „Uživatelské role" stále odpovídá plánu

### 1.3 Cesty k souborům
- Každý odkaz na soubor v CLAUDE.md (např. `app/routers/voting.py`, `docs/UI_GUIDE.md`) — existuje?
- Každý příklad importu (např. `from app.models import ...`) — funguje?
- Každý odkaz na sekci UI_GUIDE.md (např. `[UI_GUIDE.md § 13]`) — existuje ta sekce?

### 1.4 Kódové příklady
- Jsou code snippety v CLAUDE.md stále platné?
- Odpovídají aktuálnímu API (SQLAlchemy, FastAPI, Jinja2)?
- Používají aktuální názvy funkcí a proměnných?

---

## 2. docs/UI_GUIDE.md — Frontend pravidla

### 2.1 Zastaralá pravidla
- Projdi KAŽDOU sekci UI_GUIDE.md
- Pro každý UI vzor ověř že se v šablonách stále používá tak jak je popsáno
- Hledej:
  - CSS třídy které se změnily (Tailwind utility classes)
  - HTMX atributy které se změnily
  - Komponenty (tlačítka, tabulky, modaly) jejichž markup se vyvinul jinam
  - Makra která byla smazána nebo přejmenována
  - Ikony které se změnily

### 2.2 Chybějící vzory
- Projdi VŠECHNY šablony v `app/templates/`
- Najdi UI vzory které se opakují ale NEJSOU v UI_GUIDE.md:
  - Nové typy komponent (karty, stepper, progress bar...)
  - Nové HTMX interakce
  - Nové layout vzory
  - Nové formulářové vzory
  - Nové způsoby zobrazení dat

### 2.3 Konzistence s CLAUDE.md — deduplikace
- Pokud CLAUDE.md říká „UI detaily viz UI_GUIDE.md § X" — existuje ta sekce?
- Pokud oba soubory popisují stejnou věc — říkají totéž?
- Jsou křížové odkazy obousměrné? (CLAUDE.md → UI_GUIDE.md i zpět)
- **Aktivně hledej duplikáty**: sekce/odstavce které vysvětlují totéž v obou souborech
  - Logika (backend, routery, Python) patří do CLAUDE.md
  - UI detaily (HTML, CSS, Tailwind, HTMX markup) patří do UI_GUIDE.md
  - Duplicitní obsah **nahradit odkazem** na autoritativní soubor: `> Logika XY je v [CLAUDE.md § Sekce](../CLAUDE.md).`
  - Typické duplikáty: back URL navigace, wizard stepper logika, formulářová validace, upload workflow

### 2.4 Příklady HTML/CSS
- Jsou HTML snippety v UI_GUIDE.md stále platné?
- Odpovídají aktuálním šablonám?
- Používají aktuální Tailwind třídy?

---

## 3. README.md — Projektová dokumentace

### 3.1 Instalace a spuštění
- Ověř že instalační kroky fungují (správné příkazy, správné pořadí)
- Je zmíněna správná verze Pythonu?
- Jsou všechny závislosti v requirements.txt zmíněné?
- Funguje příkaz pro spuštění?
- Je zmíněn postup pro USB nasazení?

### 3.2 Seznam modulů
- Projdi skutečné routery v `app/routers/` a sidebaru v `base.html`
- Odpovídá seznam modulů v README realitě?
- Jsou všechny moduly popsané?
- Jsou popsány správně (název, funkce, cesta)?
- Chybí nové moduly?
- Jsou tam smazané moduly?

### 3.3 API endpointy
- Projdi VŠECHNY routery a extrahuj skutečné endpointy
- Porovnej se seznamem v README.md
- Chybějící endpointy přidej
- Smazané endpointy odstraň
- Změněné parametry/odpovědi aktualizuj

### 3.4 Screenshoty a ukázky
- Pokud README obsahuje screenshoty — odpovídají aktuálnímu UI?
- Pokud odkazuje na ukázkové soubory — existují?

---

## Formát reportu

Před opravami vytvoř report (vypiš do chatu):

```
## Doc Sync Report – [datum]

### CLAUDE.md
ZASTARALÉ (smazat/upravit):
- ř. XX: [co] — [proč zastaralé]
- ...

CHYBĚJÍCÍ (přidat):
- [co] — [kde v kódu se to používá]
- ...

NEFUNKČNÍ ODKAZY:
- ř. XX: [odkaz] — [soubor neexistuje / sekce neexistuje]
- ...

### UI_GUIDE.md
ZASTARALÉ:
- ...

CHYBĚJÍCÍ:
- ...

ROZPORY S CLAUDE.md:
- ...

### README.md
ZASTARALÉ:
- ...

CHYBĚJÍCÍ MODULY:
- ...

CHYBĚJÍCÍ ENDPOINTY:
- ...

### Souhrn
- Celkem změn: X
- CLAUDE.md: X úprav
- UI_GUIDE.md: X úprav
- README.md: X úprav
```

Po schválení oprav, commitni s message: `docs: synchronizace dokumentace s aktuálním stavem projektu`

---

## Spuštění

V Claude Code zadej:

```
Přečti soubor DOC-SYNC.md a proveď synchronizaci dokumentace s aktuálním stavem projektu. Nejdřív analyzuj a ukaž report, pak po schválení oprav dokumenty.
```
