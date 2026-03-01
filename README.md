# SVJ Správa

Webová aplikace pro automatizaci správy SVJ (Společenství vlastníků jednotek). Spravuje evidenci vlastníků a jednotek, hlasování per rollam, rozúčtování daní a synchronizaci dat s externími zdroji.

## Tech stack

- **Backend:** FastAPI + SQLAlchemy ORM + SQLite
- **Frontend:** Jinja2 šablony + HTMX + Tailwind CSS (CDN) + dark mode (CSS override, přepínač v sidebaru)
- **Dokumenty:** openpyxl (Excel), docxtpl (Word), pdfplumber (PDF), Tesseract (OCR)
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

## Moduly

### A. Evidence vlastníků (`/vlastnici`)

- Vytvoření nového vlastníka (inline HTMX formulář: příjmení, jméno, titul, typ, email, telefon, RČ/IČ)
- Import z Excelu (31 sloupců, sheet `Vlastnici_SVJ`) s náhledem a potvrzením
- Historie importů s možností smazání (smaže vlastníky, jednotky i přiřazení)
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
  - Inline editace kontaktů (email, telefon) přes HTMX
  - Inline editace trvalé a korespondenční adresy přes HTMX
  - Uložit/Zrušit tlačítka nahoře vedle nadpisu sekce (ne dole pod formulářem)
  - Správa přiřazených jednotek (klik „+ Přidat" → Uložit/Zrušit nahoře nahradí tlačítko, formulář dole; odebrat ikonou koše)
  - Sloupec Podíl % (podíl SČD / celkový počet podílů z administrace)
  - Souhrnný řádek Celkem (podíl SČD, podíl %, plocha)
  - Proklik na detail jednotky
  - Kolapsovatelná sekce „Historie vlastnictví" — předchozí jednotky s daty od/do, prokliky s back URL chain
- Export zpět do Excelu

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
- Neodevzdané lístky s vyhledáváním (diacritics-insensitive, jméno, email), server-side řazení (vlastník, jednotky, email, hlasy, stav), klikací vlastníci a jednotky s back URL
- Sčítání hlasů a výpočet kvóra (vstup v %, uložení jako podíl 0–1)
- Podpora hlasování v zastoupení (plné moci)
- Stavy hlasování: koncept → aktivní → uzavřené / zrušené
- Zpracování lístků: řazení dle vlastníka/jednotek/hlasů
- Hromadné zpracování: checkboxy, select all, batch zadání hlasů pro více lístků najednou
- Import výsledků hlasování z Excelu:
  - 4-krokový flow: upload → mapování sloupců → náhled → potvrzení
  - Mapování sloupců na role (vlastník, jednotka, bod hlasování) s předvyplněním z uloženého mapování
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
  - Soubory se uloží na disk, zpracování běží na pozadí (vlákno)
  - Progress bar s počtem zpracovaných/celkem, procentuální lištou, názvem aktuálního souboru, uplynulým časem a odhadem zbývajícího (ETA)
  - HTMX polling (500ms), po dokončení automatický redirect na párování
- Extrakce jmen z PDF (pdfplumber):
  - Primárně jednotlivá jména ze sekce „Údaje o vlastníkovi:" (SP řádky na str. 1)
  - Fallback na kombinované jméno ze sekce „Vlastník:" (str. 2)
  - Slučování firemních názvů rozlomených přes více SP řádků (detekce suffixů s.r.o., a.s., z.s. atd. a all-uppercase fragmentů)
- Fuzzy párování jmen na vlastníky v databázi — každé jméno z PDF se páruje zvlášť:
  - Nejdřív shoda na vlastníky dané jednotky (práh 0.6), pak globální hledání (práh 0.75)
  - Sloupec „Jméno z PDF" zobrazuje všechna individuální jména oddělená čárkou
  - Spoluvlastníci se přidávají pouze pokud jsou nalezeni v PDF, nikoliv z databáze
  - Ruční přiřazení automaticky přidá spoluvlastníky na stejné jednotce
- X tlačítko (odebrat vlastníka) skryto u potvrzených distribucí a u 100% shody
- Redesignovaná stránka přiřazení:
  - Fixní header s 5 stat kartami (celkem / potvrzeno / k potvrzení / nepřiřazeno / bez PDF)
  - Bublina „Bez PDF" (oranžová) — jednotky s vlastníky, pro které nebyl nahrán žádný dokument; tabulka s prokliky na jednotku a vlastníky
  - Toolbar s checkboxy: vybrat/zrušit vše, potvrdit vybrané, potvrdit vše
  - Multi-owner zobrazení: barevné badge s X odebráním pro každého vlastníka
  - Dropdown přiřazení s `display_name (j. X, Y)` — zobrazuje čísla jednotek
  - 7 sortable sloupců (checkbox, soubor, jednotka, jméno z PDF, vlastníci, shoda, akce)
- Odebrání vlastníka z dokumentu (pokud poslední → UNMATCHED)
- Přidání externího příjemce (ad-hoc jméno + email)
- Přejmenování relace (inline HTMX editace názvu — tlačítko „Uložit")
- Workflow dokončení relace:
  - „Uložit a zavřít" — nedestruktivní zavření, návrat na seznam
  - „Dokončit" — uzamknutí relace (read-only mód, nelze měnit přiřazení)
  - „Znovu otevřít" — odemknutí dokončené relace pro další úpravy (krok 1 zůstane zelený pokud existují dokumenty)
  - „Pokračovat na rozesílku →" — přechod k odesílání emailů (pouze u dokončených)
  - „Nahrát další PDF" — obrysové tlačítko na stránce přiřazení pro doplnění/přepsání dokumentů
  - Re-import: volba režimu „Doplnit k existujícím" / „Přepsat stávající" (smaže staré PDF + přiřazení)
  - Read-only mód: skryté checkboxy, assign dropdown, potvrdit/odebrat tlačítka, externí formulář; viditelné statusové štítky (Potvrzeno/Nepřiřazeno/Nepotvrzeno)
- Rozesílka (`/dane/{id}/rozeslat`):
  - Stat karty jako filtry (celkem, s emailem, čekající, odesláno, chyba) ve stylu shodném s matchingem — podmíněné zobrazení karet odesláno/chyba
  - Samostatný search bar pod kartami s HTMX partial swapem
  - Vyhledávání příjemců (jméno, email, název souboru) s diacritics-insensitive porovnáním
  - Server-side řazení (příjemce, email, počet dokumentů, stav) s HTMX partial
  - Bookmarkovatelné URL parametry (q, filtr, sort, order)
- Wizard stepper: kompaktní kroky (Nahrání PDF → Přiřazení → Rozesílka → Dokončeno) na kartách i detail stránkách; po dokončení workflow všechny kroky zelené
- Index stránka:
  - Filtrační bubliny podle stavu (vše, rozpracováno, připraveno, odesílání, dokončeno)
  - Compact wizard stepper na kartě každé relace
  - Progress bar „Potvrzeno X / Y" na každé kartě relace
  - Stavové badge: „Rozpracováno" (žlutá), „Dokončeno" (zelená), „Odesílá se" (modrá), „Odesláno" (modrá), „Pozastaveno" (žlutá)
- Smazání celé relace (session + dokumenty + distribuce + soubory)

### E. Kontrola vlastníků (`/synchronizace`)

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

### F. Administrace SVJ (`/sprava`)

- Informace o SVJ (název, typ budovy, celkový počet podílů) — read-only pohled + inline editace
- Správa adres SVJ — přidání, editace, smazání s řazením abecedně
- Členové výboru — přidání, inline editace, smazání (jméno, role, email, telefon)
- Členové kontrolního orgánu — stejná funkcionalita
- Autocomplete rolí přes `<datalist>` (Předseda/Místopředseda/Člen)
- Řazení členů: předsedové → místopředsedové → ostatní, v rámci role abecedně
- Zálohování a obnova dat:
  - Vytvoření zálohy (ZIP: databáze + uploads + generované soubory) s vlastním názvem
  - Ochrana proti prázdným zálohám (varování pokud nejsou žádná data)
  - Seznam existujících záloh s datem, velikostí, stažením a smazáním
  - Obnova ze zálohy — tři způsoby:
    - Upload ZIP souboru
    - Upload složky rozbalené zálohy z Finderu (webkitdirectory) — obnoví DB + uploads + generated
    - Upload souboru svj.db
  - Před každou obnovou se automaticky vytvoří pojistná záloha
  - Po obnově automatická migrace (engine.dispose + přidání chybějících sloupců/indexů) — server nepadá
  - Flash zpráva po úspěšné obnově i vytvoření zálohy
  - Sekce zůstává otevřená po všech akcích (query param `sekce=zalohy`)
  - Side-by-side layout: vytvořit zálohu vlevo, obnovit vpravo
  - `application/octet-stream` pro stahování — Safari nerozbaluje automaticky
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

### G. Kontrola podílu SČD (`/kontrola-podilu`)

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

### H. Nastavení (`/nastaveni`)

- SMTP konfigurace — read-only přehled (4-sloupcový grid) + inline editace (HTMX)
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
├── utils.py                   # Sdílené utility (strip_diacritics, build_list_url, is_htmx_partial)
├── models/                    # Databázové modely
│   ├── owner.py               #   Owner, Unit, OwnerUnit, Proxy
│   ├── voting.py              #   Voting, VotingItem, Ballot, BallotVote
│   ├── tax.py                 #   TaxSession, TaxDocument, TaxDistribution
│   ├── sync.py                #   SyncSession, SyncRecord
│   ├── share_check.py         #   ShareCheckSession, ShareCheckRecord, ShareCheckColumnMapping
│   ├── common.py              #   EmailLog, ImportLog
│   └── administration.py      #   SvjInfo, SvjAddress, BoardMember, CodeListItem, EmailTemplate
├── routers/                   # HTTP endpointy
│   ├── dashboard.py           #   GET /
│   ├── owners.py              #   /vlastnici (+ /vlastnici/import)
│   ├── units.py               #   /jednotky
│   ├── voting.py              #   /hlasovani
│   ├── tax.py                 #   /dane
│   ├── sync.py                #   /synchronizace
│   ├── share_check.py         #   /kontrola-podilu
│   ├── administration.py      #   /sprava
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
│   ├── share_check_comparator.py #  Parsování souboru + porovnání podílů SČD
│   ├── owner_exchange.py      #   Výměna vlastníků při synchronizaci
│   ├── backup_service.py      #   Zálohování a obnova dat (ZIP)
│   ├── data_export.py         #   Export dat do Excel/CSV (6 kategorií)
│   ├── email_service.py       #   SMTP odesílání emailů
│   └── code_list_service.py   #   Sdílený přístup k číselníkům
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
│   │   ├── compare.html       #     Porovnání s filtry a bublinami
│   │   └── exchange_preview.html #  Preview výměny vlastníků
│   ├── share_check/           #   Stránky kontroly podílu
│   │   ├── index.html         #     Nahrání souboru + historie kontrol
│   │   ├── mapping.html       #     Mapování sloupců (krok 2)
│   │   └── compare.html       #     Výsledky s filtry a bublinami
│   ├── administration/        #   Stránky administrace
│   │   ├── index.html         #     Info SVJ, adresy, výbor, kontrolní orgán, číselníky
│   │   ├── bulk_edit.html     #     Hromadné úpravy — výběr pole
│   │   ├── duplicates.html      #     Přehled a sloučení duplicitních vlastníků
│   │   ├── bulk_edit_values.html #  HTMX: tabulka unikátních hodnot
│   │   └── bulk_edit_records.html # HTMX: záznamy pro danou hodnotu
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
│       ├── wizard_stepper.html
│       ├── wizard_stepper_compact.html
│       ├── unit_owners.html
│       └── unit_owner_edit_row.html
└── static/                    # CSS, JS
    ├── css/custom.css         # HTMX animace
    ├── css/dark-mode.css      # Dark mode CSS override (~300 pravidel)
    └── js/app.js              # HTMX handlery, dark mode toggle, PDF modal
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

### Vlastníci (`/vlastnici`)

| Metoda | Cesta | Popis |
|--------|-------|-------|
| GET | `/vlastnici` | Seznam vlastníků (search, filtr, řazení) |
| GET | `/vlastnici/novy-formular` | HTMX: formulář nového vlastníka |
| POST | `/vlastnici/novy` | Vytvoření vlastníka → redirect na detail |
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
| GET | `/vlastnici/{id}/identita-formular` | HTMX: formulář editace identity |
| GET | `/vlastnici/{id}/identita-info` | HTMX: zobrazení identity |
| POST | `/vlastnici/{id}/identita-upravit` | Uložení identity (+ detekce duplicit) |
| POST | `/vlastnici/{id}/sloucit` | Sloučení duplicitních vlastníků |
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
| GET | `/hlasovani` | Seznam hlasování (filtr dle stavu, bubliny) |
| GET | `/hlasovani/nova` | Formulář nového hlasování |
| POST | `/hlasovani/nova/nahled-metadat` | AJAX: extrakce metadat z .docx šablony |
| POST | `/hlasovani/nova` | Vytvoření hlasování + šablona .docx |
| GET | `/hlasovani/{id}` | Detail hlasování s výsledky (search, sort, HTMX partial) |
| POST | `/hlasovani/{id}/smazat` | Smazání hlasování (cascade + soubory) |
| POST | `/hlasovani/{id}/stav` | Změna stavu hlasování |
| POST | `/hlasovani/{id}/pridat-bod` | Přidání bodu hlasování |
| POST | `/hlasovani/{id}/smazat-bod/{item_id}` | Smazání bodu hlasování |
| POST | `/hlasovani/{id}/generovat` | Generování PDF lístků |
| GET | `/hlasovani/{id}/listky` | Seznam lístků (filtr stavu, search, sort, HTMX partial) |
| GET | `/hlasovani/{id}/listek/{ballot_id}` | Detail hlasovacího lístku |
| GET | `/hlasovani/{id}/zpracovani` | Stránka zpracování lístků (search, sort, HTMX partial) |
| POST | `/hlasovani/{id}/zpracovat/{ballot_id}` | Zpracování jednoho lístku |
| POST | `/hlasovani/{id}/zpracovat-hromadne` | Hromadné zpracování vybraných lístků |
| GET | `/hlasovani/{id}/neodevzdane` | Neodevzdané lístky (search, sort) |
| GET | `/hlasovani/{id}/import` | Stránka importu výsledků z Excelu |
| POST | `/hlasovani/{id}/import` | Nahrání Excel souboru → mapování sloupců |
| POST | `/hlasovani/{id}/import/nahled` | Náhled importu (přiřazení + statistika) |
| POST | `/hlasovani/{id}/import/potvrdit` | Potvrzení a provedení importu |

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
| GET | `/dane/{id}/upload` | Formulář pro nahrání dalších PDF (append/overwrite) |
| POST | `/dane/{id}/upload` | Nahrání dalších PDF + zpracování na pozadí |
| POST | `/dane/{id}/smazat` | Smazání relace (session + dokumenty + soubory) |
| GET | `/dane/{id}/rozeslat` | Rozesílka — preview příjemců (search, sort) |

### Kontrola vlastníků (`/synchronizace`)

| Metoda | Cesta | Popis |
|--------|-------|-------|
| GET | `/synchronizace` | Nahrání CSV + historie kontrol (search, sort) |
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

### Kontrola podílu SČD (`/kontrola-podilu`)

| Metoda | Cesta | Popis |
|--------|-------|-------|
| GET | `/kontrola-podilu` | Historie kontrol + upload formulář (search, sort) |
| POST | `/kontrola-podilu/nova` | Nahrání souboru → redirect na mapování |
| GET | `/kontrola-podilu/mapovani` | Mapování sloupců (auto-detekce + preview) |
| POST | `/kontrola-podilu/potvrdit-mapovani` | Porovnání → uložení → redirect na detail |
| GET | `/kontrola-podilu/{id}` | Výsledky s filtry, bublinami a search |
| POST | `/kontrola-podilu/{id}/smazat` | Smazání kontroly (záznamy + soubor) |
| POST | `/kontrola-podilu/{id}/aktualizovat` | Batch update Unit.podil_scd z vybraných |

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
| POST | `/sprava/zaloha/obnovit-slozku` | Obnova z rozbalené složky zálohy (webkitdirectory) |
| POST | `/sprava/zaloha/obnovit-soubor` | Obnova z nahraného svj.db souboru |
| POST | `/sprava/zaloha/obnovit-adresar` | Obnova z lokální cesty k adresáři |
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

- **Owner** — vlastník (jméno, tituly, RČ/IČ, adresy, kontakty, is_active); `display_name` property: formát „příjmení jméno" s titulem
- **Unit** — jednotka (číslo KN jako INTEGER, budova, sekce, plocha, podíl SČD)
- **OwnerUnit** — vazba vlastník-jednotka (typ vlastnictví, podíl, hlasovací váha, valid_from, valid_to); valid_to=NULL = aktuálně platný, valid_to=datum = historický záznam
- **Proxy** — plná moc pro hlasování
- **Voting** → VotingItem → Ballot → BallotVote
- **TaxSession** → TaxDocument → TaxDistribution
- **SyncSession** → SyncRecord (cascade delete)
- **ShareCheckSession** → ShareCheckRecord (cascade delete); ShareCheckColumnMapping (zapamatované mapování sloupců)
- **SvjInfo** → SvjAddress — informace o SVJ a adresy
- **BoardMember** — členové výboru a kontrolního orgánu (group: board/control)
- **CodeListItem** — položky číselníků (category: space_type/section/room_count/ownership_type, value, order); unique index na (category, value)
- **EmailTemplate** — šablony emailů pro hromadné rozesílání (name, subject_template, body_template, order); placeholder `{rok}` nahrazen při výběru
- **EmailLog**, **ImportLog** — systémové logy

## UI vzory

Kompletní UI/frontend konvence (layout, tabulky, formuláře, tlačítka, bubliny, badge, inline editace, HTMX vzory, back URL navigace, checkboxy, stepper, formátování, dark mode) jsou v **[docs/UI_GUIDE.md](docs/UI_GUIDE.md)**.
