# Navigace a back URL

> Toto je detailní referenční dokument. Hlavní pravidla jsou v [CLAUDE.md](../CLAUDE.md).

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
- **Detailová stránka s vlastními filtry/bublinami** (např. sync compare, voting ballots): bubliny a sort odkazy musí propagovat `back` stejně jako na seznamových stránkách — jinak se po kliknutí na filtr/řazení ztratí šipka zpět
- **HTMX inline edit partials (`upravit-formular`, `info`) NEPOTŘEBUJÍ `back` parametr** — swapují obsah uvnitř stránky, uživatel neodchází. Back URL řeší nadřazená detail stránka, ne vnořené partials
- Při vícenásobném zanoření (seznam → detail → detail) se back URL řetězí: `?back={{ ('/aktualni/url?back=' ~ (back_url|urlencode))|urlencode }}`
- Back label se nastavuje dynamicky podle cílové URL pomocí řetězených `if/elif` s `in` nebo `.startswith()`:
  ```python
  back_label = (
      "Zpět na hromadné úpravy" if "/sprava/hromadne" in back
      else "Zpět na detail jednotky" if "/jednotky/" in back
      else "Zpět na seznam jednotek" if back.startswith("/jednotky")
      else "Zpět na porovnání" if "/synchronizace/" in back
      else "Zpět na hlasovací lístek" if "/hlasovani/" in back
      else "Zpět na nastavení" if back.startswith("/nastaveni")
      else "Zpět na seznam vlastníků"
  )
  ```
- `list_url` = URL aktuální stránky s query parametry (pro odkazy na detail, teče dopředu). `back_url` = příchozí `back` parametr (pro šipku zpět, teče dozadu). Nikdy nezaměňovat
- Pokud stránka má expandovatelné řádky (např. hromadné úpravy), back URL musí obsahovat i identifikátor rozbalené položky (např. `&hodnota=SJM`)
- Cílová stránka pak automaticky rozbalí odpovídající řádek pomocí skriptu:
  ```javascript
  var hodnota = new URLSearchParams(window.location.search).get('hodnota');
  if (hodnota) { /* najít a kliknout na řádek s data-hodnota == hodnota */ }
  ```
- **Obnova scroll pozice** — viz [UI_GUIDE.md § 13](UI_GUIDE.md). Dva vzory:
  - **Back URL (hash)**: řádky mají `id`, back URL obsahuje `#hash`, stránka volá `scrollToHash()` z `app.js`. Pro HTMX boost navigaci (AJAX body swap) řeší scroll `MutationObserver` v `app.js` — inline scripty se spustí před swapem (starý DOM), observer detekuje nový DOM a scrolluje po 80ms. HTMX config `scrollIntoViewOnBoost: false` v `base.html` zabraňuje výchozímu scrollu na začátek. **Scroll kontejner MUSÍ mít `overflow-y-auto overflow-x-hidden min-h-0`** (ne `overflow-auto`) — jinak HTMX boost neobnoví scroll pozici. CSS `scroll-margin-top: 40px` v `custom.css` zabraňuje zakrytí řádku sticky hlavičkou
  - **POST+redirect (sessionStorage)**: pro inline formuláře na stejné stránce — `sessionStorage` uloží `scrollTop` před submitem, obnoví přesnou pixel pozici po redirectu. Hash se stripne přes `history.replaceState` aby prohlížeč nepřeskočil
- **Kontrola při přidání `<a href>` na entitu** — VŽDY ověřit 3 věci: (1) odkaz má `?back=`, (2) router předává `list_url` do kontextu, (3) cílová stránka má odpovídající `back_label` větev
