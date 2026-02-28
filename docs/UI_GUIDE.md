# UI Guide — konvence pro frontend

Tento soubor shrnuje UI/frontend vzory a konvence používané v projektu. Stack: **FastAPI + Jinja2 + HTMX + Tailwind CSS (CDN)**.

---

## 1. Layout

### Detail stránka
1. Šipka zpět: `<a href="{{ back_url }}" class="text-sm text-gray-500 hover:text-gray-700">&larr; {{ back_label }}</a>`
2. Titulek: `<h1 class="text-2xl font-bold text-gray-800">`
3. Badge pod titulem: `<div class="mt-1 flex items-center gap-2">` s `rounded-full` badge
4. Obsah v grid layoutu pod tím

### Fixní header + scrollovatelný obsah
```html
<div class="flex flex-col" style="height:calc(100vh - 3rem)">
    <div class="shrink-0"><!-- header, bubliny, search --></div>
    <div class="flex-1 overflow-y-auto min-h-0"><!-- scrollovatelný obsah --></div>
</div>
```
- `3rem` = top+bottom padding z `<main class="p-6">`
- `min-h-0` je nutné aby flex child mohl být menší než obsah
- Bubliny/search se **nescrollují** — musí být vždy viditelné

---

## 2. Tabulky

### Sticky hlavičky
```html
<thead class="bg-gray-50 border-b-2 border-gray-300 sticky top-0 z-10">
```

### Řazení sloupců
- Klikací hlavičky s indikátorem směru (šipka SVG nahoru/dolů)
- Implementace přes `{% set _cols = [...] %}` + `{% for %}` cyklus (NE macro — nemá přístup ke kontextu)
- Sort parametry: `sort` (název sloupce), `order` (`asc`/`desc`)

### Řádkové akce — ikony
- Akční sloupce používají **SVG ikony** místo textových odkazů
- Ikona stáhnout: `text-blue-600 hover:bg-blue-50`
- Ikona smazat: `text-gray-400 hover:text-red-600 hover:bg-red-50`
- Ikona upravit: `text-gray-400 hover:text-blue-600 hover:bg-blue-50`
- Velikost: `w-4 h-4`, padding `p-1`, kulaté rohy `rounded`
- Vždy `title` atribut pro tooltip

### Souhrnný řádek
```html
<tfoot class="border-t-2 border-gray-300 bg-gray-50">
```

### Table layout
- `table-layout: fixed` s `<colgroup>` pro přesné šířky sloupců
- Dlouhé názvy: `truncate` + `title` tooltip

---

## 3. Formuláře

### Input styly
```
border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500
```

### Tlačítka — kanonické styly

| Typ | CSS | Použití |
|-----|-----|---------|
| **Akce (světle modré)** | `px-3 py-1.5 text-sm font-medium text-blue-600 border border-blue-300 rounded-lg hover:bg-blue-50 transition-colors` | Upravit, Přidat, Uložit |
| **Akce malá (inline)** | `px-2 py-1 text-xs font-medium text-blue-600 border border-blue-300 rounded hover:bg-blue-50` | Uložit/Přidat v tabulkách |
| **Akce s ikonou** | + `inline-flex items-center gap-1` | Upravit/Přidat s SVG ikonou |
| **Zrušit** | `px-3 py-1.5 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 text-sm font-medium` | Zrušit (cancel) |
| **Danger** | `px-3 py-1.5 bg-red-600 text-white rounded-lg hover:bg-red-700 text-sm font-medium` | Smazat |
| **Success** | `px-3 py-1.5 bg-green-600 text-white rounded-lg hover:bg-green-700 text-sm font-medium` | Dokončit, Vytvořit, Potvrdit |

- Upravit, Přidat a Uložit musí být **vždy** světle modré (obrysové) — na všech úrovních
- Zelená (success) pouze pro finální akce (Dokončit, Vytvořit, Potvrdit)

### Uložit/Zrušit — nahoře vedle nadpisu
V edit formulářích se tlačítka umísťují **nahoře vedle nadpisu sekce**, ne dole:
```html
<form hx-post="..." hx-target="..." hx-swap="innerHTML">
    <div class="flex items-center justify-between mb-4">
        <h2 class="text-lg font-semibold text-gray-700">Nadpis sekce</h2>
        <div class="flex items-center gap-2">
            <button type="submit" class="px-3 py-1.5 text-sm font-medium text-blue-600 border border-blue-300 rounded-lg hover:bg-blue-50 transition-colors">Uložit</button>
            <button type="button" hx-get="/cancel-url" hx-target="..." hx-swap="innerHTML"
                    class="px-3 py-1.5 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 text-sm font-medium">Zrušit</button>
        </div>
    </div>
    <!-- inputs -->
</form>
```

---

## 4. Inline editace (info/form partial vzor)

### Šablony
- **Info partial** (`partials/*_info.html`) — read-only + tlačítko "Upravit"
- **Form partial** (`partials/*_form.html`) — editační formulář s Uložit/Zrušit nahoře

### Detail stránka
- Wrapper `<div id="section-id">` obsahuje `{% include %}` — žádný extra markup
- Nadpis sekce je SOUČÁSTÍ partialu (uvnitř form wrapperu s flex layout)

### Backend endpointy (3 pro každou sekci)
| Endpoint | Účel | Vrací |
|----------|------|-------|
| `GET /{id}/upravit-formular` | Načtení formuláře | Form partial |
| `POST /{id}/upravit` | Uložení změn | Info partial s `saved=True` |
| `GET /{id}/info` | Zobrazení (cancel) | Info partial |

---

## 5. Akční ikony — kanonické CSS třídy

### Upravit (tužka)
```html
<button title="Upravit" class="p-1 text-gray-400 hover:text-blue-600 rounded hover:bg-blue-50">
    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"/>
    </svg>
</button>
```

### Smazat (koš)
```html
<button title="Smazat" class="p-1 text-gray-400 hover:text-red-600 rounded hover:bg-red-50">
    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
    </svg>
</button>
```

### Stáhnout
```html
<a title="Stáhnout" class="p-1 text-blue-600 hover:bg-blue-50 rounded">
    <svg class="w-4 h-4" ...><!-- download icon --></svg>
</a>
```

---

## 6. Formulář přidání (toggle hidden)

Vzor pro "přidat novou položku" bez přechodu na jinou stránku:
1. Tlačítko `+ Přidat` (světle modré) — klik skryje Přidat a odkryje Uložit+Zrušit + formulář
2. **Uložit** a **Zrušit** se zobrazí na stejném místě (nahoře) — nahradí tlačítko Přidat
3. Po uložení/zrušení se Přidat vrátí zpět (HTMX swap nebo toggle)

```html
<div class="flex items-center justify-between mb-4">
    <h2 class="text-lg font-semibold text-gray-700">Nadpis</h2>
    <div>
        <div id="add-btn">
            <button type="button" onclick="..."
                    class="inline-flex items-center gap-1 px-3 py-1.5 text-sm font-medium text-blue-600 border border-blue-300 rounded-lg hover:bg-blue-50 transition-colors">
                <svg class="w-3.5 h-3.5"><!-- plus icon --></svg>
                Přidat
            </button>
        </div>
        <div id="add-actions" class="hidden flex items-center gap-2">
            <button type="submit" form="add-form-el"
                    class="px-3 py-1.5 text-sm font-medium text-blue-600 border border-blue-300 rounded-lg hover:bg-blue-50 transition-colors">Uložit</button>
            <button type="button" onclick="..."
                    class="px-3 py-1.5 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 text-sm font-medium">Zrušit</button>
        </div>
    </div>
</div>

<div id="add-form" class="hidden mt-4 pt-4 border-t border-gray-200">
    <form id="add-form-el" ...>
        <!-- fields (submit button je nahoře přes form="add-form-el") -->
    </form>
</div>
```

---

## 7. Filtrační bubliny + search bar (společný kontejner)

Bubliny a search bar jsou vizuálně sjednoceny v jednom bílém kontejneru se stínem:

```html
<div class="bg-white rounded-lg shadow mb-2">
    <!-- Bubliny -->
    <div class="flex gap-2 p-3 pb-2">
        <a href="..." class="flex-1 block rounded p-2 text-center hover:bg-gray-50 transition-colors
                  {% if active %}ring-2 ring-gray-400{% endif %}">
            <p class="text-lg font-bold text-gray-800">{{ count }}</p>
            <p class="text-xs text-gray-500">Celkem</p>
        </a>
        <!-- Barevné varianty (bg-gray-50, bg-blue-50, bg-orange-50) zachovat -->
    </div>

    <!-- Druhý řádek bublin (volitelný) -->
    <div class="flex gap-2 px-3 pb-2">...</div>

    <!-- Oddělovač -->
    <div class="border-t border-gray-100"></div>

    <!-- Search bar -->
    <div class="flex items-center gap-3 px-3 py-2">
        <div class="flex-1">
            <input type="text" name="q" ...
                   class="w-full px-3 py-1.5 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-transparent text-xs">
        </div>
        <select name="sekce" ...
                class="px-3 py-1.5 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 text-xs h-[30px]">
        </select>
    </div>
</div>
```

### Bubliny — pravidla
- Layout: `flex gap-2` + `flex-1` (každá bublina roztažená)
- Bubliny **nemají vlastní `shadow` ani `rounded-lg`** — kontejner řeší obojí
- Styl bublin: `flex-1 block rounded p-2 text-center hover:bg-gray-50 transition-colors`
- Barevné varianty (bg-gray-50, bg-blue-50, bg-orange-50) zachovat — dávají vizuální rozlišení
- Aktivní bublina: `ring-2 ring-{color}-400`
- Split bubliny (s/bez emailu): bez shadow, s vnitřním dividerem `w-px bg-gray-200`
- Pokud dvě řady: klik na bublinu v 1. řadě resetuje 2. řadu na "Vše" (a naopak)

### Search bar — pravidla
- Uvnitř společného kontejneru — **bez vlastního** `bg-white rounded-lg shadow`
- Oddělený od bublin tenkou čarou `border-t border-gray-100`
- Select dropdown: `h-[30px]` pro shodnou výšku s inputem
- Hidden inputy vedle inputu, **ne** uvnitř tbody
- HTMX: `hx-trigger="keyup changed delay:300ms"`, `hx-push-url="true"`

### Sdílený header + kontejner otevřený přes šablony
Pokud jsou bubliny ve sdíleném header partialu (např. `_voting_header.html`) a search bar je v nadřazené šabloně:
1. Header **otevře** `<div class="bg-white rounded-lg shadow mb-2">` a vykreslí bubliny, ale **nezavře** kontejner
2. Nadřazená šablona přidá `border-t` + search bar a **zavře** `</div>`
3. Stránky bez search baru zavřou `</div>` ihned po include

```html
{# V nadřazené šabloně: #}
{% include "modul/_header.html" %}
    <div class="border-t border-gray-100"></div>
    <div class="flex items-center gap-3 px-3 py-2">
        ...search...
    </div>
</div><!-- /bubble+search kontejner -->
```

---

## 8. Seznam/index stránek

### Layout
```
┌─────────────────────────────────────────────────────┐
│ Titulek                           [Nové ... ]       │  Titulek + akce
├─────────────────────────────────────────────────────┤
│ [5 Vše] [2 Koncept] [1 Aktivní] [1 Uzavřeno] [1 ×]│  Filtrační bubliny
├─────────────────────────────────────────────────────┤
│ ┌ Karta procesu ──────────────────────────────────┐ │
│ │ Název (link)                  [Badge] [🗑]      │ │  Karta
│ │ metadata (datum, počet, ...)                     │ │
│ │ ✅──②──③──④  stepper                           │ │
│ │ ████████░░░░  progress bar                      │ │
│ └─────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
```

### Pravidla
- **Titulek řádek:** `flex items-center justify-between mb-6` — h1 vlevo, akční tlačítko vpravo
- **Tlačítko „Nové ...":** světle modré outline (`text-blue-600 border border-blue-300 hover:bg-blue-50`) — naviguje na formulář, není finální akce
- **Filtrační bubliny:** `flex gap-2 mb-6`, každá `flex-1 flex flex-col items-center py-2 px-3 rounded-lg`
  - Aktivní: `bg-{color}-100 ring-2 ring-{color}-400 text-{color}-800`
  - Neaktivní: `bg-white shadow text-gray-600 hover:bg-gray-50`
- **Karta procesu:** `bg-white rounded-lg shadow hover:shadow-md transition-shadow p-6`
  - Název (link) vlevo, **status badge + smazat vpravo** (`flex items-center justify-between`)
  - Badge: `px-3 py-1 text-xs font-medium bg-{color}-100 text-{color}-800 rounded-full`
  - Metadata pod názvem: `flex items-center mt-1 space-x-4 text-sm text-gray-500`
  - Wizard stepper compact + progress bar pod metadaty
- **Prázdný stav s filtrem:** rozlišit "žádné záznamy v tomto stavu" vs "žádné záznamy vůbec"

---

## 8b. Wizard/detail stránek — zóny

### Kanonické pořadí zón
```
A: ← Zpět na ...                                      Navigace
B: ✅──②──③──④                                       Stepper (mt-2)
C: Titulek + podnázev          [Badge] [Akce]         Titulek (mt-2 mb-4)
D: (volitelný panel, např. email konfigurace)          Panel
E+F+G: [bubliny | toolbar | search]                   Společný kontejner
H: Tabulka / obsah                                     Scrollovatelný obsah
```

### Pravidla
- **Navigace (A):** `<a>` přímo bez `<div>` wrapperu
- **Stepper (B):** obalený v `<div class="mt-2">`, vždy PŘED titulkem
- **Titulek (C):** `<div class="flex items-center justify-between mt-2 mb-4">`
  - Vlevo: `<h1 class="text-2xl font-bold">` + `<p class="text-sm text-gray-500 mt-1">podnázev</p>`
  - Vpravo: status badge + akční tlačítka
  - **Žádný prefix** v titulku (např. ne "Rozesílka — ...") — stepper už říká který krok
- **Společný kontejner (E+F+G):** `bg-white rounded-lg shadow mb-2`
  - Bubliny, toolbar (volitelný) a search bar oddělené `border-t border-gray-100`
- **Scrollovatelný obsah (H):** `flex-1 overflow-y-auto min-h-0`

### Stránky vytvoření (upload, create)
- Stejné zóny A–C (back, stepper pokud existuje, titulek + podnázev)
- Formulář v `bg-white rounded-lg shadow p-6 max-w-2xl`

---

## 9. Status badge

```html
<span class="px-2 py-1 text-xs font-medium bg-{color}-100 text-{color}-800 rounded-full">
    Status text
</span>
```

| Stav | Barva |
|------|-------|
| Draft / Neutrální | Šedá (`gray`) |
| Active / Success | Zelená (`green`) |
| Closed / Info | Modrá (`blue`) |
| Error / Cancelled | Červená (`red`) |
| Pending / Warning | Žlutá (`yellow`) |

Vždy `rounded-full`, nikdy `rounded`.

---

## 10. Prázdné stavy

```html
<p class="text-center text-gray-500 text-sm py-8">
    Žádné záznamy.
    <a href="/pridej" class="text-blue-600 hover:underline">Přidat první</a>
</p>
```
- Pro inline prázdné stavy (uvnitř karet): `text-sm text-gray-400`

---

## 11. Wizard stepper

### Logika stavů
- **done** (zelený) — `i <= max_done`
- **active** (modrý) — `i == current_step AND i > max_done`
- **pending** (šedý) — `i > max_done AND i > current_step`

### Klíčové pravidlo: all green when complete
Když je workflow plně dokončen (`max_done >= total_steps`), **všechny** kroky musí být zelené:
```python
elif i == current_step:
    step_status = "done" if i <= max_done else "active"
```

### Override pro dokumenty
Pokud existují dokumenty (step 1 = Upload PDF), krok 1 je vždy "done":
```python
if has_documents and max_done < 1:
    max_done = 1
```

---

## 12. Formátování

| Typ | Formát | Příklad |
|-----|--------|---------|
| Tisíce | `"{:,}".format(x).replace(",", " ")` | 1 234 567 |
| Podíl % | `"%.4f" \| format(value)` | 0.1234 |
| Procenta s +/- | `"{:+.2f}".format(diff)` | +1.23 |
| Datum | `strftime('%d.%m.%Y')` | 27.02.2026 |
| Chybějící hodnota | `—` (pomlčka) | — |

### Barevné kódování rozdílů
- Záporné: `text-red-600`
- Kladné: `text-blue-600`
- Nula: `text-green-600`

---

## 13. Back URL navigace

- Každý odkaz z dashboardu na modul: `?back=/`
- Každý odkaz ze seznamu na detail: `?back={{ list_url|urlencode }}`
- `list_url` se buduje v routeru: `request.url.path + "?" + request.url.query`
- Parametr `back` se propaguje přes: filtrační bubliny, HTMX hidden inputy, řadící odkazy
- `_back` helper v šabloně: `{% set _back = "&back=" ~ (back_url|default('')|urlencode) if back_url else "" %}`
- Vícenásobné zanoření: `?back={{ ('/url?back=' ~ (back_url|urlencode))|urlencode }}`

### Obnova scroll pozice
1. Řádky mají `id` (např. `id="owner-{{ owner.id }}"`)
2. Back URL obsahuje `#hash`: `?back={{ (list_url ~ '#owner-' ~ owner.id)|urlencode }}`
3. JS na stránce: `if (location.hash) { document.querySelector(location.hash)?.scrollIntoView({block:'center'}); }`

---

## 14. HTMX vzory

### hx-boost
- Na `<body>` je `hx-boost="true"` — všechny `<a>` a `<form>` automaticky AJAX
- **hx-boost="false"** povinné pro: file upload, file download, formuláře s `onsubmit="return confirm(...)"`

### Partial odpovědi
- Router vrací partial pro `HX-Request` (ne `HX-Boosted`), plnou stránku jinak:
  ```python
  if request.headers.get("HX-Request") and not request.headers.get("HX-Boosted"):
      return templates.TemplateResponse("partial.html", ctx)
  ```
- Partial = jen `<tr>` řádky (tbody-only), ne celá tabulka

### Inline editace
| Prvek | Vzor |
|-------|------|
| Filtrační bubliny | Plain `<a href>` (hx-boost swapne celou stránku) |
| Řazení sloupců | Plain `<a href>` |
| Vyhledávání | `hx-get` + `hx-target="#tbody-id"` |
| Inline editace | `hx-get`/`hx-post` + `hx-target="#section-id"` |

### hx-confirm
```html
<button hx-confirm="Opravdu smazat?">Smazat</button>
```

### Destruktivní akce
```html
<form onsubmit="return confirm('Opravdu?')">
```
