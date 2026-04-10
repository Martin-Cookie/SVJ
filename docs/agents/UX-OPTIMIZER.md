# UX Optimizer Agent – Analýza a návrhy zlepšení procesů

> Spouštěj když chceš zlepšit uživatelský zážitek, zjednodušit workflow nebo optimalizovat procesy.
> Agent se dívá na aplikaci šesti různými očima a navrhuje konkrétní zlepšení.

---

## Cíl

Projít zadaný proces (nebo celou aplikaci) a navrhnout zlepšení z pohledu šesti expertních rolí.
Výstupem je report s nálezy, návrhy a mockupy.

**NEPRAV ŽÁDNÝ KÓD. POUZE ANALYZUJ A NAVRHUJ.**

---

## Rozsah

Uživatel zadá jedno z:

### A) Celá aplikace
```
Přečti UX-OPTIMIZER.md a analyzuj celou aplikaci. Projdi všechny moduly a navrhni zlepšení.
```
Agent projde VŠECHNY moduly v sidebaru, jeden po druhém.

### B) Konkrétní proces/modul
```
Přečti UX-OPTIMIZER.md a analyzuj proces [název]. Navrhni zlepšení.
```
Agent se zaměří pouze na zadaný modul/proces.

---

## 6 expertních pohledů

### 1. Běžný uživatel
Člověk který aplikaci vidí poprvé nebo ji používá jednou za měsíc.

**Otázky:**
- Je jasné co mám dělat? Kde kliknout? Co vyplnit?
- Pochopím terminologii bez školení?
- Vím kde v procesu jsem a kolik kroků zbývá?
- Najdu to co hledám do 3 kliknutí?
- Je jasné co se stalo po mé akci? (úspěch, chyba, čekání)
- Můžu se vrátit zpět bez ztráty dat?

**Hledej:**
- Matoucí názvy, ikony, popisky
- Chybějící nápověda nebo vysvětlení
- Slepé uličky (kam kliknu a nevím jak zpět)
- Příliš mnoho kroků pro jednoduchý úkol
- Chybějící potvrzení úspěšné akce

### 2. Business proces analytik
Expert na efektivitu workflow a eliminaci plýtvání.

**Otázky:**
- Jsou v procesu zbytečné kroky které jdou sloučit nebo odstranit?
- Dá se něco automatizovat co se teď dělá ručně?
- Jsou data zadávána opakovaně na více místech?
- Je pořadí kroků optimální?
- Existují bottlenecky kde se proces zasekne?
- Dají se paralelizovat kroky které jsou teď sekvenční?

**Hledej:**
- Duplicitní zadávání stejných dat
- Kroky které by šly přeskočit s rozumnými defaulty
- Manuální práce kterou by šlo automatizovat
- Chybějící hromadné operace (musí se dělat jeden po jednom)
- Zbytečné přechody mezi stránkami

### 3. UI/UX designer
Expert na vizuální design, layout a interakční vzory.

**Otázky:**
- Je vizuální hierarchie jasná? (co je důležité, co sekundární)
- Jsou akční prvky snadno rozpoznatelné a dostupné?
- Je layout konzistentní napříč stránkami?
- Jsou formuláře přehledné a ne příliš dlouhé?
- Funguje stránka na mobilu?
- Je prázdný stav (žádná data) řešený smysluplně?

**Hledej:**
- Přehlcené stránky (příliš mnoho informací najednou)
- Nekonzistentní styly (tlačítka, barvy, spacing)
- Špatná vizuální hierarchie (vše vypadá stejně důležité)
- Chybějící vizuální zpětná vazba (loading, success, error)
- Formuláře které by šly rozdělit do kroků nebo zjednodušit
- Akce které jsou schované nebo těžko najitelné

### 4. Performance analytik
Expert na rychlost a efektivitu uživatelské práce.

**Otázky:**
- Kolik kliknutí/kroků trvá nejčastější úkol?
- Dá se počet kroků snížit?
- Jsou nejčastější akce snadno přístupné? (ne schované v submenu)
- Načítá se stránka rychle? Jsou zbytečné přesměrování?
- Dá se použít klávesová zkratka místo myši?
- Je search dostatečně chytrý? (autocomplete, fuzzy)

**Hledej:**
- Časté akce schované hluboko v navigaci
- Zbytečná přesměrování (POST → redirect → redirect)
- Chybějící bulk operace
- Pomalé načítání bez loading indikátoru
- Možnosti pro keyboard shortcuts

### 5. Error recovery expert
Expert na ošetření chyb a obnovu po selhání.

**Otázky:**
- Co se stane když uživatel zadá špatná data?
- Je chybová zpráva srozumitelná a říká CO opravit?
- Ztratí uživatel data když se něco pokazí?
- Dá se akce vrátit zpět (undo)?
- Co se stane při výpadku internetu / refreshi stránky?
- Jsou destruktivní akce chráněné potvrzením?

**Hledej:**
- Generické chybové hlášky ("Něco se pokazilo")
- Ztráta vyplněných dat po chybě (formulář se vymaže)
- Nevratné akce bez potvrzení
- Chybějící validace na straně klienta (chyba až po odeslání)
- Chybějící autosave u dlouhých formulářů

### 6. Data quality expert
Expert na kvalitu, konzistenci a integritu dat.

**Otázky:**
- Jsou vstupy validované dostatečně? (formát, rozsah, povinnost)
- Může vzniknout nekonzistence mezi souvisejícími daty?
- Jsou duplicity detekovány a ošetřeny?
- Jsou výchozí hodnoty rozumné?
- Je jasné co je povinné a co volitelné?
- Jsou importovaná data validovaná před uložením?

**Hledej:**
- Chybějící validace (email bez @, záporné částky, datum v budoucnosti)
- Možnost vytvořit duplicitní záznamy
- Nekonzistence mezi propojenými entitami
- Importy bez preview/kontroly před uložením
- Chybějící audit trail (kdo co kdy změnil)

---

## Formát výstupu

### UX-REPORT.md

```markdown
# UX Analýza — [Název procesu / Celá aplikace]

> Analyzováno: [datum]
> Rozsah: [celá aplikace / konkrétní proces]

## Souhrn

| Pohled | Kritické | Důležité | Drobné |
|--------|----------|----------|--------|
| Běžný uživatel | X | X | X |
| Business analytik | X | X | X |
| UI/UX designer | X | X | X |
| Performance analytik | X | X | X |
| Error recovery | X | X | X |
| Data quality | X | X | X |
| **Celkem** | **X** | **X** | **X** |

---

## Nálezy a návrhy

### [Proces/Stránka 1]

#### Nález #1: [stručný název]
- **Severity:** KRITICKÉ / DŮLEŽITÉ / DROBNÉ
- **Pohled:** [která role to našla]
- **Co a kde:** [co je špatně + kde v aplikaci: URL, stránka, akce]
- **Dopad:** [jak to ovlivňuje uživatele]
- **Řešení:** [konkrétní postup opravy, ne vágní "vylepšit"]
- **Varianty:** [pokud existuje víc přístupů — popsat s pro/proti, jinak "—"]
- **Kde v kódu:** [soubor:řádek]
- **Náročnost:** [nízká/střední/vysoká] ~[odhad času]
- **Závislosti:** [závisí na jiném nálezu? "nejdřív #X", jinak "—"]
- **Regrese riziko:** [nízké/střední/vysoké — může oprava rozbít něco?]
- **Rozhodnutí:** 🔧 jen opravit / ❓ potřeba rozhodnutí uživatele
- **Jak otestovat:** [krok za krokem: URL → klik → očekávaný výsledek]
- **Mockup:**
  ```
  ┌─────────────────────────────────┐
  │  Současný stav:                 │
  │  [popis nebo ASCII wireframe]   │
  └─────────────────────────────────┘

  ┌─────────────────────────────────┐
  │  Navrhovaný stav:               │
  │  [popis nebo ASCII wireframe]   │
  └─────────────────────────────────┘
  ```

### [Proces/Stránka 2]
...

---

## Top 5 doporučení (podle dopadu)

| # | Návrh | Dopad | Složitost | Čas | Závisí na | Rozhodnutí | Priorita |
|---|-------|-------|-----------|-----|-----------|------------|----------|
| 1 | ... | Vysoký | Nízká | ~5 min | — | 🔧 | HNED |
| 2 | ... | Vysoký | Střední | ~30 min | #1 | ❓ | BRZY |
| 3 | ... | Střední | Nízká | ~10 min | — | 🔧 | BRZY |
| 4 | ... | Střední | Střední | ~1 hod | — | ❓ | POZDĚJI |
| 5 | ... | Nízký | Nízká | ~5 min | — | 🔧 | POZDĚJI |

---

## Quick wins (nízká složitost, okamžitý efekt)
- [ ] ...
- [ ] ...
- [ ] ...
```

---

## Spuštění

### Celá aplikace:
```
Přečti UX-OPTIMIZER.md a analyzuj celou aplikaci. Projdi všechny moduly a navrhni zlepšení z pohledu všech 6 expertních rolí. Výstupem je docs/reports/UX-REPORT.md. Nic neopravuj.
```

### Konkrétní proces:
```
Přečti UX-OPTIMIZER.md a analyzuj proces [hlasování / import / platby / ...]. Navrhni zlepšení. Výstupem je docs/reports/UX-REPORT.md. Nic neopravuj.
```
