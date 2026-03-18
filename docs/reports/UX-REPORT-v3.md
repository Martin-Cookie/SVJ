# UX Analyza -- Cela aplikace (revize 3)

> Analyzovano: 2026-03-18
> Rozsah: Cela aplikace (9 modulu: Prehled, Vlastnici, Jednotky, Import z Excelu, Hlasovani, Hromadne rozesilani, Kontroly, Administrace, Nastaveni)
> Kontext: Predchozi report (2026-03-08 v2) mel 5K / 14D / 14Dr. Od te doby bylo opraveno vice nalezu. Hlavni zmeny: dynamicke mapovani importu (4-krokovy wizard), ciselniky redesign, formular rozesilani zjednoduseni, owners.py rozdelen na package.

## Souhrn

| Pohled | Kriticke | Dulezite | Drobne |
|--------|----------|----------|--------|
| Bezny uzivatel | 1 | 3 | 3 |
| Business analytik | 1 | 2 | 2 |
| UI/UX designer | 0 | 3 | 4 |
| Performance analytik | 1 | 1 | 1 |
| Error recovery | 1 | 2 | 2 |
| Data quality | 0 | 2 | 1 |
| **Celkem** | **4** | **13** | **13** |

### Stav predchozich nalezu (z v2)

| ID | Popis | Stav |
|----|-------|------|
| K1 | N+1 query v tax matching | **PRETRVAVA** -- viz K1 nize |
| K2 | Import vlastniku -- destruktivni akce bez potvrzeni | **OPRAVENO** -- `data-confirm` na formulari s poctem vlastniku |
| K3 | Ticha konverze nevalidnich ciselnych vstupu na NULL | **PRETRVAVA** -- viz D11 nize |
| K4 | pdf.js nacitan na kazde strance | **OPRAVENO** -- presunuto z base.html, nacitani jen v matching.html (extra_head block) |
| K5 | Dashboard nacita vsechny tax sessions bez limitu | **PRETRVAVA** -- viz K4 nize |
| D1 | Snapshot warning bez jasne akce | **PRETRVAVA** -- viz D8 nize |
| D2 | Filtracni bubliny vlastniku -- 3 rady bez hierarchie | **PRETRVAVA** -- viz D5 nize |
| D3 | Email validace -- tiche nastaveni NULL | **CASTECNE OPRAVENO** -- `type="email"` pridano na vicero mist, ale serverova logika stale uklada bez emailu |
| D4 | Nekonzistentni empty states | **CASTECNE OPRAVENO** -- dashboard ma CTA pro prazdny stav, ale dalsi moduly stale ne (viz Dr4) |
| D5 | Chybejici loading state na export tlacitcich | **OPRAVENO** -- setTimeout 3s vraceni textu implementovan |
| D6 | Test email -- chybi client-side validace | **OPRAVENO** -- `type="email"` + disable prazdne |
| D7 | Rozesilka odesílani stranka prilist minimalisticka | **OPRAVENO** -- progress bar s ETA, pozastaveni/zruseni |
| D8 | Kontroly -- dve nezavisle sekce na jedne strance | **PRETRVAVA** -- viz D6 nize |
| D9 | Hlasovani -- "Generovat listky" bez potvrzeni poctu | **OPRAVENO** -- confirm dialog s poctem |
| D10 | Neodevzdane listky -- chybi hromadna akce | **PRETRVAVA** -- viz D9 nize |
| D11 | Administrace purge bez preview | **PRETRVAVA** -- viz D10 nize |
| D12 | Rozesilka send -- checkbox stav v sessionStorage | **PRETRVAVA** -- viz Dr8 nize |
| D13 | Flash zpravy -- dva ruzne systemy | **PRETRVAVA** -- viz Dr7 nize |
| Dr1-Dr14 | Drobne nalezy | Vetsi cast opravena, viz jednotlive nalezy nize |

---

## KRITICKE

### K1: N+1 query v tax matching -- in-loop DB dotazy

- **Severity:** KRITICKE
- **Modul:** Hromadne rozesilani (matching)
- **Pohled:** Performance analytik
- **Co a kde:** V `sending.py` se pro kazdy dokument v `all_docs` smycce delaji separatni `db.query(TaxDistribution).filter_by(document_id=doc.id).all()` dotazy. Pri 100+ dokumentech = 100+ SQL dotazu.
- **Dopad:** Pomala odezva pri prirazovani emailu u session s velkym poctem dokumentu.
- **Reseni:** Predem nacist vsechny distribuce jednim dotazem a indexovat do dictu `{doc_id: [dists]}`.
- **Varianty:** --
- **Kde v kodu:** `app/routers/tax/sending.py`
- **Narocnost:** Stredni ~30 min
- **Zavislosti:** --
- **Regrese riziko:** Nizke
- **Rozhodnuti:** Opravit
- **Jak otestovat:** Otevrit matching stranku session s 50+ dokumenty, merit cas nacitani pred a po.
- **Mockup:**
  ```
  Soucasny stav (in-loop):
  for doc in all_docs:          # 100 iteraci
      dists = db.query(TD)      # 100 SQL dotazu
          .filter_by(doc.id)

  Navrhovany stav (batch):
  all_dists = db.query(TD)      # 1 SQL dotaz
      .filter(TD.document_id.in_([d.id for d in all_docs]))
  dists_by_doc = defaultdict(list)
  ```

### K2: Import mapovani -- ztrata souboru pri chybe parsovani

- **Severity:** KRITICKE
- **Modul:** Import z Excelu (novy 4-krokovy wizard)
- **Pohled:** Error recovery
- **Co a kde:** Novy import wizard (owner_import_mapping.html, contact_import_mapping.html) predava cestu k souboru (`file_path`) jako hidden field pres 3 kroky (mapovani -> nahled -> potvrzeni). Pokud se server restartuje mezi kroky, docasny soubor muze byt smazan nebo nedostupny. Potvrzovaci krok neprovadi `Path(file_path).exists()` check.
- **Dopad:** Uzivatel projde celym mapovanim a nahledem, klikne "Potvrdit", a dostane 500 chybu nebo tichy redirect. Cela prace s mapovanim je ztracena.
- **Reseni:** (a) Pridat `Path(file_path).exists()` check pred kazdy krok, (b) Pri chybejicim souboru presmerovat na upload s flash zpravou "Soubor vyprsel, nahrajte znovu", (c) Zvazit ulozeni mapovani do session/DB aby se nemuselo opakovat.
- **Varianty:** Alternativne: ulozit mapping JSON do DB/souboru pri kazdem kroku (recovery-friendly).
- **Kde v kodu:** `app/routers/owners/import_owners.py` (post "/import/potvrdit"), `app/routers/owners/import_contacts.py` (post "/import-kontaktu/potvrdit")
- **Narocnost:** Nizka ~10 min
- **Zavislosti:** --
- **Regrese riziko:** Nizke
- **Rozhodnuti:** Opravit
- **Jak otestovat:** (1) Nahrat Excel, projit na nahled. (2) Rucne smazat soubor z `data/uploads/excel/`. (3) Kliknout "Potvrdit" -> ocekavani: redirect na import s chybovou zpravou (ne 500).

### K3: Contact import -- validate_upload chyba se zobrazi jen jako "format"

- **Severity:** KRITICKE
- **Modul:** Import kontaktu
- **Pohled:** Bezny uzivatel, Error recovery
- **Co a kde:** V `import_contacts.py:54-56` se pri validate_upload chybe redirectuje na `/vlastnici/import?chyba_kontakty=format#kontakty`. Skutecna chybova zprava z `validate_upload()` (napr. "Soubor je vetsi nez 10 MB" nebo "Neplatna pripona .csv") se ztrati -- uzivatel vidi jen genericky text "Nahrajte soubor ve formatu .xlsx".
- **Dopad:** Uzivatel nevi proc import selhal. Muze opakovat s tim samym souborem.
- **Reseni:** Predat skutecnou chybovou zpravu z `validate_upload()` jako query parametr (URL-encoded) nebo pouzit formularovou odpoved misto redirectu (jako u import vlastniku, ktery to resi spravne na radku 66-73).
- **Varianty:** --
- **Kde v kodu:** `app/routers/owners/import_contacts.py:54-56`
- **Narocnost:** Nizka ~5 min
- **Zavislosti:** --
- **Regrese riziko:** Nizke
- **Rozhodnuti:** Opravit
- **Jak otestovat:** (1) Zkusit nahrat .csv soubor misto .xlsx do importu kontaktu. (2) Ocekavani: specificka chybova zprava. (3) Aktualne: genericke "Nahrajte soubor ve formatu .xlsx".

### K4: Dashboard nacita vsechny tax sessions bez limitu

- **Severity:** KRITICKE
- **Modul:** Prehled (Dashboard)
- **Pohled:** Performance analytik + Business analytik
- **Co a kde:** Dashboard nacita VSECHNY tax sessions jednim dotazem a grupuje v Pythonu. Po roce pouzivani s desitkami sessions to zbytecne zatezuje.
- **Dopad:** S narustajicim poctem sessions se zpomaluje nacitani dashboardu.
- **Reseni:** Pouzit SQL agregaci `GROUP BY send_status` pro pocty a subquery pro latest per status. Alternativne alespon `.limit(100)`.
- **Varianty:** --
- **Kde v kodu:** `app/routers/dashboard.py`
- **Narocnost:** Stredni ~30 min
- **Zavislosti:** --
- **Regrese riziko:** Nizke
- **Rozhodnuti:** Opravit
- **Jak otestovat:** Vytvorit 20+ tax sessions, merit cas nacitani dashboardu pred a po optimalizaci.

---

## DULEZITE

### D1: Import mapovani -- zadny zpusob jak se vratit k predchozimu mapovani

- **Severity:** DULEZITE
- **Modul:** Import z Excelu (novy wizard)
- **Pohled:** Business analytik, Bezny uzivatel
- **Co a kde:** Stepper na mapovaci strance ukazuje kroky 1-4, ale kliknuti na predchozi kroky nic nedela -- je to jen vizualni indikator. Uzivatel na kroku 3 (Nahled) nemuze kliknout na krok 2 (Mapovani) pro upravu prirazeni. Musi se vratit na import upload a nahrat soubor znovu.
- **Dopad:** Pri chybe v mapovani musi uzivatel zacit od zacatku (znovu nahrat soubor).
- **Reseni:** (a) Odkaz "Zpet na import" na nahledove strance smeruje na hlavni import stranku (krok 1), ale mohl by smerovat na mapovaci stranku s predvyplnenym mapovanim, (b) Stepper kroky 1-2 by mohly byt klikaci (alespon "Zpet na mapovani" tlacitko na preview strance).
- **Varianty:** Varianta A: pridat tlacitko "Upravit mapovani" na nahledovou stranku. Varianta B: klikaci stepper kroky.
- **Kde v kodu:** `app/templates/owners/import_preview.html:8`, `app/templates/partials/import_stepper.html`
- **Narocnost:** Stredni ~30 min
- **Zavislosti:** --
- **Regrese riziko:** Nizke
- **Rozhodnuti:** Potreba rozhodnuti uzivatele
- **Jak otestovat:** (1) Nahrat Excel, projit mapovani, dostat se na nahled. (2) Zjistit chybu v mapovani. (3) Ocekavani: moznost upravit mapovani bez opakovani uploadu.
- **Mockup:**
  ```
  Soucasny stav:
  [<- Zpet na import]  (= upload stranka, ztraci se mapovani)

  Navrhovany stav:
  [<- Zpet na import]  [Upravit mapovani]
  ```

### D2: Import kontaktu -- overwrite checkbox bez varnej zpravy

- **Severity:** DULEZITE
- **Modul:** Import kontaktu (novy wizard)
- **Pohled:** Error recovery, Data quality
- **Co a kde:** Na nahledove strance importu kontaktu (`contact_import_preview.html:73-76`) je checkbox "Prepsat existujici udaje". Zaskritnuti tohoto checkboxu pred odeslanim formulare nema zadny potvrzovaci dialog. Prepis muze modifikovat stovky poli najednou.
- **Dopad:** Uzivatel muze nechtene prepsat stavajici spravna data novymi (potencialne neaktualnymi) daty z Excelu.
- **Reseni:** Pridat `data-confirm` na formular pokud je overwrite checkbox zaskritnuly: "Prepise existujici udaje u X vlastniku. Pokracovat?"
- **Varianty:** --
- **Kde v kodu:** `app/templates/owners/contact_import_preview.html:61-82`
- **Narocnost:** Nizka ~10 min
- **Zavislosti:** --
- **Regrese riziko:** Nizke
- **Rozhodnuti:** Opravit
- **Jak otestovat:** (1) Na nahledu importu kontaktu zaskritnout "Prepsat existujici". (2) Kliknout "Importovat vybrane". (3) Ocekavani: confirm dialog. Aktualne: primo odesle.

### D3: Import mapovani -- zadna napoveda k prirazeni sloupcu

- **Severity:** DULEZITE
- **Modul:** Import z Excelu (novy wizard)
- **Pohled:** Bezny uzivatel
- **Co a kde:** Mapovaci stranka (`owner_import_mapping.html`, `contact_import_mapping.html`) zobrazuje skupiny poli s dropdown selectory. Ale u zadneho pole neni tooltip/napoveda co ocekavat. Napr. "Podil SCD" -- co je to? "LV" -- co to znamena? Uzivatel ktery vidi Excel poprvne nema tuseni co prirazovat.
- **Dopad:** Nezkuseny uzivatel muze spatne prirazovat sloupce, coz vede k chybnym datum.
- **Reseni:** Pridat `title` atribut na kazdou label ve skupinach mapovani. Napr.: "Podil SCD = spoluvlastnicky podil na spolecnych castech domu (cislo)", "LV = list vlastnictvi (cislo)".
- **Varianty:** Alternativne: maly info ikonka (i) s tooltip u kazdeho pole.
- **Kde v kodu:** `app/templates/partials/import_mapping_fields.html:33-35`
- **Narocnost:** Nizka ~15 min (data v FIELD_DEFS dict + tooltip v macro)
- **Zavislosti:** --
- **Regrese riziko:** Nizke
- **Rozhodnuti:** Opravit
- **Jak otestovat:** Na mapovaci strance najet mysi na label pole -> ocekavani: tooltip s vysvetlenim.

### D4: Import kontaktu -- hledani bez normalizace diakritiky

- **Severity:** DULEZITE
- **Modul:** Import kontaktu (novy wizard)
- **Pohled:** Bezny uzivatel, Data quality
- **Co a kde:** Hledani na nahledove strance importu kontaktu (`contact_import_preview.html:229-238`) pouziva proste `q.toLowerCase()` JavaScript porovnani. Hledani "novak" nenajde "Novak" protoze `a` != `a` s diakritikou.
- **Dopad:** Uzivatel nevi ze hledani nefunguje s diakritikou -- muze si myslet ze zaznam v nahledu chybi.
- **Reseni:** Pridat JS funkci pro strip diakritiky: `str.normalize('NFD').replace(/[\u0300-\u036f]/g, '')` a pouzit ji v `searchRows()`.
- **Varianty:** --
- **Kde v kodu:** `app/templates/owners/contact_import_preview.html:229-238`
- **Narocnost:** Nizka ~5 min
- **Zavislosti:** --
- **Regrese riziko:** Nizke
- **Rozhodnuti:** Opravit
- **Jak otestovat:** (1) Na nahledu importu kontaktu zadat do hledani "novak" (bez hacku). (2) Ocekavani: najde "Novak". Aktualne: nenajde.
- **Mockup:**
  ```
  Soucasny stav:
  function searchRows(q) {
      var lower = q.toLowerCase();
      // "novak" != "novak" (s hackem)

  Navrhovany stav:
  function stripDia(s) {
      return s.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
  }
  function searchRows(q) {
      var norm = stripDia(q);
      // "novak" == "novak" (oba normalizovane)
  ```

### D5: Filtracni bubliny vlastniku -- 3 rady bez hierarchie (pretrvava z v2)

- **Severity:** DULEZITE
- **Modul:** Vlastnici
- **Pohled:** UI/UX designer
- **Co a kde:** Stranka vlastniku ma stale 3 rady filtracnich bublin: (1) typ osoby + kontakt + stav, (2) typ vlastnictvi, (3) sekce. To je 12-15 bublin najednou.
- **Dopad:** Novy uzivatel je zahlcen mnozstvim filtru. Obtizne identifikuje aktivni kombinaci.
- **Reseni:** Seskupit filtry do `<details>` sekci nebo zobrazit aktivni filtry jako chips s moznosti "x" pro odebrani. Pridat "Zrusit filtry" tlacitko.
- **Varianty:** --
- **Kde v kodu:** `app/templates/owners/list.html:67-132`
- **Narocnost:** Vysoka ~2 hod
- **Zavislosti:** --
- **Regrese riziko:** Stredni (hodne existujicich filtracnich kombinaci)
- **Rozhodnuti:** Potreba rozhodnuti uzivatele

### D6: Kontroly -- dve nezavisle sekce na jedne strance (pretrvava z v2)

- **Severity:** DULEZITE
- **Modul:** Kontroly (sync)
- **Pohled:** Business analytik
- **Co a kde:** Stranka `/kontroly` stale obsahuje dve nezavisle sekce (Kontrola vlastniku a Kontrola podilu) se sdilenou URL a oddelenymi query parametry.
- **Dopad:** Pri pouziti jedne sekce se stav druhe muze resetovat.
- **Reseni:** Zvazit rozdeleni na dva samostatne podstranky s tab/bubliny prepinanim.
- **Varianty:** --
- **Kde v kodu:** `app/templates/sync/index.html`, `app/routers/sync.py`
- **Narocnost:** Stredni ~1 hod
- **Zavislosti:** --
- **Regrese riziko:** Stredni
- **Rozhodnuti:** Potreba rozhodnuti uzivatele

### D7: Ciselniky -- klikaci oblast na kartach je cela button, ale neni zjevne ze jde kliknout

- **Severity:** DULEZITE
- **Modul:** Administrace (ciselniky)
- **Pohled:** UI/UX designer, Bezny uzivatel
- **Co a kde:** Redesignovane ciselniky (`code_lists.html`) pouzivaji 5 karet v jednom gridu. Karty jsou `<button>` elementy s hover efektem. Ale vizualne vypadaji jako staticke informacni karty -- chybi vizualni indikator "klikni pro otevreni" (sipka, chevron, podtrzeni, zmena kursoru).
- **Dopad:** Novy uzivatel nemuze intuitivne poznat ze na karty jde kliknout pro zobrazeni detailu.
- **Reseni:** Pridat chevron ikonu (>) nebo sipku na pravou stranu kazde karty. Nebo pridat text "klikni pro upravu" pod pocet polozek.
- **Varianty:** --
- **Kde v kodu:** `app/templates/administration/code_lists.html:24-38`
- **Narocnost:** Nizka ~10 min
- **Zavislosti:** --
- **Regrese riziko:** Nizke
- **Rozhodnuti:** Opravit
- **Jak otestovat:** Vizualne zkontrolovat -- karty by mely mit jasny affordance pro kliknuti.
- **Mockup:**
  ```
  Soucasny stav:
  +----------------------------+
  | [icon] Typ prostoru        |
  |         4 polozek          |
  +----------------------------+
  (vizualne staticka karta)

  Navrhovany stav:
  +----------------------------+
  | [icon] Typ prostoru      > |
  |         4 polozek          |
  +----------------------------+
  (sipka indikuje klikaci akci)
  ```

### D8: Snapshot warning v hlasovani bez jasne akce (pretrvava z v2)

- **Severity:** DULEZITE
- **Modul:** Hlasovani
- **Pohled:** Bezny uzivatel
- **Co a kde:** Zluty banner `snapshot_warning` stale neobsahuje tlacitko pro primou akci.
- **Dopad:** Uzivatel vidi varovani ale nevi co konkretne delat.
- **Reseni:** Pridat odkaz/tlacitko na akci pregen nebo alespon podrobnejsi vysvetleni.
- **Kde v kodu:** `app/templates/voting/_voting_header.html`
- **Narocnost:** Nizka ~10 min
- **Zavislosti:** --
- **Regrese riziko:** Nizke
- **Rozhodnuti:** Opravit

### D9: Neodevzdane listky -- chybi hromadna akce (pretrvava z v2)

- **Severity:** DULEZITE
- **Modul:** Hlasovani
- **Pohled:** Business analytik
- **Co a kde:** Stranka neodevzdanych listku stale nema export tlacitko.
- **Dopad:** Rucni prace pri rozesilani upominek.
- **Reseni:** Pridat tlacitko "Export neodevzdanych" (Excel/CSV).
- **Kde v kodu:** `app/templates/voting/not_submitted.html`
- **Narocnost:** Nizka ~15 min
- **Zavislosti:** --
- **Regrese riziko:** Nizke
- **Rozhodnuti:** Opravit

### D10: Administrace purge bez preview co bude smazano (pretrvava z v2)

- **Severity:** DULEZITE
- **Modul:** Administrace (purge)
- **Pohled:** Error recovery
- **Co a kde:** Kaskadove upozorneni stale skryte. Po zasknuti "Vlastnici" neni jasne ze se smazou i hlasovani.
- **Dopad:** Uzivatel muze nechtene smazat vice dat nez zamyslel.
- **Reseni:** Zobrazit kaskadove upozorneni viditelne po zasknuti checkboxu.
- **Kde v kodu:** `app/templates/administration/purge.html`
- **Narocnost:** Nizka ~10 min
- **Zavislosti:** --
- **Regrese riziko:** Nizke
- **Rozhodnuti:** Opravit

### D11: Ticha konverze nevalidnich ciselnych vstupu na NULL (pretrvava z v2)

- **Severity:** DULEZITE
- **Modul:** Jednotky
- **Pohled:** Data quality
- **Co a kde:** Pri editaci jednotky se nevalidni cisla stale tise konvertuji na NULL bez varovani.
- **Dopad:** Uzivatel si mysli ze data ulozil spravne.
- **Reseni:** Validovat client-side (`type="number"`), server-side vracet warning.
- **Kde v kodu:** `app/routers/units.py`
- **Narocnost:** Nizka ~15 min
- **Zavislosti:** --
- **Regrese riziko:** Nizke
- **Rozhodnuti:** Opravit

### D12: Rozesilani upload -- formular skryva submit tlacitko dokud neni nazev

- **Severity:** DULEZITE
- **Modul:** Hromadne rozesilani
- **Pohled:** Bezny uzivatel, UI/UX designer
- **Co a kde:** Na strance `tax/upload.html` je tlacitko "Nahrat a zpracovat" `hidden` a zobrazi se teprve po vyplneni nazvu I vyberu souboru. Uzivatel ktery nejdriv vybere soubory a pak ceka na upload netuzi ze musi vyplnit jeste nazev -- vidi jen "Zrusit" a zadne upload tlacitko.
- **Dopad:** Uzivatel muze byt zmateny a nevedi jak pokracovat. Navic: auto-select sablony by mel automaticky vyplnit nazev, ale uzivatel si nemusi vsimnout ze se nazev vyplnil.
- **Reseni:** Zobrazit tlacitko vzdy, ale ve stavu `disabled` s `opacity-50`. Pridat tooltip "Vyplnte nazev a vyberte soubory".
- **Varianty:** --
- **Kde v kodu:** `app/templates/tax/upload.html:16-17`
- **Narocnost:** Nizka ~5 min
- **Zavislosti:** --
- **Regrese riziko:** Nizke
- **Rozhodnuti:** Opravit
- **Mockup:**
  ```
  Soucasny stav:
  [Nazev: ______] [Soubory: ______]  [Zrusit]
  (tlacitko "Nahrat" je hidden -- uzivatel nevi o nem)

  Navrhovany stav:
  [Nazev: ______] [Soubory: ______]  [Nahrat a zpracovat (disabled)] [Zrusit]
  (tlacitko viditelne ale neaktivni, tooltip "Vyplnte nazev a vyberte soubory")
  ```

### D13: Ciselniky -- editace polozky s usage > 0 neni mozna ale neni to jasne

- **Severity:** DULEZITE
- **Modul:** Administrace (ciselniky)
- **Pohled:** UI/UX designer
- **Co a kde:** Na strance ciselniku (`code_lists.html:93-96`) je polozka s usage > 0 zobrazena jako plain text bez kursoru a bez edit moznosti. Ale neni zadny vizualni indikator proc nejde editovat -- chybi tooltip "Pouzivano u X zaznamu, nelze upravit" nebo jiny vizualni hint.
- **Dopad:** Uzivatel chce zmenit hodnotu ciselniku ale nemuze a nevi proc.
- **Reseni:** Pridat `title` atribut na text polozky: "Pouzivano u X zaznamu -- nelze upravit. Pridejte novou hodnotu a aktualizujte zaznamy."
- **Varianty:** --
- **Kde v kodu:** `app/templates/administration/code_lists.html:92-96`
- **Narocnost:** Nizka ~5 min
- **Zavislosti:** --
- **Regrese riziko:** Nizke
- **Rozhodnuti:** Opravit

---

## DROBNE

### Dr1: Import stepper -- neni klikaci, jen vizualni

- **Severity:** DROBNE
- **Modul:** Import z Excelu (novy wizard)
- **Pohled:** UI/UX designer
- **Co a kde:** Import sub-stepper (`import_stepper.html`) zobrazuje 4 kroky jako text s sipkami. Kroky nejsou klikaci -- jde jen o vizualni indikator. To je nekonzistentni s wizard stepperem v rozesilce (ten je take neklikaci, ale tam je linearni workflow opravneny).
- **Dopad:** Minimalni -- uzivatel muze chtit navigovat zpet na predchozi krok.
- **Reseni:** Klikaci kroky pro dokoncene faze (1, 2 pokud jsme na 3).
- **Kde v kodu:** `app/templates/partials/import_stepper.html`
- **Narocnost:** Stredni ~30 min
- **Zavislosti:** D1 (navrat na mapovani)
- **Regrese riziko:** Nizke
- **Rozhodnuti:** Potreba rozhodnuti uzivatele

### Dr2: Import nahled -- "Potvrdit a ulozit" bez confirm dialogu

- **Severity:** DROBNE
- **Modul:** Import vlastniku (novy wizard)
- **Pohled:** Error recovery
- **Co a kde:** Na nahledove strance importu vlastniku (`import_preview.html:19-24`) je tlacitko "Potvrdit a ulozit" ktere spusti destruktivni akci (smaze vsechny stavajici vlastniky a nahradi je). Chybi `data-confirm` dialog.
- **Dopad:** Uzivatel muze nahodnym kliknutim spustit import -- sice s nahledem dat, ale bez finalniho potvrzeni.
- **Reseni:** Pridat `data-confirm` na formular: "Import smaze vsech X vlastniku a nahradi je Y vlastniky z Excelu. Pokracovat?"
- **Kde v kodu:** `app/templates/owners/import_preview.html:19-24`
- **Narocnost:** Nizka ~5 min
- **Zavislosti:** --
- **Regrese riziko:** Nizke
- **Rozhodnuti:** Opravit

### Dr3: Import kontaktu -- "Vybrat vse se zmenami" nevybira pri aktivnim filtru

- **Severity:** DROBNE
- **Modul:** Import kontaktu (novy wizard)
- **Pohled:** Bezny uzivatel
- **Co a kde:** Checkbox "Vybrat vse se zmenami" na nahledove strance importu kontaktu (`contact_import_preview.html:68-71`) vybira VSECHNY radky se zmenami, ne jen aktualne zobrazene/filtrovane. Pokud uzivatel filtruje na konkretni pole (napr. jen "Email") a klikne "Vybrat vse", vybere i radky ktere nevidí.
- **Dopad:** Uzivatel importuje vice zaznamu nez zamyslel.
- **Reseni:** `toggleSelectAll()` funkce uz kontroluje `row.style.display !== 'none'`, coz je spravne. ALE: checkbox label rika "Vybrat vse se zmenami" -- melo by byt "Vybrat vsechny zobrazene" pokud je aktivni filtr.
- **Kde v kodu:** `app/templates/owners/contact_import_preview.html:68-71, :241-247`
- **Narocnost:** Nizka ~5 min
- **Zavislosti:** --
- **Regrese riziko:** Nizke
- **Rozhodnuti:** Opravit

### Dr4: Nekonzistentni empty states (castecne pretrvava z v2)

- **Severity:** DROBNE
- **Modul:** Cela aplikace
- **Pohled:** UI/UX designer
- **Co a kde:** Dashboard ma nyni dobre CTA pro prazdny stav. Ale dalsi moduly stale maji minimalni empty states: `tax/index.html:126` -- "Zadne rozesilani v tomto stavu." bez akce; ciselniky maji "Zatim zadne polozky." s CTA. Nekonzistentni.
- **Dopad:** Pri prvnim pouziti modulu uzivatel nemuze intuitivne zacit.
- **Reseni:** Zavest jednotny vzor: ikona + text + primarni CTA tlacitko.
- **Kde v kodu:** Vice souboru
- **Narocnost:** Nizka ~20 min (pro vsechny moduly)
- **Zavislosti:** --
- **Regrese riziko:** Nizke
- **Rozhodnuti:** Opravit

### Dr5: Import mapovani -- "Data od radku" bez vysvetleni

- **Severity:** DROBNE
- **Modul:** Import z Excelu (novy wizard)
- **Pohled:** Bezny uzivatel
- **Co a kde:** Pole "Data od radku" na mapovaci strance (`owner_import_mapping.html:46, contact_import_mapping.html:43`) nema zadny tooltip. Novy uzivatel nevi ze "radek 1" je hlavicka a "radek 2" je prvni datovy radek (pro import vlastniku), resp. "radek 7" pro import kontaktu.
- **Dopad:** Spatne nastaveni start_row vede k chybnym datum nebo prazdnemu importu.
- **Reseni:** Pridat `title` atribut: "Cislo radku v Excelu odkud zacinaji data (1 = hlavicka)".
- **Kde v kodu:** `app/templates/owners/owner_import_mapping.html:46`, `app/templates/owners/contact_import_mapping.html:43`
- **Narocnost:** Nizka ~2 min
- **Zavislosti:** --
- **Regrese riziko:** Nizke
- **Rozhodnuti:** Opravit

### Dr6: Sidebar neni responsivni (pretrvava z v2)

- **Severity:** DROBNE
- **Modul:** Cela aplikace
- **Pohled:** UI/UX designer
- **Co a kde:** Sidebar `w-44` (176px) bez responsive breakpointu.
- **Dopad:** Na mobilnich zarizenich je sidebar neprimerane velky.
- **Reseni:** Hamburger menu pro mensi obrazovky.
- **Kde v kodu:** `app/templates/base.html:22`
- **Narocnost:** Stredni ~1 hod
- **Zavislosti:** --
- **Regrese riziko:** Nizke
- **Rozhodnuti:** Potreba rozhodnuti uzivatele (priorita vs. desktop-first)

### Dr7: Flash zpravy -- dva ruzne systemy (pretrvava z v2)

- **Severity:** DROBNE
- **Modul:** Cela aplikace
- **Pohled:** UI/UX designer
- **Co a kde:** Globalni `data-auto-dismiss` (5s) vs inline setTimeout (ruzne casy). Vizualne konzistentni, chovani ne.
- **Dopad:** Nekonzistentni UX.
- **Reseni:** Sjednotit na jeden system.
- **Kde v kodu:** `app/templates/base.html:135`, ruzne inline sablony
- **Narocnost:** Nizka ~15 min
- **Zavislosti:** --
- **Regrese riziko:** Nizke
- **Rozhodnuti:** Opravit

### Dr8: Rozesilka send -- checkbox stav v sessionStorage (pretrvava z v2)

- **Severity:** DROBNE
- **Modul:** Hromadne rozesilani
- **Pohled:** Error recovery
- **Co a kde:** Stav checkboxu prijemcu se uklada do sessionStorage. Snapshot muze byt nekonzistentni s aktualnim stavem.
- **Dopad:** Potencialni nekonzistence.
- **Reseni:** Validace snapshotu proti aktualnim datum pri nacteni.
- **Kde v kodu:** `app/static/js/app.js`
- **Narocnost:** Stredni ~30 min
- **Zavislosti:** --
- **Regrese riziko:** Nizke
- **Rozhodnuti:** Opravit

### Dr9: Import mapovani -- "Ulozit mapovani pro pristi import" neni viditelne po ulozeni

- **Severity:** DROBNE
- **Modul:** Import z Excelu (novy wizard)
- **Pohled:** Bezny uzivatel
- **Co a kde:** Checkbox "Ulozit mapovani pro pristi import" je zavisly na hidden formulari (`mapping-form`) a hodnota `save` se predava v JSON. Ale pri pristim importu neni vizualne zrejme ze se pouzilo ulozene mapovani -- pole jsou predvyplnena s `ring-2 ring-blue-300` (modre okraje pro "saved"), ale neni to nijak vysvetleno.
- **Dopad:** Uzivatel nevi proc jsou nektere selectory modre (saved) vs zelene (auto-matched) vs cervene (chybi).
- **Reseni:** Pridat legendu pod stats bar: modre = ulozene z minule, zelene = auto-prirazeno, cervene = chybi.
- **Kde v kodu:** `app/templates/partials/import_mapping_fields.html:40-43`
- **Narocnost:** Nizka ~10 min
- **Zavislosti:** --
- **Regrese riziko:** Nizke
- **Rozhodnuti:** Opravit
- **Mockup:**
  ```
  Soucasny stav:
  [6/15 nalezeno] [Povinna pole OK]

  Navrhovany stav:
  [6/15 nalezeno] [Povinna pole OK]
  Legenda: [modre] = ulozene z minule  [zelene] = auto  [cervene] = chybi
  ```

### Dr10: Administrace index -- "Smazat data" neni vizualne odlisena (castecne opraveno)

- **Severity:** DROBNE
- **Modul:** Administrace
- **Pohled:** UI/UX designer
- **Co a kde:** Karta "Smazat data" nyni ma cerveny text nadpisu (`text-red-600`), coz je zlepseni oproti v2. Ale stale je v rovnocenem gridu s bezpecnymi akcemi.
- **Dopad:** Vizualni rovnocennost bezpecnych a destruktivnich akci.
- **Reseni:** Oddelit do vlastni sekce "Nebezpecna zona" s cervenym okrajem.
- **Kde v kodu:** `app/templates/administration/index.html:102-115`
- **Narocnost:** Nizka ~10 min
- **Zavislosti:** --
- **Regrese riziko:** Nizke
- **Rozhodnuti:** Potreba rozhodnuti uzivatele

### Dr11: Formatovani dat -- nekonzistentni format data/casu (pretrvava z v2)

- **Severity:** DROBNE
- **Modul:** Cela aplikace
- **Pohled:** UI/UX designer
- **Co a kde:** Ruzne formaty data: `dd.mm.YYYY` vs `dd.mm.YYYY HH:MM` vs `dd.mm.YYYY HH:MM:SS`.
- **Dopad:** Vizualni nekonzistence.
- **Reseni:** Sjednotit na `dd.mm.YYYY HH:MM` pro timestampy.
- **Kde v kodu:** Ruzne sablony
- **Narocnost:** Nizka ~15 min
- **Zavislosti:** --
- **Regrese riziko:** Nizke
- **Rozhodnuti:** Opravit

### Dr12: Ciselniky -- emailove sablony nemaji napovedu pro promenne

- **Severity:** DROBNE
- **Modul:** Administrace (ciselniky)
- **Pohled:** Bezny uzivatel
- **Co a kde:** Formulare emailovych sablon (`code_lists.html:175`) maji poznamku `{rok} = rok rozesilani` u pole predmetu. Ale pole textu emailu nema zadnou napovedu ke klicovym slovum/promennym. Uzivatel nevi jake promenne muze pouzit.
- **Dopad:** Uzivatel vytvori sablonu bez promennych a pak musi rucne upravovat.
- **Reseni:** Pridat napovedu pod textarea: "Dostupne promenne: {rok} = rok rozesilani".
- **Kde v kodu:** `app/templates/administration/code_lists.html:179-182`
- **Narocnost:** Nizka ~5 min
- **Zavislosti:** --
- **Regrese riziko:** Nizke
- **Rozhodnuti:** Opravit

### Dr13: Rozesilani index -- back_url zobrazuje vzdy "Zpet na prehled"

- **Severity:** DROBNE
- **Modul:** Hromadne rozesilani
- **Pohled:** Bezny uzivatel
- **Co a kde:** Stranka `tax/index.html:7` zobrazuje vzdy "Zpet na prehled" bez ohledu na zdroj navigace. Pokud uzivatel prijde z administrace nebo jine stranky, label neni presny.
- **Dopad:** Minimalni -- uzivatel je vzdy presmerovan na spravnou URL, jen label neodpovida.
- **Reseni:** Dynamicky back label podle cilove URL (if/elif retezec).
- **Kde v kodu:** `app/templates/tax/index.html:5-8`
- **Narocnost:** Nizka ~5 min
- **Zavislosti:** --
- **Regrese riziko:** Nizke
- **Rozhodnuti:** Opravit

---

## NOVE NALEZY -- specificky pro nove/zmenene casti

### Pozitivni zmeny od v2

1. **Dynamicke mapovani importu** -- velke zlepseni oproti fixnimu rozlozeni sloupcu. Uzivatel muze prirazovat libovolne sloupce Excelu k polozkam. Stepper jasne ukazuje kde v procesu je. Auto-matching a ukladani mapovani sni cas opakovanych importu.

2. **Ciselniky redesign** -- kolapsovatelne karty s ikonami jsou prehlednejsi nez predchozi layout. Inline editace funguje dobre. Escape klávesa pro zruseni je implementovana.

3. **Formular rozesilani** -- zjednoduseni (sloucenici title+subject do jednoho pole, auto-select sablony) vyrazne snizuje pocet kroku pro vytvoreni noveho rozesilani.

4. **Import kontaktu wizard** -- nahled se zmenami (stare -> nove hodnoty), filtrovani podle pole, hromadny vyber -- vse dobre promyslene. Overwrite checkbox s jasnym rozlisenim barvy (oranzova = prepis).

5. **pdf.js presunuto** z base.html -- 316KB uspora na kazde strance mimo matching.

---

## Top 5 doporuceni (podle dopadu)

| # | Navrh | Dopad | Slozitost | Cas | Zavisi na | Rozhodnuti | Priorita |
|---|-------|-------|-----------|-----|-----------|------------|----------|
| 1 | Batch query v tax matching (K1) | Vysoky -- dramaticke zrychleni | Stredni | ~30 min | -- | Opravit | HNED |
| 2 | File exists check v import wizardu (K2) | Vysoky -- prevence 500 chyb | Nizka | ~10 min | -- | Opravit | HNED |
| 3 | Specificka chyba validate_upload v contact importu (K3) | Vysoky -- prevence frustrace | Nizka | ~5 min | -- | Opravit | HNED |
| 4 | Dashboard SQL agregace (K4) | Stredni -- skaluje s poctem sessions | Stredni | ~30 min | -- | Opravit | BRZY |
| 5 | Hledani bez diakritiky v import kontaktu (D4) | Stredni -- konzistence s ostatnimi moduly | Nizka | ~5 min | -- | Opravit | HNED |

---

## Quick wins (nizka slozitost, okamzity efekt)

- [ ] File exists check pred kazdym krokem import wizardu (K2) -- 3 radky Python
- [ ] Specificka chybova zprava v contact_import_upload (K3) -- 2 radky Python
- [ ] Strip diakritiky v JS hledani contact_import_preview (D4) -- 5 radku JS
- [ ] `data-confirm` na overwrite import kontaktu (D2) -- 1 atribut
- [ ] `data-confirm` na "Potvrdit a ulozit" import nahled (Dr2) -- 1 atribut
- [ ] Tooltip na "Data od radku" (Dr5) -- 1 atribut `title`
- [ ] Tooltip na ciselniky polozky s usage > 0 (D13) -- 1 atribut `title`
- [ ] Chevron ikona na ciselniky kartach (D7) -- 1 SVG element
- [ ] Legenda barev na mapovaci strance (Dr9) -- 1 radek HTML
- [ ] Napoveda promennych u emailovych sablon (Dr12) -- 1 radek HTML
- [ ] Disabled stav na "Nahrat a zpracovat" v tax upload (D12) -- 3 radky JS
- [ ] Dashboard `.limit(50)` na tax sessions query (K4) -- 1 radek Python
- [ ] Purge kaskadove upozorneni: odstranit `hidden` (D10) -- 1 atribut
- [ ] Sjednotit flash auto-dismiss timeout (Dr7)
- [ ] Back label dynamicky na tax index (Dr13) -- 5 radku Python
