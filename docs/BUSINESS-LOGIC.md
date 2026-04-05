# SVJ Aplikace — Business Logic Reference

> Technicky dokument s odkazy na zdrojovy kod (soubor:radek).
> Posledni aktualizace: 2026-04-05

---

## 1. Datovy model — entity a vztahy

### 1.1 Vlastnici a jednotky

| Entity | Tabulka | Soubor |
|--------|---------|--------|
| `Owner` | `owners` | `app/models/owner.py:17` |
| `Unit` | `units` | `app/models/owner.py:102` |
| `OwnerUnit` | `owner_units` | `app/models/owner.py:129` |
| `Proxy` | `proxies` | `app/models/owner.py:150` |

**Klicove vztahy:**
- Owner <-> Unit je M:N pres `OwnerUnit` (vlastnik muze vlastnit vice jednotek, jednotka muze mit vice vlastniku)
- `OwnerUnit.valid_to IS NULL` = aktivni vlastnictvi; `valid_to != NULL` = historicke
- `Owner.current_units` (property, `owner.py:79`) — filtrovane aktivni vazby, razene dle `unit_number`
- `Unit.current_owners` (property, `owner.py:121`) — filtrovane aktivni vazby

**Typ vlastnika** (`OwnerType`, `owner.py:12`):
- `PHYSICAL` — fyzicka osoba (identifikace pres rodne cislo)
- `LEGAL_ENTITY` — pravnicka osoba (identifikace pres IC)
- Detekce: IC = 8 cifer bez lomitka (`excel_import.py:135`); RN = format `XXXXXX/XXXX` nebo 10 cifer (`excel_import.py:127`)

**Jmeno vlastnika:**
- `display_name` (property, `owner.py:64`) — format "titul prijmeni jmeno"
- `name_with_titles` — DB sloupec pro index, nepouzivat v sablonach
- `name_normalized` — lowercase bez diakritiky, format "prijmeni jmeno" (`excel_import.py:170`)
- Normalizace diakritiky: `unicodedata.normalize("NFD")` + odstraneni `Mn` kategorie (`utils.py:9-12`)

**Vlastnictvi jednotky (`OwnerUnit`):**
- `ownership_type` — typ vlastnictvi (SJM, VL, SJVL, ...). Hodnota "ANO" z Excelu se normalizuje na "SJM" (`excel_import.py:148-155`)
- `share` — podil vlastnika na jednotce (default 1.0, pri vice vlastnicich se deli)
- `votes` — pocet hlasu (= `podil_scd` jednotky * `share`; prepocitava se pri zmene)

### 1.2 Hlasovani

| Entity | Tabulka | Soubor |
|--------|---------|--------|
| `Voting` | `votings` | `app/models/voting.py:34` |
| `VotingItem` | `voting_items` | `app/models/voting.py:58` |
| `Ballot` | `ballots` | `app/models/voting.py:71` |
| `BallotVote` | `ballot_votes` | `app/models/voting.py:95` |

**Klicove atributy Voting:**
- `quorum_threshold` — ulozeno jako 0-1 (napr. 0.5 = 50%). Formular posila 0-100, router deli `/100` (`voting.py:291-295`)
- `partial_owner_mode` — `"shared"` (SJM sdileny listek) nebo `"separate"` (kazdy vlastnik zvlast)
- `total_votes_possible` — celkovy pocet hlasu vsech listku
- `import_column_mapping` — JSON string, ulozene mapovani sloupcu z posledniho importu

### 1.3 Rozesílani (Tax/Send)

| Entity | Tabulka | Soubor |
|--------|---------|--------|
| `TaxSession` | `tax_sessions` | `app/models/tax.py:35` |
| `TaxDocument` | `tax_documents` | `app/models/tax.py:59` |
| `TaxDistribution` | `tax_distributions` | `app/models/tax.py:77` |

**Klicove atributy TaxSession:**
- `send_batch_size` — pocet emailu v davce (default 10)
- `send_batch_interval` — pauza mezi davkami v sekundach (default 5)
- `send_confirm_each_batch` — zda cekat na potvrzeni po kazde davce
- `test_email_passed` — zda prosel testovaci email

### 1.4 Synchronizace

| Entity | Tabulka | Soubor |
|--------|---------|--------|
| `SyncSession` | `sync_sessions` | `app/models/sync.py:28` |
| `SyncRecord` | `sync_records` | `app/models/sync.py:47` |

### 1.5 Kontrola podilu

| Entity | Tabulka | Soubor |
|--------|---------|--------|
| `ShareCheckSession` | `share_check_sessions` | `app/models/share_check.py:26` |
| `ShareCheckRecord` | `share_check_records` | `app/models/share_check.py:46` |
| `ShareCheckColumnMapping` | `share_check_column_mappings` | `app/models/share_check.py:61` |

### 1.6 Administrace

| Entity | Tabulka | Soubor |
|--------|---------|--------|
| `SvjInfo` | `svj_info` | `app/models/administration.py:9` |
| `SvjAddress` | `svj_addresses` | `app/models/administration.py:36` |
| `BoardMember` | `board_members` | `app/models/administration.py:47` |
| `CodeListItem` | `code_list_items` | `app/models/administration.py:60` |
| `EmailTemplate` | `email_templates` | `app/models/administration.py:74` |

**SvjInfo.total_shares** — deklarovany celkovy pocet hlasu (dle prohlaseni vlastniku). Pouziva se pro vypocet kvora a procentualniho podilu.

**SvjInfo — sdilena konfigurace odesilani** (nove od 2026-03-28):
- `send_batch_size` (default 10) — pocet prijemcu v jedne davce
- `send_batch_interval` (default 5) — pocet sekund pauzy mezi davkami
- `send_confirm_each_batch` (default False) — zda cekat na potvrzeni po kazde davce
- `send_test_email_address` — posledni pouzita adresa pro testovaci email
- Tato konfigurace je sdilena pro VSECHNY odesilacie moduly (rozesílani i nesrovnalosti)

### 1.7 Spolecne / logy

| Entity | Tabulka | Soubor |
|--------|---------|--------|
| `EmailLog` | `email_logs` | `app/models/common.py:16` |
| `ImportLog` | `import_logs` | `app/models/common.py:33` |
| `ActivityLog` | `activity_logs` | `app/models/common.py:57` |

### 1.8 Evidence plateb

| Entity | Tabulka | Soubor |
|--------|---------|--------|
| `VariableSymbolMapping` | `variable_symbol_mappings` | `app/models/payment.py:65` |
| `PrescriptionYear` | `prescription_years` | `app/models/payment.py:112` |
| `Prescription` | `prescriptions` | `app/models/payment.py:129` |
| `PrescriptionItem` | `prescription_items` | `app/models/payment.py:151` |
| `BankStatement` | `bank_statements` | `app/models/payment.py:167` |
| `Payment` | `payments` | `app/models/payment.py:190` |
| `BankStatementColumnMapping` | `bank_statement_column_mappings` | `app/models/payment.py:230` |
| `PaymentAllocation` | `payment_allocations` | `app/models/payment.py:242` |
| `Settlement` | `settlements` | `app/models/payment.py:263` |
| `SettlementItem` | `settlement_items` | `app/models/payment.py:284` |
| `UnitBalance` | `unit_balances` | `app/models/payment.py:85` |

**Hierarchie predpisu:**
- `PrescriptionYear` (rok) -> `Prescription` (mesicni predpis pro jednotku/prostor) -> `PrescriptionItem` (polozka: provozni, fond oprav, sluzby)
- Kazda `Prescription` je vazana na `unit_id` NEBO `space_id` a ma `variable_symbol` (VS pro platby)
- `PrescriptionItem.category` — 3 kategorie: `provozni` (provozni naklady), `fond_oprav` (fond oprav/udrzby), `sluzby` (sluzby)

**Bankovni vypisy a platby:**
- `BankStatement` (vypis) -> `Payment` (jednotliva transakce)
- `Payment.direction` — `INCOME` (prijem) nebo `EXPENSE` (vydej)
- `Payment.match_status` — `AUTO_MATCHED`, `SUGGESTED`, `MANUAL`, `UNMATCHED`
- `Payment.variable_symbol` (sloupec `vs`) — variabilni symbol pro parovani s predpisy
- `Payment.notified_at` — timestamp odeslani upozorneni na nesrovnalost (nove od 2026-03-28)
- `BankStatement.discrepancy_test_passed` — zda prosel testovaci email pro nesrovnalosti

**Alokace plateb:**
- `PaymentAllocation` — M:N vazba `Payment` <-> `Prescription` (jedna platba muze pokryt vice predpisu, jeden predpis muze byt pokryt vice platbami)
- `PaymentAllocation` podporuje i vazbu na `space_id` (pro prostory)
- `amount` na alokaci urcuje castku prirazenou konkretnimu predpisu

**Zustatky a vyuctovani:**
- `UnitBalance` — zustatek na jednotce/prostoru pro dany rok (kladny = dluh, zaporny = preplatek)
- `UnitBalance` podporuje `space_id` — zustatek muze byt i pro prostor (nejenom jednotku)
- `Settlement` -> `SettlementItem` — rocni vyuctovani s detailnimi polozkami
- Vzorec vyuctovani: `vysledek = (mesicni_predpis * 12) + pocatecni_zustatek - celkem_zaplaceno`

**Mapovani variabilnich symbolu:**
- `VariableSymbolMapping` — vazba VS -> jednotka NEBO prostor. Podporuje `unit_id` i `space_id`
- Jeden VS muze byt sdilen vice vlastniky (SJM), jedna jednotka muze mit vice VS (historicke zmeny)
- Slouzi pro automaticke parovani plateb s predpisy
- `SymbolSource` — zdroj VS: `AUTO` (z importu), `MANUAL` (rucne zadany), `LEGACY` (historicky)

### 1.9 Prostory a najemci (nove od 2026-03)

| Entity | Tabulka | Soubor |
|--------|---------|--------|
| `Space` | `spaces` | `app/models/space.py:30` |
| `Tenant` | `tenants` | `app/models/space.py:59` |
| `SpaceTenant` | `space_tenants` | `app/models/space.py:166` |

**Space (prostor):**
- Reprezentuje nebytovy prostor SVJ (sklep, garaz, pradelna, kancelar...)
- `space_number` (Integer, unique) — cislo prostoru
- `designation` — nazev/urceni prostoru (napr. "Sklep", "Garaz")
- `status` (`SpaceStatus`): `RENTED` (pronajato), `VACANT` (volne), `BLOCKED` (zablokovano — utilita/spolecny prostor)
- `blocked_reason` — duvod zablokovani (napr. "Automaticky detekovano z nazvu")
- `active_tenant_rel` (property) — aktualni aktivni najemni vztah

**Tenant (najemce):**
- Muze byt propojen s existujicim vlastnikem (`owner_id` FK -> Owner) nebo samostatny
- Kdyz je propojeny s Owner: `display_name`, `resolved_email`, `resolved_phone` delegují na Owner
- Kdyz je samostatny: vlastni `first_name`, `last_name`, `email`, `phone` atd.
- `is_linked` (property) — True pokud je propojeny s vlastnikem
- Sdili `OwnerType` enum s Owner (fyzicka/pravnicka osoba)
- `data_source` — odkud najemce pochazi (`manual`, `import`)

**SpaceTenant (najemni vztah):**
- Vazba `Space` <-> `Tenant` s detaily smlouvy
- `contract_number`, `contract_start`, `contract_end` — cislo a obdobi smlouvy
- `monthly_rent` (Float) — mesicni najem
- `variable_symbol` — VS pro platby najemneho
- `is_active` — aktivni/historicky vztah

**Auto-detekce blokovanych prostoru** (`space_import.py:26-30`):
- Klicova slova v nazvu: kocarkarna, ustredna, trezor, kotelna, strojovna, sklad odpadu, komora, rozvodna, chodba, schodiste, vytah, zasedaci, spolecna, technick, uklid
- Prostor s temito klicovymi slovy se automaticky nastavi jako `BLOCKED`

---

## 2. Stavove automaty

### 2.1 VotingStatus (`voting.py:12`)

```
DRAFT --[generovat listky]--> ACTIVE --[uzavrit]--> CLOSED
                                  \--[zrusit]--> CANCELLED
```

- `DRAFT` -> `ACTIVE`: automaticky pri prvnim generovani listku (`voting.py:667-668`)
- `ACTIVE` -> `CLOSED`/`CANCELLED`: manualne pres formular (`voting.py:986+`)
- Nelze se vratit z CLOSED/CANCELLED zpet

### 2.2 BallotStatus (`voting.py:26`)

```
GENERATED --[odeslat]--> SENT --[prijat]--> RECEIVED --[zpracovat]--> PROCESSED
                                                                         ^
                                                          [resetovat] ---+

GENERATED --[oznacit jako neplatny]--> INVALID
```

- `GENERATED`: listek vytvoren, ceka na odeslani
- `SENT`: listek odeslan vlastnikovi (datum v `sent_at`)
- `RECEIVED`: fyzicky listek prijat zpet
- `PROCESSED`: hlasy zpracovany a zaznamenany (datum v `processed_at`)
- `INVALID`: listek oznacen jako neplatny
- Reset: `PROCESSED` -> `GENERATED` (vymaze hlasy, `voting.py:1239+`)

### 2.3 SendStatus (`tax.py:19`) — rozesílani

```
DRAFT --[potvrdit prirazeni]--> READY --[zahajit rozeslani]--> SENDING
                                   ^                              |
                                   \--[znovu otevrit]-------------+
                                                                  +--[pozastavit]--> PAUSED
                                                                  |                    |
                                                                  |  +-[pokracovat]----+
                                                                  |  |
                                                                  \--+--[dokonceno]--> COMPLETED
```

- `DRAFT`: prace na prirazeni PDF -> vlastnikum
- `READY`: prirazeni potvrzeno, pripraveno k odeslani
- `SENDING`: probihajici rozesílani v pozadi (background thread)
- `PAUSED`: pozastaveno uzivatelem (nebo po restartu serveru, `tax.py:45-56`)
- `COMPLETED`: vsechny emaily odeslany
- Recovery pri restartu: `SENDING` -> `PAUSED` automaticky (`tax.py:45-56`)

### 2.4 MatchStatus (`tax.py:12`) — prirazeni PDF

```
UNMATCHED --[auto-match]--> AUTO_MATCHED --[potvrdit]--> CONFIRMED
                                              \--[rucne zmenit]--> MANUAL
```

### 2.5 EmailDeliveryStatus (`tax.py:27`)

```
PENDING --[zaradit do fronty]--> QUEUED --[odeslat]--> SENT
                                            \--[chyba]--> FAILED
                                                          \--[preskocit]--> SKIPPED
```

### 2.6 SyncStatus (`sync.py:12`) + SyncResolution (`sync.py:19`)

**Status:**
- `MATCH` — jmena se shoduji
- `NAME_ORDER` — jmena jsou prohozena (prijmeni/jmeno)
- `DIFFERENCE` — jmena se lisi
- `MISSING_CSV` — jednotka jen v DB, ne v CSV
- `MISSING_EXCEL` — jednotka jen v CSV, ne v DB

**Resolution:**
- `PENDING` -> `ACCEPTED` / `REJECTED` / `MANUAL_EDIT` / `EXCHANGED`

### 2.7 ShareCheckStatus (`share_check.py:13`) + ShareCheckResolution (`share_check.py:19`)

**Status:** `MATCH`, `DIFFERENCE`, `MISSING_DB`, `MISSING_FILE`
**Resolution:** `PENDING` -> `UPDATED` / `SKIPPED`

### 2.8 PaymentMatchStatus (`payment.py:48`)

```
UNMATCHED --[faze 1: VS exact]--> AUTO_MATCHED
          --[faze 2: jmeno+castka]--> SUGGESTED
          --[faze 3: VS prefix]--> SUGGESTED
          --[rucni prirazeni]--> MANUAL
```

- `AUTO_MATCHED` — VS presne odpovida predpisu (vysoka jistota)
- `SUGGESTED` — navrzen na zaklade jmena+castky nebo VS prefixu (vyzaduje potvrzeni)
- `MANUAL` — rucne prirazeno uzivatelem
- `UNMATCHED` — zadna shoda nenalezena

### 2.9 SpaceStatus (`space.py:21`)

```
VACANT --[prirazeni najemce]--> RENTED
       --[auto-detekce blok. prostoru]--> BLOCKED

RENTED --[ukonceni smlouvy]--> VACANT
BLOCKED --[rucne odblokovani]--> VACANT
```

- `RENTED` — prostor je pronajaty (existuje aktivni SpaceTenant)
- `VACANT` — prostor je volny
- `BLOCKED` — prostor neni pronajimatelny (utilita, spolecny prostor)

### 2.10 SettlementStatus (`payment.py:55`)

```
GENERATED --[odeslat]--> SENT --[zaplatit]--> PAID
                                             \--[po splatnosti]--> OVERDUE
```

---

## 3. Business procesy — kompletni workflow

### 3.1 Hlasovani per rollam

#### Krok 1: Vytvoreni hlasovani
- **Soubor:** `voting.py:275-360`
- Uzivatel vyplni: nazev, popis, kvorum (%), rezimy spoluvlastnictvi, data
- Nepovinny: upload Word sablony (.docx) pro automaticke parsovani bodu hlasovani
- Word parser (`word_parser.py:36-109`) extrahuje body hlasovani pomoci regexu:
  - Vzor "BOD 1: ..." nebo "1. ..." nebo ceske ordinalni cislovky ("Prvni bod hlasovani - ...")
  - Filtruje false-positive datumy ("19. ledna 2026")
  - Extrahuje metadata (nazev, popis, datumy zahajeni/ukonceni) z dokumentu (`word_parser.py:132-256`)
- Kvorum: formular posila 0-100, router deli `/100` pro ulozeni 0-1 (`voting.py:291-295`)

#### Krok 2: Generovani listku
- **Soubor:** `voting.py:492-671`
- Pro kazdeho aktivniho vlastnika s alespon 1 jednotkou se vytvori `Ballot` + `BallotVote` pro kazdy bod hlasovani

**SJM rezim "shared"** (`voting.py:508-625`):
1. Sestavi mapu `unit_id -> [vlastnici]` pro jednotky s typem vlastnictvi obsahujicim "SJM"
2. Paruje SJM spoluvlastniky pres connected components algoritmus — POUZE na jednotkach s PRESNE 2 SJM vlastniky
3. Neparovane SJM vlastniky seskupi dle identicke mnoziny SJM jednotek
4. Pro kazdy SJM par vytvori JEDEN sdileny listek:
   - `owner_id` = primarni vlastnik (dle `name_normalized` abecedne)
   - `total_votes` = SOUCET hlasu VSECH clenu (kazdy vlastnik ma svuj podil)
   - `units_text` = ciselny seznam jednotek (deduplikovane)
   - `shared_owners_text` = jmena vsech spoluvlastniku

**Rezim "separate":** Kazdy vlastnik dostane vlastni listek.

**Vypocet hlasu:**
- `total_votes = sum(ou.votes for ou in owner.current_units)` (`voting.py:641`)
- `ou.votes = unit.podil_scd` (nastaveno pri importu, `excel_import.py:475`)

#### Krok 3: Zpracovani hlasu
- **Rucne** (`voting.py:892-938`): Uzivatel vybere PRO/PROTI/ZDRZUJI pro kazdy bod
  - Kazdy `BallotVote` dostane `vote` (enum) + `votes_count` (vaha hlasu)
  - Listek se nastavi na `PROCESSED` + `processed_at`
- **Hromadne** (`voting.py:942-983`): Stejne hlasy na vice listku najednou
- **Import z Excelu** — viz sekce 3.1.1

#### Krok 4: Vysledky a kvorum
- **Soubor:** `voting.py:109-133`, `voting.py:157-201`
- Kvorum: `total_processed_votes / declared_shares >= voting.quorum_threshold`
  - `declared_shares` = `SvjInfo.total_shares` (deklarovane podily dle prohlaseni)
  - `total_processed_votes` = soucet `total_votes` zpracovanych listku s alespon 1 hlasem
- Per-item vysledky: PRO/PROTI/ZDRZUJI s procentualnim vyjadrenim vuci `declared_shares`
- Snapshot warning: detekce zda se zmenily hlasy od generovani (`voting.py:386-395`)

#### Krok 5: Uzavreni
- Status `ACTIVE` -> `CLOSED` nebo `CANCELLED` (`voting.py:986+`)

### 3.1.1 Import hlasovani z Excelu

- **Soubory:** `app/services/voting_import.py`, `voting.py` (import endpointy)

**Mapovani sloupcu** (`voting_import.py:10-16`):
```json
{
  "owner_col": 0,
  "unit_col": 2,
  "start_row": 2,
  "for_values": "1, ANO, YES, X, PRO",
  "against_values": "0, NE, NO, PROTI",
  "item_mappings": [
    {"item_id": 5, "for_col": 3, "against_col": 4}
  ]
}
```

**Parsovani hlasu** (`voting_import.py:63-128`):
- Podpora exaktni shody ("ANO", "1") i porovnani (">0", "<0", ">=1")
- Primarni sloupec (`for_col`): hodnota se porovna s for_values a against_values
- Sekundarni sloupec (`against_col`): logika INVERTOVANA (for_values -> PROTI)
- Nerozpoznane hodnoty: radek jde do `no_match` kategorie

**Parovani radku na listky** (`voting_import.py:199-363`):
1. Sestavi lookup `unit_number -> [ballot, ...]`
2. Pro kazdy radek: parsuje cislo jednotky (`"1098/115" -> 115`)
3. Najde listky pro danou jednotku
4. Disambiguace pri vice listcich na jednotce:
   - Porovna jmeno z Excelu s jmenem na listku (pomoci `name_normalized`)
   - Pri SJM: pokud je presne 2 SJM vlastniku, prida vyrazeneho partnera zpet
5. Propagace hlasu: pokud radek ma hlasy -> vsem listkum na jednotce (kazdy se svym `total_votes`)
6. Merge: pokud se ten samy listek objevi na vice radcich, hlasy se slouci (`seen_ballots`)

**Mody importu** (`voting_import.py:377-447`):
- **Append** (`clear_existing=False`): preskoci listky s existujicimi hlasy
- **Clear** (`clear_existing=True`): prepise vse; listky mimo import se resetuji na `GENERATED`

**Globalni mapovani:** ulozeno v `SvjInfo.voting_import_mapping` (`administration.py:17`); predvyplni se pri dalsim importu.

### 3.2 Rozesílani (Tax/Send)

#### Krok 1: Vytvoreni session + nahrani PDF
- **Soubor:** `tax.py:432-507`
- Uzivatel nahrava adresar s PDF soubory (danove vyuctovani)
- Pouze `.pdf` soubory se zpracuji; ostatni (`.DS_Store` atd.) se preskoci
- Soubory se ulozi synchronne, zpracovani bezi na pozadi (background thread)

#### Krok 2: Extrakce textu z PDF a auto-matching
- **Background thread:** `tax.py:627-864`
- **PDF extrakce** (`pdf_extractor.py`):
  - `parse_unit_from_filename()` (`pdf_extractor.py:189-195`): nazev souboru "115A.pdf" -> unit_number="115", unit_letter="A"
  - `extract_owner_from_tax_pdf()` (`pdf_extractor.py:23-31`): fulltext pres `pdfplumber`
  - `parse_owner_name()` (`pdf_extractor.py:150-186`): vzory "Vlastnik:", "Jmeno:", "Udaje o vlastnikovi:"
  - `parse_owner_names_from_details()` (`pdf_extractor.py:96-147`): parsuje sekci "Udaje o vlastnikovi" — jmena z SP radku (spoluvlastnicky podil)
  - `_merge_company_fragments()` (`pdf_extractor.py:77-93`): slije fragmenty nazvu firem rozdelene pres vice SP radku

- **Name matching** (`owner_matcher.py`):
  - Normalizace: odstraneni titulu (Ing., Mgr., ...), SJM prefixu, diakritiky, cesky stemming prijmeni (`owner_matcher.py:25-47`)
  - Cesky stemming: `-ova`, `-kova`, `-ovi`, `-ove`, `-kem` atd. (`owner_matcher.py:19-22`)
  - Porovnani: `SequenceMatcher.ratio()` + Jaccard koeficient slozek jmena (`owner_matcher.py:50-69`)
  - Surname stem check: pri globalni shode (`require_stem_overlap=True`) musi sdilet alespon 1 kmenove prijmeni (`owner_matcher.py:132-139`)

- **Logika matchingu** (`tax.py:700-758`):
  1. Pro kazde jmeno z PDF: pokusi se matchovat lokalne (vlastnici na dane jednotce, threshold 0.6)
  2. SJM prefix -> vsechny shody nad threshold; jinak jen nejlepsi
  3. Non-SJM: tez globalni match (vsichni vlastnici, threshold 0.75, `require_stem_overlap=True`)
  4. Pouzije lepsi z lokalniho/globalniho
  5. Nenalezeno -> `UNMATCHED` distribuce

- **Post-processing** (`tax.py:764-848`):
  - Pro nove nenadrazene dokumenty: zkopiruje prirazeni z existujicich dokumentu se stejnou jednotkou
  - Propaguje `email_address_used` z existujicich distribucí na nove

#### Krok 3: Manualni prirazeni (matching page)
- **Soubor:** `tax.py:964+`
- Uzivatel kontroluje a potvrzuje auto-match, rucne priradi nenadrazene
- Stavy: `AUTO_MATCHED` -> `CONFIRMED`, nebo `MANUAL` pro rucni prirazeni
- Spoluvlastnici: `_find_coowners()` (`tax.py:139-174`) — hleda spoluvlastniky na stejne jednotce s prekryvajicim se obdobim v danovem roce

#### Krok 4: Rozesílani emailu
- **Background thread:** `tax.py:2085-2214`
- Davkovy system: `batch_size` emailu, `batch_interval` sekund pauza
- Sdilene SMTP pripojeni per davka (`email_service.py:21-31`)
- Podpora pozastaveni/pokracovani/zruseni behem rozesílani
- Retry neuspiesnnych: opetovne odeslani jen `FAILED` prijemcu (`tax.py:2430+`)
- Deduplikace prijemcu pres `_build_recipients()` (`tax.py:221-300`): jeden prijemce muze mit vice dokumentu
- Podpora dualnich emailu (primarni + sekundarni)

### 3.3 Import vlastniku z Excelu

- **Soubory:** `app/services/excel_import.py`, `owners.py`
- Workflow: Upload -> Preview -> Confirm

#### Parsovani Excelu (`excel_import.py:300-349`)
- Ocekavany format: list "Vlastnici_SVJ", 31 sloupcu (A-AE)
- Klicove sloupce: A=cislo jednotky, L=jmeno, M=prijmeni, N=titul, O=RC/IC
- Parsovani cisla jednotky: `"1098/115" -> 115` (posledni cast za lomitkem)
- Detekce typu: IC (8 cifer) -> `LEGAL_ENTITY`, RC (format XXXXXX/XXXX) -> `PHYSICAL`

#### Seskupeni vlastniku (`excel_import.py:180-191`)
- Unikatni vlastnici se identifikuji pres `_owner_group_key()`:
  - Pokud ma RC/IC -> klic `"id:XXXXXXXX"`
  - Jinak -> klic `"name:prijmeni|jmeno"` (normalizovano)
- Jeden vlastnik muze mit vice radku (vice jednotek)

#### Ulozeni (`excel_import.py:352-494`)
- Faze 1: sesbirani a seskupeni radku
- Faze 2: vytvoreni DB zaznamu
  - Owner: kontaktni udaje se berou z prvniho radku, email/telefon se hleda pres vsechny radky
  - Unit: cache pro deduplikaci; existujici jednotky se pouziji
  - OwnerUnit: `votes = unit.podil_scd` (cely podil, `share=1.0`)
- Normalizace vlastnictvi: "ANO" -> "SJM"

### 3.4 Import kontaktu z Excelu

- **Soubory:** `app/services/contact_import.py`, `owners.py:273+`
- Workflow: Upload -> Background processing -> Preview -> Confirm

#### Format (`contact_import.py:6-13`)
- Sheet "ZU", data od radku 7
- Sloupce: 15=titul, 16=jmeno, 17=prijmeni, 19=RC/IC, 20-29=adresy, 30-32=kontakty

#### Matching (`contact_import.py:143-188`)
1. Primarni: shoda pres `name_normalized`
2. Fallback: RC/IC (normalizovane — bez mezer a lomitek)
3. Deduplikace: kazdy vlastnik se zpracuje jen jednou

#### Inteligentni routing kontaktu (`contact_import.py:218-256`)
- Pokud primarni kontakt je prazdny -> vyplni primarni
- Pokud Excel odpovida primarnimu NEBO sekundarnimu -> preskoci
- Pokud primarni se lisi, sekundarni je prazdny -> presmeruje do sekundarniho
- Pokud oba obsazeny, ani jeden neodpovida -> prepise primarni

#### Normalizace telefonu (`contact_import.py:52-63`)
- Odstrani `+420`, `00420`, `420` prefix
- Pri ukladani: 9 cifer -> pridani `+420` prefixu (`contact_import.py:66-75`)

### 3.5 Synchronizace (CSV porovnani)

- **Soubory:** `app/services/csv_comparator.py`, `app/routers/sync/`
- Workflow: Upload CSV -> Compare -> Review -> Accept/Reject/Exchange

#### CSV parsovani (`csv_comparator.py:16-97`)
- Podporuje `;` i `,` delimiter, auto-detekce
- Sloupce dle ruznych pojmenovani (sousede.cz, interni export)
- Format cisla jednotky: `"1098/14" -> "14"`
- Merge radku se stejnym cislem jednotky (pro interni export s radky per spoluvlastnik)
- Podpora kodovani: UTF-8, CP1250, Latin-1 s automatickym fallbackem

#### Porovnani (`csv_comparator.py:171-362`)
1. Strukturovane porovnani (`_compare_structured_names`): CSV "prijmeni jmeno" vs DB `first_name` + `last_name`
2. Fuzzy fallback: `SequenceMatcher` + mnozinove porovnani (Jaccard)
3. Rozhodovani o statusu:
   - Strukturalni shoda / Jaccard=1.0 / individualni jmena se shoduji -> `MATCH`
   - Prohozena jmena -> `NAME_ORDER`
   - ratio >= 0.85 -> `MATCH` nebo `NAME_ORDER`
   - jinak -> `DIFFERENCE`
4. Detekce zmeny podilu a typu vlastnictvi (v `match_details`)

#### Vymena vlastniku (`owner_exchange.py`)
- Pro `DIFFERENCE` zaznamy: nahradi vlastniky na jednotce daty z CSV
- Zpracovani:
  1. Match CSV jmen na existujici vlastniky (pres `match_name`, threshold 0.90)
  2. "Reuse" (existujici na jednotce) -> ponechani `OwnerUnit`, aktualizace `ownership_type`
  3. "New" (neexistujici) -> vytvoreni noveho `Owner` + `OwnerUnit`
  4. Soft-delete neparovanych: `OwnerUnit.valid_to = exchange_date`
  5. Prepocet hlasu: `_split_votes()` rovnomerne rozdeleni podilu (`owner_exchange.py:40-46`)

### 3.6 Kontrola podilu (Share Check)

- **Soubory:** `app/services/share_check_comparator.py`, `app/routers/share_check.py`
- Workflow: Upload CSV/XLSX -> Mapovani sloupcu -> Porovnani -> Review -> Aktualizace

#### Mapovani sloupcu (`share_check_comparator.py:167-207`)
1. Kontrola ulozenych mapovani (posledni pouzite)
2. Fallback na auto-detekci (prehledava zname nazvy sloupcu, `_UNIT_CANDIDATES`, `_SHARE_CANDIDATES`)

#### Porovnani (`share_check_comparator.py:352-426`)
- Parsovani podilu: `"12212/4103391" -> 12212` (cislo pred lomitkem)
- Agregace per jednotka: vice radku spoluvlastniku se scitaji
- Porovnani s `Unit.podil_scd` v DB
- Statusy: `MATCH` (hodnoty se shoduji), `DIFFERENCE`, `MISSING_DB`, `MISSING_FILE`

#### Aktualizace (`share_check.py:478+`)
- Batch update: `Unit.podil_scd = file_share` pro vybrane zaznamy
- Prepocet hlasu vsech vlastniku na jednotce pres `recalculate_unit_votes()`

### 3.7 Zalohovani a obnova

- **Soubor:** `app/services/backup_service.py`

#### Zaloha (`backup_service.py:9-42`)
- ZIP archiv obsahuje: `svj.db`, `uploads/`, `generated/`
- Pojmenovani: `svj_backup_YYYY-MM-DD_HHMMSS.zip` nebo vlastni nazev (sanitizovany)

#### Obnova (`backup_service.py:45-77`)
1. Validace ZIP (musi obsahovat `svj.db`)
2. Bezpecnostni zaloha pred obnovou (automaticky vytvori zalohu aktualniho stavu)
3. Obnova DB + uploads + generated
4. Zip Slip ochrana (`backup_service.py:157`) — overeni ze cesta zustava uvnitr ciloveho adresare

#### Obnova z adresare (`backup_service.py:80-124`)
- Podpora rozbaleneho adresare (Safari rozbaluje ZIP do podadresare)
- Hleda `svj.db` v korenu nebo o uroven hloubeji

#### Restore log (`backup_service.py:164-195`)
- JSON soubor `restore_log.json` v backup adresari
- Prezije obnovu DB (neni v databazi)
- Zaznamenava: timestamp, zdroj, metoda, bezpecnostni zaloha

### 3.8 Evidence plateb

- **Soubory:** `app/services/payment_matching.py`, `app/services/prescription_import.py`, `app/services/bank_import.py`, `app/services/settlement_service.py`, `app/services/payment_overview.py`, `app/routers/payments/`
- Workflow: Import predpisu -> Import VS mapovani -> Import bankovnich vypisu -> Automaticky matching -> Rucni korekce -> Prehled -> Vyuctovani

#### 3.8.1 Import predpisu z DOCX (`prescription_import.py`)

**Format:** DOCX soubory ze spravniho systemu DOMSYS
- Parsuje tabulky s 25 radky (fixni format)
- Extrahuje: variabilni symbol, cislo jednotky, jmeno vlastnika, polozky predpisu
- **Auto-kategorizace polozek** — nazev polozky se matchuje proti znamym vzorum:
  - `provozni`: sprava, pojisteni, uplata, odmena, uklid, elektrina, revize...
  - `fond_oprav`: fond oprav, fond udrzby, uver, splaceni...
  - `sluzby`: voda, teplo, TUV, ohrev, vytapeni, odpady, vyucita, komunitni...
- Fallback: pokud nazev neodpovida zadnemu vzoru -> `provozni`

**Detekce konfliktu VS:**
- Pri importu se kontroluje, zda existujici VS mapovani na jinou jednotku nekoliduje s novym predpisem
- Varovani se zobrazi uzivateli (`validate_vs_conflicts()`)

#### 3.8.2 Import VS mapovani (`payments/symbols.py`)

- Variabilni symboly se importuji z predpisu nebo se zadavaji rucne
- Jeden VS -> jedna jednotka NEBO prostor (ale jednotka/prostor muze mit vice VS)
- VS se pouziva jako primarni identifikator pro automaticky matching plateb

#### 3.8.3 Import bankovnich vypisu (`bank_import.py`)

**Format:** Fio banka CSV
- UTF-8 s BOM, strednik jako oddelovac
- Radky 1-8: metadata (cislo uctu, obdobi)
- Radek 10: hlavicky (19 sloupcu, duplicitni "Poznamka")
- Radky 11+: transakce

**Parsovani:**
- Detekce duplicit: kontrola podle `bank_transaction_id` (ID pohybu z Fio)
- Castka: kladna = prijem (`INCOME`), zaporna = vydej (`EXPENSE`)
- Variabilni symbol: z CSV sloupce, normalizace (odstraneni mezer, nul na zacatku)

#### 3.8.4 Automaticky matching plateb (`payment_matching.py`)

**3-fazovy algoritmus:**

**Faze 1 — VS exact match** (nejvyssi jistota):
- Pokud VS platby presne odpovida VS v `VariableSymbolMapping` -> `AUTO_MATCHED`
- Podporuje napárovani na **jednotky i prostory** (unit_id nebo space_id z VariableSymbolMapping)
- Priradi platbu k predpisu dane jednotky/prostoru pro dany mesic

**Faze 2 — Jmeno + castka** (stredni jistota):
- Porovna jmeno platce s vlastniky na jednotkach A najemci v prostorech
- Zaroven porovna castku s mesicnim predpisem (prubezny nasobek 1-12x)
- Obe podminky musi byt splneny -> `SUGGESTED`
- **Multi-unit match** (`_find_multi_unit_match`): pokud castka nesedi na jednu jednotku, zkusi kombinace 2-4 jednotek jednoho vlastnika kde soucet predpisu = castka
- **Fallback**: pokud je jediny kandidat (jmeno sedi) ale castka nesedi -> `SUGGESTED` (jeden match = dost pro navrh)

**Faze 3 — VS prefix decode + score** (nejnizsi jistota):
- VS prefix `VS_PREFIX="1098"` se odstrani, zbytek se interpretuje jako cislo jednotky
- Bodovy system (`MIN_MATCH_SCORE=5`):
  - Shoda cisla jednotky z VS: +3 body
  - Shoda castky s predpisem: +3 body
  - Shoda jmena vlastnika: +2 body
- Score >= `MIN_MATCH_SCORE` -> `SUGGESTED`

**Klicove konstanty** (`payment_matching.py`):
- `VS_PREFIX = "1098"` — prefix pro dekodovani cisla jednotky z VS
- `MIN_WORD_LENGTH = 3` — minimalni delka slova pro matching jmen
- `MIN_COMMON_WORDS = 2` — minimalni pocet spolecnych slov pro shodu
- `MAX_PRESCRIPTION_RATIO = 10` — maximalni nasobek predpisu pro validni castku
- `MIN_MATCH_SCORE = 5` — minimalni skore pro navrh prirazeni

**Lock mechanismus:**
- Matching se spousti na pozadi; lock (`matching_lock`) zabranuje soubeznemu behu
- Stav matchingu (progres, chyby) se uklada v pameti a je pristupny pres API

**Kandidatni system** (`compute_candidates`):
- Pro UNMATCHED platby pocita kandidatni jednotky a prostory
- Kandidat = entita kde jmeno vlastnika/najemce sedi s odesilatelem
- Max 3 kandidati serazeni dle skore
- Pouziva se pro naplneni suggestion dropdownu v UI

#### 3.8.5 Alokace plateb

- `PaymentAllocation` — vazba platby na konkretni predpis s castkou
- Jedna platba muze pokryt vice mesicu (napr. platba za ctvrtleti)
- Vice plateb muze pokryvat jeden predpis (napr. castecne platby)
- Alokace podporuje unit_id i space_id (pro prostory)
- Pri alokaci se aktualizuje `UnitBalance` — bezi zustatek jednotky

#### 3.8.6 Prehled plateb (`payment_overview.py`)

**Platebni matice:**
- Sloupce = mesice (1-12), radky = jednotky
- Bunka = zaplacena castka vs predepsana castka (zelena = OK, cervena = dluh, zluta = castecne)
- `PaymentWithAlloc` dataclass — wrapper pro platbu s alokacemi

**Dluznici:**
- `_count_debtors_fast()` v `payments/_helpers.py` — rychly SQL dotaz na pocet jednotek se zustatkem > 0
- Dluznik = jednotka, ktera v danem obdobi zaplatila mene nez bylo predepsano

#### 3.8.7 Vyuctovani (`settlement_service.py`)

**Vzorec:**
```
vysledek = (mesicni_predpis * 12) + pocatecni_zustatek - celkem_zaplaceno
```

- Kladny vysledek = dluh vlastnika, zaporny = preplatek
- `Settlement` se generuje per jednotka per rok
- `SettlementItem` — detailni polozky (proporcionalni rozdeleni dle pomeru kategorii)
- Proporcionalni alokace: kazda kategorie (provozni, fond_oprav, sluzby) ma svuj pomer na celku

**Pocatecni zustatek:**
- `UnitBalance.opening_balance` pro dany rok
- Pokud neexistuje -> 0

### 3.9 Detekce nesrovnalosti v platbach (NOVE od 2026-03-28)

- **Soubory:** `app/services/payment_discrepancy.py`, `app/routers/payments/statements.py:1085+`
- Workflow: Import vypisu -> Matching -> Detekce nesrovnalosti -> Preview -> Test email -> Davkove odeslani

#### Typy nesrovnalosti (`payment_discrepancy.py:1-7`)

1. **`wrong_vs`** — platba ma jiny VS nez predpis prirazene jednotky/prostoru
   - Detekovano POUZE u `MANUAL` a `SUGGESTED` plateb (u AUTO_MATCHED VS z definice sedi)
   - Podminka: `payment.vs != presc.variable_symbol` a oba jsou neprazdne

2. **`wrong_amount`** — zaplacena castka neodpovida mesicnimu predpisu
   - Tolerovano: nasobky predpisu 1-12x (ctvrtletni/pololetni/rocni platba) s toleranci 0.01
   - Tolerovano: rozdil do 0.50 Kc (zaokrouhlovaci chyba)
   - Detekovano u vsech naparovanych plateb (AUTO_MATCHED, SUGGESTED, MANUAL)

3. **`combined`** — jedna platba je rozdelena na vice jednotek/prostoru (vice alokaci)
   - Automaticky vzdy oznaceno pri `len(allocations) > 1`

#### Detekce (`detect_discrepancies`, `payment_discrepancy.py:91-336`)

- Vstup: `statement_id` (bankovni vypis)
- Nacte: predpisy pro rok, aktivni najmy prostoru, vlastniky jednotek
- Iteruje pres vsechny napárovane prijmove platby
- Pro kazdou alokaci kontroluje VS a castku
- Vystup: `list[Discrepancy]` — dataclass s kompletnim kontextem pro email

**Urceni prijemce pri SJM** (`_match_owner_by_sender`, `payment_discrepancy.py:52-88`):
- Pri vice vlastnicich na jednotce (SJM): preferuje vlastnika jehoz jmeno odpovida odesilateli platby
- Porovnani: prijmeni odesilatele se vyskytuje v `name_normalized` vlastnika
- Fallback: prvni vlastnik v seznamu
- 2-urovnova shoda: (1) alespon 2 spolecna slova, (2) alespon 1 spolecne slovo

**Podporovane entity:**
- Jednotky (unit): predpis z `Prescription`, VS z predpisu, prijemce = vlastnik
- Prostory (space): najem z `SpaceTenant.monthly_rent`, VS z `SpaceTenant.variable_symbol`, prijemce = najemce
- Kombinovane (combined): vice entit v jedne platbe — label se spoji, ocekavana castka se sectou

#### Preview a odeslani upozorneni (`statements.py:1326+`)

**Preview stránka** (`/platby/vypisy/{id}/nesrovnalosti`):
- Zobrazi vsechny detekovane nesrovnalosti s nahledem emailu
- Filtry: vse, s emailem, bez emailu, odeslano, neodeslano
- Raditelne sloupce: datum, castka, typ, prijemce
- Generuje email previews pro kazdeho prijemce z sablony

**Emailova sablona** (seedovana v `main.py:_seed_email_templates`):
- Jinja2 rendering pres `render_email_template()` z `app/utils.py`
- Promenne: `{{ jmeno }}`, `{{ mesic_nazev }}`, `{{ rok }}`, `{{ datum_platby }}`, `{{ castka_zaplaceno }}`, `{{ vs_platby }}`, `{{ entita }}`, `{{ castka_predpis }}`, `{{ vs_predpisu }}`, `{{ chyby }}`, `{{ svj_nazev }}`
- `chyby` je list stringu — iterovany pres `{% for chyba in chyby %}`

**Testovaci email** (`/platby/vypisy/{id}/nesrovnalosti/test`):
- Odesle prvni nesrovnalost na testovaci email adresu
- `BankStatement.discrepancy_test_passed = True` po uspesnem testu
- Test je POVINNY pred davkovym odeslanim

**Davkove odeslani** (`/platby/vypisy/{id}/nesrovnalosti/odeslat`):
- Spusti background thread `_send_discrepancy_emails_batch`
- Pouziva sdilenou konfiguraci z `SvjInfo` (batch_size, batch_interval, confirm_each_batch)
- Sdilene SMTP pripojeni per davka
- Pocatecni prodleva 5s (uzivatel muze pozastavit/zrusit)
- `Payment.notified_at = utcnow()` se nastavi po uspesnem odeslani
- EmailLog zaznamy s `module="payment_notice"`, `reference_id=statement_id`
- Progress tracking pres `_discrepancy_progress` dict (in-memory, thread-safe pres Lock)
- Podpora: pozastaveni, pokracovani, zruseni, potvrzeni po kazde davce

**Progress bar:**
- Pouziva sdileny `partials/_send_progress.html` + `_send_progress_inner.html`
- Stejny vzor jako u rozesilaciho modulu (tax)
- HTMX polling kazdych 500ms
- ETA vypocet pres `compute_eta()` z `app/utils.py`

### 3.10 Import prostoru z Excelu (NOVE od 2026-03)

- **Soubor:** `app/services/space_import.py`
- Workflow: Upload -> Mapovani sloupcu -> Preview -> Confirm

#### Parsovani a preview (`preview_spaces_from_excel`)
- Dynamicke mapovani sloupcu (space_number, designation, section, floor, area, tenant_name, phone, email, contract_number, contract_start, monthly_rent, variable_symbol)
- Auto-detekce blokovanych prostoru dle klicovych slov v nazvu
- Matching najemcu na existujici vlastniky (exactni name_normalized, fallback prijmeni)
- Validace: duplicitni cisla prostoru, neplatne hodnoty

#### Import (`import_spaces_from_excel`)
- Vytvori Space + Tenant + SpaceTenant zaznamy
- Auto-link na Owner pokud existuje shoda jmena
- Owner overrides z preview (uzivatel muze vybrat jineho vlastnika)
- Auto-vytvoreni `VariableSymbolMapping` a `Prescription` pro prostory s najemnym
- Fallback VS: pokud neni VS sloupec, pouzije cislo smlouvy

### 3.11 Import pocatecnich zustatku (NOVE od 2026-03)

- **Soubor:** `app/services/balance_import.py`
- Workflow: Upload Excel -> Mapovani sloupcu -> Preview -> Confirm

#### Preview (`preview_balance_import`)
- Parovani radku na jednotky (dle cisla jednotky)
- Fuzzy matching vlastniku (exaktni, prijmeni, casrove obsahovani)
- Overeni VS konzistence
- SJM handling: pri vice vlastnicich na jednotce preferuje odpovídajici Excel jmeno

#### Import (`execute_balance_import`)
- Smaze existujici zustatky pro rok (replace strategie)
- Vytvori `UnitBalance` zaznamy se zdrojem `IMPORT`
- Duplicitni radky pro stejnou jednotku se scitaji (SJM)
- Nepovinne sloupce (zalohy, vyuctovani, stav) se ulozi do poznamky

---

## 4. Vypocetni pravidla

### 4.1 Kvorum
- **Definice:** `total_processed_votes / declared_shares >= quorum_threshold`
- **Soubor:** `voting.py:120-124`
- `declared_shares` = `SvjInfo.total_shares`
- `total_processed_votes` = soucet `ballot.total_votes` pro zpracovane listky s alespon 1 hlasem
- `quorum_threshold` ulozeno jako 0-1 (ne procenta)

### 4.2 Pocitani hlasu
- Kazdy listek ma `total_votes` (vaha v hlasovani)
- Kazdy `BallotVote` ma `votes_count` = `ballot.total_votes` (tj. vsechny body na listku maji stejnou vahu)
- Per-item vysledek: `votes_for = sum(bv.votes_count for bv in item.votes if bv.vote == FOR)`
- Procentualni vyjadreni: `pct_for = votes_for / declared_shares * 100`

### 4.3 SJM podil
- SJM par: oba vlastnici sdileji JEDEN listek
- `total_votes` sdileneho listku = soucet `ou.votes` VSECH clenu paru
- Jednotky se deduplikuji (zobrazeni), ale hlasy se scitaji
- Pri importu hlasovani: radek z Excelu s hlasy -> propagace na VSECHNY listky na dane jednotce (kazdy se svym `total_votes`)

### 4.4 Podil na SCD
- `Unit.podil_scd` — podil na spolecnych castech domu (celociselna hodnota, napr. 12212)
- `OwnerUnit.votes` = `unit.podil_scd * owner_unit.share`
- Pri vice vlastnicich: `votes = split_votes(podil_scd, num_owners)` — rovnomerne rozdeleni se zbytkem

### 4.5 Konverze procent
- Formular -> DB: `quorum_threshold = form_value / 100` (`voting.py:291-295`)
- DB -> sablona: `{{ (value * 100)|round(1) }}%`

### 4.6 Normalizace jmen pro vyhledavani
- Odstraneni diakritiky: `unicodedata.normalize("NFD")` + filtr `Mn` kategorie (`utils.py:9-12`)
- Lowercase
- Format: "prijmeni jmeno" (prijmeni first)
- Vyhledavani: `Owner.name_normalized.like(search_ascii)` — NE `ilike` (je uz lowercase)
- SQLite `LIKE` nefunguje spravne s ceskou diakritikou -> proto normalizovany sloupec

### 4.7 Zustatek jednotky (znamenkova konvence)
- `UnitBalance`: kladna hodnota = dluh vlastnika, zaporna = preplatek
- Tato konvence se pouziva konzistentne v celm platebnim modulu
- Pri zobrazeni: kladne hodnoty cervene (vlastnik dluzi), zaporne zelene (preplatek)

### 4.8 Vyuctovani — vzorec
- `vysledek = (mesicni_predpis * 12) + pocatecni_zustatek - celkem_zaplaceno`
- Proporcionalni rozdeleni polozek dle pomeru kategorii na celkovem predpisu
- Kladny vysledek = nedoplatek, zaporny = preplatek

### 4.9 Matching plateb — bodovy system
- Faze 3 matchingu pouziva bodovy system s prahy:
  - `MIN_MATCH_SCORE = 5` — minimalni skore pro navrh
  - Shoda VS -> cislo jednotky: 3 body
  - Shoda castky: 3 body
  - Shoda jmena: 2 body
- Faze 1 (VS exact) nepouziva scoring — primo `AUTO_MATCHED`
- Faze 2 (jmeno+castka) vyzaduje shodu obou kriterii -> `SUGGESTED`

### 4.10 Detekce nesrovnalosti — prahy a tolerance (NOVE)
- Castka: rozdil > 0.50 Kc se povazuje za nesrovnalost
- Nasobky: platba odpovídajici 1-12x mesicnimu predpisu (s toleranci 0.01) se NEPOVAZUJE za nesrovnalost
- VS: porovnani je case-sensitive, oba musi byt neprazdne
- Kombinovana platba: automaticky `combined` pri 2+ alokacich (informativni, ne chyba)

### 4.11 Matching najemcu na vlastniky (NOVE)
- Exaktni shoda na `name_normalized` (priorita)
- Fallback: match na prijmeni (prvni slovo v normalizovanem jmene, min 3 znaky)
- Pri vice kandidatech: pokud vsichni maji stejne `name_normalized` -> vrati prvniho (duplikaty)
- Jinak -> None (nejednoznacne)

---

## 5. Integrace a formaty

### 5.1 Excel import (vlastnici)
- Format: XLSX, sheet "Vlastnici_SVJ"
- 31 sloupcu (A-AE): jednotka, vlastnik, adresy, kontakty, metadata
- Knihovna: `openpyxl`
- Sloupce viz `excel_import.py:8-39`

### 5.2 Excel import (kontakty)
- Format: XLSX, sheet "ZU", data od radku 7
- Sloupce 15-34: tituly, jmena, RC/IC, adresy, kontakty
- Knihovna: `openpyxl`

### 5.3 Excel import (hlasovani)
- Format: XLSX, libovolna struktura
- Uzivatel mapuje sloupce na vlastnika, jednotku a body hlasovani
- Konfigurovatelne hodnoty PRO/PROTI (vcetne porovnavacich vyrazu)

### 5.4 CSV import (synchronizace)
- Zdroj: sousede.cz nebo interni export
- Delimitry: `;` nebo `,` (auto-detekce)
- Kodovani: UTF-8, CP1250, Latin-1 (auto-fallback)
- Sloupce: flexibilni mapovani pres seznam kandidatu

### 5.5 CSV/XLSX import (kontrola podilu)
- Flexibilni mapovani sloupcu (jednotka + podil)
- Podpora CSV, XLSX, XLS (pres `xlrd`)
- Ulozeni mapovani pro pristi import

### 5.6 Word import (hlasovani sablon)
- Format: DOCX
- Parsovani bodu hlasovani: regexy pro "BOD 1:", "1.", ceske ordinaly
- Extrakce metadat: nazev, popis, datumy (ceske formaty)
- Knihovna: `python-docx`

### 5.7 PDF extrakce (danove dokumenty)
- Text-based PDF (ne skenovane)
- Knihovna: `pdfplumber`
- Parsovani vlastniku z "Udaje o vlastnikovi" sekce
- Parsovani cisla jednotky z nazvu souboru

### 5.8 Email
- SMTP pres `smtplib` s TLS nebo SSL
- **Podpora portu 465 (SSL)**: `smtplib.SMTP_SSL` misto `SMTP` + `starttls()` (`email_service.py:27-35`)
- Konfigurace v `.env` (`config.py:14-20`)
- HTML telo (plain text se konvertuje na HTML: `\n` -> `<br>`)
- Prilohy: libovolne soubory jako `MIMEApplication`
- Podpora vice prijemcu (`,` oddeleni) a SJM emailu (`;` oddeleni)
- **RFC 2047 encoding**: `email.header.Header` pro spravne kodovani ceskych znaku v hlavickach (`email_service.py:58-60`)
- **Sdilene SMTP pripojeni**: `create_smtp_connection()` pro davkove odesilani (jedno pripojeni per davka)

### 5.9 Excel + CSV export (vlastnici)
- **Soubor:** `owners.py:393-488`
- Endpoint: `GET /vlastnici/exportovat/{xlsx|csv}`
- Exportuji se FILTROVANE data (stejne filtry jako v seznamu: typ, vlastnictvi, kontakt, stav, sekce, hledani)
- Sloupce: vlastnik, typ, jednotky, sekce, email, email 2, telefon, podil SCD, RC/IC, trvala adresa, korespondencni adresa
- Nazev souboru obsahuje suffix dle filtru (napr. `vlastnici_fyzicke_20260309.xlsx`)
- Excel: `openpyxl`, bold hlavicky, auto-width (`excel_auto_width`)
- CSV: UTF-8 s BOM (`utf-8-sig`), strednik jako oddelovac

### 5.10 Excel + CSV export (jednotky)
- **Soubor:** `units.py:491-571`
- Endpoint: `GET /jednotky/exportovat/{xlsx|csv}`
- Exportuji se FILTROVANE data (typ, sekce, hledani)
- Sloupce: c. jednotky, budova, typ prostoru, sekce, adresa, LV, mistnosti, plocha, podil SCD, vlastnici
- Nazev souboru obsahuje suffix dle filtru (napr. `jednotky_byt_20260309.xlsx`)

### 5.11 Excel export (kontrola podilu)
- **Soubor:** `share_check.py:363-458`
- Endpoint: `POST /kontrola-podilu/{session_id}/exportovat`
- Exportuji se zaznamy dle aktualniho filtru (shoda/rozdil/chybi)
- Sloupce: jednotka, vlastnik, podil DB, podil soubor, rozdil, stav
- Zlute zvyrazneni (`PatternFill`) pro rozdilne zaznamy

### 5.12 DOCX import (predpisy — DOMSYS format)
- Format: DOCX ze spravniho systemu DOMSYS
- Tabulky s 25 radky, fixni rozlozeni
- Parsuje: VS, cislo jednotky, jmeno vlastnika, polozky predpisu s castkami
- Auto-kategorizace polozek (provozni/fond_oprav/sluzby) dle nazvu
- Knihovna: `python-docx`

### 5.13 CSV import (bankovni vypisy — Fio banka)
- Format: Fio banka CSV export
- Kodovani: UTF-8 s BOM, strednik jako oddelovac
- Struktura: 8 radku metadata, radek 10 hlavicky (19 sloupcu), radky 11+ data
- Duplicitni sloupec "Poznamka" (pozice 10 a 17)
- Parsuje: cislo uctu, VS, castka, datum, nazev protistrany, poznamka
- Deduplikace pres `bank_transaction_id` (ID pohybu)

### 5.14 Excel import (prostory) (NOVE)
- Format: XLSX, libovolna struktura
- Dynamicke mapovani sloupcu (space_number, designation, tenant_name, monthly_rent, variable_symbol...)
- Knihovna: `openpyxl`
- Auto-detekce: blokovane prostory dle klicovych slov, matching najemcu na vlastniky
- Vedlejsi efekty: auto-vytvoreni VariableSymbolMapping + Prescription pro prostory s najemnym

### 5.15 Excel import (pocatecni zustatky) (NOVE)
- Format: XLSX nebo XLS (starsi format pres `xlrd`)
- Dynamicke mapovani sloupcu (unit_number, owner_name, amount, deposits, settlement...)
- Replace strategie: smaze existujici zustatky pro rok pred importem
- SJM: duplicitni radky pro stejnou jednotku se scitaji

### 5.16 Jinja2 email template rendering (NOVE)
- **Soubor:** `app/utils.py:253-266`
- `render_email_template()` — renderuje sablonovy string s Jinja2 syntaxi
- Podporuje: `{{ variable }}`, `{% for x in list %}`, `{% if condition %}`
- Nezneme promenne se renderuji jako prazdny string (ne chyba)
- Registrovany filtr `fmt_num` pro formatovani cisel
- Pouziva se v: rozesílani (tax sending), nesrovnalosti (discrepancy emails)

---

## 6. Hranicni pripady a workaroundy

### 6.1 SJM parovani — multi-owner jednotky
- **Soubor:** `voting.py:517-564`
- Jednotky s >2 SJM vlastniky se NE-paruji pres connected components
- Fallback: seskupeni dle identicke mnoziny SJM jednotek (frozenset)
- Presne 2 vlastniky se shodnou mnozinou -> par; jinak kazdy zvlast

### 6.2 Import hlasovani — disambiguace
- **Soubor:** `voting_import.py:309-334`
- Kdyz vice listku sdili jednotku: zuzeni dle jmena
- Po zuzeni: re-add SJM partnera (presne 2 SJM na jednotce)
- Propagace hlasu jen na listky S hlasy; bez hlasu -> jen prvni nalezeny

### 6.3 Parsovani cisla jednotky
- **Vsude:** `"1098/115" -> 115` (posledni cast za lomitkem)
- `TaxDocument.unit_number` a `SyncRecord.unit_number` jsou `String(20)` (historicky z PDF/CSV)
- Pri ORDER BY: `cast(col, Integer)` pro spravne ciselne razeni

### 6.4 Recovery zaseknuteho rozesílani
- **Soubor:** `tax.py:45-56`
- Pri startu serveru: vsechny `SENDING` session se automaticky prepnou na `PAUSED`
- V endpointu: pokud DB rika `SENDING` ale neexistuje progress dict -> `PAUSED` (`tax.py:1420-1423`)

### 6.5 Zip Slip ochrana
- Viz sekce 10.3

### 6.6 Path traversal ochrana
- Viz sekce 10.2

### 6.7 Safari unzip — hleda svj.db o uroven hloubeji
- **Soubor:** `backup_service.py:90-98`
- Safari rozbaluje ZIP do podadresare -> restore hleda `svj.db` rekurzivne

### 6.8 Firemni jmena v PDF — fragmenty pres vice radku
- **Soubor:** `pdf_extractor.py:77-93`
- Dlouhe nazvy firem se deli pres vice SP radku -> `_merge_company_fragments()` je slije zpet
- Detekce fragmentu: `_is_company_suffix()` — "s.r.o.", "a.s.", jedno velke slovo

### 6.9 VS kolize pri importu predpisu
- Pri importu predpisu se kontroluje, zda VS uz neni mapovan na jinou jednotku
- `validate_vs_conflicts()` v `prescription_import.py` — varovani uzivateli pred importem
- Uzivatel muze import potvrdit i s konfliktem (neni blokujici)

### 6.10 Fio CSV duplicitni sloupec "Poznamka"
- **Soubor:** `bank_import.py`
- Fio CSV ma 2 sloupce s nazvem "Poznamka" (pozice 10 a 17)
- Parser to resi pres indexy misto nazvu sloupcu pro druhou poznamku

### 6.11 Matching lock — zabrana soubeznemu behu
- **Soubor:** `payment_matching.py`
- `matching_lock` zabranuje spusteni matchingu, pokud jiz bezi jiny
- Stav matchingu (progres %) je ulozen v pameti a pristupny pres polling endpoint

### 6.12 Platba pokryvajici vice mesicu
- Jedna platba muze byt alokovana na vice predpisu (napr. platba za ctvrtleti)
- `PaymentAllocation` umoznuje rozdelit castku na vice predpisu s ruznou castkou na kazdem

### 6.13 Nesrovnalosti — SJM prijemce (NOVE)
- **Soubor:** `payment_discrepancy.py:52-88`
- Pri SJM (vice vlastniku na jednotce) se upozorneni posle vlastnikovi jehoz jmeno odpovida odesilateli platby
- Dvoufazovy matching: (1) 2+ shodna slova, (2) 1+ shodne slovo, (3) fallback prvni vlastnik
- Predchazi situaci kdy upozorneni prijde "spatnemu" manzelovi

### 6.14 SMTP SSL vs STARTTLS (NOVE)
- **Soubor:** `email_service.py:27-35`
- Port 465 → `SMTP_SSL` (primo sifrovane pripojeni)
- Ostatni porty → `SMTP` + `starttls()` (upgradeovane pripojeni)
- Automaticke rozliseni dle portu, neni treba konfigurace uzivatelem

### 6.15 Prostor auto-detekce bloku (NOVE)
- **Soubor:** `space_import.py:26-30, 93-98`
- Klicova slova v nazvu prostoru automaticky nastavi status `BLOCKED`
- Detekce bezi na `designation` i `tenant_name` (napr. "Kotelna" v nazvu najemce)
- Zabranuje prirazeni najemce k utilitnim prostorum

---

## 7. Konfigurace

### 7.1 Aplikacni nastaveni (`app/config.py`)
```python
database_path = "data/svj.db"          # SQLite databaze
upload_dir = "data/uploads"             # Nahrane soubory
generated_dir = "data/generated"        # Generovane exporty
temp_dir = "data/temp"                  # Docasne soubory
smtp_host/port/user/password            # SMTP pro emaily
libreoffice_path                        # Pro PDF generovani z Word
```

### 7.2 Upload adresare
- `excel/` — importni Excel soubory
- `word_templates/` — Word sablony hlasovani
- `scanned_ballots/` — skeny listku
- `tax_pdfs/session_{id}/` — PDF danove dokumenty
- `csv/` — CSV soubory pro synchronizaci
- `share_check/` — soubory pro kontrolu podilu

### 7.3 Ciselniky (`CodeListItem`)
- Kategorie: `space_type`, `section`, `room_count`, `ownership_type`
- Seedovane z existujicich dat pri startu (`main.py`)

### 7.4 Emailove sablony (`EmailTemplate`)
- `"Rozúčtování příjmů za rok {rok}"` — sablona pro rozesílani danovych dokumentu
- `"Upozornění na nesrovnalost v platbě"` — sablona pro upozorneni na nesrovnalosti (Jinja2 syntax s `{{ }}`)
- Seedovane pri startu aplikace (`main.py:_seed_email_templates`)
- Editovatelne v Nastaveni

### 7.5 Sdilena konfigurace odesilani (`SvjInfo`, NOVE)
- `send_batch_size` (default 10) — pocet prijemcu v davce
- `send_batch_interval` (default 5) — pauza mezi davkami v sekundach
- `send_confirm_each_batch` (default False) — potvrzeni po kazde davce
- `send_test_email_address` — posledni testovaci email
- Pouzivano: rozesílani (tax), nesrovnalosti (discrepancy)

---

## 8. Activity logging

- **Soubor:** `app/models/common.py:57-77`
- Akce: `CREATED`, `UPDATED`, `DELETED`, `STATUS_CHANGED`, `IMPORTED`, `EXPORTED`, `RESTORED`
- Volano pres `log_activity(db, action, entity_type, module, ...)`
- Loguji se: vytvoreni/zmena hlasovani, importy, zmeny stavu, rozesílani

---

## 9. Validace vstupu

### 9.1 Validace emailu
- **Soubor:** `utils.py:135-140`
- Regex `^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$`
- Pouziva se pri: vytvoreni vlastnika (`owners.py:88-99`), editaci kontaktu (`owners.py:1257-1258`), vytvoreni najemce (`tenants/crud.py:59`)
- Neplatny email vraci formular s chybovou hlaskou (ne redirect)

### 9.2 Detekce duplicit pri vytvoreni vlastnika
- **Soubor:** `owners.py:101-138`
- Kontroluji se 3 kriteria: `name_normalized`, `birth_number`, `email`
- Kazde kriterium hleda shodu pouze mezi aktivnimi vlastniky (`is_active=True`)
- Pri nalezeni duplicit: zobrazi varovani s odkazem na existujiciho vlastnika
- Uzivatel muze potvrdit vytvoreni (hidden field `force_create=1`) — neni blokujici

### 9.3 Validace ciselnych vstupu (jednotky)
- **Soubor:** `units.py:46-122` (vytvoreni), `units.py:261-377` (editace)
- Cislo jednotky: cele cislo, rozsah 1-99999, unikatnost
- Cislo budovy: rozsah 1-99999 (pokud zadano jako cislo; alfanumericke povoleno)
- Plocha: rozsah 0-9999 m2, neplatna hodnota se ignoruje s varovanim
- Podil SCD: rozsah 0-99999999, neplatna hodnota se ignoruje s varovanim
- Varovani (warnings) se zobrazuji jako zlute bannery nad vysledkem

### 9.4 SMTP test pripojeni
- **Soubor:** `settings_page.py:193-226`
- Endpoint: `POST /nastaveni/smtp/test`
- Overuje: navazani spojeni, TLS, prihlaseni
- Rozlisuje chybove stavy: nekonfigurovano, chyba prihlaseni, chyba spojeni
- Vraci partial HTML s vysledkem (zeleny OK / cervena chyba)

### 9.5 Centralizovane upload limity
- **Soubor:** `utils.py:63-72`
- `UPLOAD_LIMITS` dict: excel (50MB), csv (50MB), pdf (100MB), docx (10MB), backup (200MB), folder (500MB)
- `validate_upload()` (`utils.py:75-106`): kontrola pripony + velikosti
- `validate_uploads()` (`utils.py:109-121`): pro seznam souboru, vraci prvni chybu

### 9.6 Validace najemce (NOVE)
- **Soubor:** `tenants/crud.py:36-60`
- Jmeno nebo prijmeni je povinne
- Email validace pres `is_valid_email()` (shodne jako u vlastniku)

---

## 10. Bezpecnost

### 10.1 Security headers middleware
- **Soubor:** `main.py:490-496`
- Kazda HTTP odpoved obsahuje:
  - `X-Frame-Options: DENY` (ochrana proti clickjacking)
  - `X-Content-Type-Options: nosniff` (prevence MIME type sniffing)
  - `Referrer-Policy: strict-origin-when-cross-origin` (omezeni referrer)

### 10.2 Path traversal ochrana
- **Soubor:** `utils.py:42-59`
- `is_safe_path()` pouziva `Path.relative_to()` misto `startswith()` (prevence prefix utoku)
- Pouziva se pri: servovani priloh (`settings_page.py:230+`), stahovani souboru, kontrola podilu

### 10.3 Zip Slip ochrana
- **Soubor:** `backup_service.py:157`
- Pred extrakci ZIP: overeni ze cesta zustava uvnitr ciloveho adresare

---

## 11. UX — front-end business logika

### 11.1 Custom confirm modal (`svjConfirm`)
- **Soubor:** `app/static/js/app.js:170-245`
- Nahradi nativni `window.confirm()` vlastnim modalem
- 3 zpusoby interceptu:
  - `data-confirm` atribut na `<form>` — intercept submit eventu
  - `data-confirm` atribut na `<button>`/`<a>` — intercept click eventu
  - `hx-confirm` atribut (HTMX) — intercept `htmx:confirm` eventu
- Callback vzor: `svjConfirm(message, onConfirm)` — callback se vola az po potvrzeni

### 11.2 Focus trap + focus restore v modalech
- **Soubor:** `app/static/js/app.js:78-117`
- Focus trap: Tab/Shift+Tab se cykli jen uvnitr modalniho okna (`_trapFocus`)
- Focus restore: po zavreni modalu se focus vrati na puvodni element (`_restoreFocus`)
- Aplikuje se na: PDF modal, confirm modal, send confirm modal
- Escape klaves zavre libovolny otevreny modal

### 11.3 Unsaved form warning (beforeunload)
- **Soubor:** `app/static/js/app.js:249-267`
- Formulare s atributem `data-warn-unsaved` sleduje zmeny (`input` event)
- Pred opustenim stranky: prohlizec zobrazi nativni varovani
- Reset pri submit nebo HTMX boosted navigaci

### 11.4 Dashboard onboarding
- **Soubor:** `app/templates/dashboard.html:114-122`
- Pokud je DB prazdna (`owners_count == 0`) a neni aktivni vyhledavani:
  - Zobrazi se uvitaci blok "Vitejte v SVJ Sprava"
  - 3 kroky: import vlastniku, kontrola s katastrem, zalozeni hlasovani
  - Nahrazuje tabulku posledni aktivity

### 11.5 SQL agregace na seznamu hlasovani (performance)
- **Soubor:** `voting/session.py:48-106`
- Misto iterace pres vsechny listky v Pythonu: 3 SQL dotazy
  1. `GROUP BY voting_id`: pocet zpracovanych listku
  2. Subquery `voted_ids` + `GROUP BY voting_id`: soucet hlasu zpracovanych listku s alespon 1 hlasem
  3. `GROUP BY voting_item_id`: SUM per-item hlasy (FOR/AGAINST/ABSTAIN) pres `case()` vyrazy
- Vyrazne snizuje pocet SQL dotazu pri desitkach hlasovani

### 11.6 Sdileny progress bar pro davkove odesilani
- **Soubory:** `partials/_send_progress.html`, `partials/_send_progress_inner.html`
- Pouzivano v: rozesílani (tax), nesrovnalosti (discrepancy)
- Vnější partial: polling div + tlacitka (Pozastavit/Pokracovat/Zrusit) MIMO polled oblast
- Vnitřní partial: progress bar, statistiky, stav — swapuje se HTMX pollingem (500ms)
- Tlacitka musi byt mimo HTMX-polled oblast — jinak `data-confirm` modal prestane fungovat
- Stav se synchronizuje pres hidden inputy + `htmx:afterSwap` event
- Po dokonceni polling ceka 3 sekundy pred redirectem
- ETA vypocet pres `compute_eta()` z `app/utils.py`

---

## Priloha: Klicove konstanty

| Konstanta | Hodnota | Soubor | Pouziti |
|-----------|---------|--------|---------|
| `VS_PREFIX` | `"1098"` | `payment_matching.py` | Prefix VS pro dekodovani cisla jednotky |
| `MIN_WORD_LENGTH` | `3` | `payment_matching.py` | Min. delka slova pro matching jmen |
| `MIN_COMMON_WORDS` | `2` | `payment_matching.py` | Min. pocet spolecnych slov |
| `MAX_PRESCRIPTION_RATIO` | `10` | `payment_matching.py` | Max. nasobek predpisu pro validni castku |
| `MIN_MATCH_SCORE` | `5` | `payment_matching.py` | Min. skore pro navrh prirazeni |
| `_CZECH_SURNAME_SUFFIXES` | `["-ova", "-kova", ...]` | `owner_matcher.py` | Cesky stemming prijmeni |
| `UPLOAD_LIMITS` | dict | `utils.py` | Limity uploadu (excel:50MB, pdf:100MB...) |
| `quorum_threshold` | 0-1 | `voting.py` | Kvorum (50% = 0.5) |
| `send_batch_size` | default 10 | `administration.py` | Emailu v davce (sdilene) |
| `send_batch_interval` | default 5 | `administration.py` | Pauza mezi davkami v sekundach (sdilene) |
| `BLOCKED_KEYWORDS` | list 15 slov | `space_import.py` | Auto-detekce blokovanych prostoru |
| Tolerance castky | 0.50 Kc | `payment_discrepancy.py` | Min. rozdil pro nesrovnalost |
| Tolerance nasobku | 0.01 | `payment_discrepancy.py` | Presnost detekce nasobku predpisu |
