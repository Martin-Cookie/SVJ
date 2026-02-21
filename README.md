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

- Import z Excelu (31 sloupců, sheet `Vlastnici_SVJ`)
- Seznam s vyhledáváním (jméno, email, telefon, RČ, IČ, č. jednotky)
- Filtrování podle typu vlastníka a sekce domu
- Řazení kliknutím na hlavičky sloupců
- Detail vlastníka (kontakty, adresy, jednotky)
- Export zpět do Excelu

### B. Hlasování per rollam (`/hlasovani`)

- Vytvoření hlasování (název, termíny, kvórum)
- Nahrání šablony hlasovacího lístku (.docx)
- Automatická extrakce bodů hlasování z šablony
- Generování personalizovaných PDF lístků pro každého vlastníka
- Zpracování naskenovaných lístků (OCR)
- Sčítání hlasů a výpočet kvóra
- Podpora hlasování v zastoupení (plné moci)

### C. Rozúčtování příjmů (`/dane`)

- Nahrání daňových PDF dokumentů
- Extrakce jmen z PDF (pdfplumber)
- Fuzzy párování jmen na vlastníky v databázi
- Ruční ověření a oprava párování
- Hromadné rozeslání emailem s přílohami

### D. Kontrola vlastníků (`/synchronizace`)

- Nahrání CSV exportu (např. ze sousede.cz)
- Porovnání s Excel daty (inteligentní párování jmen)
- Rozlišení: úplná shoda / částečná shoda / přeházená jména / rozdílní vlastníci / chybí
- Klikací filtry podle typu výsledku s dynamickými počty
- Třídění kliknutím na hlavičky sloupců (jednotka, vlastník, typ, vlastnictví, podíl, shoda)
- Selektivní aktualizace dat z CSV do databáze:
  - Checkboxy u lišících se polí (jméno, typ, vlastnictví, podíl)
  - Řádkový checkbox pro hromadné zaškrtnutí všech polí záznamu
  - Toolbar: Vybrat vše / Zrušit výběr / počítadlo / Aktualizovat vybrané
  - Po aktualizaci se přepočítá status záznamu a počítadla v bublinách
- Logování změn: každá úprava zaznamenána s názvem zdrojového CSV a časem
- Přenos kontaktů z CSV do databáze

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
│   └── common.py              #   EmailLog, ImportLog
├── routers/                   # HTTP endpointy
│   ├── dashboard.py           #   GET /
│   ├── owners.py              #   /vlastnici
│   ├── voting.py              #   /hlasovani
│   ├── tax.py                 #   /dane
│   ├── sync.py                #   /synchronizace
│   └── settings_page.py       #   /nastaveni
├── services/                  # Business logika
│   ├── excel_import.py        #   Import z 31-sloupcového Excelu
│   ├── excel_export.py        #   Export do Excelu
│   ├── word_parser.py         #   Extrakce bodů z .docx šablony
│   ├── pdf_generator.py       #   Generování PDF lístků
│   ├── pdf_extractor.py       #   Extrakce textu z PDF
│   ├── owner_matcher.py       #   Fuzzy párování jmen
│   ├── csv_comparator.py      #   Porovnání CSV vs Excel
│   └── email_service.py       #   SMTP odesílání emailů
├── templates/                 # Jinja2 šablony
│   ├── base.html              #   Layout se sidebar navigací
│   ├── owners/                #   Stránky vlastníků
│   ├── voting/                #   Stránky hlasování
│   ├── tax/                   #   Stránky daní
│   ├── sync/                  #   Stránky synchronizace
│   └── partials/              #   HTMX komponenty
└── static/                    # CSS, JS
data/
├── svj.db                     # SQLite databáze
├── uploads/                   # Nahrané soubory
└── generated/                 # Generované dokumenty
```

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

- **Owner** — vlastník (jméno, tituly, RČ/IČ, adresy, kontakty)
- **Unit** — jednotka (číslo KN, sekce, plocha, podíl SČD)
- **OwnerUnit** — vazba vlastník-jednotka (typ vlastnictví, hlasovací váha)
- **Voting** → VotingItem → Ballot → BallotVote
- **TaxSession** → TaxDocument → TaxDistribution
- **SyncSession** → SyncRecord
- **Proxy** — plná moc pro hlasování
- **EmailLog**, **ImportLog** — systémové logy
