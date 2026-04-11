# UX Analýza — Celá aplikace (revize 2)

> Analyzováno: 2026-03-08
> Rozsah: Celá aplikace (9 modulů: Přehled, Vlastníci, Jednotky, Import z Excelu, Hlasování, Hromadné rozesílání, Kontroly, Administrace, Nastavení)
> Kontext: Předchozí report (2026-03-08 v1) měl 7K / 13D / 13Dr. Od té doby bylo opraveno ~33 nálezů. Toto je nový kompletní audit.

## Souhrn

| Pohled | Kritické | Důležité | Drobné |
|--------|----------|----------|--------|
| Běžný uživatel | 1 | 3 | 4 |
| Business analytik | 1 | 2 | 1 |
| UI/UX designer | 0 | 3 | 5 |
| Performance analytik | 1 | 1 | 1 |
| Error recovery | 1 | 3 | 2 |
| Data quality | 1 | 2 | 1 |
| **Celkem** | **5** | **14** | **14** |

### Stav předchozích nálezů

| ID | Popis | Stav |
|----|-------|------|
| K1 | Quorum — započítání neúplných hlasů | **OPRAVENO** — `_ballot_stats()` nyní počítá partial ballots separátně a nezapočítává je do kvóra bez hlasů |
| K2 | Import přepisuje hlasy bez varování | **OPRAVENO** — import preview nyní ukazuje „staré → nové" + bublinu „Přepíše" + `data-confirm` |
| K3 | SJM — riziko dvojitého započtení | **OPRAVENO** — SJM warning v import preview + deduplikace přes `seen_ballots` |
| K4 | N+1 Python-side sort (podíl, jednotky) | **OPRAVENO** — přepsáno na SQL subquery sort (`podil_sub`, `unit_sub`, `sec_sub`) |
| K5 | N+1 query v tax sending | **PŘETRVÁVÁ** — viz K1 níže |
| K6 | Error reporting nekonzistentní | **ČÁSTEČNĚ OPRAVENO** — sync má `_CHYBA_MSG` dict, ale některé chybové cesty stále redirectují tiše |
| K7 | Ztráta pozice v tabulce po akci | **OPRAVENO** — HTMX partial swap + scroll save/restore v `app.js` |
| D1-D13 | Důležité nálezy | Většina opravena (bulk reset, flash zprávy, data-confirm, ballot progress) |
| Dr1-Dr13 | Drobné nálezy | Většina opravena (export pro active, quorum preview, data-confirm sjednocení) |

---

## KRITICKÉ

### K1: N+1 query v tax matching — in-loop DB dotazy

- **Severity:** KRITICKÉ
- **Modul:** Hromadné rozesílání (matching)
- **Pohled:** Performance analytik
- **Problém:** V `sending.py:238-252` se pro každý dokument v `all_docs` smyčce dělají separátní `db.query(TaxDistribution).filter_by(document_id=doc.id).all()` dotazy. Při 100+ dokumentech to znamená 100+ SQL dotazů v jednom requestu. Podobný vzor je v owner email update (řádky 220-273), kde se pro každý matched document kontrolují distribuce.
- **Dopad:** Pomalá odezva při přiřazování emailu u session s velkým počtem dokumentů. Uživatel čeká několik sekund.
- **Návrh:** Předem načíst všechny distribuce jedním dotazem a indexovat je do dictu `{doc_id: [dists]}`. Použít `joinedload` nebo batch query.
- **Kde v kódu:** `app/routers/tax/sending.py:238-252`
- **Mockup:**
  ```
  Současný stav (in-loop):
  for doc in all_docs:          # 100 iterací
      dists = db.query(TD)      # 100 SQL dotazů
          .filter_by(doc.id)
          .all()

  Navrhovaný stav (batch):
  all_dists = db.query(TD)      # 1 SQL dotaz
      .filter(TD.document_id.in_([d.id for d in all_docs]))
      .all()
  dists_by_doc = defaultdict(list)
  for d in all_dists:
      dists_by_doc[d.document_id].append(d)
  ```

### K2: Import vlastníků — destruktivní akce bez dostatečného potvrzení

- **Severity:** KRITICKÉ
- **Modul:** Import z Excelu
- **Pohled:** Error recovery
- **Problém:** Import vlastníků (sekce 1 na stránce `/vlastnici/import`) nahradí VŠECHNY stávající vlastníky v databázi. Varování je pouze žlutý box s textem „Import nahradí všechny stávající vlastníky v databázi." a tlačítko „Nahrát a zobrazit náhled". Chybí: (a) typický `data-confirm` modal s detailem co bude smazáno, (b) počet aktuálních vlastníků v upozornění, (c) požadavek na explicitní potvrzení (např. psaní „DELETE" jako na purge stránce).
- **Dopad:** Uživatel může nechtěně přijít o všechna ručně zadaná data vlastníků jedním kliknutím. Neexistuje undo.
- **Návrh:** (a) Přidat `data-confirm` na formulář s textem „Import smaže všech {N} vlastníků a nahradí je daty z Excelu. Pokračovat?", (b) Zobrazit aktuální počet vlastníků v upozornění, (c) Před importem automaticky vytvořit zálohu DB.
- **Kde v kódu:** `app/templates/owners/import.html:39-51`
- **Mockup:**
  ```
  Současný stav:
  ┌──────────────────────────────────────┐
  │ ⚠ Pozor: Import nahradí všechny     │
  │ stávající vlastníky v databázi.      │
  │                                      │
  │ [Vybrat soubor]  [Nahrát a náhled]  │
  └──────────────────────────────────────┘

  Navrhovaný stav:
  ┌──────────────────────────────────────┐
  │ ⚠ DESTRUKTIVNÍ AKCE                 │
  │ Import smaže všech 42 vlastníků     │
  │ a nahradí je daty z Excelu.          │
  │                                      │
  │ [Vybrat soubor]                      │
  │                                      │
  │ [Nahrát a náhled ← data-confirm]    │
  │                                      │
  │ Tip: Doporučujeme nejdříve zálohovat│
  │ v Administrace → Zálohy             │
  └──────────────────────────────────────┘
  ```

### K3: Tichá konverze nevalidních číselných vstupů na NULL

- **Severity:** KRITICKÉ
- **Modul:** Jednotky
- **Pohled:** Data quality
- **Problém:** Při vytváření/editaci jednotky se nevalidní číselné vstupy (LV, plocha, podíl SČD) tiše konvertují na `None` bez jakéhokoliv varování uživateli. Pokud uživatel zadá „abc" do pole Plocha, hodnota se uloží jako NULL a uživatel dostane zelenou flash zprávu „Jednotka vytvořena" — ale pole Plocha je prázdné.
- **Dopad:** Uživatel si myslí, že data uložil správně. Zjistí chybu až při kontrole nebo exportu.
- **Návrh:** (a) Validovat na straně klienta (`type="number"` s `min`/`max`), (b) Na serveru vrátit chybovou zprávu místo tiché konverze, (c) Minimálně flash warning „Neplatná hodnota plochy, pole bylo uloženo jako prázdné".
- **Kde v kódu:** `app/routers/units.py:81-98`
- **Mockup:**
  ```
  Současný stav (units.py:87-90):
  try:
      floor_area_float = float(floor_area.strip())
  except (ValueError, TypeError):
      floor_area_float = None     # ← tiše spolkne chybu

  Navrhovaný stav:
  try:
      floor_area_float = float(floor_area.strip())
  except (ValueError, TypeError):
      warnings.append(f"Neplatná plocha „{floor_area}" — pole nebylo uloženo")
      floor_area_float = None
  # ... po uložení:
  if warnings:
      flash_message = "; ".join(warnings)
      flash_type = "warning"
  ```

### K4: pdf.js načítán na každé stránce

- **Severity:** KRITICKÉ
- **Modul:** Celá aplikace
- **Pohled:** Performance analytik
- **Problém:** `pdf.min.js` (316 KB) je načítán v `base.html:17` na KAŽDÉ stránce aplikace, přestože PDF preview se používá pouze na stránce přiřazení (`matching.html`) v modulu Hromadné rozesílání. Na dashboardu, seznamu vlastníků, jednotkách, hlasování, nastavení — všude se zbytečně stahuje a parsuje 316 KB JavaScriptu.
- **Dopad:** Zpomalení prvního načtení aplikace o ~100-300ms (závisí na připojení). Na USB deployment s pomalým diskem je to výraznější.
- **Návrh:** Přesunout `<script src="pdf.min.js">` z `base.html` do šablon, které ho skutečně používají (`matching.html`, případně `send.html`). Alternativně použít lazy loading: `<script src="..." defer>` nebo dynamický `import()`.
- **Kde v kódu:** `app/templates/base.html:17`
- **Mockup:**
  ```
  Současný stav (base.html):
  <script src="https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js"></script>
  ← Načteno na VŠECH stránkách

  Navrhovaný stav:
  base.html: (odebrat řádek 17)
  matching.html: {% block extra_head %}
      <script src="...pdf.min.js"></script>
  {% endblock %}
  ```

### K5: Dashboard načítá všechny tax sessions bez limitu

- **Severity:** KRITICKÉ
- **Modul:** Přehled (Dashboard)
- **Pohled:** Performance analytik + Business analytik
- **Problém:** V `dashboard.py:125-129` se načítají VŠECHNY tax sessions bez limitu: `db.query(TaxSession).order_by(...).all()`. Po roce používání s desítkami sessions to zbytečně zatěžuje dashboard. Navíc se v Python loop (řádky 134-145) iteruje přes všechny sessions pro groupování — místo SQL GROUP BY.
- **Dopad:** S narůstajícím počtem sessions se zpomaluje načítání dashboardu.
- **Návrh:** Použít SQL agregaci `GROUP BY send_status` pro počty, a `DISTINCT ON` (nebo subquery) pro latest per status. Alternativně alespoň `.limit(100)`.
- **Kde v kódu:** `app/routers/dashboard.py:125-145`

---

## DŮLEŽITÉ

### D1: Snapshot warning bez jasné akce

- **Severity:** DŮLEŽITÉ
- **Modul:** Hlasování
- **Pohled:** Běžný uživatel
- **Problém:** Žlutý banner `snapshot_warning` (v `_voting_header.html:9-16`) zobrazuje text „Zvažte přegenerování lístků" — ale neobsahuje tlačítko pro přímé přegenerování. Uživatel musí vědět, kde tuto akci provést (stav draft → generovat, ale aktivní hlasování nelze snadno přegenerovat).
- **Dopad:** Uživatel vidí varování, ale neví co konkrétně s ním dělat.
- **Návrh:** Přidat do varování odkaz/tlačítko na akci přegenerování (pokud je technicky možné), nebo alespoň podrobnější vysvětlení co se změnilo a jaký je doporučený postup.
- **Kde v kódu:** `app/templates/voting/_voting_header.html:9-16`

### D2: Filtrační bubliny vlastníků — 3 řady bez hierarchie

- **Severity:** DŮLEŽITÉ
- **Modul:** Vlastníci
- **Pohled:** UI/UX designer
- **Problém:** Stránka vlastníků má 3 řady filtračních bublin: (1) typ osoby + kontakt + stav, (2) typ vlastnictví, (3) sekce. To je 12-15 bublin najednou. Kombinace filtrů není vizuálně jasná — není zřejmé, že typ + kontakt + sekce se kombinují AND logicky.
- **Dopad:** Nový uživatel je zahlcen množstvím filtrů. Obtížně identifikuje aktivní kombinaci filtrů.
- **Návrh:** (a) Seskupit filtry do `<details>` sekcí (typ, kontakt, vlastnictví, sekce) s počty, (b) Zobrazit aktivní filtry jako chips/tagy nad tabulkou s možností „×" pro odebrání, (c) Přidat „Zrušit filtry" tlačítko.
- **Kde v kódu:** `app/templates/owners/list.html:67-132`
- **Mockup:**
  ```
  Současný stav:
  ┌─────────────────────────────────────────┐
  │ [Vše] [Fyzické] [Právní] [✉✓] [✉✗] ...│  ← řada 1
  │ [Vše] [SJM 5] [Vl.právo 10] [Bezp 3]  │  ← řada 2
  │ [Sekce: ▼ dropdown]                     │  ← řada 3
  └─────────────────────────────────────────┘

  Navrhovaný stav:
  ┌─────────────────────────────────────────┐
  │ Aktivní filtry: [Fyzická os. ×] [S ✉ ×]│
  │ [Typ ▾] [Kontakt ▾] [Vlastnictví ▾]    │
  └─────────────────────────────────────────┘
  ```

### D3: Email validace — tiché nastavení NULL bez zprávy

- **Severity:** DŮLEŽITÉ
- **Modul:** Vlastníci
- **Pohled:** Error recovery
- **Problém:** Při vytvoření vlastníka s nevalidním emailem router uloží vlastníka bez emailu a zobrazí warning „Vlastník vytvořen, ale zadaný email měl neplatný formát a nebyl uložen." (owners.py:866). To je lepší než tiché zahodení, ale stále se data ztrácí. Při inline editaci emailu na detailu vlastníka není jasné, zda se validace chová stejně.
- **Dopad:** Uživatel může zadat email s překlepem a nevšimnout si warning zprávy (zejména pokud neprojde viewportem).
- **Návrh:** (a) Přidat `type="email"` na input pro client-side validaci, (b) Při serverové validační chybě vrátit formulář s vyplněnými daty a zvýrazněným polem, místo uložení bez emailu.
- **Kde v kódu:** `app/routers/owners.py:864-867`

### D4: Nekonzistentní empty states

- **Severity:** DŮLEŽITÉ
- **Modul:** Celá aplikace
- **Pohled:** UI/UX designer
- **Problém:** Prázdné stavy (žádná data) jsou řešeny nekonzistentně napříč modulem:
  - Některé mají CTA: `units/list.html:168` — „Žádné jednotky. Importujte data z Excelu" s odkazem
  - Některé jen text: `voting/detail.html:76` — „Přidejte body hlasování" bez tlačítka
  - Některé minimální: `tax/index.html:127` — „Žádné rozesílání v tomto stavu." bez akce
  - Dashboard aktivita: „Žádná aktivita." bez náznaku co dělat
- **Dopad:** Při prvním použití aplikace uživatel neví jak začít, protože prázdné stránky neposkytují vodítko.
- **Návrh:** Zavést jednotný vzor empty state: ikona + text + primární CTA tlačítko. Např.: „Zatím žádné hlasování. [+ Vytvořit první hlasování]"
- **Kde v kódu:** Více souborů (viz seznam výše)

### D5: Chybějící loading state na export tlačítkách

- **Severity:** DŮLEŽITÉ
- **Modul:** Vlastníci, Jednotky, Hlasování
- **Pohled:** Běžný uživatel
- **Problém:** Export tlačítka (Excel, CSV) na stránce vlastníků mají inline `onclick` handler: `this.textContent='Generuji…';this.classList.add('opacity-50')`. Ale: (a) po dokončení exportu se text nevrátí zpět (stránka se nerefreshne protože je to `hx-boost="false"` download), (b) tlačítko zůstane „Generuji…" + opacity navždy, (c) uživatel nemůže export spustit znovu bez refreshe.
- **Dopad:** Po prvním exportu vypadá tlačítko „zaseknuté". Uživatel musí refreshnout stránku.
- **Návrh:** Použít temporary state: po kliknutí změnit text na 3 sekundy, pak vrátit zpět. Nebo lépe: otevřít download v novém tabu (`target="_blank"`).
- **Kde v kódu:** `app/templates/owners/list.html:47-51`, `app/templates/voting/_voting_header.html:46-51`
- **Mockup:**
  ```
  Současný stav:
  <a onclick="this.textContent='Generuji…';this.classList.add('opacity-50')">
  ← Po kliknutí: text se změní, ale nikdy se nevrátí

  Navrhovaný stav:
  <a onclick="var btn=this;btn.textContent='Generuji…';
     btn.classList.add('opacity-50');
     setTimeout(function(){btn.textContent='↓ Excel';
     btn.classList.remove('opacity-50')},3000)">
  ```

### D6: Test email — chybí client-side validace emailu

- **Severity:** DŮLEŽITÉ
- **Modul:** Hromadné rozesílání (send)
- **Pohled:** Error recovery
- **Problém:** Na stránce rozesílky (`send.html`) je pole pro testovací email. Tlačítko „Odeslat testovací email" je aktivní i s prázdným nebo nevalidním emailem. Server sice validuje, ale uživatel musí čekat na server response aby zjistil chybu.
- **Dopad:** Zbytečné server roundtripy při zjevně nevalidním vstupu.
- **Návrh:** (a) Přidat `type="email"` + `required` na input, (b) Disable tlačítko pokud je pole prázdné, (c) Jednoduchá JS regex validace před odesláním.
- **Kde v kódu:** `app/templates/tax/send.html` (sekce test email)

### D7: Rozesílka — odesílání stránka příliš minimalistická

- **Severity:** DŮLEŽITÉ
- **Modul:** Hromadné rozesílání
- **Pohled:** UI/UX designer
- **Problém:** Stránka `sending.html` během odesílání zobrazuje pouze jednoduchou progress oblast s HTMX pollingem. Chybí: (a) vizuální progress bar s procentem, (b) odhadovaný čas dokončení, (c) seznam posledních odeslaných emailů v reálném čase, (d) tlačítko pro pozastavení přímo na progress stránce.
- **Dopad:** Uživatel neví kolik času zbývá a nemá kontrolu nad procesem.
- **Návrh:** Přidat vizuální progress bar (N z M), ETA na základě průměrného času na email, a tlačítko Pozastavit/Pokračovat.
- **Kde v kódu:** `app/templates/tax/sending.html:15-22`
- **Mockup:**
  ```
  Současný stav:
  ┌──────────────────────────┐
  │ [HTMX progress partial]  │
  └──────────────────────────┘

  Navrhovaný stav:
  ┌──────────────────────────────────┐
  │ Odesílání emailů                 │
  │ ████████████░░░░░░ 67% (20/30)   │
  │ Odhadovaný čas: ~2 min           │
  │                                  │
  │ Poslední: ✓ Novák (10:23:45)     │
  │           ✓ Dvořák (10:23:40)    │
  │                                  │
  │ [Pozastavit]  [Zpět na rozesílku]│
  └──────────────────────────────────┘
  ```

### D8: Kontroly — dvě nezávislé sekce na jedné stránce

- **Severity:** DŮLEŽITÉ
- **Modul:** Kontroly (sync)
- **Pohled:** Business analytik
- **Problém:** Stránka `/kontroly` obsahuje dvě nezávislé sekce (Kontrola vlastníků a Kontrola podílů), každá se svým vlastním uploadem, historií a search/sort. Obě sekce sdílejí jednu URL, ale mají oddělené query parametry (`sync_q`, `sc_q`, `sync_sort`, `sc_sort`). To komplikuje navigaci — bookmarking a back URL musí zachytit stav obou sekcí.
- **Dopad:** Při použití jedné sekce se stav druhé může resetovat. Back URL navigace je složitá.
- **Návrh:** Zvážit rozdělení na dva samostatné podstránky s tabem/bublinami přepínání, nebo alespoň přidat kotvy (`#kontrola-vlastniku`, `#kontrola-podilu`) pro přímý link.
- **Kde v kódu:** `app/templates/sync/index.html`, `app/routers/sync.py`

### D9: Hlasování — „Generovat lístky" bez výchozího potvrzení počtu

- **Severity:** DŮLEŽITÉ
- **Modul:** Hlasování
- **Pohled:** Běžný uživatel
- **Problém:** Potvrzovací dialog pro generování lístků (`data-confirm` v `_voting_header.html:33`) říká „Vygenerovat lístky pro všechny vlastníky?" — ale neuvádí KOLIK vlastníků/lístků bude vygenerováno. Uživatel neví zda to bude 5 nebo 500 lístků.
- **Dopad:** Uživatel nemá dostatek informací pro informované rozhodnutí.
- **Návrh:** Doplnit do confirm dialogu počet: „Vygenerovat {N} lístků pro {M} vlastníků s celkem {V} hlasy?"
- **Kde v kódu:** `app/templates/voting/_voting_header.html:32-37`

### D10: Neodevzdané lístky — chybí hromadná akce

- **Severity:** DŮLEŽITÉ
- **Modul:** Hlasování
- **Pohled:** Business analytik
- **Problém:** Stránka neodevzdaných lístků (`not_submitted.html`) zobrazuje seznam vlastníků, kteří neodevzdali lístek. Ale chybí jakákoliv hromadná akce — např. „Odeslat upomínku emailem" nebo „Exportovat seznam". Pro rozeslání upomínek musí uživatel ručně kopírovat emaily.
- **Dopad:** Ruční práce při rozesílání upomínek neodevzdaným vlastníkům.
- **Návrh:** Přidat tlačítko „Export neodevzdaných" (Excel/CSV se jmény a emaily) a v budoucnu možnost hromadného emailu.
- **Kde v kódu:** `app/templates/voting/not_submitted.html`

### D11: Administrace — purge bez preview co bude smazáno

- **Severity:** DŮLEŽITÉ
- **Modul:** Administrace (purge)
- **Pohled:** Error recovery
- **Problém:** Stránka smazání dat (`purge.html`) zobrazuje checkbox grid s kategoriemi a počty záznamů. Po zaškrtnutí a psaní „DELETE" se data smažou. Chybí: (a) preview/potvrzovací krok ukazující CO konkrétně bude smazáno (které votingy, které sessions), (b) informace o kaskádových závislostech (smazání vlastníků → smaže i hlasování).
- **Dopad:** Uživatel může nechtěně smazat více dat než zamýšlel kvůli kaskádovým závislostem.
- **Návrh:** (a) Zobrazit kaskádové upozornění viditelně (ne jen jako hidden element), (b) Po zaškrtnutí „Vlastníci" okamžitě zobrazit červený banner s výpisem co bude kaskádově smazáno, (c) Přidat mezikrok s preview.
- **Kde v kódu:** `app/templates/administration/purge.html:42-44`
- **Mockup:**
  ```
  Současný stav:
  ☑ Vlastníci (42)
    <p class="hidden">Automaticky smaže i hlasování...</p>
  ← Kaskádové upozornění je SKRYTÉ (hidden)

  Navrhovaný stav:
  ☑ Vlastníci (42)
    ⚠ Pozor: Smaže také 3 hlasování,
    2 rozesílky a všechny sync záznamy
  ← Vždy viditelné po zaškrtnutí
  ```

### D12: Rozesílka send — checkbox stav v sessionStorage

- **Severity:** DŮLEŽITÉ
- **Modul:** Hromadné rozesílání
- **Pohled:** Error recovery
- **Problém:** Checkboxy příjemců na send stránce se ukládají do `sessionStorage` (v `app.js`). Pokud uživatel otevře stránku v novém tabu nebo po zavření a znovuotevření prohlížeče, stav checkboxů se ztratí. Navíc pokud se změní příjemci (přidání/odebrání dokumentu), uložený snapshot v `sessionStorage` může být nekonzistentní s aktuálním stavem.
- **Dopad:** Potenciální nekonzistence mezi zobrazeným a skutečným výběrem příjemců.
- **Návrh:** (a) Přidat validaci snapshotu proti aktuálním datům při načtení, (b) Zobrazit upozornění pokud se snapshot neshoduje, (c) Zvážit server-side ukládání výběru.
- **Kde v kódu:** `app/static/js/app.js` (funkce pro checkbox persistence)

### D13: Flash zprávy — dva různé systémy

- **Severity:** DŮLEŽITÉ
- **Modul:** Celá aplikace
- **Pohled:** UI/UX designer
- **Problém:** Aplikace používá dva různé systémy flash zpráv: (a) Globální v `base.html:135` s `data-auto-dismiss` — zpracovávaný v `app.js`, (b) Inline v jednotlivých šablonách (např. `send.html:69-77`) s vlastním `setTimeout` skriptem. Globální systém má 5s timeout, inline na send stránce má 4s timeout. Vizuální styl je konzistentní, ale chování ne.
- **Dopad:** Nekonzistentní UX — některé flash zprávy zmizí za 4s, jiné za 5s. Údržba dvou systémů.
- **Návrh:** Sjednotit na jeden systém — buď vše přes globální `data-auto-dismiss` v `base.html`, nebo vše přes inline skripty. Doporučuji globální systém.
- **Kde v kódu:** `app/templates/base.html:135`, `app/templates/tax/send.html:76`, `app/static/js/app.js`

---

## DROBNÉ

### Dr1: Sidebar — malý a těžko citelný na mobilních zařízeních

- **Severity:** DROBNÉ
- **Modul:** Celá aplikace
- **Pohled:** UI/UX designer
- **Problém:** Sidebar je fixní šířka `w-44` (176px) bez responsive breakpointů. Na mobilním zařízení zabírá velkou část obrazovky a nelze ho schovat. Aplikace je primárně desktopová, ale i tak by měla být použitelná na tabletu.
- **Dopad:** Na zařízeních s menší obrazovkou je sidebar nepřiměřeně velký.
- **Návrh:** Přidat hamburger menu pro menší obrazovky s `lg:hidden`/`lg:block` breakpointy.
- **Kde v kódu:** `app/templates/base.html:22`

### Dr2: Hlasování — Export pro ACTIVE hlasování bez upozornění na průběžnost

- **Severity:** DROBNÉ
- **Modul:** Hlasování
- **Pohled:** Běžný uživatel
- **Problém:** Export je dostupný i pro aktivní hlasování (opraveno z předchozího reportu kde nebyl). Ale tlačítko „Exportovat do Excelu" na aktivním hlasování neindikuje, že jde o průběžné výsledky. Může vést k záměně s finálními výsledky.
- **Dopad:** Uživatel může považovat průběžný export za finální.
- **Návrh:** Přejmenovat tlačítko na „Exportovat průběžné výsledky" a/nebo přidat tooltip/upozornění v exportovaném souboru.
- **Kde v kódu:** `app/templates/voting/_voting_header.html:46-51`

### Dr3: Podíl SČD — chybí tooltip s vysvětlením

- **Severity:** DROBNÉ
- **Modul:** Vlastníci, Jednotky
- **Pohled:** Běžný uživatel
- **Problém:** Sloupec „Podíl SČD" v tabulkách vlastníků a jednotek používá odborný termín bez vysvětlení. Nový uživatel nemusí vědět, co „SČD" znamená (spoluvlastnický podíl na společných částech domu).
- **Dopad:** Zmatenost u nových uživatelů.
- **Návrh:** Přidat `title` atribut na hlavičku sloupce: „Spoluvlastnický podíl na společných částech domu".
- **Kde v kódu:** Hlavičky tabulek v `owners/list.html`, `units/list.html`

### Dr4: Vytvoření hlasování — tlačítko „Vytvořit" skryté dokud se nevyplní název

- **Severity:** DROBNÉ
- **Modul:** Hlasování
- **Pohled:** UI/UX designer
- **Problém:** Tlačítko „Vytvořit hlasování" na stránce `create.html` je `hidden` a zobrazí se teprve po vyplnění názvu (řádek 51: `oninput="...toggle('hidden', !this.value.trim())"`). To je dobrý pattern, ale uživatel který formulář vidí poprvé netuší, že tlačítko existuje — vidí pouze „Zrušit".
- **Dopad:** Mírný zmatek u nových uživatelů.
- **Návrh:** Zobrazit tlačítko vždy, ale ve stavu `disabled` s `opacity-50` dokud není název vyplněn.
- **Kde v kódu:** `app/templates/voting/create.html:17-18`

### Dr5: Dashboard — stat karty s vnořenými odkazy (a11y problém)

- **Severity:** DROBNÉ
- **Modul:** Dashboard
- **Pohled:** UI/UX designer
- **Problém:** Karta Hlasování a Rozesílání na dashboardu mají `<div>` wrapper s hlavním `<a>` a vnořenými `<a>` linky uvnitř. Vnořené `<a>` v `<a>` je HTML standard violation. Řešeno pomocí `onclick="event.stopPropagation()"`, ale screen readery mohou mít problémy.
- **Dopad:** Potenciální a11y problémy.
- **Návrh:** Přestrukturovat na `<div>` wrapper bez vnějšího `<a>`, použít CSS pro hover efekt na celé kartě.
- **Kde v kódu:** `app/templates/dashboard.html:49-77`

### Dr6: Import hlasování — klient-side sorting bez indikátoru

- **Severity:** DROBNÉ
- **Modul:** Hlasování (import preview)
- **Pohled:** UI/UX designer
- **Problém:** Import preview stránka (`import_preview.html`) používá client-side filtrování a řazení přes JavaScript. Ale při filtrování (klik na bublinu) není žádný loading indikátor ani animace — data se jen přefiltrují. Na velké datové sadě to může být okamžité, ale u menších sad to vypadá, že se „nic nestalo".
- **Dopad:** Minimální — data jsou obvykle malá. Ale vizuální feedback by pomohl.
- **Návrh:** Přidat krátký fade/transition efekt při přepnutí filtru.
- **Kde v kódu:** `app/templates/voting/import_preview.html:37-71`

### Dr7: Nastavení — SMTP sekce bez viditelného stavu

- **Severity:** DROBNÉ
- **Modul:** Nastavení
- **Pohled:** Běžný uživatel
- **Problém:** SMTP konfigurace na stránce Nastavení je includovaná jako partial (`smtp_info.html`). Pokud SMTP není nakonfigurovaný, uživatel nevidí jasné upozornění, že emaily nebudou fungovat. Stav konfigurace by měl být viditelný na první pohled.
- **Dopad:** Uživatel může zkusit rozeslat emaily bez nakonfigurovaného SMTP a netuší proč to nefunguje.
- **Návrh:** Přidat jasný badge vedle nadpisu „Nastavení": zelený „SMTP ✓ nakonfigurováno" nebo červený „SMTP ✗ nenastaveno".
- **Kde v kódu:** `app/templates/settings.html:10-14`

### Dr8: Formátování dat — nekonzistentní formát data/času

- **Severity:** DROBNÉ
- **Modul:** Celá aplikace
- **Pohled:** UI/UX designer
- **Problém:** Aplikace zobrazuje data v různých formátech: `dd.mm.YYYY` (česky správné) se používá většinově, ale některé timestamp sloupce zobrazují i čas v různých formátech (`HH:MM` vs `HH:MM:SS`). Dashboard aktivita table zobrazuje jen datum bez času u některých položek.
- **Dopad:** Vizuální nekonzistence, minimální funkční dopad.
- **Návrh:** Sjednotit na `dd.mm.YYYY HH:MM` pro timestampy, `dd.mm.YYYY` pro data. Definovat jako Jinja2 filtr.
- **Kde v kódu:** Různé šablony

### Dr9: Administrace index — kartový grid bez jasné hierachie

- **Severity:** DROBNÉ
- **Modul:** Administrace
- **Pohled:** UI/UX designer
- **Problém:** Administrační stránka zobrazuje karty v rovnocenném gridu (2×4): SVJ Info, Číselníky, Zálohy, Export, Hromadné úpravy, Duplicity, Smazat data. „Smazat data" je destruktivní akce zobrazená jako rovnocenná karta vedle „SVJ Info". Chybí vizuální odlišení nebezpečných akcí.
- **Dopad:** Vizuální rovnocennost bezpečných a destruktivních akcí.
- **Návrh:** Oddělit „Smazat data" do vlastní sekce „Nebezpečná zóna" s červeným okrajem, nebo přidat červenou barvu na kartu.
- **Kde v kódu:** `app/templates/administration/index.html`

### Dr10: Rozesílka — back URL z send stránky

- **Severity:** DROBNÉ
- **Modul:** Hromadné rozesílání
- **Pohled:** Běžný uživatel
- **Problém:** Stránka send.html (`/dane/{id}/rozeslat`) má zpět odkaz „Zpět na přiřazení" (řádek 8) — ale uživatel může přijít z jiné stránky (např. ze seznamu rozesílek). Back URL se sice propaguje, ale default fallback je vždy přiřazení, ne seznam.
- **Dopad:** Při přímém přístupu na URL (bookmark, sdílení) je zpětná navigace neoptimální.
- **Návrh:** Dynamický back label podle skutečné předchozí stránky.
- **Kde v kódu:** `app/templates/tax/send.html:8`

### Dr11: Vlastníci detail — inline edit bez escape klávesy

- **Severity:** DROBNÉ
- **Modul:** Vlastníci
- **Pohled:** Performance analytik
- **Problém:** Inline edit formuláře na detailu vlastníka (načtené přes HTMX) nemají handler pro klávesu Escape pro zrušení editace. Uživatel musí kliknout myší na „Zrušit".
- **Dopad:** Méně efektivní ovládání pro pokročilé uživatele.
- **Návrh:** Přidat `onkeydown="if(event.key==='Escape')..."` na formulářové kontejnery.
- **Kde v kódu:** HTMX partials pro inline edit

### Dr12: Hlavičky tabulek — nekonzistentní uppercase

- **Severity:** DROBNÉ
- **Modul:** Celá aplikace
- **Pohled:** UI/UX designer
- **Problém:** Některé tabulky mají hlavičky v `uppercase` (přes `text-xs font-medium uppercase`), jiné v normálním case. Např. ballots tabulka v hlasování používá uppercase, ale detail vlastníka ne.
- **Dopad:** Vizuální nekonzistence, minimální funkční dopad.
- **Návrh:** Sjednotit na `uppercase text-xs font-medium text-gray-500` pro všechny datové tabulky.
- **Kde v kódu:** Různé šablony

### Dr13: Rozesílka matching — potvrzení přiřazení bez batch operace na filtrované výsledky

- **Severity:** DROBNÉ
- **Modul:** Hromadné rozesílání
- **Pohled:** Business analytik
- **Problém:** Na stránce přiřazení (`matching.html`) lze potvrdit přiřazení individuálně nebo hromadně přes checkboxy. Ale hromadná akce „Potvrdit vybrané" nevyužívá aktivní filtr — vybírá se ručně. Bylo by užitečné „Potvrdit všechny zobrazené/filtrované" jedním kliknutím.
- **Dopad:** Více kliknutí při potvrzování velkého počtu automaticky párovaných dokumentů.
- **Návrh:** Přidat tlačítko „Potvrdit všechny zobrazené" které aplikuje potvrzení na aktuálně filtrované výsledky.
- **Kde v kódu:** `app/templates/tax/matching.html`

### Dr14: Hlasování index — smazání uzavřeného hlasování vyžaduje „DELETE" ale ne u konceptu

- **Severity:** DROBNÉ
- **Modul:** Hlasování
- **Pohled:** Error recovery
- **Problém:** Smazání uzavřeného hlasování vyžaduje psaní „DELETE" do dialogu. Smazání konceptu hlasování vyžaduje pouze potvrzení (`data-confirm`). Nekonzistence v bezpečnostní úrovni — koncept s vygenerovanými lístky by měl mít alespoň potvrzení s počtem lístků.
- **Dopad:** Minimální — koncepty typicky nemají lístky. Ale konzistence by byla lepší.
- **Návrh:** Pro koncepty s 0 lístky: jednoduchý `data-confirm`. Pro koncepty s lístky: `data-confirm` s počtem lístků.
- **Kde v kódu:** `app/templates/voting/index.html`

---

## Top 5 doporučení (podle dopadu)

| # | Návrh | Dopad | Složitost | Priorita |
|---|-------|-------|-----------|----------|
| 1 | Přesunout pdf.js z base.html do šablon kde se používá (K4) | Vysoký — 316KB méně na každé stránce | Nízká | HNED |
| 2 | Batch query místo N+1 v tax matching email update (K1) | Vysoký — dramatické zrychlení u velkých sessions | Střední | HNED |
| 3 | Import vlastníků: přidat data-confirm + počet existujících (K2) | Vysoký — prevence ztráty dat | Nízká | HNED |
| 4 | Validace číselných vstupů — warning místo tichého NULL (K3) | Střední — prevence datových problémů | Nízká | BRZY |
| 5 | Dashboard: SQL agregace místo Python loop pro tax sessions (K5) | Střední — škáluje s počtem sessions | Střední | BRZY |

---

## Quick wins (nízká složitost, okamžitý efekt)

- [ ] Přesunout `<script src="pdf.min.js">` z `base.html` do `matching.html` (K4) — 1 řádek přesun
- [ ] Přidat `data-confirm` na import vlastníků formulář (K2) — 1 atribut
- [ ] Přidat `title` tooltip na sloupec „Podíl SČD" ve všech tabulkách (Dr3)
- [ ] Export tlačítka: vrátit text po 3s timeoutu (D5) — 2 řádky JS
- [ ] Sjednotit flash auto-dismiss timeout na 5s všude (D13)
- [ ] Přidat `type="email"` na email input pole (D3, D6)
- [ ] Purge kaskádové upozornění: odstranit `class="hidden"` (D11) — 1 atribut
- [ ] Disabled stav na „Vytvořit hlasování" tlačítko místo hidden (Dr4)
- [ ] Přidat „Exportovat" tlačítko na stránku neodevzdaných lístků (D10)
- [ ] Dashboard: přidat `.limit(50)` na tax sessions query (K5) — 1 řádek
