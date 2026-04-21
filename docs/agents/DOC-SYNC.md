# Doc Sync Agent – Synchronizace dokumentace s realitou

> Spouštěj po bloku změn. Zajistí že CLAUDE.md, UI_GUIDE.md a README.md odpovídají kódu.

---

## Cíl

Synchronizovat dokumentaci s kódem: aktualizovat zastaralé, doplnit chybějící, pročistit duplikáty, ověřit křížové odkazy.

---

## Instrukce

1. **ANALÝZA** (nic neměň) — porovnej kód s dokumentací, vytvoř report
2. **PLÁN OPRAV** — ukaž co smazat/přidat/upravit
3. **IMPLEMENTACE** (po schválení) — oprav a commitni: `docs: synchronizace dokumentace`

### Rychlý vs. hluboký mód

- **Rychlý** (po menších změnách): kontroluj jen sekce dokumentace dotčené změněnými soubory:
  ```bash
  git diff --name-only $(git log --oneline -1 docs/reports/AUDIT-REPORT.md | cut -d' ' -f1)..HEAD -- app/
  ```
  Ze změněných souborů odvoď které sekce CLAUDE.md/UI_GUIDE.md/README.md mohou být zastaralé.
- **Hluboký** (před releasem): kontroluj KAŽDOU sekci všech tří dokumentů

Orchestrátor řekne který mód. Bez instrukce = hluboký.

### Kontext od orchestrátora

Pokud orchestrátor předá kontext (přejmenované funkce, nové vzory, nálezy z jiných agentů), začni ověřením těchto konkrétních bodů.

---

## 1. CLAUDE.md — Backend pravidla

### Zastaralé
- Pro KAŽDÉ pravidlo/vzor ověř že kód stále existuje a funguje popsaným způsobem
- Zmínky o smazaných/přejmenovaných souborech, funkcích, modelech, routerech
- Vzory kódu které se nepoužívají, enum hodnoty které se změnily

### Chybějící
- Projdi `app/routers/`, `app/models/`, `app/services/`, `app/templates/`
- Hledej opakující se vzory bez dokumentace: helper funkce, konvence, modely, middleware, filtry, workaroundy (`# POZOR`, `# HACK`)

### Odkazy a příklady
- Každý odkaz na soubor/sekci → existuje?
- Každý import příklad → funguje?
- Code snippety → odpovídají aktuálnímu API?

---

## 2. UI_GUIDE.md — Frontend pravidla

### Zastaralé
- Pro každý UI vzor ověř použití v šablonách
- Změněné CSS třídy, HTMX atributy, markup komponent, makra, ikony

### Chybějící
- Projdi `app/templates/` — nové opakující se vzory bez dokumentace
- Nové komponenty, HTMX interakce, layout/formulářové vzory

### Deduplikace s CLAUDE.md
- Backend logika patří do CLAUDE.md, UI markup do UI_GUIDE.md
- Duplikáty nahradit křížovým odkazem
- Ověřit obousměrnost odkazů

---

## 3. README.md — Projektová dokumentace

### Kontroly
- Instalační kroky funkční? Správná verze Pythonu?
- Seznam modulů odpovídá `app/routers/` a sidebaru v `base.html`?
- API endpointy kompletní? (projdi routery, porovnej s README)
- Screenshoty/ukázky aktuální?

---

## Formát reportu

```
## Doc Sync Report – [datum]

### CLAUDE.md
ZASTARALÉ: [ř. XX: co — proč]
CHYBĚJÍCÍ: [co — kde v kódu]
NEFUNKČNÍ ODKAZY: [ř. XX: odkaz — důvod]

### UI_GUIDE.md
ZASTARALÉ: [...]
CHYBĚJÍCÍ: [...]
ROZPORY S CLAUDE.md: [...]

### README.md
ZASTARALÉ: [...]
CHYBĚJÍCÍ MODULY/ENDPOINTY: [...]

### Souhrn
Celkem změn: X (CLAUDE.md: X, UI_GUIDE.md: X, README.md: X)
```

---

## Spuštění

```
Přečti DOC-SYNC.md a synchronizuj dokumentaci. Nejdřív report, pak po schválení opravy.
```
