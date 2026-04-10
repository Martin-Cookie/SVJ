# SVJ Audit Report – 2026-04-10

> Scope: fokus na poslední 3 commity (64acbe9, 77145dd, 79bcbe9) — model `Tenant` (resolved/active properties), `find_existing_tenant()` helper, tenant create path, detail a export nájemců, template `_row.html` a `detail.html`, migrace `_migrate_dedupe_tenants`. Lehký průchod ostatními oblastmi.

## Souhrn

- CRITICAL: 0
- HIGH: 2
- MEDIUM: 5
- LOW: 6

## Souhrnná tabulka

| # | Oblast | Soubor | Severity | Problém | Čas | Rozhodnutí |
|---|--------|--------|----------|---------|-----|------------|
| 1 | Kód / Bezpečnost | app/routers/tenants/_helpers.py:40-55 | HIGH | `find_existing_tenant()` — match podle samotného jména může nechtěně sloučit jmenovce (homonyma). Dedup při vytváření nájemce tak tiše přesměruje na cizí záznam bez potvrzení | ~30 min | ❓ |
| 2 | UI / UX | app/routers/tenants/crud.py:78-84 | HIGH | `tenant_create` — když `find_existing_tenant` najde shodu, HTMX větev vrátí jen inline HTML s odkazem (uživatel zůstane na formuláři, nevidí co se stalo), non-HTMX větev tiše přesměruje s `?flash=exists`, ale `tenant_detail` `exists` neumí → flash se ztratí | ~15 min | ❓ |
| 3 | Kód | app/routers/tenants/crud.py:648 | MEDIUM | `tenant_detail` stále předává `active_rel` do contextu, ale žádná šablona ho už nepoužívá (po commitu 64acbe9) — mrtvý kód | ~2 min | 🔧 |
| 4 | Kód / Perf | app/models/space.py:167-177 | MEDIUM | `active_space_rel` property volá `active_space_rels` (buduje a sortí list při každém přístupu). V `_filter_tenants` sort="space" se volá 2× per tenant v Python TimSortu. Triviálně cachovatelné | ~10 min | 🔧 |
| 5 | Kód | app/main.py:597-691 | MEDIUM | Migrace `_migrate_dedupe_tenants` — `_key()` pro jmennou větev vrací `None` pro záznamy bez `last_name`/`first_name` (jen `name_with_titles`). Legacy importované záznamy bez rozdělených jmen se nededuplikují a user o tom neví | ~30 min | ❓ |
| 6 | Kód | app/routers/tenants/_helpers.py:132 | MEDIUM | Sort klíč `"space"` stále volá `active_space_rel` (single), zatímco nájemce nově může mít víc prostor. Řazení bere jen první prostor — uživatel to nemusí očekávat | ~10 min | ❓ |
| 7 | Kód | app/routers/spaces/crud.py:135-140 | MEDIUM | `find_existing_tenant` zde dostane POUZE `first_name`/`last_name` (bez `birth_number`). Pokud formulář prostoru vytváří nájemce se jménem, které už existuje pro jinou osobu, dojde k nechtěnému propojení. Pokud je to úmyslné (inline UX), chybí komentář | ~5–15 min | ❓ |
| 8 | Kód | app/routers/spaces/crud.py:131-133 | LOW | `parts = tenant_name.split(); last_name = parts[0]; first_name = parts[1:]` — parsing "Jan Novák" uloží `last="Jan"`. Pre-existing, ale zhoršené tím, že dedup teď matchuje podle `name_normalized` → nekonzistence | ~10 min | ❓ |
| 9 | Bezpečnost | app/routers/tenants/crud.py:81 | LOW | HTMX větev vrací surový f-string s `existing.display_name` — pokud nájemce má titul `<script>`, XSS. Nahradit TemplateResponse (Jinja2 autoescape) | ~10 min | 🔧 |
| 10 | Git hygiene | / (root) | LOW | Reporty `AUDIT-REPORT.md`, `BACKUP-REPORT.md`, `TEST-REPORT.md`, `UX-REPORT.md`, `PREHLED-KOMPLET.md`, `SESSION-START.md` v rootu (~100 KB). `.playwright-mcp/` neexistuje (OK), žádné `*.png`/`*.jpeg` v rootu (OK) | ~5 min | ❓ |
| 11 | UI | app/templates/tenants/partials/_row.html | LOW | `align-top` je dobře, ale sloupce Jméno/Telefon/Email s `nowrap` zanechají velké bílé místo vpravo u nájemců s 3+ prostory | ~10 min | ❓ |
| 12 | Testy | tests/ | LOW | Pro nové chování (1 nájemce = N prostor, dedup, export 1 řádek per smlouva, `resolved_*`, migrace dedupe) neexistují testy | ~2 hod | 🔧 |
| 13 | Dokumentace | CLAUDE.md / README.md | LOW | CLAUDE.md nezmiňuje vzor `find_existing_*`, README nepíše že nájemce může mít více prostor současně (stacked) | ~20 min | 🔧 |

Legenda: 🔧 = jen opravit, ❓ = potřeba rozhodnutí uživatele

---

## Detailní nálezy

### 1. Kódová kvalita + Bezpečnost

#### #1 HIGH — `find_existing_tenant()` příliš volný match podle jména

1. **Co a kde**: `app/routers/tenants/_helpers.py:40-55`. Při vytváření nového nájemce bez RČ/IČ (jen jméno) se dedup opře o `Tenant.name_normalized == name_norm` + `tenant_type`. Dva různí lidé se stejným jménem splynou na jednoho bez potvrzení uživatele.
2. **Řešení**: nepoužít auto-redirect, ale vrátit formulář s bloku `duplicates` + `force_create` (vzor z `app/routers/owners/crud.py` při vytváření vlastníka). User pak explicitně potvrdí "Ano, je to nový záznam" a pošle `force_create=1`.
3. **Varianty**:
   - (a) návrh k potvrzení (doporučeno) — konzistentní s owners.
   - (b) zpřísnit match (jméno + email NEBO jméno + telefon) — funguje pro část případů, ale selže pro nájemce bez kontaktů.
4. **Náročnost**: střední, ~30 min.
5. **Závislosti**: spojeno s #2 a #9 — řešit současně (jeden patch).
6. **Regrese riziko**: nízké — mění chování nového workflow.
7. **Jak otestovat**: `/najemci/novy` → "Jan Novák" FO → uložit. Znovu `/najemci/novy` → "Jan Novák" FO → musí ukázat varování v formuláři s odkazem na existující a checkbox "Přesto vytvořit". Zaškrtnout → vytvoří nový. Bez checkboxu → zůstane na formuláři.

#### #2 HIGH — `tenant_create` tichá/neúplná zpětná vazba při duplicitě

1. **Co a kde**: `app/routers/tenants/crud.py:78-84`. HTMX větev vrátí plain `<p>` (formulář zůstane). Non-HTMX větev dělá `RedirectResponse(f"/najemci/{existing.id}?flash=exists")`, ale `tenant_detail` v GET handleru (řádky 637-642) zpracovává jen `flash == "linked"` / `"unlinked"` — klíč `exists` se zahodí a user nedostane žádné upozornění.
2. **Řešení**: (A) řešit společně s #1 — nahradit celou větev za návrat `_create_form.html` s `duplicates=[existing]`. (B) pokud se zachová redirect, přidat do `tenant_detail` `elif flash == "exists": flash_message = "Nájemce s těmito údaji už existuje."`.
3. **Náročnost**: ~15 min.
5. **Závislosti**: #1.
6. **Regrese**: nízké.
7. **Jak otestovat**: viz #1. Non-HTMX variantu: POST přes curl → ověřit že detail zobrazí toast "už existuje".

#### #3 MEDIUM — Mrtvý klíč `active_rel` v detail contextu

1. **Co a kde**: `app/routers/tenants/crud.py:629-648`. Po commitu 64acbe9 `detail.html` loopuje přes `active_rels` a `active_rel` nepoužívá (ověřeno grepem v `app/templates/tenants`).
2. **Řešení**: odstranit řádky `active_rel = active_rels[0] if active_rels else None` (řádek 630) a `"active_rel": active_rel,` (648) z contextu.
3. **Náročnost**: ~2 min.
6. **Regrese riziko**: nízké.
7. **Jak otestovat**: otevřít detail nájemce s 0, 1, 2+ prostory — musí vykreslit stejně.

#### #4 MEDIUM — `active_space_rel` property není cachovaný → zbytečná práce v sort

1. **Co a kde**: `app/models/space.py:167-177`. Každé volání buduje a sortí nový list. V `_filter_tenants` při sort="space" Python TimSort volá funkci ~ O(N log N) × O(M log M). Pro běžný dataset zanedbatelné, ale zbytečné.
2. **Řešení**: buď (a) `@functools.cached_property` pro `active_space_rels` (pozor — `cached_property` nefunguje s SQLAlchemy DeclarativeBase pokud se instance exping — ověřit), nebo (b) v `_filter_tenants` naplnit lokální dict `rels_by_tenant = {t.id: t.active_space_rels for t in tenants}` a sort klíče číst z něj.
3. **Náročnost**: ~10 min.
4. **Doporučení**: varianta (b) — bezpečnější a čitelnější.
6. **Regrese**: nízké.

#### #5 MEDIUM — Migrace `_migrate_dedupe_tenants` — legacy záznamy bez `last_name` se přeskočí

1. **Co a kde**: `app/main.py:_migrate_dedupe_tenants._key()` (řádky ~623-645). Pokud Tenant nemá ani `owner_id`, ani `birth_number`, ani `company_id`, ani `first_name`/`last_name`, vrátí `None` a záznam se přeskočí. Importy přes CSV/Excel mohly uložit jméno jen do `name_with_titles` — takové duplicity migrace nesliji.
2. **Řešení**: fallback — když `_key()` vrátí `None`, zkusit `name_normalized` jako klíč. Nebo aspoň logger.info("Skipped N tenants without dedup key") po dokončení, aby user věděl.
3. **Náročnost**: ~30 min (oprava + manuální audit DB).
4. **Varianty**: (a) rozšířit klíč — rychlé ale riskantní; (b) jen logovat — bezpečné.
5. **Regrese**: (a) střední — může sloučit nechtěně; (b) nízké.

#### #6 MEDIUM — Sort `"space"` bere jen první prostor

1. **Co a kde**: `app/routers/tenants/_helpers.py:132`: `"space": lambda t: (t.active_space_rel.space.space_number if t.active_space_rel else 0)`.
2. **Řešení**: buď ponechat + přidat tooltip "Řazeno podle nejnižšího čísla prostoru", nebo sortovat podle tuple všech čísel. Doporučení: ponechat chování + tooltip.
3. **Náročnost**: ~10 min.

#### #7 MEDIUM — Dedup v `spaces/crud.py` bez ID fields

1. **Co a kde**: `app/routers/spaces/crud.py:135-140`. `find_existing_tenant` dostává jen `first_name`/`last_name` (formulář prostoru nemá RČ/IČ). Takže se propojení dělá pouze podle jména → jmenovec se "vnutí" jako existující nájemce nového prostoru.
2. **Řešení**: pravděpodobně úmyslné pro inline UX (rychlé vytvoření prostoru). Minimum: přidat komentář nad volání "# Dedup záměrně jen podle jména — rychlé inline vytváření". Lepší: po vytvoření zobrazit toast "Přiřazeno existujícímu nájemci Jan Novák (ID 42) — opravte pokud je to jiná osoba".
3. **Náročnost**: ~5 min (komentář) / ~15 min (toast).
6. **Regrese**: nízké.

#### #8 LOW — Parsing "Jan Novák" obrácené pořadí

1. **Co a kde**: `app/routers/spaces/crud.py:131-133` — první slovo = příjmení. User píše "Jméno Příjmení" → uloží se obráceně. Pre-existing.
2. **Řešení**: placeholder "Příjmení Jméno" nebo dvě pole. Doporučuji dvě pole (stejný vzor jako owners).
3. **Náročnost**: ~10 min.

#### #9 LOW — XSS v HTMX response `tenant_create`

1. **Co a kde**: `app/routers/tenants/crud.py:81`: `HTMLResponse(content=f'<p ...>{existing.display_name}</p>')`. Jméno není escapováno. Pokud user zadá titul `<img onerror=...>`, dojde ke XSS ve formuláři. Admin-only, ale hygienicky vadí.
2. **Řešení**: nahradit za `TemplateResponse("tenants/partials/_create_form.html", {"duplicates": [existing]})` — Jinja2 autoescape vyřeší.
3. **Náročnost**: ~10 min (spojeno s #1, #2).
6. **Regrese**: nízké.

### 2. Dokumentace

#### #13 LOW — CLAUDE.md / README nepopisují nové chování

1. **Co a kde**: nikde není zmíněný vzor `find_existing_tenant` ani že nájemce teď může být vázán k více prostorům současně (stacked layout v tabulce).
2. **Řešení**: CLAUDE.md § "Router vzory" — přidat jednovětý odkaz na `find_existing_tenant` jako šablonu dedup helperu (pro znovupoužití v dalších modulech). README § Moduly/Nájemci — krátká věta "Nájemce může mít více prostor; v tabulce se zobrazují stacked pod sebou, export dává 1 řádek per smlouva".
3. **Náročnost**: ~20 min.

### 3. UI / Šablony

#### #11 LOW — `align-top` s prázdným místem u nájemců s více prostory

1. **Co a kde**: `app/templates/tenants/partials/_row.html`. Nájemce se 3 prostory → jméno/telefon/email zabírají 1 řádek, prostory/nájemné/VS 3 řádky. `align-top` je správně, ale vzniká bílé místo.
2. **Řešení**: design rozhodnutí. Možnosti: (a) ponechat (konzistentní s vlastníky); (b) přidat pod jméno malý badge "× N prostor"; (c) `vertical-align: middle`. Doporučuji (a).
3. **Náročnost**: ~10 min.

### 4. Testy

#### #12 LOW — Chybí testy pro nové flows

1. **Co a kde**: `tests/` neobsahuje cílené testy pro:
   - `find_existing_tenant()` (po identifikátoru a po jménu)
   - `Tenant.active_space_rels` řazení
   - `Tenant.resolved_birth_number` / `resolved_company_id`
   - tenant export — 2 prostory = 2 řádky
   - migrace `_migrate_dedupe_tenants` (idempotence)
2. **Řešení**: přidat ~5 pytest testů. Pokrývá regrese při další refaktoringu.
3. **Náročnost**: ~2 hod.

### 5. Git Hygiene

#### #10 LOW — Reporty v rootu, `.DS_Store`

- **Stray reporty**: `AUDIT-REPORT.md`, `BACKUP-REPORT.md`, `TEST-REPORT.md`, `UX-REPORT.md`, `PREHLED-KOMPLET.md`, `SESSION-START.md`, `CLAUDE.md` (to je OK, ten patří), `README.md` (OK). Reporty bych přesunul do `docs/reports/` nebo do `.gitignore`.
- **`.playwright-mcp/`**: **NEEXISTUJE** — čisté.
- **`*.png` / `*.jpeg` v rootu**: **ŽÁDNÉ** — čisté.
- **`.DS_Store`**: existuje v rootu. `.gitignore` ho má — ok.
- **`.env`**: existuje, ignorován. OK.

### 6. Výkon

- Viz #4. Jinak `_filter_tenants` používá správně `joinedload(Tenant.owner)` + `joinedload(Tenant.spaces).joinedload(SpaceTenant.space)` a explicitní Python dedup `seen_ids` — N+1 vyřešené.

### 7. Error Handling

- `tenant_create` — bez try/except, ale nic rizikového.
- `_migrate_dedupe_tenants` — `try/finally` s `db.close()`. SQLAlchemy rollbackuje při close implicitně, ale explicitní `except Exception: db.rollback()` by bylo čistší (viz ostatní migrace v `main.py`).

### 8. Ostatní (lehký průchod)

- **Bezpečnostní headers**: dle CLAUDE.md přítomné v `main.py` middleware — nekontrolováno v tomto runu.
- **Upload limity**: centralizované v `UPLOAD_LIMITS` — OK.
- **SQL injection**: projekt používá SQLAlchemy ORM — všechny dotazy v recent změnách parametrizované.
- **CSRF**: projekt nepoužívá (interní síť, jedno-uživatelské nasazení dle CLAUDE.md plánu).

---

## Doporučený postup oprav

1. **Nejprve HIGH — jeden patch na #1 + #2 + #9** (~40 min): přepsat `tenant_create` aby vracel `_create_form.html` s `duplicates=[existing]` + `force_create` checkbox (vzor z owners). Řeší XSS (#9), tichý flash (#2) i volný match (#1).
2. **MEDIUM — rychlé opravy #3, #4, #7** (~20 min): odstranit mrtvý `active_rel`, cache pro `active_space_rels` v `_filter_tenants`, komentář v `spaces/crud.py`.
3. **MEDIUM — rozhodnout #5, #6** s uživatelem (co se má stát s legacy záznamy bez jmen, tooltip na sort).
4. **LOW — dokumentace #13** (~20 min), testy #12 do dalších iterací.
5. **Git hygiene #10** — kdykoli.

---

_Vygenerováno: Code Guardian audit 2026-04-10, fokus na commity 64acbe9, 77145dd, 79bcbe9._
