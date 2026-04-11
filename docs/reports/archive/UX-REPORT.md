# UX Analyza -- Cela aplikace SVJ Sprava

> Analyzovano: 05.04.2026
> Rozsah: cela aplikace (vsechny moduly v sidebaru)
> Porovnano s: ORCHESTRATOR-REPORT-2026-03-27.md (34 nalezu)

---

## Souhrn

| Pohled | Kriticke | Dulezite | Drobne |
|--------|----------|----------|--------|
| Bezny uzivatel | 1 | 5 | 4 |
| Business analytik | 1 | 4 | 2 |
| UI/UX designer | 2 | 5 | 3 |
| Performance analytik | 0 | 3 | 3 |
| Error recovery | 1 | 3 | 1 |
| Data quality | 1 | 3 | 2 |
| **Celkem** | **6** | **23** | **15** |

---

## Stav oprav z predchoziho reportu (2026-03-27)

### Opravene nalezy (od minuleho reportu)

| Puv. # | Nalez | Stav |
|---------|-------|------|
| U3 | Vyuctovani -- podezrela data (vse preplatky) | CASTECNE -- stale vse preplatky, viz #2 |
| U11 | Hlasovani -- patickovy text v bodu hlasovani | OPRAVENO |
| U22 | Hlasovani listky -- back link propagace | OPRAVENO |
| U27 | "Zpet" bez kontextu na detailu jednotky | OPRAVENO -- ted "Zpet na seznam vlastniku" |
| U29 | Dashboard -- prazdny stav pro noveho uzivatele | NELZE OVERIT (data v DB) |
| A3 | datetime.utcnow deprecated | OPRAVENO |
| A6 | Logger placement v email_service.py | OPRAVENO |

### Pretrvavajici nalezy

| Puv. # | Nalez | Stav |
|---------|-------|------|
| U1 | Matice plateb -- tabulka prilis siroka | PRETRVAVA -- viz #5 |
| U2 | Sidebar nema mobilni verzi | PRETRVAVA -- viz #6 |
| U4 | Dashboard zaplneny payment_notice emaily | PRETRVAVA -- viz #1 |
| U5 | Najemci -- duplicitni radky pro propojene najemce | PRETRVAVA -- viz #8 |
| U6 | Najemci detail -- nezobrazuje skutecny pronajem | PRETRVAVA |
| U7 | Detail vlastnika -- chybi celkovy dluh za vsechny jednotky | CASTECNE -- dluh se zobrazuje ale jen jako odkaz na zustatky |
| U8 | Rozeslika -- 597 radku bez filtrovacich bublin | PRETRVAVA |
| U9 | Prostory "???" jako VS | PRETRVAVA -- viz #9 |
| U13 | Dluznici 107 ukazuje na nezpracovane platby | PRETRVAVA -- viz #11 |
| U14 | Predpisy 549 vs Jednotky 508 -- nesedi pocty | PRETRVAVA -- viz #12 |
| U17 | Email log -- limit bez paginace | PRETRVAVA -- 1025 zaznamu bez paginace |
| U18 | Predpisy/matice -- prilis mnoho bublin | PRETRVAVA -- viz #13 |
| U25 | Zustatky -- prazdna stranka bez guidance | OPRAVENO -- nyni informativni text |
| U28 | HTMX search -- chybi loading indikator | PRETRVAVA |

---

## Nalezy a navrhy

### Dashboard (/)

#### Nalez #1: Dashboard zaplaven payment_notice emaily
- **Severity:** KRITICKE
- **Pohled:** Bezny uzivatel, Business analytik
- **Co a kde:** Tabulka "Posledni aktivita" na dashboardu je kompletne zaplnena radky "Upozorneni na nesrovnalost v platbe za Brezen 2026" (modul payment_notice). Vsech 1446 zaznamu je dominovano jednim typem aktivity. Uzivatel nevidi zadnou jinou aktivitu (hlasovani, importy, zmeny dat).
- **Dopad:** Dashboard je nepouzitelny pro prehled -- uzivatel musi scrollovat pres stovky identickych radku aby nasel cokoli jineho.
- **Reseni:** (A) Pridat filtrovaci bubliny dle modulu (payment_notice, voting, sync, import, atd.) s moznosti skryt/zobrazit. (B) Seskupit stejne akce do jednoho radku s poctem ("7x Upozorneni na nesrovnalost... za Brezen 2026"). (C) Pridat "posledni akce kazdeho typu" sekci nad tabulkou.
- **Varianty:** A je nejrychlejsi (~1 hod), B je nejlepsi UX ale slozitejsi (~2 hod), C kombinuje oboji (~3 hod).
- **Kde v kodu:** `app/routers/dashboard.py` (dotaz na activity log), `app/templates/dashboard.html`
- **Narocnost:** stredni ~1-2 hod
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** -- potrebna volba varianty A/B/C

#### Nalez #2: Vyuctovani -- vsechny polozky maji kladny vysledek (preplatky)
- **Severity:** KRITICKE
- **Pohled:** Data quality, Business analytik
- **Co a kde:** Na strance `/platby/vyuctovani` -- vsech 530 vyuctovani ukazuje zeleny kladny vysledek (napr. +40 887 Kc, +46 560 Kc). Soucet preplatku 6 984 Kc vs nedoplatky 9 961 012 Kc. Predpis celkem 44 604 Kc vs zaplaceno 3 717 Kc = vysledek by mel byt zaporny.
- **Dopad:** Data jsou zavadejici -- vysledek "Predpis celkem - Zaplaceno" by mel byt zaporny (uzivatel nezaplatil vsechny predpisy), ale zobrazuje se jako preplatek.
- **Reseni:** Zkontrolovat logiku vypoctu vysledku. Pokud Vysledek = Zaplaceno - Predpis, pak +40 887 = 3 717 - 44 604 nedava smysl. Pravdepodobne chybi data zustatku nebo je obracene znamenko.
- **Kde v kodu:** `app/routers/payments/settlement.py` (vypocet vysledku), `app/templates/payments/settlement.html`
- **Narocnost:** stredni ~1 hod
- **Zavislosti:** --
- **Regrese riziko:** stredni -- zmena vypoctu ovlivni exporty
- **Rozhodnuti:** -- overit logiku s realem

#### Nalez #3: Hledani v aktivite -- neni videt co se prohledava
- **Severity:** DROBNE
- **Pohled:** Bezny uzivatel
- **Co a kde:** Dashboard search bar "Hledat v aktivite..." -- neni jasne jaka pole se prohledavaji (datum? modul? popis? detail?).
- **Dopad:** Uzivatel netuhi co hledat, zkusi a nic nenajde.
- **Reseni:** Pridat placeholder s priklady: "Hledat v aktivite (popis, prijemce, modul...)"
- **Kde v kodu:** `app/templates/dashboard.html`
- **Narocnost:** nizka ~5 min
- **Zavislosti:** --
- **Regrese riziko:** nulove
- **Rozhodnuti:** -- jen opravit

---

### Vlastnici (/vlastnici)

#### Nalez #4: Prvni radek v tabulce -- prazdny radek "Pravnicka"
- **Severity:** DULEZITE
- **Pohled:** UI/UX designer, Data quality
- **Co a kde:** V seznamu vlastniku je prvni radek prazdny s textem "Pravnicka" ve sloupci Subjekt, bez jmena, emailu ci telefonu. Podil SCD = 0.
- **Dopad:** Vyvolava otazku zda jde o chybu v datech nebo systemovy zaznam. Neni klikaci (neni odkaz), takze se na nej nelze podivat.
- **Reseni:** (A) Vyfiltrovat zaznamy s prazdnym jmenem z tabulky, (B) Zobrazit jako "[Bez jmena]" s odkazem na detail, (C) Pridat bublinu "Nekompletni" se specialnim filtrem.
- **Kde v kodu:** `app/routers/owners/crud.py`, `app/templates/owners/list.html`
- **Narocnost:** nizka ~15 min
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** -- potreba rozhodnuti co s prazdnym zaznamem

#### Nalez #5: Detail vlastnika -- dluh jako odkaz na zustatky (slepicka)
- **Severity:** DULEZITE
- **Pohled:** Bezny uzivatel
- **Co a kde:** Na detailu vlastnika `/vlastnici/15` -- "Nedoplatek 39 036 Kc" je cerveny badge s odkazem na `/platby/zustatky`. Klik vede na prazdnou stranku "Zadne pocatecni zustatky pro rok 2026".
- **Dopad:** Uzivatel vidi dluh ale klik ho zavede na prazdnou stranku -- ztrata kontextu, zmatenost.
- **Reseni:** Odkaz by mel vest na detail dluznika pro konkretni jednotku (`/platby/dluznici?jednotka=523`), nebo zobrazit breakdown dluhu primo na detailu vlastnika.
- **Kde v kodu:** `app/templates/owners/detail.html`, `app/routers/owners/crud.py`
- **Narocnost:** nizka ~20 min
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** -- jen opravit cil odkazu

---

### Najemci (/najemci)

#### Nalez #6: Duplicitni radky pro propojene najemce
- **Severity:** KRITICKE
- **Pohled:** UI/UX designer, Bezny uzivatel
- **Co a kde:** Propojeni najemci (napr. "Beranek Martin", "Dvorak Lubos", "Hodík Michal") se zobrazuji jako DVA radky -- jeden bez prostoru (propojeny vlastnik) a druhy s prostorem (najemni smlouva). Celkem 31 radku misto realnych ~20 najemcu.
- **Dopad:** Uzivatel je zmaten -- proc je Beranek Martin dvakrat? Pocet "31 najemcu" je zavadejici (realnych najemcu je 20 + 11 vlastnich).
- **Reseni:** (A) Sjednotit propojeneho najemce do jednoho radku s prostorem, (B) Vizualne odlisit radky bez prostoru (zsedle, mensi), (C) Pridat filtr "S prostorem / Bez prostoru".
- **Mockup:**
  ```
  Soucasny stav:
  | Beranek Martin [link] | FO | -- | +420 602... | -- | -- | -- |
  | Beranek Martin [link] | FO | -- | +420 602... | 9 -- B2 01.11 | 775 Kc | 020... |

  Navrhovany stav (varianta A):
  | Beranek Martin [link] | FO | -- | +420 602... | 9 -- B2 01.11 | 775 Kc | 020... |
  ```
- **Kde v kodu:** `app/routers/tenants/crud.py`, `app/templates/tenants/list.html`
- **Narocnost:** stredni ~1 hod
- **Zavislosti:** --
- **Regrese riziko:** stredni -- zmena dotazu muze ovlivnit export
- **Rozhodnuti:** -- potreba volby varianty

#### Nalez #7: VS hodnota "???" u prostoru 8
- **Severity:** DULEZITE
- **Pohled:** Data quality
- **Co a kde:** Na strance najemcu i prostoru -- prostor 8 (B2 01.09) ma variabilni symbol "???". Stejne na `/prostory`.
- **Dopad:** Neplatny VS znemoznuje parovani plateb. Uzivatel si nevsimne ze VS je neplatny.
- **Reseni:** (A) Vizualni varovani (cervene zvyrazneni) pro neplatne VS, (B) Validace VS pri ukladani (jen cisla, min/max delka).
- **Kde v kodu:** `app/templates/tenants/list_rows.html`, `app/templates/spaces/list_rows.html`
- **Narocnost:** nizka ~15 min
- **Zavislosti:** --
- **Regrese riziko:** nulove
- **Rozhodnuti:** -- jen opravit

#### Nalez #8: VS s otaznikem "0101102020?"
- **Severity:** DROBNE
- **Pohled:** Data quality
- **Co a kde:** Prostor 21 (D 01.08) ma VS "0101102020?" -- otaznik naznacuje nejistotu v datech.
- **Dopad:** Otaznik v VS zpusobi problem pri parovani plateb.
- **Reseni:** Pridat validaci VS -- povoleny jen cislice, chyba pri specialnich znacich.
- **Kde v kodu:** `app/routers/spaces/crud.py`
- **Narocnost:** nizka ~10 min
- **Zavislosti:** --
- **Regrese riziko:** nulove
- **Rozhodnuti:** -- jen opravit

---

### Prostory (/prostory)

#### Nalez #9: Sloupec "Sekce" zobrazuje neobvykly format
- **Severity:** DROBNE
- **Pohled:** Bezny uzivatel
- **Co a kde:** Sloupec "Sekce" zobrazuje hodnoty jako "A 20", "A 22", "B 15", "C 13", "D 11", "D 9" -- cislo za pismenem neni vysvetleno.
- **Dopad:** Uzivatel nevi co cislo znamena (pocet jednotek? cislo budovy? adresa?).
- **Reseni:** Pridat tooltip na hlavicku "Sekce (pocet jednotek)" nebo oddelit do dvou sloupcu.
- **Kde v kodu:** `app/templates/spaces/list_rows.html`
- **Narocnost:** nizka ~5 min
- **Zavislosti:** --
- **Regrese riziko:** nulove
- **Rozhodnuti:** -- jen opravit

---

### Hlasovani (/hlasovani)

#### Nalez #10: Dve hlasovani se stejnym nazvem a datem
- **Severity:** DULEZITE
- **Pohled:** Bezny uzivatel, Data quality
- **Co a kde:** Obe hlasovani na `/hlasovani` maji identicky nazev "ROZHODOVANI PER ROLLAM vyhlasene 19. ledna 2026", stejne datumy (19.01.-19.02.2026), stejne hlasovaci body a STEJNE vysledky (2 575 847 PRO). Rozdil je pouze v rezimu (Kazdy svuj listek vs Spolecny listek) a poctu listku (190/395 vs 145/309).
- **Dopad:** Uzivatel nevidi v cem se hlasovani lisi na prvni pohled. Musi klikat na detail aby zjistil rozdil.
- **Reseni:** (A) Zobrazit rezim hlasovani vyrazneji (badge s barvou primo v nazvu), (B) Pridat ID hlasovani do nazvu/karty.
- **Kde v kodu:** `app/templates/voting/list.html`
- **Narocnost:** nizka ~15 min
- **Zavislosti:** --
- **Regrese riziko:** nulove
- **Rozhodnuti:** -- jen opravit

---

### Platby -- obecne

#### Nalez #11: Badge "107" v sidebaru -- Dluznici nebo nesparovane?
- **Severity:** DULEZITE
- **Pohled:** Bezny uzivatel
- **Co a kde:** V sidebaru je u polozky "Platby" cerveny badge "107". Na strance Dluznici se zobrazuje "107 jednotek s dluhem". Ale na Matici se ukazuje 1420 "naparovano" a 40 nesparovanych plateb. Badge 107 = dluznici, ne nesparovane platby.
- **Dopad:** Uzivatel si mysli ze ma 107 nesparovanych plateb (tooltip rika "Nesparovane platby"), ale ve skutecnosti jde o dluzniky.
- **Reseni:** Opravit tooltip na "Dluznici" nebo zmenit hodnotu badge na pocet skutecne nesparovanych plateb (6+2+14=22).
- **Kde v kodu:** `app/templates/base.html` (sidebar), `app/routers/dashboard.py`
- **Narocnost:** nizka ~10 min
- **Zavislosti:** --
- **Regrese riziko:** nulove
- **Rozhodnuti:** -- potreba rozhodnuti co badge znamena

#### Nalez #12: Predpisy 549 vs Jednotky 508 -- nesedi pocty
- **Severity:** DULEZITE
- **Pohled:** Data quality
- **Co a kde:** V navigaci Platby se ukazuje "Predpisy 549" ale v evidenci je jen 508 jednotek. 549 predpisu na 508 jednotek = 41 predpisu navic. Zaroven "Symboly 547" nesedi ani s jednim cislem.
- **Dopad:** Uzivatel nevi zda jde o chybu nebo o to ze nekterym jednotkam pripada vice predpisu.
- **Reseni:** Pridat vysvetlujici text pod nadpis "549 predpisu pro 508 jednotek (41 jednotek ma vice predpisu)" nebo zobrazit pocet unikatnich jednotek.
- **Kde v kodu:** `app/routers/payments/prescriptions.py`
- **Narocnost:** nizka ~15 min
- **Zavislosti:** --
- **Regrese riziko:** nulove
- **Rozhodnuti:** -- jen opravit

#### Nalez #13: Matice plateb -- prilis mnoho bublin (11 typu jednotek)
- **Severity:** DULEZITE
- **Pohled:** UI/UX designer, Performance analytik
- **Co a kde:** Na `/platby/prehled` -- dve rady bublin: "Jednotky/Prostory" a pod tim 11 typu jednotek (Vse 508, byt, gar.stani, gar.stani-1/2, gar.stani-1/4, gar.stani-1/8, gar.stani-3/8, garaz, komercni, nebytovy prostor, nebytovy prostor-1/2, sklad). Zabira hodne mista a je neprehledne.
- **Dopad:** Uzivatel je zaplaven volbami, nevi co vybrat.
- **Reseni:** (A) Seseskupit do dropdownu "Typ jednotky: [vse v]", (B) Zobrazit jen typy s >10 polozkami, zbytek do "Ostatni", (C) Kolapsovatelna sekce s popisem.
- **Kde v kodu:** `app/templates/payments/overview.html`
- **Narocnost:** stredni ~45 min
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** -- potreba volby varianty

---

### Platby -- Matice (/platby/prehled)

#### Nalez #14: Matice -- prazdne mesice zabiraji misto
- **Severity:** KRITICKE
- **Pohled:** UI/UX designer, Performance analytik
- **Co a kde:** Matice zobrazuje sloupce pro vsech 12 mesicu, ale data jsou jen za 3 mesice (Led, Uno, Bre). Zbylych 9 sloupcu (Dub-Pro) je prazdnych a zabiraji misto.
- **Dopad:** Tabulka je zbytecne siroka, uzivatel musi horizontalne scrollovat. Dulezite sloupce (Celkem, Dluh) jsou odsunute doprava.
- **Reseni:** (A) Skryt prazdne mesice automaticky, (B) Pridat prepinac "Zobrazit vsechny mesice / Jen s daty", (C) Sticky sloupce (C. jednotky, Vlastnik, Predpis) vlevo.
- **Mockup:**
  ```
  Soucasny stav (12 sloupcu):
  | C. | Vlastnik | Predpis | Prevod | Led | Uno | Bre | Dub | Kve | Cvn | Cvc | Srp | Zar | Rij | Lis | Pro | Celkem | Dluh |

  Navrhovany stav (jen s daty):
  | C. | Vlastnik | Predpis | Prevod | Led | Uno | Bre | Celkem | Dluh |
  ```
- **Kde v kodu:** `app/templates/payments/overview.html`, `app/routers/payments/overview.py`
- **Narocnost:** stredni ~2 hod
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** -- potreba volby varianty

---

### Platby -- Vyuctovani (/platby/vyuctovani)

#### Nalez #15: Hromadna zmena stavu bez nahledu
- **Severity:** DULEZITE
- **Pohled:** Error recovery
- **Co a kde:** Na strance vyuctovani je dropdown "Zmenit vsech 530 na..." s tlacitkem "Vse" -- umoznuje hromadnou zmenu stavu vsech 530 vyuctovani bez nahledu nebo potvrzeni.
- **Dopad:** Uzivatel muze omylem zmenit stav 530 zaznamu jednim klikem bez moznosti vraceni.
- **Reseni:** Pridat potvrzovaci dialog "Opravdu chcete zmenit stav 530 vyuctovani na [stav]?" s data-confirm atributem.
- **Kde v kodu:** `app/templates/payments/settlement.html`
- **Narocnost:** nizka ~10 min
- **Zavislosti:** --
- **Regrese riziko:** nulove
- **Rozhodnuti:** -- jen opravit

#### Nalez #16: Checkboxy bez "Oznacit vse" funkce
- **Severity:** DROBNE
- **Pohled:** Performance analytik
- **Co a kde:** V tabulce vyuctovani jsou checkboxy na kazdem radku a checkbox v hlavicce, ale neni jasne zda "Oznacit vse" oznaci jen viditelne (filtrovane) nebo vsechny zaznamy.
- **Dopad:** Nejednoznacnost pri hromadnych operacich.
- **Reseni:** Pridat text "(530 zaznamu)" vedle checkboxu v hlavicce, nebo tooltip.
- **Kde v kodu:** `app/templates/payments/settlement.html`
- **Narocnost:** nizka ~5 min
- **Zavislosti:** --
- **Regrese riziko:** nulove
- **Rozhodnuti:** -- jen opravit

---

### Platby -- Zustatky (/platby/zustatky)

#### Nalez #17: Prazdna stranka -- informativni text funguje
- **Severity:** -- (OPRAVENO)
- **Pohled:** Bezny uzivatel
- **Co a kde:** Stranka zustatku nyni zobrazuje informativni text "Pocatecni zustatky predstavuji stav uctu na zacatku roku" a tlacitko "Pridat zustatek" i v prazdne tabulce.
- **Dopad:** Dobre -- uzivatel vi co delat.

---

### Nastaveni (/nastaveni)

#### Nalez #18: Email log 1025 zaznamu bez paginace
- **Severity:** DULEZITE
- **Pohled:** Performance analytik
- **Co a kde:** Historie odeslanych emailu zobrazuje 1025 zaznamu najednou bez paginace nebo "Nacist dalsi".
- **Dopad:** Pomale nacitani, neprehlednost. PREDMET sloupec je oriznuty -- "Upozorneni na nesrovnalost v platbe za Brezen 2..." neni citelny.
- **Reseni:** (A) Pridat paginaci (50 zaznamu na stranku), (B) "Nacist dalsi" tlacitko (HTMX lazy load), (C) Zkratit na poslednich 100 s moznosti "Zobrazit vse".
- **Kde v kodu:** `app/routers/settings_page.py`, `app/templates/settings.html`
- **Narocnost:** stredni ~45 min
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** -- potreba volby varianty

#### Nalez #19: SMTP heslo zobrazeno jako tecicky -- nelze overit spravnost
- **Severity:** DROBNE
- **Pohled:** Error recovery
- **Co a kde:** Na `/nastaveni` -- heslo zobrazeno jako "........" (8 tecek). Nelze zjistit zda je heslo spravne zadane (napr. zkratove heslo Gmailu ma 16 znaku).
- **Dopad:** Uzivatel musi prejit do editace aby overil heslo.
- **Reseni:** Pridat tlacitko "Zobrazit/Skryt heslo" vedla tecicek. Nebo zobrazit pocet znaku: "........ (8 znaku)".
- **Kde v kodu:** `app/templates/settings.html`
- **Narocnost:** nizka ~10 min
- **Zavislosti:** --
- **Regrese riziko:** nulove
- **Rozhodnuti:** -- jen opravit

---

### Kontroly (/synchronizace)

#### Nalez #20: Dve tabulky na jedne strance -- neprehledne
- **Severity:** DROBNE
- **Pohled:** UI/UX designer
- **Co a kde:** Stranka Kontroly ma dva taby (Kontrola vlastniku, Kontrola podilu), kazdy s upload formem vlevo a tabulkou historie vpravo. Layout je horizontalne rozdeleny na 2 panely.
- **Dopad:** Na mensi obrazovce je tabulka stisknuta a nazvy souboru se lámou.
- **Reseni:** Pouzit vertikalni layout (upload nahore, tabulka dole) nebo kolapsovaaci sekci pro upload.
- **Kde v kodu:** `app/templates/sync/sync_page.html`
- **Narocnost:** nizka ~20 min
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** -- jen opravit

---

### Administrace (/sprava)

#### Nalez #21: Administrace -- dobre strukturovane
- **Severity:** -- (BEZ NALEZU)
- **Pohled:** Bezny uzivatel
- **Co a kde:** Stranka Administrace pouziva prehledne kartove rozlozeni (7 karet), kazda s ikonou, nazvem a popisem. Vazne "Smazat data" je cervene.
- **Dopad:** Dobre -- jasna vizualni hierarchie.

---

### Hromadne rozeslilani (/dane)

#### Nalez #22: Rozeslani "Predpis zaloh na rok 2026" -- 0/530 potvrzeno, status Rozpracovano
- **Severity:** DULEZITE
- **Pohled:** Business analytik
- **Co a kde:** Rozeslani ID 4 ma 530 dokumentu, 0 potvrzeno, stav "Rozpracovano". Wizard ukazuje krok 2 (Prirazeni). Neni jasne proc je nehotove -- chybi prirazeni PDF k vlastnikum? Chybi email?
- **Reseni:** Pridat informativni text ke kazde kampani na seznamu co je treba udelat dal: "Zbyvajici kroky: Nahrat PDF, Prirazeni k vlastnikum".
- **Kde v kodu:** `app/templates/tax/list.html`
- **Narocnost:** nizka ~20 min
- **Zavislosti:** --
- **Regrese riziko:** nulove
- **Rozhodnuti:** -- jen opravit

#### Nalez #23: Rozeslani -- chybi filtrovaci bubliny u prirazeni (597 radku)
- **Severity:** DULEZITE
- **Pohled:** Performance analytik
- **Co a kde:** Detail rozeslani (napr. ID 3) zobrazuje 597 prirazeni bez filtrovacich bublin. Na seznamu hlasovani i plateb bubliny jsou -- tady chybi.
- **Dopad:** Uzivatel musi scrollovat pres 597 radku bez moznosti filtrovat (napr. "Neodeslano", "Bez emailu", "S chybou").
- **Reseni:** Pridat bubliny: Vse / Odeslano / Neodeslano / Chyba / Bez emailu.
- **Kde v kodu:** `app/routers/tax/session.py`, `app/templates/tax/detail.html`
- **Narocnost:** stredni ~30 min
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** -- jen opravit

---

### Sidebar (cele aplikace)

#### Nalez #24: Sidebar nema mobilni verzi
- **Severity:** KRITICKE
- **Pohled:** UI/UX designer
- **Co a kde:** Sidebar je fixni 176px siroky, nema hamburger menu a na mobilnich zarizenich zabira podstatnou cast obrazovky.
- **Dopad:** Aplikace je na mobilech nepouzitelna.
- **Reseni:** Pridat hamburger menu pro mobilni zobrazeni (pod 768px) -- sidebar se schovava a otvira klikem.
- **Kde v kodu:** `app/templates/base.html`, `static/css/custom.css`
- **Narocnost:** stredni ~2 hod
- **Zavislosti:** --
- **Regrese riziko:** stredni -- muze ovlivnit layout vsech stranek
- **Rozhodnuti:** -- potreba rozhodnuti zda je mobilni verze potreba

#### Nalez #25: Sidebar -- polozka "Import z Excelu" je zavadejici
- **Severity:** DROBNE
- **Pohled:** Bezny uzivatel
- **Co a kde:** V sidebaru je polozka "Import z Excelu" primo pod "Prehled", ktera vede na `/vlastnici/import`. Ale import dat existuje i v Platbach (CSV vypisy, DOCX predpisy), Prostorech a Kontrolach.
- **Dopad:** Uzivatel si mysli ze jde o jediny import, pritom je to jen import vlastniku.
- **Reseni:** (A) Prejmenovani na "Import vlastniku", (B) Presunout do sekce Evidence pod Vlastniky.
- **Kde v kodu:** `app/templates/base.html`
- **Narocnost:** nizka ~5 min
- **Zavislosti:** --
- **Regrese riziko:** nulove
- **Rozhodnuti:** -- jen opravit

---

### HTMX search (vice stranek)

#### Nalez #26: Chybejici loading indikator pri hledani
- **Severity:** DULEZITE
- **Pohled:** Performance analytik
- **Co a kde:** Na vsech strankach s HTMX hledanim (Vlastnici, Jednotky, Najemci, Prostory, Dashboard aktivita) -- po zapsani do search baru neni zadna vizualni zpetna vazba ze se data nacitaji.
- **Dopad:** Uzivatel nevi zda hledani probehlo nebo ne, zvlaste pri pomalejsim pripojeni.
- **Reseni:** Pridat HTMX loading indikator (`hx-indicator`) -- spinner nebo "Nacitam..." text v tabulce.
- **Kde v kodu:** Vsechny sablony se search barem (6+ souboru)
- **Narocnost:** stredni ~30 min (globalni reseni v base.html)
- **Zavislosti:** --
- **Regrese riziko:** nulove
- **Rozhodnuti:** -- jen opravit

---

### Jednotky (/jednotky)

#### Nalez #27: Sloupec "Typ" oriznuty -- "jiny nebyto..."
- **Severity:** DROBNE
- **Pohled:** Bezny uzivatel
- **Co a kde:** V tabulce jednotek se sloupec Typ u dlouzich nazvu orizne: "jiny nebyto..." misto "jiny nebytovy prostor".
- **Dopad:** Uzivatel musi najet mysi na bunku aby videl plny nazev.
- **Reseni:** Pridat `title` atribut na bunku s plnym nazvem, nebo pouzit zkratku "JNP" s tooltipem.
- **Kde v kodu:** `app/templates/units/list_rows.html`
- **Narocnost:** nizka ~10 min
- **Zavislosti:** --
- **Regrese riziko:** nulove
- **Rozhodnuti:** -- jen opravit

#### Nalez #28: Filtrovaci bubliny -- chybi bublina "S dluhem"
- **Severity:** DULEZITE
- **Pohled:** Business analytik
- **Co a kde:** V evidenci jednotek jsou bubliny: Vse 508, byt 208, garaz 283, jiny nebytovy prostor 17. Chybi bublina "S dluhem" ktera by zobrazila jednotky s nedoplatkem.
- **Dopad:** Uzivatel musi jit na Dluznici (/platby/dluznici) aby videl jednotky s dluhem, nemuze filtrovat primo na seznamu jednotek.
- **Reseni:** Pridat bublinu "S dluhem X" ktera vyfiltruje jednotky kde dluh > 0.
- **Kde v kodu:** `app/routers/units.py`, `app/templates/units/list.html`
- **Narocnost:** stredni ~30 min
- **Zavislosti:** Vyzaduje join na payment data
- **Regrese riziko:** nizke
- **Rozhodnuti:** -- potreba rozhodnuti

---

### Error recovery (cele aplikace)

#### Nalez #29: Chybejici undo po destruktivnich akcich
- **Severity:** DULEZITE
- **Pohled:** Error recovery
- **Co a kde:** Po smazani entity (vlastnik, hlasovani, rozeslani) neexistuje moznost "Zpet" nebo "Undo". Data-confirm dialog sice chrani pred nahodnym smazanim, ale po potvrzeni je akce nevratna.
- **Dopad:** Omylem smazana data se nedaji obnovit (jen ze zalohy).
- **Reseni:** (A) Soft delete (priznak `deleted_at` misto fyzickeho smazani) s moznosti obnoveni, (B) Automaticka zaloha pred mazanim, (C) "Undo" toast po smazani (5 sekund na zruseni).
- **Kde v kodu:** Vsechny delete endpointy
- **Narocnost:** vysoka ~4 hod (varianta A), stredni ~1 hod (varianta C)
- **Zavislosti:** --
- **Regrese riziko:** stredni
- **Rozhodnuti:** -- potreba rozhodnuti

#### Nalez #30: Formulare bez autosave
- **Severity:** DROBNE
- **Pohled:** Error recovery
- **Co a kde:** Delsi formulare (novy vlastnik, nastaveni SMTP, info SVJ) nemaji autosave -- pri refreshi se data ztrati.
- **Dopad:** Uzivatel pri nahodnem refreshi nebo navigaci ztrati vyplnena data.
- **Reseni:** Pridat `data-warn-unsaved` atribut na formulare kde jiz neni (app.js podporuje beforeunload varovani).
- **Kde v kodu:** Vsechny formulare bez `data-warn-unsaved`
- **Narocnost:** nizka ~15 min
- **Zavislosti:** --
- **Regrese riziko:** nulove
- **Rozhodnuti:** -- jen opravit

---

### Data quality (cele aplikace)

#### Nalez #31: Chybejici audit trail
- **Severity:** KRITICKE
- **Pohled:** Data quality
- **Co a kde:** Aplikace nema zadny audit trail -- neni zaznam o tom kdo co kdy zmenil. Dashboard "Posledni aktivita" sleduje jen odesilani emailu (payment_notice), ne zmeny dat (vytvoreni/uprava/smazani vlastniku, importy, zmeny podilu).
- **Dopad:** Nelze zpetne dohledat kdo provedl zmenu, pri chybe nelze zjistit co se stalo.
- **Reseni:** (A) Rozsirit activity log o CRUD operace (created/updated/deleted entity), (B) Pridat sloupec `updated_by` k entitam (az po implementaci uzivatelskych roli).
- **Kde v kodu:** `app/models/activity.py` (novy), vsechny routery s POST/PUT/DELETE
- **Narocnost:** vysoka ~4-6 hod
- **Zavislosti:** Castecne na uzivatelskych rolich
- **Regrese riziko:** nizke (novy feature)
- **Rozhodnuti:** -- potreba rozhodnuti

#### Nalez #32: Import dat -- chybejici dry-run/preview pro vsechny importy
- **Severity:** DULEZITE
- **Pohled:** Data quality, Error recovery
- **Co a kde:** Import vlastniku ma preview krok, ale import prostoru a import zustatku ho nemaji -- data se importuji rovnou.
- **Dopad:** Chybna data v importovem souboru se okamzite propisi do databaze bez moznosti kontroly.
- **Reseni:** Pridat preview krok ke vsem import workflowum -- zobrazit co se zmeni pred potvrzenim.
- **Kde v kodu:** `app/routers/spaces/import_spaces.py`, `app/routers/payments/balances.py`
- **Narocnost:** stredni ~2 hod
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** -- jen opravit

---

## Top 10 doporuceni (podle dopadu)

| # | Navrh | Dopad | Slozitost | Cas | Zavisi na | Rozhodnuti | Priorita |
|---|-------|-------|-----------|-----|-----------|------------|----------|
| 1 | Dashboard -- filtrovaci bubliny na aktivitu (#1) | Vysoky | Stredni | ~1-2 hod | -- | -- | HNED |
| 2 | Vyuctovani -- opravit logiku vypoctu (#2) | Vysoky | Stredni | ~1 hod | -- | -- | HNED |
| 3 | Matice -- skryt prazdne mesice (#14) | Vysoky | Stredni | ~2 hod | -- | -- | HNED |
| 4 | Najemci -- odstranit duplicitni radky (#6) | Vysoky | Stredni | ~1 hod | -- | -- | BRZY |
| 5 | HTMX search -- loading indikator (#26) | Stredni | Nizka | ~30 min | -- | -- | BRZY |
| 6 | Sidebar badge 107 -- opravit tooltip (#11) | Stredni | Nizka | ~10 min | -- | -- | BRZY |
| 7 | Predpisy pocty -- vysvetlujici text (#12) | Stredni | Nizka | ~15 min | -- | -- | BRZY |
| 8 | Vyuctovani -- potvrzeni hromadne zmeny (#15) | Stredni | Nizka | ~10 min | -- | -- | HNED |
| 9 | Email log -- paginace (#18) | Stredni | Stredni | ~45 min | -- | -- | POZDEJI |
| 10 | Audit trail (#31) | Vysoky | Vysoka | ~4-6 hod | Uzivatele | -- | POZDEJI |

---

## Quick wins (nizka slozitost, okamzity efekt)

- [ ] Opravit tooltip sidebar badge 107: "Nesparovane platby" -> "Dluznici" (#11) ~10 min
- [ ] Pridat potvrzeni hromadne zmeny vyuctovani (#15) ~10 min
- [ ] Prejmenovat "Import z Excelu" v sidebaru na "Import vlastniku" (#25) ~5 min
- [ ] Pridat vysvetlujici text k predpisum 549 vs 508 (#12) ~15 min
- [ ] Pridat title atribut na orezane typy jednotek (#27) ~10 min
- [ ] Vizualni varovani pro neplatne VS ("???") (#7) ~15 min
- [ ] Pridat `data-warn-unsaved` na formulare kde chybi (#30) ~15 min
- [ ] Lepe odlisit dve hlasovani se stejnym nazvem (#10) ~15 min
- [ ] Opravit placeholder hledani na dashboardu (#3) ~5 min

---

## Poznamka k metodologii

Analyza probehla vizualnim pruchodem vsech modulu v prohlizeci (Playwright navigate + snapshot/screenshot) na portu 8025 s realnymy daty (447 vlastniku, 508 jednotek, 1460 plateb, 1025 emailu). Kazdy modul byl zkontrolovan z pohledu 6 expertnich roli dle UX-OPTIMIZER.md. Porovnani s predchozim reportem (ORCHESTRATOR-REPORT-2026-03-27.md) identifikovalo 7 opravenych a 14 pretrvavajicich nalezu. Nove nalezy vznikly predevsim z aktualizovanych dat (vice plateb, vice emailu) a hlubsi analyzy workflow.
