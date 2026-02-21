# Popis datových souborů SVJ pro import do aplikace

## 1. Import vlastníků z Excelu

### Soubor: SVJ_Evidence_Vlastniku_CLEAN.xlsx

### Původ a příprava
Soubor byl vytvořen sloučením dvou zdrojových Excelů SVJ:
- **Evidence_vlastni_ku__1_5_2025.xlsx** – hlavní evidence vlastníků (katastr červen 2024)
- **KontaktyVlastnici.xlsx** – starší soubor s kontakty (katastr 2017), ze kterého byly převzaty emaily do samostatného sloupce

Původní soubory měly problematickou „groupovanou" strukturu – údaje o jednotce byly na jednom řádku a vlastníci na navazujících řádcích bez čísla jednotky. V novém souboru je toto vyřešeno: **každý řádek obsahuje kompletní záznam (údaje o jednotce + údaje o vlastníkovi)**.

---

### Struktura souboru

**Sheet:** `Vlastnici_SVJ`
**Hlavička:** řádek 1
**Data:** od řádku 2
**Celkem:** 771 záznamů osob / firem

| # | Sloupec | Popis | Typ dat | Příklad |
|---|---------|-------|---------|---------|
| A | Číslo jednotky (KN) | Unikátní identifikátor jednotky dle katastru nemovitostí | text | `1098/1` |
| B | Číslo prostoru (stavební) | Stavební označení prostoru | text | `A 111` |
| C | Podíl na SČD | Spoluvlastnický podíl na společných částech domu (v desetitisícinách) | číslo | `12212` |
| D | Podlahová plocha (m²) | Podlahová plocha jednotky | číslo | `185.56` |
| E | Počet místností | Dispoziční řešení | text | `3+1` |
| F | Druh prostoru | Typ jednotky | text | `byt` nebo `nebytový prostor` |
| G | Sekce domu | Sekce / vchod | text | `A`, `B`, `C` |
| H | Číslo orientační | Orientační číslo domu | číslo | `22` |
| I | Adresa jednotky | Ulice, kde se jednotka nachází | text | `Štěpařská` |
| J | LV číslo | Číslo listu vlastnictví | číslo | `3504` |
| K | Typ vlastnictví | Typ spoluvlastnictví | text | `ANO` (SJM), `VL`, `SJVL`, prázdné |
| **L** | **Jméno** | Křestní jméno vlastníka, nebo název firmy | text | `Michael` |
| **M** | **Příjmení / název** | Příjmení fyzické osoby nebo název právnické osoby | text | `Gavrilovič` |
| N | Titul | Akademický titul | text | `Ing.`, `Mgr.` |
| **O** | **Rodné číslo / IČ** | Rodné číslo (formát XXXXXX/XXXX) nebo IČ firmy | text | `711128/9911` |
| P | Trvalá adresa – ulice | Ulice trvalého bydliště / sídla firmy | text | `Štěpařská 1098/22` |
| Q | Trvalá adresa – část obce | Část obce | text | `Hlubočepy` |
| R | Trvalá adresa – město | Město / obec | text | `Praha 52` |
| S | Trvalá adresa – PSČ | Poštovní směrovací číslo | text | `152 00` |
| T | Trvalá adresa – stát | Stát (vyplněno jen u cizinců) | text | `SR` |
| U | Koresp. adresa – ulice | Korespondenční adresa – ulice | text | `Štěpařská 1098/22` |
| V | Koresp. adresa – část obce | Korespondenční adresa – část obce | text | `Hlubočepy` |
| W | Koresp. adresa – město | Korespondenční adresa – město | text | `Praha 52` |
| X | Koresp. adresa – PSČ | Korespondenční adresa – PSČ | text | `152 00` |
| Y | Koresp. adresa – stát | Korespondenční adresa – stát | text | |
| **Z** | **Telefon GSM** | Mobilní telefon (formátován +420 XXX XXX XXX kde bylo možné) | text | `+420 731 609 594` |
| AA | Telefon pevný | Pevná linka | text | |
| **AB** | **Email (Evidence 2024)** | Email z novější evidence (červen 2024) | text | `mgavrilovic@me.com` |
| **AC** | **Email (Kontakty)** | Email ze staršího souboru kontaktů (2017) | text | `mgavrilovic@seznam.cz` |
| AD | Vlastník od | Datum nabytí vlastnictví (jen u některých) | text | |
| AE | Poznámka | Poznámky z kontaktního listu | text | `Nový kontakt na vlastníka` |

---

### Klíčové vlastnosti dat

**Vztah jednotka ↔ vlastník:**
- Jedna jednotka může mít 1–5 vlastníků (SJM manželé, spoluvlastníci)
- 260 jednotek má 1 vlastníka, 242 má 2, 6 jednotek má 3–5 vlastníků
- Celkem ~513 unikátních jednotek a 771 záznamů osob
- Sloupec A (Číslo jednotky) se **opakuje** pro všechny vlastníky téže jednotky

**Typ vlastnictví (sloupec K):**
- `ANO` = společné jmění manželů (SJM)
- `VL` = výlučné vlastnictví
- `SJVL` = spoluvlastnictví (více osob, ne manželé)
- prázdné = nespecifikováno

**Emaily – dva sloupce:**
- **AB – Email (Evidence 2024)** = novější, pravděpodobně aktuálnější
- **AC – Email (Kontakty)** = starší zdroj
- Žluté podbarvení = emaily se liší mezi zdroji (78 případů) → nutná ruční verifikace
- Zelené podbarvení = email existuje pouze v Kontaktech, v Evidence chybí (11 případů)
- 337 emailů je shodných v obou zdrojích
- 102 osob nemá žádný email

**Naplněnost kontaktů:**
- Jméno + příjmení: 771 záznamů (100 %)
- Telefon GSM: ~647 (84 %)
- Email (alespoň jeden): ~669 (87 %)
- Rodné číslo / IČ: ~547 (71 %)
- Trvalá adresa: ~724 (94 %)
- Korespondenční adresa: ~718 (93 %)

---

### Postup importu v aplikaci

1. Otevřít `/vlastnici/import`
2. Nahrát `.xlsx` soubor → systém zobrazí náhled s rozpoznanými daty
3. V náhledu jsou vlastníci řazeni podle příjmení, prázdné sekce na konci
4. Po potvrzení se data uloží do databáze (Owner, Unit, OwnerUnit)
5. Import nahradí všechna stávající data (smazání → nový import)

### Mapování sloupců Excel → databáze

| Excel sloupec | Model | Pole | Poznámka |
|---------------|-------|------|----------|
| A | Unit | unit_number | Zkráceno na číslo za lomítkem (INTEGER) |
| B | Unit | building_number | |
| C | Unit | podil_scd | INTEGER (desetitisíciny) |
| D | Unit | floor_area | FLOAT |
| E | Unit | room_count | TEXT |
| F | Unit | space_type | |
| G | Unit | section | |
| H | Unit | orientation_number | INTEGER |
| I | Unit | address | |
| J | Unit | lv_number | INTEGER |
| K | OwnerUnit | ownership_type | |
| L | Owner | first_name | |
| M | Owner | last_name | |
| N | Owner | title | |
| O | Owner | birth_number / company_id | Rozlišení dle formátu |
| P–T | Owner | perm_street, perm_city_part, perm_city, perm_zip, perm_country | Trvalá adresa |
| U–Y | Owner | corr_street, corr_city_part, corr_city, corr_zip, corr_country | Korespondenční adresa |
| Z | Owner | phone | |
| AA | Owner | phone_landline | |
| AB | Owner | email | Primární email |
| AC | Owner | email_secondary | Sekundární email |
| AD | Owner | owner_since | |
| AE | Owner | note | |

---

### Doporučení pro přípravu dat

1. **Primární klíč pro jednotku:** sloupec A (`Číslo jednotky KN`) – formát `1098/XXX`, aplikace použije číslo za lomítkem jako INTEGER
2. **Identifikace osoby:** kombinace sloupců A + L + M (jednotka + jméno + příjmení), protože rodné číslo není u všech
3. **Email pro komunikaci:** prioritně AB (Evidence 2024), fallback na AC (Kontakty)
4. **Rozlišení fyzická vs. právnická osoba:** pokud sloupec O obsahuje IČ (8místné číslo bez lomítka) → firma; pokud obsahuje rodné číslo (formát XXXXXX/XXXX) → fyzická osoba
5. **Prázdné hodnoty:** prázdné buňky = údaj není k dispozici, neimportovat jako text "None"
6. **Kódování:** UTF-8, český text s diakritikou

---

## 2. Kontrola vlastníků z CSV

### Účel
Porovnání aktuální evidence vlastníků v aplikaci s daty exportovanými z externího systému (např. sousede.cz) ve formátu CSV.

### Formát CSV

- **Oddělovač:** středník (`;`) nebo čárka (`,`) — automatická detekce
- **Kódování:** UTF-8 nebo Windows-1250 — automatická detekce
- **Očekávané sloupce:** závisí na exportu z externího systému, typicky obsahuje:
  - Číslo jednotky
  - Jméno vlastníka (může být spojené: „Příjmení Jméno")
  - Typ vlastnictví
  - Druh prostoru
  - Spoluvlastnický podíl

### Postup kontroly v aplikaci

1. Otevřít `/synchronizace`
2. Nahrát CSV soubor → systém porovná s daty v databázi
3. Výsledky se zobrazí v porovnávací tabulce s filtračními bublinami:
   - **Shoda** — data jsou identická
   - **Částečná shoda** — vlastník nalezen, ale liší se některá pole
   - **Přeházená jména** — jména ve stejné jednotce, ale v jiném pořadí
   - **Rozdílní vlastníci** — vlastník nenalezen / jiný
   - **Rozdílné podíly** — liší se pouze podíl SČD
   - **Chybí** — záznam existuje jen v evidenci nebo jen v CSV
4. Každá bublina zobrazuje součty podílů (evidence vs. CSV) a rozdíl
5. Vybrané rozdíly lze selektivně aktualizovat do databáze
6. Kontakty (email, telefon) lze přenést z CSV do databáze

### Katastrální podíl
Celkový podíl na společných částech domu dle katastru: **4 103 391** (v desetitisícinách). Používá se jako referenční hodnota pro výpočet procent v porovnávacích bublinách.

### Historie kontrol
Každá kontrola se uloží do historie. Z historie lze kontroly jednotlivě mazat (smaže záznamy i nahraný CSV soubor).
