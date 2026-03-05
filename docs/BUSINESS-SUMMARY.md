# SVJ Aplikace — Shrnutí pro výbor

> Netechnický popis fungování aplikace SVJ Správa.
> Dokument je určen členům výboru, kontrolní komisi a správcům.
> Poslední aktualizace: 2026-03-05

---

## Co aplikace dělá

Aplikace SVJ Správa slouží k evidenci vlastníků, správě hlasování per rollam, hromadnému rozesílání dokumentů a kontrole dat. Běží lokálně na počítači výboru (není potřeba internet, kromě rozesílání emailů).

---

## 1. Evidence vlastníků a jednotek

### Co se eviduje
- **Vlastníci:** jméno, titul, rodné číslo/IČ, trvalá adresa, korespondenční adresa, telefon(y), email(y), typ (fyzická/právnická osoba)
- **Jednotky:** číslo jednotky, podíl na společných částech domu (SČD), podlahová plocha, sekce domu, typ prostoru, LV číslo
- **Vztah vlastník-jednotka:** typ vlastnictví (SJM, VL...), podíl, platnost od/do

### Typ vlastnictví
- **SJM** (společné jmění manželů) — manželé vlastní jednotku společně, v hlasování mají jeden společný lístek
- **VL** — výlučné vlastnictví
- Ostatní typy se evidují dle prohlášení vlastníků

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

## 4. Synchronizace s externími zdroji

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

---

## 5. Administrace

### Informace o SVJ
- Název SVJ, typ budovy, celkový počet podílů (SČD)
- Adresy domů
- **Celkový počet podílů** je klíčový pro výpočet kvóra a procentuálních podílů

### Členové výboru
- Jméno, funkce, email, telefon
- Rozděleno na skupiny: výbor, kontrolní komise

### Číselníky
- Správa typů prostor, sekcí, počtů místností, typů vlastnictví
- Automaticky se naplní z existujících dat

### Emailové šablony
- Přednastavené šablony pro rozesílání
- Předmět + tělo emailu

### Zálohy
- **Záloha:** vytvoří ZIP se vším (databáze + nahrané soubory)
- **Obnova:** ze ZIP nebo rozbalené složky
- Před každou obnovou se automaticky vytvoří bezpečnostní záloha
- Historie obnov se ukládá do souboru (přežije i obnovu databáze)

### Smazání dat
- Selektivní mazání dat po kategoriích (vlastníci, hlasování, rozesílání, zálohy...)
- Respektuje závislosti (například smazání vlastníků smaže i jejich lístky)

---

## 6. Exporty

- **Excel export** z libovolného filtrovaného pohledu
- Formát XLSX s formátováním (tučné hlavičky, barevné zvýraznění rozdílů)
- Export vždy reflektuje aktuálně zobrazený filtr

---

## 7. Technické minimum pro výbor

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

## 8. Slovníček pojmů

| Pojem | Význam |
|-------|--------|
| **SJM** | Společné jmění manželů — manželé vlastní jednotku společně |
| **SČD** | Společné části domu — podíl vlastníka na společných prostorech |
| **Kvórum** | Minimální podíl hlasů potřebný pro platnost hlasování |
| **Per rollam** | Korespondenční hlasování (bez shromáždění) |
| **Lístek** | Hlasovací lístek konkrétního vlastníka v konkrétním hlasování |
| **Session** | Jedna kampaň rozesílání (např. vyúčtování 2025) |
| **Distribuce** | Přiřazení PDF dokumentu ke konkrétnímu vlastníkovi |
| **Matching** | Automatické přiřazení — aplikace hledá shodu jmen |
| **Výměna vlastníků** | Nahrazení vlastníků na jednotce novými (např. při prodeji) |
| **Podíl** | Číslo vyjadřující váhu vlastníka (podíl na SČD = počet hlasů) |
| **Číselník** | Seznam povolených hodnot (typ prostoru, sekce domu...) |

---

## 9. Časté otázky

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
