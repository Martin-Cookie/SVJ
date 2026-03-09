# Business logika -- SVJ Management System

> Automaticky extrahováno z kódu dne 2026-03-09

## Obsah

1. [Business procesy](#1-business-procesy)
2. [Business pravidla](#2-business-pravidla)
3. [Datový model](#3-datový-model)
4. [Edge cases a workaroundy](#4-edge-cases-a-workaroundy)
5. [Integrace](#5-integrace)

---

## 1. Business procesy

### 1.1 Hlasování per rollam (Voting Workflow)

**Účel:** Řízení celého životního cyklu hlasování per rollam -- od vytvoření přes generování hlasovacích lístků, zpracování hlasů až po uzavření a export výsledků.

**Stavový diagram:**

```
[DRAFT] --generovat lístky--> [ACTIVE] --uzavřít--> [CLOSED]
                                  ^                    |
                                  +---znovu otevřít----+
```

Povolené přechody (whitelist):
- `DRAFT -> ACTIVE` (automaticky při generování lístků)
- `ACTIVE -> CLOSED` (manuální uzavření)
- `CLOSED -> ACTIVE` (znovuotevření)
- `CANCELLED` -- existuje jako enum, ale žádný kód ho nenastavuje

**Kroky (Wizard stepper -- 5 kroků):**

1. **Nastavení** -- Vytvoření hlasování, nahrání Word šablony (.docx), extrakce bodů hlasování a metadat (datum, popis)
2. **Generování lístků** -- Automatická tvorba hlasovacích lístků pro všechny aktivní vlastníky. SJM vlastníci jsou sdruženi do jednoho lístku
3. **Zpracování** -- Import hlasů z Excelu nebo ruční zadání. Párování přes číslo jednotky
4. **Výsledky** -- Zobrazení výsledků per bod (PRO/PROTI/ZDRŽEL SE), kontrola kvóra
5. **Uzavření** -- Finální export do Excelu

**Kde v kódu:**
- Wizard: `app/routers/voting/_helpers.py:_voting_wizard()` (řádky 19-69)
- Generování: `app/routers/voting/session.py:generate_ballots()` (řádky 403-591)
- Import hlasů: `app/services/voting_import.py`
- Stavové přechody: `app/routers/voting/session.py:update_voting_status()` (řádky 594-620)

**Důležitý detail -- SJM sdílení lístků:**

V režimu `partial_owner_mode = "shared"` (default) se manželé se SJM na stejné jednotce sdružují do jednoho lístku:

1. Najdi všechny vlastníky se SJM ownership_type na společných jednotkách
2. Na jednotkách s přesně 2 SJM vlastníky je spáruj do jednoho lístku
3. Na jednotkách s >2 SJM vlastníky (dva páry spoluvlastní) -- nespárovávej
4. Nepárovaní SJM vlastníci se seskupí podle identických SJM unit setů (frozenset)
5. Primární vlastník = první dle name_normalized (abecední řazení)
6. Hlasy = součet hlasů VŠECH členů skupiny (ne jen jedné jednotky)

Kde v kódu: `app/routers/voting/session.py:generate_ballots()` (řádky 425-541)

---

### 1.2 Rozesílka daňových podkladů (Tax Distribution Workflow)

**Účel:** Nahrání PDF daňových podkladů, automatické párování s vlastníky, nastavení emailu a hromadné rozeslání s přílohami.

**Stavový diagram (SendStatus):**

```
[DRAFT] --nastavit email/příjemce--> [READY] --odeslat--> [SENDING] --dokončit--> [COMPLETED]
                                                              |
                                                          [PAUSED] (pozastavení / restart serveru)
```

**Kroky (Wizard stepper -- 4 kroky):**

1. **Nahrání PDF** -- Upload adresáře s PDF soubory, extrakce čísla jednotky z názvu souboru (regex `(\d+)([a-zA-Z])?$`), extrakce jména vlastníka z obsahu PDF
2. **Přiřazení** -- Automatický matching vlastníků (fuzzy name matching, threshold 0.70), manuální potvrzení/oprava, přiřazení spoluvlastníků
3. **Rozesílka** -- Konfigurace emailu (předmět, tělo, batch size), testovací email, hromadné odeslání
4. **Dokončeno** -- Přehled odeslaných/selhaných

**Background sending (threading):**
- Emaily se odesílají v background threadu (`_send_emails_batch`)
- Sdílená SMTP connection per batch (optimalizace)
- Progress tracking přes in-memory dict s lock (`_sending_progress`, `_sending_lock`)
- Polling z UI přes HTMX (endpoint `/prubeh-stav`)
- Podpora pozastavení/pokračování/zrušení
- Podpora potvrzení po každém batchi (`send_confirm_each_batch`)
- Recovery: při startu serveru se SENDING sessions resetují na PAUSED (`recover_stuck_sending_sessions`)

**Kde v kódu:**
- Session/Processing: `app/routers/tax/session.py`, `app/routers/tax/processing.py`
- Matching: `app/routers/tax/matching.py`
- Sending: `app/routers/tax/sending.py`
- PDF extrakce: `app/services/pdf_extractor.py`
- Email service: `app/services/email_service.py`

**Match status stavový diagram:**

```
[UNMATCHED] --auto match--> [AUTO_MATCHED] --potvrdit--> [CONFIRMED]
[UNMATCHED] --manuální přiřazení--> [MANUAL]
[AUTO_MATCHED] --odmítnout/změnit--> [MANUAL]
```

Pravidlo: Nepotvrzená přiřazení (AUTO_MATCHED) se přeskočí při rozesílce. Musí být CONFIRMED nebo MANUAL.

---

### 1.3 Synchronizace s CSV (Sync Workflow)

**Účel:** Porovnání evidence vlastníků (Excel/DB) s externím CSV exportem (sousede.cz) -- detekce rozdílů v jménech, typech vlastnictví, podílech.

**Kroky:**

1. **Upload CSV** -- Parsování s autodetekcí oddělovače (`;` nebo `,`) a kódování (UTF-8, CP1250, Latin-1). Sloučení řádků se stejným číslem jednotky
2. **Porovnání** -- Strukturální porovnání jmen (příjmení+jméno vs DB fields), fuzzy matching přes SequenceMatcher a Jaccard, detekce prohozených jmen
3. **Zobrazení výsledků** -- Statusy: MATCH, NAME_ORDER, DIFFERENCE, MISSING_CSV, MISSING_EXCEL
4. **Řešení rozdílů** -- Akceptovat CSV data, odmítnout, manuálně upravit, nebo provést výměnu vlastníků (exchange)

**Resolution stavy:**

```
[PENDING] --akceptovat--> [ACCEPTED]
[PENDING] --odmítnout--> [REJECTED]
[PENDING] --upravit--> [MANUAL_EDIT]
[PENDING] --výměna vlastníků--> [EXCHANGED]
```

**Kde v kódu:**
- CSV parsing: `app/services/csv_comparator.py:parse_sousede_csv()`
- Porovnání: `app/services/csv_comparator.py:compare_owners()`
- Výměna vlastníků: `app/services/owner_exchange.py:execute_exchange()`
- Router: `app/routers/sync.py`

---

### 1.4 Import vlastníků z Excelu

**Účel:** Počáteční naplnění evidence z Excel souboru "SVJ_Evidence_Vlastniku_CLEAN.xlsx".

**Kroky:**

1. **Upload** -- Nahrání .xlsx souboru (max 50 MB)
2. **Preview** -- Parsování dat, detekce unikátních vlastníků a jednotek, zobrazení náhledu
3. **Confirm** -- Vytvoření záznamů v DB (owners, units, owner_units)

**Dva průchody dat:**

1. **První průchod** -- Seskupení řádků podle `_owner_group_key` (RČ/IČ nebo normalizované jméno)
2. **Druhý průchod** -- Vytvoření DB záznamů: Owner → flush → Unit (cache) → OwnerUnit

**Kde v kódu:** `app/services/excel_import.py`

---

### 1.5 Import kontaktních údajů

**Účel:** Aktualizace kontaktních údajů vlastníků z druhého Excel souboru (KontaktyVlastnici).

**Kroky:**

1. **Upload** -- Nahrání .xlsx, sheet "ZU", data od řádku 7
2. **Preview** -- Matching na DB vlastníky přes normalized name nebo RČ/IČ, detekce změn
3. **Execute** -- Aplikace vybraných změn s podporou overwrite/skip pro existující hodnoty

**Inteligentní routing kontaktů:**
- Pokud primární email/telefon je prázdný → vyplnit primární
- Pokud primární existuje a hodnota se shoduje → skip
- Pokud primární existuje, sekundární prázdný → naplnit sekundární
- Pokud oba obsazené, ani jeden se neshoduje → přepsat primární (jen s overwrite=True)

**Kde v kódu:** `app/services/contact_import.py`

---

### 1.6 Kontrola podílů (Share Check)

**Účel:** Porovnání podílů na společných částech domu (SČD) mezi evidencí a externím souborem.

**Kroky:**

1. **Upload** -- CSV, XLSX, nebo XLS soubor
2. **Column mapping** -- Autodetekce sloupců (kandidátní názvy) nebo výběr z uložených mapování
3. **Porovnání** -- Agregace podílů per jednotka (součet řádků pro spoluvlastníky), porovnání s DB
4. **Řešení** -- Aktualizovat DB hodnotu, přeskočit, nebo ponechat pending

**Kde v kódu:** `app/services/share_check_comparator.py`, `app/routers/share_check.py`

---

### 1.7 Záloha a obnova

**Účel:** Kompletní záloha a obnova dat (DB + uploaded files + generated files + .env).

**Záloha obsahuje:**
- `svj.db` (SQLite databáze, po WAL checkpoint)
- `uploads/` (Excel, Word, PDF, CSV soubory)
- `generated/` (vygenerované lístky, exporty)
- `.env` (konfigurace, pokud existuje)
- `manifest.json` (metadata: čas, verze)

**Bezpečnostní mechanismy:**
- Disk space check: potřeba 2x odhadované velikosti
- Auto-cleanup: max 10 záloh (nejstarší se mažou)
- Safety backup před restore (automaticky)
- Rollback při selhání restore
- File-based restore lock (prevence souběžné obnovy, stale lock po 10 min)
- Zip Slip protection při extrakci
- Post-restore migrace (přidání chybějících sloupců/tabulek)

**Kde v kódu:** `app/services/backup_service.py`, `app/routers/administration.py`

---

### 1.8 Výměna vlastníků (Owner Exchange)

**Účel:** Při synchronizaci nahradit vlastníky na jednotce novými (CSV data).

**Logika:**

1. Parsovat CSV jména na jednotlivé vlastníky
2. Pro každé jméno najít existujícího vlastníka (exact match → fuzzy match → new)
3. Soft-delete OwnerUnit pro odcházející vlastníky (`valid_to = exchange_date`)
4. Vytvořit nové OwnerUnit pro příchozí vlastníky (`valid_from = exchange_date`)
5. Přepočítat hlasy (votes) rovnoměrně mezi nové vlastníky
6. Deaktivovat vlastníky bez aktivních jednotek (`is_active = False`)

**Kde v kódu:** `app/services/owner_exchange.py`

---

### 1.9 Slučování duplicitních vlastníků

**Účel:** Detekce a sloučení duplicitních záznamů vlastníků (stejné jméno, různé záznamy z různých importů).

**Logika detekce:** GROUP BY `name_normalized`, HAVING COUNT > 1

**Logika doporučení:** Preferuje se: Excel source > manual > csv_sync, pak nejvíce jednotek, pak nejstarší

**Logika sloučení:**
1. Přesun OwnerUnit na cílového vlastníka (soft-delete pokud duplicitní jednotka)
2. Smart merge kontaktů: nové hodnoty vyplní první prázdný slot (email → email_secondary)
3. Kopie adres: trvalá/korespondenční, pokud cíl nemá
4. Deaktivace duplicitního vlastníka

**Kde v kódu:** `app/services/owner_service.py`

---

## 2. Business pravidla

### 2.1 Kvórum hlasování

**Pravidlo:** Hlasování je usnášeníschopné, pokud součet hlasů zpracovaných lístků >= `quorum_threshold * declared_shares`

**Implementace:**
- `quorum_threshold` se ukládá jako podíl 0-1 (formulář posílá 0-100, router dělí /100)
- `declared_shares` = `SvjInfo.total_shares` (celkový podíl dle prohlášení)
- Hlasy = `Ballot.total_votes` sumováno přes zpracované lístky s reálnými hlasy

**Kde v kódu:** `app/routers/voting/_helpers.py:_ballot_stats()` (řádky 78-145)

**Výpočet:**
```python
quorum_reached = processed_with_votes / declared_shares >= voting.quorum_threshold
```

### 2.2 Výpočet hlasů vlastníka

**Pravidlo:** Hlasy vlastníka = `podil_scd` jednotky (podíl na společných částech domu) * `share` (podíl vlastnictví na jednotce)

**Implementace při importu:**
```python
votes = unit.podil_scd or 0  # přímo z jednotky
ou.share = 1.0  # defaultně 100% podíl
```

**Přepočet při výměně vlastníků:**
```python
# Rovnoměrné rozdělení hlasů
share = 1.0 / num_owners  # každý vlastník stejný podíl
votes = total_votes // num_owners + (1 if i < remainder else 0)  # remainder prvním
```

**Kde v kódu:** `app/services/owner_exchange.py:recalculate_unit_votes()`, `_split_votes()`

### 2.3 Párování vlastníků z PDF (fuzzy matching)

**Pravidlo:** Kandidátní jméno se páruje na známé vlastníky přes dvě metriky:
1. `SequenceMatcher.ratio()` -- sekvenční podobnost
2. `name_parts_match()` -- Jaccard index / overlap coefficient přes normalizované slova

**Prahy:**
- Default threshold: **0.70** (70% shoda)
- Tax matching s `require_stem_overlap=True`: vyžaduje shodu alespoň jednoho příjmení (stem)
- Sync comparison: **0.85** pro MATCH/NAME_ORDER vs DIFFERENCE

**Normalizace jmen (`normalize_for_matching`):**
1. Strip akademických titulů (Ing., Mgr., JUDr., Ph.D., MBA...)
2. Odstranění SJM/SJ prefixu a suffixu
3. Odstranění závorek
4. Strip diakritiky → lowercase
5. Stemming českých příjmení (odstranění -ová, -ková, -ovi, -ovou...)

**Kde v kódu:** `app/services/owner_matcher.py`

### 2.4 Detekce typu vlastníka (fyzická/právnická osoba)

**Pravidlo:**
- 8 číslic bez lomítka = IČ → právnická osoba (`OwnerType.LEGAL_ENTITY`)
- 6 číslic + lomítko + 3-4 číslice = rodné číslo → fyzická osoba
- 10 číslic bez lomítka = rodné číslo → fyzická osoba
- Všechno ostatní → fyzická osoba (default)

**Detekce právnické osoby v CSV:**
- Regex: `\b(s\.r\.o\.|a\.s\.|spol\.|z\.s\.|v\.o\.s\.)\b`

**Kde v kódu:** `app/services/excel_import.py:_is_birth_number()`, `_is_company_id()`, `_detect_owner_type()`

### 2.5 Normalizace typu vlastnictví

**Pravidlo:** Hodnota "ANO" v Excelu se normalizuje na "SJM" (společné jmění manželů).

```python
if val.upper() == "ANO":
    return "SJM"
```

**Kde v kódu:** `app/services/excel_import.py:_normalize_ownership_type()`

### 2.6 Parsování čísla jednotky

**Pravidlo:** Katastrální číslo "1098/115" → extrahuje se 115 (část za lomítkem).

```python
if "/" in unit_kn:
    unit_kn = unit_kn.split("/")[-1].strip()
unit_kn = int(unit_kn)
```

Toto pravidlo se konzistentně aplikuje ve VŠECH import/parsing modulech.

**Kde v kódu:** Každý service modul (`excel_import.py`, `voting_import.py`, `csv_comparator.py`, `share_check_comparator.py`)

### 2.7 Parsování podílu z CSV

**Pravidlo:** CSV podíl "12212/4103391" → extrahuje se 12212 (čitatel). Prostý "3051" → 3051.

```python
if "/" in csv_share_raw:
    csv_share = int(csv_share_raw.split("/")[0].strip())
```

**Kde v kódu:** `app/services/csv_comparator.py` (řádky 197-207), `app/services/share_check_comparator.py:_parse_share_value()`

### 2.8 Formátování telefonního čísla

**Pravidla:**
- 9 číslic → přidat prefix `+420` (české číslo)
- 12 číslic začínajících `420` → přidat `+`
- Odstranění `+420`, `00420`, `420` prefixu pro porovnání

**Kde v kódu:** `app/services/contact_import.py:_normalize_phone()`, `_format_phone_for_db()`

### 2.9 Spoluvlastníci u daňových podkladů

**Pravidlo:** Při přiřazení PDF k vlastníkovi se automaticky najdou spoluvlastníci na stejné jednotce v daném daňovém roce.

**Logika:**
1. Najdi jednotku podle čísla
2. Pro každý OwnerUnit na jednotce zkontroluj překryv s daňovým rokem (`valid_from`..`valid_to` vs `year_start`..`year_end`)
3. Vrať všechny owner_id s překrývajícím se obdobím
4. Pokud rok není zadán → vrať pouze aktuální vlastníky (`valid_to IS NULL`)

**Kde v kódu:** `app/routers/tax/_helpers.py:_find_coowners()`

### 2.10 Import hlasů -- SJM spoluvlastnictví

**Pravidla:**
1. Párování Excel řádků na lístky přes číslo jednotky (ne přes jméno)
2. Pokud řádek **má hlasy** → párovat na VŠECHNY lístky sdílející tu jednotku
3. Pokud řádek **nemá hlasy** → párovat jen na první nalezený lístek
4. Deduplikace přes `seen_ballots` -- stejný lístek se nezpracuje dvakrát
5. Disambiguace při vícero lístcích: name matching (`name_normalized in excel_name`)
6. SJM re-inclusion: pokud disambiguace vyloučí jednoho z páru SJM (přesně 2 SJM na jednotce), přidej ho zpět

**Kde v kódu:** `app/services/voting_import.py:preview_voting_import()` (řádky 320-345)

### 2.11 Rozesílka -- přeskočení nepotvrzených přiřazení

**Pravidlo:** Při hromadné rozesílce se přeskočí distribuce se stavem `AUTO_MATCHED` -- musí být `CONFIRMED` nebo `MANUAL`.

**Kde v kódu:** `app/routers/tax/_helpers.py:_build_recipients()` (řádek 214)

### 2.12 Mazání dat -- pořadí a kaskády

**Pravidlo:** Data se mažou v definovaném pořadí respektujícím FK závislosti:

```python
_PURGE_ORDER = [
    "owners",       # BallotVote → Ballot → Owner, OwnerUnit, Unit, Proxy
    "votings",      # BallotVote → Ballot → VotingItem → Voting
    "tax",          # TaxDistribution → TaxDocument → TaxSession
    "sync",         # SyncRecord → SyncSession
    "share_check",  # ShareCheckRecord → ShareCheckSession + ShareCheckColumnMapping
    "email_logs", "import_logs", "activity_logs",
    "svj_info", "board", "code_lists", "email_templates",
    "backups",      # ZIP soubory na disku
    "restore_log",  # JSON soubor na disku
]
```

**Kaskáda:** Mazání `owners` automaticky maže i `sync` (sync záznamy jsou bez vlastníků bezcenné).

**Kde v kódu:** `app/routers/administration.py` (řádky 976-1076)

---

## 3. Datový model

### 3.1 Owner (Vlastník)

**Business účel:** Fyzická nebo právnická osoba vlastnící bytovou jednotku v SVJ.

**Klíčové atributy:**
- `first_name`, `last_name`, `title` -- strukturovaná identita
- `name_with_titles` -- zobrazovací jméno (příjmení-first formát s tituly) -- index, ne pro UI
- `name_normalized` -- lowercase bez diakritiky (příjmení jméno) -- pro vyhledávání a řazení
- `display_name` -- computed property: "titul příjmení jméno" -- pro UI zobrazení
- `owner_type` -- `PHYSICAL` / `LEGAL_ENTITY`
- `birth_number` / `company_id` -- RČ nebo IČ
- `data_source` -- `excel`, `manual`, `csv_sync` -- pro prioritizaci při slučování
- `is_active` -- soft delete (deaktivace místo smazání)

**Relace:**
- `Owner 1:N OwnerUnit N:1 Unit` -- M:N přes asociativní tabulku s atributy
- `Owner 1:N Ballot` -- hlasovací lístky (cascade delete)
- `Owner 1:N TaxDistribution` -- daňové distribuce (cascade delete)
- `Owner 1:N Proxy` -- plné moci (jako grantor i proxy_holder)

**Temporální aspekt:** Vlastnictví má historii přes `OwnerUnit.valid_from/valid_to`.

### 3.2 Unit (Jednotka)

**Business účel:** Bytová nebo nebytová jednotka v domě.

**Klíčové atributy:**
- `unit_number` -- katastrální číslo (INTEGER, unique) -- klíčový identifikátor pro párování
- `podil_scd` -- podíl na společných částech domu (Float) -- základ pro hlasování
- `space_type` -- druh prostoru (byt, ateliér, garáž...)
- `section` -- sekce domu (A, B, C...)
- `floor_area` -- podlahová plocha v m²

**Relace:**
- `Unit 1:N OwnerUnit N:1 Owner` -- vlastníci jednotky
- Properties: `current_owners` (valid_to IS NULL), `historical_owners` (valid_to IS NOT NULL)

### 3.3 OwnerUnit (Vlastnický vztah)

**Business účel:** Vazba vlastníka na jednotku s temporálními atributy a podílem.

**Klíčové atributy:**
- `ownership_type` -- typ vlastnictví (SJM, VL, SJVL...)
- `share` -- podíl na jednotce (0.0-1.0, default 1.0)
- `votes` -- počet hlasů (odvozeno z `unit.podil_scd * share`)
- `valid_from`, `valid_to` -- období platnosti (soft-delete mechanismus)
- `excel_row_number` -- číslo řádku v importním Excelu

### 3.4 Voting (Hlasování)

**Business účel:** Jedna instance hlasování per rollam.

**Klíčové atributy:**
- `status` -- DRAFT → ACTIVE → CLOSED (VotingStatus enum)
- `quorum_threshold` -- požadované kvórum (0.0-1.0, uloženo jako podíl)
- `partial_owner_mode` -- `shared` (SJM společný lístek) / `separate` (každý zvlášť)
- `template_path` -- cesta k Word šabloně
- `import_column_mapping` -- JSON string s posledním použitým mapováním sloupců pro import

### 3.5 Ballot (Hlasovací lístek)

**Business účel:** Jeden hlasovací lístek pro jednoho vlastníka (nebo SJM skupinu).

**Klíčové atributy:**
- `status` -- GENERATED → SENT → RECEIVED → PROCESSED / INVALID
- `total_votes` -- celkový počet hlasů tohoto lístku (snapshot v čase generování)
- `units_text` -- čísla jednotek oddělená čárkou ("14, 15, 16")
- `shared_owners_text` -- jména SJM spoluvlastníků ("Kočí Martin, Kočová Jana")
- `voted_by_proxy` -- hlasováno v zastoupení
- `pdf_path`, `scan_path` -- cesty k souborům

### 3.6 BallotVote (Hlas na lístku)

**Business účel:** Jeden hlas pro jeden bod hlasování na jednom lístku.

**Klíčové atributy:**
- `vote` -- FOR / AGAINST / ABSTAIN / INVALID (nullable -- NULL = dosud nehlasoval)
- `votes_count` -- váha hlasu (= `ballot.total_votes`)
- `manually_verified` -- příznak manuálního ověření

### 3.7 TaxSession (Daňová relace)

**Business účel:** Jedna kampaň rozesílání daňových podkladů.

**Klíčové atributy:**
- `send_status` -- DRAFT → READY → SENDING → COMPLETED / PAUSED
- `send_batch_size` -- počet emailů v jednom batchi (default 10)
- `send_batch_interval` -- pauza mezi batchemi v sekundách (default 5)
- `send_confirm_each_batch` -- čekat na potvrzení po každém batchi
- `test_email_passed` -- příznak úspěšného testovacího emailu (povinný před rozesílkou)
- `test_email_address` -- adresa posledního testovacího emailu

### 3.8 TaxDocument (Daňový dokument)

**Business účel:** Jeden PDF soubor s daňovým podkladem.

**Klíčové atributy:**
- `unit_number` -- číslo jednotky (String, extrahováno z názvu souboru)
- `unit_letter` -- písmeno za číslem (např. "A" z "14A.pdf")
- `extracted_owner_name` -- jméno vlastníka extrahované z PDF textu

### 3.9 TaxDistribution (Distribuce)

**Business účel:** Přiřazení dokumentu ke konkrétnímu vlastníkovi s informací o doručení.

**Klíčové atributy:**
- `match_status` -- AUTO_MATCHED / CONFIRMED / MANUAL / UNMATCHED
- `match_confidence` -- skóre shody (0.0-1.0)
- `email_status` -- PENDING → QUEUED → SENT / FAILED / SKIPPED
- `email_address_used` -- použitá emailová adresa (může být čárkou oddělený seznam)
- `ad_hoc_name`, `ad_hoc_email` -- pro externí příjemce (ne v DB)

### 3.10 SyncSession + SyncRecord (Synchronizace)

**Business účel:** Porovnání jednoho CSV souboru s evidencí.

**SyncRecord klíčové atributy:**
- `status` -- MATCH / NAME_ORDER / DIFFERENCE / MISSING_CSV / MISSING_EXCEL
- `resolution` -- PENDING / ACCEPTED / REJECTED / MANUAL_EDIT / EXCHANGED
- Párové sloupce: `csv_owner_name` vs `excel_owner_name`, `csv_ownership_type` vs `excel_ownership_type`, atd.

### 3.11 Administration entities

**SvjInfo** -- Singleton (max 1 záznam): název SVJ, typ budovy, celkové podíly, poslední mapování importu.

**SvjAddress** -- Adresy SVJ (1:N k SvjInfo, ordered).

**BoardMember** -- Členové výboru a kontrolního orgánu. Řazení: Předseda → Místopředseda → ostatní (SQL CASE expression).

**CodeListItem** -- Dynamické číselníky. Kategorie: `space_type`, `section`, `room_count`, `ownership_type`. Seedovány z existujících dat při prvním startu.

**EmailTemplate** -- Šablony emailů s placeholdery (např. `{rok}`).

### 3.12 Common entities

**EmailLog** -- Záznam každého odeslaného emailu (modul, příjemce, stav, chybová zpráva).

**ImportLog** -- Záznam každého importu (soubor, typ, počty řádků, chyby).

**ActivityLog** -- Audit log všech akcí (CREATED, UPDATED, DELETED, STATUS_CHANGED, IMPORTED, EXPORTED, RESTORED).

---

## 4. Edge cases a workaroundy

### 4.1 Diakritika v SQLite

**Problém:** SQLite `lower()` a `LIKE`/`ilike` nefungují s českou diakritikou (č != Č, ř != Ř).

**Řešení:** Sloupec `name_normalized` obsahuje lowercase text bez diakritiky. Vyhledávání vždy přes tento sloupec s normalizovaným hledaným výrazem:
```python
search_ascii = f"%{strip_diacritics(q)}%"
Owner.name_normalized.like(search_ascii)  # NE ilike — name_normalized je už lowercase
```

**Kde v kódu:** Všechny routery s vyhledáváním, `app/utils.py:strip_diacritics()`

### 4.2 CSV encoding detekce

**Problém:** CSV soubory z různých zdrojů mají různé kódování.

**Řešení:** Pokus o čtení ve třech kódováních v pořadí: UTF-8 → CP1250 → Latin-1. BOM (`\ufeff`) se stripuje.

**Kde v kódu:** `app/services/share_check_comparator.py:_read_csv_file()`

### 4.3 CSV oddělovač

**Problém:** CSV soubory mohou používat `;` (české locale) nebo `,`.

**Řešení:** Autodetekce z prvního řádku: `delimiter = ";" if ";" in first_line else ","`

**Kde v kódu:** `app/services/csv_comparator.py:parse_sousede_csv()`, `app/services/share_check_comparator.py`

### 4.4 unit_number typ mismatch

**Problém:** `Unit.unit_number` je INTEGER, ale `TaxDocument.unit_number` a `SyncRecord.unit_number` jsou String (historicky z PDF/CSV).

**Řešení:** Při ORDER BY vždy `cast(col, Integer)`, při Python sort vždy `int(x)` s try/except fallback na 0.

### 4.5 SJM sdružování -- více než 2 vlastníci na jednotce

**Problém:** Na jedné jednotce mohou být >2 SJM vlastníci (dva manželské páry spoluvlastní).

**Řešení:** Pouze jednotky s přesně 2 SJM vlastníky se párují. Více vlastníků → alternativní seskupení přes identické SJM unit sety (frozenset).

**Kde v kódu:** `app/routers/voting/session.py:generate_ballots()` (řádky 433-481)

### 4.6 PDF company name split

**Problém:** Dlouhá firemní jména v PDF se rozloží přes více SP řádků:
```
SP 2 ... 35 ASSOCIATES INVESTMENT
SP 3 ... GROUP s.r.o.
```

**Řešení:** `_merge_company_fragments()` -- pokud řádek vypadá jako suffix firmy (jen 1 slovo + právní forma, nebo jen `s.r.o.`), připojí se k předchozímu jménu.

**Kde v kódu:** `app/services/pdf_extractor.py:_merge_company_fragments()`, `_is_company_suffix()`

### 4.7 Stale SMTP connection

**Problém:** SMTP connection může spadnout uprostřed batche.

**Řešení:** Sdílená SMTP connection se vytváří per batch (ne globálně). Pokud vytvoření selže, fallback na per-email connection.

**Kde v kódu:** `app/routers/tax/sending.py:_send_emails_batch()` (řádky 641-646)

### 4.8 Server restart během odesílání

**Problém:** Pokud server restartuje během SENDING, progress dict se ztratí ale DB status zůstane SENDING.

**Řešení:**
1. Na startu `recover_stuck_sending_sessions()` resetuje SENDING → PAUSED
2. Na send preview stránce: pokud DB=SENDING ale progress dict neexistuje → reset na PAUSED

**Kde v kódu:** `app/routers/tax/_helpers.py:recover_stuck_sending_sessions()`, `app/routers/tax/sending.py:tax_send_preview()` (řádky 155-157)

### 4.9 Snapshot warning u hlasování

**Problém:** Hlasy na lístcích jsou snapshoty z doby generování. Pokud se podíly/vlastníci změní po generování, lístky mají zastaralé hlasy.

**Řešení:** Detekce: pro každý lístek porovnej `ballot.total_votes` vs aktuální `sum(ou.votes)` vlastníka. Pokud se liší → warning v UI.

**Kde v kódu:** `app/routers/voting/session.py:voting_detail()` (řádky 293-300)

### 4.10 Čeština v Word šablonách -- date false positives

**Problém:** Regex pro body hlasování `^\d+\.\s*(.+)` chytá i české datum "19. ledna 2026".

**Řešení:** `_DATE_AFTER_NUM` regex detekuje české měsíce za číslem a přeskočí takové řádky.

**Kde v kódu:** `app/services/word_parser.py` (řádky 30-33, 84-86)

### 4.11 Multipart upload limit

**Problém:** Starlette default `max_files=1000` nestačí pro upload adresáře s PDF (může být 200+ souborů).

**Řešení:** Override na 5000 files / 5000 fields při startu:
```python
_StarletteRequest.form.__kwdefaults__["max_files"] = 5000
```

**Kde v kódu:** `app/main.py` (řádky 499-505)

### 4.12 Email content change invalidates test

**Pravidlo:** Pokud se změní email_subject nebo email_body, `test_email_passed` se resetuje na False. Uživatel musí znovu odeslat testovací email.

**Kde v kódu:** `app/routers/tax/sending.py:save_send_settings()` (řádky 573-575)

### 4.13 CSV export UTF-8 BOM

**Problém:** Excel na Windows nečte UTF-8 CSV správně bez BOM markeru.

**Řešení:** CSV se exportuje s `encoding="utf-8-sig"` (= BOM prefix `\ufeff`).

**Kde v kódu:** `app/services/data_export.py:export_category_csv()`

---

## 5. Integrace

### 5.1 Excel import -- SVJ Evidence

**Směr:** Import
**Formát:** XLSX (openpyxl), sheet "Vlastnici_SVJ"
**Struktura:** 31 sloupců (A-AE), data od řádku 2
**Klíčové sloupce:** A=číslo jednotky KN, L=jméno, M=příjmení, O=RČ/IČ, K=typ vlastnictví
**Seskupení:** Řádky se stejným RČ/IČ (nebo jménem) → jeden Owner s více OwnerUnit

**Kde v kódu:** `app/services/excel_import.py`

### 5.2 Excel import -- Kontakty vlastníků

**Směr:** Import
**Formát:** XLSX (openpyxl), sheet "ZU", data od řádku 7
**Klíčové sloupce:** 16=jméno, 17=příjmení, 19=RČ/IČ, 30=GSM, 32=email
**Matching:** Normalized name nebo RČ/IČ

**Kde v kódu:** `app/services/contact_import.py`

### 5.3 CSV import -- sousede.cz

**Směr:** Import pro porovnání
**Formát:** CSV (`;` nebo `,` oddělovač, UTF-8/CP1250/Latin-1)
**Autodetekce sloupců:** Kandidátní názvy pro unit_number, owners, space_type, ownership_type, share, email, phone
**Sloučení:** Řádky se stejným číslem jednotky (internal export má jeden řádek per spoluvlastník)

**Kde v kódu:** `app/services/csv_comparator.py`

### 5.4 Word šablona -- hlasovací lístek

**Směr:** Import (čtení) + Export (generování)
**Formát:** DOCX (python-docx pro čtení, docxtpl pro generování)
**Extrakce bodů:** Regex patterns: `BOD N:`, `N.`, `N)`, `N:`, české ordinals ("první bod hlasování")
**Extrakce metadat:** Titel (Heading 1, Title style, "per rollam"), datumové patterny

**Kde v kódu:** `app/services/word_parser.py`

### 5.5 PDF extrakce -- daňové podklady

**Směr:** Import (čtení)
**Formát:** PDF text-based (pdfplumber)
**Extrakce jmen:** Pattern "Vlastník:", "Jméno:", "Údaje o vlastníkovi:" + SP řádky
**Parsování čísla z filename:** `(\d+)([a-zA-Z])?$` → unit_number + unit_letter

**Kde v kódu:** `app/services/pdf_extractor.py`

### 5.6 PDF generování -- hlasovací lístky

**Směr:** Export
**Formát:** DOCX (docxtpl) → PDF (LibreOffice headless conversion)
**Template variables:** `owner_name`, `units_text`, `total_votes`, `items`, `proxy_name`, `date`, `voting_title`
**Závislost:** LibreOffice musí být nainstalován (`settings.libreoffice_path`)

**Kde v kódu:** `app/services/pdf_generator.py`

### 5.7 Email -- SMTP

**Směr:** Export
**Protokol:** SMTP (smtplib) s TLS
**Formát:** MIME multipart (HTML body + PDF přílohy)
**Konfigurace:** `.env` soubor (SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM_NAME, SMTP_FROM_EMAIL)
**Podpora:** Více příjemců (`,` oddělené), SJM vlastníci (`;` oddělené emaily → samostatné emaily)

**Kde v kódu:** `app/services/email_service.py`

### 5.8 Excel export

**Směr:** Export
**Formáty:** XLSX (openpyxl) + CSV (UTF-8-sig)
**Kategorie:** owners, votings, tax, sync, share_check, logs, administration
**Vlastnosti:** Bold hlavička, auto-width sloupců, barevné zvýraznění (zelená PRO, červená PROTI)

**Kde v kódu:** `app/services/data_export.py`, `app/services/excel_export.py`

### 5.9 ZIP záloha

**Směr:** Export + Import
**Formát:** ZIP (zipfile, ZIP_DEFLATED)
**Obsah:** svj.db + uploads/ + generated/ + .env + manifest.json
**Bezpečnost:** WAL checkpoint před zálohou, CRC check při restore, Zip Slip protection

**Kde v kódu:** `app/services/backup_service.py`

---

## Appendix: Důležité konstanty

| Konstanta | Hodnota | Kde | Účel |
|-----------|---------|-----|------|
| `SHEET_NAME` | `"Vlastnici_SVJ"` | `excel_import.py` | Název sheetu pro import vlastníků |
| `quorum_threshold` default | `0.5` (50%) | `voting.py` model | Výchozí kvórum |
| `send_batch_size` default | `10` | `tax.py` model | Emailů v jednom batchi |
| `send_batch_interval` default | `5` (s) | `tax.py` model | Pauza mezi batchemi |
| `_LOCK_STALE_SECONDS` | `600` (10 min) | `backup_service.py` | Timeout pro stale restore lock |
| `keep_count` (zálohy) | `10` | `backup_service.py` | Max počet záloh |
| Disk space safety | `2x` estimated | `backup_service.py` | Potřebné volné místo |
| Match threshold (default) | `0.70` | `owner_matcher.py` | Minimální shoda jmen |
| Match threshold (exchange) | `0.90` | `owner_exchange.py` | Přísnější shoda pro výměnu |
| Match threshold (sync) | `0.85` | `csv_comparator.py` | Pro MATCH/NAME_ORDER detection |
| Upload max PDF | `100 MB` | `utils.py` | Max velikost PDF uploadu |
| Upload max Excel | `50 MB` | `utils.py` | Max velikost Excel uploadu |
| Upload max backup | `200 MB` | `utils.py` | Max velikost ZIP zálohy |
| Upload max folder | `500 MB` | `utils.py` | Max velikost adresáře |
| Max files per upload | `5000` | `main.py` | Starlette multipart limit |
| SMTP timeout | `30 s` (batch) / `10 s` (single) | `email_service.py` | Timeout SMTP připojení |
| LibreOffice timeout | `120 s` | `pdf_generator.py` | Timeout konverze DOCX→PDF |
| Excel auto-width max | `45` chars | `utils.py` | Max šířka sloupce v exportu |
| Excel sheet name max | `31` chars | `data_export.py` | Excel limit pro název sheetu |

## Appendix: Enum hodnoty s business kontextem

| Enum | Hodnoty | Business kontext |
|------|---------|------------------|
| `OwnerType` | PHYSICAL, LEGAL_ENTITY | Fyzická vs právnická osoba (detekce přes RČ/IČ formát) |
| `VotingStatus` | DRAFT, ACTIVE, CLOSED, CANCELLED | Životní cyklus hlasování |
| `BallotStatus` | GENERATED, SENT, RECEIVED, PROCESSED, INVALID | Stav hlasovacího lístku |
| `VoteValue` | FOR, AGAINST, ABSTAIN, INVALID | Hodnota hlasu |
| `MatchStatus` | AUTO_MATCHED, CONFIRMED, MANUAL, UNMATCHED | Stav párování PDF→vlastník |
| `SendStatus` | DRAFT, READY, SENDING, PAUSED, COMPLETED | Stav rozesílky |
| `EmailDeliveryStatus` | PENDING, QUEUED, SENT, FAILED, SKIPPED | Stav doručení emailu |
| `SyncStatus` | MATCH, NAME_ORDER, DIFFERENCE, MISSING_CSV, MISSING_EXCEL | Výsledek porovnání |
| `SyncResolution` | PENDING, ACCEPTED, REJECTED, MANUAL_EDIT, EXCHANGED | Řešení rozdílu |
| `ShareCheckStatus` | MATCH, DIFFERENCE, MISSING_DB, MISSING_FILE | Výsledek kontroly podílů |
| `ShareCheckResolution` | PENDING, UPDATED, SKIPPED | Řešení rozdílu podílů |
| `EmailStatus` | PENDING, SENT, FAILED | Stav emailového logu |
| `ActivityAction` | CREATED, UPDATED, DELETED, STATUS_CHANGED, IMPORTED, EXPORTED, RESTORED | Typ aktivity |
