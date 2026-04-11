# UX Analýza — Hlasování per rollam

> Analyzováno: 2026-03-04
> Rozsah: modul Hlasování per rollam — celý workflow od vytvoření hlasování po uzavření a export

## Souhrn

| Pohled | Kritické | Důležité | Drobné |
|--------|----------|----------|--------|
| Běžný uživatel | 2 | 3 | 4 |
| Business analytik | 1 | 4 | 2 |
| UI/UX designer | 0 | 1 | 5 |
| Performance analytik | 0 | 1 | 1 |
| Error recovery | 2 | 3 | 1 |
| Data quality | 2 | 3 | 1 |
| **Celkem (unikátní)** | **4** | **10** | **9** |

---

## Nálezy a návrhy

### Krok 1: Vytvoření hlasování

#### Nález #1: Chyba uploadu šablony — tichý redirect bez zprávy
- **Severity:** KRITICKÉ
- **Pohled:** Běžný uživatel, Error recovery
- **Problém:** Když `validate_upload()` při vytvoření hlasování najde problém (špatná přípona, příliš velký soubor), router přesměruje na `/hlasovani/nova?chyba=upload`. Šablona `create.html` ale parametr `chyba` **vůbec nečte ani nezobrazuje** — uživatel vidí prázdný formulář bez vysvětlení.
- **Dopad:** Uživatel opakovaně nahrává soubor a nedostává žádnou zpětnou vazbu. Může se vzdát bez pochopení problému.
- **Kde v kódu:** `app/routers/voting.py:304-305` (redirect s `?chyba=upload`), `app/templates/voting/create.html` (chybí čtení query parametru)
- **Návrh:** Přidat `chyba: str = Query("")` parametr do GET endpointu `voting_create_page` a zobrazit flash zprávu v šabloně. Alternativně vrátit šablonu přímo z POST endpointu s `flash_message` (jako u importu).

#### Nález #2: Selhání extrakce bodů z Word šablony — tiché spolknutí chyby
- **Severity:** DŮLEŽITÉ
- **Pohled:** Běžný uživatel, Error recovery
- **Problém:** Pokud `extract_voting_items()` selže (poškozený .docx, neočekávaný formát), `except Exception` na řádku 327 tiše spolkne chybu. Hlasování se vytvoří **bez bodů** a bez upozornění. Uživatel musí ručně přidávat body, aniž ví, že extrakce selhala.
- **Dopad:** Uživatel očekává body z šablony, ale vidí prázdný detail. Neví, zda šablona neobsahovala body, nebo zda extrakce selhala.
- **Kde v kódu:** `app/routers/voting.py:327-329`
- **Návrh:** Po catchnutí výjimky přidat flash zprávu (query parametr): `?info=extrakce-selhala`. Na detail stránce zobrazit varování: „Body hlasování nebyly nalezeny v šabloně. Přidejte je ručně."

#### Nález #3: „Generovat lístky" nemá potvrzovací dialog
- **Severity:** KRITICKÉ
- **Pohled:** Běžný uživatel, Data quality
- **Problém:** Tlačítko „Generovat lístky" v headeru je přímý `<form method="post">` bez `onsubmit="return confirm()"`. Jedno kliknutí nevratně přesune hlasování z DRAFT do ACTIVE a vytvoří lístky pro všechny vlastníky. Neexistuje cesta zpět (nelze vrátit do DRAFT).
- **Dopad:** Uživatel může omylem kliknout před dokončením přípravy bodů. Lístky se vytvoří se snapshot hlasů — pozdější změny vlastníků se neprojeví.
- **Kde v kódu:** `app/templates/voting/_voting_header.html:23-27`
- **Návrh:** Přidat `onsubmit="return confirm('Vygenerovat lístky pro X vlastníků? Po generování nelze přidávat ani odebírat body hlasování.')"`. Počet vlastníků předat ze serveru.
- **Mockup:**
  ```
  Současný stav:
  ┌──────────────────────────────────┐
  │  [Generovat lístky]  ← přímý POST, žádné potvrzení
  └──────────────────────────────────┘

  Navrhovaný stav:
  ┌──────────────────────────────────────────────────┐
  │  "Vygenerovat lístky pro 85 vlastníků?           │
  │  Po generování nelze přidávat ani odebírat       │
  │  body hlasování."                                │
  │                           [Zrušit] [Generovat]   │
  └──────────────────────────────────────────────────┘
  ```

#### Nález #4: Body hlasování nelze přeuspořádat ani editovat
- **Severity:** DŮLEŽITÉ
- **Pohled:** Běžný uživatel, Business analytik
- **Problém:** Po přidání bodu hlasování neexistuje způsob, jak změnit jeho název, popis nebo pořadí. Uživatel může bod pouze smazat a přidat znovu (tím ztratí pořadí). Přidání přiřadí `order = max_order + 1` — po smazání prostředního bodu vznikne mezera v číslování (1, 3, 4).
- **Dopad:** Uživatel musí smazat a znovu přidat body pro opravu překlepu nebo změnu pořadí. Mezery v číslování matou při ručním zpracování.
- **Kde v kódu:** `app/routers/voting.py:939-959` (přidání), `app/routers/voting.py:926-936` (mazání)
- **Návrh:** (a) Přidat inline edit tlačítko pro úpravu názvu/popisu bodu. (b) Drag & drop nebo šipky nahoru/dolů pro přeuspořádání. (c) Při mazání přečíslovat zbylé body.

---

### Krok 2: Generování lístků

#### Nález #5: Snapshot hlasů bez varování o zastaralosti
- **Severity:** DŮLEŽITÉ
- **Pohled:** Data quality, Business analytik
- **Problém:** Při generování lístků se `total_votes` a `units_text` uloží jako snapshot aktuálního stavu. Pokud se po generování změní vlastnictví (prodej jednotky, změna podílu), lístek stále zobrazuje staré údaje. Neexistuje žádné varování ani způsob aktualizace.
- **Dopad:** Hlasování může proběhnout s neaktuálními údaji o hlasech, což zpochybní jeho platnost. Zejména problém u dlouho běžících hlasování (týdny/měsíce).
- **Kde v kódu:** `app/routers/voting.py:474-483` (snapshot při generování)
- **Návrh:** (a) Na detail stránce zobrazit varování, pokud se `total_votes_possible` (aktuální součet) liší od součtu `ballot.total_votes` (snapshotů). (b) Nabídnout tlačítko „Přepočítat hlasy" (s potvrzením).

#### Nález #6: Stavy „Odesláno" a „Přijato" nemají UI pro nastavení
- **Severity:** DROBNÉ
- **Pohled:** UI/UX designer, Business analytik
- **Problém:** Model `BallotStatus` definuje stavy SENT a RECEIVED, header je zobrazuje v bublinách, ballot detail je vykresluje jako badge — ale neexistuje žádné tlačítko, formulář ani endpoint pro přechod lístku do těchto stavů. Tyto bubliny vždy ukazují 0.
- **Dopad:** Matoucí UI — uživatel vidí bublinu „Odesláno: 0" a „Přijato: 0" bez možnosti tyto stavy nastavit. Zabírají místo zbytečně.
- **Kde v kódu:** `app/templates/voting/_voting_header.html:67-72` (bublina sent)
- **Návrh:** Buď (a) přidat UI pro hromadné označení lístků jako odeslaných/přijatých (checkbox + bulk akce), nebo (b) skrýt tyto bubliny dokud nebudou mít funkční UI. Varianta (b) je jednodušší.

---

### Krok 3: Ruční zpracování

#### Nález #7: Zpracování lístku bez hlasů — žádná validace
- **Severity:** KRITICKÉ
- **Pohled:** Data quality, Error recovery
- **Problém:** Uživatel může kliknout „Potvrdit zpracování" na kartě lístku bez výběru jakéhokoliv hlasu (žádný radio button zaškrtnutý). Backend podmínka `if vote_value:` přeskočí nevyplněné položky, ale lístek se přesto označí jako PROCESSED s `vote = NULL` u všech bodů. Takový lístek se počítá do kvóra, ale nemá žádné hlasy.
- **Dopad:** Lístek bez hlasů ovlivňuje kvórum, ale nezapočítá se do výsledků bodů. Data quality problém — nelze rozlišit „vlastník se zdržel u všech bodů" od „zpracovatel zapomněl vyplnit hlasy".
- **Kde v kódu:** `app/routers/voting.py:718-727` (process_ballot — žádná validace)
- **Návrh:** Přidat validaci: alespoň u jednoho bodu musí být hlas vybrán. Pokud ne, vrátit kartu s chybovou zprávou místo označení PROCESSED.
- **Mockup:**
  ```
  Současný stav:
  ┌────────────────────────────────────┐
  │  Bod 1: ○ PRO  ○ PROTI  ○ Zdržel │  ← nic nevybráno
  │  Bod 2: ○ PRO  ○ PROTI  ○ Zdržel │  ← nic nevybráno
  │  [Potvrdit zpracování]            │  ← funguje! Lístek PROCESSED bez hlasů
  └────────────────────────────────────┘

  Navrhovaný stav:
  ┌────────────────────────────────────┐
  │  ⚠ Vyberte hlas u všech bodů.     │  ← červená zpráva
  │  Bod 1: ○ PRO  ○ PROTI  ○ Zdržel │
  │  Bod 2: ○ PRO  ○ PROTI  ○ Zdržel │
  │  [Potvrdit zpracování]            │
  └────────────────────────────────────┘
  ```

#### Nález #8: Hromadné zpracování bez potvrzení a bez validace
- **Severity:** DŮLEŽITÉ
- **Pohled:** Běžný uživatel, Data quality
- **Problém:** „Zpracovat vybrané" v bulk baru nemá `confirm()` dialog a nemá validaci hlasů (stejný problém jako #7). Uživatel může označit 50 lístků a odeslat je s prázdnými hlasy jedním klikem.
- **Dopad:** Hromadné zpracování bez validace může nevratně poškodit výsledky celého hlasování.
- **Kde v kódu:** `app/routers/voting.py:741-778`, `app/templates/voting/process.html:69-71`
- **Návrh:** (a) Přidat `onsubmit="return confirm('Zpracovat X lístků se stejnými hlasy?')"`. (b) Validovat, že alespoň u jednoho bodu je hlas vybrán.

#### Nález #9: Zpracovaný lístek nelze opravit
- **Severity:** DŮLEŽITÉ
- **Pohled:** Běžný uživatel, Error recovery
- **Problém:** Jakmile je lístek PROCESSED, ballot detail zobrazuje pouze read-only tabulku. Neexistuje tlačítko „Opravit" ani endpoint pro návrat lístku do stavu GENERATED. Pokud zpracovatel udělal chybu, musí editovat přímo v databázi.
- **Dopad:** Chyba při zpracování jednoho lístku z 85 nemá řešení v UI. Uživatel buď žije s chybou, nebo žádá o zásah do DB.
- **Kde v kódu:** `app/templates/voting/ballot_detail.html:51` (podmínka `if ballot.status.value == 'processed'`)
- **Návrh:** Přidat tlačítko „Opravit hlas" na ballot detail stránce (dostupné pro active hlasování). Reset lístku do GENERATED s potvrzením: „Opravdu chcete upravit zpracovaný lístek? Stávající hlasy budou smazány."

---

### Krok 4: Import výsledků z Excelu

#### Nález #10: Import result nezobrazuje statistiky
- **Severity:** DŮLEŽITÉ
- **Pohled:** Běžný uživatel, Business analytik
- **Problém:** Po potvrzení importu šablona `import_result.html` zobrazí pouze generickou zprávu „Import výsledků dokončen." a režim (doplnit/přepsat). Router předává `result` dict s klíči `processed_count`, `skipped_count`, `cleared_count`, `unmatched_count` — ale šablona je **nezobrazuje**.
- **Dopad:** Uživatel neví, kolik lístků bylo skutečně importováno, kolik přeskočeno, kolik nepřiřazeno. Musí ručně zkontrolovat seznam lístků.
- **Kde v kódu:** `app/templates/voting/import_result.html:14-16` (zobrazuje jen režim), `app/routers/voting.py:1203-1207` (result dict s daty)
- **Návrh:** Zobrazit statistiky:
- **Mockup:**
  ```
  Současný stav:
  ┌──────────────────────────────────┐
  │  ✓ Import výsledků dokončen.     │
  │  Režim: doplnit data.           │
  └──────────────────────────────────┘

  Navrhovaný stav:
  ┌──────────────────────────────────────────┐
  │  ✓ Import výsledků dokončen.             │
  │  Režim: doplnit data                     │
  │                                          │
  │  Zpracováno: 72 lístků                   │
  │  Přeskočeno: 8 (již zpracované)          │
  │  Nepřiřazeno: 3 řádků                   │
  │  Vyčištěno: 0                            │
  └──────────────────────────────────────────┘
  ```

#### Nález #11: Import confirm neověřuje existenci souboru
- **Severity:** DŮLEŽITÉ
- **Pohled:** Error recovery
- **Problém:** Mezi krokem Preview a Confirm může uplynout čas. Pokud se server mezitím restartuje a dočasné soubory se smažou, `import_confirm` endpoint zavolá `execute_voting_import()` s neexistujícím souborem → neošetřená výjimka → HTTP 500.
- **Dopad:** Uživatel vidí generickou 500 chybovou stránku místo srozumitelné zprávy.
- **Kde v kódu:** `app/routers/voting.py:1203` (`execute_voting_import` volá `load_workbook`)
- **Návrh:** Přidat kontrolu `Path(file_path).exists()` před voláním importu. Pokud soubor chybí, přesměrovat na import upload s flash zprávou „Soubor nebyl nalezen, nahrajte ho znovu."

#### Nález #12: Import v režimu „přepsat" nemá dodatečné varování
- **Severity:** DŮLEŽITÉ
- **Pohled:** Běžný uživatel, Error recovery
- **Problém:** Na preview stránce se zobrazuje badge „vyčistit a přepsat", ale při kliknutí na „Zapsat naimportované výsledky" neexistuje `confirm()` dialog. Režim přepsání resetuje VŠECHNY lístky, které nejsou v importu, zpět na GENERATED (smaže jejich hlasy).
- **Dopad:** Uživatel, který ručně zpracoval 20 lístků a pak importuje Excel s 60 lístky, přijde o ručně zadané hlasy bez varování.
- **Kde v kódu:** `app/templates/voting/import_preview.html` (tlačítko bez confirm)
- **Návrh:** Přidat `confirm()` pro overwrite mode: „Režim 'přepsat' smaže hlasy u X ručně zpracovaných lístků, které nejsou v importu. Pokračovat?"

---

### Krok 5: Uzavření hlasování

#### Nález #13: Uzavřít hlasování lze s jedním zpracovaným lístkem
- **Severity:** DŮLEŽITÉ
- **Pohled:** Business analytik, Data quality
- **Problém:** Podmínka pro zobrazení tlačítka „Uzavřít hlasování" je `show_close_voting = has_processed` — stačí jediný zpracovaný lístek z 85. Dialog `confirm('Opravdu uzavřít hlasování?')` neříká, kolik lístků zbývá zpracovat ani zda bylo dosaženo kvóra.
- **Dopad:** Hlasování může být uzavřeno předčasně s neúplnými výsledky. Uzavření je nevratné.
- **Kde v kódu:** `app/templates/voting/_voting_header.html:36-43`, `app/routers/voting.py:420` (`show_close_voting`)
- **Návrh:** Upravit confirm dialog: „Uzavřít hlasování? Zpracováno X z Y lístků (Z%). Kvórum: dosaženo/nedosaženo." Případně nepovolovat uzavření bez dosažení kvóra (nebo alespoň silnější varování).
- **Mockup:**
  ```
  Současný stav:
  ┌──────────────────────────────────┐
  │  "Opravdu uzavřít hlasování?"   │
  │                    [Zrušit] [OK] │
  └──────────────────────────────────┘

  Navrhovaný stav:
  ┌──────────────────────────────────────────┐
  │  Uzavřít hlasování?                      │
  │                                          │
  │  Zpracováno: 72 z 85 lístků (84.7%)     │
  │  Neodevzdáno: 13 lístků                  │
  │  Kvórum: 67.3% (dosaženo)               │
  │                                          │
  │  Po uzavření nelze přidávat hlasy.       │
  │                    [Zrušit] [Uzavřít]    │
  └──────────────────────────────────────────┘
  ```

#### Nález #14: Uzavřené hlasování nelze znovu otevřít
- **Severity:** DŮLEŽITÉ
- **Pohled:** Business analytik, Error recovery
- **Problém:** Po uzavření hlasování neexistuje UI pro jeho znovuotevření. Endpoint `/stav` technicky přijímá jakýkoliv status (včetně `active`), ale v šabloně headeru pro `closed` stav chybí jakékoliv akční tlačítko.
- **Dopad:** Pokud uživatel omylem uzavře hlasování nebo potřebuje doplnit lístky, nemá žádnou cestu zpět. Musí manipulovat DB.
- **Kde v kódu:** `app/templates/voting/_voting_header.html:45-47` (closed stav — jen badge, žádná akce)
- **Návrh:** Přidat tlačítko „Znovu otevřít" (se silným potvrzením) na detail stránce uzavřeného hlasování. Omezit na admin roli (až bude implementována).

---

### Průřezové problémy

#### Nález #15: Vyhledávání bez normalizace diakritiky na většině stránek
- **Severity:** DŮLEŽITÉ
- **Pohled:** Běžný uživatel, Performance analytik
- **Problém:** Hledání na stránkách lístky, zpracování a detail výsledků používá prosté `q.lower() in display_name.lower()`. Hledání „novak" nenajde „Novák", protože `á` ≠ `a`. **Jediná stránka s korektním vyhledáváním je neodevzdané** (`strip_diacritics`).
- **Dopad:** Uživatel zvyklý z jiných modulů aplikace (vlastníci, jednotky), kde hledání funguje bez diakritiky, je překvapen, že v hlasování nefunguje.
- **Kde v kódu:** `app/routers/voting.py:536-541` (ballots), `app/routers/voting.py:668-674` (process), `app/routers/voting.py:401-403` (detail results)
- **Návrh:** Přidat `strip_diacritics()` na všechny search filtry v modulu hlasování — stejný vzor jako `not_submitted` (řádek 986).

#### Nález #16: Hromadné zpracování — bulk bar ztrácí výběr po HTMX akci
- **Severity:** DROBNÉ
- **Pohled:** UI/UX designer, Běžný uživatel
- **Problém:** Po zpracování jednoho lístku přes HTMX (karta se nahradí zelenou potvrzovací kartou), `selectedBallots` Set v JS stále obsahuje ID zpracovaného lístku. Pokud uživatel pak klikne „Zpracovat vybrané", odešle se i ID již zpracovaného lístku. Backend ho přeskočí (filtruje dle `ballot_ids`), ale počet v bulk baru je zavádějící.
- **Dopad:** Mírně matoucí — „5 vybráno" ale jen 4 se zpracují, protože 1 už byl zpracován jednotlivě.
- **Kde v kódu:** `app/templates/voting/process.html:82-122` (JS), `app/templates/partials/ballot_processed.html` (nemá JS pro odebrání z Set)
- **Návrh:** V `ballot_processed.html` přidat inline `<script>` pro odebrání ballot ID ze `selectedBallots` setu a aktualizaci bulk baru. Nebo: skrýt checkbox na zpracovaných kartách.

#### Nález #17: Export dostupný pouze přes URL — chybí odkaz na detail stránce
- **Severity:** DROBNÉ
- **Pohled:** Běžný uživatel, UI/UX designer
- **Problém:** Endpoint `/exportovat` existuje a funguje, ale na detail stránce uzavřeného hlasování chybí tlačítko/odkaz pro export. Export ikona je jen na kartě v seznamu hlasování. Uživatel na detail stránce (kde tráví čas analýzou výsledků) nemá přímý přístup k exportu.
- **Dopad:** Uživatel musí navigovat zpět na seznam hlasování, aby našel export ikonu.
- **Kde v kódu:** `app/templates/voting/_voting_header.html:45-47` (closed stav — jen badge)
- **Návrh:** Přidat odkaz „Exportovat do Excelu" vedle badge „Uzavřeno" v headeru pro closed hlasování.

#### Nález #18: Nahrané Excel soubory (import) se nikdy nemažou
- **Severity:** DROBNÉ
- **Pohled:** Performance analytik
- **Problém:** Každý import uploadu uloží Excel soubor do `uploads/excel/`, ale po dokončení importu (confirm) se soubor nesmaže. Po čase se naakumulují desítky nepotřebných souborů. Srovnání: Word šablona v metadata preview se korektně maže (`finally: dest.unlink()`).
- **Dopad:** Plýtvání místem na disku. U USB distribuce (malý disk) může být problém.
- **Kde v kódu:** `app/routers/voting.py:1096-1100` (upload uloží), `app/routers/voting.py:1203` (confirm neruší soubor)
- **Návrh:** Po úspěšném importu smazat soubor: `try: Path(file_path).unlink() except: pass`.

#### Nález #19: `partial_owner_mode` se neuplatňuje při generování lístků
- **Severity:** KRITICKÉ
- **Pohled:** Data quality, Business analytik
- **Problém:** Formulář vytvoření nabízí volbu „Společný lístek" vs „Každý svůj lístek" pro spoluvlastnictví (SJM). Hodnota se uloží do `voting.partial_owner_mode`, ale `generate_ballots()` **vždy vytvoří jeden lístek na vlastníka** bez ohledu na toto nastavení. Režim `shared` by měl vytvořit jeden společný lístek pro SJM pár, `separate` oddělené.
- **Dopad:** Nastavení je nefunkční placebo. SJM páry vždy dostanou oddělené lístky, i když uživatel zvolí „Společný lístek".
- **Kde v kódu:** `app/routers/voting.py:461-498` (generate_ballots — žádná reference na `partial_owner_mode`)
- **Návrh:** V režimu `shared`: seskupit vlastníky podle jednotky (SJM pár sdílí jednotku), vytvořit jeden lístek pro skupinu se společným `total_votes`. V režimu `separate`: stávající chování (jeden lístek na vlastníka). Alternativně: pokud není plánována implementace, odebrat tuto volbu z formuláře aby uživatele nemátla.

#### Nález #20: Detail hlasování — výsledky nerozlišují „Zdržel se" a „Neodevzdané"
- **Severity:** DROBNÉ
- **Pohled:** Business analytik, UI/UX designer
- **Problém:** Na detail stránce (výsledková tabulka) jsou sloupce PRO, PROTI a „Chybí" (= `declared - for - against`). „Chybí" zahrnuje dohromady: (a) zdržení se, (b) neplatné hlasy, (c) neodevzdané lístky. Uživatel nerozlišuje, kolik vlastníků se aktivně zdrželo vs kolik vůbec neodevzdalo.
- **Dopad:** Nepřesné výsledky — u bodu s 40% PRO, 30% PROTI a 30% „Chybí" uživatel netuší, zda 30% se zdrželo nebo nehlasovalo.
- **Kde v kódu:** `app/routers/voting.py:377-398` (výpočet results — `votes_missing` nezahrnuje abstain zvlášť)
- **Návrh:** Přidat sloupec „Zdržel se" do výsledkové tabulky. „Chybí" pak = `declared - for - against - abstain`.

#### Nález #21: Wizard stepper — nekonzistentní logika na list page vs detail page
- **Severity:** DROBNÉ
- **Pohled:** UI/UX designer
- **Problém:** Na list stránce má active hlasování se všemi zpracovanými lístky `wizard_step = 5` (Uzavření), ale `list_max_done = 4`. Na detail stránce se pro stejný stav nastaví `detail_step = 5` a `_voting_wizard` vrátí `max_done = 4`. Výsledek je vizuálně identický, ale logika je duplicitní a mírně odlišná — na list page je extra `all_processed` check.
- **Dopad:** Minimální vizuální dopad, ale zvyšuje riziko budoucích bugů při úpravě jednoho místa bez druhého.
- **Kde v kódu:** `app/routers/voting.py:166-178` (list), `app/routers/voting.py:421-426` (detail)
- **Návrh:** Extrahovat wizard step logiku do `_voting_wizard()` helper funkce (ta již existuje, ale list page ji nepoužívá — má vlastní inline implementaci).

#### Nález #22: Kvórum bubble nezobrazuje, kolik hlasů chybí
- **Severity:** DROBNÉ
- **Pohled:** Běžný uživatel, UI/UX designer
- **Problém:** Kvórum bublina zobrazuje aktuální procento a zda bylo dosaženo. Když kvórum dosaženo nebylo, uživatel musí ručně počítat, kolik hlasů ještě potřebuje.
- **Dopad:** Uživatel nevidí na první pohled, jak daleko je od kvóra.
- **Kde v kódu:** `app/templates/voting/_voting_header.html:85-93`
- **Návrh:** Když kvórum není dosaženo, zobrazit pod procentem: „Chybí X hlasů" (= `quorum_threshold * declared - processed_votes`).

#### Nález #23: Ballot detail nemá wizard stepper ani status bubliny
- **Severity:** DROBNÉ
- **Pohled:** UI/UX designer
- **Problém:** Ballot detail stránka (`/listek/{id}`) používá jednoduchý layout s back šipkou, ale neobsahuje wizard stepper ani status bubliny z headeru. Uživatel ztrácí kontext o celkovém stavu hlasování.
- **Dopad:** Uživatel na ballot detailu neví, kolik lístků zbývá zpracovat nebo zda bylo dosaženo kvóra. Musí se vracet na přehled.
- **Kde v kódu:** `app/templates/voting/ballot_detail.html:5-7` (jen back link, žádný header)
- **Návrh:** Zahrnout `_voting_header.html` partial nebo alespoň kompaktní progress bar. Vyžaduje předání `_ballot_stats()` kontextu do ballot detail endpointu.

---

## Top 5 doporučení (podle dopadu)

| # | Návrh | Dopad | Složitost | Priorita |
|---|-------|-------|-----------|----------|
| 1 | Validace hlasů před zpracováním lístku (#7, #8) | Vysoký — chrání integritu dat | Nízká | HNED |
| 2 | Confirm dialog na „Generovat lístky" (#3) | Vysoký — nevratná akce bez ochrany | Nízká | HNED |
| 3 | Flash zpráva při chybě uploadu šablony (#1) | Vysoký — tichý fail frustruje | Nízká | HNED |
| 4 | Diakritika ve vyhledávání (#15) | Střední — konzistence s ostatními moduly | Nízká | BRZY |
| 5 | Import result statistiky (#10) + confirm při přepsání (#12) | Střední — uživatel neví co se stalo | Nízká–Střední | BRZY |

---

## Quick wins (nízká složitost, okamžitý efekt)

- [x] Confirm dialog na „Generovat lístky" (1 řádek `onsubmit` v šabloně)
- [x] Flash zpráva při chybě uploadu šablony (přidat `chyba` query param do GET endpointu + zobrazení v šabloně)
- [x] Validace hlasů při zpracování — alespoň warning (backend check + HTMX error response)
- [x] Confirm dialog na „Zpracovat vybrané" v bulk baru (1 řádek `onsubmit`)
- [x] `strip_diacritics()` ve vyhledávání na všech stránkách modulu (3 místa v routeru)
- [x] Import result — zobrazit `processed_count`, `skipped_count` z `result` dictu v šabloně
- [x] Confirm dialog na import v režimu „přepsat" (1 řádek JS v šabloně)
- [x] Smazání Excel souboru po úspěšném importu (2 řádky v routeru)
- [x] Export odkaz na detail stránce uzavřeného hlasování (1 `<a>` tag v headeru)
- [x] Kvórum bubble — zobrazit „Chybí X hlasů" (1 výpočet + text v šabloně)

---

## Výsledky implementace

> Implementováno: 2026-03-04
> Všechny quick wins implementovány a otestovány

### Stav jednotlivých fixů

| # | Nález | Stav | Poznámka |
|---|-------|------|----------|
| 1 | Flash při chybě uploadu šablony | ✅ Hotovo | `chyba` query param + flash v create.html |
| 2 | Selhání extrakce bodů — flash varování | ✅ Hotovo | `info` query param na detail page (extrakce-selhala / sablona-prazdna) |
| 3 | Generovat lístky bez potvrzení | ✅ Hotovo | `confirm()` dialog s varováním o nevratnosti |
| 4 | Body nelze přeuspořádat/editovat | ⏭️ Přeskočeno | Vyžaduje nový UI (drag & drop nebo šipky), větší scope |
| 5 | Snapshot hlasů bez varování | ⏭️ Přeskočeno | Vyžaduje novou logiku porovnání snapshot vs aktuální stav |
| 6 | Prázdné bubliny sent/received | ✅ Hotovo | Bublina "Odesláno" se skryje při count 0 |
| 7 | Zpracování lístku bez hlasů | ✅ Hotovo | Backend validace + HTMX error partial s červenou zprávou |
| 8 | Hromadné zpracování bez potvrzení | ✅ Hotovo | `confirm()` s počtem vybraných + backend validace hlasů |
| 9 | Zpracovaný lístek nelze opravit | ⏭️ Přeskočeno | Vyžaduje nový endpoint + UI s potvrzením, větší scope |
| 10 | Import result bez statistik | ✅ Hotovo | Zobrazení processed/skipped/unmatched/cleared counts |
| 11 | Import confirm neověřuje soubor | ✅ Hotovo | `Path(file_path).exists()` check před importem |
| 12 | Import přepsat bez varování | ✅ Hotovo | `confirm()` pro režim „přepsat" |
| 13 | Uzavření s 1 lístkem — špatný confirm | ✅ Hotovo | Confirm zobrazuje počty zpracovaných, neodevzdaných a stav kvóra |
| 14 | Nelze znovu otevřít hlasování | ⏭️ Přeskočeno | Vyžaduje nový endpoint + UI, navázáno na role (admin) |
| 15 | Vyhledávání bez diakritiky | ✅ Hotovo | `strip_diacritics()` na ballots, process a detail results |
| 16 | Bulk bar ztrácí výběr po HTMX | ⏭️ Přeskočeno | Minor JS edge case |
| 17 | Export odkaz na detail closed | ✅ Hotovo | "Exportovat do Excelu" tlačítko v headeru closed hlasování |
| 18 | Excel soubory se nemažou | ✅ Hotovo | `Path(file_path).unlink()` po úspěšném importu |
| 19 | partial_owner_mode nefunkční | ⏭️ Přeskočeno | Vyžaduje velký refaktoring generate_ballots, zvážit odebrání volby |
| 20 | Výsledky nerozlišují Zdržel/Neodevzdané | ⏭️ Přeskočeno | Vyžaduje přidání sloupce do tabulky + přepočet |
| 21 | Wizard duplicitní logika | ⏭️ Přeskočeno | Refaktoring bez vizuálního dopadu |
| 22 | Kvórum — chybí X hlasů | ✅ Hotovo | Zobrazení "Chybí X" pod kvórem když nedosaženo |
| 23 | Ballot detail bez kontextu | ⏭️ Přeskočeno | Vyžaduje předání ballot_stats do endpoint kontextu |

**Celkem:** 14 implementováno, 9 přeskočeno (větší scope / minimální dopad)

### Změněné soubory

| Soubor | Změny |
|--------|-------|
| `app/routers/voting.py` | Flash zprávy (#1,#2), validace hlasů (#7,#8), diakritika search (#15), file check (#11), Excel cleanup (#18), `info` param na detail (#2) |
| `app/templates/voting/create.html` | Flash message zobrazení (#1) |
| `app/templates/voting/_voting_header.html` | Confirm generate (#3), skrytí sent bubliny (#6), close confirm s počty (#13), export odkaz (#17), kvórum chybí (#22) |
| `app/templates/voting/process.html` | Confirm na bulk zpracování (#8) |
| `app/templates/voting/import_result.html` | Statistiky importu (#10) |
| `app/templates/voting/import_preview.html` | Confirm na přepsat (#12) |
| `app/templates/partials/ballot_vote_error.html` | Nový — HTMX error partial pro validaci (#7) |

### Manuální testování

1. **Flash při chybě uploadu (#1):** Navštívit `/hlasovani/nova?chyba=upload` → červená zpráva
2. **Flash při selhání extrakce (#2):** Navštívit `/hlasovani/{id}?info=extrakce-selhala` → žluté varování
3. **Confirm generování (#3):** Na draft hlasování kliknout „Generovat lístky" → confirm dialog
4. **Validace hlasů (#7):** Na zpracování kliknout „Potvrdit zpracování" bez výběru → červená chyba na kartě
5. **Bulk confirm (#8):** Označit lístky, kliknout „Zpracovat vybrané" → confirm s počtem
6. **Skrytá sent bublina (#6):** Na hlasování bez odeslaných lístků chybí bublina „Odesláno"
7. **Import statistiky (#10):** Po importu vidět počet zpracovaných, přeskočených, nepřiřazených
8. **Import přepsat confirm (#12):** Při importu v režimu „přepsat" → confirm dialog
9. **Uzavření confirm (#13):** Klik na „Uzavřít hlasování" → confirm s počty a kvórem
10. **Diakritika (#15):** Na lístcích hledat „novak" → najde „Novák"
11. **Export odkaz (#17):** Na closed hlasování v headeru tlačítko „Exportovat do Excelu"
12. **Kvórum chybí (#22):** Na hlasování bez kvóra zobrazit „Chybí X" pod procentem
13. **Excel cleanup (#18):** Po importu zkontrolovat, že Excel soubor smazán z `uploads/excel/`
14. **File check (#11):** Smazat Excel soubor ručně, pak potvrdit import → redirect na upload (ne 500)
