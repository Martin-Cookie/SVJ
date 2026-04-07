# UX Analyza -- Cela aplikace

> Analyzovano: 2026-03-27
> Predchozi analyza: 2026-03-09
> Rozsah: cela aplikace (dashboard, vlastnici, jednotky, najemci, prostory, hlasovani, dane/rozesilani, synchronizace, kontroly, platby, sprava, nastaveni)
> Metoda: navigace cele aplikace pres Playwright (snapshots + screenshoty) + analyza z 6 expertnich roli

## Stav nalezu k 2026-04-07

Z 34 nalezu tohoto reportu bylo **34 opraveno** (vsechny), zbyva **0 otevrenych**:

| # | Nalez | Stav |
|---|-------|------|
| #1 Dashboard aktivita zahltena | ✅ OPRAVENO — groupovani emailu |
| #2 Dashboard filtracni bubliny | ✅ OPRAVENO — bubliny dle modulu |
| #3 Dashboard onboarding | ✅ OPRAVENO — welcome blok |
| #4 Vlastnici dluh tooltip | ✅ OPRAVENO |
| #5 Detail vlastnika celkovy dluh | ✅ OPRAVENO — badge + link |
| #6 Najemci duplicitni radky | ✅ OPRAVENO — overeno v DB, zadne duplicity |
| #7 Propojeny najemce bez edit | ✅ OPRAVENO — info blok + link |
| #8 Propojeny najemce bez pronajmu | ✅ OPRAVENO |
| #9 VS "???" bez varovani | ✅ OPRAVENO — cerveny text + title |
| #10 Prostory filtr "S najemcem" | ✅ OPRAVENO 2026-04-07 — bubliny S najemcem/Bez najemce |
| #11 Hlasovani back link | ✅ OPRAVENO |
| #12 Hlasovaci polozka patickovy text | ✅ OPRAVENO 2026-04-07 — validace >200 znaku |
| #13 Pozastavena rozesilka vizual | ✅ OPRAVENO — zluty border |
| #14 Rozesilka matching bez paginace | ✅ OPRAVENO 2026-04-07 — info radek + filtry |
| #15 Platebni karta orezana | ✅ OPRAVENO |
| #16 Platebni matice siroka | ✅ OPRAVENO — skryti prazdnych mesicu + toggle |
| #17 Dluznici zavadejici pocet | ✅ OPRAVENO — info zprava |
| #18 Reparovat bez tooltipu | ✅ OPRAVENO |
| #19 Vyuctovani vsechny zelene | ✅ OPRAVENO 2026-04-07 — varovani pri samych preplatcich |
| #20 Zustatky prazdna stranka | ✅ OPRAVENO — info blok |
| #21 Sync zalozky nejasne | ✅ OPRAVENO — vizualni styl |
| #22 Administrace dobre navrzena | ✅ pozitivni nalez |
| #23 Smazat data bezpecnost | ✅ pozitivni nalez |
| #24 Hromadne upravy preview | ✅ OPRAVENO 2026-04-07 — pocet zaznamu v zahlavi |
| #25 Email log limit 100 | ✅ OPRAVENO — bez limitu |
| #26 Sidebar mobilni | ✅ OPRAVENO — hamburger menu |
| #27 Sidebar badge tooltip | ✅ OPRAVENO |
| #28 Search loading spinner | ✅ OPRAVENO — hx-indicator |
| #29 Unit detail back link | ✅ OPRAVENO — kontextove labely |
| #30 Nesoulad poctu predpisu | ✅ OPRAVENO — tooltip |
| #31 Hromadna zmena potvrzeni | ✅ OPRAVENO — data-confirm |
| #32 Badge platby neklikatelny | ✅ OPRAVENO — hover efekt |
| #33 Import varovani alarmujici | ✅ OPRAVENO — mirnejsi text |
| #34 Prilis mnoho bublin typu | ✅ OPRAVENO 2026-04-07 — dropdown pri >6 typech |

### Otevrene nalezy

Vsechny nalezy byly opraveny k 2026-04-07.

---

## Zmeny od posledni analyzy (09.03.2026)

Od posledni analyzy byly pridany/vyrazne zmeneny tyto moduly:
- **Najemci** -- novy modul pro evidenci najemcu s propojenim na vlastniky a prostory
- **Prostory** -- novy modul s importem, stavem pronajmu, napojenim na najemce
- **Platby** -- kompletni modul (predpisy, VS mapovani, vypisy, matice, dluznici, vyuctovani, zustatky)
- **Administrace** -- novy modul Duplicity, Export dat; rozsirene Smazat data
- **Dashboard** -- pridana karta Platby a Prostory

### Stav oprav z predchoziho reportu

| # | Nalez | Stav |
|---|-------|------|
| #1 Prazdny stav dashboardu | Nezmeneno -- stale bez onboarding bloku |
| #4 Validace duplicit vlastniku | OPRAVENO -- existuje `/sprava/duplicity` |
| #5 Email validace pri tvorbe | OPRAVENO -- formular vraci chybu s form_data |
| #22 Smazat data potvrzeni | OPRAVENO -- DELETE modal s textovym potvrzenim |
| #24 Administrace popisy karet | OPRAVENO -- karty maji druhy radek s popisem |
| #25 SMTP heslo placeholder | OPRAVENO -- viditelny placeholder |
| #27 SMTP test pripojeni | OPRAVENO -- tlacitko "Test pripojeni" existuje |
| #28 Sidebar mobilni verze | Nezmeneno -- stale bez responsivniho sidebaru |
| #31 CSV delimiter | Nutno overit v kodu |
| #35 emails_count | Nutno overit v kodu |

---

## Souhrn

| Pohled | Kriticke | Dulezite | Drobne |
|--------|----------|----------|--------|
| Bezny uzivatel | 1 | 4 | 3 |
| Business analytik | 0 | 3 | 2 |
| UI/UX designer | 1 | 3 | 4 |
| Performance analytik | 1 | 2 | 1 |
| Error recovery | 1 | 3 | 2 |
| Data quality | 0 | 2 | 2 |
| **Celkem** | **4** | **17** | **14** |

---

## Nalezy a navrhy

### Dashboard

#### Nalez #1: Dashboard posledni aktivita je zaplavena chybami rozesilky
- **Severity:** DULEZITE
- **Pohled:** Bezny uzivatel
- **Co a kde:** Dashboard (`/`) zobrazuje v tabulce "Posledni aktivita" desitky radku se stavem "Chyba" z rozesilky. Vsechny maji stejny modul, stejny popis, lisi se jen jmenem. Uzitecna aktivita (importy, zmeny stavu) je utopena pod stovkami chybovych radku.
- **Dopad:** Uzivatel po otevreni aplikace vidi jen chyby, nevi co se v aplikaci skutecne deje. Dashboard ztaci svuj ucel.
- **Reseni:** (1) Seskupit stejne udalosti -- misto 30x "Chyba - Vyuctovani ... - Jmeno" zobrazit "30 chyb pri rozesilce Vyuctovani..." s moznosti rozbaleni. (2) Nebo pridat filtr modulu na aktivitu (bubliny: Vse / Rozesilani / Import / Platby).
- **Varianty:** A) Seskupeni -- nizka slozitost, zachova detail. B) Filtrovaci bubliny -- stredni slozitost, vetsi flexibilita.
- **Kde v kodu:** `app/templates/dashboard.html`, `app/routers/dashboard.py` (query pro aktivitu)
- **Narocnost:** stredni ~1 hod
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** Potreba rozhodnuti uzivatele
- **Jak otestovat:** Otevrit `/` -- melo by byt jasne co se deje, ne 50 radku "Chyba"

#### Nalez #2: Dashboard -- chybi filtrovaci bubliny na posledni aktivitu
- **Severity:** DROBNE
- **Pohled:** Business analytik
- **Co a kde:** Tabulka posledni aktivity na dashboardu nema filtrovaci bubliny podle modulu (Rozesilani, Import, Platby, Hlasovani) ani podle stavu (Chyba, Uspech, Info).
- **Dopad:** Uzivatel nemuze rychle najit konkretni typ aktivity.
- **Reseni:** Pridat bubliny nad tabulku: Vse / Rozesilani / Import / Hlasovani / Platby + Vse / Chyba / Uspech.
- **Kde v kodu:** `app/templates/dashboard.html`, `app/routers/dashboard.py`
- **Narocnost:** stredni ~45 min
- **Zavislosti:** Souvis s #1
- **Regrese riziko:** nizke
- **Rozhodnuti:** Potreba rozhodnuti uzivatele
- **Jak otestovat:** Na dashboardu by mely byt filtrovaci bubliny nad aktivitou

#### Nalez #3: Dashboard -- chybi prazdny stav pro noveho uzivatele (z reportu #1)
- **Severity:** DROBNE
- **Pohled:** Bezny uzivatel
- **Co a kde:** Stale plati z predchoziho reportu. S prazdnou DB uzivatel vidi jen nulove karty a zadny navod.
- **Dopad:** Novy uzivatel nevi kde zacit.
- **Reseni:** Onboarding blok s kroky: 1) Import vlastniku, 2) Kontrola podilu, 3) Zalozit hlasovani.
- **Kde v kodu:** `app/templates/dashboard.html`
- **Narocnost:** nizka ~30 min
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** Opravit

---

### Vlastnici

#### Nalez #4: Seznam vlastniku -- sloupec "Dluh" se zobrazuje cervene, ale chybi vysvetleni
- **Severity:** DROBNE
- **Pohled:** Bezny uzivatel
- **Co a kde:** V tabulce vlastniku (`/vlastnici`) se u nekterych vlastniku zobrazuje cervena castka v sloupci "Dluh" (napr. "422 Kc", "150 Kc"). Neni jasne za jake obdobi, jak se pocita, ani na co presne se klikne.
- **Dopad:** Uzivatel vidi cislo ale nema kontext.
- **Reseni:** Pridat tooltip na castku dluhu s vysvetlenim ("Dluh za rok 2026 = predpis - zaplaceno"). Kliknutim na dluh presmerovat na detail plateb dane jednotky.
- **Kde v kodu:** `app/templates/owners/list.html` (sloupec Dluh)
- **Narocnost:** nizka ~20 min
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** Opravit

#### Nalez #5: Detail vlastnika -- neni videt celkovy dluh za vsechny jednotky
- **Severity:** DULEZITE
- **Pohled:** Business analytik
- **Co a kde:** Detail vlastnika (`/vlastnici/{id}`) zobrazuje jednotky s podily a plochou, ale sloupec "Dluh" v tabulce jednotek je prazdny u nekterych -- neni jasne jestli to znamena 0 Kc nebo chybejici data.
- **Dopad:** Uzivatel musi kazde cislo jednotky rozkliknout zvlast aby zjistil stav plateb.
- **Reseni:** (1) Zobrazit dluh v tabulce jednotek na detailu vlastnika. (2) Pridat sumacni radek "Celkovy dluh: X Kc" jako je to u podilu SCD.
- **Kde v kodu:** `app/templates/owners/detail.html`, `app/routers/owners/crud.py`
- **Narocnost:** stredni ~30 min
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** Opravit

---

### Najemci (novy modul)

#### Nalez #6: Najemci -- duplicitni radky pro propojene najemce
- **Severity:** DULEZITE
- **Pohled:** UI/UX designer
- **Co a kde:** V seznamu najemcu (`/najemci`) se propojeni najemci (ti co maji vazbu na vlastnika) zobrazuji 2x -- jednou jako "zakladni" zaznam bez prostoru a jednou jako "prostorovy" zaznam s prostorem. Napr. "Beranek Martin" je v tabulce dvakrat, jednou bez prostoru a jednou s prostorem "9 - B2 01.11".
- **Dopad:** Tabulka ma 31 radku ale realne je 20 propojeni + 11 vlastnich = az 31 unikatnich, ale vizualne to vypada jako duplicity. Matouci pro uzivatele.
- **Reseni:** (1) Sloupcit radky -- propojeny najemce zobrazit jednou s jeho prostorem/y. (2) Nebo vizualne seskupit (odsazeni, skupina) aby bylo jasne ze druhy radek patri ke stejne osobe.
- **Varianty:** A) Sjednotit na 1 radek per najemce. B) Zachovat ale vizualne seskupit. C) Pridat bublinu "Bez prostoru" pro filtraci.
- **Kde v kodu:** `app/routers/tenants/crud.py`, `app/templates/tenants/list.html`
- **Narocnost:** stredni ~1 hod
- **Zavislosti:** --
- **Regrese riziko:** stredni (zmena struktury dat v tabulce)
- **Rozhodnuti:** Potreba rozhodnuti uzivatele
- **Jak otestovat:** Otevrit `/najemci` a zkontrolovat ze kazdy najemce je jen 1x (nebo jasne seskupeny)

#### Nalez #7: Najemci detail -- propojeny najemce nema editacni moznosti
- **Severity:** DULEZITE
- **Pohled:** Bezny uzivatel
- **Co a kde:** Detail propojeneho najemce (`/najemci/1`) zobrazuje vsechny udaje z vlastnika (identifikace, kontakty, adresy) ale misto tlacitek "Upravit" ma jen "Vlastnik ->" odkaz. Uzivatel musi prejit na kartu vlastnika pro jakoukoli upravu.
- **Dopad:** Pokud chce uzivatel zmenit telefon najemce, musi klikat pres 2 stranky.
- **Reseni:** Budu u propojeneho najemce zobrazit jasnou hlasku "Data se ctou z karty vlastnika. Upravte udaje tam." s vyraznym odkazem na vlastnika. Nebo umoznit primou editaci s propagaci na vlastnika.
- **Kde v kodu:** `app/templates/tenants/detail.html`
- **Narocnost:** nizka ~15 min (jasnejsi UX text)
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** Opravit (text)

#### Nalez #8: Najemci -- "Aktualni prostor" u propojeneho najemce ukazuje "Zadny aktivni pronajem"
- **Severity:** DULEZITE
- **Pohled:** Data quality
- **Co a kde:** Detail najemce Jelinek Roman (ID 1, propojeny s vlastnikem) zobrazuje "Zadny aktivni pronajem" v sekci "Aktualni prostor", prestoze v seznamu najemcu existuje druhy zaznam (ID 21) se stejnym jmenem ktery MA prostor "1 - A 01.06".
- **Dopad:** Uzivatel nevidime na detailu najemce jeho skutecny pronajem.
- **Reseni:** Pri zobrazeni detailu propojeneho najemce zobrazit vsechny prostory kde je jako najemce evidovan (vcetne prostoru z jineho zaznamu najemce se stejnym propojenim).
- **Kde v kodu:** `app/routers/tenants/crud.py` (detail endpoint), `app/templates/tenants/detail.html`
- **Narocnost:** stredni ~30 min
- **Zavislosti:** Souvis s #6
- **Regrese riziko:** nizke
- **Rozhodnuti:** Opravit

---

### Prostory (novy modul)

#### Nalez #9: Prostory -- "???" jako variabilni symbol u nekterych prostoru
- **Severity:** DROBNE
- **Pohled:** Data quality
- **Co a kde:** V tabulce prostoru (`/prostory`) i najemcu (`/najemci`) se u nekterych zaznamu zobrazuje "???" ve sloupci VS (napr. prostor 8, najemce Chvostik). To vypada jako chyba nebo placeholder ktery se zapomnel nahradit.
- **Dopad:** Uzivatel nevi jestli "???" je chyba v datech nebo skutecna hodnota.
- **Reseni:** (1) Validovat VS pri importu/zadani -- upozornit na neplatne hodnoty. (2) Zobrazit "???" cervenou barvou s ikonou varovani aby bylo jasne ze je to problem.
- **Kde v kodu:** `app/templates/spaces/list.html`, data v DB
- **Narocnost:** nizka ~15 min (vizualni upozorneni)
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** Opravit (vizualni upozorneni)

#### Nalez #10: Prostory -- chybi bublina "S najemcem" / "Bez najemce"
- **Severity:** DROBNE
- **Pohled:** Performance analytik
- **Co a kde:** Prostory maji bubliny Vse/Pronajato/Volne/Blokovane a dropdown sekci. Ale chybi moznost rychle filtrovat "prostory s platnym najemcem" vs "prostory bez najemce" (ne jen podle stavu).
- **Dopad:** Minorni -- "Pronajato" je blizky filtr, ale nezahrnuje prostory s najemcem ale bez smlouvy.
- **Reseni:** Zvazit zda existuji prostory se stavem "Pronajato" ale bez najemce -- pokud ne, neni treba.
- **Kde v kodu:** `app/routers/spaces/crud.py`
- **Narocnost:** nizka ~15 min
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** Drobne, neni priorita

---

### Hlasovani

#### Nalez #11: Hlasovani listky -- chybi back link na strance listku
- **Severity:** DROBNE
- **Pohled:** Bezny uzivatel
- **Co a kde:** Na strance hlasovacich listku (`/hlasovani/2/listky`) je back link "Zpet na hlasovani", ale bubliny (Celkem listku / Zbyva zpracovat / Zpracovano / Neodevzdane) se prepinaji mezi strankami bez zachovani back URL kontextu.
- **Dopad:** Minorni -- uzivatel se muze ztratit pri preklikavani mezi podstrankami hlasovani.
- **Reseni:** Overit ze vsechny bubliny a odkazy na podstrankach hlasovani propaguji `back` parametr.
- **Kde v kodu:** `app/templates/voting/ballots.html`
- **Narocnost:** nizka ~15 min
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** Opravit

#### Nalez #12: Hlasovani detail -- druhy bod hlasovani obsahuje patickovy text
- **Severity:** DULEZITE
- **Pohled:** Data quality
- **Co a kde:** Na detailu hlasovani (`/hlasovani/2`) druhy bod obsahuje text "Hlasovaci listek prosim vlozte do schranky spolecenstvi v Hogerova 11. Termin pro odevzdani je 19. unora 2026. Dekujeme Vam za Vas cas a hlasovani!" -- to je text z paticky hlasovacieho listku, ne soucast bodu.
- **Dopad:** Vysledky hlasovani vypadaji neprofesionalne a matouci. Bod je neprimerane dlouhy.
- **Reseni:** Toto je datovy problem -- pri importu/vytvoreni hlasovani se paticka vlozila do textu bodu. Opravit v datech + pridat warning pri vytvoreni bodu pokud je text neobvykle dlouhy.
- **Kde v kodu:** Data v DB (voting_items tabulka), `app/routers/voting/session.py` (create/edit items)
- **Narocnost:** nizka ~10 min (oprava dat), stredni ~30 min (prevence)
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** Opravit data

---

### Hromadne rozesilani (dane)

#### Nalez #13: Rozesilka -- pozastavena rozesilka nema vyrazny vizualni stav
- **Severity:** DULEZITE
- **Pohled:** Bezny uzivatel
- **Co a kde:** Na seznamu rozesilek (`/dane`) rozesilka "Vyuctovani sluzeb..." ma stav "Pozastaveno" a 669/805, ale vizualne se lisi jen textem badge. Chybi jasna indikace ze rozesilka ceka na akci uzivatele.
- **Dopad:** Uzivatel muze prehlednout ze rozesilka je pozastavena a potrebuje pozornost.
- **Reseni:** Pridat vizualni odliseni pro pozastavene rozesilky -- napr. oranzovy ramecek kolem karty, ikona varovani, nebo pulzujici indikator.
- **Kde v kodu:** `app/templates/tax/index.html`
- **Narocnost:** nizka ~15 min
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** Opravit

#### Nalez #14: Rozesilka detail -- stranky prirazeni je zahltena 597 radky bez rozumne navigace
- **Severity:** DULEZITE
- **Pohled:** Performance analytik
- **Co a kde:** Detail rozesilky (`/dane/3`) na kroku "Prirazeni" zobrazuje vsech 597 PDF v jedne tabulce. I s hledanim je to velmi dlouha tabulka.
- **Dopad:** Pomale scrollovani, tezke najit konkretni PDF. Napr. najit neprirazene dokumenty vyzaduje prochazeni vsech.
- **Reseni:** (1) Pridat paginaci (50 radku na stranku). (2) Pridat filtrovaci bubliny nad tabulku (Potvrzeno / K potvrzeni / Neprirazeno) -- bubliny uz existuji, ale jen jako stat karty nahore.
- **Kde v kodu:** `app/routers/tax/session.py`, `app/templates/tax/matching.html`
- **Narocnost:** stredni ~45 min (paginace), nizka ~20 min (bubliny jako filtry)
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** Opravit (bubliny jako filtry)

---

### Platby (novy modul)

#### Nalez #15: Platby nav karty -- "VS mapov..." je orezany text
- **Severity:** DROBNE
- **Pohled:** UI/UX designer
- **Co a kde:** V navigacnich kartach modulu Platby je druha karta orezana jako "VS mapov... 547". Plny text "VS mapovani" se nevejde do karty.
- **Dopad:** Uzivatel nemuze precist cely nazev sekce.
- **Reseni:** (1) Zkratit na "VS" s tooltipem. (2) Nebo zvetsit sirku karet. (3) Nebo pouzit mensi font-size pro delsi texty.
- **Kde v kodu:** `app/templates/payments/_nav.html` nebo ekvivalent
- **Narocnost:** nizka ~10 min
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** Opravit

#### Nalez #16: Matice plateb -- 12 mesicu + meta sloupce = tabulka nekonecne siroka
- **Severity:** KRITICKE
- **Pohled:** UI/UX designer
- **Co a kde:** Matice plateb (`/platby/prehled`) zobrazuje 508 radku x ~20 sloupcu (C., Sekce, Vlastnik, Predpis, Prevod, Led-Pro, Celkem, Dluh). Tabulka je extre mnoe siroka. Na screenshotu vidim ze mesice za Unor jsou prazdne ale zabiji prostor.
- **Dopad:** Tabulka je tezko prehledna, horizontalni scroll je nutny. Mesice bez dat zabiji prostor.
- **Reseni:** (1) Skryt mesice bez dat (zobrazit jen mesice kde existuji platby). (2) Nebo pridat konfiguraci "Zobrazit mesice od-do". (3) Pridat sticky prvni 3 sloupce (C., Sekce, Vlastnik) aby pri scrollu bylo videt kdo je kdo.
- **Varianty:** A) Skryt prazdne mesice -- nejjednodussi. B) Sticky sloupce -- lepsi UX ale slozitejsi. C) Oboje.
- **Kde v kodu:** `app/templates/payments/overview.html`, `app/routers/payments/overview.py`
- **Narocnost:** stredni ~1 hod (skryt prazdne), stredni ~1.5 hod (sticky)
- **Zavislosti:** --
- **Regrese riziko:** stredni
- **Rozhodnuti:** Potreba rozhodnuti uzivatele
- **Jak otestovat:** Otevrit `/platby/prehled` -- melo by byt prehledne i pri 500+ radcich
- **Mockup:**
  ```
  Soucasny stav:
  +----+------+----------+--------+--------+-----+-----+-----+---+---+---+---+---+---+---+---+--------+------+
  | C. | Sek. | Vlastnik | Predp. | Prevod | Led | Uno | Bre | D | K | C | S | Z | R | L | P | Celkem | Dluh |
  +----+------+----------+--------+--------+-----+-----+-----+---+---+---+---+---+---+---+---+--------+------+
  | 1  | A    | Gavril.. | 3717   | --     | V   | V   |     |   |   |   |   |   |   |   |   | 7434   | 0    |
  (10 prazdnych mesicnich sloupcu)

  Navrhovany stav (varianta A):
  +----+------+--------------+--------+--------+-----+-----+--------+------+
  | C. | Sek. | Vlastnik     | Predp. | Prevod | Led | Uno | Celkem | Dluh |
  +----+------+--------------+--------+--------+-----+-----+--------+------+
  | 1  | A    | Gavrilovic.. | 3717   | --     | V   | V   | 7434   | 0    |
  (jen mesice s daty)
  ```

#### Nalez #17: Dluznici -- vysoky pocet (109) ukazuje na mozny systemovy problem
- **Severity:** DULEZITE
- **Pohled:** Business analytik
- **Co a kde:** Dluznici (`/platby/dluznici`) ukazuje 109 jednotek s dluhem, celkem 211 953 Kc. U vsech je "Zaplaceno: 0 Kc" a "Mesice: 2". To vypada jako by se nezpracovaly zadne platby za unor, ne jako skutecne dluhy.
- **Dopad:** Uzivatel vidi alarmujici cisla ktera jsou mozna jen dusledkem toho ze unor jeste nebyl zpracovan.
- **Reseni:** (1) Pridat informativni hlasku "Data zahrnuji platby do [posledni importovany mesic]". (2) Pridat moznost vyloucit aktualni/posledni mesic ze zobrazeni. (3) Zvyraznit ze dluh = predpis - zaplaceno a pokud neni import za dany mesic, je dluh ocekavany.
- **Kde v kodu:** `app/routers/payments/settlement.py`, `app/templates/payments/debtors.html`
- **Narocnost:** nizka ~20 min (informativni hlaska)
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** Opravit

#### Nalez #18: Vypis detail -- "Preparovat" tlacitko bez vysvetleni
- **Severity:** DROBNE
- **Pohled:** Bezny uzivatel
- **Co a kde:** Na detailu vypisu (`/platby/vypisy/2`) jsou tri akni tlacitka: "Preparovat", "Smazat", "Zamknout". Tlacitko "Preparovat" je bez jakehokoliv vysvetleni -- co presne udela?
- **Dopad:** Uzivatel muze omylem spustit akci jejiz dopad neceka.
- **Reseni:** Pridat tooltip/title na tlacitko: "Znovu sparovat vsechny platby s predpisy podle VS".
- **Kde v kodu:** `app/templates/payments/statement_detail.html`
- **Narocnost:** nizka ~5 min
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** Opravit

#### Nalez #19: Vyuctovani -- vsechny vysledky ukazuji zelene plusy (preplatky)
- **Severity:** DULEZITE
- **Pohled:** Data quality
- **Co a kde:** Na strance vyuctovani (`/platby/vyuctovani`) vsech 530 zaznamu ukazuje zeleny preplatek (napr. "+40 887 Kc"). Celkove preplatky 6 984 Kc, nedoplatky 9 961 012 Kc. Cisla jsou podezrele -- soucet preplatku (cca 7K) vs nedoplatku (cca 10M) je nekonzistentni.
- **Dopad:** Vyuctovani muze byt chybne. Uzivatel nevi jestli jsou cisla spravna.
- **Reseni:** (1) Overit logiku vypoctu vyuctovani (predpis celkem - zaplaceno). (2) Pridat validaci -- pokud vsechny vysledky jsou preplatky, zobrazit varovani. (3) Pridat sumarni radek dole.
- **Kde v kodu:** `app/routers/payments/settlement.py`, `app/services/settlement_service.py`
- **Narocnost:** stredni ~1 hod (overeni + oprava logiky)
- **Zavislosti:** --
- **Regrese riziko:** stredni
- **Rozhodnuti:** Opravit (overit logiku)

#### Nalez #20: Zustatky -- prazdna stranka bez guidance
- **Severity:** DROBNE
- **Pohled:** Bezny uzivatel
- **Co a kde:** Stranka zustatku (`/platby/zustatky`) zobrazuje prazdnou tabulku s textem "Zadne pocatecni zustatky pro rok 2026. Pridat zustatek ->". Chybi vysvetleni co jsou pocatecni zustatky a proc by je uzivatel mel zadat.
- **Dopad:** Uzivatel nevi co stranka dela a proc je dulezita.
- **Reseni:** Pridat informativni blok nad tabulku: "Pocatecni zustatky predstavuji stav uctu na zacatku roku. Importujte je z Excelu nebo zadejte rucne aby vyuctovani spravne pocitalo."
- **Kde v kodu:** `app/templates/payments/balances.html`
- **Narocnost:** nizka ~10 min
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** Opravit

---

### Synchronizace / Kontroly

#### Nalez #21: Kontroly -- dva typy kontrol na jedne strance s prepinacimi tlacitky
- **Severity:** DROBNE
- **Pohled:** UI/UX designer
- **Co a kde:** Stranka `/synchronizace` zobrazuje bud "Kontrola vlastniku" nebo "Kontrola podilu" podle kliknuti na prepinaci tlacitka nahore. Prepinani funguje dobre, ale vizualne to nejsou taby -- vypadaji jako obycejne tlacitka.
- **Dopad:** Minorni -- uzivatel si nemuze byt jisty ze jde o prepinani obsahu stranky.
- **Reseni:** Vizualne odlisit aktivni tab (napr. podtrzeni, zmena pozadi) aby bylo jasne ze jde o tab navigaci.
- **Kde v kodu:** `app/templates/sync/index.html`
- **Narocnost:** nizka ~10 min
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** Drobne, neni priorita

---

### Administrace

#### Nalez #22: Administrace -- index stranka je dobre navrzena
- **Severity:** --
- **Pohled:** UI/UX designer
- **Co a kde:** Stranka `/sprava` ma 7 prehlednych karet s ikonami, nazvy a popisy. Kazda karta ma druhy radek s kontextovou informaci (pocty, posledni datum). Navigace je intuitivni.
- **Dopad:** Pozitivni nalez -- dobre navrzene.
- **Reseni:** Zadna zmena nutna.

#### Nalez #23: Smazat data -- vyborne navrzena bezpecnostni stranka
- **Severity:** --
- **Pohled:** Error recovery
- **Co a kde:** Stranka `/sprava/smazat` ma vicevrstvou ochranu: (1) checkboxy pro kategorie, (2) pocty zaznamu u kazde kategorie, (3) popis co smazani ovlivni, (4) varovani "smazana data nelze obnovit", (5) textove potvrzeni "DELETE", (6) disabled tlacitko dokud neni napsano DELETE.
- **Dopad:** Pozitivni nalez -- nebezpecna akce je velmi dobre chranena.
- **Reseni:** Zadna zmena nutna.

#### Nalez #24: Hromadne upravy -- chybi vizualni nahled zmen (z reportu)
- **Severity:** DULEZITE
- **Pohled:** Bezny uzivatel
- **Co a kde:** Stale plati z predchoziho reportu. Karty hromadnych uprav (`/sprava/hromadne-upravy`) ukazuji pocty hodnot a vazeb, ale po kliknuti chybi nahled "co se zmeni".
- **Dopad:** Uzivatel provede zmenu bez plneho vedomosti o dopadu.
- **Reseni:** Pridat pocitadlo ovlivnenych zaznamu pred potvrzenim operace.
- **Kde v kodu:** `app/templates/administration/bulk_edit_records.html`
- **Narocnost:** stredni ~45 min
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** Opravit

---

### Nastaveni

#### Nalez #25: Email log -- stale limit 100 zaznamu bez paginace
- **Severity:** DROBNE
- **Pohled:** Performance analytik
- **Co a kde:** Stale plati z predchoziho reportu. Na screenshotu vidim "100 zaznamu" -- uzivatel nemuze videt starsi emaily.
- **Dopad:** Po odeslani vice nez 100 emailu neni pristup ke starsim zaznamum.
- **Reseni:** Pridat paginaci nebo tlacitko "Nacist dalsi".
- **Kde v kodu:** `app/routers/settings_page.py`
- **Narocnost:** stredni ~45 min
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** Potreba rozhodnuti -- 100 muze byt dost

---

### Globalni / Prurezove

#### Nalez #26: Sidebar nema mobilni verzi (z reportu #28)
- **Severity:** KRITICKE
- **Pohled:** UI/UX designer
- **Co a kde:** Stale plati. Sidebar je fixovany na `w-44` bez responzivniho chovani. Na mobilnich zarizenich je aplikace nepouzitelna.
- **Dopad:** Aplikace nefunguje na tabletu/telefonu.
- **Reseni:** Hamburger menu pro obrazovky pod 768px.
- **Kde v kodu:** `app/templates/base.html`
- **Narocnost:** stredni ~2 hod
- **Zavislosti:** --
- **Regrese riziko:** stredni
- **Rozhodnuti:** Potreba rozhodnuti -- pouziva se na mobilu?

#### Nalez #27: Sidebar badge "109" u Platby -- chybi vysvetleni
- **Severity:** DROBNE
- **Pohled:** Bezny uzivatel
- **Co a kde:** V sidebaru u polozky "Platby" je cerveny badge "109". Neni jasne co cislo znamena -- pocet dluzniku? Pocet nezpracovanych plateb? Pocet nepaparovanych?
- **Dopad:** Badge vyvolava pocit naLehavosti ale uzivatel nevi proc.
- **Reseni:** Pridat tooltip na badge: "109 jednotek s dluhem". Nebo zmenit barvu -- cervena = alarm, seda/modra = informativni.
- **Kde v kodu:** `app/templates/base.html` (sidebar polozka Platby)
- **Narocnost:** nizka ~5 min
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** Opravit

#### Nalez #28: HTMX search -- chybi loading indikator (z reportu #30)
- **Severity:** DULEZITE
- **Pohled:** Bezny uzivatel
- **Co a kde:** Stale plati. Search bary na vsech strankach (vlastnici, jednotky, najemci, prostory, dashboard) nemaji vizualni indikator nacitani pri HTMX requestu.
- **Dopad:** Uzivatel nevi zda se hledani provadi.
- **Reseni:** Pridat `hx-indicator` s spinnerem na search bary.
- **Kde v kodu:** Vsechny search inputy v sablon ach
- **Narocnost:** nizka ~30 min
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** Opravit

#### Nalez #29: Jednotky detail -- back link rika jen "Zpet" bez kontextu
- **Severity:** DROBNE
- **Pohled:** Bezny uzivatel
- **Co a kde:** Na detailu jednotky (`/jednotky/1`) back link rika jen "Zpet" misto "Zpet na seznam jednotek". Na detailu vlastnika spravne rika "Zpet na seznam vlastniku".
- **Dopad:** Minorni nekonzistence v navigaci.
- **Reseni:** Zmenit back_label pro jednotky na "Zpet na seznam jednotek" nebo "Zpet na detail vlastnika" podle kontextu.
- **Kde v kodu:** `app/routers/units.py` (back_label logika)
- **Narocnost:** nizka ~5 min
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** Opravit

#### Nalez #30: Predpisy 549 vs Jednotky 508 -- nesedi pocty
- **Severity:** DULEZITE
- **Pohled:** Data quality
- **Co a kde:** V navigaci Plateb je "Predpisy 549" ale v evidenci je jen 508 jednotek. Detail predpisu ukazuje 530 predpisu. Cisla 549 vs 530 vs 508 nesedi a neni jasne proc.
- **Dopad:** Uzivatel nevi ktere cislo je spravne a proc se lisi.
- **Reseni:** (1) Vysvetlit na strance predpisu odkud cislo pochazi (napr. "549 radku v DOCX = 530 jednotek + 19 spoluvlastniku"). (2) Pridat info text ke stat kartam v navigaci.
- **Kde v kodu:** `app/routers/payments/prescriptions.py`
- **Narocnost:** nizka ~15 min (informativni text)
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** Opravit

#### Nalez #31: Vyuctovani -- hromadna zmena stavu bez nahledu
- **Severity:** DULEZITE
- **Pohled:** Error recovery
- **Co a kde:** Na strance vyuctovani (`/platby/vyuctovani`) je dropdown "Zmenit vsech 530 na..." s tlacitkem "Vse". Toto umoznuje hromadne zmenit stav vsech 530 vyuctovani jednim kliknutim bez potvrzeni.
- **Dopad:** Nechcena hromadna zmena muze zpusobit problemy.
- **Reseni:** Pridat potvrzovaci dialog: "Opravdu chcete zmenit stav u 530 vyuctovani na [novy stav]?".
- **Kde v kodu:** `app/templates/payments/settlement.html`
- **Narocnost:** nizka ~10 min
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** Opravit

#### Nalez #32: Jednotky detail -- badge "Zaplaceno" vs "Dluh" je klikaci ale cil neni jasny
- **Severity:** DROBNE
- **Pohled:** Bezny uzivatel
- **Co a kde:** Na detailu jednotky (`/jednotky/1`) je badge "Zaplaceno" (zeleny) ktery je odkaz na `/platby/jednotka/1`. Uzivatel nevi ze je to odkaz -- vypada jako staticky badge.
- **Dopad:** Uzivatel neprozkouma platby dane jednotky protoze nevi ze badge je klikaci.
- **Reseni:** Pridat sipku nebo podtrzeni na badge aby bylo jasne ze je klikaci. Nebo zmenit na explicitni odkaz "Zobrazit platby ->".
- **Kde v kodu:** `app/templates/units/detail.html`
- **Narocnost:** nizka ~5 min
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** Opravit

#### Nalez #33: Import vlastniku -- varovani "Import nahradi vsech 512 vlastniku" je desive
- **Severity:** DULEZITE
- **Pohled:** Error recovery
- **Co a kde:** Na strance importu (`/vlastnici/import`) je cervene varovani "Pozor: Import nahradi vsech 512 vlastniku v databazi." Toto muze uzivatele odradit od pouziti importu i kdyz je to bezpecna operace (re-import ze stejneho souboru).
- **Dopad:** Uzivatel se boji pouzit import i kdyz potrebuje aktualizovat data.
- **Reseni:** (1) Zmenit text na "Import aktualizuje evidenci -- existujici vlastnici budou aktualizovani, novi pridani." (2) Pridat krok nahledu pred potvrzenim importu (uz existuje v kontaktech, aplikovat i na vlastniky).
- **Kde v kodu:** `app/templates/owners/import.html`
- **Narocnost:** nizka ~10 min (zmena textu)
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** Opravit (text)

#### Nalez #34: Tabulky typ prostoru bubliny -- prilis mnoho typu
- **Severity:** DROBNE
- **Pohled:** UI/UX designer
- **Co a kde:** Na strankach predpisu a matice plateb je 11+ bublin pro typy prostoru (byt, gar.stani, gar.stani-1/2, gar.stani-1/4, gar.stani-1/8, gar.stani-3/8, garaz, komercni, nebytovy prostor, nebytovy prostor-1/2, sklad). Bubliny zabiraji 2 radky a ztracuji prehlednost.
- **Dopad:** Prilis mnoho filtracnich moznosti mate uzivatele. Vetisna uzivatelu pouzije jen "byt" a "garaz".
- **Reseni:** (1) Seskupit podobne typy -- "gar.stani (vse)" misto 5 variant. (2) Nebo pouzit dropdown misto bublin pro typy s mene nez 10 zaznamy.
- **Kde v kodu:** `app/templates/payments/prescriptions_detail.html`, `app/templates/payments/overview.html`
- **Narocnost:** stredni ~45 min
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** Potreba rozhodnuti uzivatele

---

## Top 5 doporuceni (podle dopadu)

| # | Navrh | Dopad | Slozitost | Cas | Zavisi na | Rozhodnuti | Priorita |
|---|-------|-------|-----------|-----|-----------|------------|----------|
| 1 | #16: Matice plateb -- skryt prazdne mesice + sticky sloupce | Vysoky (klicova stranka neprehledna) | Stredni | ~2 hod | -- | Potreba rozhodnuti | BRZY |
| 2 | #1: Dashboard -- seskupit/filtrovat aktivitu | Vysoky (dashboard neplni ucel) | Stredni | ~1 hod | -- | Potreba rozhodnuti | BRZY |
| 3 | #19: Vyuctovani -- overit logiku vypoctu | Vysoky (mozna chybna data) | Stredni | ~1 hod | -- | Opravit | HNED |
| 4 | #6: Najemci -- resit duplicitni radky | Stredni (matouci UI) | Stredni | ~1 hod | -- | Potreba rozhodnuti | BRZY |
| 5 | #28: HTMX search loading indikator | Stredni (chybejici zpetna vazba) | Nizka | ~30 min | -- | Opravit | HNED |

---

## Quick wins (nizka slozitost, okamzity efekt)

- [ ] #15: Platby nav -- opravit orezany text "VS mapov..." (~10 min)
- [ ] #18: Vypis detail -- pridat tooltip na "Preparovat" (~5 min)
- [ ] #27: Sidebar badge -- pridat tooltip "109 jednotek s dluhem" (~5 min)
- [ ] #29: Jednotky detail -- zmenit "Zpet" na "Zpet na seznam jednotek" (~5 min)
- [ ] #32: Jednotky detail -- zvyraznit klikaci badge plateb (~5 min)
- [ ] #9: Prostory -- zvyraznit "???" jako varovani (~15 min)
- [ ] #13: Rozesilka -- vizualni odliseni pozastavene rozesilky (~15 min)
- [ ] #17: Dluznici -- pridat info o obdobi dat (~20 min)
- [ ] #20: Zustatky -- pridat informativni text (~10 min)
- [ ] #30: Predpisy -- vysvetlit rozdil v poctech (~15 min)
- [ ] #33: Import -- zmenit desive varovani na informativni text (~10 min)
- [ ] #7: Najemci detail -- jasnejsi UX text u propojeneho najemce (~15 min)
- [ ] #31: Vyuctovani -- pridat potvrzeni pro hromadnou zmenu (~10 min)
