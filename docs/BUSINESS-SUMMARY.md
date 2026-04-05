# SVJ Aplikace — Shrnutí pro výbor

> Netechnický popis fungování aplikace SVJ Správa.
> Dokument je určen členům výboru, kontrolní komisi a správcům.
> Poslední aktualizace: 2026-04-05

---

## Co aplikace dělá

Aplikace SVJ Správa slouží k evidenci vlastníků, správě hlasování per rollam, hromadnému rozesílání dokumentů, evidenci plateb, správě prostor a nájemců, a kontrole dat. Běží lokálně na počítači výboru (není potřeba internet, kromě rozesílání emailů).

---

## 1. Evidence vlastníků a jednotek

### Co se eviduje
- **Vlastníci:** jméno, titul, rodné číslo/IČ, trvalá adresa, korespondenční adresa, telefon(y), email(y), typ (fyzická/právnická osoba)
- **Jednotky:** číslo jednotky, číslo budovy, podíl na společných částech domu (SČD), podlahová plocha, sekce domu, typ prostoru, LV číslo
- **Vztah vlastník-jednotka:** typ vlastnictví (SJM, VL...), podíl, platnost od/do

### Typ vlastnictví
- **SJM** (společné jmění manželů) — manželé vlastní jednotku společně, v hlasování mají jeden společný lístek
- **VL** — výlučné vlastnictví
- Ostatní typy se evidují dle prohlášení vlastníků

### Ruční vytvoření vlastníka
Kromě importu z Excelu lze vlastníka vytvořit ručně přímo v aplikaci:
- Zadání jména, příjmení, titulu, typu, emailu, telefonu, RČ/IČ
- **Kontrola emailu** — aplikace ověří, že email má platný formát (např. `jmeno@domena.cz`)
- **Detekce duplicit** — při vytváření se kontroluje, zda už vlastník se stejným jménem, rodným číslem nebo emailem neexistuje. Pokud ano, zobrazí se upozornění s odkazem na existujícího vlastníka. Vytvoření je možné i přesto potvrdit (není blokující)

### Ruční vytvoření a úprava jednotky
- Číslo jednotky musí být celé číslo v rozsahu 1-99999, nesmí se opakovat
- Číslo budovy (volitelné): rozsah 1-99999
- Při zadání neplatné plochy nebo podílu SČD se hodnota ignoruje a zobrazí se upozornění (žlutý banner)

### Import vlastníků z Excelu
Aplikace umí načíst seznam vlastníků z Excelu (formát „Evidence vlastníků SVJ"):
1. **Nahrání souboru** — Excel s listem „Vlastnici_SVJ"
2. **Náhled** — aplikace ukáže co bude importováno (počet vlastníků, jednotek, případné chyby)
3. **Potvrzení** — data se uloží do evidence

Vlastník je identifikován podle rodného čísla/IČ. Pokud má více řádků v Excelu (více jednotek), vytvoří se jeden záznam vlastníka s vazbami na všechny jednotky.

### Import kontaktů
Doplnění kontaktních údajů (telefon, email, adresa) z jiného Excelu:
1. Nahrání souboru
2. Aplikace automaticky spáruje záznamy podle jména a RČ/IČ
3. Ukáže náhled změn — co se doplní, co se přepíše
4. Výbor vybere které změny provést

Inteligentní zpracování: pokud vlastník už má email, ale v Excelu je jiný, nový se uloží jako sekundární email (nepřepíše původní).

### Export vlastníků a jednotek
Data z evidence je možné kdykoliv vyexportovat do Excelu (XLSX) nebo CSV:
- **Export vlastníků** — ze stránky „Vlastníci", tlačítko Export
- **Export jednotek** — ze stránky „Jednotky", tlačítko Export
- Exportovaná data odpovídají **aktuálně zobrazenému filtru** — např. pokud jsou zobrazeni jen vlastníci s emailem, vyexportují se jen ti
- Název souboru automaticky obsahuje popis filtru (např. `vlastnici_fyzicke_20260309.xlsx`)

---

## 2. Hlasování per rollam

### Jak to funguje

Hlasování probíhá v 5 krocích (průvodce v aplikaci):

#### Krok 1 — Nastavení
- Název a popis hlasování
- Datum zahájení a ukončení
- **Kvórum** — kolik procent hlasů je potřeba pro platnost (např. 50 %)
- **Režim SJM** — zda manželé dostávají jeden společný lístek (doporučeno) nebo každý svůj
- Možnost nahrát Word šablonu — aplikace z ní automaticky vytáhne body hlasování

#### Krok 2 — Generování lístků
- Pro každého aktivního vlastníka se vytvoří hlasovací lístek
- U SJM: manželé dostávají jeden lístek s hlasy obou (jejich podíly se sečtou)
- Lístek obsahuje: jméno vlastníka, čísla jednotek, počet hlasů, body hlasování

#### Krok 3 — Zpracování hlasů
Tři způsoby zadávání hlasů:
1. **Ručně** — kliknutím pro každý lístek (PRO / PROTI / ZDRŽUJI SE)
2. **Hromadně** — stejné hlasy pro více lístků najednou
3. **Import z Excelu** — nahrání tabulky s výsledky hlasování

##### Import hlasů z Excelu
- Nahrání Excel souboru s výsledky
- Namapování sloupců: který sloupec = jméno, který = jednotka, které = hlasy
- Konfigurovatelné hodnoty: co znamená PRO (např. "1", "ANO", "X"), co PROTI
- Náhled: které řádky se spárovaly, které ne, nerozpoznané hodnoty
- Potvrzení importu

#### Krok 4 — Výsledky
- Celkový počet hlasů, kolik hlasovalo, procento
- **Kvórum:** zda bylo dosaženo potřebného procenta
- Pro každý bod: kolik PRO, PROTI, ZDRŽUJI SE (v hlasech i procentech)

#### Krok 5 — Uzavření
- Hlasování se uzavře nebo zruší
- Uzavřené hlasování již nelze měnit

### Důležité koncepty

**Počet hlasů = podíl na SČD.** Každý vlastník hlasuje vahou odpovídající jeho podílu na společných částech domu. Kdo má větší byt, má více hlasů.

**Kvórum.** Hlasování je platné, pokud se zúčastnila dostatečná část vlastníků (měřeno podíly, ne počtem osob). Výchozí je 50 %.

**Snapshot varování.** Pokud se od generování lístků změní vlastník nebo podíly (např. prodej bytu), aplikace na to upozorní.

---

## 3. Hromadné rozesílání (daňové dokumenty aj.)

### Jak to funguje

Rozesílání probíhá ve 4 krocích:

#### Krok 1 — Nahrání PDF
- Nahrání složky s PDF dokumenty (typicky vyúčtování služeb)
- Název souboru = číslo jednotky (např. „115.pdf", „115A.pdf")
- Aplikace automaticky rozpozná jméno vlastníka z textu PDF

#### Krok 2 — Přiřazení
- Aplikace automaticky přiřadí dokumenty k vlastníkům podle jména a čísla jednotky
- Výbor zkontroluje a potvrdí přiřazení
- Nepřiřazené dokumenty je možné přiřadit ručně
- Podpora spoluvlastníků: jeden dokument se pošle více vlastníkům stejné jednotky

#### Krok 3 — Rozesílka
- Nastavení šablony emailu (předmět, tělo)
- Testovací email — ověření před odesláním
- **Dávkové odesílání:** emaily se posílají po dávkách (nastavitelná velikost a interval)
- Možnost pozastavení, pokračování a zrušení rozesílky
- Sledování průběhu v reálném čase

#### Krok 4 — Dokončeno
- Přehled odeslaných a neúspěšných emailů
- Možnost opakovaného odeslání neúspěšných

### Bezpečnost rozesílání
- Při restartu serveru se rozpracovaná rozesílka automaticky pozastaví (neztratí se stav)
- Každý email se loguje (datum, příjemce, stav, případná chyba)

---

## 4. Evidence plateb

### Co modul řeší

Evidence plateb slouží ke sledování předpisů (kolik mají vlastníci platit), přijatých plateb z bankovních výpisů a vzájemnému párování — kdo zaplatil, kolik a za které období. Výstupem je přehled plateb, identifikace dlužníků a roční vyúčtování.

### Jak to funguje

#### Krok 1 — Import předpisů
- Nahrání dokumentu s měsíčními předpisy (formát DOMSYS — Word dokument)
- Aplikace automaticky rozpozná: číslo jednotky, variabilní symbol, jméno vlastníka, jednotlivé položky předpisu
- **Položky se automaticky kategorizují** do 3 skupin:
  - **Provozní náklady** — správa domu, pojištění, úklid, elektřina společných prostor, revize...
  - **Fond oprav** — fond oprav, fond údržby, splácení úvěru...
  - **Služby** — voda, teplo, TUV, vytápění, odpady...

#### Krok 2 — Variabilní symboly
- Každá jednotka (a prostor) má přiřazený variabilní symbol (VS) — číslo, které vlastník/nájemce uvádí při platbě
- VS se importují automaticky z předpisů nebo se zadávají ručně
- Jeden vlastník může mít více VS (např. při změně vlastníka, SJM)

#### Krok 3 — Import bankovních výpisů
- Nahrání CSV souboru z Fio banky
- Aplikace automaticky rozpozná příjmy a výdaje
- Kontrola duplicit — stejný výpis se nenaimportuje dvakrát

#### Krok 4 — Párování plateb
Aplikace automaticky přiřadí platby k předpisům ve 3 fázích:

1. **Přesná shoda VS** — pokud variabilní symbol na platbě přesně odpovídá VS jednotky nebo prostoru, platba se přiřadí automaticky (nejvyšší jistota)
2. **Shoda jména a částky** — pokud se jméno plátce shoduje s vlastníkem/nájemcem a částka odpovídá předpisu (střední jistota, vyžaduje potvrzení)
3. **Dekódování VS** — pokud VS obsahuje číslo jednotky (např. VS 1098115 = jednotka 115), aplikace to rozpozná a navrhne přiřazení (nejnižší jistota, vyžaduje potvrzení)

Nepřiřazené platby lze přiřadit ručně — aplikace nabídne dropdown s navrhovanými jednotkami a prostory.

#### Krok 5 — Přehled
- **Platební matice** — tabulka zobrazující všechny jednotky a měsíce:
  - Zelená = zaplaceno v plné výši
  - Červená = nezaplaceno nebo nedoplatek
  - Žlutá = zaplaceno částečně
- **Seznam dlužníků** — jednotky, které mají dluh
- **Detail jednotky** — všechny platby a předpisy za období

#### Krok 6 — Vyúčtování
- Roční vyúčtování pro každou jednotku
- **Vzorec:** `výsledek = (měsíční předpis x 12) + počáteční zůstatek - celkem zaplaceno`
  - Kladný výsledek = vlastník dluží (nedoplatek)
  - Záporný výsledek = přeplatek
- Detailní rozpis po kategoriích (provozní, fond oprav, služby)

### Nesrovnalosti v platbách (NOVINKA)

Po importu bankovního výpisu a napárování plateb aplikace automaticky detekuje nesrovnalosti:

- **Špatný variabilní symbol** — vlastník použil jiný VS, než odpovídá jeho předpisu
- **Nesprávná výše platby** — zaplacená částka neodpovídá měsíčnímu předpisu (tolerují se přesné násobky 1-12 měsíců)
- **Sloučená platba** — jedna platba pokrývá více jednotek/prostorů

**Jak upozornění funguje:**
1. Na stránce bankovního výpisu se zobrazí tlačítko „Nesrovnalosti" s počtem nalezených problémů
2. Na stránce nesrovnalostí je přehled všech problémů s náhledem emailu, který bude odeslán
3. Před odesláním je povinný **testovací email** — ověří se správnost obsahu
4. Poté se upozornění rozešlou **dávkově** (stejný systém jako u rozesílání dokumentů)
5. U každé platby se zaznamená datum odeslání upozornění (aby se neposílalo dvakrát)

Při SJM (manželé na jedné jednotce) se upozornění automaticky pošle tomu z manželů, kdo platbu odeslal (rozpozná se podle jména odesílatele na výpisu).

### Důležité koncepty

**Variabilní symbol (VS).** Unikátní číslo přiřazené jednotce nebo prostoru. Vlastník/nájemce ho uvádí při platbě, aby aplikace poznala, za koho platba je.

**Předpis.** Měsíční částka, kterou má vlastník platit. Skládá se z položek (správa, fond oprav, voda, teplo...).

**Alokace.** Jedna platba může pokrýt více měsíců (např. čtvrtletní platba) a naopak jeden měsíc může být pokryt více platbami (např. částečné platby).

**Zůstatek.** Průběžný stav účtu jednotky — kladný = dluh, záporný = přeplatek.

---

## 5. Prostory a nájemci (NOVINKA)

### Co se eviduje

- **Prostory:** číslo prostoru, název (sklep, garáž...), sekce, podlaží, plocha, stav (pronajato/volné/blokované)
- **Nájemci:** jméno, kontakty, typ (fyzická/právnická osoba). Nájemce může být propojený s existujícím vlastníkem v evidenci
- **Nájemní vztahy:** smlouva (číslo, datum), měsíční nájem, variabilní symbol

### Stavy prostoru
- **Pronajato** — prostor má aktivního nájemce
- **Volné** — prostor je k dispozici
- **Blokované** — prostor nelze pronajmout (kotelna, chodba, společné prostory...). Aplikace automaticky rozpozná tyto prostory podle názvu

### Import prostorů z Excelu
1. Nahrání Excel souboru
2. Namapování sloupců (číslo prostoru, název, nájemce, nájem, VS...)
3. Náhled — aplikace ukáže co bude vytvořeno a pokusí se spárovat nájemce s existujícími vlastníky
4. Potvrzení importu

Při importu se automaticky vytvoří i variabilní symboly a předpisy pro prostory s nájemným.

### Propojení s platbami
Prostory s nájemným se zahrnují do platebního modulu:
- VS prostoru se používá pro párování plateb (stejně jako u jednotek)
- Nesrovnalosti v platbách nájemců se detekují a upozornění se posílají nájemcům

---

## 6. Synchronizace s externími zdroji

### Porovnání vlastníků (CSV ze sousede.cz)
Porovná evidenci s exportem z portálu sousede.cz nebo jiným CSV:
1. **Nahrání CSV** — automatická detekce formátu a kódování
2. **Porovnání** — aplikace najde:
   - **Shody** — data se shodují
   - **Prohozená jména** — jen pořadí jméno/příjmení je jiné
   - **Rozdíly** — vlastník se liší
   - **Chybějící** — jednotka je jen v jednom zdroji
3. **Akce:**
   - Přijmout / Odmítnout rozdíl
   - Ručně opravit jméno
   - **Výměna vlastníků** — nahradit vlastníky na jednotce podle CSV

#### Výměna vlastníků
Když se na jednotce změní vlastník (prodej bytu):
- Aplikace navrhne nové vlastníky z CSV
- Pokud vlastník už existuje v evidenci, použije se existující záznam
- Pokud je nový, vytvoří se nový vlastník
- Starý vlastník se „odebere" z jednotky (zůstane v historii)
- Hlasy se přepočítají

### Kontrola podílů (SČD)
Porovná podíly na SČD v evidenci se souborem (CSV/Excel):
1. **Nahrání souboru** — automatická nebo ruční volba sloupců
2. **Porovnání** — shody, rozdíly, chybějící
3. **Aktualizace** — možnost přepsat podíly v evidenci hodnotami ze souboru
4. **Export výsledků** — výsledky porovnání lze vyexportovat do Excelu (včetně zvýraznění rozdílů)

---

## 7. Administrace

### Informace o SVJ
- Název SVJ, typ budovy, celkový počet podílů (SČD)
- Adresy domů
- **Celkový počet podílů** je klíčový pro výpočet kvóra a procentuálních podílů

### Nastavení odesílání emailů (NOVINKA)
- **Sdílená konfigurace** pro všechny moduly odesílání (rozesílání dokumentů i upozornění na nesrovnalosti):
  - Velikost dávky (kolik emailů najednou)
  - Interval mezi dávkami (kolik sekund pauza)
  - Potvrzení po každé dávce (ano/ne)
  - Testovací emailová adresa

### Členové výboru
- Jméno, funkce, email, telefon
- Rozděleno na skupiny: výbor, kontrolní komise

### Číselníky
- Správa typů prostor, sekcí, počtů místností, typů vlastnictví
- Automaticky se naplní z existujících dat

### Emailové šablony
- Přednastavené šablony pro rozesílání a upozornění na nesrovnalosti
- Předmět + tělo emailu, s proměnnými (jméno vlastníka, měsíc, částka...)

### Nastavení SMTP (email server)
- Konfigurace serveru pro odesílání emailů (adresa serveru, port, přihlášení)
- **Podpora SSL (port 465)** — pro emailové servery vyžadující přímé šifrování
- **Test připojení** — tlačítko „Otestovat SMTP" ověří, že se aplikace dokáže připojit k emailovému serveru

### Zálohy
- **Záloha:** vytvoří ZIP se vším (databáze + nahrané soubory)
- **Obnova:** ze ZIP nebo rozbalené složky
- Před každou obnovou se automaticky vytvoří bezpečnostní záloha
- Historie obnov se ukládá do souboru (přežije i obnovu databáze)

### Smazání dat
- Selektivní mazání dat po kategoriích (vlastníci, hlasování, rozesílání, platby, zálohy...)
- Respektuje závislosti (například smazání vlastníků smaže i jejich lístky)

---

## 8. Exporty

- **Excel a CSV export** ze seznamu vlastníků a jednotek
- Export z kontroly podílů do Excelu (s barevným zvýrazněním rozdílů)
- Export historie odeslaných emailů
- Export přiřazení a rozesílky dokumentů
- Formát XLSX s formátováním (tučné hlavičky, automatická šířka sloupců)
- Export vždy reflektuje aktuálně zobrazený filtr — exportuje se to, co je vidět na obrazovce

---

## 9. Ochrana dat a bezpečnost

### Potvrzování destruktivních akcí
Všechny akce, které mažou nebo přepisují data (smazání vlastníka, zrušení hlasování, smazání zálohy apod.), vyžadují potvrzení ve speciálním dialogovém okně. Nelze je provést omylem jedním kliknutím.

### Upozornění na neuložené změny
Pokud ve formuláři provedete změny a pokusíte se odejít ze stránky bez uložení, prohlížeč vás upozorní a zeptá se, zda chcete stránku opravdu opustit.

### Validace vstupů
Aplikace kontroluje správnost zadávaných údajů:
- Email musí mít platný formát
- Číslo jednotky musí být v rozsahu 1-99999
- Číslo budovy musí být v rozsahu 1-99999
- Neplatné číselné hodnoty (plocha, podíl) se nepřijmou a zobrazí se upozornění

### Bezpečnostní hlavičky
Aplikace automaticky přidává bezpečnostní hlavičky ke každé odpovědi — ochrana proti vložení stránky do rámce cizího webu a další standardní opatření.

---

## 10. Úvodní obrazovka (dashboard)

### Přehled
- 6 statistických karet: vlastníci, jednotky, hlasování, rozesílání, platby, prostory
- Tabulka poslední aktivity (emaily, importy, změny)
- Porovnání podílů: deklarované vs. evidované vs. součet z jednotek

### Uvítání pro nové instalace
Pokud je databáze prázdná (žádní vlastníci), zobrazí se místo tabulky aktivity uvítací blok s návodem prvních kroků:
1. Importovat vlastníky z Excelu
2. Zkontrolovat data s katastrem (CSV ze sousede.cz)
3. Založit první hlasování

---

## 11. Technické minimum pro výbor

### Spuštění
- Dvakrát kliknout na `spustit.command` (macOS)
- Aplikace se otevře v prohlížeči na `http://localhost:8000`
- Není potřeba internet (kromě emailů)

### Přenos na jiný počítač
- Zkopírovat celý projekt na USB
- Na novém počítači spustit `spustit.command`
- Pro přenos dat: zkopírovat složku `data/` (databáze + soubory)

### Zálohy
- **Doporučení:** před důležitými operacemi (import, výměna vlastníků) vytvořit zálohu
- Zálohy se ukládají do složky `data/backups/`

### Kde jsou data
- `data/svj.db` — hlavní databáze (SQLite)
- `data/uploads/` — nahrané soubory (Excel, PDF, Word, CSV)
- `data/generated/` — vygenerované exporty
- `data/backups/` — zálohy

---

## 12. Slovníček pojmů

| Pojem | Význam |
|-------|--------|
| **SJM** | Společné jmění manželů — manželé vlastní jednotku společně |
| **SČD** | Společné části domu — podíl vlastníka na společných prostorech |
| **Kvórum** | Minimální podíl hlasů potřebný pro platnost hlasování |
| **Per rollam** | Korespondenční hlasování (bez shromáždění) |
| **Lístek** | Hlasovací lístek konkrétního vlastníka v konkrétním hlasování |
| **Session** | Jedna kampaň rozesílání (např. vyúčtování 2025) |
| **Distribuce** | Přiřazení PDF dokumentu ke konkrétnímu vlastníkovi |
| **Matching** | Automatické přiřazení — aplikace hledá shodu jmen nebo variabilních symbolů |
| **Výměna vlastníků** | Nahrazení vlastníků na jednotce novými (např. při prodeji) |
| **Podíl** | Číslo vyjadřující váhu vlastníka (podíl na SČD = počet hlasů) |
| **Číselník** | Seznam povolených hodnot (typ prostoru, sekce domu...) |
| **SMTP** | Emailový server — nastavení pro odesílání emailů |
| **Variabilní symbol (VS)** | Unikátní číslo pro identifikaci platby — vlastník/nájemce ho uvádí při bankovním převodu |
| **Předpis** | Měsíční částka, kterou má vlastník platit SVJ |
| **Alokace** | Přiřazení platby ke konkrétnímu předpisu (měsíci) |
| **Nedoplatek** | Vlastník zaplatil méně, než bylo předepsáno |
| **Přeplatek** | Vlastník zaplatil více, než bylo předepsáno |
| **Vyúčtování** | Roční souhrn předpisů a plateb s výsledným nedoplatkem/přeplatkem |
| **Nesrovnalost** | Problém v platbě — špatný VS, nesprávná částka, nebo sloučená platba za více jednotek |
| **Prostor** | Nebytový prostor SVJ (sklep, garáž, kancelář...) — může být pronajímán |
| **Nájemce** | Osoba pronajímající prostor SVJ — může být propojená s vlastníkem |

---

## 13. Časté otázky

**Kolik procent je potřeba pro schválení bodu hlasování?**
Závisí na nastavení kvóra. Standardně 50 % podílů, ale výbor může nastavit jiné číslo. Pozor: počítají se podíly (SČD), ne osoby.

**Co se stane, když se prodá byt uprostřed hlasování?**
Aplikace upozorní, že se od generování lístků změnily podíly. Doporučuje se hlasování uzavřít s původními lístky, nebo vygenerovat nové.

**Může mít jeden vlastník více emailů?**
Ano. Aplikace eviduje primární a sekundární email. Při rozesílání si výbor vybere, na které adresy poslat.

**Co když import z Excelu najde duplicitního vlastníka?**
Vlastníci se identifikují podle rodného čísla/IČ. Pokud má stejné RČ, je to ten samý vlastník (jen s více jednotkami). Pokud nemá RČ, identifikuje se podle jména.

**Jak funguje bezpečnostní záloha?**
Před KAŽDOU obnovou ze zálohy aplikace automaticky vytvoří zálohu aktuálního stavu. Takže i kdyby se obnova nepovedla, data se neztratí.

**Co když zadám špatný email při vytváření vlastníka?**
Aplikace zkontroluje formát emailu a nepovolí uložení, pokud email nemá platný formát (např. chybí zavináč nebo doména). Zároveň upozorní, pokud vlastník se stejným emailem už existuje.

**Jak zjistím, že emailový server funguje?**
V Nastavení je tlačítko „Otestovat SMTP", které ověří připojení k emailovému serveru. Výsledek se zobrazí okamžitě — buď zelené potvrzení, nebo popis chyby.

**Jak exportuji data?**
Na stránce vlastníků nebo jednotek klikněte na tlačítko Export. Můžete si vybrat formát Excel (XLSX) nebo CSV. Exportují se vždy jen aktuálně zobrazená (filtrovaná) data.

**Jak funguje párování plateb?**
Aplikace se pokusí automaticky přiřadit platby z bankovního výpisu k předpisům. Nejdříve hledá přesnou shodu variabilního symbolu (nejvyšší jistota), pak shodu jména a částky, a nakonec zkouší dekódovat číslo jednotky z variabilního symbolu. Nepřiřazené platby lze přiřadit ručně.

**Co když vlastník platí za více měsíců najednou?**
Aplikace to zvládne — jedna platba se může rozdělit na více měsíců. Například čtvrtletní platba se alokuje na 3 měsíční předpisy.

**Jak zjistím, kdo dluží?**
V platebním přehledu je barevná matice — červené buňky znamenají nezaplacené měsíce. Aplikace také zobrazuje seznam dlužníků s celkovou dlužnou částkou.

**Co znamená „nedoplatek" ve vyúčtování?**
Nedoplatek znamená, že vlastník za daný rok zaplatil méně, než bylo celkem předepsáno (včetně případného zůstatku z předchozího roku). Přeplatek je opak — zaplatil více.

**Jak fungují nesrovnalosti v platbách?**
Po importu bankovního výpisu aplikace automaticky zkontroluje napárované platby a zjistí, kde vlastník použil špatný variabilní symbol, zaplatil jinou částku nebo sloučil platby za více jednotek. Tyto problémy zobrazí na přehledné stránce a nabídne možnost rozeslat upozornění emailem.

**Může se upozornění na nesrovnalost poslat dvakrát?**
Ne. Aplikace si u každé platby pamatuje, kdy bylo upozornění odesláno. Na stránce nesrovnalostí je vidět, které upozornění už byly odeslány a které ne.

**Jak fungují prostory a nájemci?**
Prostory SVJ (sklepy, garáže, kanceláře...) se evidují se svými nájemci. Nájemce může být propojený s existujícím vlastníkem nebo být zcela samostatná osoba. Platby nájemného se párují stejně jako platby vlastníků — přes variabilní symbol.
