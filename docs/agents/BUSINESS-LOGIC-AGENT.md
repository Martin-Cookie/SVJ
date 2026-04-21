# Business Logic Agent – Extrakce business logiky z kódu

> Spouštěj před přepisem do nového stacku, pro onboarding nebo dokumentaci.

---

## Cíl

Projít celý projekt a extrahovat business logiku do dvou souborů:
1. **docs/BUSINESS-LOGIC.md** — technický dokument pro vývojáře/Clauda
2. **docs/BUSINESS-SUMMARY.md** — srozumitelný souhrn pro netechnického člověka

**NEPRAV ŽÁDNÝ KÓD. POUZE ANALYZUJ A DOKUMENTUJ.**

---

## Instrukce

Projdi VŠECHNY soubory: modely, routery, services, šablony, konfigurace. Čti kód a hledej business logiku.

### Kontext od orchestrátora

Pokud orchestrátor předá kontext (nově přidané moduly, změněné flows), začni těmito oblastmi.

---

## Co extrahovat

### 1. Business procesy (workflow)
- Vícekrokové procesy (vytvoření → úprava → schválení → dokončení)
- Stavové automaty (draft → active → completed)
- Podmíněné větvení, automatické akce na pozadí

### 2. Business pravidla
- Validační pravidla (formát, rozsah, povinnost, unikátnost)
- Výpočetní pravidla (vzorce, konverze, zaokrouhlování)
- Prahy a limity (magická čísla — proč 0.6? proč 80 CZK?)
- Pořadí operací (FK závislosti, cascade)
- Defaultní hodnoty, formátování, řazení, deduplikace, párování

### 3. Datový model
- Entity a jejich business účel (ne jen název tabulky)
- Relace a sémantika (vlastník VLASTNÍ jednotku, ne jen FK)
- Enum hodnoty — business kontext každé hodnoty
- Computed/derived atributy, temporální aspekty

### 4. Edge cases a workaroundy
- Komentáře `# POZOR`, `# HACK`, `# WORKAROUND`, `# BUG`
- Try/except s nestandardním chováním
- Podmínky pro speciální případy (`if typ == "SJM"`)
- Platform-specific kód, encoding workaroundy

### 5. Integrace
- Import/export — zdroje, formáty, mapování, validace, chybové stavy
- Email/notifikace — kdy, komu, obsah, SMTP
- PDF generování — layout, knihovny

---

## Formát výstupu

### BUSINESS-LOGIC.md (technický)

```markdown
# Business logika — SVJ

> Extrahováno z kódu [datum].

## 1. Business procesy
### 1.1 [Proces]
**Účel:** ...
**Kroky:** 1. ... 2. ... 3. ...
**Kde v kódu:** `soubor.py:funkce()` ř. XX-YY
**Stavový diagram:** [stav1] → akce → [stav2]

## 2. Business pravidla
### 2.1 [Pravidlo]
**Pravidlo:** ... **Důvod:** ... **Kde:** `soubor:řádek` **Hodnoty:** ...

## 3. Datový model
## 4. Edge cases a workaroundy
## 5. Integrace

## Appendix: Důležité konstanty
| Konstanta | Hodnota | Kde | Účel |
```

### BUSINESS-SUMMARY.md (netechnický)

```markdown
# Co aplikace dělá — SVJ

> Srozumitelný popis pro netechnického člověka. Vytvořeno [datum].

## Přehled
[2-3 věty]

## Hlavní funkce
### [Funkce — srozumitelný název]
[Popis z pohledu uživatele]

## Jak spolu věci souvisí
## Důležitá pravidla
## Omezení a specifika
```

---

## Spuštění

```
Přečti BUSINESS-LOGIC-AGENT.md a extrahuj business logiku. Výstup: docs/BUSINESS-LOGIC.md + docs/BUSINESS-SUMMARY.md. Nic neměň v kódu.
```
