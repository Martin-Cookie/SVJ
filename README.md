# SVJ Správa

Webová aplikace pro automatizaci správy SVJ (Společenství vlastníků jednotek). Spravuje evidenci vlastníků a jednotek, hlasování per rollam, rozúčtování daní a synchronizaci dat s externími zdroji.

## Tech stack

- **Backend:** FastAPI + SQLAlchemy ORM + SQLite
- **Frontend:** Jinja2 šablony + HTMX + Tailwind CSS (CDN)
- **Dokumenty:** openpyxl (Excel), docxtpl (Word), pdfplumber (PDF), Tesseract (OCR)
- **Email:** SMTP s TLS

## Instalace

```bash
git clone https://github.com/Martin-Cookie/SVJ.git
cd SVJ
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt  # nebo: pip install fastapi uvicorn[standard] sqlalchemy pydantic-settings jinja2 python-multipart openpyxl python-docx docxtpl pdfplumber pytesseract Pillow unidecode
cp .env.example .env  # upravit SMTP a cesty
```

## Spuštění

```bash
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

Aplikace běží na http://localhost:8000

## Moduly

### A. Evidence vlastníků (`/vlastnici`)

- Import z Excelu (31 sloupců, sheet `Vlastnici_SVJ`) s náhledem a potvrzením
- Historie importů s možností smazání (smaže vlastníky, jednotky i přiřazení)
- Seznam s vyhledáváním (jméno, email, telefon, RČ, IČ, č. jednotky)
- Filtrační bubliny podle typu vlastníka (fyzická/právnická osoba) a sekce domu
- Filtrační bubliny podle typu vlastnictví (SJM, VL, SJVL, Výhradní, Podílové, Neuvedeno)
- Filtrační bubliny kontaktů: s/bez emailu, s/bez telefonu (rozdělené bubliny)
- Všechny bubliny dynamicky roztažené na celou šířku (flex-1)
- Zachování filtrů při navigaci seznam → detail → detail → zpět (back URL řetěz)
- Řazení kliknutím na hlavičky sloupců (jméno, typ, email, telefon, podíl, jednotky, sekce)
- Sticky hlavička tabulky
- RČ/IČ viditelné v seznamu i detailu
- Porovnání podílů: prohlášení vlastníka vs evidence s barevným rozdílem a %
- Detail vlastníka:
  - Inline editace kontaktů (email, telefon) přes HTMX
  - Inline editace trvalé a korespondenční adresy přes HTMX
  - Správa přiřazených jednotek (přidat z dropdownu, odebrat)
  - Sloupec Podíl % (podíl SČD / celkový počet podílů z administrace)
  - Souhrnný řádek Celkem (podíl SČD, podíl %, plocha)
  - Proklik na detail jednotky
- Export zpět do Excelu

### B. Evidence jednotek (`/jednotky`)

- Seznam jednotek s vyhledáváním (číslo, budova, typ, sekce, adresa, vlastník)
- Filtrační bubliny podle typu prostoru a sekce domu (dynamicky roztažené na celou šířku)
- Zachování filtrů při navigaci seznam → detail → zpět (back URL řetěz)
- Řazení kliknutím na hlavičky sloupců
- Porovnání podílů: prohlášení vlastníka vs evidence s barevným rozdílem a %
- Vytvoření nové jednotky (inline HTMX formulář)
- Detail jednotky:
  - Inline editace všech polí přes HTMX (číslo, budova, typ, sekce, adresa, LV, místnosti, plocha, podíl)
  - Seznam vlastníků s prokliky
  - Smazání jednotky (cascade smaže přiřazení)
- Číslo jednotky uloženo jako INTEGER

### C. Hlasování per rollam (`/hlasovani`)

- Vytvoření hlasování (název, termíny, kvórum)
- Nahrání šablony hlasovacího lístku (.docx)
- Automatická extrakce bodů hlasování z šablony
- Přidání a smazání jednotlivých bodů hlasování
- Generování personalizovaných PDF lístků pro každého vlastníka
- Seznam hlasování s výsledky po bodech (PRO/PROTI/Zdržel se s procenty)
- Seznam lístků s dynamickými sloupci hlasování pro každý bod
- Detail hlasovacího lístku s prokliky na vlastníka
- Zpracování lístků: zadání hlasů (PRO/PROTI/Zdržel se) pro každý bod
- Sčítání hlasů a výpočet kvóra
- Podpora hlasování v zastoupení (plné moci)
- Stavy hlasování: návrh → aktivní → uzavřené / zrušené
- Přehled neodevzdaných lístků

### D. Rozúčtování příjmů (`/dane`)

- Nahrání daňových PDF dokumentů
- Extrakce jmen z PDF (pdfplumber)
- Fuzzy párování jmen na vlastníky v databázi (práh 0.6 pro jednotku, 0.75 globálně)
- Ruční ověření a oprava párování
- Hromadné rozeslání emailem s přílohami

### E. Kontrola vlastníků (`/synchronizace`)

- Nahrání CSV exportu (např. ze sousede.cz) — stránka s formulářem a historií kontrol
- Historie kontrol s možností smazání (cascade smaže záznamy i CSV soubor)
- Porovnání s daty v databázi (inteligentní párování jmen)
- Rozlišení: úplná shoda / částečná shoda / přeházená jména / rozdílní vlastníci / rozdílné podíly / chybí
- Klikací filtrační bubliny s dynamickými počty a souhrny podílů:
  - Každá bublina zobrazuje podíly v evidenci, CSV a rozdíl
  - Bublina „Vše" zobrazuje i katastrální podíl (4 103 391) s procentuálními rozdíly
  - Bublina „Rozdílné podíly" filtruje záznamy kde se liší pouze podíl SČD
- Třídění kliknutím na hlavičky sloupců (jednotka, vlastník, typ, vlastnictví, podíl, shoda)
- Selektivní aktualizace dat z CSV do databáze:
  - Checkboxy u lišících se polí (jméno, typ, vlastnictví, podíl)
  - Řádkový checkbox pro hromadné zaškrtnutí všech polí záznamu
  - Toolbar: Vybrat vše / Zrušit výběr / počítadlo / Aktualizovat vybrané
  - Po aktualizaci se přepočítá status záznamu a počítadla v bublinách
- Aktualizace jmen více vlastníků (SJM): fuzzy párování jednotlivých jmen
- Logování změn: každá úprava zaznamenána s názvem zdrojového CSV a časem
- Proklik jména vlastníka do detailní karty s návratem zpět na porovnání
- Přenos kontaktů (email, telefon) z CSV do databáze

### F. Administrace SVJ (`/sprava`)

- Informace o SVJ (název, typ budovy, celkový počet podílů) — read-only pohled + inline editace
- Správa adres SVJ — přidání, editace, smazání s řazením abecedně
- Členové výboru — přidání, inline editace, smazání (jméno, role, email, telefon)
- Členové kontrolního orgánu — stejná funkcionalita
- Autocomplete rolí přes `<datalist>` (Předseda/Místopředseda/Člen)
- Řazení členů: předsedové → místopředsedové → ostatní, v rámci role abecedně
- Zálohování a obnova dat:
  - Vytvoření zálohy (ZIP: databáze + uploads + generované soubory)
  - Seznam existujících záloh s datem, velikostí, stažením a smazáním
  - Obnova ze zálohy (upload ZIP) — před obnovou se automaticky vytvoří pojistná záloha
- Hromadné úpravy (`/sprava/hromadne-upravy`):
  - Výběr pole (typ prostoru, sekce, počet místností, vlastnictví, adresa, orientační číslo)
  - Tabulka unikátních hodnot s počtem výskytů
  - Rozkliknutí hodnoty zobrazí všechny záznamy (jednotky nebo vlastnictví) s detailními údaji
  - Inline oprava s datalist napovídáním — hromadné přepsání všech záznamů se shodnou hodnotou
- Všechny sekce zabaleny do skládacích `<details>` bloků
- Modely: `SvjInfo`, `SvjAddress`, `BoardMember`

### G. Nastavení (`/nastaveni`)

- Přehled odeslaných emailů (posledních 50)

## Struktura projektu

```
app/
├── main.py                    # FastAPI aplikace
├── config.py                  # Nastavení (Pydantic)
├── database.py                # SQLAlchemy engine + session
├── models/                    # Databázové modely
│   ├── owner.py               #   Owner, Unit, OwnerUnit, Proxy
│   ├── voting.py              #   Voting, VotingItem, Ballot, BallotVote
│   ├── tax.py                 #   TaxSession, TaxDocument, TaxDistribution
│   ├── sync.py                #   SyncSession, SyncRecord
│   ├── common.py              #   EmailLog, ImportLog
│   └── administration.py      #   SvjInfo, SvjAddress, BoardMember
├── routers/                   # HTTP endpointy
│   ├── dashboard.py           #   GET /
│   ├── owners.py              #   /vlastnici (+ /vlastnici/import)
│   ├── units.py               #   /jednotky
│   ├── voting.py              #   /hlasovani
│   ├── tax.py                 #   /dane
│   ├── sync.py                #   /synchronizace
│   ├── administration.py      #   /sprava
│   └── settings_page.py       #   /nastaveni
├── services/                  # Business logika
│   ├── excel_import.py        #   Import z 31-sloupcového Excelu
│   ├── excel_export.py        #   Export do Excelu
│   ├── word_parser.py         #   Extrakce bodů z .docx šablony
│   ├── pdf_generator.py       #   Generování PDF lístků
│   ├── pdf_extractor.py       #   Extrakce textu z PDF
│   ├── owner_matcher.py       #   Fuzzy párování jmen
│   ├── csv_comparator.py      #   Porovnání CSV vs Excel
│   ├── backup_service.py      #   Zálohování a obnova dat (ZIP)
│   └── email_service.py       #   SMTP odesílání emailů
├── templates/                 # Jinja2 šablony
│   ├── base.html              #   Layout se sidebar navigací
│   ├── dashboard.html         #   Přehled (statistiky vlastníků, jednotek, podílů)
│   ├── settings.html          #   Nastavení
│   ├── owners/                #   Stránky vlastníků
│   │   ├── list.html          #     Seznam vlastníků
│   │   ├── detail.html        #     Detail vlastníka
│   │   ├── import.html        #     Import z Excelu + historie
│   │   ├── import_preview.html#     Náhled před importem
│   │   └── import_result.html #     Výsledek importu
│   ├── units/                 #   Stránky jednotek
│   │   ├── list.html          #     Seznam jednotek
│   │   └── detail.html        #     Detail jednotky
│   ├── voting/                #   Stránky hlasování
│   │   ├── index.html         #     Seznam hlasování
│   │   ├── create.html        #     Vytvoření hlasování
│   │   ├── detail.html        #     Detail hlasování
│   │   ├── ballots.html       #     Seznam lístků
│   │   ├── ballot_detail.html #     Detail hlasovacího lístku
│   │   ├── process.html       #     Zpracování lístků
│   │   └── not_submitted.html #     Neodevzdané lístky
│   ├── tax/                   #   Stránky daní
│   │   ├── index.html         #     Seznam rozúčtování
│   │   ├── upload.html        #     Nahrání PDF
│   │   └── matching.html      #     Párování dokumentů
│   ├── sync/                  #   Stránky synchronizace
│   │   ├── index.html         #     Nahrání CSV + historie kontrol
│   │   └── compare.html       #     Porovnání s filtry a bublinami
│   ├── administration/        #   Stránky administrace
│   │   ├── index.html         #     Info SVJ, adresy, výbor, kontrolní orgán
│   │   ├── bulk_edit.html     #     Hromadné úpravy — výběr pole
│   │   ├── bulk_edit_values.html #  HTMX: tabulka unikátních hodnot
│   │   └── bulk_edit_records.html # HTMX: záznamy pro danou hodnotu
│   └── partials/              #   HTMX komponenty
│       ├── owner_row.html
│       ├── owner_table_body.html
│       ├── owner_contact_form.html
│       ├── owner_contact_info.html
│       ├── owner_address_form.html
│       ├── owner_address_info.html
│       ├── owner_units_section.html
│       ├── unit_row.html
│       ├── unit_table_body.html
│       ├── unit_create_form.html
│       ├── unit_edit_form.html
│       ├── unit_info.html
│       ├── sync_row.html
│       ├── tax_match_row.html
│       └── ballot_processed.html
└── static/                    # CSS, JS
    ├── css/custom.css
    └── js/app.js
data/
├── svj.db                     # SQLite databáze
├── uploads/                   # Nahrané soubory (Excel, CSV, PDF)
├── generated/                 # Generované dokumenty (PDF lístky)
└── backups/                   # ZIP zálohy (DB + uploads + generated)
```

## API endpointy

### Vlastníci (`/vlastnici`)

| Metoda | Cesta | Popis |
|--------|-------|-------|
| GET | `/vlastnici` | Seznam vlastníků (search, filtr, řazení) |
| GET | `/vlastnici/import` | Stránka importu z Excelu + historie |
| POST | `/vlastnici/import` | Nahrání Excel souboru → náhled |
| POST | `/vlastnici/import/potvrdit` | Potvrzení importu → uložení |
| POST | `/vlastnici/import/{log_id}/smazat` | Smazání importu (data + soubor) |
| GET | `/vlastnici/{id}` | Detail vlastníka |
| GET | `/vlastnici/{id}/upravit-formular` | HTMX: formulář kontaktů |
| GET | `/vlastnici/{id}/info` | HTMX: zobrazení kontaktů |
| POST | `/vlastnici/{id}/upravit` | Uložení kontaktů |
| GET | `/vlastnici/{id}/adresa/{prefix}/upravit-formular` | HTMX: formulář adresy (perm/corr) |
| GET | `/vlastnici/{id}/adresa/{prefix}/info` | HTMX: zobrazení adresy |
| POST | `/vlastnici/{id}/adresa/{prefix}/upravit` | Uložení adresy |
| POST | `/vlastnici/{id}/jednotky/pridat` | Přidat jednotku vlastníkovi |
| POST | `/vlastnici/{id}/jednotky/{ou_id}/odebrat` | Odebrat jednotku vlastníkovi |

### Jednotky (`/jednotky`)

| Metoda | Cesta | Popis |
|--------|-------|-------|
| GET | `/jednotky` | Seznam jednotek (search, filtr, řazení) |
| GET | `/jednotky/nova-formular` | HTMX: formulář nové jednotky |
| POST | `/jednotky/nova` | Vytvoření jednotky |
| GET | `/jednotky/{id}` | Detail jednotky |
| GET | `/jednotky/{id}/upravit-formular` | HTMX: formulář editace |
| GET | `/jednotky/{id}/info` | HTMX: zobrazení údajů |
| POST | `/jednotky/{id}/upravit` | Uložení údajů jednotky |

### Hlasování (`/hlasovani`)

| Metoda | Cesta | Popis |
|--------|-------|-------|
| GET | `/hlasovani` | Seznam hlasování |
| GET | `/hlasovani/nova` | Formulář nového hlasování |
| POST | `/hlasovani/nova` | Vytvoření hlasování + šablona .docx |
| GET | `/hlasovani/{id}` | Detail hlasování s výsledky |
| POST | `/hlasovani/{id}/stav` | Změna stavu hlasování |
| POST | `/hlasovani/{id}/pridat-bod` | Přidání bodu hlasování |
| POST | `/hlasovani/{id}/smazat-bod/{item_id}` | Smazání bodu hlasování |
| POST | `/hlasovani/{id}/generovat` | Generování PDF lístků |
| GET | `/hlasovani/{id}/listky` | Seznam lístků s hlasy po bodech |
| GET | `/hlasovani/{id}/listek/{ballot_id}` | Detail hlasovacího lístku |
| GET | `/hlasovani/{id}/zpracovani` | Stránka zpracování lístků |
| POST | `/hlasovani/{id}/zpracovat/{ballot_id}` | Zpracování jednoho lístku |
| GET | `/hlasovani/{id}/neodevzdane` | Neodevzdané lístky |

### Rozúčtování (`/dane`)

| Metoda | Cesta | Popis |
|--------|-------|-------|
| GET | `/dane` | Seznam rozúčtování |
| GET | `/dane/nova` | Formulář nového rozúčtování |
| POST | `/dane/nova` | Vytvoření s nahráním PDF |
| GET | `/dane/{id}` | Detail s párováním dokumentů |
| POST | `/dane/{id}/potvrdit/{dist_id}` | Potvrzení automatického párování |
| POST | `/dane/{id}/prirazeni/{doc_id}` | Ruční přiřazení dokumentu |

### Kontrola vlastníků (`/synchronizace`)

| Metoda | Cesta | Popis |
|--------|-------|-------|
| GET | `/synchronizace` | Nahrání CSV + historie kontrol |
| POST | `/synchronizace/nova` | Nahrání a porovnání CSV |
| POST | `/synchronizace/{id}/smazat` | Smazání kontroly (záznamy + CSV) |
| GET | `/synchronizace/{id}` | Porovnání s filtry a bublinami |
| POST | `/synchronizace/{id}/aktualizovat` | Aplikace vybraných změn z CSV |
| POST | `/synchronizace/{id}/aplikovat-kontakty` | Přenos kontaktů z CSV |
| POST | `/synchronizace/{id}/exportovat` | Export do Excelu |
| POST | `/synchronizace/{id}/prijmout/{rec_id}` | Přijetí změny |
| POST | `/synchronizace/{id}/odmitnout/{rec_id}` | Odmítnutí změny |
| POST | `/synchronizace/{id}/upravit/{rec_id}` | Ruční úprava jména |

### Administrace (`/sprava`)

| Metoda | Cesta | Popis |
|--------|-------|-------|
| GET | `/sprava` | Stránka administrace SVJ |
| POST | `/sprava/info` | Uložení info o SVJ (název, typ, podíly) |
| POST | `/sprava/adresa/pridat` | Přidání adresy SVJ |
| POST | `/sprava/adresa/{id}/upravit` | Editace adresy |
| POST | `/sprava/adresa/{id}/smazat` | Smazání adresy |
| POST | `/sprava/clen/pridat` | Přidání člena (výbor/kontrolní orgán) |
| POST | `/sprava/clen/{id}/upravit` | Editace člena |
| POST | `/sprava/clen/{id}/smazat` | Smazání člena |
| POST | `/sprava/zaloha/vytvorit` | Vytvoření zálohy (ZIP) |
| GET | `/sprava/zaloha/{filename}/stahnout` | Stažení zálohy |
| POST | `/sprava/zaloha/{filename}/smazat` | Smazání zálohy |
| POST | `/sprava/zaloha/obnovit` | Obnova dat ze zálohy (upload ZIP) |
| GET | `/sprava/hromadne-upravy` | Stránka hromadných úprav |
| GET | `/sprava/hromadne-upravy/hodnoty` | HTMX: tabulka unikátních hodnot pole |
| GET | `/sprava/hromadne-upravy/zaznamy` | HTMX: záznamy pro danou hodnotu |
| POST | `/sprava/hromadne-upravy/opravit` | Hromadná oprava hodnoty |

## Konfigurace (.env)

```env
DATABASE_PATH=data/svj.db
UPLOAD_DIR=data/uploads
GENERATED_DIR=data/generated
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=svj@example.com
SMTP_FROM_NAME=SVJ
LIBREOFFICE_PATH=/Applications/LibreOffice.app/Contents/MacOS/soffice
```

## Datový model

- **Owner** — vlastník (jméno, tituly, RČ/IČ, adresy, kontakty, is_active)
- **Unit** — jednotka (číslo KN jako INTEGER, budova, sekce, plocha, podíl SČD)
- **OwnerUnit** — vazba vlastník-jednotka (typ vlastnictví, podíl, hlasovací váha)
- **Proxy** — plná moc pro hlasování
- **Voting** → VotingItem → Ballot → BallotVote
- **TaxSession** → TaxDocument → TaxDistribution
- **SyncSession** → SyncRecord (cascade delete)
- **SvjInfo** → SvjAddress — informace o SVJ a adresy
- **BoardMember** — členové výboru a kontrolního orgánu (group: board/control)
- **EmailLog**, **ImportLog** — systémové logy

## UI vzory

- **Dashboard** — přehled s klikacími bublinami (vlastníci, jednotky, hlasování) a modulovými kartami, vše dynamicky roztažené na šířku; bublina hlasování zobrazuje seznam aktivních/konceptových hlasování se stavem a názvem (truncate + tooltip)
- **Sidebar navigace** — fixní levý panel (w-44) s ikonami a sekcemi
- **Filtrační bubliny** — klikací filtry nad tabulkou s počty záznamů, dynamicky roztažené na celou šířku, rozdělené bubliny (s/bez emailu, s/bez telefonu)
- **Back URL řetěz** — zachování filtrů a šipky "Zpět na přehled" při navigaci dashboard → seznam → detail → zpět přes celý řetěz (parametr `back` propagován přes bubliny, hledání, řazení, HTMX a detailové odkazy)
- **Sticky hlavičky** — záhlaví tabulek zůstává viditelné při scrollu
- **HTMX inline editace** — formuláře pro kontakty, adresy a údaje jednotek se přepínají bez reloadu
- **Dvousloupcový layout** — formulář vlevo + historie vpravo (import, kontrola)
- **Flex layout s fixní hlavičkou** — `height:calc(100vh - 48px)` pro stránky kde scrolluje jen tělo tabulky
