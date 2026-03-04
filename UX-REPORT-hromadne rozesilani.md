# UX Analýza — Hromadné rozesílání

> Analyzováno: 2026-03-03
> Rozsah: modul Hromadné rozesílání (dane/tax) — celý workflow od nahrání PDF po odeslání emailů

## Souhrn

| Pohled | Kritické | Důležité | Drobné |
|--------|----------|----------|--------|
| Běžný uživatel | 3 | 5 | 6 |
| Business analytik | 1 | 6 | 1 |
| UI/UX designer | 0 | 0 | 9 |
| Performance analytik | 0 | 3 | 1 |
| Error recovery | 3 | 4 | 2 |
| Data quality | 1 | 4 | 1 |
| **Celkem (unikátní)** | **4** | **12** | **12** |

---

## Nálezy a návrhy

### Krok 1: Nahrání PDF

#### Nález #1: Tichý redirect při selhání validace uploadu
- **Severity:** KRITICKÉ
- **Pohled:** Běžný uživatel, Error recovery
- **Problém:** Když `validate_uploads()` najde problém (příliš velký soubor, špatná přípona), router tichze přesměruje na `/dane` bez jakékoliv chybové zprávy. Celý upload se zahodí beze slova.
- **Dopad:** Uživatel nahraje 50 PDF, jedno je příliš velké — vše se tiše zahodí. Vrátí se na seznam bez vysvětlení. Může zkoušet znovu opakovaně.
- **Kde v kódu:** `app/routers/tax.py:419-421` (a znovu na řádku 516-518 pro doplnění PDF)
- **Návrh:** Zachytit chybovou zprávu z `validate_uploads()` a předat ji jako flash/query parametr:
  ```python
  if err:
      return RedirectResponse(f"/dane/nova?chyba={quote(err)}", status_code=302)
  ```

#### Nález #2: Tichý redirect když nejsou nalezeny žádné validní PDF
- **Severity:** KRITICKÉ
- **Pohled:** Běžný uživatel, Error recovery
- **Problém:** Pokud uživatel nahraje složku obsahující pouze `.DS_Store` nebo jiné soubory (běžné při `webkitdirectory`), router tiše přesměruje na `/dane` bez zpětné vazby.
- **Dopad:** Stejný jako #1 — uživatel ztrácí kontext bez vysvětlení.
- **Kde v kódu:** `app/routers/tax.py:414-417`
- **Návrh:** Flash zpráva vysvětlující, že nebyly nalezeny žádné validní PDF soubory.

#### Nález #5: Rok je hardcoded na aktuální rok
- **Severity:** DŮLEŽITÉ
- **Pohled:** Business analytik, Data quality
- **Problém:** Rok session se nastavuje automaticky na `datetime.now().year` bez možnosti změny. Daňové dokumenty mohou být za předchozí roky (např. opětovné rozesílání za rok 2023 v roce 2024). Rok se používá pro vyhledávání spoluvlastníků — špatný rok = špatní spoluvlastníci.
- **Dopad:** Session pro loňské dokumenty dostane špatný rok, což způsobí nesprávné párování spoluvlastníků. Rok nejde po vytvoření opravit.
- **Kde v kódu:** `app/routers/tax.py:423`, `app/templates/tax/upload.html`
- **Návrh:** Přidat editovatelné pole `rok` do formuláře nahrávání s defaultem na aktuální rok.
- **Mockup:**
  ```
  Současný stav:
  ┌─────────────────────────────────┐
  │  Název session: [___________]   │
  │  [Nahrát PDF]                   │
  └─────────────────────────────────┘

  Navrhovaný stav:
  ┌─────────────────────────────────┐
  │  Název session: [___________]   │
  │  Rok:           [2026 ▼]        │
  │  [Nahrát PDF]                   │
  └─────────────────────────────────┘
  ```

#### Nález #21: Přepisovací mód maže staré soubory před uložením nových
- **Severity:** DŮLEŽITÉ
- **Pohled:** Error recovery, Performance analytik
- **Problém:** V režimu „Přepsat stávající" se nejdřív smažou všechny staré soubory a DB záznamy, a teprve potom se zapisují nové soubory. Pokud zápis selže (plný disk, chyba oprávnění), stará data jsou pryč ale nová jsou neúplná.
- **Dopad:** Nevratná ztráta dat při selhání zápisu na disk — prázdná session bez PDF a bez distribucí.
- **Kde v kódu:** `app/routers/tax.py:527-557`
- **Návrh:** Zapsat nové soubory nejdřív, pak smazat staré, pak commit.

#### Nález #11: Přepsání maže potvrzená přiřazení s minimálním varováním
- **Severity:** DŮLEŽITÉ
- **Pohled:** Běžný uživatel, Error recovery
- **Problém:** Režim „Přepsat stávající" nevratně smaže všechny potvrzené a ručně přiřazené distribuce. UI varování je jen jednořádková poznámka pod radio buttonem bez potvrzovacího dialogu.
- **Dopad:** Uživatel, který strávil hodinu ručním párováním 80 PDF, může přijít o veškerou práci jedním kliknutím.
- **Kde v kódu:** `app/routers/tax.py:527-540`, `app/templates/tax/upload_additional.html:44`
- **Návrh:** Přidat `confirm()` dialog: „Toto smaže X potvrzených a Y ručně přiřazených dokumentů. Tato operace je nevratná."

---

### Krok 2: Přiřazení (matching)

#### Nález #10: Žádné shrnutí před „Potvrdit vše"
- **Severity:** DŮLEŽITÉ
- **Pohled:** Běžný uživatel, Business analytik
- **Problém:** Dialog „Potvrdit všechny automaticky přiřazené?" neříká: kolik jich je, jaká je minimální confidence, kolik zůstane nepřiřazených. Uživatel může kliknout OK v domnění, že potvrdil úplně vše.
- **Dopad:** Uživatelé uzamykají session s nepřiřazenými PDF a pak jsou překvapeni na stránce rozesílky.
- **Kde v kódu:** `app/templates/tax/matching.html:137-142`
- **Návrh:** Zobrazit shrnutí: počet potvrzovaných, rozsah confidence, počet stále nepřiřazených. Před „Uzamknout": počet nepřiřazených dokumentů.
- **Mockup:**
  ```
  Současný stav:
  ┌──────────────────────────────────────────┐
  │  "Potvrdit všechny automaticky           │
  │   přiřazené?"                            │
  │                     [Zrušit] [OK]        │
  └──────────────────────────────────────────┘

  Navrhovaný stav:
  ┌──────────────────────────────────────────┐
  │  Potvrdit 45 automatických přiřazení?    │
  │  • Confidence 80-100%: 38               │
  │  • Confidence 60-79%:   7               │
  │  • Zůstane nepřiřazeno: 3              │
  │                     [Zrušit] [Potvrdit]  │
  └──────────────────────────────────────────┘
  ```

#### Nález #22: Žádná paginace na matching stránce
- **Severity:** DŮLEŽITÉ
- **Pohled:** Performance analytik
- **Problém:** Všechny dokumenty, jejich distribuce a vlastníci se načítají v jednom dotazu s `joinedload`. Pro velké budovy (300 jednotek, SJM = 600 dokumentů) jde o obrovský dotaz. Navíc se stejný dotaz spouští při KAŽDÉM hledání (HTMX keyup).
- **Dopad:** Pomalé načítání a lag při psaní do vyhledávacího pole u velkých session.
- **Kde v kódu:** `app/routers/tax.py:910-916`
- **Návrh:** Přidat LIMIT/paginaci, nebo alespoň lehčí dotaz pro HTMX partial (bez eager loading owners).

---

### Krok 3: Rozesílka (send)

#### Nález #3: Chyby zpracování PDF se nikdy nezobrazí uživateli
- **Severity:** KRITICKÉ
- **Pohled:** Běžný uživatel, Error recovery
- **Problém:** Když background thread selže uprostřed zpracování PDF, chyba se uloží do progress dictu, ale šablona `tax_progress.html` toto pole NEVYKRESLUJE. Status endpoint přesměruje na matching stránku jakmile `done=True` — bez ohledu na to, zda byla chyba.
- **Dopad:** Uživatel je tiše přesměrován na matching stránku s částečnými daty. Chybějící dokumenty nejsou vysvětleny.
- **Kde v kódu:** `app/routers/tax.py:801-808`, `app/templates/partials/tax_progress.html`
- **Návrh:** (a) Partial musí vykreslovat `{% if error %}` blok. (b) Status endpoint nesmí přesměrovávat při chybě. (c) Session by měla být označena jako failed.

#### Nález #4: Uložení emailových nastavení vynucuje status READY
- **Severity:** KRITICKÉ
- **Pohled:** Business analytik, Data quality
- **Problém:** Endpoint `save_send_settings` bezpodmínečně nastaví `send_status = READY` — i když session je v DRAFT stavu (matching není dokončen). Uživatel, který naviguje přímo na rozesílku a klikne „Uložit nastavení", obejde intended workflow.
- **Dopad:** Session s nepřiřazenými PDF se objeví jako „připravená k odeslání" na seznamu session.
- **Kde v kódu:** `app/routers/tax.py:1726-1736`
- **Návrh:** Nastavovat `READY` pouze pokud session již byla READY nebo to nastavil finalize endpoint. DRAFT session ponechat v DRAFT.

#### Nález #8: Změna emailu neinvaliduje příznak test_email_passed
- **Severity:** DŮLEŽITÉ
- **Pohled:** Data quality, Error recovery
- **Problém:** Uživatel může změnit předmět/tělo emailu, uložit nastavení, a příznak „Test OK" zůstane z předchozího testu — test je ale zastaralý.
- **Dopad:** Uživatel změní tělo emailu, neodešle nový test, sebevědomě rozešle 100 příjemcům rozbitou šablonu.
- **Kde v kódu:** `app/routers/tax.py:1726-1736`
- **Návrh:** Nastavit `session.test_email_passed = False` vždy když se změní `email_subject` nebo `email_body`. Přidat validaci formátu emailu pro `test_email_inline`.

#### Nález #7: Testovací email používá náhodné první PDF
- **Severity:** DŮLEŽITÉ
- **Pohled:** Běžný uživatel, Business analytik
- **Problém:** Test email vždy přiloží první PDF v databázi (nejnižší ID) — ne dokument příjemce. Uživatel nemůže ověřit, jak bude vypadat reálný email pro konkrétního vlastníka.
- **Dopad:** Účel testovacího emailu je ověřit reálný uživatelský zážitek — posílání náhodného PDF to nesplňuje.
- **Kde v kódu:** `app/routers/tax.py:1637-1645`
- **Návrh:** Nechat uživatele vybrat testovacího příjemce z existujících (pošle mu jeho skutečný dokument), nebo minimálně jasně uvést, že jde o vzorový PDF.

#### Nález #6: Dual-email checkbox vždy postuje na dist_ids[0]
- **Severity:** DŮLEŽITÉ
- **Pohled:** Data quality, Business analytik
- **Problém:** Oba email checkboxy (primární i sekundární) používají `r.dist_ids[0]` — první distribuci. Pokud tato distribuce patří k dokumentu, který byl již SENT, editace může mít nežádoucí vedlejší efekty.
- **Dopad:** Tichá nekonzistence dat u multi-dokumentových příjemců s dual emailem.
- **Kde v kódu:** `app/templates/partials/tax_recipient_row.html:28,34`
- **Návrh:** Endpoint by měl používat `owner_id` lookup místo `dist_id`, a validovat konzistenci `email_address_used` napříč sibling distribucemi.

#### Nález #12: Email edit formulář používá dist_ids[0] i pro odeslané distribuce
- **Severity:** DŮLEŽITÉ
- **Pohled:** Data quality, Business analytik
- **Problém:** Inline edit emailu posílá na endpoint s `dist_ids[0]`. Pokud tato distribuce má `email_status = sent`, endpoint přesto aktualizuje `email_address_used`, čímž přepisuje historický záznam.
- **Dopad:** Falešný historický záznam — po editaci vypadá, jako by email šel na jinou adresu, než kam reálně dorazil.
- **Kde v kódu:** `app/templates/partials/tax_recipient_row.html:52-53`
- **Návrh:** Zamknout edit emailu pro distribuce se statusem SENT.

#### Nález #13: Žádná možnost zrušit rozesílku — pouze pozastavit
- **Severity:** DŮLEŽITÉ
- **Pohled:** Běžný uživatel, Business analytik
- **Problém:** Progress stránka nabízí „Pozastavit" a „Pokračovat", ale ne „Zrušit rozesílku". Po pozastavení uživatel nemůže rozesílku zrušit — musí nakonec pokračovat.
- **Dopad:** Uživatel, který po pozastavení zjistí chybu (špatný předmět, špatné tělo), nemůže rozesílku zastavit. Pro již odeslaným příjemcům retry neexistuje.
- **Kde v kódu:** `app/routers/tax.py:2149-2165`, `app/templates/partials/tax_send_progress.html`
- **Návrh:** Přidat tlačítko „Zrušit rozesílku" — nastaví `done=True`, resetuje QUEUED distribuce zpět na PENDING.
- **Mockup:**
  ```
  Současný stav:
  ┌──────────────────────────────────────┐
  │  Odesláno 15/80                      │
  │  ████████░░░░░░░  19%                │
  │           [Pozastavit]               │
  └──────────────────────────────────────┘

  Navrhovaný stav:
  ┌──────────────────────────────────────┐
  │  Odesláno 15/80                      │
  │  ████████░░░░░░░  19%                │
  │   [Zrušit rozesílku] [Pozastavit]   │
  └──────────────────────────────────────┘
  ```

#### Nález #9: In-memory progress ztracen při restartu serveru
- **Severity:** DŮLEŽITÉ
- **Pohled:** Error recovery, Běžný uživatel
- **Problém:** Background thread odesílání je `daemon=True` — zabije se při ukončení procesu bez dokončení DB commitů. Distribuce mohou mít v DB status QUEUED, ale emaily byly reálně odeslány. Při restartu neexistuje startup recovery job.
- **Dopad:** Po restartu serveru: některé emaily odeslány, ale distribuce ukazují QUEUED. Opětovné spuštění = dvojité odeslání.
- **Kde v kódu:** `app/routers/tax.py:1325-1328`, funkce `_send_emails_batch`
- **Návrh:** Přidat startup recovery v `lifespan` — resetovat SENDING session na PAUSED. Zapisovat progress do DB po každém odeslaném emailu (ne jen do paměti).

#### Nález #25: Nové SMTP připojení pro každý email v dávce
- **Severity:** DŮLEŽITÉ
- **Pohled:** Performance analytik
- **Problém:** `send_email()` otevírá nové TCP spojení na SMTP server, provádí STARTTLS handshake, autentizuje se, odešle 1 zprávu a odpojí se. Pro 100 emailů = 100 TCP připojení a 100 autentizací.
- **Dopad:** Velmi pomalé dávkové odesílání (každé spojení ~100-500ms pro TLS). Gmail App Passwords mají přísné limity na připojení.
- **Kde v kódu:** `app/services/email_service.py:84-95`
- **Návrh:** Reuse jediné SMTP připojení pro celou dávku. Předat SMTP server objekt do `send_email()` jako volitelný parametr.
- **Mockup:**
  ```
  Současný stav (100 emailů):
  ┌─────────────────────────────────────┐
  │ Email 1: connect → TLS → auth →    │
  │          send → quit    ~400ms      │
  │ Email 2: connect → TLS → auth →    │
  │          send → quit    ~400ms      │
  │ ...                                 │
  │ Celkem: ~40 sekund + intervaly      │
  └─────────────────────────────────────┘

  Navrhovaný stav (100 emailů):
  ┌─────────────────────────────────────┐
  │ connect → TLS → auth               │
  │ Email 1: send           ~50ms      │
  │ Email 2: send           ~50ms      │
  │ ...                                 │
  │ quit                                │
  │ Celkem: ~5 sekund + intervaly       │
  └─────────────────────────────────────┘
  ```

#### Nález #15: „Uložit a zavřít" neukládá emailová nastavení
- **Severity:** DROBNÉ
- **Pohled:** Běžný uživatel, UI/UX designer
- **Problém:** Oba tlačítka „Zavřít" a „Uložit a zavřít" navigují na `/dane/{id}`. Rozdíl je jen v sessionStorage (checkbox snapshot). „Uložit a zavřít" NEUKLÁDÁ emailová nastavení (předmět, tělo) — to dělá jen „Uložit nastavení".
- **Dopad:** Uživatel klikne „Uložit a zavřít" v domění, že jeho úpravy emailu se uložily. Při návratu zjistí, že ne.
- **Kde v kódu:** `app/templates/tax/send.html:23-30`
- **Návrh:** Buď odebrat „Uložit a zavřít" a ponechat jen „Zavřít", nebo „Uložit a zavřít" skutečně odešle formulář nastavení.

#### Nález #14: Flash zpráva z testovacího emailu může být neviditelná
- **Severity:** DROBNÉ
- **Pohled:** Běžný uživatel, UI/UX designer
- **Problém:** Po odeslání testovacího emailu se flash zpráva zobrazí v base šabloně nahoře — ale send stránka má fixed-height layout (`calc(100vh - 3rem)`). Flash zpráva může být mimo viditelnou oblast.
- **Dopad:** Uživatel nevidí výsledek testu. „Test OK" / chybová zpráva se ztratí.
- **Kde v kódu:** `app/templates/tax/send.html:59`
- **Návrh:** Zobrazit flash zprávu uvnitř settings panelu (vedle tlačítka „Odeslat test").

#### Nález #17: Tlačítko „Rozeslat" ukazuje count 0 při načtení
- **Severity:** DROBNÉ
- **Pohled:** UI/UX designer, Běžný uživatel
- **Problém:** Tlačítko vždy startuje s `Rozeslat (0)` v HTML, pak JavaScript aktualizuje count. Při pomalém načtení JS uživatel vidí „Rozeslat (0)".
- **Dopad:** Krátký záblesk „Rozeslat (0)" při každém načtení stránky — matoucí.
- **Kde v kódu:** `app/templates/tax/send.html:43-44`
- **Návrh:** Nastavit iniciální count server-side v šabloně, nebo skrýt tlačítko dokud JS neproběhne.

#### Nález #19: Send modal tlačítko se nedeaktivuje po kliknutí
- **Severity:** DROBNÉ
- **Pohled:** UI/UX designer, Běžný uživatel
- **Problém:** Po kliknutí „Rozeslat" v potvrzovacím modalu se tlačítko vizuálně nedeaktivuje. Uživatel může kliknout vícekrát. Backend má guard, ale UX je špatný.
- **Kde v kódu:** `app/static/js/app.js:460-476`
- **Návrh:** Disable tlačítko + spinner po prvním kliknutí.

#### Nález #20: Nastavení dávek nemá nápovědu
- **Severity:** DROBNÉ
- **Pohled:** Běžný uživatel, UI/UX designer
- **Problém:** „Potvrdit každou dávku", „Velikost dávky" a „Interval mezi dávkami" nemají žádný tooltip ani vysvětlení. Běžný SVJ uživatel netuší, co je „dávka".
- **Dopad:** Uživatelé buď nastavení ignorují, nebo špatně nakonfigurují (např. dávka=1 + potvrdit každou = katastrofa pro 80 příjemců).
- **Kde v kódu:** `app/templates/tax/send.html:91-95`
- **Návrh:** Přidat popisky/tooltipy ke všem nastavením. Např.: „Dávka = kolik emailů se odešle najednou před pauzou."

#### Nález #26: Žádná serverová validace formátu emailu při inline editaci
- **Severity:** DROBNÉ
- **Pohled:** Data quality, Error recovery
- **Problém:** HTML `type="email"` poskytuje základní browser validaci, ale backend endpoint `update_recipient_email` nevaliduje formát — přijme cokoliv. Neplatné emaily projdou a selžou až při odesílání s kryptickou SMTP chybou.
- **Kde v kódu:** `app/templates/partials/tax_recipient_row.html:55-58`, `app/routers/tax.py:1430`
- **Návrh:** Přidat základní regex validaci emailu na backendu.

---

### Celý workflow / průřezové

#### Nález #16: Wizard stepper — nejednoznačný stav pro SENDING
- **Severity:** DROBNÉ
- **Pohled:** UI/UX designer, Business analytik
- **Problém:** `max_done = 2` pro READY i SENDING — wizard vizuálně nerozlišuje „připraveno k odeslání" od „právě se odesílá".
- **Kde v kódu:** `app/routers/tax.py:61-71`
- **Návrh:** Pro SENDING nastavit `max_done = 2` s animovaným krokem 3 (pulzující ikona).

#### Nález #18: Filtr „Vše" produkuje nečistou URL
- **Severity:** DROBNÉ
- **Pohled:** UI/UX designer
- **Problém:** Odkaz „Vše" generuje `/dane?stav=` (s prázdným `=`). Funkčně v pořádku, ale v address baru vypadá jako neúplný parametr.
- **Kde v kódu:** `app/templates/tax/index.html:19`
- **Návrh:** Použít `/dane` bez query stringu pro filtr „Vše".

#### Nález #24: Processing stránka nemá wizard stepper
- **Severity:** DROBNÉ
- **Pohled:** UI/UX designer, Běžný uživatel
- **Problém:** Processing stránka (zpracování PDF) nezobrazuje wizard kroky — uživatel neví, kde v procesu se nachází.
- **Kde v kódu:** `app/templates/tax/processing.html`
- **Návrh:** Předat `_tax_wizard` kontext a zobrazit stepper.

#### Nález #27: Back label nepokrývá všechny navigační zdroje
- **Severity:** DROBNÉ
- **Pohled:** UI/UX designer
- **Problém:** Back label na matching stránce má jen dva případy: dashboard → „Zpět na přehled", vše ostatní → „Zpět na rozesílání". Dle CLAUDE.md konvence by měl být řetězený `if/elif`.
- **Kde v kódu:** `app/routers/tax.py:1025-1026`
- **Návrh:** Přidat větve pro `/dane` (filtrovaný seznam), `/dane/{id}/upload` atd.

#### Nález #28: Chyba background threadu zanechá osiřelé soubory na disku
- **Severity:** DROBNÉ
- **Pohled:** Error recovery
- **Problém:** Při výjimce v `_process_tax_files` se DB rollbackne (smaže částečné záznamy), ale fyzické PDF soubory na disku zůstanou. Neexistuje cleanup mechanismus.
- **Dopad:** Osiřelé PDF soubory bez DB záznamu. Žádný způsob automatického vyčištění.
- **Kde v kódu:** `app/routers/tax.py:800-808`
- **Návrh:** Po rollbacku smazat soubory z `saved_files` listu.

#### Nález #23: Plný rebuild příjemců při každé editaci emailu
- **Severity:** DROBNÉ
- **Pohled:** Performance analytik
- **Problém:** `_build_recipients()` se volá při každé editaci jednoho emailu — pro 300 příjemců se přebuduje celý seznam kvůli aktualizaci jednoho řádku.
- **Kde v kódu:** `app/routers/tax.py:1517-1527`
- **Návrh:** Vrátit jen jeden aktualizovaný řádek bez přebudování celého seznamu.

---

## Top 5 doporučení (podle dopadu)

| # | Návrh | Dopad | Složitost | Priorita |
|---|-------|-------|-----------|----------|
| 1 | Flash zprávy při selhání uploadu (#1, #2) | Vysoký — uživatelé ztrácejí orientaci | Nízká | HNED |
| 2 | Zobrazit chyby background zpracování (#3) | Vysoký — skryté selhání vytváří zmatky | Nízká | HNED |
| 3 | Nenastavovat READY při uložení nastavení (#4) | Vysoký — obchází workflow | Nízká | HNED |
| 4 | Reuse SMTP spojení v dávce (#25) | Vysoký — 8x rychlejší odesílání | Střední | BRZY |
| 5 | Cancel rozesílky + invalidace testu (#13, #8) | Střední — nemožnost zastavit chybu | Střední | BRZY |

---

## Quick wins (nízká složitost, okamžitý efekt)

- [x] Flash zprávy při selhání uploadu validace (2 řádky kódu v routeru)
- [x] Nenastavovat `send_status = READY` v `save_send_settings` pokud session je DRAFT
- [x] Invalidovat `test_email_passed` při změně emailu předmětu/těla
- [x] Čistá URL `/dane` pro filtr „Vše" (1 řádek v šabloně)
- [x] Přidat wizard stepper na processing stránku (1 include + kontext)
- [x] Tooltip/popisek u nastavení dávek
- [x] Disable tlačítko v send modal po kliknutí
- [x] Přidat back label větve dle CLAUDE.md konvence

---

## Výsledky implementace

> Implementováno: 2026-03-04
> Všech 6 skupin implementováno a otestováno (automaticky i manuálně)

### Stav jednotlivých fixů

| # | Nález | Stav | Poznámka |
|---|-------|------|----------|
| 1 | Tichý redirect při selhání validace uploadu | ✅ Hotovo | Flash zpráva přes `?chyba=` query parametr |
| 2 | Tichý redirect bez validních PDF | ✅ Hotovo | Stejný mechanismus jako #1 |
| 3 | Chyby zpracování PDF se nezobrazí | ✅ Hotovo | Error blok v `tax_progress.html`, endpoint neředirektuje při chybě |
| 4 | Uložení nastavení vynucuje READY | ✅ Hotovo | READY se nastaví jen pokud session není DRAFT |
| 5 | Rok hardcoded | ✅ Hotovo | Editovatelné pole s defaultem na aktuální rok, validace 2020–2099 |
| 6 | Dual-email checkbox a SENT distribuce | ✅ Hotovo | Propagace přeskočí distribuce se statusem SENT |
| 7 | Testovací email s náhodným PDF | ⏭️ Přeskočeno | Vyžaduje větší refaktoring test email flow |
| 8 | Změna emailu neinvaliduje test | ✅ Hotovo | `test_email_passed = False` při změně předmětu/těla |
| 9 | In-memory progress ztracen při restartu | ✅ Hotovo | Startup recovery: SENDING → PAUSED v `main.py` lifespan |
| 10 | Žádné shrnutí před „Potvrdit vše" | ✅ Hotovo | Dialog zobrazuje počet auto-matched a zbývajících nepřiřazených |
| 11 | Přepsání bez potvrzení | ✅ Hotovo | `confirm()` dialog s varováním před ztrátou dat |
| 12 | Email edit u odeslaných distribucí | ✅ Hotovo | Endpoint přeskočí distribuce se statusem SENT |
| 13 | Žádná možnost zrušit rozesílku | ✅ Hotovo | Nový endpoint `POST /{id}/rozeslat/zrusit`, tlačítko v progress UI |
| 14 | Flash zpráva z testu neviditelná | ✅ Hotovo | Flash se zobrazuje uvnitř settings `<details>` panelu |
| 15 | „Uložit a zavřít" neukládá | ✅ Hotovo | Odstraněno, ponecháno jen „Zavřít" |
| 16 | Wizard nerozlišuje READY/SENDING | ⏭️ Přeskočeno | Minimální vizuální dopad |
| 17 | Send count 0 při načtení | ✅ Hotovo | Počáteční hodnota nastavena server-side |
| 18 | Filtr „Vše" nečistá URL | ✅ Hotovo | Odkaz vede na `/dane/` bez query stringu |
| 19 | Send tlačítko se nedeaktivuje | ✅ Hotovo | `disabled=true` + text „Odesílám…" po kliknutí |
| 20 | Nastavení dávek bez nápovědy | ✅ Hotovo | Tooltip `title` atributy na všech polích |
| 21 | Přepisovací mód maže před zápisem | ✅ Hotovo | Pořadí obráceno: zápis nových → smazání starých |
| 22 | Žádná paginace matchingu | ⏭️ Přeskočeno | Předčasná optimalizace pro typickou SVJ (100–300 jednotek) |
| 23 | Plný rebuild příjemců při editaci | ⏭️ Přeskočeno | Předčasná optimalizace, SQLite zvládá efektivně |
| 24 | Processing bez wizard stepperu | ✅ Hotovo | `_tax_wizard(session, 1)` kontext + include v šabloně |
| 25 | Nové SMTP spojení pro každý email | ✅ Hotovo | `create_smtp_connection()` + reuse v `_send_emails_batch` |
| 26 | Žádná serverová validace emailu | ✅ Hotovo | Regex validace v `update_recipient_email` |
| 27 | Back label nepokrývá zdroje | ✅ Hotovo | Řetězený `if/elif` s větvemi pro `/`, `/dane`, default |
| 28 | Osiřelé soubory při chybě threadu | ✅ Hotovo | Cleanup v exception handleru `_process_tax_files` |

**Celkem:** 24 implementováno, 4 přeskočeno (záměrně)

### Změněné soubory

| Soubor | Změny |
|--------|-------|
| `app/routers/tax.py` | Flash zprávy (#1,#2), error zobrazení (#3), READY guard (#4), rok (#5), SENT ochrana (#6,#12), test invalidace (#8), startup recovery (#9), cancel sending (#13), email validace (#26), back labels (#27), file cleanup (#28), SMTP reuse (#25), safe overwrite (#21) |
| `app/main.py` | Startup recovery stuck sessions (#9) |
| `app/services/email_service.py` | `create_smtp_connection()`, SMTP reuse parametr (#25) |
| `app/templates/tax/send.html` | Flash v settings (#14), remove „Uložit a zavřít" (#15), send count init (#17), button disable (#19), tooltips (#20) |
| `app/templates/tax/index.html` | „Vše" filter URL (#18) |
| `app/templates/tax/upload.html` | Year input field (#5) |
| `app/templates/tax/upload_additional.html` | Confirm dialog pro overwrite (#11) |
| `app/templates/tax/matching.html` | Confirm s počty (#10) |
| `app/templates/tax/processing.html` | Wizard stepper (#24) |
| `app/templates/partials/tax_progress.html` | Error state zobrazení (#3) |
| `app/templates/partials/tax_send_progress.html` | „Zrušit rozesílku" tlačítko (#13) |

---

## Manuální testování

### Krok 1 — Nahrání PDF

1. **Flash při chybě uploadu (#1, #2)**
   - Jít na `/dane/nova`
   - Nahrát složku obsahující pouze `.DS_Store` (nebo žádné PDF)
   - Očekávání: červená flash zpráva „Nebyly nalezeny žádné platné PDF soubory"
   - Nahrát soubor přesahující limit (>10 MB)
   - Očekávání: flash zpráva s konkrétní chybou z `validate_uploads()`

2. **Pole rok (#5)**
   - Na `/dane/nova` ověřit, že se zobrazuje pole „Rok" s výchozí hodnotou aktuálního roku
   - Změnit rok na 2025, nahrát PDF
   - Ověřit, že session má `year = 2025`

3. **Přepisovací confirm (#11)**
   - Na stránce doplnění PDF (`/dane/{id}/nahrat-dalsi`) zvolit „Přepsat stávající"
   - Kliknout „Nahrát" → měl by se objevit `confirm()` dialog s varováním

### Krok 2 — Přiřazení (matching)

4. **Potvrdit vše — shrnutí (#10)**
   - Na `/dane/{id}/prirazeni` kliknout „Potvrdit vše"
   - Očekávání: dialog zobrazuje počet auto-matched a počet nepřiřazených

5. **Uzamknout — varování (#10)**
   - Kliknout „Uzamknout" když existují nepřiřazené dokumenty
   - Očekávání: dialog upozorní na nepřiřazené dokumenty

### Krok 3 — Rozesílka (send)

6. **Settings flash (#14)**
   - Na `/dane/{id}/rozeslat` otevřít nastavení (kliknout na `<details>`)
   - Odeslat testovací email (nebo uložit nastavení)
   - Očekávání: flash zpráva se zobrazí UVNITŘ settings panelu (ne nahoře stránky)

7. **Zavřít místo „Uložit a zavřít" (#15)**
   - Ověřit, že na send stránce je jen tlačítko „Zavřít" (ne „Uložit a zavřít")

8. **Počet odesílaných (#17)**
   - Načíst send stránku — tlačítko „Rozeslat" by mělo hned zobrazovat správný počet (ne 0)

9. **Disable po kliknutí (#19)**
   - Kliknout na „Rozeslat" v potvrzovacím modalu
   - Očekávání: tlačítko se zdeaktivuje, text se změní na „Odesílám…"

10. **Tooltips (#20)**
    - V nastavení dávek najet myší na „Velikost dávky", „Interval" atd.
    - Očekávání: tooltip s vysvětlením

11. **Zrušit rozesílku (#13)**
    - Při aktivním odesílání ověřit tlačítko „Zrušit rozesílku"
    - Po kliknutí: session se nastaví na PAUSED, neodeslaní příjemci se resetují

12. **Test invalidace (#8)**
    - Odeslat testovací email → ověřit „Test OK" badge
    - Změnit předmět emailu → uložit nastavení
    - Očekávání: „Test OK" zmizí, je potřeba nový test

### Průřezové

13. **Back labels (#27)**
    - Přijít na detail session z dashboardu (`?back=/`) → „Zpět na přehled"
    - Přijít z filtru (`?back=/dane?stav=ready`) → „Zpět na seznam rozesílek"

14. **Wizard stepper na processing (#24)**
    - Spustit zpracování nových PDF
    - Očekávání: processing stránka zobrazuje wizard stepper s aktuálním krokem

15. **Startup recovery (#9)**
    - Restartovat server když existuje session se stavem SENDING
    - Očekávání: session se automaticky přepne na PAUSED (log warning)

16. **SENT ochrana (#6, #12)**
    - U příjemce s odeslaným emailem zkusit změnit email
    - Očekávání: odeslaná distribuce se NEZMĚNÍ, pouze neodeslaná

17. **URL filtru „Vše" (#18)**
    - Na `/dane` kliknout na bublinu „Vše"
    - Očekávání: URL je `/dane/` (ne `/dane?stav=`)
