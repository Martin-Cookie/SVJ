# UX Optimizer Agent – Analýza a návrhy UX zlepšení

> Spouštěj když chceš zlepšit UX, zjednodušit workflow nebo optimalizovat procesy.
> UI konzistence a HTMX interakce se nekontrolují zde — ty řeší Code Guardian.

---

## Cíl

Projít zadaný proces (nebo celou aplikaci) z pohledu 6 expertních rolí a navrhnout zlepšení. Výstup: `docs/reports/UX-REPORT.md`.

**NEPRAV ŽÁDNÝ KÓD. POUZE ANALYZUJ A NAVRHUJ.**

---

## Rozsah

Uživatel zadá:
- **Celá aplikace** → projdi VŠECHNY moduly v sidebaru
- **Konkrétní modul** → zaměř se pouze na zadaný modul

### Rychlý vs. hluboký mód

- **Rychlý**: projdi jen moduly které se změnily od posledního UX reportu + moduly z kontextu orchestrátora. Aplikuj pohledy 1 (běžný uživatel) a 3 (UI/UX designer).
- **Hluboký**: projdi VŠECHNY moduly, všech 6 pohledů.

Orchestrátor řekne který mód. Bez instrukce = hluboký.

### Kontext od orchestrátora

Pokud orchestrátor předá nálezy (stránky se selháním, problémové flows), začni analýzou těchto oblastí.

---

## 6 expertních pohledů

### 1. Běžný uživatel
- Je jasné co dělat, kde kliknout, co vyplnit?
- Pochopím terminologii bez školení?
- Vím kde v procesu jsem? Najdu věc do 3 kliknutí?
- Můžu se vrátit bez ztráty dat?

### 2. Business proces analytik
- Zbytečné kroky které jdou sloučit/odstranit?
- Automatizovatelná manuální práce?
- Duplicitní zadávání dat? Chybějící hromadné operace?
- Rozumné defaulty místo povinného vyplňování?

### 3. UI/UX designer
- Jasná vizuální hierarchie?
- Konzistentní layout napříč stránkami?
- Přehledné formuláře (ne příliš dlouhé)?
- Řešený prázdný stav (žádná data)?

### 4. Performance analytik
- Kolik kliknutí trvá nejčastější úkol? Dá se snížit?
- Časté akce snadno přístupné (ne v submenu)?
- Chybějící bulk operace?

### 5. Error recovery expert
- Srozumitelné chybové zprávy (říkají CO opravit)?
- Zachování dat při chybě?
- Destruktivní akce chráněné potvrzením?
- Undo možnost?

### 6. Data quality expert
- Dostatečná validace (formát, rozsah, povinnost)?
- Detekce duplicit?
- Rozumné výchozí hodnoty?
- Import s preview před uložením?

---

## Formát výstupu

Vytvoř `docs/reports/UX-REPORT.md`:

```markdown
# UX Analýza – [Název / Celá aplikace]

> Analyzováno: [datum]

## Souhrn

| Pohled | Kritické | Důležité | Drobné |
|--------|----------|----------|--------|
| Běžný uživatel | X | X | X |
| Business analytik | X | X | X |
| UI/UX designer | X | X | X |
| Performance analytik | X | X | X |
| Error recovery | X | X | X |
| Data quality | X | X | X |

## Nálezy

### [Stránka/Proces]

#### Nález #N: [název]
- **Severity:** KRITICKÉ / DŮLEŽITÉ / DROBNÉ
- **Pohled:** [role]
- **Co a kde:** [popis + URL/akce]
- **Dopad:** [jak ovlivňuje uživatele]
- **Řešení:** [konkrétní postup]
- **Kde v kódu:** [soubor:řádek]
- **Náročnost:** [nízká/střední/vysoká] ~[čas]
- **Rozhodnutí:** fix / varianty
- **Jak otestovat:** [URL → klik → výsledek]
- **Mockup:**
  Současný stav: [ASCII wireframe]
  Navrhovaný stav: [ASCII wireframe]

## Top 5 doporučení

| # | Návrh | Dopad | Složitost | Čas | Priorita |
|---|-------|-------|-----------|-----|----------|
| 1 | ... | Vysoký | Nízká | ~5 min | HNED |

## Quick wins
- [ ] ...
```

---

## Spuštění

```
Přečti UX-OPTIMIZER.md a analyzuj [celou aplikaci / proces X]. Výstup: docs/reports/UX-REPORT.md. Nic neopravuj.
```
