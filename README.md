# SVJ Správa

Webová aplikace pro automatizaci správy SVJ (Společenství vlastníků jednotek). Spravuje evidenci vlastníků a jednotek, hlasování per rollam, rozúčtování daní a synchronizaci dat s externími zdroji.

## Tech stack

- **Backend:** FastAPI + SQLAlchemy ORM + SQLite
- **Frontend:** Jinja2 šablony + HTMX + Tailwind CSS (CDN) + dark mode (CSS override, přepínač v sidebaru)
- **Dokumenty:** openpyxl (Excel), docxtpl (Word), pdfplumber (PDF)
- **Email:** SMTP s TLS

## Instalace

```bash
git clone https://github.com/Martin-Cookie/SVJ.git
cd SVJ
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env  # upravit SMTP a cesty
```

## Spuštění

```bash
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

Aplikace běží na http://localhost:8000

### Spuštění z USB (jiný počítač)

Pro spuštění na jiném Macu bez nutnosti klonovat repozitář:

1. **Příprava USB** (na tvém počítači):
   ```bash
   ./pripravit_usb.sh    # stáhne offline balíčky do wheels/
   ```
   Zkopírovat celou složku `SVJ/` na USB **bez** `.venv/`

2. **Na cílovém počítači**: dvakrát kliknout na `spustit.command`

Skript automaticky vytvoří virtuální prostředí, nainstaluje závislosti (offline z wheels nebo online) a spustí aplikaci.

**Požadavky na cílovém počítači:**
- Python 3.9+ (`python3 --version`)
- LibreOffice (volitelně, jen pro generování PDF lístků)

## Testy a CI

```bash
python3 -m pytest tests/ -v          # spustit všechny testy
python3 -m pytest tests/ -q --tb=short  # stručný výstup
```

**336 testů** (~4s, in-memory SQLite) pokrývá:

| Soubor | Testů | Oblast |
|--------|-------|--------|
| `test_csv_comparator.py` | 77 | CSV parsing, fuzzy matching, Czech stemming |
| `test_voting.py` | 72 | wizard, ballot stats, import, SJM párování |
| `test_payment_advanced.py` | 50 | space matching, confirm/reject, lock, multi-unit, endpoints, diacritics |
| `test_backup.py` | 43 | lock, ZIP create/restore, cleanup, integrity |
| `test_payment_matching.py` | 33 | matching pipeline, settlement, rounding |
| `test_smoke.py` | 19 | app start, dashboard, routes smoke |
| `test_tenants.py` | 12 | dedup helper, resolved properties, multi-space, /prostory/novy flow |
| `test_owner_matcher.py` | 10 | TITLE_PATTERNS, Czech surname stemming, stem overlap |
| `test_import_mapping.py` | 9 | column detection, mapping validation |
| `test_email_service.py` | 5 | SMTP, template rendering |
| `test_voting_aggregation.py` | 3 | vote aggregation pipeline |
| `test_contact_import.py` | 3 | contact import flow |

**Automatizace:**
- **Pre-push hook** — testy se spustí automaticky před každým `git push`. Pokud selžou, push se zablokuje
- **GitHub Actions** — testy běží při push na `main`/`Platby` a při pull requestech (`.github/workflows/tests.yml`)

## Moduly

### A. Evidence vlastníků (`/vlastnici`)

- Vytvoření nového vlastníka (inline HTMX formulář: příjmení, jméno, titul, typ, email, telefon, RČ/IČ)
- Import z Excelu s dynamickým mapováním sloupců:
  - Upload → automatická detekce mapování (31 polí v 6 skupinách: Jednotka, Vlastník, Trvalá adresa, Korespondenční adresa, Kontakty, Ostatní)
  - Mapování uložené v DB (`SvjInfo.owner_import_mapping`) — při dalším importu předvyplněné
  - Výběr sheetu a počátečního řádku dat, uložení mapování pro příští import
  - 4-krokový sub-stepper: Nahrání → Mapování → Náhled → Výsledek
  - Náhled a potvrzení importu
- Historia importů s možností smazání (smaže vlastníky, jednotky i přiřazení)
- **Import kontaktů** (dolní sekce na `/vlastnici/import`):
  - Nahrání Excelu se kontaktními údaji s dynamickým mapováním sloupců (17 polí v 5 skupinách: Párování, Kontakty, Identifikace, Trvalá adresa, Korespondenční adresa)
  - Mapování uložené v DB (`SvjInfo.contact_import_mapping`) — při dalším importu předvyplněné
  - Párování Excel řádků na vlastníky v evidenci (fuzzy match podle jména + fallback RČ/IČ)
  - Podpora IČ (company_id field) pro právnické osoby + detekce RČ vs IČ podle typu vlastníka
  - Progress bar s reálným procentem a odhadem zbývajícího času (ETA) během zpracování
  - Normalizace telefonních čísel (607179964 ≡ +420 607 179 964, automatické přidání +420 prefix pro 9-ciferná čísla)
  - Náhled změn po párování s filtrační kartami (stat kardy na field badges):
    - Stat karty: Celkem / Spárováno / Bez spárování / S změnami
    - Field badges: klikací filtry zobrazující počet změn v každém poli
  - Selektivní výběr vlastníků k importu (checkboxy + "Vybrat vše")
  - Volba režimu: „Doplnit" (ponechat existující hodnoty) nebo „Přepsat" (nahradit prázdné i vyplněné)
  - Inteligentní routing do sekundárních polí: když Excel má jiný telefon/email než DB, automaticky nabídne doplnění do sekundárního pole (GSM 2, Email 2) místo přepisu primárního — modrý badge v náhledu
  - Výsledková zpráva s počtem aktualizovaných vlastníků a polí
- Seznam s vyhledáváním (jméno, email, telefon, RČ, IČ, č. jednotky)
- Filtrační bubliny podle typu vlastníka (fyzická/právnická osoba) a sekce domu
- Filtrační bubliny podle typu vlastnictví (SJM, VL, SJVL, Výhradní, Podílové, Neuvedeno)
- Filtrační bubliny kontaktů: s/bez emailu, s/bez telefonu (rozdělené bubliny)
- Filtrační bublina „Bez jednotky" — vlastníci bez aktuální jednotky (historičtí, po výměně)
- Všechny bubliny dynamicky roztažené na celou šířku (flex-1)
- Zachování filtrů při navigaci seznam → detail → detail → zpět (back URL řetěz)
- Řazení kliknutím na hlavičky sloupců (jméno, typ, email, telefon, podíl, jednotky, sekce)
- Sticky hlavička tabulky
- RČ/IČ viditelné v seznamu i detailu
- Porovnání podílů: prohlášení vlastníka vs evidence s barevným rozdílem a %
- Detail vlastníka:
  - Inline editace identity přes HTMX (typ osoby, jméno/příjmení/titul, RČ/IČ, název firmy)
  - Přepínání fyzická/právnická osoba s dynamickým zobrazením relevantních polí
  - Automatická detekce duplicitních záznamů po uložení identity (podle name_normalized)
  - Sloučení duplicit: přesun jednotek pod hlavního vlastníka, doplnění kontaktů/adres, deaktivace duplikátů
  - OOB aktualizace záhlaví stránky (jméno + badge typ/RČ/IČ) a sekce Jednotky po sloučení
  - Inline editace kontaktů (email, email 2, telefon GSM, GSM 2, pevný) přes HTMX
  - Inline editace trvalé a korespondenční adresy přes HTMX
  - Uložit/Zrušit tlačítka nahoře vedle nadpisu sekce (ne dole pod formulářem)
  - Správa přiřazených jednotek (klik „+ Přidat" → Uložit/Zrušit nahoře nahradí tlačítko, formulář dole; odebrat ikonou koše)
  - Sloupec Podíl % (podíl SČD / celkový počet podílů z administrace)
  - Souhrnný řádek Celkem (podíl SČD, podíl %, plocha)
  - Proklik na detail jednotky
  - Kolapsovatelná sekce „Historie vlastnictví" — předchozí jednotky s daty od/do, prokliky s back URL chain
- Export do Excelu/CSV s aktuálními filtry

### B. Evidence jednotek (`/jednotky`)

- Seznam jednotek s vyhledáváním (číslo, budova, typ, sekce, adresa, vlastník včetně historických)
- Filtrační bubliny podle typu prostoru a sekce domu (dynamicky roztažené na celou šířku)
- Zachování filtrů při navigaci seznam → detail → zpět (back URL řetěz)
- Řazení kliknutím na hlavičky sloupců
- Porovnání podílů: prohlášení vlastníka vs evidence s barevným rozdílem a %
- Vytvoření nové jednotky (inline HTMX formulář)
- Detail jednotky:
  - Inline editace všech polí přes HTMX (číslo, budova, typ, sekce, adresa, LV, místnosti, plocha, podíl)
  - Uložit/Zrušit tlačítka nahoře vedle nadpisu sekce
  - Seznam vlastníků s prokliky (aktuální modře, historičtí šedě), editace ikonou tužky
  - Kolapsovatelná sekce „Předchozí vlastníci" — historické záznamy s daty od/do, prokliky s back URL chain
  - Smazání jednotky (cascade smaže přiřazení)
- Číslo jednotky uloženo jako INTEGER
- Export do Excelu/CSV s aktuálními filtry

### C. Hlasování per rollam (`/hlasovani`)

- Vytvoření hlasování (název, termíny, kvórum)
- Nahrání šablony hlasovacího lístku (.docx)
- Automatická extrakce bodů hlasování z šablony
- Automatická extrakce metadat z .docx šablony (název, popis, data zahájení/ukončení):
  - AJAX náhled při výběru souboru — předvyplní prázdná pole formuláře
  - Parsování českých dat (DD.MM.YYYY i „19. ledna 2026")
  - Název: z document properties, Heading 1, nebo regex „per rollam" + datum
  - Popis: text mezi názvem a prvním BODem (filtruje boilerplate)
  - Server-side prefill prázdných polí při odeslání formuláře
- Přidání a smazání jednotlivých bodů hlasování (pouze ve stavu koncept)
- Generování personalizovaných PDF lístků pro každého vlastníka
- Smazání hlasování z přehledu (cascade smaže body, lístky, hlasy + soubory) s potvrzovacím dialogem
- Seznam hlasování s výsledky po bodech (PRO/PROTI/Zdržel se s procenty)
- Wizard stepper: kompaktní kroky (Nastavení → Generování → Zpracování → Výsledky → Uzavření) na kartách i detail stránkách; po uzavření hlasování všechny kroky zelené
- Filtrační bubliny dle stavu hlasování (vše, koncept, aktivní, uzavřeno, zrušeno)
- Sdílený header na všech stránkách hlasování (partial `_voting_header.html`) s popisem hlasování
- Status bubliny fixně nahoře (celkem, zbývá zpracovat, odesláno, zpracováno, neodevzdané, kvórum) — nescrollují se
- Aktivní bublina zvýrazněna ring-2 dle aktuální stránky/filtru
- Viditelnost UI dle stavu: koncept zobrazuje správu bodů + generování, po generování výsledky + zpracování
- Detail hlasování: vyhledávání v bodech + řazení sloupců (HTMX partial)
- Seznam lístků s vyhledáváním vlastníka a řazením všech sloupců (vlastník, jednotky, hlasy, body hlasování, plná moc, stav)
- Klikací vlastníci a jednotky v seznamu lístků i neodevzdaných — prokliky s back URL a scroll restoration
- Detail hlasovacího lístku s prokliky na vlastníka (back URL chain pro zanoření)
- Zpracování lístků: zadání hlasů (PRO/PROTI/Zdržel se) s vyhledáváním vlastníka
- Neodevzdané lístky s vyhledáváním (diacritics-insensitive, jméno, email), server-side řazení (vlastník, jednotky, email, hlasy, stav), klikací vlastníci a jednotky s back URL, export do Excelu
- Sčítání hlasů a výpočet kvóra (vstup v %, uložení jako podíl 0–1)
- Podpora hlasování v zastoupení (plné moci)
- Stavy hlasování: koncept → aktivní → uzavřené / zrušené
- Zpracování lístků: řazení dle vlastníka/jednotek/hlasů
- Hromadné zpracování: checkboxy, select all, batch zadání hlasů pro více lístků najednou
- Oprava zpracovaného lístku: reset hlasů a znovu zpracování (tlačítko „Opravit" na detailu lístku)
- Import výsledků hlasování z Excelu:
  - 4-krokový flow: upload → mapování sloupců → náhled → potvrzení
  - Mapování sloupců na role (vlastník, jednotka, bod hlasování) s předvyplněním z uloženého mapování (globálně sdílené napříč hlasováními)
  - Konfigurovatelné hodnoty PRO/PROTI (výchozí 1,ANO / 0,NE)
  - Nastavitelný počáteční řádek dat
  - Režim importu: doplnit (ponechat existující) nebo vyčistit a přepsat
  - Automatické párování spoluvlastníků (SJM): pokud Excel řádek má hlasy, aplikují se na všechny vlastníky sdílející tutéž jednotku
  - Podpora porovnávacích operátorů (`>0`, `<0`, `>=`, `<=`) pro hodnoty PRO/PROTI
  - Náhled s filtračními bublinami (přiřazeno/nepřiřazeno/nerozpoznáno/chyby)
  - Detekce nerozpoznaných hodnot: řádky s vyplněnými buňkami, které neodpovídají pravidlům PRO/PROTI, se zobrazí v oranžové bublině „Nerozpoznáno" se surovými hodnotami
  - Výsledek s prokliky na zpracované/nezpracované lístky

### D. Hromadné rozesílání (`/dane`)

- Nahrání daňových PDF dokumentů (jednotlivě nebo celý adresář) s progress barem:
  - Upload progress bar (XMLHttpRequest s upload.onprogress) — okamžitá zpětná vazba při nahrávání stovek souborů
  - Automatické filtrování ne-PDF souborů při uploadu adresáře (webkitdirectory posílá i .DS_Store apod.)
  - Zvýšený limit max_files na 5000 (Starlette default 1000), optimalizovaná validace velikosti bez čtení celého souboru do paměti
  - Soubory se uloží na disk, zpracování běží na pozadí (vlákno)
  - Zpracovací progress bar s počtem zpracovaných/celkem, procentuální lištou, názvem aktuálního souboru, uplynulým časem a odhadem zbývajícího (ETA)
  - HTMX polling (500ms), po dokončení automatický redirect na párování
- Extrakce jmen z PDF (pdfplumber):
  - Primárně jednotlivá jména ze sekce „Údaje o vlastníkovi:" (SP řádky na str. 1)
  - Podpora formátu bez SP řádků (Příjmy) — standalone jména za hlavičkou sekce
  - Podpora firemních názvů začínajících číslem (např. „35 ASSOCIATES INVESTMENT GROUP s.r.o.")
  - Fallback na kombinované jméno ze sekce „Vlastník:" (str. 2)
  - Slučování firemních názvů rozlomených přes více SP řádků (detekce suffixů s.r.o., a.s., z.s. atd. a all-uppercase fragmentů)
- Fuzzy párování jmen na vlastníky v databázi — každé jméno z PDF se páruje zvlášť:
  - Nejdřív shoda na vlastníky dané jednotky (práh 0.6), pak globální hledání (práh 0.75)
  - Lokální matching zahrnuje i bývalé vlastníky překrývající se s daňovým rokem (valid_from/valid_to)
  - Globální matching vyžaduje shodu stemovaného příjmení (`require_stem_overlap`) — zabraňuje false positive kde se shoduje jen křestní jméno (např. Bartíková→Birčáková přes sdílené „Barbora")
  - Sloupec „Jméno z PDF" zobrazuje všechna individuální jména oddělená čárkou
  - Spoluvlastníci se přidávají pouze pokud jsou nalezeni v PDF, nikoliv z databáze
  - Ruční přiřazení automaticky přidá spoluvlastníky na stejné jednotce
- X tlačítko (odebrat vlastníka) skryto u potvrzených distribucí a u 100% shody
- Redesignovaná stránka přiřazení:
  - Fixní header s 5 stat kartami (celkem / potvrzeno / k potvrzení / nepřiřazeno / bez PDF) — HTMX partial swap při kliknutí na bublinu/řadící hlavičku (bez full reload)
  - Bublina „Bez PDF" (oranžová) — jednotky s vlastníky, pro které nebyl nahrán žádný dokument; tabulka s prokliky na jednotku a vlastníky
  - Obnova scroll pozice při návratu z detailu vlastníka/jednotky (globální mechanismus v app.js — sessionStorage + přesná pixelová pozice)
  - Toolbar s checkboxy: vybrat/zrušit vše, potvrdit vybrané, potvrdit vše
  - Multi-owner zobrazení: barevné badge s X odebráním pro každého vlastníka
  - Dropdown přiřazení s `display_name (j. X, Y)` — zobrazuje čísla jednotek
  - 7 sortable sloupců (checkbox, soubor, jednotka, jméno z PDF, vlastníci, shoda, akce)
- Odebrání vlastníka z dokumentu (pokud poslední → UNMATCHED)
- Přidání externího příjemce (ad-hoc jméno + email)
- Přejmenování relace (inline HTMX editace názvu — tlačítko „Uložit")
- Workflow dokončení relace:
  - „Zavřít" — návrat na seznam relací
  - „Uzamknout" — uzamknutí relace (read-only mód, nelze měnit přiřazení)
  - „Odemknout" — odemknutí uzamčené relace pro další úpravy (krok 1 zůstane zelený pokud existují dokumenty)
  - „Pokračovat na rozesílku →" — přechod k odesílání emailů (pouze u dokončených)
  - „Nahrát další PDF" — obrysové tlačítko na stránce přiřazení pro doplnění/přepsání dokumentů
  - Re-import: volba režimu „Doplnit k existujícím" / „Přepsat stávající" (smaže staré PDF + přiřazení)
  - Read-only mód: skryté checkboxy, assign dropdown, potvrdit/odebrat tlačítka, externí formulář; viditelné statusové štítky (Potvrzeno/Nepřiřazeno/Nepotvrzeno)
- Rozesílka (`/dane/{id}/rozeslat`):
  - Stat karty jako filtry (celkem, s emailem, čekající, odesláno, chyba, bez emailu) — HTMX partial swap, scroll pozice při návratu z detailu
  - Bublina „Bez emailu" (oranžová) — filtruje příjemce bez nastavené emailové adresy
  - Duální email: vlastníci se dvěma emaily (primární + sekundární) mají checkboxy pro výběr kam poslat; HTMX toggle s propagací na sibling distribuce
  - Multi-adresní odesílání: email se odešle na všechny zaškrtnuté adresy (samostatný email na každou adresu)
  - Rozlišení odeslaných/neodeslaných dokumentů: zelený badge (odesláno) vs modrý (k odeslání), dva řádky s labelem při mixu
  - Přidání nového PDF k již odeslané sadě: pošle jen nové přílohy, existující neopakuje
  - Konfigurace emailu: po uložení zůstane rozbalená, po odeslání testu se zavře
  - Odeslat test automaticky uloží předmět a text (neztratí se neuložené změny)
  - Tlačítko „Zavřít" — návrat na seznam relací (výběr emailů se ukládá automaticky přes HTMX)
  - Samostatný search bar pod kartami s HTMX partial swapem
  - Vyhledávání příjemců (jméno, email, název souboru) s diacritics-insensitive porovnáním
  - Server-side řazení (příjemce, email, počet dokumentů, stav) s HTMX partial
  - Bookmarkovatelné URL parametry (q, filtr, sort, order)
  - Pouze potvrzená přiřazení (CONFIRMED + MANUAL) — nepotvrzené auto-shody se přeskočí s varovným bannerem a odkazem zpět na přiřazení
  - Testovací email s prefixem `[TEST]` v předmětu pro odlišení od ostrých emailů
- Wizard stepper: kompaktní kroky (Nahrání PDF → Přiřazení → Rozesílka → Dokončeno) na kartách i detail stránkách; po dokončení workflow všechny kroky zelené
- Index stránka:
  - Filtrační bubliny podle stavu (vše, rozpracováno, připraveno, odesílání, dokončeno)
  - Compact wizard stepper na kartě každé relace
  - Progress bar „Potvrzeno X / Y" na každé kartě relace
  - Stavové badge: „Rozpracováno" (žlutá), „Dokončeno" (zelená), „Odesílá se" (modrá), „Odesláno" (modrá), „Pozastaveno" (žlutá)
  - Odkaz „Rozeslat →" u READY session — přímý přístup k rozesílce ze seznamu
- Smazání celé relace (session + dokumenty + distribuce + soubory)

### E. Evidence plateb (`/platby`)

Modul pro správu předpisů, bankovních výpisů, variabilních symbolů a přehledu plateb.

- **Předpisy** — import z DOCX, automatické párování na jednotky, správa roků předpisů, detekce VS konfliktů při importu (pokud VS z DOCX ukazuje na jinou jednotku než existující mapování — potvrzovací dialog s přehledem konfliktů)
- **Variabilní symboly** — mapování VS → jednotka/prostor (ruční + automatické z předpisů), inline editace s přepínačem entity (Jednotka/Prostor), editovatelné VS pole
- **Bankovní výpisy** — import Fio CSV (reimport zachová ruční přiřazení), 3-fázové automatické párování plateb:
  - Fáze 1: VS → `VariableSymbolMapping` lookup (výsledek: AUTO_MATCHED)
  - Fáze 2: Fallback jméno odesílatele + částka vs předpis (výsledek: SUGGESTED); podpora multi-unit plateb — kombinace jednotek jednoho vlastníka kde součet předpisů odpovídá částce
  - Fáze 3: VS-prefix dekódování + skórovací systém (jméno + částka + VS shoda; výsledek: SUGGESTED při skóre ≥ 5)
  - Stavy párování: `AUTO_MATCHED`, `SUGGESTED`, `MANUAL`, `UNMATCHED` — jako potvrzené (confirmed) se počítají pouze `AUTO_MATCHED` + `MANUAL`; `SUGGESTED` vyžaduje ruční potvrzení/odmítnutí
  - Ruční přiřazení: single-unit (celá částka) i multi-unit (čísla oddělená čárkou, částka rozdělena proporcionálně dle předpisů)
  - PaymentAllocation: dual-write model — každé přiřazení vytváří alokační záznamy (podpora multi-unit plateb kde jedna platba pokrývá více jednotek); `unit_id` nullable (pro space-only alokace), `space_id` + `prescription_id` FK
  - Detail výpisu: filtr bubliny dle entity (Vše/Jednotky/Prostory), samostatný sloupec Prostor; hromadné potvrzení všech navržených přiřazení; suggestion dropdowny s předvýběrem dle jména protiúčtu (zelené zvýraznění, potvrzovací tlačítko ✓)
  - Zamčení/odemčení výpisu (`locked_at`) — zamčený výpis nelze přepárovat, měnit ani mazat
- **Počáteční zůstatky** — evidované zůstatky per jednotka/rok s vazbou na vlastníka; import z Excelu (.xlsx/.xls) s 4-krokovým workflow (upload → mapování sloupců → náhled → potvrzení); ruční přidání/editace s dynamickým výběrem vlastníka; zobrazení dluhů v seznamech i detailech jednotek a vlastníků
- **Matice plateb** — přehled jednotek/prostorů × 12 měsíců s barevným stavem (zaplaceno/částečně/nezaplaceno), přepínač entity (jednotky/prostory), filtry dle typu prostoru, řazení, hledání, export xlsx
- **Dlužníci** — seznam jednotek s dluhem seřazený dle výše dluhu
- **Detail plateb jednotky** — měsíční grid + seznam přijatých plateb
- **Vyúčtování** — roční vyúčtování per jednotka (předpis × 12 vs. zaplaceno), rozpad po položkách, změna stavu (vygenerováno → odesláno → zaplaceno / po splatnosti), hledání, řazení, bubliny dle stavu, hromadná změna stavu, export do Excelu (souhrn / s položkami)
- **Nesrovnalosti v platbách** — automatická detekce chyb v napárovaných platbách:
  - Typy: špatný VS (`wrong_vs`), nesprávná částka (`wrong_amount`), sloučená platba (`combined`)
  - Náhled s checkboxy pro výběr příjemců, testovací email, dávkové odesílání s progress barem
  - SJM podpora — příjemce se vybírá dle shody jména odesílatele platby s vlastníkem jednotky
  - Sdílený progress bar (`partials/_send_progress.html`) s Pozastavit/Pokračovat/Zrušit (sdílený s hromadným rozesíláním)
- **Dashboard integrace** — 5. karta na hlavním dashboardu (napárované platby, výpisy)
- **Badge v detailu jednotky** — "Zaplaceno ✓" (zelený) nebo "Dluh X Kč" (červený/žlutý)

### F. Prostory a nájemci (`/prostory`, `/najemci`)

Evidence pronajímaných společných prostorů SVJ (sklady, nebytové prostory, kočárkárny) a jejich nájemců.

- **Prostory** — CRUD s řaditelnými sloupci, hledáním, filtry (stav, sekce), bubliny (pronajato/volné/blokované), export Excel/CSV; formulář vytvoření prostoru s volitelnými poli nájemce (auto-vytvoří Tenant + SpaceTenant + VS mapping + Prescription)
- **Nájemci** — CRUD s per-section inline editací (identita, kontakt, adresy), propojení na vlastníky (Tenant ↔ Owner), resolved properties (jméno, telefon, email, RČ, IČ, typ se čtou z Owner pokud propojený), export Excel/CSV
  - **Multi-space**: 1 nájemce může mít souběžně více prostor (více smluv). Seznam zobrazuje jeden řádek per nájemce se stacked prostory/nájemným/VS pod sebou, detail má sekci „Aktuální prostory (N)", export 1 řádek per smlouva
  - **Deduplikace**: `find_existing_tenant()` helper (priorita owner_id → RČ → IČ → jméno+typ) zabraňuje vytváření duplicitních nájemců při create přes `/najemci/novy` i při inline vytvoření v `/prostory/novy`. Historické duplicity řeší startup migrace `_migrate_dedupe_tenants` (sloučí záznamy, vítěz = nejvíce vyplněných polí, SpaceTenant vztahy se přesunou na vítěze)
  - **Rozdělené pole jméno** v `/prostory/novy`: formulář má dvě pole `tenant_last_name` + `tenant_first_name` (ne jedno `tenant_name`). Validace: při zadání jakéhokoliv údaje nájemce je příjmení povinné
- **Nájemní vztahy** (SpaceTenant) — přiřazení nájemce k prostoru s detaily smlouvy (číslo, datum, nájemné, VS, PDF příloha). Detail prostoru podporuje inline editaci aktuálního nájemního vztahu (VS, nájemné, číslo smlouvy, PDF) přes HTMX info/form partial vzor
- **Platební integrace**:
  - Auto-vytvoření `VariableSymbolMapping` (space_id) při přiřazení nájemce s VS
  - Auto-vytvoření `Prescription` (space_id) při přiřazení nájemce s nájemným
  - VS stránka zobrazuje prostory i jednotky (filtr bubliny Jednotky/Prostory)
  - Matice plateb + dlužníci s přepínačem entity (jednotky/prostory)
  - Detail plateb prostoru (`/platby/prostor/{id}`)
  - Matching engine: VS + name matching rozšířeno pro prostory (Tenant.name_normalized)
  - Bankovní výpisy: zobrazení `P {číslo}` badge pro space matche
- **Import z Excelu** — 4-krokový wizard (upload → mapování → náhled → potvrzení):
  - Auto-detekce sloupců (11 polí: číslo, označení, sekce, podlaží, výměra, nájemce, telefon, email, smlouva, nájemné, VS)
  - Auto-detekce blokovaných prostorů (klíčová slova: kočárkárna, ústředna, trezor, kotelna atd.)
  - Propojení nájemců na vlastníky (Owner matching v náhledu)
  - Additivní import (existující prostory se nepřepisují)
- **Dashboard** — stat karta Prostory (pronajato/volné/blokované + expirace smluv ≤3 měsíce)
- **Purge** — kategorie "Prostory a nájemci" v administraci

### G. Kontroly (`/synchronizace`)

Sloučená stránka se dvěma sekcemi — Kontrola vlastníků (nahoře) a Kontrola podílů (dole). Každá sekce má upload formulář a historii kontrol s nezávislým vyhledáváním.

#### Kontrola vlastníků

- Nahrání CSV exportu (sousede.cz nebo interní export aplikace) — stránka s formulářem a historií kontrol (search + sort s HTMX partial)
- Automatická detekce formátu CSV: sousede.cz (Vlastníci jednotky) i interní export (Příjmení + Jméno)
- BOM stripping pro korektní parsování UTF-8 souborů s BOM
- Sloučení spoluvlastníků z interního exportu (řádek na vlastníka → jeden záznam na jednotku)
- Historie kontrol s možností smazání (cascade smaže záznamy i CSV soubor)
- Porovnání s daty v databázi (inteligentní párování jmen)
- Rozlišení: úplná shoda / částečná shoda / přeházená jména / rozdílní vlastníci / rozdílné podíly / chybí
- Klikací filtrační bubliny s dynamickými počty a souhrny podílů:
  - Každá bublina zobrazuje podíly v evidenci, CSV a rozdíl
  - Bublina „Vše" zobrazuje i katastrální podíl (4 103 391) s procentuálními rozdíly
  - Bublina „Rozdílné podíly" filtruje záznamy kde se liší pouze podíl SČD
  - Bubliny i řazení zachovávají back URL pro správnou navigaci zpět
- Vyhledávání v porovnání (jednotka, vlastník, typ — diacritics-insensitive, HTMX live search s `hx-target="main"` swapem)
- Třídění kliknutím na hlavičky sloupců (jednotka, vlastník, typ, vlastnictví, podíl, shoda)
- Selektivní aktualizace dat z CSV do databáze:
  - Checkboxy u lišících se polí (jméno, typ, vlastnictví, podíl)
  - Řádkový checkbox pro hromadné zaškrtnutí všech polí záznamu
  - Toolbar: Vybrat vše / Zrušit výběr / počítadlo / Aktualizovat vybrané
  - Po aktualizaci se přepočítá status záznamu a počítadla v bublinách
- Aktualizace vlastníků přes checkbox: matchování CSV jmen na DB (fuzzy ≥75%), přejmenování shodných, přidání nových, hard-delete nepárovaných OwnerUnit (bez historie — historie se tvoří pouze přes Výměnu)
- Aktualizace ownership_type se propisuje všem spoluvlastníkům na jednotce (checkbox i výměna)
- Logování změn: každá úprava zaznamenána s názvem zdrojového CSV a časem
- Proklik jména vlastníka do detailní karty s návratem zpět na porovnání
- Export filtrovaného pohledu do Excelu (evidence vs CSV sloupce, žluté zvýraznění rozdílů)
- Přenos kontaktů (email, telefon) z CSV do databáze
- Výměna vlastníků:
  - Preview výměny s porovnáním starých a nových vlastníků (přeškrtnutí → zelené badge)
  - Inteligentní párování: existující vlastník (přesná shoda), možná shoda (fuzzy ≥90%), nový vlastník
  - Rovnoměrné rozdělení hlasů mezi spoluvlastníky s upozorněním na kontrolu na LV
  - Změny typu prostoru a druhu vlastnictví pokud se liší
  - Hromadná výměna všech rozdílných záznamů najednou
  - Date picker pro datum výměny (výchozí dnešní, uživatel může změnit)
  - Soft-delete: pouze nepárované OwnerUnit dostanou valid_to; shodní vlastníci zachováni beze změny
  - Vlastníci bez jednotek zůstávají v evidenci (zešedlý řádek, opacity-50)
  - Zachování filtru a scroll pozice při navigaci zpět z výměny (filtr + #sync-{id} anchor)
  - Logování změn do ImportLog

### H. Administrace SVJ (`/sprava`)

- Informace o SVJ (název, typ budovy, celkový počet podílů) — read-only pohled + inline editace
- Správa adres SVJ — přidání, editace, smazání s řazením abecedně
- Členové výboru — přidání, inline editace, smazání (jméno, role, email, telefon)
- Členové kontrolního orgánu — stejná funkcionalita
- Autocomplete rolí přes `<datalist>` (Předseda/Místopředseda/Člen)
- Řazení členů: předsedové → místopředsedové → ostatní, v rámci role abecedně
- Zálohování a obnova dat:
  - Vytvoření zálohy (ZIP: databáze + uploads + generované soubory + .env + manifest.json) s vlastním názvem
  - Ochrana proti prázdným zálohám (varování pokud nejsou žádná data)
  - ZIP validace: CRC integrity check (`testzip()`) před obnovou — odmítne poškozené archivy
  - Disk space check: kontrola volného místa (2× heuristika) před vytvořením zálohy
  - Auto-cleanup: automatická rotace záloh (max 10), nejstarší se mažou po vytvoření nové
  - Celková velikost záloh zobrazena v UI
  - Seznam existujících záloh s datem, velikostí, stažením a smazáním
  - Obnova ze zálohy — tři způsoby:
    - Upload ZIP souboru
    - Upload složky rozbalené zálohy z Finderu (webkitdirectory) — obnoví DB + uploads + generated
    - Upload souboru svj.db
  - Před každou obnovou se automaticky vytvoří pojistná záloha
  - Rollback: při selhání obnovy automatický návrat do původního stavu ze safety backup
  - File lock: souběžné restore operace blokované přes `.restore_lock` (stale lock timeout 10 min)
  - Po obnově automatická migrace (engine.dispose + přidání chybějících sloupců/indexů) — server nepadá
  - Migrace vrací warnings — UI zobrazí varování pokud některé neproběhly
  - Flash zpráva po úspěšné obnově i vytvoření zálohy, chybové hlášky při selhání
  - Side-by-side layout: vytvořit zálohu vlevo, obnovit vpravo
  - `application/octet-stream` pro stahování — Safari nerozbaluje automaticky
  - WAL mode: SQLite journal_mode=WAL pro lepší concurrent read/write
- Smazání dat:
  - Výběr kategorií ke smazání (vlastníci, hlasování, daně, synchronizace, kontrola podílu, logy, administrace, zálohy, historie obnovení)
  - Checkbox „Vybrat/Zrušit vše" pro hromadné označení
  - Počet záznamů a popis u každé kategorie (DB modely i souborové kategorie)
  - Potvrzení zadáním slova DELETE — tlačítko disabled dokud není zadáno
  - Cascade smazání v bezpečném pořadí (děti před rodiči)
  - Varování o kaskádovém mazání (smazání vlastníků automaticky smaže i synchronizační data)
  - Granulární mazání souborů — každá kategorie maže jen své upload adresáře (ne celý uploads/)
- Export dat:
  - Výběr kategorií k exportu s checkboxy a „Vybrat/Zrušit vše"
  - Počet záznamů a popis u každé kategorie
  - Stažení ve formátu Excel (xlsx) nebo CSV (UTF-8 s BOM)
  - Hromadný export: jedna kategorie = přímý soubor, více kategorií = ZIP archiv
  - 7 kategorií: vlastníci a jednotky, hlasování, daňové podklady, synchronizace, kontrola podílu, logy, administrace
  - Export administrace zahrnuje číselníky i emailové šablony
- Číselníky (centrálně spravované kódy):
  - 4 kategorie: Typ prostoru, Sekce, Počet místností, Typ vlastnictví
  - Automatické naplnění z existujících unikátních hodnot v DB při prvním startu
  - Inline editace: klik na hodnotu → input na místě (Enter uloží, Esc zruší)
  - Smazání pouze nepoužívaných položek (používané nemají ikony akce)
  - Zobrazení počtu použití u každé položky
  - 2×2 grid kompaktních karet v administraci
  - Dropdowny (`<select>`) ve všech formulářích: vytvoření/editace jednotky, přidání jednotky vlastníkovi
  - Edge case: hodnota mimo číselník se zobrazí jako extra `<option>` v editačním formuláři
  - Integrace s hromadnými úpravami (suggestions z číselníku)
  - Zahrnuty v purge kategorie „administrace" (po smazání a restartu se znovu seedují)
  - Zahrnuty v SQLite záloze (full file backup)
- Emailové šablony:
  - Správa šablon pro hromadné rozesílání (název, předmět, text s placeholder `{rok}`)
  - CRUD na stránce číselníků (přidat, upravit, smazat)
  - Výchozí šablona „Rozúčtování příjmů" seedována při prvním startu
  - Integrace do formuláře nového rozesílání — dropdown s automatickým vyplněním polí
  - Placeholder `{rok}` nahrazen aktuálním rokem při výběru šablony
- Hromadné úpravy (`/sprava/hromadne-upravy`):
  - Výběr pole (typ prostoru, sekce, počet místností, vlastnictví druh, vlastnictví/podíl, adresa, orientační číslo)
  - Tabulka unikátních hodnot s počtem výskytů
  - Rozkliknutí hodnoty zobrazí všechny záznamy (jednotky nebo vlastnictví) s detailními údaji
  - Prokliky na detail jednotky a detail vlastníka s navigací zpět
  - Třídění sloupců kliknutím na hlavičky (klientské řazení)
  - Checkboxy pro selektivní opravu — vybrat/zrušit vše + počítadlo + indeterminate stav
  - Persistence výběru checkboxů přes sessionStorage (zachová se při navigaci na detail a zpět)
  - Inline oprava s datalist napovídáním — přepsání vybraných záznamů
- Všechny sekce zabaleny do skládacích `<details>` bloků
- Modely: `SvjInfo`, `SvjAddress`, `BoardMember`, `CodeListItem`, `EmailTemplate`

#### Kontrola podílů

- Nahrání CSV, XLSX nebo XLS souboru s podíly SČD
- Automatická detekce sloupců (case-insensitive kandidáti) s fallbackem na uloženou historii mapování
- Náhled vzorkových hodnot u každého sloupce při výběru mapování
- Podpora starého .xls formátu (xlrd) i .xlsx (openpyxl)
- CSV: auto-detekce oddělovače (středník/čárka) a kódování (UTF-8/Windows-1250)
- Parsování čísla jednotky z formátu „1098/14" → 14, podílu z „12212/4103391" → 12212
- Deduplikace spoluvlastníků (stejná jednotka → první výskyt)
- Porovnání s evidencí: shoda / rozdíl / chybí v DB / chybí v souboru
- Filtrační bubliny s dynamickými počty a souhrny podílů (DB, soubor, rozdíl)
- Klikací jména vlastníků s proklikem na detail a návratem zpět
- Klikací čísla jednotek s proklikem na detail a návratem zpět
- Vyhledávání v porovnání (jednotka, vlastník — diacritics-insensitive, HTMX live search s `hx-target="main"` swapem)
- Třídění kliknutím na hlavičky sloupců
- Selektivní aktualizace: checkboxy u rozdílů → batch update Unit.podil_scd
- Historie kontrol s vyhledáváním a řazením (soubor, datum, shoda, rozdíly) s HTMX partial
- Stará URL `/kontrola-podilu` automaticky přesměruje na `/synchronizace#kontrola-podilu`

### I. Nastavení (`/nastaveni`)

- SMTP konfigurace — read-only přehled (4-sloupcový grid) + inline editace (HTMX)
- Výchozí nastavení odesílání (kolapsovatelná sekce) — globální defaults pro dávku, interval, potvrzení, testovací email. Nové rozesílky a nesrovnalosti dědí tato nastavení, lze je pak přepsat per-session/per-výpis
- Historie odeslaných emailů (posledních 100):
  - Řaditelné sloupce (datum, modul, příjemce, předmět, stav) s šipkami
  - Hledání (příjemce, email, předmět, modul — diacritics-insensitive)
  - Prokliky na detail vlastníka u příjemců nalezených v DB (s back URL pro návrat)
  - Klikací přílohy — náhled/stažení PDF a dalších souborů přímo z email logu (`target="_blank"`)
  - Plné cesty příloh uložené v DB (zpětně kompatibilní se starými záznamy bez cest)
  - Status badge: OK (zelená), Chyba (červená s tooltip), Čeká (žlutá)
  - HTMX partial pro live search, flex layout s fixní hlavičkou

## Struktura projektu

```
app/
├── main.py                    # FastAPI aplikace
├── config.py                  # Nastavení (Pydantic)
├── database.py                # SQLAlchemy engine + session
├── utils.py                   # Sdílené utility (utcnow, strip_diacritics, build_list_url, is_htmx_partial, fmt_num, is_safe_path, validate_upload, validate_uploads, setup_jinja_filters, excel_auto_width, compute_eta, build_wizard_steps, build_name_with_titles, render_email_template, UPLOAD_LIMITS, is_valid_email, templates)
├── models/                    # Databázové modely
│   ├── owner.py               #   Owner, Unit, OwnerUnit, Proxy
│   ├── voting.py              #   Voting, VotingItem, Ballot, BallotVote
│   ├── tax.py                 #   TaxSession, TaxDocument, TaxDistribution
│   ├── sync.py                #   SyncSession, SyncRecord
│   ├── share_check.py         #   ShareCheckSession, ShareCheckRecord, ShareCheckColumnMapping
│   ├── payment.py             #   PrescriptionYear, Prescription, PrescriptionItem, VariableSymbolMapping, BankStatement, Payment, PaymentAllocation, BankStatementColumnMapping, UnitBalance, Settlement, SettlementItem
│   ├── space.py               #   Space, SpaceStatus, Tenant, SpaceTenant
│   ├── common.py              #   EmailLog (+ name_normalized), ImportLog, ActivityLog, ActivityAction, log_activity()
│   └── administration.py      #   SvjInfo (+ owner/contact_import_mapping), SvjAddress, BoardMember, CodeListItem, EmailTemplate
├── routers/                   # HTTP endpointy
│   ├── dashboard.py           #   GET /
│   ├── owners/                #   /vlastnici (crud, import vlastníků, import kontaktů)
│   │   ├── __init__.py
│   │   ├── crud.py            #   CRUD, detail, export
│   │   ├── import_owners.py   #   Import vlastníků z Excelu (mapování + náhled)
│   │   ├── import_contacts.py #   Import kontaktů z Excelu (mapování + zpracování)
│   │   └── _helpers.py        #   Sdílené funkce (uložení/načtení mapování)
│   ├── units.py               #   /jednotky
│   ├── voting/                #   /hlasovani (session, ballots, import_votes, _helpers)
│   │   ├── __init__.py
│   │   ├── session.py         #   CRUD, detail, generování lístků, export
│   │   ├── ballots.py         #   Seznam lístků, zpracování, neodevzdané
│   │   ├── import_votes.py    #   Import výsledků z Excelu
│   │   └── _helpers.py        #   _voting_wizard, _ballot_stats
│   ├── tax/                   #   /dane (session, processing, matching, sending, _helpers)
│   │   ├── __init__.py
│   │   ├── session.py         #   CRUD, detail, export
│   │   ├── processing.py      #   PDF zpracování, progress
│   │   ├── matching.py        #   Přiřazení, potvrzení
│   │   ├── sending.py         #   Email rozesílání, progress
│   │   └── _helpers.py        #   _tax_wizard, _session_stats, _find_coowners
│   ├── payments/              #   /platby (předpisy, symboly, výpisy, zůstatky, přehled, vyúčtování)
│   │   ├── __init__.py
│   │   ├── prescriptions.py   #   Import DOCX, seznam, detail, VS konflikty
│   │   ├── symbols.py         #   Variabilní symboly CRUD + inline edit
│   │   ├── statements.py      #   Import CSV, detail, párování, lock/unlock
│   │   ├── balances.py        #   Počáteční zůstatky
│   │   ├── overview.py        #   Matice plateb, dlužníci, detail jednotky
│   │   ├── settlement.py      #   Vyúčtování CRUD, export
│   │   ├── discrepancies.py   #   Nesrovnalosti v platbách, email upozornění, progress
│   │   └── _helpers.py        #   compute_nav_stats, sdílené funkce
│   ├── spaces/                #   /prostory (CRUD, import)
│   │   ├── __init__.py
│   │   ├── crud.py            #   Seznam, detail, inline edit, nájemce přiřazení/ukončení
│   │   ├── import_spaces.py   #   Import prostorů z Excelu (mapování + náhled)
│   │   └── _helpers.py        #   Sdílené funkce
│   ├── tenants/               #   /najemci (CRUD, per-section inline edit)
│   │   ├── __init__.py
│   │   ├── crud.py            #   Seznam, detail, identita/kontakt/adresa editace
│   │   └── _helpers.py        #   Sdílené funkce
│   ├── sync/                  #   /synchronizace (sloučená stránka Kontroly)
│   │   ├── session.py         #   Seznam, vytvoření, smazání, detail, export
│   │   ├── contacts.py        #   Přijetí/zamítnutí změn, aplikace kontaktů
│   │   ├── exchange.py        #   Výměna vlastníků preview + potvrzení
│   │   └── _helpers.py        #   Sdílené konstanty a funkce
│   ├── share_check.py         #   /kontrola-podilu (detail + redirect na /synchronizace)
│   ├── administration/        #   /sprava
│   │   ├── info.py            #   SVJ info CRUD, adresy
│   │   ├── board.py           #   Členové výboru
│   │   ├── code_lists.py      #   Číselníky + emailové šablony
│   │   ├── backups.py         #   Zálohy vytvoření/stažení/mazání/obnova
│   │   ├── bulk.py            #   Export, purge, hromadné úpravy, duplicity
│   │   └── _helpers.py        #   DB_PATH, BACKUP_DIR, _PURGE_ORDER
│   └── settings_page.py       #   /nastaveni
├── services/                  # Business logika
│   ├── excel_import.py        #   Import z 31-sloupcového Excelu
│   ├── excel_export.py        #   Export do Excelu
│   ├── word_parser.py         #   Extrakce bodů a metadat z .docx šablony
│   ├── pdf_generator.py       #   Generování PDF lístků
│   ├── pdf_extractor.py       #   Extrakce textu a jmen vlastníků z PDF
│   ├── owner_matcher.py       #   Fuzzy párování jmen
│   ├── owner_service.py       #   Sloučení duplicitních vlastníků
│   ├── voting_import.py       #   Import výsledků hlasování z Excelu
│   ├── csv_comparator.py      #   Porovnání CSV vs Excel
│   ├── contact_import.py      #   Import kontaktních údajů
│   ├── share_check_comparator.py #  Parsování souboru + porovnání podílů SČD
│   ├── owner_exchange.py      #   Výměna vlastníků při synchronizaci
│   ├── backup_service.py      #   Zálohování a obnova dat (ZIP)
│   ├── data_export.py         #   Export dat do Excel/CSV (7 kategorií)
│   ├── import_mapping.py      #   Definice polí a auto-detekce mapování pro import vlastníků/kontaktů/zůstatků
│   ├── balance_import.py      #   Import počátečních zůstatků z Excelu (.xlsx/.xls)
│   ├── email_service.py       #   SMTP odesílání emailů
│   ├── code_list_service.py   #   Sdílený přístup k číselníkům
│   ├── prescription_import.py #   Parsování DOCX předpisů
│   ├── bank_import.py         #   Parsování Fio CSV bankovních výpisů
│   ├── payment_matching.py    #   3-fázové párování plateb (VS, jméno+částka, VS-prefix)
│   ├── payment_discrepancy.py #   Detekce nesrovnalostí v platbách, SJM matching, email kontext
│   ├── payment_overview.py    #   Matice plateb, dlužníci, detail jednotky
│   ├── settlement_service.py  #   Logika vyúčtování (generování, přepočet)
│   └── space_import.py        #   Import prostorů z Excelu
├── templates/                 # Jinja2 šablony
│   ├── base.html              #   Layout se sidebar navigací
│   ├── dashboard.html         #   Přehled (statistiky vlastníků, jednotek, podílů)
│   ├── dashboard_shares.html  #   Breakdown rozdílu podílů
│   ├── settings.html          #   Nastavení
│   ├── owners/                #   Stránky vlastníků
│   │   ├── list.html          #     Seznam vlastníků
│   │   ├── detail.html        #     Detail vlastníka
│   │   ├── import.html        #     Import z Excelu + historie
│   │   ├── owner_import_mapping.html #  Mapování sloupců pro import vlastníků
│   │   ├── import_preview.html#     Náhled před importem
│   │   ├── import_result.html #     Výsledek importu
│   │   ├── contact_import.html #    Import kontaktů — hlavní stránka
│   │   ├── contact_import_mapping.html # Mapování sloupců pro import kontaktů
│   │   ├── contact_import_processing.html # Progress bar zpracování kontaktů
│   │   ├── contact_import_preview.html #  Náhled párování kontaktů
│   │   └── contact_import_result.html #   Výsledek importu kontaktů
│   ├── units/                 #   Stránky jednotek
│   │   ├── list.html          #     Seznam jednotek
│   │   └── detail.html        #     Detail jednotky
│   ├── voting/                #   Stránky hlasování
│   │   ├── _voting_header.html#     Sdílený header (title, bubliny) — fixní
│   │   ├── index.html         #     Seznam hlasování
│   │   ├── create.html        #     Vytvoření hlasování
│   │   ├── detail.html        #     Detail hlasování (výsledky po bodech)
│   │   ├── detail_results.html#     HTMX: tbody řádky výsledků
│   │   ├── ballots.html       #     Seznam lístků (search + sort)
│   │   ├── ballots_table.html #     HTMX: tbody řádky lístků
│   │   ├── ballot_detail.html #     Detail hlasovacího lístku
│   │   ├── process.html       #     Zpracování lístků (search)
│   │   ├── process_cards.html #     HTMX: karty lístků ke zpracování
│   │   ├── not_submitted.html #     Neodevzdané lístky (search)
│   │   ├── not_submitted_table.html # HTMX: tbody řádky neodevzdaných
│   │   ├── import_upload.html #     Import výsledků: upload souboru
│   │   ├── import_mapping.html#     Import: mapování sloupců
│   │   ├── import_preview.html#     Import: náhled přiřazení
│   │   └── import_result.html #     Import: výsledek importu
│   ├── tax/                   #   Stránky daní
│   │   ├── index.html         #     Seznam rozesílání
│   │   ├── upload.html        #     Nahrání PDF (nová relace)
│   │   ├── upload_additional.html #  Nahrání dalších PDF (append/overwrite)
│   │   ├── processing.html    #     Progress bar zpracování PDF
│   │   ├── matching.html      #     Párování dokumentů
│   │   ├── sending.html       #     Progress rozesílky emailů
│   │   └── send.html          #     Rozesílka emailů (search + sort)
│   ├── sync/                  #   Stránky synchronizace
│   │   ├── index.html         #     Nahrání CSV + historie kontrol
│   │   ├── upload.html        #     Nahrání CSV souboru
│   │   ├── compare.html       #     Porovnání s filtry a bublinami
│   │   ├── contacts_preview.html #  Náhled přenosu kontaktů
│   │   └── exchange_preview.html #  Preview výměny vlastníků
│   ├── share_check/           #   Stránky kontroly podílu (upload + historie na sloučené /synchronizace)
│   │   ├── mapping.html       #     Mapování sloupců (krok 2)
│   │   └── compare.html       #     Výsledky s filtry a bublinami
│   ├── administration/        #   Stránky administrace
│   │   ├── index.html         #     Info SVJ, adresy, výbor, kontrolní orgán, číselníky
│   │   ├── svj_info.html      #     HTMX: sekce info o SVJ
│   │   ├── code_lists.html    #     HTMX: sekce číselníků
│   │   ├── backups.html       #     HTMX: sekce záloh
│   │   ├── purge.html         #     HTMX: sekce mazání dat
│   │   ├── export.html        #     HTMX: sekce exportu
│   │   ├── bulk_edit.html     #     Hromadné úpravy — výběr pole
│   │   ├── duplicates.html    #     Přehled a sloučení duplicitních vlastníků
│   │   ├── bulk_edit_values.html #  HTMX: tabulka unikátních hodnot
│   │   └── bulk_edit_records.html # HTMX: záznamy pro danou hodnotu
│   ├── payments/              #   Stránky plateb
│   │   ├── predpisy.html      #     Seznam předpisů (roky)
│   │   ├── predpisy_import.html #   Import předpisů (DOCX upload, VS konflikt dialog)
│   │   ├── predpisy_detail.html #   Detail roku předpisů
│   │   ├── predpis_detail.html #    Detail jednoho předpisu (položky)
│   │   ├── symboly.html       #     Variabilní symboly
│   │   ├── zustatky.html      #     Počáteční zůstatky
│   │   ├── zustatky_import.html #   Import zůstatků (upload)
│   │   ├── zustatky_mapping.html #  Import — mapování sloupců
│   │   ├── zustatky_preview.html #  Import — náhled před potvrzením
│   │   ├── vypisy.html        #     Seznam bankovních výpisů
│   │   ├── vypis_import.html  #     Import výpisu (CSV upload, confirm overwrite)
│   │   ├── vypis_detail.html  #     Detail výpisu s platbami (filtry, search, lock)
│   │   ├── prehled.html       #     Matice plateb (jednotky × měsíce)
│   │   ├── dluznici.html      #     Seznam dlužníků
│   │   ├── jednotka_platby.html #   Detail plateb jednotky
│   │   ├── prostor_platby.html #   Detail plateb prostoru
│   │   ├── vyuctovani.html    #     Seznam vyúčtování
│   │   ├── vyuctovani_detail.html # Detail vyúčtování
│   │   ├── nesrovnalosti_preview.html # Náhled nesrovnalostí (checkboxy, test email)
│   │   └── nesrovnalosti_progress.html # Progress odesílání upozornění
│   ├── spaces/                #   Stránky prostorů
│   │   ├── list.html          #     Seznam prostorů
│   │   ├── detail.html        #     Detail prostoru (info + nájemce + historie)
│   │   ├── space_import.html  #     Import — upload
│   │   ├── space_import_mapping.html # Import — mapování sloupců
│   │   ├── space_import_preview.html # Import — náhled
│   │   ├── space_import_result.html #  Import — výsledek
│   │   └── partials/          #     HTMX partials (_create_form, _row, _tbody, _space_info, _tenant_info)
│   ├── tenants/               #   Stránky nájemců
│   │   ├── list.html          #     Seznam nájemců
│   │   ├── detail.html        #     Detail nájemce (per-section inline edit)
│   │   └── partials/          #     HTMX partials (_create_form, _row, _tbody, _tenant_info,
│   │                          #       _tenant_identity_form/info, _tenant_contact_form/info,
│   │                          #       _tenant_address_form/info)
│   └── partials/              #   HTMX komponenty
│       ├── owner_row.html
│       ├── owner_table_body.html
│       ├── owner_identity_form.html
│       ├── owner_identity_info.html
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
│       ├── share_check_row.html
│       ├── tax_match_row.html
│       ├── tax_send_body.html
│       ├── tax_progress.html
│       ├── tax_recipient_row.html
│       ├── sync_list_body.html
│       ├── share_check_list_body.html
│       ├── dashboard_activity_body.html
│       ├── settings_email_tbody.html
│       ├── ballot_processed.html
│       ├── contact_import_progress.html
│       ├── owner_create_form.html
│       ├── tax_table_body.html
│       ├── _send_progress.html        # Sdílený progress bar pro dávkové odesílání (vnější wrapper + tlačítka)
│       ├── _send_progress_inner.html  # Sdílený progress bar vnitřek (HTMX-polled)
│       ├── smtp_form.html
│       ├── smtp_info.html
│       ├── wizard_stepper.html
│       ├── wizard_stepper_compact.html
│       ├── import_stepper.html
│       ├── import_mapping_fields.html  # Sdílený Jinja2 macro pro mapování sloupců
│       ├── import_mapping_js.html      # Sdílený JS pro mapování sloupců
│       ├── ballot_vote_error.html
│       ├── unit_owners.html
│       └── unit_owner_edit_row.html
└── static/                    # CSS, JS
    ├── css/custom.css         # HTMX animace, search pulse, loading indicators
    ├── css/dark-mode.css      # Dark mode CSS override (~300 pravidel)
    └── js/app.js              # HTMX handlery, dark mode, confirm modal, focus trap, beforeunload, PDF modal
CLAUDE.md                          # Pravidla pro vývoj (backend, routery, modely, workflow)
docs/
└── UI_GUIDE.md                # UI/frontend konvence — jediný zdroj pravdy pro UI vzory
data/
├── svj.db                     # SQLite databáze
├── uploads/                   # Nahrané soubory (Excel, CSV, PDF)
├── generated/                 # Generované dokumenty (PDF lístky)
└── backups/                   # ZIP zálohy (DB + uploads + generated)
spustit.command                # macOS spouštěcí skript (USB nasazení)
pripravit_usb.sh               # Příprava offline wheels pro USB
wheels/                        # Offline Python balíčky (gitignored)
```

## API endpointy

### Dashboard (`/`)

| Metoda | Cesta | Popis |
|--------|-------|-------|
| GET | `/` | Hlavní dashboard (statistiky, poslední aktivita) |
| GET | `/prehled/rozdil-podilu` | Breakdown rozdílu podílů |
| GET | `/exportovat/{fmt}` | Export poslední aktivity (xlsx/csv, respektuje hledání) |

**Poslední aktivita** — tabulka sdružuje `ActivityLog` (CRUD napříč moduly: vlastníci, jednotky, prostory, nájemci, hlasování, rozesílání, platby, kontroly, administrace, nastavení) s `EmailLog` (odeslané emaily). Bubliny filtrují podle modulu, hledání podle popisu/detailu, řádky jsou klikací na detail entity. CRUD operace volají `log_activity(db, action, entity_type, module, entity_id, entity_name, description)` z `app/models/common.py` před `db.commit()`.

### Vlastníci (`/vlastnici`)

| Metoda | Cesta | Popis |
|--------|-------|-------|
| GET | `/vlastnici` | Seznam vlastníků (search, filtr, řazení) |
| GET | `/vlastnici/novy-formular` | HTMX: formulář nového vlastníka |
| POST | `/vlastnici/novy` | Vytvoření vlastníka → redirect na detail |
| GET | `/vlastnici/import` | Sloučená stránka importu: vlastníci (nahoře) + kontakty (dole), každý s upload + historií |
| POST | `/vlastnici/import` | Nahrání Excel souboru vlastníků → mapování sloupců |
| POST | `/vlastnici/import/mapovani` | Potvrzení mapování → zpracování a přesměrování na náhled |
| POST | `/vlastnici/import/nahled` | Náhled importovaných dat před potvrzením |
| POST | `/vlastnici/import/potvrdit` | Potvrzení importu vlastníků → uložení |
| POST | `/vlastnici/import/{log_id}/smazat` | Smazání logu importu vlastníků (log + soubor) |
| GET | `/vlastnici/import-kontaktu` | Redirect → `/vlastnici/import#kontakty` |
| POST | `/vlastnici/import-kontaktu` | Nahrání Excel kontaktů → mapování sloupců |
| POST | `/vlastnici/import-kontaktu/mapovani` | Potvrzení mapování → náhled s auto-detekcí |
| POST | `/vlastnici/import-kontaktu/nahled` | Potvrzení náhledu → zpracování na pozadí |
| GET | `/vlastnici/import-kontaktu/zpracovani` | Stránka progress baru zpracování kontaktů |
| GET | `/vlastnici/import-kontaktu/zpracovani-stav` | HTMX polling: stav zpracování (nebo HX-Redirect po dokončení) |
| GET | `/vlastnici/import-kontaktu/nahled-vysledek` | Náhled párování a změn z cache, klikací stat karty a field filtry |
| POST | `/vlastnici/import-kontaktu/potvrdit` | Potvrzení importu kontaktů + uložení do DB + ImportLog |
| GET | `/vlastnici/import-kontaktu/znovu` | Restart zpracování importu kontaktů |
| POST | `/vlastnici/import-kontaktu/{log_id}/smazat` | Smazání logu importu kontaktů (log + soubor) |
| GET | `/vlastnici/{id}` | Detail vlastníka |
| GET | `/vlastnici/{id}/upravit-formular` | HTMX: formulář kontaktů |
| GET | `/vlastnici/{id}/info` | HTMX: zobrazení kontaktů |
| POST | `/vlastnici/{id}/upravit` | Uložení kontaktů |
| GET | `/vlastnici/{id}/adresa/{prefix}/upravit-formular` | HTMX: formulář adresy (perm/corr) |
| GET | `/vlastnici/{id}/adresa/{prefix}/info` | HTMX: zobrazení adresy |
| POST | `/vlastnici/{id}/adresa/{prefix}/upravit` | Uložení adresy |
| GET | `/vlastnici/{id}/identita-formular` | HTMX: formulář editace identity |
| GET | `/vlastnici/{id}/identita-info` | HTMX: zobrazení identity |
| POST | `/vlastnici/{id}/identita-upravit` | Uložení identity (+ detekce duplicit) |
| POST | `/vlastnici/{id}/sloucit` | Sloučení duplicitních vlastníků |
| POST | `/vlastnici/{id}/jednotky/pridat` | Přidat jednotku vlastníkovi |
| POST | `/vlastnici/{id}/jednotky/{ou_id}/odebrat` | Odebrat jednotku vlastníkovi |
| GET | `/vlastnici/exportovat/{fmt}` | Export vlastníků (xlsx/csv) s aktuálními filtry |

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
| GET | `/jednotky/exportovat/{fmt}` | Export jednotek (xlsx/csv) s aktuálními filtry |
| GET | `/jednotky/{id}/vlastnici-sekce` | HTMX: sekce vlastníků na detailu |
| GET | `/jednotky/{id}/vlastnik/{ou_id}/upravit-formular` | HTMX: editační formulář vlastníka |
| POST | `/jednotky/{id}/vlastnik/{ou_id}/upravit` | Uložení úpravy vlastníka |

### Hlasování (`/hlasovani`)

| Metoda | Cesta | Popis |
|--------|-------|-------|
| GET | `/hlasovani` | Seznam hlasování (filtr dle stavu, bubliny) |
| GET | `/hlasovani/nova` | Formulář nového hlasování |
| POST | `/hlasovani/nova/nahled-metadat` | AJAX: extrakce metadat z .docx šablony |
| POST | `/hlasovani/nova` | Vytvoření hlasování + šablona .docx |
| GET | `/hlasovani/{id}` | Detail hlasování s výsledky (search, sort, HTMX partial) |
| POST | `/hlasovani/{id}/smazat` | Smazání hlasování (cascade + soubory) |
| POST | `/hlasovani/{id}/stav` | Změna stavu hlasování |
| POST | `/hlasovani/{id}/pridat-bod` | Přidání bodu hlasování |
| POST | `/hlasovani/{id}/smazat-bod/{item_id}` | Smazání bodu hlasování |
| POST | `/hlasovani/{id}/bod/{item_id}/upravit` | Editace bodu hlasování |
| POST | `/hlasovani/{id}/bod/{item_id}/posunout` | Posun bodu (reorder) |
| POST | `/hlasovani/{id}/generovat` | Generování PDF lístků |
| GET | `/hlasovani/{id}/listky` | Seznam lístků (filtr stavu, search, sort, HTMX partial) |
| GET | `/hlasovani/{id}/listek/{ballot_id}` | Detail hlasovacího lístku |
| GET | `/hlasovani/{id}/zpracovani` | Stránka zpracování lístků (search, sort, HTMX partial) |
| POST | `/hlasovani/{id}/zpracovat/{ballot_id}` | Zpracování jednoho lístku |
| POST | `/hlasovani/{id}/zpracovat-hromadne` | Hromadné zpracování vybraných lístků |
| GET | `/hlasovani/{id}/neodevzdane` | Neodevzdané lístky (search, sort) |
| GET | `/hlasovani/{id}/import` | Stránka importu výsledků z Excelu |
| POST | `/hlasovani/{id}/import` | Nahrání Excel souboru → mapování sloupců |
| POST | `/hlasovani/{id}/import/mapovani` | Návrat na mapování z náhledu (back navigace) |
| POST | `/hlasovani/{id}/import/nahled` | Náhled importu (přiřazení + statistika) |
| POST | `/hlasovani/{id}/import/potvrdit` | Potvrzení a provedení importu |
| POST | `/hlasovani/{id}/listek/{ballot_id}/opravit` | Oprava zpracovaného lístku (reset hlasů → znovu zpracovat) |
| GET | `/hlasovani/{id}/listek/{ballot_id}/pdf` | Stažení PDF lístku |
| POST | `/hlasovani/{id}/listky/hromadny-reset` | Hromadný reset vybraných zpracovaných lístků |
| GET | `/hlasovani/{id}/neodevzdane/exportovat` | Export neodevzdaných lístků do Excelu |
| GET | `/hlasovani/{id}/exportovat` | Export do Excelu |

### Hromadné rozesílání (`/dane`)

| Metoda | Cesta | Popis |
|--------|-------|-------|
| GET | `/dane` | Seznam rozesílání |
| GET | `/dane/nova` | Formulář nového rozesílání |
| POST | `/dane/nova` | Nahrání PDF + spuštění zpracování na pozadí → redirect na progress |
| GET | `/dane/{id}/zpracovani` | Stránka s progress barem zpracování PDF |
| GET | `/dane/{id}/zpracovani-stav` | HTMX polling: aktuální stav zpracování (nebo HX-Redirect po dokončení) |
| GET | `/dane/{id}` | Detail s párováním dokumentů (stat karty, checkboxy) |
| POST | `/dane/{id}/prejmenovat` | Přejmenování relace (HTMX inline editace) |
| POST | `/dane/{id}/potvrdit/{dist_id}` | Potvrzení automatického párování |
| POST | `/dane/{id}/prirazeni/{doc_id}` | Ruční přiřazení dokumentu (+ spoluvlastníci) |
| POST | `/dane/{id}/potvrdit-vse` | Potvrzení všech automaticky přiřazených |
| POST | `/dane/{id}/potvrdit-vybrane` | Potvrzení vybraných (z checkboxů) |
| POST | `/dane/{id}/odebrat/{dist_id}` | Odebrání vlastníka z dokumentu |
| POST | `/dane/{id}/pridat-externi/{doc_id}` | Přidání externího příjemce (jméno + email) |
| POST | `/dane/{id}/dokoncit` | Uzamknutí relace (read-only mód) |
| POST | `/dane/{id}/znovu-otevrit` | Odemknutí relace pro další úpravy |
| POST | `/dane/{id}/prepocitat-skore` | Přepočet `match_confidence` u AUTO_MATCHED dokumentů aktuálním matcherem (jen navýšení, nikdy nesníží) |
| GET | `/dane/{id}/upload` | Formulář pro nahrání dalších PDF (append/overwrite) |
| POST | `/dane/{id}/upload` | Nahrání dalších PDF + zpracování na pozadí |
| POST | `/dane/{id}/smazat` | Smazání relace (session + dokumenty + soubory) |
| GET | `/dane/{id}/rozeslat` | Rozesílka — preview příjemců (search, sort) |
| GET | `/dane/{id}/dokument/{doc_id}` | Náhled/stažení dokumentu |
| POST | `/dane/{id}/rozeslat/odeslat` | Spuštění odesílání emailů |
| GET | `/dane/{id}/rozeslat/prubeh` | Stránka průběhu odesílání |
| GET | `/dane/{id}/rozeslat/prubeh-stav` | HTMX: polling stavu odesílání |
| POST | `/dane/{id}/rozeslat/pozastavit` | Pozastavení odesílání |
| POST | `/dane/{id}/rozeslat/pokracovat` | Pokračování v odesílání |
| POST | `/dane/{id}/rozeslat/zrusit` | Zrušení odesílání |
| POST | `/dane/{id}/rozeslat/retry` | Opakování neúspěšných |
| POST | `/dane/{id}/rozeslat/test` | Odeslání testovacího emailu |
| POST | `/dane/{id}/rozeslat/nastaveni` | Uložení nastavení odesílání |
| POST | `/dane/{id}/rozeslat/email/{dist_id}` | Úprava emailu příjemce |
| POST | `/dane/{id}/rozeslat/email-vyber/{dist_id}` | Toggle email checkboxu (duální email) |
| GET | `/dane/{id}/exportovat` | Export do Excelu |

### Nedoručené emaily — bounces (`/rozesilani/bounces`)

Připojuje se na IMAP schránku (Gmail SSL imap.gmail.com:993, fallback na SMTP creds), hledá DSN bounce zprávy (Delivery Status Notification, Mail Delivery Failed, Returned Mail…), parsuje dle RFC 3464 (Final-Recipient, Diagnostic-Code, Status-Code), ukládá do `email_bounces`. Hard bounces (5.x.x) automaticky nastaví `Owner.email_invalid=True` → vlastník je vyloučen z budoucích rozesílek (daně, platby) a v UI se zobrazuje červený badge `⚠ neplatný` v kontaktech a `⚠ skrytý` v rozesílce. **Auto-reset:** když uživatel v detailu vlastníka (`/vlastnici/{id}/upravit`) změní primární email na novou neprázdnou hodnotu, `email_invalid` + `email_invalid_reason` se automaticky vyprázdní a vlastník je znovu plnohodnotný příjemce. Manuální spuštění tlačítkem, deduplikace přes `imap_uid`, zprávy se v Gmailu označí jako přečtené. Časový rozsah: od poslední kontroly (–1 den buffer) nebo 30 dní fallback. Vyžaduje alespoň jeden indikátor selhání (status code / diagnostic / reason) — auto-reply zprávy se přeskočí. Vlastní SMTP from-adresa je vyloučena z parsování (prevence false positives).

| Metoda | Cesta | Popis |
|--------|-------|-------|
| GET | `/rozesilani/bounces` | Seznam nedoručených emailů (filtry typ/modul, search, sort) |
| POST | `/rozesilani/bounces/zkontrolovat` | Manuální spuštění IMAP kontroly |
| GET | `/rozesilani/bounces/exportovat/{xlsx\|csv}` | Export do Excelu/CSV (respektuje filtry) |

### Kontroly (`/synchronizace` + `/kontrola-podilu`)

| Metoda | Cesta | Popis |
|--------|-------|-------|
| GET | `/synchronizace` | Sloučená stránka: kontrola vlastníků + kontrola podílů (search, sort) |
| GET | `/synchronizace/nova` | Redirect na seznam |
| POST | `/synchronizace/nova` | Nahrání a porovnání CSV |
| POST | `/synchronizace/{id}/smazat` | Smazání kontroly (záznamy + CSV) |
| GET | `/synchronizace/{id}` | Porovnání s filtry, bublinami a search |
| POST | `/synchronizace/{id}/aktualizovat` | Aplikace vybraných změn z CSV |
| POST | `/synchronizace/{id}/aplikovat-kontakty` | Přenos kontaktů z CSV |
| POST | `/synchronizace/{id}/exportovat` | Export filtrovaného pohledu do Excelu (se zvýrazněním rozdílů) |
| GET | `/synchronizace/{id}/vymena/{rec_id}` | Preview výměny vlastníků pro jednotku |
| POST | `/synchronizace/{id}/vymena/{rec_id}/potvrdit` | Potvrzení výměny vlastníků |
| POST | `/synchronizace/{id}/vymena-hromadna` | Preview hromadné výměny všech rozdílných |
| POST | `/synchronizace/{id}/vymena-hromadna/potvrdit` | Potvrzení hromadné výměny |
| POST | `/synchronizace/{id}/prijmout/{rec_id}` | Přijetí změny |
| POST | `/synchronizace/{id}/odmitnout/{rec_id}` | Odmítnutí změny |
| POST | `/synchronizace/{id}/upravit/{rec_id}` | Ruční úprava jména |
| GET | `/synchronizace/{id}/nahled-kontaktu` | Náhled přenosu kontaktů |

| GET | `/kontrola-podilu` | Redirect → `/synchronizace#kontrola-podilu` |
| POST | `/kontrola-podilu/nova` | Nahrání souboru → redirect na mapování |
| GET | `/kontrola-podilu/mapovani` | Mapování sloupců (auto-detekce + preview) |
| POST | `/kontrola-podilu/potvrdit-mapovani` | Porovnání → uložení → redirect na detail |
| GET | `/kontrola-podilu/{id}` | Výsledky s filtry, bublinami a search |
| POST | `/kontrola-podilu/{id}/smazat` | Smazání kontroly (záznamy + soubor) |
| POST | `/kontrola-podilu/{id}/aktualizovat` | Batch update Unit.podil_scd z vybraných |
| POST | `/kontrola-podilu/{id}/exportovat` | Export do Excelu |

### Administrace (`/sprava`)

| Metoda | Cesta | Popis |
|--------|-------|-------|
| GET | `/sprava` | Stránka administrace SVJ |
| GET | `/sprava/svj-info` | HTMX: sekce info o SVJ |
| GET | `/sprava/ciselniky` | HTMX: sekce číselníků |
| GET | `/sprava/zalohy` | HTMX: sekce záloh |
| GET | `/sprava/smazat` | HTMX: sekce mazání dat |
| GET | `/sprava/export` | HTMX: sekce exportu |
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
| POST | `/sprava/zaloha/{filename}/prejmenovat` | Přejmenování zálohy |
| POST | `/sprava/zaloha/{filename}/obnovit` | Obnovení ze zálohy |
| POST | `/sprava/zaloha/obnovit` | Obnova dat ze zálohy (upload ZIP) |
| POST | `/sprava/zaloha/obnovit-slozku` | Obnova z rozbalené složky zálohy (webkitdirectory) |
| POST | `/sprava/zaloha/obnovit-soubor` | Obnova z nahraného svj.db souboru |
| POST | `/sprava/smazat-data` | Smazání vybraných kategorií dat (potvrzení DELETE) |
| GET | `/sprava/export/{category}/{fmt}` | Export jedné kategorie (xlsx/csv) |
| POST | `/sprava/export/hromadny` | Hromadný export vybraných kategorií (soubor nebo ZIP) |
| GET | `/sprava/hromadne-upravy` | Stránka hromadných úprav |
| GET | `/sprava/hromadne-upravy/hodnoty` | HTMX: tabulka unikátních hodnot pole |
| GET | `/sprava/hromadne-upravy/zaznamy` | HTMX: záznamy pro danou hodnotu |
| POST | `/sprava/hromadne-upravy/opravit` | Hromadná oprava hodnoty |
| POST | `/sprava/ciselnik/pridat` | Přidání položky do číselníku |
| POST | `/sprava/ciselnik/{id}/upravit` | Přejmenování položky (jen nepoužívané) |
| POST | `/sprava/ciselnik/{id}/smazat` | Smazání položky (jen nepoužívané) |
| POST | `/sprava/sablona/pridat` | Přidání emailové šablony |
| POST | `/sprava/sablona/{id}/upravit` | Editace emailové šablony |
| POST | `/sprava/sablona/{id}/smazat` | Smazání emailové šablony |
| GET | `/sprava/duplicity` | Přehled duplicitních vlastníků (skupiny dle name_normalized) |
| POST | `/sprava/duplicity/sloucit` | Sloučení jedné skupiny duplicit do cílového vlastníka |
| POST | `/sprava/duplicity/sloucit-vse` | Sloučení všech skupin najednou (doporučení cíle) |

### Evidence plateb (`/platby`)

| Metoda | Cesta | Popis |
|--------|-------|-------|
| GET | `/platby` | Redirect na výchozí tab (předpisy) |
| GET | `/platby/predpisy` | Seznam předpisů podle roku |
| GET | `/platby/predpisy/import` | Import předpisů — formulář (upload DOCX) |
| POST | `/platby/predpisy/import` | Import předpisů — zpracování DOCX |
| GET | `/platby/predpisy/{year_id}` | Detail předpisů roku (tabulka s filtry) |
| GET | `/platby/predpisy/{year_id}/{prescription_id}` | Detail jednoho předpisu (položky) |
| POST | `/platby/predpisy/{year_id}/smazat` | Smazání roku předpisů |
| GET | `/platby/symboly` | Seznam variabilních symbolů (inline edit, entity type toggle) |
| POST | `/platby/symboly/pridat` | Přidání VS mapování (Jednotka/Prostor) |
| POST | `/platby/symboly/{id}/upravit` | Úprava VS mapování (VS, entita, popis) |
| GET | `/platby/symboly/{id}/upravit-formular` | HTMX partial — inline editační formulář |
| GET | `/platby/symboly/{id}/info` | HTMX partial — read-only zobrazení |
| POST | `/platby/symboly/{id}/smazat` | Smazání VS mapování |
| GET | `/platby/zustatky` | Počáteční zůstatky jednotek |
| POST | `/platby/zustatky/pridat` | Přidání zůstatku (s vlastníkem) |
| POST | `/platby/zustatky/{id}/upravit` | Úprava zůstatku |
| POST | `/platby/zustatky/{id}/smazat` | Smazání zůstatku |
| GET | `/platby/zustatky/vlastnici/{unit_id}` | JSON API — vlastníci jednotky (pro dropdown) |
| GET | `/platby/zustatky/import` | Import zůstatků — upload formulář |
| POST | `/platby/zustatky/import` | Import zůstatků — upload souboru |
| GET | `/platby/zustatky/import/mapovani` | Import — zobrazení mapování sloupců |
| POST | `/platby/zustatky/import/mapovani` | Import — uložení mapování sloupců |
| POST | `/platby/zustatky/import/nahled` | Import — náhled dat |
| POST | `/platby/zustatky/import/potvrdit` | Import — potvrzení importu |
| GET | `/platby/vypisy` | Seznam bankovních výpisů |
| GET | `/platby/vypisy/import` | Import bankovního výpisu — formulář (upload CSV) |
| POST | `/platby/vypisy/import` | Import bankovního výpisu — zpracování CSV |
| GET | `/platby/vypisy/{id}` | Detail výpisu s platbami (filtry: stav, směr, entita, hledání) |
| GET | `/platby/vypisy/{id}/soubor` | Stažení původního CSV bankovního výpisu |
| GET | `/platby/vypisy/exportovat/{fmt}` | Export seznamu výpisů (xlsx/csv, respektuje filtry) |
| GET | `/platby/vypisy/{id}/exportovat/{fmt}` | Export plateb z detailu výpisu (xlsx/csv) |
| POST | `/platby/vypisy/{id}/prirazeni/{payment_id}` | Ruční přiřazení platby (single/multi-unit) |
| POST | `/platby/vypisy/{id}/prirazeni-prostor/{payment_id}` | Ruční přiřazení platby k prostoru |
| POST | `/platby/vypisy/{id}/potvrdit-vse` | Hromadné potvrzení všech SUGGESTED přiřazení |
| POST | `/platby/vypisy/{id}/potvrdit/{payment_id}` | Potvrzení navrženého přiřazení (SUGGESTED → MANUAL) |
| POST | `/platby/vypisy/{id}/odmitnout/{payment_id}` | Odmítnutí navrženého přiřazení (SUGGESTED → UNMATCHED) |
| POST | `/platby/vypisy/{id}/preparovat` | Přepárování plateb (reset AUTO + SUGGESTED, zachová MANUAL) |
| POST | `/platby/vypisy/{id}/zamknout` | Zamčení/odemčení párování výpisu |
| POST | `/platby/vypisy/{id}/smazat` | Smazání výpisu (zamčený výpis nelze smazat) |
| GET | `/platby/prehled` | Matice plateb (jednotky × měsíce, přepínač entity) |
| GET | `/platby/prehled/exportovat/{fmt}` | Export matice plateb (xlsx/csv, podporuje `entita=prostory`, respektuje filtry) |
| GET | `/platby/dluznici` | Seznam dlužníků (přepínač entity) |
| GET | `/platby/dluznici/exportovat/{fmt}` | Export dlužníků (xlsx/csv) |
| GET | `/platby/jednotka/{unit_id}` | Platební detail jedné jednotky |
| GET | `/platby/prostor/{space_id}` | Platební detail jednoho prostoru |
| GET | `/platby/vyuctovani` | Seznam vyúčtování (rok, filtry, search, sort) |
| GET | `/platby/vyuctovani/{id}` | Detail vyúčtování (položky, platby, stav) |
| POST | `/platby/vyuctovani/generovat` | Generování vyúčtování pro rok |
| POST | `/platby/vyuctovani/{id}/stav` | Změna stavu vyúčtování |
| POST | `/platby/vyuctovani/hromadny-stav` | Hromadná změna stavu vyúčtování (vybrané checkboxem) |
| POST | `/platby/vyuctovani/hromadny-stav-filtrovane` | Hromadná změna stavu dle aktuálního filtru |
| GET | `/platby/vyuctovani/exportovat/{fmt}` | Export vyúčtování (xlsx souhrn / xlsx s položkami) |
| POST | `/platby/vyuctovani/smazat-rok` | Smazání všech vyúčtování roku |
| GET | `/platby/vypisy/{id}/nesrovnalosti` | Náhled nesrovnalostí v platbách (špatný VS, částka, sloučené) |
| POST | `/platby/vypisy/{id}/nesrovnalosti/test` | Odeslání testovacího emailu s upozorněním |
| POST | `/platby/vypisy/{id}/nesrovnalosti/nastaveni` | Uložení per-výpis nastavení odesílání (dědí z globálu, lze přepsat) |
| POST | `/platby/vypisy/{id}/nesrovnalosti/odeslat` | Zahájení dávkového odesílání vybraných upozornění |
| GET | `/platby/vypisy/{id}/nesrovnalosti/prubeh` | Stránka s progress barem odesílání |
| GET | `/platby/vypisy/{id}/nesrovnalosti/prubeh-stav` | HTMX polling endpoint pro progress |
| POST | `/platby/vypisy/{id}/nesrovnalosti/pozastavit` | Pozastavení odesílání |
| POST | `/platby/vypisy/{id}/nesrovnalosti/pokracovat` | Pokračování v odesílání |
| POST | `/platby/vypisy/{id}/nesrovnalosti/zrusit` | Zrušení odesílání |

### Prostory (`/prostory`)

| Metoda | Cesta | Popis |
|--------|-------|-------|
| GET | `/prostory` | Seznam prostorů (řazení, hledání, filtry stav/sekce) |
| GET | `/prostory/{id}` | Detail prostoru (info + aktuální nájemce + historie) |
| GET | `/prostory/novy-formular` | HTMX: formulář pro nový prostor |
| POST | `/prostory/novy` | Vytvoření prostoru |
| GET | `/prostory/{id}/upravit-formular` | HTMX: editační formulář |
| GET | `/prostory/{id}/info` | HTMX: info karta prostoru |
| POST | `/prostory/{id}/upravit` | Úprava prostoru |
| POST | `/prostory/{id}/smazat` | Smazání prostoru |
| POST | `/prostory/{id}/pridat-najemce` | Přiřazení nájemce (+ VS mapping + Prescription) |
| POST | `/prostory/{id}/ukoncit-najem` | Ukončení nájmu |
| GET | `/prostory/{id}/najemce-formular` | HTMX: inline editační formulář aktuálního nájemce (VS, nájemné, smlouva) |
| GET | `/prostory/{id}/najemce-info` | HTMX: info karta aktuálního nájemce |
| POST | `/prostory/{id}/upravit-najemce` | Uložení inline edit nájemního vztahu |
| GET | `/prostory/exportovat/{fmt}` | Export prostorů (xlsx/csv) |
| GET | `/prostory/import` | Import prostorů — upload stránka |
| POST | `/prostory/import` | Import — upload souboru |
| POST | `/prostory/import/mapovani` | Import — mapování sloupců |
| POST | `/prostory/import/nahled` | Import — náhled dat |
| POST | `/prostory/import/potvrdit` | Import — potvrzení importu |
| POST | `/prostory/import/{log_id}/smazat` | Smazání záznamu importu |

### Nájemci (`/najemci`)

| Metoda | Cesta | Popis |
|--------|-------|-------|
| GET | `/najemci` | Seznam nájemců (řazení, hledání) |
| GET | `/najemci/{id}` | Detail nájemce (per-section inline edit, propojení s Owner) |
| GET | `/najemci/novy-formular` | HTMX: formulář pro nového nájemce |
| POST | `/najemci/novy` | Vytvoření nájemce |
| GET | `/najemci/{id}/identita-formular` | HTMX: inline edit identifikace |
| GET | `/najemci/{id}/identita-info` | HTMX: info karta identifikace |
| POST | `/najemci/{id}/identita-upravit` | Uložení identifikace |
| GET | `/najemci/{id}/kontakt-formular` | HTMX: inline edit kontaktu |
| GET | `/najemci/{id}/kontakt-info` | HTMX: info karta kontaktu |
| POST | `/najemci/{id}/kontakt-upravit` | Uložení kontaktu |
| GET | `/najemci/{id}/adresa/{prefix}/formular` | HTMX: inline edit adresy (perm/corr) |
| GET | `/najemci/{id}/adresa/{prefix}/info` | HTMX: info karta adresy |
| POST | `/najemci/{id}/adresa/{prefix}/upravit` | Uložení adresy |
| POST | `/najemci/{id}/smazat` | Smazání nájemce |
| POST | `/najemci/{id}/propojit` | Propojení s existujícím vlastníkem |
| POST | `/najemci/{id}/odpojit` | Odpojení od vlastníka |
| GET | `/najemci/exportovat/{fmt}` | Export nájemců (xlsx/csv) |

### Nastavení (`/nastaveni`)

| Metoda | Cesta | Popis |
|--------|-------|-------|
| GET | `/nastaveni` | Seznam šablon, SMTP a globální nastavení odesílání |
| POST | `/nastaveni/odesilani` | Uložení výchozích nastavení odesílání (dávka, interval, potvrzení, test email) |
| GET | `/nastaveni/smtp/formular` | HTMX: editační formulář SMTP |
| GET | `/nastaveni/smtp/info` | HTMX: zobrazení SMTP nastavení |
| POST | `/nastaveni/smtp` | Uložení SMTP nastavení |
| POST | `/nastaveni/smtp/test` | Test SMTP připojení (smtplib) |
| GET | `/nastaveni/priloha/{log_id}/{filename}` | Stažení přílohy emailové šablony |

## Konfigurace (.env)

```env
DEBUG=true
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=svj@example.com
SMTP_FROM_NAME=SVJ
SMTP_USE_TLS=true
LIBREOFFICE_PATH=/Applications/LibreOffice.app/Contents/MacOS/soffice
```

## Datový model

- **Owner** — vlastník (jméno, tituly, RČ/IČ, adresy, kontakty, phone_secondary, email_secondary, company_id, is_active); `display_name` property: formát „příjmení jméno" s titulem
- **Unit** — jednotka (číslo KN jako INTEGER, budova, sekce, plocha, podíl SČD, orientation_number)
- **OwnerUnit** — vazba vlastník-jednotka (typ vlastnictví, podíl, hlasovací váha, valid_from, valid_to); valid_to=NULL = aktuálně platný, valid_to=datum = historický záznam
- **Proxy** — plná moc pro hlasování
- **Space** — prostor SVJ (číslo, označení, sekce, podlaží, výměra, stav: rented/vacant/blocked)
- **Tenant** — nájemce (identity vlastní nebo z Owner přes owner_id FK; resolved properties pro jméno/kontakt/RČ/IČ/typ; `active_space_rels` list aktivních SpaceTenants pro multi-space zobrazení)
- **SpaceTenant** — nájemní vztah (smlouva, nájemné, VS, is_active, contract_path)
- **Voting** (partial_owner_mode, import_column_mapping) → VotingItem → Ballot (scan_path, voted_by_proxy, shared_owners_text) → BallotVote
- **TaxSession** → TaxDocument → TaxDistribution
- **SyncSession** → SyncRecord (cascade delete)
- **ShareCheckSession** → ShareCheckRecord (cascade delete); ShareCheckColumnMapping (zapamatované mapování sloupců)
- **SvjInfo** → SvjAddress — informace o SVJ a adresy; `voting_import_mapping`, `owner_import_mapping`, `contact_import_mapping` pro globální uložení mapování sloupců importů (JSON); `send_batch_size`, `send_batch_interval`, `send_confirm_each_batch`, `send_test_email_address` pro konfiguraci dávkového odesílání
- **BoardMember** — členové výboru a kontrolního orgánu (group: board/control)
- **CodeListItem** — položky číselníků (category: space_type/section/room_count/ownership_type, value, order); unique index na (category, value)
- **EmailTemplate** — šablony emailů pro hromadné rozesílání (name, subject_template, body_template, order); placeholder `{rok}` a další kontextové proměnné přes `render_email_template()` (Jinja2)
- **ActivityLog** — log aktivit (modul, akce, entita, timestamp); **ActivityAction** — enum typů aktivit (CREATED, UPDATED, DELETED, STATUS_CHANGED, IMPORTED, EXPORTED, RESTORED)
- **PrescriptionYear** → **Prescription** (monthly_total, variable_symbol, space_type) → **PrescriptionItem** (name, amount, category, order); předpisy plateb per rok/jednotka
- **VariableSymbolMapping** — mapování VS → jednotka/prostor (unit_id nullable, space_id nullable; source: manual/auto/legacy)
- **BankStatement** (locked_at) — importovaný bankovní výpis (Fio CSV); → **Payment** (amount, date, direction, match_status, unit_id, space_id, notified_at) → **PaymentAllocation** (payment_id, unit_id nullable, space_id, owner_id, prescription_id, amount — dual-write pro multi-unit/space platby); PaymentMatchStatus (UNMATCHED/AUTO_MATCHED/SUGGESTED/MANUAL), PaymentDirection (INCOME/EXPENSE); **BankStatementColumnMapping** (zapamatované mapování sloupců CSV)
- **UnitBalance** — počáteční zůstatek jednotky per rok (opening_amount, source: manual/import/carryover, owner_id FK → Owner, owner_name text z importu)
- **Settlement** → **SettlementItem** — roční vyúčtování per jednotka; SettlementStatus (GENERATED/SENT/PAID/OVERDUE)
- **EmailLog** (+ `name_normalized` pro diacritics-insensitive vyhledávání), **ImportLog** — systémové logy

## Bezpečnost a kvalita kódu

Projekt prošel bezpečnostním auditem (52 nálezů). Opraveny všechny CRITICAL, HIGH a většina MEDIUM/LOW:

**CRITICAL (8/8 opraveno):**
- Path traversal ochrana na všech download/file endpointech (validace cesty v povolených adresářích)
- CSRF ochrana pro destruktivní POST operace
- SQL injection prevence (parametrizované dotazy)
- Rate limiting na SMTP endpointech

**HIGH (12/12 opraveno):**
- Validace uploadovaných souborů (typ, velikost, přípona) — sdílená utilita `validate_upload()`
- Pinned verze závislostí s horními hranicemi (`>=X,<Y`)
- N+1 query optimalizace (joinedload ve voting.py, dashboard.py)
- HTMX error handler pro server chyby
- Accessibility: aria-label na search inputech, label binding na checkboxech

**MEDIUM/LOW (opraveno 19/32):**
- `aria-hidden="true"` na 100 dekorativních SVG ikonách (WCAG AA)
- Thread safety: `threading.Lock` pro sdílené progress dict v tax.py
- SMTP timeout (10s) proti indefinite hang
- Error handling: try/except na load_workbook, int/float parsing, logger místo traceback.print_exc
- Dark mode focus ring CSS pro lepší viditelnost
- Flash message auto-dismiss přes `data-auto-dismiss` atribut
- Odstranění nepoužitých importů
- Bounds checking na numerických inputech (HTML min/max + backend validace)
- Sjednocení button stylingu (`rounded-lg`, `transition-colors`, `bg-green-600`)
- Sjednocení input padding outliers (tax send, recipient row)
- HTMX loading indikátor — globální CSS disabled styl na submit tlačítkách během requestu
- Heading hierarchy — sidebar `<h1>` → `<div>`, jediný `<h1>` v obsahu
- `role="alert"` na error zprávách a flash messages (screen reader podpora)

**Druhý audit (2026-03-03) — 42 nálezů, opraveno 10:**
- Zip Slip ochrana při rozbalování záloh (`backup_service.py`)
- Path traversal: `is_safe_path()` na 6 endpointech (voting, share_check, owners)
- Custom 404/500 chybové stránky v designu aplikace (`error.html`)
- Security headers middleware (X-Frame-Options: DENY, X-Content-Type-Options, Referrer-Policy)
- Dashboard výkon: N+1 tax stats → GROUP BY, voting COUNT + selective eager load
- Test email: `asyncio.to_thread()` pro neblokující SMTP
- Responsive dashboard grid (`grid-cols-1 sm:grid-cols-2 lg:grid-cols-4`)
- WCAG AA kontrast: `text-gray-400` → `text-gray-500` napříč ~60 šablonami

Zbývající nálezy z druhého auditu: autentizace (plánováno), CSRF ochrana, testy, mobilní sidebar.

**Třetí audit (2026-03-05) — 30 nálezů, opraveno 11:**
- Odstraněn duplikát `_strip_diacritics` (import z utils)
- Extrahován `has_processed_ballots` jako `@property` na modelu Voting
- Sjednocen timestamp na `datetime.utcnow()` (4 výskyty)
- Try/except kolem PDF extrakce + logování v background threadech
- Přidán `hx-swap="innerHTML"` na HTMX search inputy
- Validace import mappingu (`validate_mapping()`)
- Enum porovnání místo string `.value ==` (13 výskytů)
- Binární soubory (.png, .xlsx) odstraněny z gitu

**Čtvrtý audit (2026-03-08) — 33 nálezů, opraveno 20:**
- Path traversal fix v `contact_import_rerun` — přidána `is_safe_path()` validace
- Sjednocen `strip_diacritics` import z `app.utils` (odstraněny kopie v `excel_import.py`, `contact_import.py`)
- Extrahován `excel_auto_width()` helper do `utils.py` (nahrazeno 8 duplikátů v 8 souborech)
- Vyčištěny unused imports (7 souborů: sync, voting, administration, dashboard, main, excel_export, share_check_comparator)
- Přesunut logger v `tax.py` na začátek za importy
- `date.fromisoformat()` ošetřen try/except v hlasování a synchronizaci
- SQL filtrování emailového logu (settings_page) místo Python-only filtrování
- Sjednocen `<thead>` styl (border-b-2, sticky) ve 4 šablonách
- Sjednocen flash message vzor (role=alert, warning podpora) ve 3 šablonách
- Přidán `logger.debug` ke všem tichým `except: pass` u file cleanup (11 míst, 5 routerů)
- Přesunuty agent/report MD soubory z rootu do `docs/agents/` a `docs/reports/`
- `is_valid_email()` validace při ukládání emailu do DB (owners, administration)
- Globální exception handler pro `IntegrityError`/`OperationalError` — přátelská chybová stránka místo 500
- SQL filtrování a řazení lístků (ballots) místo Python-side, SQL agregace ve `_ballot_stats`
- Rozdělen `tax.py` (2515 řádků) na package `tax/` — 6 modulů (session, processing, matching, sending, helpers)
- Rozdělen `voting.py` (1613 řádků) na package `voting/` — 5 modulů (session, ballots, import, helpers)
- Zbývá: testy, autentizace + CSRF

**Pátý audit (2026-03-09) — LOW items cleanup:**
- Nahrazena závislost `unidecode` vlastní `strip_diacritics()` z `app/utils.py`
- `_has_processed_ballots()` → `@property` na modelu Voting
- `build_wizard_steps()` extrahován do `utils.py` (sdílený voting + tax)
- `build_name_with_titles()` přesunut z `excel_import.py` do `utils.py`
- Inline importy přesunuty na top-level v 8 routerech

**Šestý audit (2026-03-10) — 8 nálezů, opraveno 8:**
- XSS escape uživatelského vstupu ve varováních jednotek (`markupsafe.escape()`)
- Generická chybová zpráva místo exception detailu v DOCX preview (info leakage)
- Generická chybová zpráva místo SMTP exception (info leakage)
- Smazány redundantní inline importy (`Path` 3×, `smtplib`, `markupsafe`, `sa_func`, `engine`, `sqlite3`)
- Extrahován `_parse_numeric_fields()` a `_build_warn_html()` v units.py (deduplikace)
- `force_create` jako Form parametr místo `request.form()` v owners/crud.py
- Smazán zastaralý `docs/CLAUDE-zaloha.md`

**Sedmý audit — Code Guardian (2026-03-18) — 9 nálezů, opraveno 9:**
- Rozdělen `owners.py` (1800+ řádků) na package `owners/` — 4 moduly (crud, import_owners, import_contacts, _helpers)
- Dynamické mapování sloupců pro import vlastníků a kontaktů — sdílená service `import_mapping.py` s auto-detekcí, validací a uloženým mapováním
- Sdílené Jinja2 partials pro mapování: `import_mapping_fields.html` (macro), `import_mapping_js.html` (JS), `import_stepper.html` (4-krokový sub-stepper)
- `EmailLog.name_normalized` sloupec pro diacritics-insensitive vyhledávání v email logu
- Voting detail: SQL agregace (GROUP BY) místo Python iterace pro statistiky hlasování
- PDF parser fix: parsování jmen ze spoluvlastnického podílu v daňových dokumentech
- Formulář rozesílání zjednodušen: rok odstraněn, title+subject sloučeny
- Číselníky redesign: kolapsovatelné karty s ikonami (5-sloupcový grid)
- Nové migrace v `main.py`: `_migrate_svj_import_mappings()`, `_migrate_email_log_name_normalized()`

**Audit zálohovacího systému (2026-03-05) — 14 nálezů, opraveno 12:**
- ZIP validace: CRC integrity check (`testzip()`) před restore
- Rollback: automatická obnova ze safety backup při selhání restore
- Disk space check: `shutil.disk_usage()` s 2× heuristikou
- File lock: `.restore_lock` proti souběžným restore operacím (stale timeout 10 min)
- Auto-cleanup: rotace záloh (max 10), nejstarší se automaticky mažou
- .env backup: zahrnut v ZIP + obnoven při restore
- manifest.json: metadata (timestamp, verze) v každé záloze
- Chunked copy: `shutil.copyfileobj()` místo `read()`/`write()` celého souboru
- WAL mode: `PRAGMA journal_mode=WAL` pro lepší concurrent read/write
- Exception handling: try/except ve všech restore endpointech s error flash messages
- Post-restore migrace vrací warnings list pro UI feedback
- Odstraněn nebezpečný endpoint `obnovit-adresar` (přijímal libovolnou cestu z formuláře)

**Osmý audit — platební modul (2026-03-22) — 28 nálezů, opraveno 20:**
- Refaktoring `match_payments()` na 3 fázové funkce (VS match, name match, VS-prefix decode)
- Sdílená `templates` instance z `app.utils` (nahrazeno 9 duplicitních `Jinja2Templates` setupů)
- `_create_error_log()` helper v email_service (nahrazeny 4 copy-paste bloky)
- `except Exception: pass` → `logger.debug()` s exc_info ve statements.py
- `overflow-x-auto` wrapper na tabulkách ve 27 šablonách (mobilní responsivita)
- `datetime.utcnow()` → helper `utcnow()` v `app/utils.py` (44 výskytů, Python 3.12+ kompatibilita)
- Lokální kopie Tailwind CSS + HTMX s CDN fallback (offline podpora)
- `aria-label` na 22 inputech/checkboxech ve 13 šablonách (WCAG AA)
- Rozdělen `administration.py` (1426 ř.) na package — 6 modulů (info, board, code_lists, backups, bulk)
- Rozdělen `sync.py` (1171 ř.) na package — 4 moduly (session, contacts, exchange)
- Refaktoring 4 nejdelších funkcí na menší helpery (20 nových helper funkcí)
- 298 automatizovaných testů (voting, backup, CSV comparator, payment matching, settlement, endpoints)
- Pre-push git hook + GitHub Actions CI workflow
- UX Optimizer: 18/18 nálezů opraveno (compute_nav_stats skip, export matice, VS inline edit, hromadné potvrzení SUGGESTED, hromadná změna stavu filtrovaných, search výpisů, hardcoded rok, confirm dialogy, dashboard dlužníci, empty state CTA, sort měsíců v matici, sidebar badge dlužníků)
- Zobrazení všech spoluvlastníků v platebním modulu (dlužníci, matice, vyúčtování, exporty)
- Zbývá: autentizace + CSRF

**Devátý audit — Code Guardian + Doc Sync + UX (2026-04-11) — 24 nálezů, opraveno 24:**

*Code Guardian (13):*
- XSS: odstraněn `|safe` u `body_preview` v email logu + HTML se stripuje před uložením (`_html_to_plain()` v email_service)
- Dashboard: LIMIT 200 na EmailLog/ActivityLog, N+1 voting/tax aggregáty (1 dotaz místo ~16), Payment count jeden agregát místo 4 dotazů
- `_norm_module` extrahován na module-level v dashboard.py (deduplikace view + export)
- Matice plateb export: podpora `entita=prostory`, sdílený `_matrix_sort_fns()` helper mezi view a exportem
- `strip_diacritics()` ve všech export suffixech (vlastníci, jednotky, prostory, nájemci, výpisy) — HTTP Content-Disposition je latin-1
- Eager loading v detail výpisu: 1 JOIN místo 3 dotazů (Unit + OwnerUnit + Owner pro dropdown)
- Nový endpoint `GET /platby/vypisy/{id}/soubor` + klikací filename v seznamu i detailu (stažení zdrojového CSV)
- `db.rollback()` fallback v discrepancies po neúspěšném `notified_at` update
- Silent `except` v dashboard debtor count → `logger.warning` s exc info

*Doc Sync (5):*
- README § Evidence plateb: doplněny endpointy `/vypisy/{id}/soubor`, `/vypisy/exportovat/{fmt}`, `/vypisy/{id}/exportovat/{fmt}`
- README: opravena metoda POST→GET u `/platby/prehled/exportovat/{fmt}` a `/platby/dluznici/exportovat/{fmt}` + zmínka `entita=prostory`
- README § Prostory: doplněny 3 HTMX endpointy inline edit nájemce (`najemce-formular`, `najemce-info`, `upravit-najemce`) + feature popis inline editace
- README: doplněn `/exportovat/{fmt}` pro dashboard export poslední aktivity
- CLAUDE.md § Export dat: příklad `vypis_{id}_filter_YYYYMMDD`

*UX (6):*
- 4 tenant partials (`_tenant_contact_info`, `_tenant_address_info`, `_tenant_identity_info`, `_tenant_info`): odkaz na vlastníka propaguje `?back=/najemci/{id}`
- `administration/duplicates.html`: `?back=/sprava/duplicity` na odkazech vlastníků
- `voting/_voting_header.html`: import/zpracování propagují `?back`, `import_result.html` stejné sjednocení
- `owner_create_form.html` + `tenants/_create_form.html`: duplicita odkazy na entitu s `?back=/vlastnici/novy` / `/najemci/novy`
- `owners/crud.py` `back_label`: nové větve pro `/najemci/` a `/sprava/duplicity`
- `administration/backups.html`: client-side search pole nad tabulkou záloh (zobrazí se při >5 záloh)

Zbývající z 9. auditu (vyžaduje rozhodnutí nebo odloženo): Business Logic — 4 kritické nálezy (OwnerUnit.votes Int vs Float podíl, SJM první import, hardcoded VS_PREFIX, přeplatky v nesrovnalostech), `administration/duplicates.html` layout (karty ponechány), autentizace + CSRF.

**Doplněk — /hlasovani sjednocení bublin+sort (1 oprava):**
`voting/index.html` byl v 9. auditu přehlédnutý — měl bubliny a Řadit: jako dva samostatné bloky s nekanonickým `rounded-full` stylem. Sjednoceno na kanonický vzor: shared `bg-white` container s `border-t` separátorem mezi bublinami a sort pills (stejně jako /dane, /vlastnici, /jednotky a 6 dalších stránek).

**Doplněk — /platby/vypisy, vypis_detail, nesrovnalosti (3 opravy):**
Tři stránky v modulu Platby měly starý `rounded-full bg-blue-600 text-white` styl bublin s shadow a bubliny mimo shared container. Sjednoceno na kanonický plochý vzor (`rounded border bg-{color}-100 border-{color}-300 ring-2`) v shared containeru. Tím je 9. audit kompletně uzavřen.

**Desátý audit — Code Guardian (2026-04-11) — 13 nálezů, opraveno 8:**
- **HIGH #1** — `_prepare_owner_lookup` měl N² lookup při párování vlastník→jednotka (`owner_dicts` prohledáván pro každou `OwnerUnit`). Nahrazeno dict mapou `owner_by_id` → O(n+m). Pro 100 vlastníků × 50 jednotek: 5000 → 150 operací
- **HIGH #2** — `vypisy.html` používal křehký `_back|replace('&back=', 'back=')` pattern generující `??` nebo `&&` v URL. Přepsáno na Jinja2 `qs()` makro (poskládá querystring z neprázdných dvojic) — stejný vzor použit i ve voting/index.html
- **MEDIUM #3** — `voting/index.html` používal `_sort_suffix[1:]` string slicing pro odstranění `&` prefixu. Nahrazeno `qs()` makrem (čistější, testovatelné)
- **MEDIUM #4** — `tax_recompute_scores` volal `match_name()` ~1800× pro typické sezení (30 dokumentů × 3 kandidáti × 20 distribucí). Přidán memo cache `(candidate, owner_id) → confidence` → ~10× zrychlení
- **MEDIUM #6** — `backup_service._count_db_rows` f-string SQL `SELECT COUNT(*) FROM {table}` s hardcoded seznamem. Přidán `assert table.replace("_","").isalnum()` jako druhý whitelist layer
- **MEDIUM #7** — Odstraněno nepoužívané `except Exception as e:` v `tax/processing.py` a `voting/session.py` (jen `logger.exception` bez reference na `e`)
- **LOW #11** — Rozšířený docstring `_stem_czech_surname` vysvětluje `len(word) - len(s) >= 3` guard proti over-stemmingu krátkých jmen (Eva → E)
- **LOW #12** — Přejmenováno `_group_key_counts` → `grouped_emails` v `dashboard.py` (underscore prefix nepatří k lokální proměnné)
- **LOW #13** — Nový `tests/test_owner_matcher.py` s 10 testy pro TITLE_PATTERNS (Ph.D., M.B.A., LL.M., arch., SJM), Czech stemming, stem overlap rejection a ochranu krátkých jmen. Celkem 320 testů (+10)

Odloženo (vyžaduje rozhodnutí nebo UX diskuzi): #9 `owner_update` rename (breaking change bez přínosu).

**Desátý audit follow-up (2026-04-11) — dokončení 3 nálezů (#5, #8, #10):**
- **#5** — `|safe` SVG sort ikony v `voting/detail.html`, `process.html`, `ballots.html` nahrazeny sdíleným partialem `partials/_sort_icon.html` (volání `{% with direction=order %}{% include ... %}{% endwith %}`). Odstraněn XSS-adjacentní raw HTML, jediný zdroj pravdy pro sort ikonu
- **#8** — 16 starých reportů (ORCHESTRATOR-REPORT-*, UX-REPORT-*, PREHLED-KOMPLET, TEST-REPORT, BACKUP-REPORT) přesunuto do `docs/reports/archive/`. V `docs/reports/` zůstává pouze aktuální `AUDIT-REPORT.md`
- **#10** — Emoji badges (🔴/🟡/⚪) v `bounces/_table.html` nahrazeny SVG kolečky (`w-1.5 h-1.5 rounded-full bg-*`) — konzistentní s ostatními badge v aplikaci, nezávislé na font rendering

**Jedenáctý audit — follow-up z Business Logic + UX (2026-04-11) — 3 opravy:**
- **BL-1 CRITICAL** — `excel_import.py` vytvářel pro spoluvlastníky (SJM) `share=1.0` a `votes=unit.podil_scd` každému — při re-importu z Excelu by se součet hlasů za jednotku s N spoluvlastníky nafoukl N× (→ rozbité kvórum + kontrola podílů). Přidán druhý průchod po vytvoření všech OwnerUnit: `share=1/N`, `votes` rozdělené rovnoměrně s rounding compensation (idx < remainder → +1). Stejný vzor jako v `sync/_helpers.py`
- **UX-3** — Globální JS handler pro `data-loading="Zpracovávám..."` atribut na formulářích (plain POST, ne HTMX). Při submitu disabluje tlačítko a zobrazí SVG spinner — prevence double-submit u pomalých Excel importů. Přidáno na 4 import formuláře: vlastníci, prostory, zůstatky, hlasy (předpisy už mají custom onsubmit spinner)
- **BL-4** — `VS_PREFIX = "1098"` natvrdo v `payment_matching.py` přesunut do `SvjInfo.vs_prefix` (nullable, default "1098") s UI polem v `/sprava/svj-info`. Projekt už není vázaný na konkrétní SVJ, lze ho snadno nasadit pro jiné SVJ bez úpravy kódu. Migrace `_migrate_svj_send_settings` rozšířena o `vs_prefix` sloupec

## UX vylepšení

Projekt prošel UX analýzou klíčových modulů (6 expertních perspektiv: UX Designer, Information Architect, Accessibility Specialist, Error Prevention, Interaction Designer, Data Integrity Guardian).

**Hromadné rozesílání — 24 oprav:**
- Potvrzovací dialogy u destruktivních akcí (smazání, přepsání, odeslání)
- Disable tlačítek po kliknutí (prevence double-submit)
- Flash zprávy pro výsledky akcí (smazání, chyby uploadu)
- Konzistentní back URL navigace a labeling
- Přesný počet příjemců na tlačítku odeslání
- Inline validace emailu (formát + vizuální feedback)
- Scroll-to-top při HTMX swapech na send stránce

**Hlasování per rollam — 14 oprav:**
- Validace hlasů před zpracováním lístku (alespoň jeden hlas povinný)
- Flash zprávy při selhání uploadu/extrakce DOCX šablony
- Potvrzovací dialogy s kontextovými údaji (generování lístků, uzavření hlasování s kvórem)
- Diacritics-insensitive vyhledávání (lístky, zpracování, výsledky)
- Kontrola existence souboru před importem + úklid dočasných souborů po importu
- Statistiky na výsledkové stránce importu (zpracováno, přeskočeno, nepřiřazeno)
- Zobrazení chybějících hlasů pro dosažení kvóra
- Export do Excelu dostupný přímo z header tlačítek uzavřeného hlasování

**Komplexní UX audit celé aplikace (2026-03-08) — 33 nálezů, opraveno 33:**

*Drobné (13):* export jen u aktivních/uzavřených hlasování, kvórum v confirm dialogu, PDF lístek jako klikací link, empty states, tooltipy na truncated texty, modré zpětné šipky, kompaktní dashboard, validace test emailu, konzistentní badge a formátování čísel.

*Důležité (10):* import wizard stepper (4 kroky), nápověda pod mapovacími selecty, badge „Hlasováno: X/Y bodů" na detailu lístku, hromadný reset lístků s checkboxy, badge „Odesílá se"/„Pozastaveno" v rozesílce, kompaktní filtr kontaktů (4 segmenty), flash varování při neplatném emailu, červené zvýraznění při chybě validace, flash po vytvoření vlastníka.

*Kritické (7):*
- K1: Zobrazení počtu neúplně hlasovaných lístků v kvórum sekci (varování o neúplných hlasech)
- K2: Import preview ukazuje existující hlasy při přepisu („staré → nové") + bublina „Přepíše: N"
- K3: SJM varování při duplicitním přiřazení lístku z více řádků Excelu
- K4: SQL subquery sort místo Python-side sort (podíl, jednotky, sekce u vlastníků; vlastníci u jednotek)
- K5: Fix N+1 query v tax sending (joinedload distributions)
- K6: Flash chybové zprávy v kontrolách (share_check, sync) — 5 typů chybových zpráv
- K7: Zachování pozice v tabulce po potvrzení přiřazení (referer-based redirect)

**Celoplošný UX audit (2026-03-09) — 27 nálezů, opraveno 27:**

*Wave 1 (8):* responsive grid na detailu vlastníka, exchange varování (nevratná operace), čitelné kontaktní filtry (text místo ikon), popisky admin karet, smazání hlasování — DELETE modal pokud má lístky, HTMX loading pulzace na search inputech.

*Wave 2 (3):* dashboard kompaktnější layout, varování u výměny vlastníků s `data-confirm`, responsivní 2×2 grid na mobilních zařízeních.

*Wave 3 (4):* detekce duplicitních vlastníků při vytváření (jméno/RČ/email s možností vynucení), SMTP test připojení (smtplib), onboarding blok na dashboardu pro prázdnou DB, varování při opuštění neuloženého formuláře (`beforeunload`).

*Wave 4 (4):* email validace vrací formulář s chybou místo tichého zahození, výraznější varování u neplatných číselných vstupů (plocha, podíl), varování o nepotvrzených auto-match přiřazeních v rozesílce, počet dotčených záznamů v confirm dialogu hromadných úprav.

*Wave 5 (6):* validace rozsahu čísla budovy (1–99999), vizuální oddělení sekcí na stránce kontrol, ARIA atributy pro modály (`role="dialog"`, `aria-modal`, `aria-labelledby`), focus trap v modalech (Tab/Shift+Tab), focus restore po zavření modálu, `aria-label` na icon-only tlačítkách (14 šablon).

*Wave 6 (2):* SQL agregace na seznamu hlasování — nahrazeno joinedload + Python iterace dvěma GROUP BY dotazy, eliminuje načítání tisíců BallotVote objektů do paměti. XSS escape uživatelského vstupu ve varováních jednotek (`markupsafe.escape()`).

**Audit zálohovacího systému + business logiky (2026-03-08) — 8 nálezů, opraveno 8:**

*HIGH (3):*
- H1: ABSTAIN v importu hlasování — `_match_vote()` rozšířen o zdržel se/abstain/Z/2
- H2: Trojitý `db.commit()` při importu → jeden atomický commit v routeru
- H3: `recalculate_unit_votes()` po změně podílů v kontrole podílů (oprava kvóra)

*MEDIUM (5):*
- M1: Cascade delete na Owner.ballots, tax_distributions, proxies (prevence osiřelých záznamů)
- M2: WAL checkpoint (`PRAGMA wal_checkpoint(TRUNCATE)`) před SQLite zálohou
- M3: Kontrola `voting.status == ACTIVE` před zpracováním/importem lístků
- M4: Path traversal ochrana + `restore_from_directory()` s rollback ve folder restore
- M5: `owner_exchange` nastaví `is_active=False` vlastníkům bez aktivních jednotek

**UX sjednocení 8 stránek + bounce-check modul (2026-04-11):**

*Nový modul — nedoručené emaily (`/rozesilani/bounces`):* IMAP kontrola bounce zpráv (RFC 3464), automatické označení `Owner.email_invalid=True` u hard bounces (5.x.x), vyloučení neplatných adres z budoucích rozesílek. Deduplikace přes `imap_uid`, filtry typ/modul, export Excel/CSV. Nová šablona `bounces/index.html` + `bounces/_table.html`, router `app/routers/bounces.py`, service `app/services/bounce_service.py`. UI badge `⚠ neplatný` v kontaktech vlastníka, `⚠ skrytý` v dist list v rozesílce.

*UX sjednocení s kanonickým vzorem `/vlastnici` (8 stránek):* stat-card bubliny + HTMX search ve sdíleném `bg-white rounded-lg shadow` kontejneru s `border-t` separátorem, `<a href>` sort odkazy místo `onclick`, hidden inputy pro HTMX state propagation. Stránky: `/platby/dluznici`, `/platby/prehled`, `/platby/vyuctovani`, `/platby/symboly`, `/platby/zustatky`, `/dane`, `/rozesilani/bounces`, nedoručené hlasovací lístky (už přes partial). Bounces stránka dostala stejný layout hned při vzniku.

*Revert vypisy_list designu:* experimentální přepis řádků v `/platby/vypisy` odmítnut, návrat k původní verzi (commit `47f1983`).

*Fuzzy matcher — rozšířené tituly + rematch endpoint:* `owner_matcher.py` nově rozpoznává `arch.` (z `Ing.arch.`) a dotted `M.B.A.` formu — tyto konstrukce dříve zůstávaly jako tokeny a snižovaly confidence na 0.8. Přidán endpoint `POST /dane/{id}/prepocitat-skore` s tlačítkem „Přepočítat skóre" v hlavičce kroku 2 — bezpečně přepočítá `match_confidence` u AUTO_MATCHED dokumentů aktuálním matcherem, aktualizuje jen tam, kde by nové skóre bylo vyšší (nikdy nesnižuje). Řeší zamrzlá stará skóre u sezení vytvořených před opravou matcheru.

## Dokumentace business logiky

- **[docs/BUSINESS-LOGIC.md](docs/BUSINESS-LOGIC.md)** — technický popis business logiky, stavových automatů, výpočetních pravidel a integracích s odkazy na zdrojový kód
- **[docs/BUSINESS-SUMMARY.md](docs/BUSINESS-SUMMARY.md)** — netechnický souhrn pro členy výboru SVJ

## UI vzory

Kompletní UI/frontend konvence (layout, tabulky, formuláře, tlačítka, bubliny, badge, inline editace, HTMX vzory, back URL navigace, checkboxy, stepper, formátování, dark mode) jsou v **[docs/UI_GUIDE.md](docs/UI_GUIDE.md)**.
