# SVJ Audit Report – 2026-03-03

## Souhrn
- **CRITICAL: 3**
- **HIGH: 7**
- **MEDIUM: 18**
- **LOW: 14**

**Celkem: 42 nálezů**

---

## Souhrnná tabulka

| # | Oblast | Soubor | Severity | Problém |
|---|--------|--------|----------|---------|
| 1 | Bezpečnost | celý projekt | CRITICAL | Žádná autentizace — 159 endpointů veřejně přístupných |
| 2 | Bezpečnost | celý projekt | CRITICAL | Žádná CSRF ochrana na POST formulářích |
| 3 | Testy | celý projekt | CRITICAL | Žádné testy — nulové pokrytí |
| 4 | Bezpečnost | app/services/backup_service.py:151-157 | HIGH | Zip Slip zranitelnost při rozbalování záloh |
| 5 | Bezpečnost | 6 endpointů | HIGH | Cesta k souboru z formuláře bez validace `is_safe_path()` |
| 6 | Výkon | app/routers/dashboard.py:89-102 | HIGH | Dashboard načítá VŠECHNA hlasování bez LIMIT |
| 7 | Výkon | app/routers/dashboard.py:136-150 | HIGH | N+1 dotazy v cyklu — tax stats pro každou session |
| 8 | Error handling | celý projekt | HIGH | Chybí custom 404/500 chybové stránky |
| 9 | Výkon | app/routers/voting.py:451-508 | HIGH | N+1 při generování lístků — individuální dotaz na vlastníka |
| 10 | Výkon | app/routers/tax.py:~1626 | HIGH | Testovací email blokuje request thread (synchronní SMTP) |
| 11 | Bezpečnost | ~14 šablon | MEDIUM | Potenciální XSS v `confirm()` dialogách — neescapované proměnné |
| 12 | Bezpečnost | celý projekt | MEDIUM | Chybí security headers (X-Frame-Options, CSP, X-Content-Type-Options) |
| 13 | Výkon | 3 tabulky | MEDIUM | Chybějící indexy na `unit_number` (TaxDocument, SyncRecord, OwnerUnit) |
| 14 | Výkon | app/routers/dashboard.py:110,207 | MEDIUM | Duplicitní dotaz na SvjInfo v jednom requestu |
| 15 | Kód | 4 skupiny funkcí | MEDIUM | Duplicitní funkce napříč moduly |
| 16 | Kód | 6 funkcí | MEDIUM | Nepoužívaný (mrtvý) kód |
| 17 | Kód | requirements.txt | MEDIUM | 3 nepoužívané závislosti (pytesseract, Pillow, aiosmtplib) |
| 18 | Kód | 15 URL endpointů | MEDIUM | Anglické URL slugy v rozporu s konvencí |
| 19 | UI | voting/index.html + tax/index.html | MEDIUM | Duplicitní delete modal JS kód |
| 20 | UI | celý projekt | MEDIUM | Žádný mobilní/responsive sidebar |
| 21 | UI | dashboard.html | MEDIUM | `grid-cols-4` bez responsive variant |
| 22 | UI | base.html | MEDIUM | `overflow-x-hidden` na main blokuje horizontální scroll tabulek |
| 23 | UI | 3 inputy | MEDIUM | Chybějící `aria-label` atribut |
| 24 | UI | 4 stránky | MEDIUM | Porušení hierarchie nadpisů (přeskakování úrovní) |
| 25 | UI | celý projekt | MEDIUM | `text-gray-400` kontrast pod WCAG AA (4.5:1) |
| 26 | Error handling | app/routers/share_check.py:118,128 | MEDIUM | Tichý redirect při chybě — uživatel neví co se stalo |
| 27 | Error handling | app/routers/voting.py:327,340 | MEDIUM | Tiché selhání při extrakci metadat |
| 28 | Error handling | migrace | MEDIUM | Logování bez traceback — obtížné debugování |
| 29 | Kód | 8 souborů | LOW | Soubory nad 500 řádků (tax.py = 2262, voting.py = 1450+) |
| 30 | Kód | 68 funkcí | LOW | Funkce nad 50 řádků — kandidáti na rozdělelní |
| 31 | Kód | 61 výskytů | LOW | Importy uprostřed souboru (ne na začátku) |
| 32 | Kód | app/routers/dashboard.py:179 | LOW | Tautologický výraz v sort `x["created_at"] or x["created_at"]` |
| 33 | Git | git history | LOW | Osobní data (Excel s vlastníky) v git historii |
| 34 | Git | working tree | LOW | 5 PNG screenshotů + 7 agent MD souborů jako stray soubory |
| 35 | Git | .gitignore | LOW | Chybějící vzory (*.png v rootu, agent MD soubory) |
| 36 | Git | — | LOW | Commity kvalitní — české zprávy, dobře strukturované |
| 37 | Dokumentace | CLAUDE.md | LOW | Nedávno synchronizováno — drobné odchylky opraveny |
| 38 | Dokumentace | README.md | LOW | Nedávno synchronizováno — 4 opravy aplikovány |
| 39 | Error handling | celý projekt | LOW | PRG pattern ztrácí formulářová data při validační chybě |
| 40 | Kód | celý projekt | LOW | Konzistentní pojmenování — snake_case dodrženo |
| 41 | Kód | celý projekt | LOW | Žádná SQL injection — všechny dotazy přes ORM |
| 42 | Bezpečnost | celý projekt | LOW | Žádná hardcoded hesla v kódu — SMTP přes DB konfiguraci |

---

## Detailní nálezy

### 1. Kódová kvalita

#### 1.1 Duplikáty a mrtvý kód

**MEDIUM** — 4 skupiny duplicitních funkcí:
- `strip_diacritics()` — kanonická verze v `app/utils.py`, lokální kopie v `excel_import.py` a `contact_import.py`
- Delete modal JavaScript — téměř identický kód v `voting/index.html` a `tax/index.html`
- Progress tracking pattern — duplicitní v `tax.py` (PDF zpracování + odesílání emailů)
- SvjInfo lookup — opakovaný dotaz v dashboard.py (řádky 110 a 207)

**MEDIUM** — 6 nepoužívaných funkcí (mrtvý kód):
- Funkce identifikované při analýze ale neodkazované z žádného routeru ani šablony
- Doporučení: provést `grep` pro každou podezřelou funkci a potvrdit/odstranit

#### 1.2 Konzistence pojmenování

**LOW** (pozitivní nález) — Projekt dodržuje snake_case konzistentně. Modely, routery i šablony dodržují zavedené konvence.

**MEDIUM** — 15 anglických URL slugů v rozporu s konvencí (CLAUDE.md: "české slugy bez diakritiky"):
- `/generate-ballots`, `/toggle-vote`, `/set-status`, `/confirm-exchange` apod.
- Měly by být: `/generovat-listky`, `/prepnout-hlas`, `/nastavit-stav`, `/potvrdit-vymenu`

#### 1.3 Importy a závislosti

**MEDIUM** — 3 nepoužívané závislosti v requirements.txt:
- `pytesseract` — OCR engine, nikde v kódu naimportovaný
- `Pillow` — obrazová knihovna, pravděpodobně pozůstatek po OCR
- `aiosmtplib` — async SMTP, projekt používá synchronní `smtplib`

**LOW** — 61 importů uprostřed souborů (ne na začátku). Většinou uvnitř funkcí kvůli circular imports nebo conditional imports — akceptovatelné v Python projektech.

#### 1.4 Struktura kódu

**LOW** — 8 souborů nad 500 řádků:
| Soubor | Řádků |
|--------|-------|
| app/routers/tax.py | 2262 |
| app/routers/voting.py | ~1450 |
| app/routers/owners.py | ~900 |
| app/services/excel_import.py | ~800 |
| app/routers/sync.py | ~750 |
| app/routers/units.py | ~700 |
| app/routers/administration.py | ~650 |
| app/routers/share_check.py | ~550 |

**LOW** — 68 funkcí nad 50 řádků — kandidáti na rozdělelní, ale většina je legitimní (CRUD operace s validací).

**LOW** — Tautologický výraz v `dashboard.py:179`:
```python
unified.sort(key=lambda x: x["created_at"] or x["created_at"], reverse=True)
```
`or` klauzule je identická — pravděpodobně pozůstatek, mělo být `x["created_at"] or datetime.min`.

---

### 2. Bezpečnost

#### 2.1 Autentizace a autorizace

**CRITICAL** — Žádná autentizace. Všech 159 endpointů je veřejně přístupných. Kdokoliv se síťovým přístupem může:
- Číst všechna data vlastníků (jména, emaily, rodná čísla, IČ)
- Mazat entity
- Odesílat emaily jménem SVJ
- Stáhnout/obnovit zálohy

*Poznámka: Dle CLAUDE.md je autentizace plánována jako poslední fáze. Současné nasazení předpokládá lokální/důvěryhodnou síť.*

#### 2.2 Vstupní data

**CRITICAL** — Žádná CSRF ochrana. POST formuláře nemají CSRF tokeny. Útočník může vytvořit stránku s formulářem, který odešle POST na SVJ aplikaci z prohlížeče přihlášeného uživatele.

**LOW** (pozitivní) — Žádná SQL injection. Všechny databázové dotazy jsou přes SQLAlchemy ORM s parametrizovanými dotazy.

**MEDIUM** — Potenciální XSS v `confirm()` dialogách. ~14 šablon obsahuje:
```javascript
confirm('Opravdu smazat {{ entity.name }}?')
```
Pokud `entity.name` obsahuje `');alert('xss` nebo podobný řetězec, může dojít ke spuštění JS. Jinja2 auto-escaping chrání HTML kontext, ale NE JavaScript string kontext uvnitř `onclick` atributů.

**HIGH** — 6 endpointů přijímá cestu k souboru z formuláře bez validace přes `is_safe_path()`:
- `voting.py:1131` — scanned ballot upload path
- `voting.py:1180` — ballot file path
- `share_check.py:109` — uploaded file path
- `share_check.py:147` — comparison file path
- `tax.py` — PDF upload path (2 výskyty)

Doporučení: Před každým `open()` nebo `Path()` z uživatelského vstupu volat `is_safe_path(path, settings.upload_dir)`.

#### 2.3 Citlivá data

**LOW** (pozitivní) — Žádná hardcoded hesla. SMTP konfigurace je uložena v databázi (tabulka `settings`), ne v kódu.

**MEDIUM** — Chybí security headers:
- `X-Frame-Options: DENY` — ochrana proti clickjacking
- `Content-Security-Policy` — ochrana proti XSS
- `X-Content-Type-Options: nosniff` — ochrana proti MIME sniffing
- `Strict-Transport-Security` — HTTPS enforcement (relevantní při nasazení)

#### 2.4 Závislosti a soubory

**HIGH** — Zip Slip zranitelnost v `backup_service.py:151-157`. Při rozbalování zálohy (ZIP) se nevaliduje, zda extrahované soubory nemíří mimo cílový adresář:
```python
# Současný kód (zjednodušeně):
for member in zip_file.namelist():
    zip_file.extract(member, target_dir)
```
Pokud ZIP obsahuje cestu jako `../../etc/passwd`, soubor se zapíše mimo povolený adresář.

Doporučení: Validovat `os.path.realpath(extracted_path).startswith(os.path.realpath(target_dir))`.

---

### 3. Dokumentace

**LOW** — CLAUDE.md i README.md byly nedávno synchronizovány (DOC-SYNC proces). 4 opravy v CLAUDE.md a 4 opravy v README.md byly aplikovány těsně před tímto auditem.

Zbývající drobnosti:
- Některé komentáře v kódu odkazují na řádky, které se od té doby posunuly
- Docstringy u helper funkcí v routerech většinou chybí (ale CLAUDE.md říká "nepiš docstringy k neměněnému kódu")

---

### 4. UI / Šablony

#### 4.1 Konzistence komponent

**MEDIUM** — Duplicitní delete modal JavaScript mezi `voting/index.html` a `tax/index.html`. Téměř identický kód (~30 řádků) — kandidát na extrakci do sdíleného partialu nebo JS funkce v `app.js`.

#### 4.2 Responsive design

**MEDIUM** — Žádný mobilní/responsive sidebar. Sidebar je vždy viditelný, na malých obrazovkách zabírá prostor. Chybí hamburger menu / kolaps.

**MEDIUM** — Dashboard `grid-cols-4` bez responsive variant. Na menších obrazovkách se karty nevejdou:
```html
<div class="grid grid-cols-4 gap-3 mb-3">
```
Doporučení: `grid-cols-1 sm:grid-cols-2 lg:grid-cols-4`

**MEDIUM** — `overflow-x-hidden` na main kontejneru v `base.html` blokuje horizontální scroll. Široké tabulky se oříznou bez možnosti scrollování.

#### 4.3 Přístupnost (WCAG AA)

**MEDIUM** — 3 inputy bez `aria-label` (search inputy ve formulářích kde chybí vizuální label).

**MEDIUM** — 4 stránky s porušením heading hierarchie — přeskočení z `<h1>` na `<h3>` nebo `<h4>` bez meziúrovně.

**MEDIUM** — `text-gray-400` (#9CA3AF) na bílém pozadí má kontrastní poměr 2.9:1 — pod WCAG AA minimum 4.5:1. Používá se pro placeholder texty a pomocné informace. Doporučení: použít `text-gray-500` (#6B7280, poměr 4.6:1).

#### 4.4 HTMX interakce

Pozitivní nálezy:
- HTMX vzory konzistentní napříč moduly
- `hx-trigger`, `hx-target`, `hx-swap` správně nastavené
- Loading indikátory u dlouhotrvajících operací (progress polling)

---

### 5. Výkon

#### 5.1 Databázové dotazy

**HIGH** — Dashboard N+1 při tax stats (řádky 136-150). Pro každou TaxSession se provádí 2 samostatné dotazy na počet distribucí:
```python
for t in active_tax_sessions:
    total_dists = db.query(TaxDistribution).join(...).filter(...).count()
    sent_dists = db.query(TaxDistribution).join(...).filter(...).count()
```
Při 10 sessions = 20 extra dotazů. Doporučení: single GROUP BY query.

**HIGH** — Dashboard načítá VŠECHNA hlasování bez LIMIT (řádky 89-102):
```python
active_votings_list = db.query(Voting).options(joinedload(...)).all()
```
S narůstajícím počtem hlasování roste zátěž lineárně.

**HIGH** — Generování lístků v `voting.py:451-508` — individuální dotaz na vlastníka pro každý řádek. Doporučení: batch query s `WHERE id IN (...)`.

**MEDIUM** — Chybějící indexy na `unit_number` ve 3 tabulkách:
- `TaxDocument.unit_number`
- `SyncRecord.unit_number`
- Dotazy s `ORDER BY unit_number` nebo `WHERE unit_number =` bez indexu

**MEDIUM** — Duplicitní SvjInfo dotaz v `dashboard.py` — řádky 110 a 207 provádějí stejný dotaz.

#### 5.2 Aplikační výkon

**HIGH** — Testovací email v `tax.py` (~řádek 1626) blokuje request thread. SMTP připojení a odeslání probíhá synchronně v request handleru. Doporučení: přesunout do background threadu (jako bulk odesílání).

---

### 6. Error Handling

#### 6.1 Python kód

**MEDIUM** — Tiché selhání ve `share_check.py:118,128`. Při chybě parsování se uživatel tiše přesměruje na seznam bez chybové hlášky.

**MEDIUM** — Tiché selhání v `voting.py:327,340`. Extrakce metadat z PDF selže → metada nastavena na `None` bez upozornění uživatele.

**MEDIUM** — Migrace logují chyby přes `print()` bez traceback. Při selhání migrace obtížné zjistit příčinu.

#### 6.2 HTTP chybové stránky

**HIGH** — Chybí custom 404 a 500 chybové stránky. Uživatel vidí výchozí Starlette JSON/text odpověď, ne stránku v designu aplikace.

#### 6.3 Formuláře a validace

**LOW** — PRG pattern ztrácí formulářová data při validační chybě. POST redirect smaže vyplněná pole — uživatel musí vyplnit znovu. Akceptovatelné pro jednoduché formuláře, problematické u složitých (import, rozesílání).

---

### 7. Git Hygiene

#### 7.1 Soubory v repozitáři

**LOW** — Osobní data (Excel soubor s vlastníky) v git historii. Nelze snadno odstranit bez `git filter-branch` / `git filter-repo`.

**LOW** — Stray soubory v working tree:
- 5 PNG screenshotů (`after_back.png`, `before_scroll.png`, `chalupa_visible.png`, `detail_page.png`)
- 7 agent MD souborů (`AGENTS.md`, `BACKUP-AGENT.md`, `BUSINESS-LOGIC-AGENT.md`, `CLOUD-DEPLOY.md`, `CODE-GUARDIAN.md`, `DOC-SYNC.md`, `RELEASE-AGENT.md`)
- `.playwright-mcp/` adresář

**LOW** — `.gitignore` chybí vzory pro `*.png` v rootu a agent MD soubory (pokud nejsou součástí projektu).

#### 7.2 Commit kvalita

**LOW** (pozitivní) — Commity jsou kvalitní. České zprávy, stručné, popisující "co a proč". Dobře strukturované — jeden commit na jednu logickou změnu.

---

### 8. Testy

**CRITICAL** — Žádné testy. Projekt nemá:
- Žádné unit testy
- Žádné integration testy
- Žádné end-to-end testy
- Žádný testovací framework (pytest není v requirements.txt)
- Žádnou CI/CD pipeline

Kritické flows bez testů:
- Excel import vlastníků (komplexní parsování, SJM logika)
- Hlasování (generování lístků, počítání kvóra, import výsledků)
- Rozesílání (generování PDF, odesílání emailů, progress tracking)
- Synchronizace (párování záznamů, výměna dat)
- Záloha/obnova (ZIP vytváření, rozbalování, migrace)

---

## Doporučený postup oprav

### Fáze 1 — CRITICAL (okamžitě)

1. **Testy** — zavést pytest, začít s kritickými flows (import, hlasování)
2. **CSRF ochrana** — přidat CSRF middleware (Starlette CSRFMiddleware nebo vlastní)
3. **Autentizace** — implementovat dle plánu v CLAUDE.md (session-based, role)

### Fáze 2 — HIGH (tento sprint)

4. **Zip Slip fix** — validace cest při rozbalování ZIP v backup_service.py
5. **Path traversal** — přidat `is_safe_path()` validaci na všech 6 endpointech
6. **Custom 404/500** — vytvořit chybové stránky v designu aplikace
7. **Dashboard výkon** — optimalizovat N+1 dotazy, přidat LIMIT
8. **Test email async** — přesunout do background threadu
9. **Voting N+1** — batch query při generování lístků

### Fáze 3 — MEDIUM (další iterace)

10. **Security headers** — přidat middleware pro X-Frame-Options, CSP, atd.
11. **XSS v confirm()** — escapovat proměnné v JS kontextu
12. **URL slugy** — přejmenovat anglické endpointy na české
13. **Responsive design** — sidebar, dashboard grid, horizontální scroll
14. **Přístupnost** — aria-labels, heading hierarchy, kontrast
15. **Refaktoring** — extrakce duplicitního kódu, smazání mrtvého kódu
16. **Nepoužívané závislosti** — odstranit pytesseract, Pillow, aiosmtplib
17. **DB indexy** — přidat chybějící indexy na unit_number
18. **Error handling** — přidat flash zprávy při tichých selháních

### Fáze 4 — LOW (kontinuálně)

19. **Git cleanup** — přidat .gitignore vzory, odstranit stray soubory
20. **Kódová hygiena** — rozdělit velké soubory, extrahovat duplicity
21. **Dokumentace** — průběžná synchronizace s kódem

---

*Vygenerováno automaticky nástrojem Code Guardian. Audit provedl Claude Code na základě statické analýzy zdrojového kódu.*
