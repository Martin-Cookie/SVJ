# Router vzory

> Toto je detailní referenční dokument. Hlavní pravidla jsou v [CLAUDE.md](../CLAUDE.md).

### Boilerplate
- Každý router: `router = APIRouter()` + `from app.utils import templates` (sdílená singleton instance)
- Žádné prefixy na `APIRouter()` — všechny prefixy v `main.py` přes `include_router(prefix=...)`
- Každý `TemplateResponse` musí obsahovat `"active_nav": "module_key"` pro zvýraznění sidebaru

### POST-Redirect-GET (PRG)
- Všechny POST endpointy po mutaci: `RedirectResponse(url, status_code=302)` pro non-HTMX requesty
- Pro HTMX requesty: vrací partial šablonu místo redirectu
- Vždy `status_code=302`, nikdy 303 nebo 301

### Entity not found → redirect
- Když `db.query(Model).get(id)` vrátí `None`: `RedirectResponse("/seznam", status_code=302)`
- Nikdy `HTTPException(404)` — uživatel je tiše přesměrován na seznam

### Flash zprávy (toast)
- Zobrazují se jako **toast** — fixní pozice vpravo nahoře, nepřesouvají obsah. Viz [UI_GUIDE.md § 18b](UI_GUIDE.md)
- Předávají se jako `flash_message` + `flash_type` (`"error"`, `"warning"`, nebo default) v kontextu šablony
- Pro zprávy přes redirect: POST handler redirectuje s `?flash=ok`, GET handler přeloží na `flash_message` v kontextu
- **Nikdy nepsat inline flash bloky v šablonách** — vše řeší globální toast v `base.html`
- Projekt NEPOUŽÍVÁ session-based flash messaging

### HTMX partial odpovědi
- Router rozlišuje HX-Request vs HX-Boosted — boosted navigace dostává plnou stránku:
  ```python
  from app.utils import is_htmx_partial

  if is_htmx_partial(request):
      return templates.TemplateResponse(request, "partial.html", ctx)
  return templates.TemplateResponse(request, "full_page.html", ctx)
  ```
- Partial = jen `<tr>` řádky (tbody-only), hlavní šablona dělá `{% include "partial.html" %}` uvnitř `<tbody id="...">`

### Starlette 0.29+ TemplateResponse API
- Všechna volání `templates.TemplateResponse` MUSÍ předávat `request` jako **první pozicionální argument**, ne jako klíč v context dictu:
  ```python
  # SPRÁVNĚ (Starlette 0.29+)
  return templates.TemplateResponse(request, "tpl.html", {"foo": bar, ...})

  # ŠPATNĚ (deprecated, Starlette warning)
  return templates.TemplateResponse("tpl.html", {"request": request, "foo": bar, ...})
  ```
- Context dict už **nemá obsahovat `"request": request`** — Starlette ho doplní automaticky
- Platí pro všechny routery (211 volání ve 32 souborech). Při přidání nového TemplateResponse vždy nový API styl

### HTMX redirect po POST (XSS-safe vzor)
- Pro POST handlery které po úspěšné mutaci mají přesměrovat HTMX klienta NIKDY nepoužívat `HTMLResponse(f"<script>...</script>")` nebo interpolované f-stringy — XSS riziko
- Správný vzor:
  ```python
  from fastapi.responses import Response
  return Response(status_code=204, headers={"HX-Redirect": f"/najemci/{tenant.id}"})
  ```
- Používá se v `tenants/crud.py`, `spaces/crud.py` — pro HTMX klient v reakci na hlavičku `HX-Redirect` provede navigaci

### Řazení — `SORT_COLUMNS` dictionary
- Modul-level `SORT_COLUMNS` dict mapující sort parametry na SQLAlchemy sloupce (nebo `None` pro Python-side sort)
- SQL sorty vždy s `.nulls_last()`
- Python-side sort: `items.sort(key=lambda x: ..., reverse=(order == "desc"))`

### Helper funkce v routerech
- Interní helper funkce mají prefix `_` (např. `_ballot_stats`, `_purge_counts`)
- Vrací dict, který se rozbalí do template kontextu: `**_ballot_stats(voting)`
- Typické helpery: `voting.has_processed_ballots` (model property), `_voting_wizard(voting, step)` / `_tax_wizard(...)` (wizard stepper kontext)
- Validační funkce v service vrstvě: `validate_owner_mapping(mapping)` / `validate_contact_mapping(mapping)` → `str | None` (chybová zpráva nebo None)

### Formulářová validace — návrat formuláře s chybou
- Při validační chybě (neplatný email, duplicita, rozsah) vracet **formulářovou šablonu s `error`** místo tichého redirectu:
  ```python
  return templates.TemplateResponse("partials/owner_create_form.html", {
      "request": request,
      "error": "Neplatný formát emailu",
      "form_data": {"first_name": first_name, "last_name": last_name, ...},
  })
  ```
- Šablona zobrazí červenou hlášku a zachová vyplněná pole přes `form_data`
- Používáno v: `owners/crud.py` (email validace), `units.py` (unit_number, building_number rozsah)

### Detekce duplicit při vytváření entity
- Před vytvořením vlastníka ověřit duplicitu (jméno, RČ, email) — zobrazit varování s existujícími záznamy
- Uživatel může vynuceně pokračovat přes hidden field `force_create`:
  ```python
  if duplicates and not force_create:
      return templates.TemplateResponse("partials/owner_create_form.html", {
          "request": request, "duplicates": duplicates, "form_data": {...},
      })
  ```

### Tenants — dedup helper a resolved properties
- **`find_existing_tenant()`** v `app/routers/tenants/_helpers.py` — jediný zdroj pravdy pro vyhledávání existujícího nájemce při create (`/najemci/novy`) i při inline vytvoření nájemce v novém prostoru (`/prostory/novy`). Prevence duplicit = merge místo insert
- Priorita hledání: `owner_id` → `birth_number` → `company_id` → `name_normalized + tenant_type` (pouze pro nepropojené). Vrací první shodu nebo `None`
- **Výjimka `spaces/crud.py`**: rychlé vytvoření nájemce při zakládání prostoru (`/prostory/novy`) má jen pole příjmení + jméno (ne RČ/IČ). `find_existing_tenant` se tam volá s `birth_number=None, company_id=None` — dedup probíhá **jen podle jména**. Reuse je indikován flash `tenant_reused` (amber toast na detailu prostoru), uživatel má možnost opravit přiřazení v sekci nájemců. Jiný kontrakt než při `/najemci/novy`, kde se vyplňují všechna ID pole
- **Resolved properties** na `Tenant` modelu (analogicky k `resolved_phone`, `resolved_email`): `resolved_birth_number`, `resolved_company_id`, `resolved_type`, `resolved_name_normalized` — pokud je tenant propojený na Owner (`owner_id`), čtou se z Owner; jinak z vlastních polí. **Vždy používat resolved varianty** v šablonách, exportu i hledání — přímý přístup k `tenant.birth_number` selže u propojených nájemců
- **Rozdělené pole jméno v `/prostory/novy`**: formulář má místo jednoho `tenant_name` **dvě pole** `tenant_last_name` + `tenant_first_name` (kvůli strukturované dedup logice a správnému sestavení `name_normalized`). Validace: pokud je vyplněné jakékoliv pole nájemce (jméno/telefon/email/smlouva), je **příjmení povinné** — jinak router vrací formulář s chybou
- **Multi-space podpora**: `Tenant.active_space_rels` vrací list aktivních SpaceTenants seřazený podle `space_number`, `Tenant.active_space_rel` vrací první (zpětná kompatibilita). Jeden nájemce může mít více současných smluv — seznam i detail zobrazují všechny prostory stacked pod sebou, export má 1 řádek per smlouva
- Historická duplicita v DB je řešena startup migrací `_migrate_dedupe_tenants` (viz § Startup)

### Dynamické formuláře
- `Form(...)` pro fixní pole. `await request.form()` + `.get()`/`.getlist()` pro dynamické názvy polí (např. `vote_5`, `update__12__field`)
