# UX Analyza -- Cela aplikace (revize 4)

> Analyzovano: 2026-03-19
> Rozsah: Cela aplikace (9 modulu: Prehled, Vlastnici, Jednotky, Import z Excelu, Hlasovani, Hromadne rozesilani, Kontroly, Administrace, Nastaveni)
> Kontext: Predchozi report (2026-03-18 v3) mel 4K / 13D / 13Dr. Od te doby bylo opraveno 6 nalezu (D1, D5, D6, Dr1, Dr6, Dr10) a provedeny mensi UX tweaky. Tato revize kontroluje stav predchozich nalezu a pridava nove.

## Souhrn

| Pohled | Kriticke | Dulezite | Drobne |
|--------|----------|----------|--------|
| Bezny uzivatel | 1 | 3 | 4 |
| Business analytik | 1 | 2 | 1 |
| UI/UX designer | 0 | 3 | 5 |
| Performance analytik | 1 | 1 | 1 |
| Error recovery | 1 | 2 | 1 |
| Data quality | 0 | 2 | 1 |
| **Celkem** | **4** | **13** | **13** |

### Stav predchozich nalezu (z v3)

| ID | Popis | Stav |
|----|-------|------|
| K1 | N+1 query v tax matching -- in-loop DB dotazy | **PRETRVAVA** -- viz K1 nize |
| K2 | Import mapovani -- ztrata souboru pri chybe parsovani | **PRETRVAVA** -- viz K2 nize |
| K3 | Contact import -- validate_upload chyba se zobrazi jen jako "format" | **PRETRVAVA** -- viz K3 nize |
| K4 | Dashboard nacita vsechny tax sessions bez limitu | **CASTECNE OPRAVENO** -- pouziva SQL GROUP BY + per-status latest query (misto nacitani vsech sessions), ale per-status query se opakuji (viz K4 nize) |
| D1 | Import mapovani -- zadny zpusob jak se vratit k predchozimu mapovani | **OPRAVENO** -- dle git commitu fb74860 |
| D2 | Import kontaktu -- overwrite checkbox bez varnej zpravy | **PRETRVAVA** -- viz D2 nize |
| D3 | Import mapovani -- zadna napoveda k prirazeni sloupcu | **PRETRVAVA** -- viz D3 nize |
| D4 | Import kontaktu -- hledani bez normalizace diakritiky | **PRETRVAVA** -- viz D4 nize |
| D5 | Filtracni bubliny vlastniku -- 3 rady bez hierarchie | **OPRAVENO** -- dle git commitu fb74860 (odlozeny nalez) |
| D6 | Kontroly -- dve nezavisle sekce na jedne strance | **OPRAVENO** -- dle git commitu fb74860 (odlozeny nalez); tab prepinani implementovano |
| D7 | Ciselniky -- klikaci oblast na kartach neni zjevne ze jde kliknout | **PRETRVAVA** -- viz D7 nize |
| D8 | Snapshot warning v hlasovani bez jasne akce | **OPRAVENO** -- pridano tlacitko "Pregenerovat listky" s confirm dialogem primo ve warning banneru |
| D9 | Neodevzdane listky -- chybi hromadna akce | **OPRAVENO** -- export neodevzdanych implementovan v _voting_header.html |
| D10 | Administrace purge bez preview co bude smazano | **CASTECNE OPRAVENO** -- kaskadove varovani pridano pro owners (JS `purgeHandleOwnersDeps`), ale stale se zobrazi az po zasknuti checkboxu, ne predem |
| D11 | Ticha konverze nevalidnich ciselnych vstupu na NULL | **PRETRVAVA** -- viz D11 nize |
| D12 | Rozesilani upload -- formular skryva submit tlacitko | **PRETRVAVA** -- viz D12 nize |
| D13 | Ciselniky -- editace polozky s usage > 0 neni mozna ale neni to jasne | **PRETRVAVA** -- viz D13 nize |
| Dr1 | Import stepper -- neni klikaci, jen vizualni | **OPRAVENO** -- dle git commitu fb74860 (odlozeny nalez) |
| Dr2 | Import nahled -- "Potvrdit a ulozit" bez confirm dialogu | **PRETRVAVA** -- viz Dr2 nize |
| Dr3 | Import kontaktu -- "Vybrat vse se zmenami" nevybira pri aktivnim filtru | **PRETRVAVA** -- viz Dr3 nize |
| Dr4 | Nekonzistentni empty states | **PRETRVAVA** -- viz Dr4 nize |
| Dr5 | Import mapovani -- "Data od radku" bez vysvetleni | **PRETRVAVA** -- viz Dr5 nize |
| Dr6 | Sidebar neni responsivni | **OPRAVENO** -- hamburger menu pro mobilni zobrazeni implementovano (md:hidden toggle + overlay) |
| Dr7 | Flash zpravy -- dva ruzne systemy | **PRETRVAVA** -- viz Dr7 nize |
| Dr8 | Rozesilka send -- checkbox stav v sessionStorage | **PRETRVAVA** -- viz Dr8 nize |
| Dr9 | Import mapovani -- barvy mapovani bez legendy | **PRETRVAVA** -- viz Dr9 nize |
| Dr10 | Administrace index -- "Smazat data" neni vizualne odlisena | **OPRAVENO** -- dle git commitu fb74860 (odlozeny nalez) |
| Dr11 | Formatovani dat -- nekonzistentni format data/casu | **PRETRVAVA** -- viz Dr11 nize |
| Dr12 | Ciselniky -- emailove sablony nemaji napovedu pro promenne | **PRETRVAVA** -- viz Dr12 nize |
| Dr13 | Rozesilani index -- back_url zobrazuje vzdy "Zpet na prehled" | **OPRAVENO** -- dynamicky back_label implementovan v `tax/session.py:129-134` s if/elif retezcem |

---

## KRITICKE

### K1: N+1 query v tax matching -- in-loop DB dotazy (pretrvava z v3)

- **Severity:** KRITICKE
- **Modul:** Hromadne rozesilani (matching/sending)
- **Pohled:** Performance analytik
- **Co a kde:** V `sending.py` funkce `_auto_assign_unmatched_docs` iteruje pres `all_docs` a pro kazdy dokument pristupuje k `doc.distributions` (lazy-loaded relace). Pri 100+ dokumentech = 100+ SQL dotazu. Podobny vzor je v `_build_single_recipient`, kde se pro kazdy recipient delaji separatni dotazy na `TaxDistribution`.
- **Dopad:** Pomala odezva pri prirazovani a zobrazovani prijemcu u session s velkym poctem dokumentu. Riziko timeoutu.
- **Reseni:** Predem nacist vsechny distribuce jednim dotazem a indexovat do dictu `{doc_id: [dists]}`. V `tax_send_preview` uz je `joinedload(TaxDocument.distributions)` pouzit, ale v `_auto_assign_unmatched_docs` se stale pristupuje k `doc.distributions` bez eager loadingu.
- **Varianty:** --
- **Kde v kodu:** `app/routers/tax/sending.py:42-49` (doc.distributions pristup), `app/routers/tax/sending.py:70-86` (_build_single_recipient N+1)
- **Narocnost:** Stredni ~30 min
- **Zavislosti:** --
- **Regrese riziko:** Nizke
- **Rozhodnuti:** Opravit
- **Jak otestovat:** Otevrit matching stranku session s 50+ dokumenty, merit cas nacitani pred a po.
- **Mockup:**
  ```
  Soucasny stav (in-loop):
  for doc in all_docs:          # 100 iteraci
      dists = doc.distributions # 100 lazy-load SQL dotazu

  Navrhovany stav (batch):
  all_dists = db.query(TD)      # 1 SQL dotaz
      .filter(TD.document_id.in_([d.id for d in all_docs]))
  dists_by_doc = defaultdict(list)
  for d in all_dists: dists_by_doc[d.document_id].append(d)
  ```

### K2: Import mapovani -- ztrata souboru pri chybe parsovani (pretrvava z v3)

- **Severity:** KRITICKE
- **Modul:** Import z Excelu
- **Pohled:** Error recovery
- **Co a kde:** Import wizard predava cestu k souboru (`file_path`) jako hidden field pres 3 kroky. Pokud se server restartuje mezi kroky, docasny soubor muze byt nedostupny. Potvrzovaci krok neprovadi `Path(file_path).exists()` check.
- **Dopad:** Uzivatel projde celym mapovanim a nahledem, klikne "Potvrdit", a dostane 500 chybu. Cela prace s mapovanim je ztracena.
- **Reseni:** Pridat `Path(file_path).exists()` check pred kazdy krok. Pri chybejicim souboru presmerovat na upload s flash zpravou.
- **Varianty:** --
- **Kde v kodu:** `app/routers/owners/import_owners.py` (post "/import/potvrdit"), `app/routers/owners/import_contacts.py` (post "/import-kontaktu/potvrdit")
- **Narocnost:** Nizka ~10 min
- **Zavislosti:** --
- **Regrese riziko:** Nizke
- **Rozhodnuti:** Opravit
- **Jak otestovat:** (1) Nahrat Excel, projit na nahled. (2) Rucne smazat soubor z `data/uploads/excel/`. (3) Kliknout "Potvrdit" -> ocekavani: redirect s chybovou zpravou (ne 500).

### K3: Contact import -- validate_upload chyba se zobrazi jen jako "format" (pretrvava z v3)

- **Severity:** KRITICKE
- **Modul:** Import kontaktu
- **Pohled:** Bezny uzivatel, Error recovery
- **Co a kde:** V `import_contacts.py` se pri validate_upload chybe redirectuje na `/vlastnici/import?chyba_kontakty=format#kontakty`. Skutecna chybova zprava (napr. "Soubor je vetsi nez 10 MB") se ztrati.
- **Dopad:** Uzivatel nevi proc import selhal. Opakovane nahra stejny soubor.
- **Reseni:** Predat skutecnou chybovou zpravu z `validate_upload()` jako query parametr.
- **Varianty:** --
- **Kde v kodu:** `app/routers/owners/import_contacts.py:54-56`
- **Narocnost:** Nizka ~5 min
- **Zavislosti:** --
- **Regrese riziko:** Nizke
- **Rozhodnuti:** Opravit
- **Jak otestovat:** Zkusit nahrat .csv soubor misto .xlsx do importu kontaktu. Ocekavani: specificka chybova zprava. Aktualne: genericke "Nahrajte soubor ve formatu .xlsx".

### K4: Dashboard -- per-status dotazy na posledni voting/tax session (pretrvava z v3, castecne opraveno)

- **Severity:** KRITICKE
- **Modul:** Prehled (Dashboard)
- **Pohled:** Performance analytik + Business analytik
- **Co a kde:** Dashboard pouziva `GROUP BY` pro pocty statusu (dobre), ale pak pro KAZDY status delá separatni `db.query(Voting/TaxSession)...first()` s eager loadingem. Pri 4 voting statusech = 4 separatni dotazy, kazdy s `joinedload(Voting.ballots).joinedload(Ballot.votes)` -- nacita VSECHNY listky + hlasy pro kazde hlasovani.
- **Dopad:** S narustajicim poctem hlasovacich listek (stovky) se zpomaluje nacitani dashboardu. 500 listek * 10 hlasu = 5000 relaci nacteno jen pro dashboard.
- **Reseni:** Misto eager loadingu vsech ballots+votes pouzit SQL agregaci: `SUM(CASE WHEN ballot.status='processed' AND vote IS NOT NULL THEN ballot.total_votes ELSE 0 END)` primo v dotazu. Alternativne `.limit(1)` na subquery a agregovat v SQL.
- **Varianty:** (A) SQL agregace v jednom dotazu, (B) ukladat kvorum do cache/sloupce na Voting modelu pri kazdem zpracovani listku.
- **Kde v kodu:** `app/routers/dashboard.py:102-123` (voting per-status loop s joinedload)
- **Narocnost:** Stredni ~30 min
- **Zavislosti:** --
- **Regrese riziko:** Nizke
- **Rozhodnuti:** Opravit
- **Jak otestovat:** Vytvorit hlasovani s 500+ listky, merit cas nacitani dashboardu pred a po optimalizaci.

---

## DULEZITE

### D2: Import kontaktu -- overwrite checkbox bez varnej zpravy (pretrvava z v3)

- **Severity:** DULEZITE
- **Modul:** Import kontaktu
- **Pohled:** Error recovery, Data quality
- **Co a kde:** Na nahledove strance importu kontaktu je checkbox "Prepsat existujici udaje". Zaskritnuti nema zadny potvrzovaci dialog. Prepis muze modifikovat stovky poli najednou.
- **Dopad:** Uzivatel muze nechtene prepsat stavajici spravna data novymi daty z Excelu.
- **Reseni:** Pridat `data-confirm` na formular pokud je overwrite checkbox zaskritnuly.
- **Varianty:** --
- **Kde v kodu:** `app/templates/owners/contact_import_preview.html:61-82`
- **Narocnost:** Nizka ~10 min
- **Zavislosti:** --
- **Regrese riziko:** Nizke
- **Rozhodnuti:** Opravit
- **Jak otestovat:** Zaskritnout "Prepsat existujici" -> kliknout "Importovat vybrane" -> ocekavani: confirm dialog.

### D3: Import mapovani -- zadna napoveda k prirazeni sloupcu (pretrvava z v3)

- **Severity:** DULEZITE
- **Modul:** Import z Excelu
- **Pohled:** Bezny uzivatel
- **Co a kde:** Mapovaci stranka zobrazuje skupiny poli s dropdown selectory, ale u zadneho pole neni tooltip/napoveda. "Podil SCD", "LV" -- uzivatel nevi co to znamena.
- **Dopad:** Nezkuseny uzivatel muze spatne prirazovat sloupce.
- **Reseni:** Pridat `title` atribut na kazdou label s vysvetlenim. Napr.: "Podil SCD = spoluvlastnicky podil na spolecnych castech domu".
- **Varianty:** Info ikonka (i) s tooltip.
- **Kde v kodu:** `app/templates/partials/import_mapping_fields.html:33-35`
- **Narocnost:** Nizka ~15 min
- **Zavislosti:** --
- **Regrese riziko:** Nizke
- **Rozhodnuti:** Opravit
- **Jak otestovat:** Na mapovaci strance najet mysi na label pole -> ocekavani: tooltip s vysvetlenim.

### D4: Import kontaktu -- hledani bez normalizace diakritiky (pretrvava z v3)

- **Severity:** DULEZITE
- **Modul:** Import kontaktu
- **Pohled:** Bezny uzivatel, Data quality
- **Co a kde:** Hledani na nahledove strance importu kontaktu pouziva proste `q.toLowerCase()` JavaScript porovnani. Hledani "novak" nenajde "Novak" (s hackem).
- **Dopad:** Uzivatel nevi ze hledani nefunguje s diakritikou.
- **Reseni:** Pridat JS funkci `str.normalize('NFD').replace(/[\u0300-\u036f]/g, '')` a pouzit v searchRows.
- **Varianty:** --
- **Kde v kodu:** `app/templates/owners/contact_import_preview.html:229-238`
- **Narocnost:** Nizka ~5 min
- **Zavislosti:** --
- **Regrese riziko:** Nizke
- **Rozhodnuti:** Opravit
- **Jak otestovat:** Zadat "novak" (bez hacku) -> ocekavani: najde "Novak". Aktualne: nenajde.

### D7: Ciselniky -- klikaci oblast na kartach neni zjevne (pretrvava z v3)

- **Severity:** DULEZITE
- **Modul:** Administrace (ciselniky)
- **Pohled:** UI/UX designer, Bezny uzivatel
- **Co a kde:** Karty ciselniku jsou `<button>` elementy s hover efektem, ale vizualne vypadaji jako staticke informacni karty. Chybi vizualni indikator klikatelnosti (sipka, chevron).
- **Dopad:** Novy uzivatel nemuze intuitivne poznat ze na karty jde kliknout.
- **Reseni:** Pridat chevron ikonu (>) na pravou stranu kazde karty.
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

  Navrhovany stav:
  +----------------------------+
  | [icon] Typ prostoru      > |
  |         4 polozek          |
  +----------------------------+
  ```

### D10: Administrace purge -- kaskadove varovani se ukazuje az po zasknuti (castecne opraveno z v3)

- **Severity:** DULEZITE
- **Modul:** Administrace (purge)
- **Pohled:** Error recovery
- **Co a kde:** Kaskadove varovani je nyni implementovano (JS `purgeHandleOwnersDeps` + `purge-cascade-warn` element), ale je `hidden` a zobrazi se AZ po zasknuti checkboxu "Vlastnici". Uzivatel pred zaskrinutim nevidi ze smazani vlastniku kaskadove maze i hlasovani a dane.
- **Dopad:** Uzivatel nemuze ucínit informovane rozhodnuti PRED kliknutim na checkbox.
- **Reseni:** Zobrazit text kaskadovych zavislosti jako permanentni popis u kazde kategorie (maly text pod labelem), ne jako skryty element.
- **Varianty:** (A) Permanentni popis, (B) tooltip na label.
- **Kde v kodu:** `app/templates/administration/purge.html:48-49`
- **Narocnost:** Nizka ~10 min
- **Zavislosti:** --
- **Regrese riziko:** Nizke
- **Rozhodnuti:** Opravit
- **Jak otestovat:** Otevrit stranku Smazat data -> u kategorie "Vlastnici" ocekavani: text o kaskadovem mazani viditelny PRED zaskrinutim.
- **Mockup:**
  ```
  Soucasny stav:
  [ ] Vlastnici (447)
      Vsichni vlastnici v evidenci
      (varovani se zobrazi AZ po zasknuti)

  Navrhovany stav:
  [ ] Vlastnici (447)
      Vsichni vlastnici v evidenci
      Smaže i: hlasování, daňové podklady, sync data
  ```

### D11: Ticha konverze nevalidnich ciselnych vstupu na NULL (pretrvava z v3)

- **Severity:** DULEZITE
- **Modul:** Jednotky
- **Pohled:** Data quality
- **Co a kde:** Pri editaci jednotky se nevalidni cisla tise konvertuji na NULL bez varovani. Uzivatel zada "abc" do pole podilu a pole se ulozi jako prazdne.
- **Dopad:** Uzivatel si mysli ze data ulozil spravne.
- **Reseni:** Validovat client-side (`type="number" min="0"`), server-side vracet warning pri nevalidnim vstupu.
- **Kde v kodu:** `app/routers/units.py`
- **Narocnost:** Nizka ~15 min
- **Zavislosti:** --
- **Regrese riziko:** Nizke
- **Rozhodnuti:** Opravit

### D12: Rozesilani upload -- formular skryva submit tlacitko (pretrvava z v3)

- **Severity:** DULEZITE
- **Modul:** Hromadne rozesilani
- **Pohled:** Bezny uzivatel, UI/UX designer
- **Co a kde:** Na strance `tax/upload.html` je tlacitko "Nahrat a zpracovat" `hidden` a zobrazi se teprve po vyplneni nazvu I vyberu souboru.
- **Dopad:** Uzivatel ktery nejdriv vybere soubory a pak ceka netuzi ze musi vyplnit jeste nazev.
- **Reseni:** Zobrazit tlacitko vzdy, ale ve stavu `disabled` s `opacity-50`.
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
  (tlacitko "Nahrat" je hidden)

  Navrhovany stav:
  [Nazev: ______] [Soubory: ______]  [Nahrat a zpracovat (disabled)] [Zrusit]
  ```

### D13: Ciselniky -- editace polozky s usage > 0 bez vysvetleni (pretrvava z v3)

- **Severity:** DULEZITE
- **Modul:** Administrace (ciselniky)
- **Pohled:** UI/UX designer
- **Co a kde:** Polozka s usage > 0 je zobrazena jako plain text bez moznosti editace. Ale neni zadny vizualni indikator proc nejde editovat.
- **Dopad:** Uzivatel chce zmenit hodnotu ciselniku ale nemuze a nevi proc.
- **Reseni:** Pridat `title` atribut: "Pouzivano u X zaznamu -- nelze upravit."
- **Varianty:** --
- **Kde v kodu:** `app/templates/administration/code_lists.html:92-96`
- **Narocnost:** Nizka ~5 min
- **Zavislosti:** --
- **Regrese riziko:** Nizke
- **Rozhodnuti:** Opravit

### D14 (NOVY): Dashboard aktivita -- modul zobrazuje anglicke/raw nazvy

- **Severity:** DULEZITE
- **Modul:** Prehled (Dashboard)
- **Pohled:** Bezny uzivatel
- **Co a kde:** V tabulce posledni aktivity na dashboardu (`dashboard_activity_body.html:4`) se sloupec "Modul" zobrazuje jako raw hodnota z DB: `dane`, `tax`, `sprava`, `hlasovani`, `owners`, `voting`. Uzivatel vidi technicke anglicke nazvy misto ceskych popisku.
- **Dopad:** Bezny uzivatel nerozumi technicke terminologii. "dane" vs "tax" -- proc jsou ruzne?
- **Reseni:** V sablone nebo routeru prekladat moduly na ceske nazvy pomoci mapovani: `{"dane": "Rozesilani", "tax": "Rozesilani", "owners": "Vlastnici", "voting": "Hlasovani", "sprava": "Administrace", "units": "Jednotky", "sync": "Kontroly"}`.
- **Varianty:** (A) Jinja2 macro/filtr v sablone, (B) Preklad v routeru pri tvorbe unified listu.
- **Kde v kodu:** `app/templates/partials/dashboard_activity_body.html:4`, `app/routers/dashboard.py:178-198`
- **Narocnost:** Nizka ~10 min
- **Zavislosti:** --
- **Regrese riziko:** Nizke
- **Rozhodnuti:** Opravit
- **Jak otestovat:** Otevrit dashboard -> tabulka posledni aktivity -> sloupec Modul -> ocekavani: ceske nazvy.
- **Mockup:**
  ```
  Soucasny stav:
  | Datum      | Modul    | Popis          |
  | 19.03.     | dane     | Session XY     |
  | 19.03.     | tax      | Document AB    |
  | 19.03.     | sprava   | Backup         |

  Navrhovany stav:
  | Datum      | Modul       | Popis          |
  | 19.03.     | Rozesílání  | Session XY     |
  | 19.03.     | Rozesílání  | Document AB    |
  | 19.03.     | Administrace| Backup         |
  ```

### D15 (NOVY): Dashboard aktivita -- radky nejsou klikaci

- **Severity:** DULEZITE
- **Modul:** Prehled (Dashboard)
- **Pohled:** Business analytik, Bezny uzivatel
- **Co a kde:** Radky v tabulce posledni aktivity na dashboardu (`dashboard_activity_body.html`) jsou plain text `<tr>` bez odkazu. Uzivatel vidi "Session XY" ale nemuze na ni kliknout pro prechod na detail.
- **Dopad:** Uzivatel musi rucne navigovat do modulu a najit danou entitu. Dashboard slouzi jen k informaci, ne k navigaci.
- **Reseni:** Pridat sloupec s klikacim odkazem na detail entity (vlastnik, hlasovani, rozesilani). ActivityLog ma `entity_type` a `entity_id` -- pouzit pro sestaveni URL. EmailLog ma `session_id` -- pouzit pro odkaz na rozesilku.
- **Varianty:** (A) Cely radek klikaci (hover efekt), (B) Ikona odkazu v poslednim sloupci.
- **Kde v kodu:** `app/templates/partials/dashboard_activity_body.html`, `app/routers/dashboard.py:174-198`
- **Narocnost:** Stredni ~30 min
- **Zavislosti:** Nutne overit ze ActivityLog ma spravne `entity_type`/`entity_id` pro vsechny typy entit.
- **Regrese riziko:** Nizke
- **Rozhodnuti:** Potreba rozhodnuti uzivatele (varianta klikaci radek vs ikona)
- **Jak otestovat:** Na dashboardu kliknout na radek aktivity -> ocekavani: prechod na detail entity.

---

## DROBNE

### Dr2: Import nahled -- "Potvrdit a ulozit" bez confirm dialogu (pretrvava z v3)

- **Severity:** DROBNE
- **Modul:** Import vlastniku
- **Pohled:** Error recovery
- **Co a kde:** Tlacitko "Potvrdit a ulozit" na nahledove strance importu vlastniku spusti destruktivni akci bez `data-confirm` dialogu.
- **Dopad:** Uzivatel muze nahodnym kliknutim spustit import.
- **Reseni:** Pridat `data-confirm` na formular.
- **Kde v kodu:** `app/templates/owners/import_preview.html:19-24`
- **Narocnost:** Nizka ~5 min
- **Zavislosti:** --
- **Regrese riziko:** Nizke
- **Rozhodnuti:** Opravit

### Dr3: Import kontaktu -- "Vybrat vse se zmenami" label nekoresponduje s filtrovanym stavem (pretrvava z v3)

- **Severity:** DROBNE
- **Modul:** Import kontaktu
- **Pohled:** Bezny uzivatel
- **Co a kde:** Checkbox label rika "Vybrat vse se zmenami" i pri aktivnim filtru. Melo by byt "Vybrat vsechny zobrazene".
- **Dopad:** Uzivatel muze importovat vice zaznamu nez zamyslel.
- **Reseni:** Dynamicky zmenit label checkboxu pri aktivnim filtru.
- **Kde v kodu:** `app/templates/owners/contact_import_preview.html:68-71`
- **Narocnost:** Nizka ~5 min
- **Zavislosti:** --
- **Regrese riziko:** Nizke
- **Rozhodnuti:** Opravit

### Dr4: Nekonzistentni empty states (pretrvava z v3)

- **Severity:** DROBNE
- **Modul:** Cela aplikace
- **Pohled:** UI/UX designer
- **Co a kde:** Dashboard ma nyni dobre CTA pro prazdny stav. Ale dalsi moduly stale maji minimalni empty states: `tax/index.html:126` -- "Zadne rozesilani v tomto stavu." bez ikony a CTA.
- **Dopad:** Pri prvnim pouziti modulu uzivatel nemuze intuitivne zacit.
- **Reseni:** Zavest jednotny vzor: ikona + text + primarni CTA tlacitko.
- **Kde v kodu:** Vice souboru
- **Narocnost:** Nizka ~20 min
- **Zavislosti:** --
- **Regrese riziko:** Nizke
- **Rozhodnuti:** Opravit

### Dr5: Import mapovani -- "Data od radku" bez vysvetleni (pretrvava z v3)

- **Severity:** DROBNE
- **Modul:** Import z Excelu
- **Pohled:** Bezny uzivatel
- **Co a kde:** Pole "Data od radku" nema tooltip.
- **Dopad:** Spatne nastaveni start_row vede k chybnym datum.
- **Reseni:** Pridat `title` atribut: "Cislo radku v Excelu odkud zacinaji data (1 = hlavicka)".
- **Kde v kodu:** `app/templates/owners/owner_import_mapping.html:46`, `app/templates/owners/contact_import_mapping.html:43`
- **Narocnost:** Nizka ~2 min
- **Zavislosti:** --
- **Regrese riziko:** Nizke
- **Rozhodnuti:** Opravit

### Dr7: Flash zpravy -- dva ruzne systemy (pretrvava z v3)

- **Severity:** DROBNE
- **Modul:** Cela aplikace
- **Pohled:** UI/UX designer
- **Co a kde:** Globalni `data-auto-dismiss` (5s) vs inline setTimeout (ruzne casy).
- **Dopad:** Nekonzistentni UX.
- **Reseni:** Sjednotit na jeden system.
- **Kde v kodu:** `app/templates/base.html:135`, ruzne inline sablony
- **Narocnost:** Nizka ~15 min
- **Zavislosti:** --
- **Regrese riziko:** Nizke
- **Rozhodnuti:** Opravit

### Dr8: Rozesilka send -- checkbox stav v sessionStorage (pretrvava z v3)

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

### Dr9: Import mapovani -- barvy mapovani bez legendy (pretrvava z v3)

- **Severity:** DROBNE
- **Modul:** Import z Excelu
- **Pohled:** Bezny uzivatel
- **Co a kde:** Selectory v mapovani maji ruzne barvy okraju (modre = ulozene, zelene = auto-matched, cervene = chybi), ale neni legenda.
- **Dopad:** Uzivatel nevi co barvy znamenaji.
- **Reseni:** Pridat legendu pod stats bar.
- **Kde v kodu:** `app/templates/partials/import_mapping_fields.html:40-43`
- **Narocnost:** Nizka ~10 min
- **Zavislosti:** --
- **Regrese riziko:** Nizke
- **Rozhodnuti:** Opravit
- **Mockup:**
  ```
  Navrhovany stav pod stats barem:
  Legenda: [modre] = ulozene z minule  [zelene] = auto  [cervene] = chybi
  ```

### Dr11: Formatovani dat -- nekonzistentni format data/casu (pretrvava z v3)

- **Severity:** DROBNE
- **Modul:** Cela aplikace
- **Pohled:** UI/UX designer
- **Co a kde:** Ruzne formaty: `dd.mm.YYYY` (hlasovani datumy) vs `dd.mm.YYYY HH:MM` (aktivita) vs `dd.mm.YYYY HH:MM:SS` (nekde jinde). Nekonzistentni.
- **Dopad:** Vizualni nekonzistence.
- **Reseni:** Sjednotit: `dd.mm.YYYY` pro samotna data, `dd.mm.YYYY HH:MM` pro timestampy. Nikdy `:SS`.
- **Kde v kodu:** Ruzne sablony
- **Narocnost:** Nizka ~15 min
- **Zavislosti:** --
- **Regrese riziko:** Nizke
- **Rozhodnuti:** Opravit

### Dr12: Ciselniky -- emailove sablony nemaji napovedu pro promenne (pretrvava z v3)

- **Severity:** DROBNE
- **Modul:** Administrace (ciselniky)
- **Pohled:** Bezny uzivatel
- **Co a kde:** Pole textu emailu nema napovedu ke klicovym promennym. Uzivatel nevi jake promenne muze pouzit.
- **Dopad:** Uzivatel vytvori sablonu bez promennych.
- **Reseni:** Pridat napovedu pod textarea: "Dostupne promenne: {rok} = rok rozesilani".
- **Kde v kodu:** `app/templates/administration/code_lists.html:179-182`
- **Narocnost:** Nizka ~5 min
- **Zavislosti:** --
- **Regrese riziko:** Nizke
- **Rozhodnuti:** Opravit

### Dr14 (NOVY): Kontroly -- tab prepinani neni URL-driven

- **Severity:** DROBNE
- **Modul:** Kontroly (sync)
- **Pohled:** UI/UX designer
- **Co a kde:** Na strance `/synchronizace` se taby (Kontrola vlastniku, Kontrola podilu) prepinaji client-side pres `switchTab()` JavaScript funkci. Neni to URL-driven -- pri reloadu stranky se vzdy zobrazi prvni tab. Query parametr `?tab=podily` nema efekt.
- **Dopad:** Uzivatel ktery pracuje v druhem tabu po reloadu ztraci kontext.
- **Reseni:** (A) Pridat `?tab=podily` query parametr a inicializovat spravny tab v JS pri nacteni, nebo (B) pouzit hash fragmenty (#podily) s client-side inicializaci.
- **Varianty:** Hash je jednodussi (zadna zmena v routeru).
- **Kde v kodu:** `app/templates/sync/index.html:20-36`, `app/routers/sync.py`
- **Narocnost:** Nizka ~10 min
- **Zavislosti:** --
- **Regrese riziko:** Nizke
- **Rozhodnuti:** Opravit
- **Jak otestovat:** (1) Prepnout na tab "Kontrola podilu". (2) Refreshnout stranku. (3) Ocekavani: druhy tab je stale aktivni. Aktualne: vrati se na prvni tab.

### Dr15 (NOVY): Tailwind config -- console error na kazde strance

- **Severity:** DROBNE
- **Modul:** Cela aplikace
- **Pohled:** Performance analytik
- **Co a kde:** V `base.html:12` je `<script>tailwind.config={darkMode:'class'}</script>` PRED nacitanim Tailwind CDN (`base.html:13`). V dobe vykonani skriptu promenna `tailwind` jeste neexistuje. Kazde nacteni stranky loguje do console: `ReferenceError: tailwind is not defined`. Stejna chyba v `error.html:12`.
- **Dopad:** Konzole je zahlcena chybami. Dark mode konfigurace se nemusi spravne aplikovat. Developeri jsou zahlceni falesnymi chybami.
- **Reseni:** Presunout konfiguraci ZA nacteni CDN, nebo pouzit doporuceny zpusob z Tailwind CDN: `<script src="https://cdn.tailwindcss.com"></script>` nasledovany `<script>tailwind.config = {darkMode: 'class'}</script>`.
- **Varianty:** --
- **Kde v kodu:** `app/templates/base.html:12-13`, `app/templates/error.html:12-13`
- **Narocnost:** Nizka ~2 min (jen prohodit poradi dvou radku)
- **Zavislosti:** --
- **Regrese riziko:** Nizke (ale otestovat dark mode po zmene)
- **Rozhodnuti:** Opravit
- **Jak otestovat:** (1) Otevrit libovolnou stranku. (2) Otevrit DevTools Console. (3) Ocekavani: zadna `tailwind is not defined` chyba.
- **Mockup:**
  ```
  Soucasny stav (radky 12-13):
  <script>tailwind.config={darkMode:'class'}</script>     <!-- tailwind jeste neexistuje! -->
  <script src="https://cdn.tailwindcss.com"></script>

  Navrhovany stav:
  <script src="https://cdn.tailwindcss.com"></script>
  <script>tailwind.config={darkMode:'class'}</script>     <!-- tailwind uz je definovany -->
  ```

### Dr16 (NOVY): Chybejici favicon -- 404 na kazdem requestu

- **Severity:** DROBNE
- **Modul:** Cela aplikace
- **Pohled:** UI/UX designer
- **Co a kde:** Prohlizec automaticky pozaduje `/favicon.ico` ale server vraci 404. Kazdy page load generuje zbytecny 404 error v logu.
- **Dopad:** Zahlceni serveru zbytecnymi 404 requesty. Absence faviconu vypada neprofesionalne. Tab v prohlizeci nema ikonu.
- **Reseni:** Pridat minimalni favicon (16x16 SVG nebo PNG) do `app/static/` a pridat `<link rel="icon">` do `base.html`.
- **Varianty:** SVG favicon (moderni, skalovatelny) vs PNG favicon (maximalní kompatibilita).
- **Kde v kodu:** `app/templates/base.html` (chybi `<link rel="icon">`), `app/static/` (chybi soubor)
- **Narocnost:** Nizka ~10 min
- **Zavislosti:** --
- **Regrese riziko:** Nizke
- **Rozhodnuti:** Opravit

---

## NOVE NALEZY -- specificke pro tuto revizi

### Pozitivni zmeny od v3

1. **Snapshot warning opraveno** -- banner nyni obsahuje primo tlacitko "Pregenerovat listky" s confirm dialogem. Uzivatel ma jasnou akci.

2. **Neodevzdane export implementovan** -- `_voting_header.html` nyni podminene generuje export odkaz pro neodevzdane listky (`/hlasovani/{id}/neodevzdane/exportovat`).

3. **Responsivni sidebar** -- hamburger menu pro mobilni zarizeni implementovano (md:hidden toggle + overlay + close icon). Sidebar je skryty na mobilech s moznosti rozblit.

4. **Smazat data vizualne odlisena** -- dle git commitu opraveno, karta ma jiny vizualni styl.

5. **Import stepper klikaci** -- dle git commitu opraveno, stepper kroky jsou klikaci.

6. **Back label na rozesilce opraveno** -- `tax/session.py` ma dynamicky back_label s if/elif retezcem.

7. **Tax sessions na dashboardu** -- castecne opraveno. Dashboard pouziva `GROUP BY send_status` pro pocty a per-status subquery pro latest session. Vyrazne lepsi nez nacitani vsech sessions.

8. **Kontroly tab prepinani** -- dve sekce na jedne strance jsou nyni reseny jako taby s client-side prepinanim. Vizualne ciste, i kdyz URL-driven chybi (viz Dr14).

---

## Top 5 doporuceni (podle dopadu)

| # | Navrh | Dopad | Slozitost | Cas | Zavisi na | Rozhodnuti | Priorita |
|---|-------|-------|-----------|-----|-----------|------------|----------|
| 1 | Batch query v tax sending (K1) | Vysoky -- dramaticke zrychleni | Stredni | ~30 min | -- | Opravit | HNED |
| 2 | File exists check v import wizardu (K2) | Vysoky -- prevence 500 chyb | Nizka | ~10 min | -- | Opravit | HNED |
| 3 | Specificka chyba validate_upload v contact importu (K3) | Vysoky -- prevence frustrace | Nizka | ~5 min | -- | Opravit | HNED |
| 4 | Dashboard SQL agregace misto eager load (K4) | Stredni -- skaluje s poctem listek | Stredni | ~30 min | -- | Opravit | BRZY |
| 5 | Modul nazvy v cestine na dashboardu (D14) | Stredni -- zakladni srozumitelnost | Nizka | ~10 min | -- | Opravit | HNED |

---

## Quick wins (nizka slozitost, okamzity efekt)

- [ ] Tailwind config poradi radku v base.html + error.html (Dr15) -- 2 radky prohodit
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
- [ ] Purge kaskadove upozorneni permanentne viditelne (D10) -- odstranit `hidden` class
- [ ] Modul nazvy preklad na dashboardu (D14) -- 10 radku Python/Jinja2
- [ ] Tab switching URL-driven na kontrolach (Dr14) -- 5 radku JS
- [ ] Pridani faviconu (Dr16) -- 1 soubor + 1 HTML tag
- [ ] Sjednotit flash auto-dismiss timeout (Dr7) -- 5 radku
