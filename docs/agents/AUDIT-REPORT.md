# SVJ Audit Report — Modul Platby — 2026-03-22

> Scope: app/routers/payments/, app/services/payment_matching.py, app/services/payment_overview.py, app/services/settlement_service.py, app/models/payment.py, app/templates/payments/

## Souhrn

- **CRITICAL**: 1
- **HIGH**: 5
- **MEDIUM**: 11
- **LOW**: 8

## Souhrnna tabulka

| #  | Oblast       | Soubor                                                       | Severity | Problem                                                        | Cas      | Rozhodnuti |
|----|-------------|--------------------------------------------------------------|----------|----------------------------------------------------------------|----------|------------|
| 1  | Bezpecnost  | statements.py:104, prescriptions.py:82                       | CRITICAL | `saved_path` z formulare bez path traversal validace           | ~15 min  | :wrench:   |
| 2  | Vykon       | payment_matching.py:60,89,91,411,507                         | HIGH     | N+1 dotazy: `db.query(Unit).get()` / `db.query(Owner).get()` v cyklu | ~30 min  | :wrench:   |
| 3  | Vykon       | _helpers.py:76-141                                           | HIGH     | `_count_debtors_fast` nacita vsechny prescriptions + balances do pameti | ~20 min  | :wrench:   |
| 4  | Kod         | settlement.py:157+173                                        | HIGH     | Duplicitni klic `active_tab` v context dict                    | ~2 min   | :wrench:   |
| 5  | Kod         | payment_matching.py (587 r.), statements.py (797 r.)         | HIGH     | Dlouhe soubory, match_payments() ma 280+ radku                 | ~1 hod   | :question: |
| 6  | Bezpecnost  | payment.py (vsechny financni sloupce)                        | HIGH     | `Float` misto `Numeric` pro penezni castky — zaokrouhlovaci chyby | ~2 hod   | :question: |
| 7  | Kod         | prescriptions.py:3-4                                         | MEDIUM   | Nepouzite importy `os`, `shutil`                               | ~1 min   | :wrench:   |
| 8  | Kod         | payment.py:224, 246                                          | MEDIUM   | Duplicitni sekce komentare `Vyuctovani (Faze 4)`               | ~1 min   | :wrench:   |
| 9  | Kod         | prescriptions.py:328, symbols.py:54, statements.py:387       | MEDIUM   | Inline import `from sqlalchemy import asc, desc` uvnitr funkce (3x) | ~5 min   | :wrench:   |
| 10 | Kod         | payment_matching.py:313, 407, 505                            | MEDIUM   | Inline importy uvnitr funkce (`PrescriptionYear`, `Owner`) — obejiti cirkularniho importu | ~10 min  | :question: |
| 11 | Vykon       | compute_candidates():56-66                                   | MEDIUM   | N+1: `db.query(Unit).get(p.unit_id)` pro kazdy predpis        | ~15 min  | :wrench:   |
| 12 | Vykon       | overview.py:58-61                                            | MEDIUM   | `compute_payment_matrix()` vola se dvakrat u dluznici (jednou v service, jednou pres compute_debtor_list) | ~10 min  | :wrench:   |
| 13 | Vykon       | _helpers.py:23-73                                            | MEDIUM   | `compute_nav_stats()` se vola na kazdem payment endpointu (7+ DB dotazu) | ~30 min  | :question: |
| 14 | Sablony     | vypis_tbody.html:29-73                                       | MEDIUM   | Duplicitni formulare confirm/reject (14x hidden input bloky)   | ~20 min  | :wrench:   |
| 15 | Error       | statements.py:292-294                                        | MEDIUM   | Chybejici error handling pri match_payments (muze hodit vyjimku) | ~5 min   | :wrench:   |
| 16 | Error       | overview.py:157-158                                          | MEDIUM   | `compute_payment_matrix` vraci None — template spadne          | ~5 min   | :wrench:   |
| 17 | Sablony     | predpisy_import.html, vypis_import.html                      | MEDIUM   | Formulare pri chybe nezachovavaji vsechna vyplnena pole         | ~10 min  | :wrench:   |
| 18 | Dok         | payment_matching.py:249-290                                  | LOW      | `_extract_unit_from_vs` — hardcoded "1098" bez vysvetleni      | ~5 min   | :wrench:   |
| 19 | Kod         | overview.py:22-25                                            | LOW      | `MONTH_NAMES` dict definovany duplicitne (overview.py + sablony) | ~5 min   | :wrench:   |
| 20 | Kod         | payment_overview.py:188                                      | LOW      | `payment.alloc_amount` dynamicky pridavany atribut na ORM objekt | ~15 min  | :question: |
| 21 | Sablony     | jednotka_platby.html, vyuctovani_detail.html                 | LOW      | Duplicitni payment list sablona (radky 86-113 a 154-183)       | ~15 min  | :wrench:   |
| 22 | Git         | test_vypis.csv (110 KB)                                      | LOW      | Testovaci CSV soubor v koreni projektu (netrackovan)           | ~1 min   | :wrench:   |
| 23 | Testy       | (zadny soubor)                                               | LOW      | Nulove pokryti testy — zadny test_payment*.py                  | ~4 hod   | :question: |
| 24 | Error       | balances.py:106-107                                          | LOW      | Rok validace (2020-2040) bez flash zpravy uzivateli            | ~5 min   | :wrench:   |
| 25 | Dok         | payment_matching.py: _find_name_matches, _find_multi_unit_match | LOW      | Chybejici komentare u magickych hodnot (score 5, slova > 3 znaky) | ~10 min  | :wrench:   |

Legenda: :wrench: = jen opravit, :question: = potreba rozhodnuti uzivatele (vice variant)

---

## Detailni nalezy

### 1. Kodova kvalita

#### N1 — CRITICAL: `saved_path` bez validace path traversal
- **Co a kde**: `statements.py:104` a `prescriptions.py:82` — uzivatel posle `saved_path` jako hidden field z formulare. Server pouzije tuto cestu primo k `Path(saved_path).read_bytes()` bez volani `is_safe_path()`.
- **Reseni**: Pred ctenim souboru pridat validaci `is_safe_path(saved_path, [settings.upload_dir / "temp"])`. Pokud selze, vratit error.
- **Narocnost + cas**: nizka, ~15 min
- **Zavislosti**: zadne
- **Regrese riziko**: nizke — pridava validaci, nemeni logiku
- **Jak otestovat**: (1) Nahrat soubor do importu predpisu/vypisu. (2) V prohlizeci upravit hidden input `saved_path` na `../../data/svj.db`. (3) Odeslat formular. (4) Overit ze server odmitne s chybou misto nacteni DB souboru.

#### N4 — HIGH: Duplicitni klic `active_tab` v context dict
- **Co a kde**: `settlement.py:157` a `settlement.py:173` — v `vyuctovani_seznam()` je `"active_tab": "vyuctovani"` v ctx dict dvakrat. Python to nehlasi, druhy prepise prvni, ale je to zbytecny kod.
- **Reseni**: Smazat radek 173 (`"active_tab": "vyuctovani",`).
- **Narocnost + cas**: nizka, ~2 min
- **Zavislosti**: zadne
- **Regrese riziko**: nulove — druhy klic uz prepisuje ten samy hodnotou
- **Jak otestovat**: Overit ze navigacni karta vyuctovani je stale zvyraznena na `/platby/vyuctovani`.

#### N5 — HIGH: Dlouhe soubory a funkce
- **Co a kde**: `statements.py` (797 radku), `payment_matching.py` (587 radku), `settlement.py` (542 radku). Funkce `match_payments()` ma 280+ radku — tezko testovatelna a citelna.
- **Reseni**: Varianty: (A) Rozdelit `match_payments` na 3 samostatne funkce pro kazdy fazi (`_phase1_vs_match`, `_phase2_name_match`, `_phase3_vs_prefix_match`). (B) Rozdelit `statements.py` na `statements_import.py` + `statements_detail.py` + `statements_actions.py`.
- **Narocnost + cas**: stredni, ~1 hod
- **Zavislosti**: zadne
- **Regrese riziko**: stredni — refactoring muze zavest chyby v logice parovani
- **Jak otestovat**: Importovat CSV vypis, overit ze parovani funguje stejne.

#### N7 — MEDIUM: Nepouzite importy
- **Co a kde**: `prescriptions.py:3-4` — `import os` a `import shutil` nejsou v souboru nikde pouzity.
- **Reseni**: Smazat oba importy.
- **Narocnost + cas**: nizka, ~1 min
- **Zavislosti**: zadne
- **Regrese riziko**: nulove
- **Jak otestovat**: Spustit server, importovat predpisy — overit ze funguje.

#### N8 — MEDIUM: Duplicitni sekce komentare v modelu
- **Co a kde**: `payment.py:224` a `payment.py:246` — dve identicky `# -- Vyuctovani (Faze 4)` komentarove sekce. Pravdepodobne pozustatek z refactoringu kdy se pridal `PaymentAllocation` model mezi ne.
- **Reseni**: Smazat druhou (radek 246), pripadne prejmenovat prvni na neco vystiznejsiho.
- **Narocnost + cas**: nizka, ~1 min
- **Zavislosti**: zadne
- **Regrese riziko**: nulove
- **Jak otestovat**: Automaticky — zadny dopad na runtime.

#### N9 — MEDIUM: Opakujici se inline import `asc`/`desc`
- **Co a kde**: `prescriptions.py:328`, `symbols.py:54`, `statements.py:387` — `from sqlalchemy import asc as sa_asc, desc as sa_desc` je importovano uvnitr funkce misto na zacatku souboru.
- **Reseni**: Presunout do top-level importu.
- **Narocnost + cas**: nizka, ~5 min
- **Zavislosti**: zadne
- **Regrese riziko**: nulove
- **Jak otestovat**: Overit razeni na vsech tabulkach modulu.

#### N10 — MEDIUM: Inline importy uvnitr `match_payments()`
- **Co a kde**: `payment_matching.py:313` (`from app.models import PrescriptionYear`), `:407` (`from app.models import Owner`), `:505` (`from app.models import Owner`).
- **Reseni**: Presunout na zacatek souboru (PrescriptionYear a Owner uz nejsou v cirkularni zavislosti s payment.py).
- **Narocnost + cas**: nizka, ~10 min. Pozor: otestovat ze import neni cirkularni.
- **Zavislosti**: zadne
- **Regrese riziko**: nizke — muze zpusobit cirkularni import, ale pravdepodobne ne
- **Jak otestovat**: `python -c "from app.services.payment_matching import match_payments"` — overit ze import probehne.

#### N19 — LOW: Duplicitni MONTH_NAMES
- **Co a kde**: `overview.py:22-25` definuje `MONTH_NAMES` dict. Sablony `vypis_detail.html:2` a `vypisy.html:18` definuji vlastni `month_names` dict s jinym formatem (zkracena vs plna jmena).
- **Reseni**: Centralizovat do `_helpers.py` — kratky i dlouhy format. Sablony importuji z kontextu.
- **Narocnost + cas**: nizka, ~5 min
- **Zavislosti**: zadne
- **Regrese riziko**: nizke
- **Jak otestovat**: Overit ze mesice se zobrazuji spravne na vsech strankach.

#### N20 — LOW: Dynamicky pridavany atribut na ORM objektu
- **Co a kde**: `payment_overview.py:188` a `settlement_service.py:173` — `payment.alloc_amount = alloc.amount` dynamicky pridava atribut na SQLAlchemy objekt. Sablona pak pouziva `p.alloc_amount if p.alloc_amount is defined`.
- **Reseni**: Varianty: (A) Vytvorit namedtuple/dataclass `PaymentWithAlloc(payment, alloc_amount)`. (B) Ponechat — funguje to, je to jednoduche.
- **Narocnost + cas**: nizka/stredni, ~15 min
- **Zavislosti**: zadne
- **Regrese riziko**: nizke
- **Jak otestovat**: Detail platby jednotky a detail vyuctovani — overit castky.

#### N21 — LOW: Duplicitni payment list sablona
- **Co a kde**: `jednotka_platby.html:86-113` a `vyuctovani_detail.html:154-183` — temer identicky blok kodu pro zobrazeni seznamu plateb.
- **Reseni**: Extrahovat do `partials/_payment_list.html` a includovat na obou mistech.
- **Narocnost + cas**: nizka, ~15 min
- **Zavislosti**: zadne
- **Regrese riziko**: nizke
- **Jak otestovat**: Zobrazit detail plateb jednotky i detail vyuctovani — overit vizualni shodu.

---

### 2. Bezpecnost

#### N1 — CRITICAL: Path traversal pres `saved_path` (viz vyse)

Uzivatel muze poslat libovolnou cestu v hidden input `saved_path`. Server cte obsah souboru z teto cesty bez validace:
```python
saved_file = Path(saved_path)  # LIBOVOLNA CESTA
file_content = saved_file.read_bytes()  # CTENI BEZ VALIDACE
```
Utocnik muze precist libovolny soubor na serveru (`/etc/passwd`, `data/svj.db`).

#### N6 — HIGH: Float pro penezni castky
- **Co a kde**: `payment.py` — vsechny financni sloupce pouzivaji `Float` (amount, monthly_total, opening_amount, result_amount, cost_building, paid, result atd.). SQLite Float je IEEE 754 double, ktery ma inherentni zaokrouhlovaci chyby u desitkovych hodnot.
- **Reseni**: Varianty: (A) Prejit na `Numeric(precision=10, scale=2)` — umi presne desitky, vyzaduje migraci. (B) Ponechat Float, ale dusledne pouzivat `round()` pri vsech vypoctech. (C) Pouzivat Integer (halerove castky) — nejpresnejsi, ale vyzaduje prepis celeho modulu.
- **Pro/proti**: (A) je nejlepsi kompromis, ale SQLite Numeric se chova jako Float, takze skutecny prinos je limitovany. Doporucuji variantu (B) — uz se dela v `settlement_service.py`, ale chybi na dalsich mistech.
- **Narocnost + cas**: stredni, ~2 hod pro kompletni audit a round() doplneni
- **Zavislosti**: zadne
- **Regrese riziko**: stredni — zaokrouhleni muze zmenit existujici data o halerove castky
- **Jak otestovat**: Generovat vyuctovani, overit ze vysledky sedi s manualnim vypoctem.

#### Pozitivni nalezy (bez problemu):
- **SQL injection**: Vsechny DB dotazy pouzivaji SQLAlchemy ORM (parametrizovane). Zadne f-stringy v SQL.
- **XSS**: Jinja2 auto-escaping je zapnuty. Uzivatelske vstupy v sablobach jsou escapovane.
- **CSRF**: Projekt nepouziva CSRF tokeny (FastAPI default), ale je to lokalni aplikace bez autentizace.
- **File upload validace**: Pouziva se `validate_upload()` s centralizovanymi limity — OK.
- **LIKE escape**: V `symbols.py:40-44` se spravne escapuji `%` a `_` v LIKE dotazech.

---

### 3. Dokumentace

#### N18 — LOW: Hardcoded "1098" bez vysvetleni
- **Co a kde**: `payment_matching.py:259` — funkce `_extract_unit_from_vs` hleda retezec "1098" v VS cisle. Toto je pravdepodobne specificky prefix pro toto SVJ, ale v kodu chybi jakekoliv vysvetleni.
- **Reseni**: Pridat komentar vysvetlujici puvod prefixu. Idealne extrahovat do konstanty `VS_PREFIX = "1098"`.
- **Narocnost + cas**: nizka, ~5 min
- **Zavislosti**: zadne
- **Regrese riziko**: nulove
- **Jak otestovat**: Automaticky — zadny dopad na runtime.

#### N25 — LOW: Magicke hodnoty v matching logice
- **Co a kde**: `payment_matching.py` — vice magickych cisel:
  - Radek 29: slova > 3 znaky (proc ne 2 nebo 4?)
  - Radek 119: `len(common) >= 2` (proc prave 2?)
  - Radek 132: `monthly > payment.amount * 10` (proc 10x?)
  - Radek 554: `score >= 5` (proc prave 5?)
- **Reseni**: Pridat komentare vysvetlujici volbu hodnot, idealne extrahovat do pojmenovanych konstant (`MIN_WORD_LENGTH = 3`, `MIN_COMMON_WORDS = 2`, `MAX_PRESCRIPTION_RATIO = 10`, `MIN_MATCH_SCORE = 5`).
- **Narocnost + cas**: nizka, ~10 min
- **Zavislosti**: zadne
- **Regrese riziko**: nulove
- **Jak otestovat**: Automaticky — zadny dopad na runtime.

#### Pozitivni nalezy:
- **Docstringy**: Vsechny hlavni funkce maji popisne docstringy (match_payments, compute_candidates, compute_payment_matrix, generate_settlements).
- **Modely v __init__.py**: Vsechny modely a enumy jsou spravne exportovane.
- **Indexy v _ensure_indexes()**: Vsechny FK a filtrovaci sloupce payment modulu maji indexy v `_ensure_indexes()` — sedi s modely.

---

### 4. UI / Sablony

#### N14 — MEDIUM: Duplicitni formulare v vypis_tbody.html
- **Co a kde**: `vypis_tbody.html:29-73` — pro kazdy SUGGESTED platbu s potvrdit/odmitnout tlacitky je 14 hidden inputu (7 pro potvrdit, 7 pro odmitnout). Toto se opakuje pro single-unit i multi-unit varianty. S 50 navrzenym platbami je to 1400 hidden inputu.
- **Reseni**: Varianty: (A) Presunout filtrovaci hidden inputy do jednoho spolecneho formulare a pouzit JS k prepinani action URL. (B) Ponechat — funkcionalne spravne, jen verbozni.
- **Narocnost + cas**: stredni, ~20 min
- **Zavislosti**: zadne
- **Regrese riziko**: stredni — zmena formulare muze rozbit HTMX interakce
- **Jak otestovat**: (1) Otevrit detail vypisu s navrhy. (2) Potvrdit navrh. (3) Odmitnout navrh. (4) Overit ze filtry a scroll pozice se zachovaji.

#### N17 — MEDIUM: Formulare nezachovavaji pole pri chybe
- **Co a kde**: `predpisy_import.html` a `vypis_import.html` — pri validacni chybe v import vypisu se formular zobrazi prazdny (bez `form_data` predaneho zpet). V `statements.py` error kontexty nepredavaji `form_data`.
- **Reseni**: Pridat `"form_data": {...}` do vsech error kontextu v `vypis_import_upload()`. Poznamka: u CSV importu neni co zachovavat (zadny textovy input krome souboru), takze dopad je minimalni.
- **Narocnost + cas**: nizka, ~10 min
- **Zavislosti**: zadne
- **Regrese riziko**: nizke
- **Jak otestovat**: Na importu vypisu odeslat nevalidni soubor — overit chybovou hlasku.

#### Pozitivni nalezy:
- **Konzistence UI**: Vsechny stranky pouzivaji konzistentni Tailwind tridy, dark mode podpora, sticky hlavicky.
- **HTMX interakce**: Spravne `hx-target`, `hx-swap`, `hx-trigger="keyup changed delay:300ms"`. Loading indikatory u importu.
- **Back URL propagace**: Spravne implementovana na vsech strankach — bubliny, razeni, hledani zachovavaji `back` parametr.
- **Pristupnost**: Label elementy u formularu, `title` atributy na tlacitcich, `data-confirm` na destruktivnich akcich.
- **`hx-boost="false"`**: Spravne na vsech file inputech a delete formularich.
- **Scroll restore**: Sdileny `_scroll_restore.html` partial s highlight efektem.
- **Klikaci entity**: Vsechny entity (jednotky, vlastnici) jsou klikaci s back URL.
- **Razitelne sloupce**: Vsechny datove tabulky maji razitelne sloupce.
- **Search HTMX**: Vsechny seznamove stranky maji HTMX search s debounce.

---

### 5. Vykon

#### N2 — HIGH: N+1 dotazy v payment_matching.py
- **Co a kde**: `payment_matching.py` — tri mista s N+1 problemem:
  1. **Radek 60**: `db.query(Unit).get(p.unit_id)` uvnitr cyklu pres vsechny predpisy (compute_candidates) — potencialne 100+ dotazu.
  2. **Radek 89-91**: `db.query(Owner).get(ou.owner_id)` + `db.query(Unit).get(ou.unit_id)` pro kazdy aktivni OwnerUnit — potencialne 200+ dotazu.
  3. **Radky 411, 507**: `db.query(Owner).get(ou.owner_id)` v cyklu v match_payments() faze 2 a 3 — potencialne 100+ dotazu.
- **Reseni**: Nacist vsechny Unit/Owner najednou pred cyklem:
  ```python
  units_by_id = {u.id: u for u in db.query(Unit).all()}
  owners_by_id = {o.id: o for o in db.query(Owner).all()}
  ```
- **Narocnost + cas**: stredni, ~30 min
- **Zavislosti**: zadne
- **Regrese riziko**: nizke — meni jen zpusob nacitani, ne logiku
- **Jak otestovat**: (1) Importovat CSV vypis s 50+ platbami. (2) Merit cas importu pred a po oprave. (3) Overit ze vysledky parovani jsou shodne.

#### N3 — HIGH: `_count_debtors_fast` neni tak fast
- **Co a kde**: `_helpers.py:76-141` — funkce nacita vsechny predpisy, vsechny platby (pres alokace), vsechny zustatky pro rok do pameti. Potom iteruje v Pythonu. Pro 100 jednotek a 1000 plateb to je 3+ dotazy + Python iterace. Funkce se vola na **kazdem** page loadu (cela navigace ho pouziva).
- **Reseni**: Presunout vypocet do jedineho SQL dotazu s GROUP BY a HAVING. Nebo cachovat vysledek per rok (cislo dluziku se meni jen pri importu/parovani).
- **Narocnost + cas**: stredni, ~20 min
- **Zavislosti**: zadne
- **Regrese riziko**: stredni — SQL optimalizace muze mit jiny vysledek nez Python logika
- **Jak otestovat**: Porovnat cislo dluziku pred a po optimalizaci.

#### N11 — MEDIUM: N+1 v compute_candidates()
- **Co a kde**: `payment_matching.py:60` — `db.query(Unit).get(p.unit_id)` pro kazdy predpis s unit_id.
- **Reseni**: Zahrnut v oprave N2.
- **Zavislosti**: zavisi na N2
- **Regrese riziko**: nizke
- **Jak otestovat**: viz N2

#### N12 — MEDIUM: Dvojite volani compute_payment_matrix
- **Co a kde**: `payment_overview.py:148-153` — `compute_debtor_list()` vola `compute_payment_matrix(db, year)` a pak filtruje vysledek. Kazdy endpoint vola jednu z techto funkci oddelene, ale neni zadny sdileny cache.
- **Reseni**: Varianta (A): cachovat na urovni requestu. Varianta (B): akceptovatelne — kazdy endpoint vola jednu funkci.
- **Narocnost + cas**: nizka, ~10 min
- **Zavislosti**: zadne
- **Regrese riziko**: nizke
- **Jak otestovat**: Overit ze dluznici stale ukazuji spravna data po optimalizaci.

#### N13 — MEDIUM: compute_nav_stats na kazdem requestu
- **Co a kde**: `_helpers.py:23-73` — kazdy endpoint platebniho modulu vola `compute_nav_stats(db)`, ktery provede 7+ DB dotazu (years, vs_count, prescriptions, statements, payments, debtors, settlements, balances). Na kazdem page loadu.
- **Reseni**: Varianty: (A) Cachovani s kratkym TTL (~5s). (B) Lehci verze — misto pocitani dluziku ukazovat jen pocet predpisu/plateb. (C) Akceptovatelne pro lokalni SQLite — 7 jednoduchych dotazu trvaji < 10ms.
- **Narocnost + cas**: stredni, ~30 min (pro implementaci caching)
- **Zavislosti**: zadne
- **Regrese riziko**: stredni — caching muze ukazovat stara data
- **Jak otestovat**: Overit ze navigacni statistiky se aktualizuji po importu.

---

### 6. Error Handling

#### N15 — MEDIUM: Chybejici error handling pri match_payments
- **Co a kde**: `statements.py:294` — `match_payments(db, statement.id, year)` se vola bez try/except. Pokud matching selze (napr. chyba v DB), cely import selze a data zustanou v nekonzistentnim stavu (platby vlozeny, ale nenaprovany).
- **Reseni**: Obalit do try/except, pri chybe nastavit match_result na nulove hodnoty a pridat warning do flash zpravy.
- **Narocnost + cas**: nizka, ~5 min
- **Zavislosti**: zadne
- **Regrese riziko**: nizke
- **Jak otestovat**: Tezko — vyzaduje simulaci chyby v match_payments.

#### N16 — MEDIUM: compute_unit_payment_detail vraci None
- **Co a kde**: `payment_overview.py:157` — `compute_unit_payment_detail()` muze vratit `None` kdyz jednotka neexistuje. Router `overview.py:216` uz tento pripad korektne handluje — `detail` muze byt None a sablona ho testuje (`{% if detail %}`).
- **Reseni**: Pridat explicitni kontrolu v routeru: `if not detail: return RedirectResponse(...)` — pro jasnejsi kod.
- **Narocnost + cas**: nizka, ~5 min
- **Zavislosti**: zadne
- **Regrese riziko**: nizke
- **Jak otestovat**: Navstivit `/platby/jednotka/999999` — overit ze se zobrazi prazdna zprava, ne error.

#### N24 — LOW: Rok validace bez uzivatelske zpravy
- **Co a kde**: `balances.py:106-107` — pokud rok je mimo rozsah 2020-2040, vraci redirect s `flash=chyba_rok`, ale na strance zustatku se tento flash parametr neprekonvertuje na zpravu (chybi vetev v flash_param handlingu na radku 64-69).
- **Reseni**: Pridat vetev `elif flash_param == "chyba_rok": flash_message = "Rok musi byt mezi 2020 a 2040."`.
- **Narocnost + cas**: nizka, ~5 min
- **Zavislosti**: zadne
- **Regrese riziko**: nulove
- **Jak otestovat**: Zkusit pridat zustatek s rokem 2050 — overit ze se zobrazi chybova zprava.

---

### 7. Git Hygiene

#### N22 — LOW: Testovaci CSV v koreni projektu
- **Co a kde**: `test_vypis.csv` (110 KB) — netrackovan soubor v Git. Pravdepodobne pozustatek z manualniho testovani importu.
- **Reseni**: Smazat nebo pridat do `.gitignore`.
- **Narocnost + cas**: nizka, ~1 min
- **Zavislosti**: zadne
- **Regrese riziko**: nulove
- **Jak otestovat**: Automaticky — zadny dopad.

#### Pozitivni nalezy:
- **Commit messages**: Vsech 20 commitu ma srozumitelne ceske commit messages s prefixy (feat, fix, ui).
- **Commit granularita**: Kazdy commit resi jednu vec — bez michanich zmen.
- **.gitignore**: Neni viditelny problem s citlivymi daty v repozitari.
- **Zadne soubory v .playwright-mcp/**: Cisto.

---

### 8. Testy

#### N23 — LOW: Nulove pokryti testy
- **Co a kde**: Neexistuje zadny `test_payment*.py`. Projekt ma testy pro import_mapping, email_service, contact_import, voting_aggregation, a smoke test — ale ZADNE pro platebni modul.
- **Reseni**: Vytvorit testy pro kriticke flows:
  1. `test_payment_matching.py` — unit testy pro `match_payments()`, `_check_amount_match()`, `_extract_unit_from_vs()`, `_find_name_matches()`, `_find_multi_unit_match()`
  2. `test_payment_overview.py` — testy pro `compute_payment_matrix()`, `compute_debtor_list()`
  3. `test_settlement_service.py` — testy pro `generate_settlements()`
- **Narocnost + cas**: vysoka, ~4 hod
- **Zavislosti**: zadne
- **Regrese riziko**: nulove — testy pridavaji, nic nemeni
- **Jak otestovat**: `pytest tests/ -v`

#### Prioritni test scenare:
- **match_payments**: Platba s VS -> auto match. Platba bez VS, s jmenem -> suggested. Multi-unit match. VS prefix dekodovani. Duplicitni operation_id -> preskocit.
- **compute_payment_matrix**: Jednotka s predpisem bez plateb -> dluh. Castecna platba -> partial. Overeni mesicnich statusu.
- **generate_settlements**: Presny vypocet nedoplatku/preplatku. Upsert logika (update existujiciho).
- **_extract_unit_from_vs**: Ruzne formaty VS. Neexistujici jednotka. Prazdny VS.

---

## Doporuceny postup oprav

### 1. Ihned (CRITICAL)
1. **N1**: Path traversal validace `saved_path` (~15 min)

### 2. Vysoka priorita (HIGH)
2. **N2**: N+1 v payment_matching.py (~30 min)
3. **N4**: Duplicitni `active_tab` klic (~2 min)
4. **N3**: Optimalizace `_count_debtors_fast` (~20 min)
5. **N5**: Refactoring dlouhych souboru (~1 hod) — doporucuji po pridani testu (N23)
6. **N6**: Float vs Numeric rozhodnuti (~2 hod) — rozhodnout variantu

### 3. Stredni priorita (MEDIUM)
7. **N7**: Nepouzite importy (~1 min)
8. **N8**: Duplicitni komentare (~1 min)
9. **N9**: Inline import asc/desc (~5 min)
10. **N15**: Error handling match_payments (~5 min)
11. **N16**: None handling v overview (~5 min)
12. **N24**: Flash zprava pro chybny rok (~5 min)
13. **N14**: Duplicitni hidden inputy (~20 min)
14. **N13**: Nav stats optimalizace (~30 min)
15. **N10**: Inline importy v matching (~10 min)
16. **N11**: N+1 v compute_candidates (~15 min, soucast N2)
17. **N12**: Dvojite volani matrix (~10 min)
18. **N17**: Zachovani formularu pri chybe (~10 min)

### 4. Nizka priorita (LOW) — naplanovat do dalsich iteraci
19. **N22**: Smazat test_vypis.csv (~1 min)
20. **N18**: Komentar k "1098" (~5 min)
21. **N25**: Komentare k magickym hodnotam (~10 min)
22. **N19**: Centralizace MONTH_NAMES (~5 min)
23. **N20**: alloc_amount dynamicky atribut (~15 min)
24. **N21**: Extrakce payment list partialu (~15 min)
25. **N23**: Testy pro platebni modul (~4 hod)

---

## Celkovy odhad casu oprav

| Priorita | Pocet | Cas       |
|----------|-------|-----------|
| CRITICAL | 1     | ~15 min   |
| HIGH     | 5     | ~4.5 hod  |
| MEDIUM   | 11    | ~2 hod    |
| LOW      | 8     | ~5 hod    |
| **Celkem** | **25** | **~11.5 hod** |

Pozn.: CRITICAL a HIGH opravy (bez N5 a N6 ktere vyzaduji rozhodnuti) = ~1 hod. S testama (N23) = ~5 hod.
