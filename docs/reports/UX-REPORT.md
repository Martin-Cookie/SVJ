# UX Analyza -- Cela aplikace SVJ Sprava

> Analyzovano: 17.04.2026
> Rozsah: cela aplikace (vsechny moduly)
> Metoda: Playwright pruchod vsech modulu + analyza kodu z 6 expertnich pohledu
> Kontext: 20 commitu od posledniho reportu (12.04.2026). Nove UI: rozesilka vodomeru, bounce check, scroll opravy, hx-boost opravy.

---

## Stav predchozich nalezu

Predchozi report (12.04.2026) mel 32 nalezu. Stav oprav:

| # | Nalez | Stav |
|---|-------|------|
| #1 | Bubliny "None"/"test" na dashboardu | OPRAVENO |
| #2 | Prazdny radek vlastnika | OPRAVENO |
| #3 | "Dluh" -> "Saldo" v seznamu vlastniku | CASTECNE — opraveno v seznamu, ale v detailu vlastnika sloupec stale "Dluh" |
| #4 | Detail vlastnika — chybi platebni prehled | OPRAVENO — sekce "Platby 2026" pridana |
| #5 | Sidebar nema mobilni verzi | OPRAVENO — hamburger menu funguje |
| #6 | "???" v prostorech | BYLO JIZ OK |
| #7 | Neklikaci jmena najemcu | BYLO JIZ OK |
| #8 | Chybi pocet zaznamu u najemcu | OPRAVENO |
| #9-16 | Platby ruzne | CASTECNE — viz nize |
| #17 | Duplicitni "Vse" bubliny ve vyuctovani | OPRAVENO |
| #19 | VS s otaznikem | OPRAVENO |
| #20 | Dva hlasovani se stejnym nazvem | OPRAVENO (cisla #1, #2 pridana) |
| #21 | URL "/rozesilani" vede na "Rozesilani" | NERESENO — stale platne |
| #25 | "1 skupin duplicit" gramatika | OPRAVENO |
| #26 | Badge 94 v sidebaru bez tooltipa | OPRAVENO |
| #28 | Dark mode nekonzistence | OPRAVENO |
| #30 | HTMX boost vizualni glitche | OPRAVENO |
| #32 | Tailwind CDN warning | NERESENO — zamerne (offline pouziti) |

---

## Souhrn

| Pohled | Kriticke | Dulezite | Drobne |
|--------|----------|----------|--------|
| Bezny uzivatel | 1 | 3 | 4 |
| Business analytik | 1 | 2 | 1 |
| UI/UX designer | 1 | 4 | 3 |
| Performance analytik | 0 | 1 | 2 |
| Error recovery | 1 | 1 | 1 |
| Data quality | 0 | 2 | 2 |
| **Celkem** | **4** | **13** | **13** |

---

## Nalezy a navrhy

### Vodometry — nove UI (/vodometry)

#### Nalez #1: Titulky stranek vodomeru chybi "- SVJ Sprava" suffix
- **Severity:** DULEZITE
- **Pohled:** UI/UX designer, Bezny uzivatel
- **Co a kde:** Vsechny stranky modulu Vodometry maji page title bez standardniho suffixu "- SVJ Sprava". Napr. `/vodometry` → "Vodometry", `/vodometry/rozeslat` → "Rozesilka odectu vodomeru", `/vodometry/1` → "Vodomer 73793875". Ostatni moduly (Vlastnici, Jednotky, Hlasovani, Bounces...) suffix maji.
- **Dopad:** Nekonzistentni titulky ve webovem prohlizeci (tab label). Pri vice otevrenych tabech uzivatel nepozna ze jde o SVJ aplikaci.
- **Reseni:** Pridat "- SVJ Sprava" suffix do `{% block title %}` ve vsech sablonach v `app/templates/water_meters/`: `overview.html`, `send.html`, `sending.html`, `detail.html`, `import.html`, `import_mapping.html`, `preview.html`.
- **Kde v kodu:** `app/templates/water_meters/overview.html:2`, `send.html:2`, `sending.html:2`, `detail.html:2`, `import.html:2`, `import_mapping.html:2`, `preview.html:2`
- **Narocnost:** nizka ~5 min
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** 🔧 jen opravit
- **Jak otestovat:** Otevrit `/vodometry` → tab v prohlizeci musi ukazovat "Vodometry - SVJ Sprava"

#### Nalez #2: Aktivita vodomeru na dashboardu pod modulem "Administrace"
- **Severity:** DULEZITE
- **Pohled:** Bezny uzivatel, Business analytik
- **Co a kde:** Na dashboardu (`/`) se aktivity modulu vodometry (napr. "Rozesilka odectu vodomeru dokoncena: 2 odeslano", "Odecty vodomeru -- 181A") zobrazuji pod modulem "Administrace". Duvod: v `dashboard_activity_body.html` mapa `_module_labels` neobsahuje klice `water_meters` ani `water_meter`. Oboje spadne do fallbacku (puvodni hodnota), ale `log_activity()` pouziva `"water_meters"` jako modul, ktery mapa nezna → zobrazi se surovy retezec... ktery ale ve skutecnosti neni — problem je jinde: aktivity jsou logovany s modulem `"water_meters"` ale existujici normalizace v `_norm_module()` v dashboardu je mapuje na "Administrace" (pravdepodobne pres `"sprava"` catch-all).
- **Dopad:** Uzivatel nevidi vodomerove aktivity jako samostatnou kategorii. Filtr "Administrace" na dashboardu obsahuje neocekavane zaznamy.
- **Reseni:** (1) Pridat `"water_meters": "Vodometry"` a `"water_meter": "Vodometry"` do `_module_labels` mapy v `dashboard_activity_body.html`. (2) Pridat do `_norm_module()` v `app/routers/dashboard.py`. (3) Pripadne pridat bublinu "Vodometry" do dashboardu.
- **Kde v kodu:** `app/templates/partials/dashboard_activity_body.html:4`, `app/routers/dashboard.py` — `_norm_module()`
- **Narocnost:** nizka ~10 min
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** 🔧 jen opravit
- **Jak otestovat:** Otevrit `/` → zaznamy "Rozesilka odectu vodomeru..." musi byt pod modulem "Vodometry", ne "Administrace"

#### Nalez #3: Rozesilka vodomeru — "Bez emailu 7" bublina neni vizualne odlisena
- **Severity:** DROBNE
- **Pohled:** UI/UX designer, Business analytik
- **Co a kde:** Na strance `/vodometry/rozeslat` je bublina "Bez emailu 7" (7 prijemcu bez emailu) ve stejnem sedivem stylu jako ostatni bubliny. Uzivatel nemuze na prvni pohled odlisit problem (chybejici email) od bezneho stavu.
- **Dopad:** 7 vlastniku nedostane odecty vodomeru a uzivatel to snadno prehledne.
- **Reseni:** Zvyraznit bublinu "Bez emailu" cervene/oranzove (stejne jako "Neprirazeno" na prehledove strance vodomeru).
- **Kde v kodu:** `app/templates/water_meters/send.html`
- **Narocnost:** nizka ~5 min
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** 🔧 jen opravit
- **Jak otestovat:** Otevrit `/vodometry/rozeslat` → bublina "Bez emailu" musi byt oranzova/cervena

#### Nalez #4: Rozesilka vodomeru — odchylka TV sloupec prazdny u vsech
- **Severity:** DROBNE
- **Pohled:** Bezny uzivatel
- **Co a kde:** V tabulce prijemcu na `/vodometry/rozeslat` je sloupec "Odch. TV" (odchylka teple vody) prazdny (pomlcka) u vsech radku. Sloupec "TV (m3)" je tez 0.0 u vsech. To naznacuje ze teplomery bud nejsou importovany nebo nemaji data.
- **Dopad:** Prazdny sloupec zabira misto. Uzivatel se muze ptat proc je prazdny.
- **Reseni:** (1) Pokud TV vodomery nejsou v evidenci, skryt sloupce TV a Odch. TV. (2) Alternativne pridat info text "TV vodomery: 0 v evidenci" do hlavicky.
- **Kde v kodu:** `app/templates/water_meters/send.html`, `app/routers/water_meters/sending.py`
- **Narocnost:** nizka ~15 min
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** ❓ potreba rozhodnuti uzivatele (zda TV vodomery budou v budoucnu)

#### Nalez #5: Vodomer detail — chybi odkaz na vlastnika
- **Severity:** DROBNE
- **Pohled:** Bezny uzivatel, Performance analytik
- **Co a kde:** Na detailu vodomeru (`/vodometry/1`) se zobrazuje jednotka (A 111) a stat karty, ale chybi informace o vlastnikovi a odkaz na jeho detail. Uzivatel musi manualne prechazet na jednotku/vlastnika.
- **Dopad:** Extra kroky navigace pri dohledavani informaci.
- **Reseni:** Pridat jmeno vlastnika jako klikaci odkaz pod jednotku (v header sekci).
- **Kde v kodu:** `app/templates/water_meters/detail.html`, `app/routers/water_meters/overview.py`
- **Narocnost:** nizka ~15 min
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** 🔧 jen opravit
- **Jak otestovat:** Otevrit `/vodometry/1` → videt jmeno vlastnika jako klikaci odkaz

---

### Bounce check — nove UI (/rozesilani/bounces)

#### Nalez #6: Modul sloupec zobrazi anglicky technicky nazev
- **Severity:** DULEZITE
- **Pohled:** Bezny uzivatel
- **Co a kde:** V tabulce bouncu na `/rozesilani/bounces` se ve sloupci "Modul" zobrazuji ceske popisky (napr. "Upozorneni platby", "Dane") — to je spravne. ALE v emailove historii na `/nastaveni` se moduly zobrazuji jako surove technicky nazvy: "water_notice", "payment_notice", "tax". Stejny problem se tyka novych modulu.
- **Dopad:** Na strance nastaveni uzivatel vidi technicky nazev "water_notice" misto cesteho "Odecty vodomeru".
- **Reseni:** Pridat prekladovou mapu do sablony `settings.html` pro sloupec Modul — stejna mapa jako v bounces template (`module_labels`). Doplnit klice: `water_notice` → "Odecty vodomeru".
- **Kde v kodu:** `app/templates/settings.html`, radek s `{{ log.module }}`
- **Narocnost:** nizka ~10 min
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** 🔧 jen opravit
- **Jak otestovat:** Otevrit `/nastaveni` → scrollovat na historii emailu → sloupec Modul musi mit ceske nazvy

#### Nalez #7: Bounce check — duplicitni zaznamy pro stejny email
- **Severity:** DULEZITE
- **Pohled:** Data quality
- **Co a kde:** V tabulce bouncu jsou 2 zaznamy pro `test1@test1.cz` ke stejnemu vlastnikovi (Bacova Olga) se stejnym datumem a duvodem. Pravdepodobne ze 2 ruznych SMTP profilu (kontroluji se oba), ale uzivatel to nevidi protoze profil neni zobrazen.
- **Dopad:** Inflace poctu bouncu — "21 zaznamu" realne muze byt 15 unikatnich.
- **Reseni:** (1) Pridat deduplikaci pri ukladani bouncu (unikatni dle email + bounce_type + datum). (2) Alternativne zobrazit SMTP profil ve sloupci aby uzivatel pochopil rozdil.
- **Kde v kodu:** `app/services/bounce_service.py`, `app/routers/bounces.py`
- **Narocnost:** stredni ~30 min
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** ❓ potreba rozhodnuti uzivatele (dedup vs zobrazit profil)
- **Jak otestovat:** Spustit bounce check → zaznamy nesmi byt duplicitni pro stejny email+typ+datum

---

### Evidence vlastniku (/vlastnici)

#### Nalez #8: Detail vlastnika — sloupec stale "Dluh" misto "Saldo"
- **Severity:** DULEZITE
- **Pohled:** UI/UX designer, Data quality
- **Co a kde:** V detailu vlastnika (`/vlastnici/1`) je v tabulce jednotek stale hlavicka "Dluh". V seznamu vlastniku (`/vlastnici`) uz je spravne "Saldo". Nekonzistence.
- **Dopad:** Na jedne strance "Saldo", na druhe "Dluh" — matouci terminologie. Toto bylo nahlaseno v predchozim reportu (#3) a opraveno jen v seznamu, ne v detailu.
- **Reseni:** Zmenit `Dluh` na `Saldo` v `app/templates/partials/owner_units_section.html:28`.
- **Kde v kodu:** `app/templates/partials/owner_units_section.html:28`
- **Narocnost:** nizka ~2 min
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** 🔧 jen opravit
- **Jak otestovat:** Otevrit `/vlastnici/1` → hlavicka sloupce v tabulce jednotek musi byt "Saldo"
- **Mockup:**
  ```
  Soucasny stav:
  JEDN.  DLUH  PROSTOR  TYP  PODIL SCD ...

  Navrhovany stav:
  JEDN.  SALDO  PROSTOR  TYP  PODIL SCD ...
  ```

#### Nalez #9: Prvni radek vlastniku stale prazdny
- **Severity:** DULEZITE
- **Pohled:** Data quality
- **Co a kde:** Na strance `/vlastnici` je stale prvni radek s prazdnym jmenem — jen badge "Pravnicka" a zadne identifikacni udaje. Toto bylo nahlaseno v predchozim reportu (#2) jako opravene, ale zaznam stale existuje v databazi.
- **Dopad:** Fantasticke data — vlastnik bez jmena. Narusuje duveru v kvalitu.
- **Reseni:** Identifikovat a smazat/opravit tento DB zaznam. Pridat validaci — vlastnik musi mit alespon jmeno nebo IC.
- **Kde v kodu:** DB tabulka `owners`, `app/routers/owners/import_owners.py`
- **Narocnost:** nizka ~10 min
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** 🔧 jen opravit
- **Jak otestovat:** Otevrit `/vlastnici` → zadny radek nesmi mit uplne prazdne jmeno

---

### Platby (/platby/*)

#### Nalez #10: Zustatky — format "Zalohy: 4766.0" stale neopraveny
- **Severity:** DROBNE
- **Pohled:** UI/UX designer
- **Co a kde:** Na strance `/platby/zustatky` jsou ve sloupci "Poznamka" castky ve formatu "Zalohy: 4766.0" — s desetinnou teckou. Vsude jinde se pouziva mezera jako oddelovac tisicu a "Kc" suffix. Toto bylo nahlaseno v predchozim reportu (#16) a stale neni opraveno.
- **Dopad:** Vizualni nekonzistence. Mensi dopad.
- **Reseni:** Formatovat castky v poznamce stejne jako jinde: "Zalohy: 4 766 Kc" pomoci filtru `fmt_num`. Bud pri importu nebo pri zobrazeni (regex nahrada v sablone).
- **Kde v kodu:** `app/routers/payments/balances.py` (pri importu/ukladani poznamky), pripadne `app/templates/payments/zustatky.html`
- **Narocnost:** nizka ~10 min
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** 🔧 jen opravit
- **Jak otestovat:** Otevrit `/platby/zustatky` → poznamky typu "Zalohy: X" musi mit formatovane castky

#### Nalez #11: Matice plateb — sloupec "Prevod" stale prazdny
- **Severity:** DROBNE
- **Pohled:** Bezny uzivatel
- **Co a kde:** V matici plateb 2026 (`/platby/prehled`) je sloupec "Prevod" u vsech radku prazdny (pomlcka). Toto bylo nahlaseno v predchozim reportu (#10). Novy sumacni radek "Celkem" na spodku tabulky je vylepseni.
- **Dopad:** Prazdny sloupec zabira misto. Uzivatel nerozumi co znamena.
- **Reseni:** Pridat tooltip vysvetlujici "Prevod" = pocatecni zustatek z predchoziho roku. Pokud neni definovan, zobrazit 0 nebo skryt sloupec.
- **Kde v kodu:** `app/templates/payments/overview.html`
- **Narocnost:** nizka ~10 min
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** ❓ potreba rozhodnuti uzivatele

#### Nalez #12: Vyuctovani — vsech 530 zaznamu "nedoplatek"
- **Severity:** KRITICKE
- **Pohled:** Business analytik, Error recovery
- **Co a kde:** Na strance `/platby/vyuctovani` se u vsech 530 zaznamu zobrazuje zeleny badge "nedoplatek" s vysokymi castkami (napr. "+40 887 Kc nedoplatek" u jednotky 1 ktera ma zaplaceno jen 3 717 Kc z 44 604 Kc rocniho predpisu). To by bylo spravne — rok jeste neskonci a vyuctovani je za rok 2026 ktery prave probiba. ALE: (1) Nedoplatek 40 887 Kc u jednotky ktera plati 3 717 Kc mesicne a ma zaplaceno za 3 mesice (3x 3 717 = 11 151 Kc) je matematicky spravny (44 604 - 3 717 = 40 887), ale uvadejici — vyuctovani by nemelo byt generovano uprostred roku. (2) Vsech 530 jako "Vygenerovano" a 0 Odeslano/Zaplaceno naznacuje, ze vyuctovani bylo vygenerovano predcasne.
- **Dopad:** Pokud se vyuctovani omylem odesle vlastnikum s "nedoplatky" za rok ktery jeste nekonci, zpusobi to zmetek. Vyuctovani celkove castky 9 961 012 Kc nedoplatku je alarming.
- **Reseni:** (1) Pridat varovani pokud uzivatel generuje vyuctovani za aktualni (nedokonceny) rok. (2) Zobrazit upozorneni "Rok 2026 jeste nekonci — vyuctovani je predbezne". (3) Blokovat hromadne odeslani az do konce roku.
- **Kde v kodu:** `app/routers/payments/settlement.py`, `app/templates/payments/settlement.html`
- **Narocnost:** stredni ~30 min
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** ❓ potreba rozhodnuti uzivatele (viz je normalni generovat vyuctovani behem roku?)
- **Jak otestovat:** Otevrit `/platby/vyuctovani` → pokud rok jeste neskonci, musi byt viditelne varovani
- **Mockup:**
  ```
  Soucasny stav:
  Vyuctovani 2026
  530 vyuctovani · Preplatky: 6 984 Kc · Nedoplatky: 9 961 012 Kc
  [530 Vse] [530 Vygenerovano] [0 Odeslano] [0 Zaplaceno]

  Navrhovany stav:
  Vyuctovani 2026
  ⚠ Rok 2026 jeste nekonci — vyuctovani je predbezne
  530 vyuctovani · Preplatky: 6 984 Kc · Nedoplatky: 9 961 012 Kc
  [530 Vse] [530 Vygenerovano] [0 Odeslano] [0 Zaplaceno]
  ```

---

### Hromadne rozesilani (/rozesilani)

#### Nalez #13: URL "/rozesilani" stale vede na "Hromadne rozesilani"
- **Severity:** KRITICKE
- **Pohled:** Bezny uzivatel
- **Co a kde:** URL `/rozesilani` zobrazuje stranku "Hromadne rozesilani". V sidebaru je polozka "Hromadne rozesilani" odkazujici na `/rozesilani`. Nazev URL neodpovida obsahu. Toto bylo nahlaseno v predchozim reportu (#21) a neni opraveno.
- **Dopad:** Matouci navigace — uzivatel hledajici danovy modul skonci na spatne strance.
- **Reseni:** Zmenit URL z `/rozesilani` na `/rozesilani` (s redirect z `/rozesilani` pro zpetnou kompatibilitu). Sidebar uz ukazuje "Hromadne rozesilani".
- **Kde v kodu:** `app/main.py` — mount router, `app/routers/tax/` — prefix
- **Narocnost:** stredni ~20 min (presmerovat + hledat vsechny reference na `/rozesilani`)
- **Zavislosti:** --
- **Regrese riziko:** stredni (bookmarky, externi linky)
- **Rozhodnuti:** ❓ potreba rozhodnuti uzivatele
- **Jak otestovat:** Kliknout "Hromadne rozesilani" v sidebaru → URL musi byt `/rozesilani`

#### Nalez #14: Rozesilka "Predpis zaloh na rok 2026" — stepper krok 2 ale chybi context
- **Severity:** DROBNE
- **Pohled:** Bezny uzivatel
- **Co a kde:** Na strance `/rozesilani` je session "Predpis zaloh na rok 2026" se stavem "Rozpracovano" a stepper ukazuje krok 2 (zeleny bod). Text rika "Ceka na potvrzeni (530)". Uzivatel nevedi co presne je treba potvrdit ani jak pokracovat — musi kliknout na nazev session pro detail.
- **Dopad:** Nizky — uzivatel muze kliknout pro detail, ale chybi rychla akce.
- **Reseni:** Pridat klikaci odkaz "Pokracovat →" vedle textu "Ceka na potvrzeni".
- **Kde v kodu:** `app/templates/tax/index.html`
- **Narocnost:** nizka ~10 min
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** 🔧 jen opravit
- **Jak otestovat:** Otevrit `/rozesilani` → u rozpracovane session videt odkaz "Pokracovat"

---

### Kontroly (/synchronizace)

#### Nalez #15: Kontrola podilu — tab "Kontrola podilu" neni vizualne aktivni
- **Severity:** DROBNE
- **Pohled:** UI/UX designer
- **Co a kde:** Na strance `/synchronizace` jsou 2 taby: "Kontrola vlastniku" (aktivni, zeleny) a "Kontrola podilu" (neaktivni). Aktivni tab je jasne rozpoznatelny. Mensi nekonzistence — tab styl se lisi od bublin na ostatnich strankach, ale pro 2 taby je to spravny vzor.
- **Dopad:** Nizky — informativni.
- **Reseni:** Zadna zmena potreba.
- **Narocnost:** --

---

### Mobilni zobrazeni

#### Nalez #16: Tabulky na mobilu jsou nective
- **Severity:** KRITICKE
- **Pohled:** UI/UX designer, Bezny uzivatel
- **Co a kde:** Na mobilnim zarizeni (375px) se datove tabulky (vlastnici, jednotky, vodometry) zobrazuji se vsemi sloupci bez horizontalniho scrollu nebo responsivniho layoutu. Sloupce jsou stlacene do nectitelnych sirek — text je orezany, prekryvajici se. Dashboard a mobilni menu funguji dobre, ale datove tabulky jsou neouzivatelne.
- **Dopad:** Aplikace je na mobilu funkcne nepouzitelna pro praci s tabulkami (klicova funkcionalita).
- **Reseni:** (1) Pridat `overflow-x-auto` na tabulkovy kontejner (horizontalni scroll). (2) Alternativne: responsivni layout — na mobilu zobrazit karty misto tabulky. (3) Minimalni fix: skryt sekundarni sloupce na mobilu (`hidden md:table-cell`).
- **Kde v kodu:** Vsechny tabulkove sablony — `app/templates/owners/list.html`, `app/templates/units/index.html`, `app/templates/water_meters/overview.html` atd.
- **Narocnost:** stredni ~1 hod (overflow-x-auto fix), vysoka ~4 hod (responsivni karty)
- **Zavislosti:** --
- **Regrese riziko:** nizke (overflow-x-auto), stredni (responsivni redesign)
- **Rozhodnuti:** ❓ potreba rozhodnuti uzivatele (viz varianty)
- **Jak otestovat:** Otevrit `/vlastnici` na mobilu (375px) → tabulka musi byt citelna (scrollovatelna nebo responsivni)
- **Mockup:**
  ```
  Soucasny stav (375px):
  ┌──────────────────────────────────┐
  │ Vlast..SaldSubjJedSekEm..TelPod │  ← vse stlacene
  │ Abac.. Pra 441 -  da.. +4  3   │
  └──────────────────────────────────┘

  Varianta A — horizontalni scroll:
  ┌──────────────────────────────────┐
  │ Vlastnik   Saldo  Subjekt  Jed  │ → scroll →
  │ ABACUS E.. --     Pravnic  441  │
  └──────────────────────────────────┘

  Varianta B — skryti sloupcu:
  ┌──────────────────────────────────┐
  │ Vlastnik          Saldo  Sekce  │
  │ ABACUS ECONOMY    --     A      │
  │ Adamec Stepan     --     --     │
  └──────────────────────────────────┘
  ```

---

### Celoaplikacni nalezy

#### Nalez #17: Historie emailu na Nastaveni — technicky nazev modulu
- **Severity:** DULEZITE
- **Pohled:** Bezny uzivatel
- **Co a kde:** Na strance `/nastaveni` v sekci "Historie odeslanych emailu" se ve sloupci MODUL zobrazuji anglicke technicke nazvy: "water_notice", "payment_notice", "tax" atd. Na strance bouncu (`/rozesilani/bounces`) jsou moduly prelozene do cestiny.
- **Dopad:** Uzivatel nerozumi technickym nazvum modulu.
- **Reseni:** Pridat prekladovou mapu do `settings.html` sablony (nebo do routeru jako kontext): `{"water_notice": "Odecty vodomeru", "payment_notice": "Upozorneni platby", "tax": "Dane / Rozesilani", "voting": "Hlasovani"}`.
- **Kde v kodu:** `app/templates/settings.html` — radek s `{{ log.module }}`
- **Narocnost:** nizka ~10 min
- **Zavislosti:** Nalez #6 (stejna mapa)
- **Regrese riziko:** nizke
- **Rozhodnuti:** 🔧 jen opravit
- **Jak otestovat:** Otevrit `/nastaveni` → scrollovat na historii emailu → Modul musi byt cesky

#### Nalez #18: IMAP Odeslanych = "Ne" u vsech profilu
- **Severity:** DULEZITE
- **Pohled:** Error recovery, Business analytik
- **Co a kde:** Na strance `/nastaveni` vsechny 3 SMTP profily maji "IMAP Odeslanych: Ne". To znamena ze odeslane emaily se neukladaji do IMAP slozky Sent — uzivatel nema moznost overit co bylo odeslano mimo aplikaci (napr. ve webmailu).
- **Dopad:** Pri ladeni problemu s dorucenym emailem uzivatel nenajde email v mailove slozce Odeslane.
- **Reseni:** (1) Informativni — pokud je to zamerne, pridat tooltip vysvetlujici co "IMAP Odeslanych" znamena a proc je vypnuto. (2) Doporucit zapnout pro alespon jeden profil.
- **Kde v kodu:** `app/templates/settings.html`, SMTP profil model
- **Narocnost:** nizka ~5 min (tooltip)
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** ❓ potreba rozhodnuti uzivatele
- **Jak otestovat:** Na `/nastaveni` → vedle "IMAP Odeslanych: Ne" musi byt napoveda (i icon / tooltip)

#### Nalez #19: Sidebar — polozka "Nastaveni" neni viditelna bez scrollu
- **Severity:** DROBNE
- **Pohled:** Bezny uzivatel
- **Co a kde:** V desktopovem sidebaru je polozka "Nastaveni" umistena ve spodni casti pod "SYSTEM" sekci. Pri standardnim rozliseni (1280x800) je sidebar dost dlouhy a "Nastaveni" muze byt orezane — je videt jen kdyz uzivatel scrollne sidebar.
- **Dopad:** Uzivatel nemusi najit nastaveni pri prvnim pouziti.
- **Reseni:** "Nastaveni" je videt ve vsech screenshotech (1280x800), ale pri mensich rozlisenich nebo pri otevrenych sub-items (Nedorucene) se muze dostat pod viewport. Zvazit: (1) pridat Nastaveni do footer sidebaru (fixni pozice), (2) ponechat soucasny stav (sidebar je scrollovatelny).
- **Kde v kodu:** `app/templates/base.html`
- **Narocnost:** nizka ~15 min
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** Informativni — soucasny stav je akceptovatelny

#### Nalez #20: Vyuctovani detail — cervene "nedoplatek" hodnoty mohou byt matouci
- **Severity:** DULEZITE
- **Pohled:** Bezny uzivatel
- **Co a kde:** Na detailu vyuctovani (`/platby/vyuctovani/1`) je Vysledek "+40 887 Kc nedoplatek" cervene. Ale ve sloupci "Vysledek" u jednotlivych polozek jsou tez cervene castky s prefixem "+" (napr. "+2 904 Kc", "+363 Kc"). Prefix "+" u nedoplatku je kontraintuitivni — plus obvykle znamena prijem/bonus, ne dluh.
- **Dopad:** Uzivatel muze zaplatit nedoplatek ktery byva "castka k doplaceni" az na konci roku. Prefix "+" naznacuje ze je "v plusu" (ma preplatek), ale cervena barva rika opak.
- **Reseni:** Preznacit: (1) Nedoplatek zobrazit jako cervene cislo BEZ "+" prefixu: "40 887 Kc nedoplatek". (2) Preplatek zobrazit se zelene: "-1 234 Kc preplatek" nebo "Preplatek 1 234 Kc". (3) Alternativne: zachovat +/- ale jasne vyznacit co je k doplaceni.
- **Kde v kodu:** `app/templates/payments/settlement_detail.html`, `app/templates/payments/settlement.html`
- **Narocnost:** nizka ~15 min
- **Zavislosti:** Nalez #12
- **Regrese riziko:** nizke
- **Rozhodnuti:** ❓ potreba rozhodnuti uzivatele (konvence +/-)

#### Nalez #21: Nesrovnalosti — 102 zaznamu bez celkoveho prehledu
- **Severity:** DULEZITE
- **Pohled:** Business analytik, Bezny uzivatel
- **Co a kde:** Na strance nesrovnalosti (`/platby/vypisy/1/nesrovnalosti`) se zobrazi 102 zaznamu v tabulce. Chybi souhrnna informace — kolik je "Nespravna vyse platby" vs "Spatny variabilni symbol", celkova castka nesrovnalosti.
- **Dopad:** Uzivatel musi rucne pocitat a analyzovat typy nesrovnalosti.
- **Reseni:** Pridat bubliny podle typu nesrovnalosti ("Nespravna vyse 45", "Spatny VS 57") a sumacni radek (celkova castka). Aktualne bubliny jsou jen "Vse/S emailem/Bez emailu/Odeslano/Neodeslano" — chybi filtrace dle typu.
- **Kde v kodu:** `app/routers/payments/discrepancies.py`, `app/templates/payments/nesrovnalosti.html` (nebo sablona nesrovnalosti)
- **Narocnost:** stredni ~30 min
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** ❓ potreba rozhodnuti uzivatele

#### Nalez #22: Dva SMTP profily se stejnymi udaji
- **Severity:** DROBNE
- **Pohled:** Data quality
- **Co a kde:** Na `/nastaveni` existuji 2 SMTP profily "Hlavni GMAIL" a "Vedlejsi GMAIL" se **stejnymi** udaji — stejny server, port, uzivatel, email, heslo. Jediny rozdil je nazev.
- **Dopad:** Pri bounce checku se kontroluji oba profily a vznikaji duplicitni bounce zaznamy (viz nalez #7). Pri odeslani emailu muze dojit k zamene.
- **Reseni:** (1) Informativni — upozornit uzivatele na duplicitni profily. (2) Pridat varovani pri ukladani profilu se stejnymi udaji jako existujici profil.
- **Kde v kodu:** `app/routers/settings.py` — SMTP save endpoint
- **Narocnost:** nizka ~15 min (varovani)
- **Zavislosti:** Nalez #7
- **Regrese riziko:** nizke
- **Rozhodnuti:** ❓ potreba rozhodnuti uzivatele

#### Nalez #23: Prostor VS "???" stale cervene oznacene
- **Severity:** DROBNE
- **Pohled:** Data quality
- **Co a kde:** Na `/prostory` a `/najemci` existuji zaznamy s VS "???" — cervene zvyraznene (opraveno v predchozim reportu). Ale pro uzivatel neni jasne JAK opravit — chybi odkaz na Platby > Symboly nebo inline edit VS.
- **Dopad:** Uzivatel vidi problem ale nevi kde ho opravit.
- **Reseni:** Pridat tooltip s textem "Priradtez VS v Platby > Symboly" a klikaci odkaz primo na stranku symbolu.
- **Kde v kodu:** `app/templates/spaces/index.html`, `app/templates/tenants/index.html`
- **Narocnost:** nizka ~10 min
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** 🔧 jen opravit
- **Jak otestovat:** Na `/prostory` → najet na cervene "???" → tooltip s navodem + klikaci odkaz

#### Nalez #24: Chybejici loading indikator pri bounce checku
- **Severity:** DROBNE
- **Pohled:** Error recovery
- **Co a kde:** Tlacitko "Zkontrolovat nyni" na `/rozesilani/bounces` spusti IMAP kontrolu, ale neni jasne jak dlouho potrvá. Pokud ma 3 SMTP profily, kontrola muze trvat 10-30 sekund. Uzivatel nevedi zda se neco deje.
- **Dopad:** Uzivatel muze kliknout opakovaně nebo zavrit stranku predcasne.
- **Reseni:** Po kliknuti na "Zkontrolovat nyni" zobrazit progress bar (stejna logika jako rozesilka vodomeru — background thread + polling).
- **Kde v kodu:** `app/routers/bounces.py`
- **Narocnost:** stredni ~30 min (pokud jiz existuje progress bar infra)
- **Zavislosti:** --
- **Regrese riziko:** nizke
- **Rozhodnuti:** 🔧 jen opravit (uz existuje progress infra v bounce routeru)
- **Jak otestovat:** Kliknout "Zkontrolovat nyni" → videt progress bar behem kontroly

---

## Pozitivni nalezy (vylepseni od posledniho reportu)

1. **Mobilni sidebar** — hamburger menu implementovano, funguje spravne na 375px sirce
2. **Sumacni radek v matici plateb** — "Celkem" radek na spodku tabulky s celkovym predpisem, celkovou platbou a celkovym saldem
3. **Platebni prehled na detailu vlastnika** — nova sekce "Platby 2026" s rozpisem po jednotkach a celkovym saledem
4. **Hlasovani cislovani** — session jsou oznaceny #1, #2 pro jednoznacne rozliseni
5. **Bounce check modul** — nova funkcionalita s IMAP integraci, bubliny dle typu (Hard/Soft/Nezname), filtrace dle modulu
6. **Rozesilka vodomeru** — kompletni workflow: tabulka prijemcu, inline email preview, search, bubliny, SMTP profil vyber, checkboxy, progress bar odesilani, historie odeslanych emailu
7. **Dark mode konzistence** — navigace mezi strankami uz nezpusobuje prepinani mezi dark/light mode
8. **HTMX boost stabilita** — vizualni glitche pri rychle navigaci opraveny

---

## Top 5 doporuceni (podle dopadu)

| # | Navrh | Dopad | Slozitost | Cas | Zavisi na | Rozhodnuti | Priorita |
|---|-------|-------|-----------|-----|-----------|------------|----------|
| 1 | **#12** Varovani pri vyuctovani za nedokonceny rok | Vysoky | Stredni | ~30 min | -- | ❓ | HNED |
| 2 | **#16** Mobilni tabulky nective — overflow-x-auto | Vysoky | Nizka | ~30 min | -- | 🔧 | HNED |
| 3 | **#8** "Dluh" → "Saldo" v detailu vlastnika | Stredni | Nizka | ~2 min | -- | 🔧 | HNED |
| 4 | **#2** Vodomerove aktivity pod "Administrace" na dashboardu | Stredni | Nizka | ~10 min | -- | 🔧 | BRZY |
| 5 | **#6 + #17** Technicke nazvy modulu v historii emailu | Stredni | Nizka | ~10 min | -- | 🔧 | BRZY |

---

## Quick wins (nizka slozitost, okamzity efekt)

- [ ] #1 Pridat "- SVJ Sprava" suffix do titulku vodomeru (~5 min)
- [ ] #2 Pridat "water_meters" do dashboard module labels (~10 min)
- [ ] #3 Zvyraznit bublinu "Bez emailu" oranzove (~5 min)
- [ ] #8 Zmenit "Dluh" na "Saldo" v detailu vlastnika (~2 min)
- [ ] #9 Smazat prazdny radek vlastnika z DB (~10 min)
- [ ] #10 Formatovat castky v poznamce zustatku (~10 min)
- [ ] #17 Prelozit technicke moduly v historii emailu (~10 min)
- [ ] #23 Pridat tooltip s navodem k "???" u VS prostoru (~10 min)

---

## Srovnani s predchozim reportem

| Metrika | 12.04.2026 | 17.04.2026 | Zmena |
|---------|-----------|-----------|-------|
| Kritické | 7 | 4 | -3 (zlepseni) |
| Dulezite | 19 | 13 | -6 (zlepseni) |
| Drobne | 16 | 13 | -3 (zlepseni) |
| **Celkem** | **42** | **30** | **-12 (28% zlepseni)** |

Nove nalezy (od poslednich 20 commitu): #1-#7 (vodometry, bounces). Pretrvavajici: #8, #9, #10, #11, #13. Plne opraveno: 14 nalezu z puvodniho reportu.
