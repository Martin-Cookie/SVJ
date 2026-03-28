# Aplikace pro správu SVJ -- shrnutí pro laika

> Automaticky vygenerováno z kódu dne 2026-03-27 (aktualizace z 2026-03-09).
> Technické detaily viz [BUSINESS-LOGIC.md](BUSINESS-LOGIC.md).

---

## Co aplikace dělá

Aplikace slouží ke správě **Společenství vlastníků jednotek (SVJ)** -- tedy společenství lidí, kteří vlastní byty či nebytové prostory v jednom domě. Pokrývá všechny hlavní činnosti, které SVJ potřebuje: evidenci vlastníků a jejich bytů, hlasování per rollam, hromadné rozesílání daňových podkladů, synchronizaci dat s externími zdroji, kontrolu podílů, evidenci plateb a vyúčtování, správu společných prostor a nájemců.

Aplikace běží jako webová stránka na počítači -- není potřeba internet (kromě odesílání emailů). Ovládá se přes prohlížeč (Chrome, Safari, Firefox).

---

## Hlavní funkce

### 1. Evidence vlastníků a jednotek

**Co to je:** Základní databáze všech vlastníků (lidí i firem) a jejich bytů/nebytových prostor v domě.

**Co aplikace umí:**
- Evidovat jména, kontakty (email, telefon), adresy, rodná čísla / IČ
- Ke každému vlastníkovi evidovat, které jednotky vlastní a s jakým podílem
- Rozlišovat spoluvlastnictví manželů (SJM -- "společné jmění manželů") od běžného vlastnictví
- Uchovávat historii -- když se vlastník změní, starý záznam se nesmaže, ale označí se datem ukončení
- Hledat vlastníky podle jména, emailu, telefonu, RČ, IČ, čísla jednotky (včetně české diakritiky)
- Detekovat a slučovat duplicitní záznamy (stejná osoba importovaná z více zdrojů)

**Důležité pojmy:**
- **Jednotka** = byt nebo nebytový prostor (garáž, sklep, ateliér). Každá má unikátní číslo
- **Podíl SČD** = podíl na společných částech domu -- určuje váhu hlasu při hlasování
- **SJM** = společné jmění manželů -- manželé vlastní byt dohromady

**Odkud data pocházejí:**
- Původní import z Excel souboru (tabulka "SVJ Evidence Vlastníků")
- Ruční zadání přes formuláře v aplikaci
- Aktualizace z CSV exportu webu sousede.cz

---

### 2. Hlasování per rollam

**Co to je:** Hlasování, které probíhá písemně (korespondenčně), bez shromáždění. Vlastníci obdrží hlasovací lístky, vyplní své hlasy a odešlou zpět.

**Jak to funguje (krok za krokem):**

1. **Nastavení hlasování** -- Uživatel vytvoří hlasování, nahraje Word šablonu s body hlasování. Aplikace automaticky rozpozná body ("Bod 1:", "Bod 2:" apod.) a extrahuje název a data
2. **Generování lístků** -- Aplikace vytvoří hlasovací lístek pro každého aktivního vlastníka. Manželé se SJM dostanou společný lístek (jedno hlasování za oba). Lístek obsahuje čísla jednotek a počet hlasů
3. **Zpracování hlasů** -- Uživatel nahraje vyplněné lístky (Excel soubor nebo skenované PDF), nebo zadá hlasy ručně. Aplikace automaticky spáruje hlasy s lístky podle čísla jednotky
4. **Výsledky** -- Aplikace spočítá hlasy PRO / PROTI / ZDRŽELI SE pro každý bod. Zobrazí, zda bylo dosaženo kvórum (minimální účast potřebná pro platnost hlasování)
5. **Uzavření a export** -- Výsledky se exportují do Excelu

**Důležitá pravidla:**
- **Kvórum** = minimální počet hlasů, aby bylo hlasování platné (např. 50 % všech podílů). Nastavuje se pro každé hlasování zvlášť
- **SJM sdílení lístků** = Manželé, kteří vlastní byt ve společném jmění, dostanou jeden společný lístek. Jejich hlasy se sčítají
- Po vygenerování lístků se změny v evidenci (nové podíly, noví vlastníci) automaticky nepropisují -- hlasy na lístcích jsou "snapshot" stavu v době generování

---

### 3. Hromadné rozesílání daňových podkladů

**Co to je:** Služba pro hromadné rozeslání PDF dokumentů (typicky daňových podkladů) vlastníkům emailem.

**Jak to funguje (krok za krokem):**

1. **Nahrání PDF** -- Uživatel nahraje složku s PDF soubory. Každý soubor je pojmenován podle čísla jednotky (např. "14.pdf", "115A.pdf"). Aplikace automaticky rozpozná číslo jednotky z názvu souboru a pokusí se z obsahu PDF zjistit jméno vlastníka
2. **Přiřazení** -- Aplikace automaticky spáruje každý PDF s vlastníkem v evidenci (podle čísla jednotky + fuzzy porovnání jmen). Uživatel přehledně vidí navržená přiřazení a může je potvrdit, odmítnout nebo opravit. Nepotvrzená přiřazení se při rozesílce přeskočí
3. **Rozesílka** -- Uživatel nastaví předmět a text emailu, odešle testovací email (povinné), a pak spustí hromadnou rozesílku. Emaily se odesílají po dávkách (např. 10 emailů, pauza 5 sekund). Rozesílku lze pozastavit a obnovit
4. **Dokončeno** -- Přehled odeslaných a selhaných emailů, možnost opakovat odeslání pro selhané

**Důležitá pravidla:**
- Každý PDF se automaticky přiřazuje i spoluvlastníkům na stejné jednotce (např. manžel/ka)
- Před rozesílkou je povinný testovací email -- po změně předmětu nebo textu je třeba znovu otestovat
- Pokud server spadne uprostřed rozesílky, při dalším spuštění se stav automaticky nastaví na "pozastaveno" a uživatel může pokračovat

---

### 4. Synchronizace s externím CSV

**Co to je:** Porovnání evidence s daty z externího zdroje (web sousede.cz) -- detekce rozdílů v jménech, typech vlastnictví a podílech.

**Jak to funguje:**

1. **Nahrání CSV** -- Uživatel nahraje CSV export ze sousede.cz
2. **Automatické porovnání** -- Aplikace každý záznam z CSV spáruje s evidencí podle čísla jednotky a porovná:
   - Jména vlastníků (inteligentně -- prohozené pořadí, drobné překlepy apod.)
   - Typ vlastnictví (SJM vs běžné)
   - Podíl na společných částech
3. **Zobrazení výsledků** -- Každý záznam dostane status:
   - **Shoda** -- vše sedí
   - **Prohozené pořadí** -- jména sedí, ale v jiném pořadí
   - **Rozdíl** -- neshoda v datech
   - **Chybí v CSV** -- v evidenci existuje, v CSV ne
   - **Chybí v evidenci** -- v CSV existuje, v evidenci ne
4. **Řešení rozdílů** -- Uživatel může pro každý rozdíl: přijmout data z CSV, odmítnout, upravit ručně, nebo provést výměnu vlastníků

**Výměna vlastníků** = speciální akce, kdy se na jednotce nahrazují dosavadní vlastníci novými. Starý vlastník se neztrácí -- jeho vazba na jednotku se označí datem ukončení a původní data zůstanou v historii.

---

### 5. Evidence plateb -- NOVÉ

**Co to je:** Kompletní systém pro správu financí SVJ -- od měsíčních předpisů přes bankovní výpisy až po roční vyúčtování.

**Hlavní části:**

#### Předpisy plateb
Každá jednotka/prostor má měsíční předpis -- kolik má vlastník/nájemce platit. Předpisy se importují z Word souboru (evidenční listy ze systému DOMSYS). Každý předpis obsahuje položky rozčleněné do kategorií: provozní náklady, fond oprav, služby.

#### Variabilní symboly
Centrální evidence variabilních symbolů -- každý symbol je přiřazený k jedné jednotce nebo prostoru. Při platbě se podle variabilního symbolu automaticky pozná, kdo platí.

#### Počáteční zůstatky
Na začátku roku se nahrají z Excelu nedoplatky/přeplatky z minulého období. Tyto zůstatky se pak započítávají do celkového výpočtu dluhů.

#### Bankovní výpisy
Uživatel nahraje CSV výpis z Fio banky. Aplikace automaticky:

1. **Páruje platby na jednotky** -- nejdřív podle variabilního symbolu (přesná shoda), pak podle jména odesílatele a částky (inteligentní odhad), a nakonec dekódováním VS
2. **Navrhuje přiřazení** -- platby se statusem "navrženo" musí uživatel potvrdit
3. **Detekuje multi-unit platby** -- když vlastník zaplatí jednou platbou za více jednotek, aplikace to rozpozná a rozpočítá

**Zamykání výpisů:** Hotově zpracovaný výpis lze zamknout, aby se zabránilo nechtěným změnám.

#### Matice plateb
Přehledová tabulka (jednotky × měsíce) ukazuje, kdo zaplatil a kdo ne. Každé políčko je zeleně (zaplaceno), žlutě (částečně) nebo červeně (nezaplaceno).

#### Dlužníci
Automatická detekce jednotek, kde zaplaceno méně než předepsáno. Počet dlužníků se zobrazuje v postranním menu jako červený badge.

**Výpočet dluhu:** Předpis × počet měsíců s daty + počáteční zůstatek - zaplaceno = dluh.

#### Vyúčtování
Na konci roku aplikace automaticky vygeneruje roční vyúčtování pro každou jednotku:
- Roční předpis (měsíční × 12)
- Celkem zaplaceno
- Počáteční zůstatek
- **Výsledek:** kladný = nedoplatek, záporný = přeplatek

Vyúčtování obsahuje rozpad po položkách (fond oprav, služby, provozní) s poměrným rozúčtováním.

---

### 6. Správa prostorů a nájemců -- NOVÉ

**Co to je:** Evidence společných prostor SVJ (nebytové prostory, pronajímatelné jednotky) a jejich nájemců.

**Prostory:**
- Každý prostor má číslo, název, sekci, patro a výměru
- Tři stavy: **Pronajatý** (má nájemce), **Volný** (nemá nájemce), **Blokovaný** (kočárkárna, kotelna, ústředna -- nerentabilní)
- Import prostorů z Excelu -- aplikace automaticky rozpozná blokované prostory podle klíčových slov v názvu

**Nájemci:**
- Nájemce může být propojený s existujícím vlastníkem v domě (pak se kontakty přebírají z evidence vlastníků) nebo samostatná osoba
- Každý nájemce může mít přiřazený prostor se smlouvou (číslo smlouvy, datum, měsíční nájem, variabilní symbol)

**Propojení s platebním modulem:**
- Při přiřazení nájemce na prostor se automaticky vytvoří předpis a mapování variabilního symbolu
- Platby nájemců se párují stejným mechanismem jako platby vlastníků

---

### 7. Kontrola podílů

**Co to je:** Porovnání podílů na společných částech domu (SČD) v evidenci s údaji z externího souboru.

**Jak to funguje:**

1. Uživatel nahraje soubor (CSV, Excel) s podíly
2. Aplikace automaticky detekuje, které sloupce obsahují čísla jednotek a podíly
3. Pro každou jednotku porovná podíl v evidenci s podílem v souboru
4. Zobrazení neshod s možností aktualizovat hodnoty v evidenci

---

### 8. Správa SVJ

**Co to zahrnuje:**

- **Informace o SVJ** -- název, adresa, celkové podíly, typ budovy
- **Členové výboru** -- předseda, místopředseda, členové, kontrolní komise
- **Číselníky** -- seznamy možných hodnot (typy prostor, sekce domu, typy vlastnictví)
- **Emailové šablony** -- předpřipravené texty emailů s automatickými proměnnými (rok, jméno apod.)
- **Hromadné úpravy** -- změna typu vlastnictví nebo druhu prostoru pro více záznamů najednou
- **Export dat** -- export všech dat do Excelu nebo CSV (filtrovatelné)
- **Záloha a obnova** -- kompletní záloha dat (databáze + všechny soubory) do ZIP archivu, možnost obnovy ze zálohy

---

## Jak spolu věci souvisejí

```
                            ┌──────────────┐
                            │   Dashboard  │
                            │  (přehled)   │
                            └──────┬───────┘
                                   │
        ┌──────────────────────────┼──────────────────────────┐
        │              │           │           │              │
┌───────▼────────┐ ┌───▼───────┐ ┌▼──────────┐ ┌▼───────────┐ ┌▼──────────┐
│   Vlastníci    │ │  Jednotky │ │ Hlasování │ │  Prostory  │ │  Platby   │
│ (osoby/firmy)  │ │(byty/gar.)│ │(per rollam)│ │(neb.prost.)│ │(předpisy) │
└───────┬────────┘ └───┬───────┘ └───┬───────┘ └───┬────────┘ └───┬───────┘
        │              │             │              │              │
        └──── M:N ─────┘             │              │              │
        (vlastnický vztah            │         ┌────▼────┐         │
         s podíly a historií)        │         │ Nájemci │         │
                  │                  │         └─────────┘         │
        ┌─────────┼─────────┐       │                             │
        │         │         │       │          ┌──────────────────┘
┌───────▼──┐ ┌───▼─────┐   ├───────┘          │
│ Synchron.│ │ Kontrola│   │            ┌──────▼──────┐
│ s CSV    │ │ podílů  │   │            │  Bankovní   │
└──────────┘ └─────────┘   │            │  výpisy     │
                           │            └──────┬──────┘
                  ┌────────▼────────┐          │
                  │   Rozesílka     │   ┌──────▼──────┐
                  │ (daň. podklady) │   │ Vyúčtování  │
                  └─────────────────┘   │ + dlužníci  │
                                        └─────────────┘
```

**Základní princip:** Všechno se točí kolem **vlastníků** a **jednotek**. Vlastník může vlastnit více jednotek, jednu jednotku může vlastnit více vlastníků. Tento vztah určuje hlasy pro hlasování, příjemce pro rozesílku, a data pro synchronizaci.

**Nově:** Společné prostory mají vlastní nájemce (propojené nebo nezávislé na vlastnících) a integrují se do platebního systému -- mají své předpisy, variabilní symboly a párování plateb.

---

## Důležitá pravidla a omezení

### Automatické párování jmen

Aplikace dokáže "chytře" párovat jména -- například:
- "Nováková Jana" se spáruje s "Jana Nováková" (prohozené pořadí)
- "Ing. Jan Novák, Ph.D." se spáruje s "Novák Jan" (ignorují se tituly)
- "Nováková" se spáruje s "Novák" (český stemming příjmení)
- Drobné překlepy se tolerují (např. "Novák" vs "Nowák" při dostatečně vysoké shodě)

Všude v aplikaci, kde se páruje jméno (import, synchronizace, rozesílka, párování plateb), je nastaven minimální práh shody (typicky 70-90 %), pod který se párování nepovažuje za shodu.

### Automatické párování plateb

Bankovní platby se párují na jednotky ve třech krocích:
1. **Přesná shoda variabilního symbolu** -- nejspolehlivější metoda
2. **Jméno odesílatele + částka** -- pokud VS chybí, ale jméno sedí a částka odpovídá násobku předpisu
3. **Dekódování VS** -- pokus extrahovat číslo jednotky z formátu variabilního symbolu

Navržené (automaticky napárované) platby se do finančních přehledů počítají **až po potvrzení** uživatelem.

### Historie vlastnictví

Když se vlastník změní (prodej, dědictví), starý záznam se **nesmaže**. Místo toho se nastaví datum ukončení ("platné do") a vytvoří se nový záznam s datem zahájení ("platné od"). Díky tomu je možné zpětně dohledat, kdo vlastnil jednotku v kterémkoli roce.

### SJM (společné jmění manželů)

Manželé, kteří vlastní byt ve společném jmění, jsou v systému evidováni jako dva samostatní vlastníci s vazbou na stejnou jednotku a typem vlastnictví "SJM". Aplikace je na mnoha místech zpracovává společně -- např. při generování hlasovacích lístků dostanou jeden společný lístek.

### Bezpečnost dat

- Zálohy se vytvářejí automaticky (do ZIP souboru), uchovává se max 10 posledních
- Před obnovou ze zálohy se automaticky vytvoří "bezpečnostní záloha" aktuálního stavu
- Pokud obnova ze zálohy selže, automaticky se provede návrat do původního stavu
- Soubory se ukládají na disk vedle databáze, cesty jsou kontrolovány proti neautorizovanému přístupu
- Bankovní výpisy lze zamknout, aby se zabránilo nechtěným změnám párování

### Offline fungování

Aplikace funguje kompletně offline (bez internetu) -- s jedinou výjimkou: odesílání emailů vyžaduje přístup k emailovému serveru. Všechna data jsou uložena lokálně na počítači v jedinom souboru databáze (`svj.db`).

---

## Typické scénáře použití

### Scénář 1: Příprava hlasování per rollam

1. Předseda SVJ vytvoří nové hlasování, nahraje Word šablonu s body
2. Aplikace rozpozná body hlasování a vytvoří lístky pro všechny vlastníky
3. Lístky se vytisknou a rozešle vlastníkům (nebo vygeneruje PDF)
4. Po shromáždění vyplněných lístků se hlasy zapisují do systému (ručně nebo z Excelu)
5. Aplikace automaticky vyhodnotí výsledky a zkontroluje kvórum

### Scénář 2: Roční rozeslání daňových podkladů

1. Účetní připraví PDF soubory (jeden pro každý byt), pojmenuje je číslem jednotky
2. Nahrání všech PDF najednou do aplikace
3. Aplikace automaticky rozpozná, komu který PDF patří
4. Rychlá kontrola a potvrzení přiřazení
5. Odeslání testovacího emailu (povinné)
6. Spuštění hromadné rozesílky -- všichni vlastníci obdrží svůj PDF emailem

### Scénář 3: Kontrola aktuálnosti evidence

1. Předseda stáhne CSV export z webu sousede.cz (katastrální data)
2. Nahrání CSV do aplikace
3. Aplikace porovná každý záznam s evidencí a zvýrazní rozdíly
4. Předseda projde rozdíly a rozhodne, které přijmout (změna vlastníka, oprava údajů)

### Scénář 4: Změna vlastníka (prodej bytu)

1. Při synchronizaci s CSV se detekuje, že na jednotce je jiný vlastník než v evidenci
2. Uživatel zvolí "Výměna vlastníků"
3. Aplikace automaticky:
   - Označí původní vlastnictví datem ukončení (nesmaže!)
   - Vytvoří nové vlastnictví pro nového vlastníka
   - Přepočítá hlasy (pokud je více nových vlastníků, rozdělí rovnoměrně)
   - Pokud starý vlastník nemá žádnou další jednotku, označí ho jako neaktivního

### Scénář 5: Měsíční zpracování plateb -- NOVÉ

1. Pokladní stáhne CSV výpis z Fio banky za uplynulý měsíc
2. Nahraje výpis do aplikace
3. Aplikace automaticky napáruje většinu plateb na jednotky (podle variabilních symbolů)
4. U zbylých plateb navrhne přiřazení podle jména odesílatele a částky
5. Pokladní zkontroluje návrhy, potvrdí správné, opraví chybné
6. V matici plateb je přehledně vidět, kdo zaplatil a kdo dluží
7. Na konci roku se vygeneruje vyúčtování s nedoplatky/přeplatky

### Scénář 6: Evidence pronájmu společného prostoru -- NOVÉ

1. Předseda nahraje Excel se seznamem prostorů (kočárkárna, ateliéry, sklady)
2. Aplikace automaticky rozpozná utility prostory (kočárkárna → blokovaná)
3. U pronajímaných prostorů se vytvoří nájemce, smlouva a variabilní symbol
4. Platby nájemců se následně párují automaticky stejně jako platby vlastníků

---

## Glosář

| Pojem | Vysvětlení |
|-------|------------|
| **SVJ** | Společenství vlastníků jednotek -- právnická osoba sdružující vlastníky bytů v jednom domě |
| **Jednotka** | Byt nebo nebytový prostor (garáž, sklep, ateliér) v domě |
| **Prostor** | Společný/pronajímatelný prostor (kočárkárna, ateliér, sklad) -- na rozdíl od jednotky není v osobním vlastnictví |
| **Podíl SČD** | Podíl na společných částech domu -- určuje váhu hlasu vlastníka |
| **SJM** | Společné jmění manželů -- manželé vlastní byt dohromady jako jeden celek |
| **Per rollam** | Způsob hlasování bez shromáždění (korespondenčně, písemně) |
| **Kvórum** | Minimální počet hlasů (podílů) potřebný k platnosti hlasování |
| **Variabilní symbol** | Číselný kód přiřazený jednotce/prostoru, slouží k identifikaci platby |
| **Předpis** | Měsíční částka, kterou má vlastník/nájemce platit (fond oprav + služby + provozní) |
| **Vyúčtování** | Roční zúčtování -- porovnání zaplacených záloh s celkovým předpisem |
| **Fuzzy matching** | Inteligentní párování jmen, které toleruje drobné rozdíly (překlepy, pořadí, tituly) |
| **Dashboard** | Úvodní stránka s přehledem všech modulů a posledních aktivit |
| **CSV** | Textový soubor s daty oddělenými čárkami/středníky (export z webu sousede.cz nebo z banky) |
| **DOCX** | Dokument MS Word (šablona pro hlasovací lístky, evidenční listy předpisů) |
| **Batch** | Dávka -- emaily se neodesílají všechny najednou, ale po dávkách (např. 10) s pauzou mezi nimi |

---

## Omezení aplikace

1. **Pouze pro jedno SVJ** -- aplikace není multi-tenant, spravuje data jednoho SVJ
2. **Jeden uživatel** -- zatím není implementovaný systém přihlašování a rolí (plánováno do budoucna)
3. **Lokální provoz** -- běží na jednom počítači, není určena pro provoz na serveru s více uživateli současně
4. **Email vyžaduje internet** -- všechno ostatní funguje offline
5. **Hlasy jsou snapshot** -- po vygenerování lístků se změny podílů/vlastníků nepropisují automaticky
6. **LibreOffice pro PDF** -- generování PDF lístků vyžaduje nainstalovaný LibreOffice
7. **Max 5000 souborů** při jednom uploadu (typicky dostatečné i pro velké SVJ)
8. **Pouze Fio banka** -- import bankovních výpisů podporuje formát Fio CSV (jiné banky vyžadují úpravu)
9. **Předpisy z DOMSYS** -- import předpisů parsuje specifický formát evidenčních listů ze systému DOMSYS
