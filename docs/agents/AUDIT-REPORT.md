# SVJ Audit Report — Platby + Prostory + Nájemci — 2026-03-24

> Scope: app/routers/payments/, app/routers/spaces/, app/routers/tenants/, app/services/balance_import.py, app/services/payment_matching.py, app/services/payment_overview.py, app/models/payment.py, app/models/space.py, app/templates/payments/, app/templates/spaces/, app/templates/tenants/
>
> Focus: změny od 2026-03-22 (předchozí audit). Nálezy z předchozího auditu (N1–N25) nejsou opakovány.

## Souhrn

- **CRITICAL**: 1
- **HIGH**: 3
- **MEDIUM**: 5
- **LOW**: 4

## Souhrnná tabulka

| #  | Oblast       | Soubor                                      | Severity | Problém                                                                 | Čas      | Rozhodnutí |
|----|-------------|----------------------------------------------|----------|-------------------------------------------------------------------------|----------|------------|
| 1  | Bezpečnost  | import_spaces.py:247-258                     | CRITICAL | Replace mód importu maže VŠECHNY nájemce (i ručně založené mimo import) | ~15 min  | :wrench:   |
| 2  | Kód         | spaces/crud.py:665                           | HIGH     | `flash_type = "error"` nastaveno ale nepředáno do template kontextu     | ~2 min   | :wrench:   |
| 3  | Kód         | balance_import.py:90                         | HIGH     | SJM matching — `name_normalized.split()[0] in excel_norm` je příliš volný | ~15 min  | :wrench:   |
| 4  | Kód         | statements.py:464-475                        | HIGH     | Špatný GROUP BY pro typ bubble counts — `isnot(None)` v SELECT vs GROUP BY | ~10 min  | :wrench:   |
| 5  | Kód         | symbols.py:88-99                             | MEDIUM   | Flash `upraveno` není zpracován v GET endpointu → tichý redirect bez zprávy | ~2 min   | :wrench:   |
| 6  | Kód         | symbols.py:206-207                           | MEDIUM   | VS edit: prázdný `variable_symbol` přijat bez varování (jen se přeskočí update) | ~5 min   | :wrench:   |
| 7  | Modely      | space.py (všech 6 instancí), payment.py (13 instancí) | MEDIUM   | `datetime.utcnow` (deprecated) v column defaults — routery používají `utcnow()` | ~15 min  | :wrench:   |
| 8  | Kód         | spaces/crud.py:158 + 368                     | MEDIUM   | Inline import `from datetime import date as date_type` uvnitř funkce (2×) | ~2 min   | :wrench:   |
| 9  | Kód         | tenants/crud.py (žádný flash_type)           | MEDIUM   | Tenant detail nemá `flash_type` v kontextu → error flash se zobrazí bez stylu | ~2 min   | :wrench:   |
| 10 | Kód         | spaces/crud.py:130-131                       | LOW      | Parsování jména nájemce `parts[0]` = příjmení — nefunguje pro složená jména | ~10 min  | :question: |
| 11 | Kód         | import_spaces.py:248                         | LOW      | Inline import `from app.models import SpaceTenant...` uvnitř if bloku   | ~2 min   | :wrench:   |
| 12 | Kód         | balance_import.py:85                         | LOW      | SJM detekce přes `"SJM" in ownership_type.upper()` — citlivé na formát dat | ~5 min   | :question: |
| 13 | Kód         | tenants/crud.py:260-274                      | LOW      | `_address_ctx` duplikuje logiku pro perm/corr — refaktor přes `getattr()` | ~10 min  | :wrench:   |

Legenda: :wrench: = jen opravit, :question: = potřeba rozhodnutí uživatele (více variant)

---

## Detailní nálezy

### 1. Bezpečnost

#### N1 — CRITICAL: Replace mód importu maže VŠECHNY nájemce včetně ručně založených

- **Co a kde**: `import_spaces.py:247-258` — při `import_mode == "replace"` se volá `db.query(SpaceTenant).delete()` a `db.query(Tenant).delete()` **bez filtru**. To smaže VŠECHNY nájemce v DB — nejen ty vytvořené předchozím importem, ale i ručně založené nájemce, nájemce propojené s vlastníky atd.
- **Řešení**: Mazat pouze záznamy svázané s prostory: `db.query(SpaceTenant).filter(SpaceTenant.space_id.in_(db.query(Space.id))).delete(synchronize_session=False)` a poté nájemce bez aktivních vztahů, nebo použít kaskádní delete přes Space.
- **Varianty**: (A) Smazat jen SpaceTenant + Space, nájemce ponechat (bezpečnější). (B) Smazat nájemce které nemají `owner_id` (standalone), propojené ponechat.
- **Náročnost + čas**: nízká, ~15 min
- **Závislosti**: žádné
- **Regrese riziko**: střední — je třeba ověřit že import stále funguje korektně po omezení mazání
- **Jak otestovat**: (1) Ručně vytvořit nájemce. (2) Importovat prostory v replace módu. (3) Ověřit že ručně vytvořený nájemce přežil.

---

### 2. Kódová kvalita

#### N2 — HIGH: `flash_type` nastaveno ale nepředáno do kontextu

- **Co a kde**: `spaces/crud.py:665` — v `space_detail()` se nastaví `flash_type = "error"` pro případ `flash == "tenant_not_found"`, ale proměnná `flash_type` není deklarována na řádku 658 (kde je jen `flash_message = None`) a **není předána do template kontextu** na řádku 667-677. Kód nastaví lokální proměnnou, kterou nikdo nečte. V důsledku se `flash_message` "Nájemce nenalezen." zobrazí jako neutrální toast místo červeného error toastu.
- **Řešení**: (1) Přidat `flash_type = None` na řádek 658. (2) Přidat `"flash_type": flash_type` do template kontextu na řádku 676.
- **Náročnost + čas**: nízká, ~2 min
- **Závislosti**: žádné
- **Regrese riziko**: nulové
- **Jak otestovat**: (1) Na stránce detailu prostoru zkusit přiřadit neexistujícího nájemce. (2) Ověřit že flash zpráva má červený (error) styl.

#### N3 — HIGH: SJM matching logika je příliš volná — false positives

- **Co a kde**: `balance_import.py:90` — `o.name_normalized.split()[0] in excel_norm` kontroluje zda **první slovo** jména vlastníka (příjmení) je **obsaženo jako substring** v normalizovaném Excel jménu. Problém: krátká příjmení (např. "Novak") se mohou vyskytovat jako substring v nesouvisejících jménech (např. "Novaková Jana + SJM Novakovic Petr"). Operátor `in` dělá substring match, ne word match.
- **Řešení**: Použít word-level match: `o.name_normalized.split()[0] in excel_norm.split()` — porovnává celá slova místo substring. Nebo použít stávající `_match_owner()` funkci s vyšším prahem.
- **Náročnost + čas**: nízká, ~15 min
- **Závislosti**: žádné
- **Regrese riziko**: nízké — může způsobit méně matchů u SJM (lepší než false positives)
- **Jak otestovat**: (1) Vytvořit SJM vlastníky s podobnými příjmeními. (2) Importovat zůstatky s Excel jménem obsahujícím substring příjmení. (3) Ověřit že se páruje jen správný vlastník.

#### N4 — HIGH: Špatný GROUP BY pro typ bubble counts

- **Co a kde**: `statements.py:464-475` — dotaz `group_by(Payment.unit_id.isnot(None), Payment.space_id.isnot(None))` seskupí platby podle boolean výrazů (True/False), ale SELECT vrací `Payment.unit_id, Payment.space_id, func.count()` — tedy konkrétní hodnoty sloupců, ne boolean výrazy. SQLite vrací **libovolný** `unit_id`/`space_id` z každé skupiny. Kód pak testuje `if unit_id:` a `if space_id:`, ale pro skupinu kde jsou i NULL i non-NULL hodnoty dostane jen jednu z nich.
- **Řešení**: Změnit SELECT aby odpovídal GROUP BY: `db.query(Payment.unit_id.isnot(None).label('has_unit'), Payment.space_id.isnot(None).label('has_space'), func.count())` a `.group_by('has_unit', 'has_space')`. Nebo jednodušeji dva samostatné count dotazy.
- **Náročnost + čas**: nízká, ~10 min
- **Závislosti**: žádné
- **Regrese riziko**: nízké — opravuje existující bug, výsledky budou přesnější
- **Jak otestovat**: (1) Importovat výpis s platbami párovanými na jednotky i prostory. (2) Ověřit že bubliny Jednotky/Prostory v detailu výpisu ukazují správné počty.

#### N5 — MEDIUM: Flash zpráva `upraveno` chybí v GET endpointu

- **Co a kde**: `symbols.py:221` odesílá redirect s `flash="upraveno"`, ale GET endpoint `symboly_seznam()` na řádcích 92-99 zpracovává jen flash hodnoty `ok` a `smazano`. Flash `upraveno` se tiše ztratí — uživatel po úpravě VS nevidí potvrzení.
- **Řešení**: Přidat `elif flash_param == "upraveno": flash_message = "Variabilní symbol upraven."` do flash zpracování.
- **Náročnost + čas**: nízká, ~2 min
- **Závislosti**: žádné
- **Regrese riziko**: nulové
- **Jak otestovat**: (1) Upravit VS v inline editaci. (2) Ověřit že se zobrazí toast "Variabilní symbol upraven."

#### N6 — MEDIUM: Prázdný VS při editaci se tiše přeskočí

- **Co a kde**: `symbols.py:207` — `if vs_clean and vs_clean != mapping.variable_symbol:` — pokud uživatel smaže VS v input poli a odešle formulář, `vs_clean` je prázdný string, podmínka `if vs_clean` je False, a VS se nezmění. Uživatel si myslí že uložil prázdné VS, ale ve skutečnosti zůstalo staré. Chybí validace + chybová zpráva.
- **Řešení**: Přidat validaci: pokud `not vs_clean`, vrátit redirect s `chyba="prazdny"`.
- **Náročnost + čas**: nízká, ~5 min
- **Závislosti**: žádné
- **Regrese riziko**: nulové
- **Jak otestovat**: (1) Otevřít inline edit VS. (2) Smazat VS a odeslat. (3) Ověřit že se zobrazí chyba "VS nesmí být prázdný".

#### N7 — MEDIUM: `datetime.utcnow` (deprecated) v modelech Space a Payment

- **Co a kde**: `space.py:40-41, 102-103, 181-182` a `payment.py:73-74, 95-96, 120, 140-141, 182, 212-213, 232, 272-273` — celkem 19 instancí `datetime.utcnow` v column defaults/onupdate. Python 3.12+ deprecated `datetime.utcnow()`. Routery a services správně používají `utcnow()` z `app.utils`, ale modely stále mají starý tvar.
- **Řešení**: Nahradit `datetime.utcnow` za `utcnow` z `app.utils`:
  ```python
  from app.utils import utcnow
  created_at = Column(DateTime, default=utcnow)
  updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
  ```
- **Náročnost + čas**: nízká, ~15 min (mechanická náhrada)
- **Závislosti**: žádné (ale pozor: mělo by se udělat i v ostatních modelech mimo scope auditu)
- **Regrese riziko**: nízké — `utcnow()` vrací stejný typ jako `datetime.utcnow()`
- **Jak otestovat**: Vytvořit prostor/nájemce, ověřit že `created_at` má korektní timestamp.

#### N8 — MEDIUM: Inline import `from datetime import date as date_type` uvnitř funkcí

- **Co a kde**: `spaces/crud.py:158` (v `space_create`) a `spaces/crud.py:368` (v `space_assign_tenant`) — import `from datetime import date as date_type` je uvnitř těla funkce. Modul už importuje `from datetime import datetime` na řádku 3.
- **Řešení**: Přesunout `from datetime import date as date_type` na začátek souboru, nebo použít `datetime.date` přímo (z existujícího importu).
- **Náročnost + čas**: nízká, ~2 min
- **Závislosti**: žádné
- **Regrese riziko**: nulové
- **Jak otestovat**: Vytvořit prostor s nájemcem a datem smlouvy — ověřit že se uloží korektně.

#### N9 — MEDIUM: Tenant detail nemá `flash_type` v kontextu

- **Co a kde**: `tenants/crud.py:577-629` — endpoint `tenant_detail()` zpracovává flash zprávy (`linked`, `unlinked`), ale nepředává `flash_type` do template kontextu. Pokud by se v budoucnu přidala error flash zpráva (jako v spaces), chyběl by error styl. Momentálně jen preventivní — žádná error flash se nepoužívá.
- **Řešení**: Přidat `flash_type = None` a `"flash_type": flash_type` do kontextu pro konzistenci s ostatními moduly.
- **Náročnost + čas**: nízká, ~2 min
- **Závislosti**: žádné
- **Regrese riziko**: nulové
- **Jak otestovat**: N/A — preventivní oprava.

#### N10 — LOW: Parsování jména nájemce při vytváření prostoru

- **Co a kde**: `spaces/crud.py:130-131` — `parts = tenant_name.split(); last_name = parts[0]` předpokládá formát "příjmení jméno". Funguje pro jednoduché české jméno ("Novák Jan"), ale selže pro složená jména ("Van Der Berg Jan") nebo firemní názvy.
- **Řešení**: Varianty: (A) Přidat samostatná pole pro jméno a příjmení do formuláře. (B) Ponechat — pro rychlé vytvoření prostoru s nájemcem je to akceptovatelné, detaily lze upravit v detailu nájemce.
- **Náročnost + čas**: střední, ~10 min (varianta A)
- **Závislosti**: žádné
- **Regrese riziko**: nízké
- **Jak otestovat**: Vytvořit prostor s nájemcem "Van Der Berg Jan" — ověřit jak se rozparsuje.

#### N11 — LOW: Inline import uvnitř `if import_mode == "replace"`

- **Co a kde**: `import_spaces.py:248` — `from app.models import SpaceTenant, Tenant, VariableSymbolMapping, Prescription` je uvnitř if bloku. Tyto modely by měly být importovány na začátku souboru (většina z nich se už používá v jiných částech kódu, nebo je dostupná přes top-level importy).
- **Řešení**: Přesunout import na začátek souboru. Zkontrolovat cirkulární závislosti.
- **Náročnost + čas**: nízká, ~2 min
- **Závislosti**: žádné
- **Regrese riziko**: nízké
- **Jak otestovat**: `python -c "from app.routers.spaces.import_spaces import router"` — ověřit že import proběhne.

#### N12 — LOW: SJM detekce přes substring `"SJM"` v ownership_type

- **Co a kde**: `balance_import.py:85` — `"SJM" in (ou.ownership_type or "").upper()` detekuje SJM přes substring match. Pokud by existoval ownership_type obsahující "SJM" jako součást jiného slova (nepravděpodobné, ale možné), dal by false positive.
- **Řešení**: Porovnávat přesně: `(ou.ownership_type or "").upper().strip() == "SJM"` nebo `.startswith("SJM")`.
- **Náročnost + čas**: nízká, ~5 min
- **Závislosti**: záleží na formátu dat v DB (jaké hodnoty `ownership_type` existují)
- **Regrese riziko**: nízké
- **Jak otestovat**: Zkontrolovat DB: `SELECT DISTINCT ownership_type FROM owner_units`.

#### N13 — LOW: Duplikovaná logika pro perm/corr adresu

- **Co a kde**: `tenants/crud.py:260-274` — `_address_ctx()` duplikuje 5 polí (street, district, city, zip, country) v if/else pro prefix `perm` vs `corr`.
- **Řešení**: Použít `getattr(tenant, f"{prefix}_street")` atd. v jedné větvi.
- **Náročnost + čas**: nízká, ~10 min
- **Závislosti**: žádné
- **Regrese riziko**: nízké
- **Jak otestovat**: Editovat obě adresy nájemce — ověřit že se správně zobrazují a ukládají.

---

### 3. Pozitivní nálezy (bez problémů)

- **Path traversal**: `import_spaces.py` správně validuje `is_safe_path()` na všech endpointech s `file_path` (řádky 109, 175, 225).
- **SQL injection**: Všechny dotazy používají SQLAlchemy ORM — žádné raw SQL.
- **XSS**: Jinja2 auto-escaping je zapnutý. Žádné `|safe` filtry na uživatelský vstup.
- **HTMX interakce**: `hx-boost="false"` na formulářích v symboly.html (řádek 185).
- **Back URL**: Správně implementováno v spaces/crud.py i tenants/crud.py.
- **Eager loading**: Všechny detail stránky mají `joinedload()` pro relace.
- **Flash zprávy**: spaces/crud.py a tenants/crud.py mají flash zprávy pro hlavní akce.
- **Payment matching konstanty**: Předchozí audit (N18, N25) byl opravený — konstanty `VS_PREFIX`, `MIN_WORD_LENGTH`, `MIN_COMMON_WORDS`, `MAX_PRESCRIPTION_RATIO`, `MIN_MATCH_SCORE` jsou definovány na řádcích 30-38 s komentáři.
- **Error handling match_payments**: Předchozí audit N15 opravený — `try/except` na řádku 305-309 v statements.py.
- **Inline import asc/desc opravený**: symbols.py má `from sqlalchemy import asc as sa_asc, desc as sa_desc` na top-level.
- **Tenants CRUD**: Kvalitní inline edit s per-section formuláři (identita, kontakt, adresa). Propojení s vlastníkem kopíruje data při odpojení.

---

## Doporučený postup oprav

### 1. Ihned (CRITICAL)
1. **N1**: Replace mód importu prostorů — omezit mazání na svázané záznamy (~15 min)

### 2. Vysoká priorita (HIGH)
2. **N2**: `flash_type` nepředáno v spaces/detail (~2 min)
3. **N3**: SJM matching — substring vs word match (~15 min)
4. **N4**: GROUP BY bug v typ bubble counts (~10 min)

### 3. Střední priorita (MEDIUM)
5. **N5**: Flash `upraveno` chybí (~2 min)
6. **N6**: Prázdné VS při editaci (~5 min)
7. **N7**: `datetime.utcnow` deprecated v modelech (~15 min)
8. **N8**: Inline import datetime (~2 min)
9. **N9**: Chybějící `flash_type` v tenant detail (~2 min)

### 4. Nízká priorita (LOW)
10. **N10**: Parsování jména nájemce (~10 min, rozhodnutí)
11. **N11**: Inline import v replace mód (~2 min)
12. **N12**: SJM detekce substring (~5 min, rozhodnutí)
13. **N13**: Duplikovaná adresní logika (~10 min)

---

## Celkový odhad času oprav

| Priorita   | Počet | Čas       |
|------------|-------|-----------|
| CRITICAL   | 1     | ~15 min   |
| HIGH       | 3     | ~27 min   |
| MEDIUM     | 5     | ~26 min   |
| LOW        | 4     | ~27 min   |
| **Celkem** | **13** | **~1.5 hod** |

Pozn.: CRITICAL + HIGH opravy = ~42 min. Všechny opravy bez rozhodnutí = ~1 hod.
