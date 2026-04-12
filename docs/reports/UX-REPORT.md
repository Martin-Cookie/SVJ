# UX Analyza -- Cela aplikace SVJ Sprava

> Analyzovano: 12.04.2026
> Rozsah: cela aplikace (vsechny moduly)
> Metoda: Playwright pruchod vsech modulu + analyza kodu z 6 expertnich pohledu

---

## Souhrn

| Pohled | Kriticke | Dulezite | Drobne |
|--------|----------|----------|--------|
| Bezny uzivatel | 2 | 4 | 3 |
| Business analytik | 1 | 3 | 2 |
| UI/UX designer | 2 | 5 | 4 |
| Performance analytik | 0 | 2 | 3 |
| Error recovery | 1 | 2 | 2 |
| Data quality | 1 | 3 | 2 |
| **Celkem** | **7** | **19** | **16** |

---

## Nalezy a navrhy

### Dashboard (/)

#### Nalez #1: Bubliny "None" a "test" v aktivite
- **Severity:** DULEZITE
- **Pohled:** Bezny uzivatel, Data quality
- **Co a kde:** Na dashboardu v sekci "Posledni aktivita" se zobrazi filtr bubliny "test 1", "3 2", "1 3", "2 3", "None 4" -- tyto nazvy modulu jsou nesrozumitelne a matouci.
- **Dopad:** Uzivatel nevedi co bubliny znamenaji, nektere jsou ocividne zbytky testovacich dat ("test") a chybne normalizace ("None").
- **Reseni:** (1) V `_norm_module()` v `dashboard.py` pridat mapovani pro nezname moduly na citelne nazvy. (2) Filtrovat pryc moduly bez nazvu nebo s nazvem "None". (3) Vycistit zaznamy s modulem "test" z ActivityLog.
- **Kde v kodu:** `app/routers/dashboard.py` -- funkce `_norm_module()` a `module_counts_ordered`
- **Narocnost:** nizka ~15 min
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** 🔧 jen opravit
- **Jak otestovat:** Otevrit `/` -> v bublinach nesmeni byt "None" ani "test"

#### Nalez #2: Prvni radek v tabulce vlastniku bez jmena
- **Severity:** DULEZITE
- **Pohled:** Data quality, Bezny uzivatel
- **Co a kde:** Na strance `/vlastnici` se zobrazi prvni radek tabulky s prazdnym jmenem -- jen badge "Pravnicka" a zadne jmeno, email, telefon, ani IC. Radek neni klikaci.
- **Dopad:** Fantasticke data -- vlastnik bez identifikace. Narusuje duveru v kvalitu dat.
- **Reseni:** (1) Identifikovat a smazat/opravit zaznam (pravdepodobne artifact importu). (2) Pridat validaci pri importu -- vlastnik musi mit alespon jmeno nebo IC.
- **Kde v kodu:** DB zaznam v tabulce `owners` + `app/routers/owners/import_owners.py`
- **Narocnost:** nizka ~10 min (cisteni dat), stredni ~30 min (validace importu)
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** 🔧 jen opravit
- **Jak otestovat:** Otevrit `/vlastnici` -> zadny radek nesmi mit prazdne jmeno

---

### Evidence vlastniku (/vlastnici)

#### Nalez #3: Sloupec "Dluh" neni preimenovan na "Saldo"
- **Severity:** DULEZITE
- **Pohled:** UI/UX designer, Bezny uzivatel
- **Co a kde:** V tabulce vlastniku a jednotek se stale pouziva hlavicka "Dluh", zatimco v platebnim modulu uz je vsude "Saldo". Viz take AUDIT-REPORT nalez #10.
- **Dopad:** Nekonzistentni terminologie mate uzivatele -- na jedne strance "Dluh", na druhe "Saldo".
- **Reseni:** Prejmenovat "Dluh" na "Saldo" v sablonach `owners/_table.html` a `units/index.html`.
- **Kde v kodu:** `app/templates/owners/_table.html`, `app/templates/units/index.html`
- **Narocnost:** nizka ~10 min
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** 🔧 jen opravit
- **Jak otestovat:** Otevrit `/vlastnici` a `/jednotky` -> hlavicka sloupce musi byt "Saldo"

#### Nalez #4: Detail vlastnika -- chybi platebni prehled
- **Severity:** DULEZITE
- **Pohled:** Business analytik
- **Co a kde:** Na detailu vlastnika (`/vlastnici/1`) se zobrazi identifikace, kontakty, adresy a jednotky, ale CHYBI jakekoliv informace o platbach -- predpisy, zaplaceno, saldo, vyuctovani.
- **Dopad:** Uzivatel musi prechazet do platebniho modulu a hledat jednotku rucne. Neni mozne rychle ziskat kompletni prehled o vlastnikovi.
- **Reseni:** Pridat sekci "Platby" pod tabulku jednotek s prehledem: predpis/mes, zaplaceno celkem, saldo. Odkaz na matici plateb s filtrem na dane jednotky.
- **Kde v kodu:** `app/templates/owners/detail.html`, `app/routers/owners/crud.py`
- **Narocnost:** stredni ~1 hod
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** ❓ potreba rozhodnuti uzivatele
- **Jak otestovat:** Otevrit `/vlastnici/1` -> pod jednotkami videt platebni prehled
- **Mockup:**
  ```
  Soucasny stav:
  +-------------------------------------------+
  | Jednotky                        [+ Pridat] |
  | Jedn. | Dluh | Prostor | Typ | Podil SCD  |
  |   1   |  --  |  A 111  | byt | 12 212     |
  +-------------------------------------------+
  (konec stranky)

  Navrhovany stav:
  +-------------------------------------------+
  | Jednotky                        [+ Pridat] |
  | Jedn. | Saldo | Prostor | Typ | Podil SCD |
  |   1   |   0   |  A 111  | byt | 12 212    |
  +-------------------------------------------+
  | Platby 2026                                |
  | Predpis/mes: 3 717 Kc                      |
  | Zaplaceno: 11 151 Kc (3 mes.)              |
  | Saldo: 0 Kc                                |
  | [-> Matice plateb]  [-> Vyuctovani]        |
  +-------------------------------------------+
  ```

---

### Evidence jednotek (/jednotky)

#### Nalez #5: Chybi bubliny pro filtrovani dle sekce
- **Severity:** DROBNE
- **Pohled:** Performance analytik
- **Co a kde:** Stanka jednotek ma 508 zaznamu a dropdown "Vsechny sekce", ale nema bubliny pro rychle filtrovani typu (byt/garaz/jiny). Pouze ma 4 bubliny (Vse/byt/garaz/jiny nebytovy prostor).
- **Dopad:** Sekce A/B/C/D/K se da filtrovat jen pres dropdown, ne jednim kliknutim.
- **Reseni:** Dropdown pro sekce je v poradku pri 5+ sekcich. Neni treba menit -- dropdown je zde spravny vzor.
- **Narocnost:** --
- **Zavislosti:** --
- **Regrese riziko:** --
- **Rozhodnuti:** Informativni -- soucasny stav je OK
- **Jak otestovat:** --

---

### Evidence prostoru (/prostory)

#### Nalez #6: Nektere prostory maji VS "???" 
- **Severity:** DULEZITE
- **Pohled:** Data quality
- **Co a kde:** V tabulce prostoru (radek 5 -- A 01.03, radek 8 -- B2 01.09) je ve sloupci VS hodnota "???". To signalizuje chybejici variabilni symbol.
- **Dopad:** Platby za tyto prostory nelze automaticky parovat. Uzivatel to nemusi zaznamenat.
- **Reseni:** (1) Zvyraznit "???" cervene + tooltip "Chybi variabilni symbol -- priradtez v Platby > Symboly". (2) Pridat kontrolu na strance Kontroly ktera identifikuje prostory bez VS.
- **Kde v kodu:** `app/templates/spaces/index.html`
- **Narocnost:** nizka ~15 min
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** 🔧 jen opravit
- **Jak otestovat:** Otevrit `/prostory` -> "???" musi byt cervene s tooltipem

---

### Evidence najemcu (/najemci)

#### Nalez #7: Nektere radky nemaji klikaci jmeno
- **Severity:** DROBNE
- **Pohled:** UI/UX designer, Bezny uzivatel
- **Co a kde:** V tabulce najemcu maji nektere radky jmeno jako plain text (cerne), jine jako modry odkaz. Napr. "Baumrt", "Novak Petr" jsou neklikaci, zatimco "Beranek Martin" je klikaci (modre s ikonou propojeni).
- **Dopad:** Uzivatel nemuze otevrit detail neklikacich najemcu. Nekonzistentni chovani.
- **Reseni:** Vsechna jmena v tabulce by mela byt klikaci (odkaz na detail najemce). Propojeni na vlastnika je uz vizualizovano ikonou retezce.
- **Kde v kodu:** `app/templates/tenants/index.html`
- **Narocnost:** nizka ~10 min
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** 🔧 jen opravit
- **Jak otestovat:** Otevrit `/najemci` -> kazde jmeno musi byt klikaci odkaz

#### Nalez #8: Chybi export tlacitka v kontext. buble
- **Severity:** DROBNE
- **Pohled:** UI/UX designer
- **Co a kde:** Tabulka najemcu ma export (Excel/CSV) v hlavicce, ale chybi pocet zaznamu (napr. "20 najemcu") vedle exportnich tlacitek -- je pouze v titulku.
- **Dopad:** Mensi -- informace je k dispozici, jen ne na ocekavanem miste.
- **Reseni:** Pridat pocet zaznamu vedle exportnich tlacitek, konzistentne s ostatnimi tabulkami.
- **Kde v kodu:** `app/templates/tenants/index.html`
- **Narocnost:** nizka ~5 min
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** 🔧 jen opravit
- **Jak otestovat:** Otevrit `/najemci` -> vedle Excel/CSV tlacitek videt "20 zaznamu"

---

### Platby -- Predpisy (/platby/predpisy)

#### Nalez #9: Prazdna plocha pod predpisem roku
- **Severity:** DROBNE
- **Pohled:** UI/UX designer
- **Co a kde:** Stranka predpisu zobrazuje jediny radek (2026) a pod nim zustava obrovska prazdna plocha. Stranka nevyuziva prostor efektivne.
- **Dopad:** Uzivatel muze byt zmateny, zda se stranka nacetla spravne.
- **Reseni:** (1) Pridat informacni text nebo statistiky predpisovych polozek. (2) Zobrazit preview top 5 predpisovych polozek primo na strance. (3) Alternativne -- presmerovat primo na detail predpisu (pokud existuje jen 1 rok).
- **Kde v kodu:** `app/templates/payments/prescriptions.html`
- **Narocnost:** nizka ~15 min
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** ❓ potreba rozhodnuti uzivatele
- **Jak otestovat:** Otevrit `/platby/predpisy` -> stranka nema velkou prazdnou plochu

---

### Platby -- Matice (/platby/prehled)

#### Nalez #10: Sloupec "Prevod" je prazdny u vsech radku
- **Severity:** DULEZITE
- **Pohled:** Bezny uzivatel, Business analytik
- **Co a kde:** V matici plateb 2026 je sloupec "Prevod" u vsech radku prazdny (pomlcka). Uzivatel nevedi co sloupec znamena ani proc je prazdny.
- **Dopad:** Zbytecny sloupec zabira misto a mate uzivatele.
- **Reseni:** (1) Pridat tooltip/napovedu vysvetlujici co "Prevod" znamena (pocatecni zustatek / prevod z predchoziho roku). (2) Pokud neni prevod definovan pro 2026, skryt sloupec nebo zobrazit 0.
- **Kde v kodu:** `app/templates/payments/overview.html`
- **Narocnost:** nizka ~10 min
- **Zavislosti:** Souvisi s nalez #15 (zustatky)
- **Regrese riziko:** nizke
- **Rozhodnuti:** ❓ potreba rozhodnuti uzivatele
- **Jak otestovat:** Otevrit `/platby/prehled` -> sloupec Prevod musi byt buд vyplneny nebo skryty

#### Nalez #11: Cervene castky bez vysvetleni v matici
- **Severity:** DULEZITE
- **Pohled:** Bezny uzivatel
- **Co a kde:** V matici plateb jsou cervene castky v mesicnich sloupcich (napr. "1 471" u jednotky 4 v lednu). Uzivatel nemuze na prvni pohled rozlisit zda cervena znamena: (a) castecne zaplaceno, (b) preplaceno, (c) nezaplaceno.
- **Dopad:** Legenda dole ("Zaplaceno / Castecne / Nezaplaceno / Bez dat") pouziva barvy, ale castky v bunkach jsou casto jen cervene cislo bez kontextu.
- **Reseni:** Pridat tooltip na mesicni bunky s detailem: predpis X Kc, zaplaceno Y Kc, rozdil Z Kc.
- **Kde v kodu:** `app/templates/payments/overview.html`
- **Narocnost:** stredni ~30 min
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** 🔧 jen opravit
- **Jak otestovat:** Otevrit `/platby/prehled` -> najet mysi na cervenou castku -> tooltip zobrazi detail

#### Nalez #12: Matice -- chybi sumacni radek
- **Severity:** DROBNE
- **Pohled:** Business analytik
- **Co a kde:** Matice plateb nema souhrnny radek (celkovy predpis, celkem zaplaceno per mesic, celkove saldo).
- **Dopad:** Uzivatel nema rychly prehled o celkovem stavu plateb za SVJ.
- **Reseni:** Pridat `<tfoot>` se sumami: celkovy predpis/mes, suma zaplaceno per mesic, celkove saldo.
- **Kde v kodu:** `app/templates/payments/overview.html`
- **Narocnost:** stredni ~45 min
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** ❓ potreba rozhodnuti uzivatele
- **Jak otestovat:** Otevrit `/platby/prehled` -> scrollovat dolu -> videt souhrnny radek

---

### Platby -- Dluznici (/platby/dluznici)

#### Nalez #13: Dluznici -- "Detail ->" link neni dostatecne viditelny
- **Severity:** DROBNE
- **Pohled:** UI/UX designer
- **Co a kde:** V tabulce dluzniku je sloupec "Detail ->" jako posledni, s textem sedy na tmavem pozadi. Neni dostatecne vyrazny.
- **Dopad:** Uzivatel muze prehlednout moznost zobrazit detail.
- **Reseni:** Nahradit text "Detail ->" SVG ikonou sipky (konzistentne s ostatnimi tabulkami kde jsou ikony akci).
- **Kde v kodu:** `app/templates/payments/dluznici.html`
- **Narocnost:** nizka ~5 min
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** 🔧 jen opravit
- **Jak otestovat:** Otevrit `/platby/dluznici` -> misto textu "Detail ->" videt ikonu sipky

---

### Platby -- Vypisy (/platby/vypisy)

#### Nalez #14: Vypis detail -- 102 nesrovnalosti badge bez akce
- **Severity:** KRITICKE
- **Pohled:** Bezny uzivatel, Error recovery
- **Co a kde:** Na detailu vypisu Leden 2026 (`/platby/vypisy/1`) je cerveny badge "102 nesrovnalosti", ale neni klikaci a neni jasne jak se k nesrovnalostem dostat.
- **Dopad:** Uzivatel vidi ze existuji nesrovnalosti, ale nema jak je resit primo z teto stranky.
- **Reseni:** Udelat badge klikaci -- odkaz na detail nesrovnalosti (s filtrem na dany mesic). Pridat tooltip vysvetlujici co nesrovnalost znamena.
- **Kde v kodu:** `app/templates/payments/vypis_detail.html`
- **Narocnost:** nizka ~15 min
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** 🔧 jen opravit
- **Jak otestovat:** Otevrit `/platby/vypisy/1` -> kliknout na badge "102 nesrovnalosti" -> otevre se seznam nesrovnalosti

#### Nalez #15: Vypis detail -- datum bez roku u plateb
- **Severity:** DROBNE
- **Pohled:** Bezny uzivatel
- **Co a kde:** V tabulce plateb na detailu vypisu jsou datumy ve formatu "02.01." (bez roku). U starsiho vypisu to muze byt matouci.
- **Dopad:** Nizky -- rok je jasny z kontextu (titul stranky), ale u budoucich roku s vice vypisy muze byt matouci.
- **Reseni:** Ponechat soucasny stav -- rok je uveden v titulku stranky a vsechny platby v jednom vypisu jsou ze stejneho mesice.
- **Narocnost:** --
- **Zavislosti:** --
- **Regrese riziko:** --
- **Rozhodnuti:** Informativni -- soucasny stav je akceptovatelny

---

### Platby -- Zustatky (/platby/zustatky)

#### Nalez #16: Poznamka "Zalohy: 4766.0" format
- **Severity:** DROBNE
- **Pohled:** UI/UX designer
- **Co a kde:** Ve sloupci "Poznamka" zustatku jsou hodnoty typu "Zalohy: 4766.0" -- cislo ma desetinnou tecku a jednu nulu za teckou. Neni konzistentni s formatovanim castek jinde v aplikaci (kde se pouziva mezera jako oddelovac tisicu a "Kc" suffix).
- **Dopad:** Vizualni nekonzistence. Uzivatel muze byt zmateny formatem.
- **Reseni:** Formatovat castky v poznamce stejne jako jinde: "Zalohy: 4 766 Kc" pomoci filtru `fmt_num`.
- **Kde v kodu:** `app/routers/payments/balances.py` (pri importu/ukladani poznamky)
- **Narocnost:** nizka ~10 min
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** 🔧 jen opravit
- **Jak otestovat:** Otevrit `/platby/zustatky` -> poznamky musi mit formatovane castky

---

### Platby -- Vyuctovani (/platby/vyuctovani)

#### Nalez #17: Vyuctovani -- dve bubliny "Vse" vedle sebe
- **Severity:** KRITICKE
- **Pohled:** UI/UX designer, Bezny uzivatel
- **Co a kde:** Na strance vyuctovani jsou DVE sady bublin, obe zacinajici bublinkou "Vse". Prvni rada: "530 Vse" | "530 Vse" | "530 Vygenerovano" | "0 Odeslano" | "0 Zaplaceno" | "0 Po splatnosti". Druha bublivka "530 Vse" je duplicitni a matouci.
- **Dopad:** Uzivatel nevedi kterou "Vse" bublinu kliknout. Vizualne to pusobi jako chyba.
- **Reseni:** Odstranit duplicitni bublinu nebo preznacit -- jedna sada je pro filtrovani dle stavu (Vygenerovano/Odeslano/Zaplaceno), druha muze byt pro typ. Pokud obe maji stejnou funkci, sloucit.
- **Kde v kodu:** `app/templates/payments/settlement.html`
- **Narocnost:** nizka ~15 min
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** 🔧 jen opravit
- **Jak otestovat:** Otevrit `/platby/vyuctovani` -> nesmeni byt dve "Vse" bubliny vedle sebe

#### Nalez #18: Vyuctovani detail -- polozky "SluTy" a "Provozni" kategorie
- **Severity:** DROBNE
- **Pohled:** Bezny uzivatel
- **Co a kde:** Na detailu vyuctovani jednotky 1 jsou kategorie polozek zkracene: "SluTy" (sluzby/typ?), "Provozni", "Fond sprav". Nektere zkratky nemuseji byt srozumitelne.
- **Dopad:** Uzivatel musi hadat co znamena "SluTy".
- **Reseni:** Zobrazit plne nazvy kategorii nebo pridat tooltip s plnym nazvem.
- **Kde v kodu:** `app/templates/payments/settlement_detail.html`
- **Narocnost:** nizka ~10 min
- **Zavislosti:** Zavisi na tom, jak jsou kategorie definovany v predpisech/ciselniku
- **Regrese riziko:** nizke
- **Rozhodnuti:** ❓ potreba rozhodnuti uzivatele (zda zkratky jsou zamerne)
- **Jak otestovat:** Otevrit `/platby/vyuctovani/1` -> kategorie musi byt srozumitelne

---

### Platby -- Symboly (/platby/symboly)

#### Nalez #19: VS s otaznikem na konci
- **Severity:** DULEZITE
- **Pohled:** Data quality
- **Co a kde:** V tabulce variabilnich symbolu existuji zaznamy jako "0101102020?" (s otaznikem). To signalizuje nejisty/neovereny symbol.
- **Dopad:** System muze selhat pri parovani plateb, pokud pouziva VS s otaznikem pro porovnavani.
- **Reseni:** (1) Zvyraznit otazniky cervene. (2) Pridat moznost snadno opravit -- inline edit nebo filtrovaci bublina "Neoverene".
- **Kde v kodu:** `app/templates/payments/symboly.html`
- **Narocnost:** nizka ~15 min
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** 🔧 jen opravit
- **Jak otestovat:** Otevrit `/platby/symboly` -> symboly s "?" musi byt vizualne odlisene

---

### Hlasovani (/hlasovani)

#### Nalez #20: Dva hlasovani se stejnym nazvem
- **Severity:** DULEZITE
- **Pohled:** Bezny uzivatel
- **Co a kde:** Na strance hlasovani jsou dve session se STEJNYM nazvem "ROZHODOVANI PER ROLLAM VYHLASENE 19. LEDNA 2026", obe uzavrene, se stejnymi daty (od/do), ale s ruznym poctem listku (190/395 vs 145/309) a rezimem (Kazdy svuj listek vs Spolecny listek).
- **Dopad:** Uzivatel nerozlisni ktere hlasovani je ktere. Matouci.
- **Reseni:** (1) Pridat vizualni rozlisovac -- napr. cislo session, nebo zobrazit rezim prominentne v titulku. (2) Doporucit uzivateli prejmenovat session.
- **Kde v kodu:** `app/templates/voting/index.html`
- **Narocnost:** nizka ~10 min
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** 🔧 jen opravit (pridat cislo/rozlisovac)
- **Jak otestovat:** Otevrit `/hlasovani` -> kazda session musi byt jednoznacne rozlisitelna

---

### Hromadne rozesilani (/dane)

#### Nalez #21: URL "/dane" vede na "Hromadne rozesilani"
- **Severity:** KRITICKE
- **Pohled:** Bezny uzivatel, Performance analytik
- **Co a kde:** URL `/dane` (ktere by clovek ocekaval pro danovy modul) ve skutecnosti zobrazuje "Hromadne rozesilani". V sidebaru je polozka "Hromadne rozesilani" s odlisnou URL. Dochazi k mateni.
- **Dopad:** Uzivatel hledajici danovy modul skoci na spatnou stranku. Navigace je matouci.
- **Reseni:** Overit: pokud `/dane` je skutecne pro rozesilani (historicky nazev), pridat presmerovani a sjednotit. Pokud "dane" je samostatny modul (danove dokumenty), zajistit ze ma vlastni URL.
- **Kde v kodu:** `app/routers/` -- routing konfigurace
- **Narocnost:** nizka ~15 min
- **Zavislosti:** --
- **Regrese riziko:** stredni (zmena URL muze rozbít bookmarky)
- **Rozhodnuti:** ❓ potreba rozhodnuti uzivatele
- **Jak otestovat:** Otevrit `/dane` -> stranka musi jasne odpovidat svemu ucelu

#### Nalez #22: Rozesilani -- progress bar "Potvrzeno 0 / 572" na rozpracovanych
- **Severity:** DROBNE
- **Pohled:** Bezny uzivatel
- **Co a kde:** U rozpracovanych rozesilacich session se zobrazuje "Potvrzeno 0 / 572" s prazdnym progress barem. Uzivatel nemuze rozlisit zda se session teprve pripravuje nebo zda neco selhalo.
- **Dopad:** Nizky -- uzivatel muze kliknout na session pro detail.
- **Reseni:** Pridat textovy popisek stavu: "Ceka na potvrzeni" nebo "Rozpracovano -- pokracujte kliknutim".
- **Kde v kodu:** `app/templates/tax/index.html`
- **Narocnost:** nizka ~5 min
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** 🔧 jen opravit
- **Jak otestovat:** Otevrit `/dane` -> rozpracovane session musi mit popisek stavu

---

### Kontroly (/synchronizace)

#### Nalez #23: Nazev souboru orezany "Spoluvlastnicke podily..."
- **Severity:** DROBNE
- **Pohled:** Bezny uzivatel
- **Co a kde:** V historii kontrol podilu je nazev souboru orezany s "..." na konci. Uzivatel nevidi plny nazev.
- **Dopad:** Nizky -- uzivatel muze kliknout pro detail.
- **Reseni:** Pridat `title` atribut s plnym nazvem souboru pro tooltip pri najeti mysi.
- **Kde v kodu:** `app/templates/sync/share_check.html`
- **Narocnost:** nizka ~5 min
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** 🔧 jen opravit
- **Jak otestovat:** Najet mysi na orezany nazev -> tooltip zobrazi plny nazev

---

### Nastaveni (/nastaveni)

#### Nalez #24: SMTP hesla zobrazena jako hvezdicky bez moznosti zobrazeni
- **Severity:** DROBNE
- **Pohled:** Bezny uzivatel
- **Co a kde:** V kartach SMTP profilu jsou hesla zobrazena jako "•••••••". Uzivatel nemuze overit spravnost hesla bez otevreni editacniho formulare.
- **Dopad:** Pri ladeni problemu s odesilanim emailu uzivatel musi otevrit editaci kazdeho profilu.
- **Reseni:** Pridat "oko" ikonu pro zobrazeni/skryti hesla v read-only rezimu. Pozor: bezpecnostni riziko -- viz AUDIT nalez #3 (base64 ulozeni).
- **Kde v kodu:** `app/templates/settings.html`
- **Narocnost:** nizka ~15 min
- **Zavislosti:** AUDIT nalez #3 (sifrovani hesel)
- **Regrese riziko:** stredni (bezpecnostni implikace)
- **Rozhodnuti:** ❓ potreba rozhodnuti uzivatele
- **Jak otestovat:** Na strance `/nastaveni` -> kliknout na oko u hesla -> heslo se zobrazi

---

### Administrace (/sprava)

#### Nalez #25: "1 skupin duplicit" -- matouci text
- **Severity:** DROBNE
- **Pohled:** Bezny uzivatel
- **Co a kde:** Na kartach administrace se zobrazuje "1 skupin duplicit" -- gramaticky nejednotne (mel by byt "1 skupina duplicit").
- **Dopad:** Nizky -- kosmeticky problem.
- **Reseni:** Pridat skloneni: 1 skupina, 2-4 skupiny, 5+ skupin.
- **Kde v kodu:** `app/templates/administration/index.html`
- **Narocnost:** nizka ~5 min
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** 🔧 jen opravit
- **Jak otestovat:** Otevrit `/sprava` -> text musi byt gramaticky spravny

---

### Cele-aplikacni nalezy

#### Nalez #26: Badge "94" u Platby v sidebaru -- chybi vysvetleni
- **Severity:** KRITICKE
- **Pohled:** Bezny uzivatel
- **Co a kde:** V sidebaru u polozky "Platby" je cerveny badge s cislem 94. Uzivatel nevi co cislo znamena -- pocet dluzniku? Nespracovanych plateb? Nesrovnalosti?
- **Dopad:** Uzivatel je znepokojen cervenym badgem, ale nevi co s nim delat.
- **Reseni:** Pridat tooltip na badge: "94 jednotek s dluhem" (nebo cokoliv badge reprezentuje). Zvazit zmenu barvy -- cervena naznacuje urgentni problem.
- **Kde v kodu:** `app/templates/base.html`
- **Narocnost:** nizka ~10 min
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** 🔧 jen opravit
- **Jak otestovat:** Najet mysi na badge 94 u Platby -> tooltip musi vysvetlit vyznam

#### Nalez #27: Navigacni karty v platebnim modulu -- vizualni nesourodost
- **Severity:** DULEZITE
- **Pohled:** UI/UX designer
- **Co a kde:** V platebnim modulu je horni navigace realizovana 7 kartami (Predpisy, Symboly, Vypisy, Matice, Dluznici, Vyuctovani, Zustatky). Tyto karty jsou vizualne odlisne od navigace v jinych modulech (kde se pouzivaji bubliny).
- **Dopad:** Nekonzistentni navigacni vzor -- v jednom modulu karty, v jinem bubliny, v jinych nic.
- **Reseni:** Sjednotit navigaci -- v ramci platebniho modulu jsou karty spravne (7 sub-modulu je prilis pro bubliny). Ale zajistit konzistentni vizualni styl karet.
- **Kde v kodu:** `app/templates/payments/` -- kazda sablona ma vlastni navigacni karty
- **Narocnost:** stredni ~30 min
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** Informativni -- soucasny stav je funkcni, karty jsou vhodne pro 7 sub-modulu

#### Nalez #28: Dark mode / Light mode nekonzistence
- **Severity:** KRITICKE
- **Pohled:** UI/UX designer
- **Co a kde:** Behem testovani se aplikace stridave zobrazovala v dark mode a light mode. Dashboard a evidence moduly byly v dark mode, ale Kontroly a Nastaveni se zobrazily v light mode. Prepinac v sidebaru ("Svetly rezim" / "Tmavy rezim") funguje, ale stav neni konzistentni pri prechodu mezi strankami.
- **Dopad:** Vizualni skok pri navigaci -- uzivatel je oslnen prechodem z tmave na svetlou.
- **Reseni:** Overit ze dark mode preference je ulozena v localStorage a aplikovana pred renderovanim stranky (ne az po HTMX boost swapnuti). Typicky problem s HTMX boost -- `<html class="dark">` se muze ztratit pri swap.
- **Kde v kodu:** `app/static/js/app.js`, `app/templates/base.html`
- **Narocnost:** stredni ~30 min
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** 🔧 jen opravit
- **Jak otestovat:** Zapnout dark mode -> navigovat 5+ ruznych stranek -> vsechny musi byt v dark mode

#### Nalez #29: Chybi breadcrumb navigace
- **Severity:** DULEZITE
- **Pohled:** Bezny uzivatel, Performance analytik
- **Co a kde:** Aplikace pouziva "sipku zpet" na detailovych strankach, ale chybi breadcrumb pro orientaci v hierarchii. Napr. na detailu vyuctovani jednotky 1 je jen "Zpet na vyuctovani" -- uzivatel nevedi ze je v Platby > Vyuctovani > Jednotka 1.
- **Dopad:** Uzivatel se v hluboko vnorenych strankach (detail predpisu, detail vyuctovani, detail vypisu) muze ztratit.
- **Reseni:** (1) Pridat breadcrumb navigaci pod header: "Platby > Vyuctovani > Jednotka 1". (2) Alternativne -- zvyraznit aktivni polozku v sub-navigaci platebniho modulu.
- **Kde v kodu:** Vsechny detailove sablony
- **Narocnost:** stredni ~1 hod
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** ❓ potreba rozhodnuti uzivatele
- **Jak otestovat:** Otevrit detail vyuctovani -> videt breadcrumb "Platby > Vyuctovani > Jed. 1"

#### Nalez #30: HTMX boost zpusobuje vizualni glitche pri navigaci
- **Severity:** KRITICKE
- **Pohled:** Performance analytik, Error recovery
- **Co a kde:** Pri rychle navigaci (klikani na sidebar polozky) se obcas zobrazi obsah predchozi stranky s titulkem nove stranky. Playwright zachytil tento stav opakovane -- page title se zmeni, ale body zustane stary.
- **Dopad:** Uzivatel vidi spatna data -- muze se dostat do stavu kde si mysli ze je na jine strance nez ve skutecnosti je.
- **Reseni:** (1) Overit `hx-boost` konfiguraci -- zda je `hx-swap` nastaven spravne. (2) Pridat loading indikator pri navigaci. (3) Zvazit `hx-push-url` konzistenci.
- **Kde v kodu:** `app/templates/base.html` -- `hx-boost="true"`, `app/static/js/app.js`
- **Narocnost:** stredni ~1 hod
- **Zavislosti:** Souvisi s nalez #28 (dark mode)
- **Regrese riziko:** stredni
- **Rozhodnuti:** 🔧 jen opravit
- **Jak otestovat:** Rychle klikat na sidebar polozky -> obsah stranky musi vzdy odpovedat titulku

#### Nalez #31: Chybejici prazdne stavy (empty states) u nekterych modulu
- **Severity:** DULEZITE
- **Pohled:** UI/UX designer, Bezny uzivatel
- **Co a kde:** Nektere stranky nemaji vizualni prazdny stav kdyz neexistuji zadna data. Napr. predpisy plateb zobrazuji jen jednu radku; pokud by nebyly zadne predpisy, stranka by byla uplne prazdna.
- **Dopad:** Uzivatel nevedi zda se stranka nacetla spravne nebo zda opravdu nejsou data.
- **Reseni:** Pridat empty state messaging: "Zatim nebyly importovany zadne predpisy. [Importovat z DOCX]" s ilustraci.
- **Kde v kodu:** Vsechny tabulkove sablony
- **Narocnost:** stredni ~1 hod (vsechny moduly)
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** ❓ potreba rozhodnuti uzivatele
- **Jak otestovat:** Smazat data v testovacim prostredi -> kazda stranka musi mit smysluplny prazdny stav

#### Nalez #32: Tailwind CDN warning na kazde strance
- **Severity:** DULEZITE
- **Pohled:** Performance analytik
- **Co a kde:** Konzole prohlizece hlasi "cdn.tailwindcss.com should not be used in production" pri kazdem nacteni stranky. Kazda navigace generuje novy warning.
- **Dopad:** (1) Prodluction build Tailwindu by vyrazne snizil velikost CSS (z ~300 KB na ~10-30 KB). (2) CDN zavislost -- bez internetu se styl nenacte.
- **Reseni:** Nahradit CDN prodluction buildem Tailwindu (CLI nebo PostCSS). Pro offline pouziti (USB deployment) je to dulezite.
- **Kde v kodu:** `app/templates/base.html` -- `<script src="https://cdn.tailwindcss.com">`
- **Narocnost:** stredni ~1 hod
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** ❓ potreba rozhodnuti uzivatele (CDN je v CLAUDE.md definovano jako intentional choice)
- **Jak otestovat:** Otevrit konzoli prohlizece -> nesmeni byt Tailwind CDN warning

---

## Top 5 doporuceni (podle dopadu)

| # | Navrh | Dopad | Slozitost | Cas | Zavisi na | Rozhodnuti | Priorita |
|---|-------|-------|-----------|-----|-----------|------------|----------|
| 1 | **#30** Opravit HTMX boost vizualni glitche | Vysoky | Stredni | ~1 hod | -- | 🔧 | HNED |
| 2 | **#28** Dark mode konzistence pri navigaci | Vysoky | Stredni | ~30 min | #30 | 🔧 | HNED |
| 3 | **#17** Odstranit duplicitni "Vse" bubliny ve vyuctovani | Vysoky | Nizka | ~15 min | -- | 🔧 | HNED |
| 4 | **#26** Tooltip na badge 94 v sidebaru | Vysoky | Nizka | ~10 min | -- | 🔧 | HNED |
| 5 | **#14** Klikaci badge "102 nesrovnalosti" na detailu vypisu | Vysoky | Nizka | ~15 min | -- | 🔧 | BRZY |

---

## Quick wins (nizka slozitost, okamzity efekt)

- [ ] #1 Odstranit "None" a "test" bubliny z dashboardu (~15 min)
- [ ] #3 Prejmenovat "Dluh" na "Saldo" ve vlastnicich/jednotkach (~10 min)
- [ ] #7 Udelat vsechna jmena najemcu klikaci (~10 min)
- [ ] #17 Odstranit duplicitni "Vse" bubliny (~15 min)
- [ ] #25 Opravit skloneni "1 skupin duplicit" (~5 min)
- [ ] #26 Pridat tooltip na badge 94 (~10 min)
- [ ] #6 Zvyraznit "???" ve sloupci VS u prostoru (~15 min)
- [ ] #19 Zvyraznit VS s otaznikem (~15 min)
- [ ] #22 Pridat popisek stavu k rozpracovanym rozsilkam (~5 min)
- [ ] #23 Pridat title tooltip na orezany nazev souboru (~5 min)

---

## Pozitivni nalazy

Aplikace ma radu silnych stranek ktere stoji za zminku:

1. **Konzistentni tabulkovy vzor** -- vsechny evidence moduly (vlastnici, jednotky, prostory, najemci) pouzivaji shodny layout: bubliny, search, sortable sloupce, export.
2. **Inline editace v detailu vlastnika** -- 4-sloupcovy grid s HTMX editaci je elegantni a rychle.
3. **Matice plateb** -- vizualne jasna s barevnym kodovanim stavu plateb.
4. **Wizard stepper v rozesilani** -- jasne ukazuje kde v procesu uzivatel je.
5. **Stat karty na dashboardu** -- kompaktni prehled celeho SVJ na jedne strance.
6. **Barevne bubliny pro filtrovani** -- rychle a intuitivni filtrovani v tabulkach.
7. **HTMX search s debounce** -- okamzite vysledky bez obnovy cele stranky.
