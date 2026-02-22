# SVJ Projekt — pravidla pro vývoj

## Navigace a back URL

- Každý odkaz z dashboardu na seznam/modul musí obsahovat `?back=/`
- Každý odkaz ze seznamu na detail musí obsahovat `?back={{ list_url|urlencode }}`
- `list_url` se vždy buduje v routeru z `request.url` (path + query), aby zachytil všechny filtry:
  ```python
  list_url = str(request.url.path)
  if request.url.query:
      list_url += "?" + str(request.url.query)
  ```
- Parametr `back` se musí propagovat přes:
  - filtrační bubliny (v query string proměnných `_base`, `_base2`, `_ubase` atd.)
  - HTMX hledání a filtry (hidden input `<input type="hidden" name="back">` + přidání `[name='back']` do `hx-include`)
  - řadící odkazy v hlavičkách sloupců
  - `_back` helper proměnná v šabloně: `{% set _back = "&back=" ~ (back_url|default('')|urlencode) if back_url else "" %}`
- Detailová stránka vždy přijímá `back` query parametr a zobrazuje šipku zpět
- Při vícenásobném zanoření (seznam → detail → detail) se back URL řetězí: `?back={{ ('/aktualni/url?back=' ~ (back_url|urlencode))|urlencode }}`
- Back label se nastavuje dynamicky podle cílové URL (např. "Zpět na přehled", "Zpět na seznam vlastníků", "Zpět na detail vlastníka")

## Filtrační bubliny

- Bubliny jsou vždy dynamické: `flex` + `flex-1` (nikdy ne `grid` ani `flex-wrap`)
- Roztahují se na celou šířku obrazovky
- Pokud existují dvě řady bublin nad sebou:
  - Klik na bublinu v prvním řádku resetuje druhý řádek na "Vše" (a obráceně)
  - Toho se dosáhne tím, že `_base` (pro řádek 1) neobsahuje parametry řádku 2 a naopak
- Rozdělené bubliny (s/bez emailu, s/bez telefonu) jsou uvnitř jednoho `flex-1` wrapperu s `<div class="w-px bg-gray-200">` oddělovačem
- Aktivní bublina má `ring-2 ring-{color}-400`
- Bubliny zobrazují počet záznamů (velký, bold) a popis (malý text pod číslem)

## Tabulky a layout

- Hlavičky tabulek jsou vždy sticky: `sticky top-0 z-10` na `<thead>`
- Tabulky mají omezenou výšku s vertikálním scrollem: `max-height:calc(100vh - Xpx); overflow-y:auto`
- Řazení kliknutím na hlavičky sloupců s indikátorem směru (šipka SVG nahoru/dolů)
- Řadící hlavičky se implementují přes Jinja2 macro `sort_th(label, col, align)` pro konzistenci
- Souhrnný řádek (`<tfoot>`) pod tabulkami kde to dává smysl (celkový podíl, plocha, procenta)
- `table-layout: fixed` s `<colgroup>` pro přesné šířky sloupců

## Formátování čísel a dat

- Tisíce se oddělují mezerou: `"{:,}".format(x).replace(",", " ")`
- Podíl v procentech na 4 desetinná místa: `"%.4f" | format(value)`
- Procenta rozdílu se znaménkem: `"{:+.2f}".format(diff_pct)`
- Barevné kódování rozdílů: červená (`text-red-600`) pro záporné, modrá (`text-blue-600`) pro kladné, zelená (`text-green-600`) pro nulu
- Datum ve formátu `dd.mm.YYYY`: `strftime('%d.%m.%Y')`
- Pomlčka `—` pro chybějící hodnoty (ne prázdný řetězec)

## Statistiky podílů

- Porovnání podílů se zobrazuje na dashboardu i v seznamech (vlastníci, jednotky):
  - Podíly dle prohlášení (z `SvjInfo.total_shares`)
  - Podíly v evidenci (součet z tabulky)
  - Rozdíl s barevným kódováním a procentuálním vyjádřením
- V detailu vlastníka: sloupec "Podíl %" = `podil_scd / declared_shares * 100` (4 des. místa)
- `declared_shares` se předává do všech šablon kde se zobrazují podíly (včetně HTMX partials)

## Dashboard

- Statistické bubliny i modulové karty jsou plně klikací (`<a>` tag, ne `<div>` s vnořeným odkazem)
- Bublina hlasování zobrazuje seznam aktivních/konceptových hlasování se stavem (badge) a názvem (truncate + title tooltip)
- Vše dynamicky roztažené přes `flex` + `flex-1`
- Žádný text "Otevřít modul" — celá karta je klikací

## Inline editace (Upravit / Uložit / Zrušit)

Vzor se skládá ze dvou partials (info + form) a tří endpointů:

### Šablony
- **Info partial** (`partials/*_info.html`) — read-only zobrazení dat + tlačítko "Upravit":
  ```html
  <button hx-get="/entita/{id}/upravit-formular"
          hx-target="#section-id" hx-swap="innerHTML">Upravit</button>
  ```
  Po úspěšném uložení zobrazí `{% if saved %}<span class="text-green-600">Uloženo</span>{% endif %}`
- **Form partial** (`partials/*_form.html`) — editační formulář + "Uložit" a "Zrušit":
  ```html
  <form hx-post="/entita/{id}/upravit" hx-target="#section-id" hx-swap="innerHTML">
      <!-- inputy -->
      <button type="submit">Uložit</button>
      <button type="button" hx-get="/entita/{id}/info"
              hx-target="#section-id" hx-swap="innerHTML">Zrušit</button>
  </form>
  ```

### Detail stránka
- Wrapper `<div id="section-id">` obsahuje pouze `{% include %}` partials — žádný extra markup
- Nadpis sekce (`<h2>`) je VNĚ wrapperu, aby se neměnil při přepínání

### Backend endpointy (3 pro každou sekci)
| Endpoint | Účel | Vrací |
|----------|------|-------|
| `GET /{id}/upravit-formular` | Načtení formuláře | Form partial |
| `POST /{id}/upravit` | Uložení změn | Info partial s `saved=True` |
| `GET /{id}/info` | Zobrazení (cancel) | Info partial |

- POST endpoint: pro HTMX vrací partial, pro běžný request dělá `RedirectResponse`
- Pro vnořené sekce s prefixem (např. adresa trvalá/korespondenční): `/{id}/adresa/{prefix}/upravit`

### Alternativní vzor (administrace — seznam položek)
- View i form jsou na stránce oba, přepínání přes CSS `hidden` class + JS:
  ```javascript
  function toggleEdit(id) {
      document.getElementById('view-' + id).classList.toggle('hidden');
      document.getElementById('edit-' + id).classList.toggle('hidden');
  }
  ```
- Formuláře používají standardní POST (`hx-boost="false"`) s redirect po uložení

## HTMX vzory

- Partial odpovědi: router vrací partial šablonu pro HTMX requesty (`HX-Request` hlavička), plnou stránku pro běžné requesty
- Rozlišovat `HX-Request` vs `HX-Boosted` — boosted navigace dostává plnou stránku
- `hx-push-url="true"` na vyhledávání a filtrech — aby se URL aktualizovala v prohlížeči
- `hx-confirm` pro destruktivní akce (smazání, odebrání)
- Hidden inputy pro přenos stavu filtrů při HTMX požadavcích

## Vyhledávání

- Hledání probíhá přes HTMX s debounce: `hx-trigger="keyup changed delay:300ms"`
- Prohledávají se všechna relevantní pole (jméno, email, telefon, RČ, IČ, číslo jednotky, adresa)
- Hledání se kombinuje s filtry (typ, sekce, vlastnictví, kontakt) — filtry se přenáší přes hidden inputy a `hx-include`

## SQLAlchemy vzory

- `case()` se importuje přímo ze `sqlalchemy`, ne přes `func.case()`
- `func.coalesce(field, "")` pro seskupování NULL a prázdných řetězců (např. ownership_type)
- `func.distinct()` v agregacích pro počítání unikátních záznamů
- `joinedload()` pro eager loading relací (předchází N+1 queries)
- Číslo jednotky (`unit_number`) je INTEGER (ne string)

## Nové moduly / entity

- Musí dodržovat VŠECHNY výše uvedené vzory od začátku:
  - Back URL navigace (router `back` param + `list_url` + šipka zpět v šabloně)
  - Dynamické bubliny (pokud mají filtry)
  - Sticky hlavičky tabulek
  - Plně klikací karty (ne vnořené odkazy)
  - Formátování čísel s mezerovým oddělovačem
  - HTMX partial odpovědi
- Registrace v `app/main.py` (`include_router`)
- Export modelů v `app/models/__init__.py`
- Odkaz v sidebar (`base.html`) s `active_nav` kontrolou
- Přidání do README.md (popis modulu + API endpointy)

## Workflow

- Po dokončení změn: commit + push (pokud uživatel požádá)
- Po commitu: aktualizovat README.md (pokud uživatel požádá)
- Commit message v češtině, stručný, popisuje "co a proč"

## Komunikace s uživatelem

- NEPTÁT SE na přístup/implementaci, pokud je vzor již zavedený v projektu — použít existující vzor
- Pokud uživatel řekne "commit this and push" — udělat commit a push bez dalších otázek
- Pokud uživatel řekne "dokumentaci" — aktualizovat README.md bez ptaní se co přidat
- Být proaktivní: když vytvářím novou stránku/entitu, rovnou aplikovat VŠECHNA pravidla z tohoto souboru (back URL, dynamické bubliny, sticky hlavičky, formátování čísel atd.) bez čekání na připomínku
- Komunikovat stručně — co jsem udělal, ne co bych mohl udělat
- Na potvrzení se PTÁT — "Chceš commitnout?", "Chceš něco upravit?" atd. jsou v pořádku
