# SVJ Aplikace — Business Logic Reference

> Technický dokument s odkazy na zdrojový kód (soubor:řádek).
> Poslední aktualizace: 2026-03-09

---

## 1. Datový model — entity a vztahy

### 1.1 Vlastníci a jednotky

| Entity | Tabulka | Soubor |
|--------|---------|--------|
| `Owner` | `owners` | `app/models/owner.py:17` |
| `Unit` | `units` | `app/models/owner.py:102` |
| `OwnerUnit` | `owner_units` | `app/models/owner.py:129` |
| `Proxy` | `proxies` | `app/models/owner.py:150` |

**Klicove vztahy:**
- Owner ↔ Unit je M:N pres `OwnerUnit` (vlastnik muze vlastnit vice jednotek, jednotka muze mit vice vlastniku)
- `OwnerUnit.valid_to IS NULL` = aktivni vlastnictvi; `valid_to != NULL` = historicke
- `Owner.current_units` (property, `owner.py:79`) — filtrovane aktivni vazby, razene dle `unit_number`
- `Unit.current_owners` (property, `owner.py:121`) — filtrovane aktivni vazby

**Typ vlastnika** (`OwnerType`, `owner.py:12`):
- `PHYSICAL` — fyzicka osoba (identifikace pres rodne cislo)
- `LEGAL_ENTITY` — pravnicka osoba (identifikace pres IC)
- Detekce: IC = 8 cifer bez lomitka (`excel_import.py:135`); RN = format `XXXXXX/XXXX` nebo 10 cifer (`excel_import.py:127`)

**Jmeno vlastnika:**
- `display_name` (property, `owner.py:64`) — format "titul prijmeni jmeno"
- `name_with_titles` — DB sloupec pro index, nepoiuzivat v sablonach
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
- `quorum_threshold` — ulozeno jako 0–1 (napr. 0.5 = 50%). Formular posila 0–100, router deli `/100` (`voting.py:291-295`)
- `partial_owner_mode` — `"shared"` (SJM sdileny listek) nebo `"separate"` (kazdy vlastnik zvlast)
- `total_votes_possible` — celkovy pocet hlasu vsech lystku
- `import_column_mapping` — JSON string, ulozene mapovani sloupcu z posledniho importu

### 1.3 Rozesilaní (Tax/Send)

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
| `SvjAddress` | `svj_addresses` | `app/models/administration.py:25` |
| `BoardMember` | `board_members` | `app/models/administration.py:36` |
| `CodeListItem` | `code_list_items` | `app/models/administration.py:49` |
| `EmailTemplate` | `email_templates` | `app/models/administration.py:63` |

**SvjInfo.total_shares** — deklarovany celkovy pocet hlasu (dle prohlaseni vlastniku). Pouziva se pro vypocet kvora a procentualniho podilu.

### 1.7 Spolecne / logy

| Entity | Tabulka | Soubor |
|--------|---------|--------|
| `EmailLog` | `email_logs` | `app/models/common.py:16` |
| `ImportLog` | `import_logs` | `app/models/common.py:33` |
| `ActivityLog` | `activity_logs` | `app/models/common.py:57` |

---

## 2. Stavove automaty

### 2.1 VotingStatus (`voting.py:12`)

```
DRAFT ──[generovat listky]──> ACTIVE ──[uzavrit]──> CLOSED
                                  └──[zrusit]──> CANCELLED
```

- `DRAFT` → `ACTIVE`: automaticky pri prvnim generovani listku (`voting.py:667-668`)
- `ACTIVE` → `CLOSED`/`CANCELLED`: manualne pres formular (`voting.py:986+`)
- Nelze se vratit z CLOSED/CANCELLED zpet

### 2.2 BallotStatus (`voting.py:26`)

```
GENERATED ──[odeslat]──> SENT ──[prijat]──> RECEIVED ──[zpracovat]──> PROCESSED
                                                                         ↑
                                                          [resetovat] ───┘

GENERATED ──[oznacit jako neplatny]──> INVALID
```

- `GENERATED`: listek vytvoren, ceka na odeslani
- `SENT`: listek odeslan vlastnikovi (datum v `sent_at`)
- `RECEIVED`: fyzicky listek prijat zpet
- `PROCESSED`: hlasy zpracovany a zaznamenany (datum v `processed_at`)
- `INVALID`: listek oznacen jako neplatny
- Reset: `PROCESSED` → `GENERATED` (vymaze hlasy, `voting.py:1239+`)

### 2.3 SendStatus (`tax.py:19`) — rozesilaní

```
DRAFT ──[potvrdit prirazeni]──> READY ──[zahajit rozeslani]──> SENDING
                                   ↑                              │
                                   └──[znovu otevrit]─────────────┤
                                                                  ├──[pozastavit]──> PAUSED
                                                                  │                    │
                                                                  │  ┌─[pokracovat]────┘
                                                                  │  │
                                                                  └──┴──[dokonceno]──> COMPLETED
```

- `DRAFT`: prace na prirazeni PDF → vlastnikum
- `READY`: prirazeni potvrzeno, pripraveno k odeslani
- `SENDING`: probihajici rozesilaní v pozadi (background thread)
- `PAUSED`: pozastaveno uzivatelem (nebo po restartu serveru, `tax.py:45-56`)
- `COMPLETED`: vsechny emaily odeslany
- Recovery pri restartu: `SENDING` → `PAUSED` automaticky (`tax.py:45-56`)

### 2.4 MatchStatus (`tax.py:12`) — prirazeni PDF

```
UNMATCHED ──[auto-match]──> AUTO_MATCHED ──[potvrdit]──> CONFIRMED
                                              └──[rucne zmenit]──> MANUAL
```

### 2.5 EmailDeliveryStatus (`tax.py:27`)

```
PENDING ──[zaradit do fronty]──> QUEUED ──[odeslat]──> SENT
                                            └──[chyba]──> FAILED
                                                          └──[preskocit]──> SKIPPED
```

### 2.6 SyncStatus (`sync.py:12`) + SyncResolution (`sync.py:19`)

**Status:**
- `MATCH` — jmena se shoduji
- `NAME_ORDER` — jmena jsou prohozena (prijmeni/jmeno)
- `DIFFERENCE` — jmena se lisi
- `MISSING_CSV` — jednotka jen v DB, ne v CSV
- `MISSING_EXCEL` — jednotka jen v CSV, ne v DB

**Resolution:**
- `PENDING` → `ACCEPTED` / `REJECTED` / `MANUAL_EDIT` / `EXCHANGED`

### 2.7 ShareCheckStatus (`share_check.py:13`) + ShareCheckResolution (`share_check.py:19`)

**Status:** `MATCH`, `DIFFERENCE`, `MISSING_DB`, `MISSING_FILE`
**Resolution:** `PENDING` → `UPDATED` / `SKIPPED`

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
1. Sestavi mapu `unit_id → [vlastnici]` pro jednotky s typem vlastnictvi obsahujicim "SJM"
2. Paruje SJM spoluvlastniky pres connected components algoritmus — POUZE na jednotkach s PRESNE 2 SJM vlastniky
3. Neparovane SJM vlastniky (multi-owner jednotky) seskupi dle identicke mnoziny SJM jednotek
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
- Status `ACTIVE` → `CLOSED` nebo `CANCELLED` (`voting.py:986+`)

### 3.1.1 Import hlasovani z Excelu

- **Soubory:** `app/services/voting_import.py`, `voting.py` (import endpointy)

**Mapovani sloupcu** (`voting_import.py:10-16`):
```json
{
  "owner_col": 0,        // index sloupce se jmenem
  "unit_col": 2,         // index sloupce s cislem jednotky
  "start_row": 2,        // prvni radek s daty
  "for_values": "1, ANO, YES, X, PRO",      // co znamena PRO
  "against_values": "0, NE, NO, PROTI",     // co znamena PROTI
  "item_mappings": [
    {"item_id": 5, "for_col": 3, "against_col": 4}
  ]
}
```

**Parsovani hlasu** (`voting_import.py:63-128`):
- Podpora exaktni shody ("ANO", "1") i porovnani (">0", "<0", ">=1")
- Primarni sloupec (`for_col`): hodnota se porovna s for_values a against_values
- Sekundarni sloupec (`against_col`): logika INVERTOVANA (for_values → PROTI)
- Nerozpoznane hodnoty: radek jde do `no_match` kategorie

**Parovani radku na listky** (`voting_import.py:199-363`):
1. Sestavi lookup `unit_number → [ballot, ...]`
2. Pro kazdy radek: parsuje cislo jednotky (`"1098/115" → 115`)
3. Najde listky pro danou jednotku
4. Disambiguace pri vice listcich na jednotce:
   - Porovna jmeno z Excelu s jmenem na listku (pomoci `name_normalized`)
   - Pri SJM: pokud je presne 2 SJM vlastniku, prida vyrazeneho partnera zpet
5. Propagace hlasu: pokud radek ma hlasy → vsem listkum na jednotce (kazdy se svym `total_votes`)
6. Merge: pokud se ten samy listek objevi na vice radcich, hlasy se slouci (`seen_ballots`)

**Mody importu** (`voting_import.py:377-447`):
- **Append** (`clear_existing=False`): preskoci listky s existujicimi hlasy
- **Clear** (`clear_existing=True`): prepise vse; listky mimo import se resetuji na `GENERATED`

**Globalni mapovani:** ulozeno v `SvjInfo.voting_import_mapping` (`administration.py:17`); predvyplni se pri dalsim importu.

### 3.2 Rozesílaní (Tax/Send)

#### Krok 1: Vytvoreni session + nahrani PDF
- **Soubor:** `tax.py:432-507`
- Uzivatel nahrava adresar s PDF soubory (daňová vyúčtování)
- Pouze `.pdf` soubory se zpracuji; ostatni (`.DS_Store` atd.) se preskoci
- Soubory se ulozi synchronne, zpracovani bezi na pozadi (background thread)

#### Krok 2: Extrakce textu z PDF a auto-matching
- **Background thread:** `tax.py:627-864`
- **PDF extrakce** (`pdf_extractor.py`):
  - `parse_unit_from_filename()` (`pdf_extractor.py:189-195`): nazev souboru "115A.pdf" → unit_number="115", unit_letter="A"
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
  2. SJM prefix → vsechny shody nad threshold; jinak jen nejlepsi
  3. Non-SJM: tez globalni match (vsichni vlastnici, threshold 0.75, `require_stem_overlap=True`)
  4. Pouzije lepsi z lokalniho/globalniho
  5. Nenalezeno → `UNMATCHED` distribuce

- **Post-processing** (`tax.py:764-848`):
  - Pro nove nenadrazene dokumenty: zkopiruje prirazeni z existujicich dokumentu se stejnou jednotkou
  - Propaguje `email_address_used` z existujicich distribucí na nove

#### Krok 3: Manualni prirazeni (matching page)
- **Soubor:** `tax.py:964+`
- Uzivatel kontroluje a potvrzuje auto-match, rucne priradi nenadrazene
- Stavy: `AUTO_MATCHED` → `CONFIRMED`, nebo `MANUAL` pro rucni prirazeni
- Spoluvlastnici: `_find_coowners()` (`tax.py:139-174`) — hleda spoluvlastniky na stejne jednotce s prekryvajicim se obdobim v danovem roce

#### Krok 4: Rozesílaní emailu
- **Background thread:** `tax.py:2085-2214`
- Davkovy system: `batch_size` emailu, `batch_interval` sekund pauza
- Sdilene SMTP pripojeni per davka (`email_service.py:21-31`)
- Podpora pozastaveni/pokracovani/zruseni behem rozesilaní
- Retry neuspiesnnych: opetovne odeslani jen `FAILED` prijemcu (`tax.py:2430+`)
- Deduplikace prijemcu pres `_build_recipients()` (`tax.py:221-300`): jeden prijemce muze mit vice dokumentu
- Podpora dualnich emailu (primarni + sekundarni)

### 3.3 Import vlastniku z Excelu

- **Soubory:** `app/services/excel_import.py`, `owners.py`
- Workflow: Upload → Preview → Confirm

#### Parsovani Excelu (`excel_import.py:300-349`)
- Ocekavany format: list "Vlastnici_SVJ", 31 sloupcu (A-AE)
- Klicove sloupce: A=cislo jednotky, L=jmeno, M=prijmeni, N=titul, O=RC/IC
- Parsovani cisla jednotky: `"1098/115" → 115` (posledni cast za lomitkem)
- Detekce typu: IC (8 cifer) → `LEGAL_ENTITY`, RC (format XXXXXX/XXXX) → `PHYSICAL`

#### Seskupeni vlastniku (`excel_import.py:180-191`)
- Unikatni vlastnici se identifikuji pres `_owner_group_key()`:
  - Pokud ma RC/IC → klic `"id:XXXXXXXX"`
  - Jinak → klic `"name:prijmeni|jmeno"` (normalizovano)
- Jeden vlastnik muze mit vice radku (vice jednotek)

#### Ulozeni (`excel_import.py:352-494`)
- Faze 1: sesbirani a seskupeni radku
- Faze 2: vytvoreni DB zaznamu
  - Owner: kontaktni udaje se berou z prvniho radku, email/telefon se hleda pres vsechny radky
  - Unit: cache pro deduplikaci; existujici jednotky se pouziji
  - OwnerUnit: `votes = unit.podil_scd` (cely podil, `share=1.0`)
- Normalizace vlastnictvi: "ANO" → "SJM"

### 3.4 Import kontaktu z Excelu

- **Soubory:** `app/services/contact_import.py`, `owners.py:273+`
- Workflow: Upload → Background processing → Preview → Confirm

#### Format (`contact_import.py:6-13`)
- Sheet "ZU", data od radku 7
- Sloupce: 15=titul, 16=jmeno, 17=prijmeni, 19=RC/IC, 20-29=adresy, 30-32=kontakty

#### Matching (`contact_import.py:143-188`)
1. Primarni: shoda pres `name_normalized`
2. Fallback: RC/IC (normalizovane — bez mezer a lomitek)
3. Deduplikace: kazdy vlastnik se zpracuje jen jednou

#### Inteligentni routing kontaktu (`contact_import.py:218-256`)
- Pokud primarni kontakt je prazdny → vyplni primarni
- Pokud Excel odpovida primarnimu NEBO sekundarnimu → preskoci
- Pokud primarni se lisi, sekundarni je prazdny → presmeruje do sekundarniho
- Pokud oba obsazeny, ani jeden neodpovida → prepise primarni

#### Normalizace telefonu (`contact_import.py:52-63`)
- Odstrani `+420`, `00420`, `420` prefix
- Pri ukladani: 9 cifer → pridani `+420` prefixu (`contact_import.py:66-75`)

### 3.5 Synchronizace (CSV porovnani)

- **Soubory:** `app/services/csv_comparator.py`, `app/routers/sync.py`
- Workflow: Upload CSV → Compare → Review → Accept/Reject/Exchange

#### CSV parsovani (`csv_comparator.py:16-97`)
- Podporuje `;` i `,` delimiter, auto-detekce
- Sloupce dle ruznych pojmenovani (sousede.cz, interni export)
- Format cisla jednotky: `"1098/14" → "14"`
- Merge radku se stejnym cislem jednotky (pro interni export s radky per spoluvlastnik)
- Podpora kodovaání: UTF-8, CP1250, Latin-1 s automatickym fallbackem

#### Porovnani (`csv_comparator.py:171-362`)
1. Strukturovane porovnani (`_compare_structured_names`): CSV "prijmeni jmeno" vs DB `first_name` + `last_name`
2. Fuzzy fallback: `SequenceMatcher` + mnozinove porovnani (Jaccard)
3. Rozhodovani o statusu:
   - Strukturalni shoda / Jaccard=1.0 / individualni jmena se shoduji → `MATCH`
   - Prohozena jmena → `NAME_ORDER`
   - ratio >= 0.85 → `MATCH` nebo `NAME_ORDER`
   - jinak → `DIFFERENCE`
4. Detekce zmeny podilu a typu vlastnictvi (v `match_details`)

#### Vymena vlastniku (`owner_exchange.py`)
- Pro `DIFFERENCE` zaznamy: nahradi vlastniky na jednotce daty z CSV
- Zpracovani:
  1. Match CSV jmen na existujici vlastniky (pres `match_name`, threshold 0.90)
  2. "Reuse" (existujici na jednotce) → ponechani `OwnerUnit`, aktualizace `ownership_type`
  3. "New" (neexistujici) → vytvoreni noveho `Owner` + `OwnerUnit`
  4. Soft-delete neparovanych: `OwnerUnit.valid_to = exchange_date`
  5. Prepocet hlasu: `_split_votes()` rovnomerne rozdeleni podilu (`owner_exchange.py:40-46`)

### 3.6 Kontrola podilu (Share Check)

- **Soubory:** `app/services/share_check_comparator.py`, `app/routers/share_check.py`
- Workflow: Upload CSV/XLSX → Mapovani sloupcu → Porovnani → Review → Aktualizace

#### Mapovani sloupcu (`share_check_comparator.py:167-207`)
1. Kontrola ulozenych mapovani (posledni pouzite)
2. Fallback na auto-detekci (prehledava zname nazvy sloupcu, `_UNIT_CANDIDATES`, `_SHARE_CANDIDATES`)

#### Porovnani (`share_check_comparator.py:352-426`)
- Parsovani podilu: `"12212/4103391" → 12212` (cislo pred lomitkem)
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
- Pri importu hlasovani: radek z Excelu s hlasy → propagace na VSECHNY listky na dane jednotce (kazdy se svym `total_votes`)

### 4.4 Podil na SCD
- `Unit.podil_scd` — podil na spolecnych castech domu (celociselna hodnota, napr. 12212)
- `OwnerUnit.votes` = `unit.podil_scd * owner_unit.share`
- Pri vice vlastnicich: `votes = split_votes(podil_scd, num_owners)` — rovnomerne rozdeleni se zbytkem

### 4.5 Konverze procent
- Formular → DB: `quorum_threshold = form_value / 100` (`voting.py:291-295`)
- DB → sablona: `{{ (value * 100)|round(1) }}%`

### 4.6 Normalizace jmen pro vyhledavani
- Odstraneni diakritiky: `unicodedata.normalize("NFD")` + filtr `Mn` kategorie (`utils.py:9-12`)
- Lowercase
- Format: "prijmeni jmeno" (prijmeni first)
- Vyhledavani: `Owner.name_normalized.like(search_ascii)` — NE `ilike` (je uz lowercase)
- SQLite `LIKE` nefunguje spravne s ceskou diakritikou → proto normalizovany sloupec

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

### 5.7 PDF extrakce (daňové dokumenty)
- Text-based PDF (ne skenovane)
- Knihovna: `pdfplumber`
- Parsovani vlastniku z "Udaje o vlastnikovi" sekce
- Parsovani cisla jednotky z nazvu souboru

### 5.8 Email
- SMTP pres `smtplib` s TLS
- Konfigurace v `.env` (`config.py:14-20`)
- HTML telo (plain text se konvertuje na HTML: `\n` → `<br>`)
- Prilohy: libovolne soubory jako `MIMEApplication`
- Podpora vice prijemcu (`,` oddeleni) a SJM emailu (`;` oddeleni)

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

---

## 6. Hranicni pripady a workaroundy

### 6.1 SJM parovani — multi-owner jednotky
- **Soubor:** `voting.py:517-564`
- Jednotky s >2 SJM vlastniky se NE-paruji pres connected components
- Fallback: seskupeni dle identicke mnoziny SJM jednotek (frozenset)
- Presne 2 vlastniky se shodnou mnozinou → par; jinak kazdy zvlast

### 6.2 Import hlasovani — disambiguace
- **Soubor:** `voting_import.py:309-334`
- Kdyz vice listku sdili jednotku: zuzeni dle jmena
- Po zuzeni: re-add SJM partnera (presne 2 SJM na jednotce)
- Propagace hlasu jen na listky S hlasy; bez hlasu → jen prvni nalezeny

### 6.3 Parsovani cisla jednotky
- **Vsude:** `"1098/115" → 115` (posledni cast za lomitkem)
- `TaxDocument.unit_number` a `SyncRecord.unit_number` jsou `String(20)` (historicky z PDF/CSV)
- Pri ORDER BY: `cast(col, Integer)` pro spravne ciselne razeni

### 6.4 Recovery zaseknuteho rozesilaní
- **Soubor:** `tax.py:45-56`
- Pri startu serveru: vsechny `SENDING` session se automaticky prepnou na `PAUSED`
- V endpointu: pokud DB rika `SENDING` ale neexistuje progress dict → `PAUSED` (`tax.py:1420-1423`)

### 6.5 Zip Slip ochrana
- Viz sekce 10.3

### 6.6 Path traversal ochrana
- Viz sekce 10.2

### 6.7 Safari unzip — hleda svj.db o uroven hloubeji
- **Soubor:** `backup_service.py:90-98`
- Safari rozbaluje ZIP do podadresare → restore hleda `svj.db` rekurzivne

### 6.8 Firemni jmena v PDF — fragmenty pres vice radku
- **Soubor:** `pdf_extractor.py:77-93`
- Dlouhe nazvy firem se deli pres vice SP radku → `_merge_company_fragments()` je slije zpet
- Detekce fragmentu: `_is_company_suffix()` — "s.r.o.", "a.s.", jedno velke slovo

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

### 7.3 Ciselníky (`CodeListItem`)
- Kategorie: `space_type`, `section`, `room_count`, `ownership_type`
- Seedovane z existujicich dat pri startu (`main.py`)

### 7.4 Emailove sablony (`EmailTemplate`)
- Predmet + telo sablony
- Pouzivane pri tvorbe rozesílaní session

---

## 8. Activity logging

- **Soubor:** `app/models/common.py:57-77`
- Akce: `CREATED`, `UPDATED`, `DELETED`, `STATUS_CHANGED`, `IMPORTED`, `EXPORTED`, `RESTORED`
- Volano pres `log_activity(db, action, entity_type, module, ...)`
- Loguji se: vytvoreni/zmena hlasovani, importy, zmeny stavu, rozesílaní

---

## 9. Validace vstupu

### 9.1 Validace emailu
- **Soubor:** `utils.py:135-140`
- Regex `^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$`
- Pouziva se pri: vytvoreni vlastnika (`owners.py:88-99`), editaci kontaktu (`owners.py:1257-1258`)
- Neplatny email vraci formular s chybovou hlaskou (ne redirect)

### 9.2 Detekce duplicit pri vytvoreni vlastnika
- **Soubor:** `owners.py:101-138`
- Kontroluji se 3 kriteria: `name_normalized`, `birth_number`, `email`
- Kazde kriterium hleda shodu pouze mezi aktivnimi vlastniky (`is_active=True`)
- Pri nalezeni duplicit: zobrazi varovani s odkazem na existujiciho vlastnika
- Uzivatel muze potvrdit vytvoreni (hidden field `force_create=1`) — neni blokujici

### 9.3 Validace ciselnych vstupu (jednotky)
- **Soubor:** `units.py:46-122` (vytvoreni), `units.py:261-377` (editace)
- Cislo jednotky: cele cislo, rozsah 1–99999, unikatnost
- Cislo budovy: rozsah 1–99999 (pokud zadano jako cislo; alfanumericke povoleno)
- Plocha: rozsah 0–9999 m2, neplatna hodnota se ignoruje s varovanim
- Podil SCD: rozsah 0–99999999, neplatna hodnota se ignoruje s varovanim
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
- Pouziva se pri: servovani priloh (`settings_page.py:230+`), stahování souborů, kontrola podílů

### 10.3 Zip Slip ochrana
- **Soubor:** `backup_service.py:157`
- Pred extrakcí ZIP: overeni ze cesta zustava uvnitr ciloveho adresare

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
- Vyrazne snizuje pocet SQL dotazu pri desítkach hlasovani
