# UI konvence — FastAPI + Jinja2 + HTMX + Tailwind CSS (CDN)

Dodržuj tyto UI vzory a konvence při vývoji frontendu.

## Stack
- **FastAPI** backend s Jinja2 šablonami
- **HTMX** (CDN) pro interaktivitu bez JS frameworků
- **Tailwind CSS** (CDN) — žádný build pipeline, vše přes utility classes
- **Vanilla JS** only (žádný jQuery ani external knihovny kromě HTMX)
- Stránkový JS do `<script>` na konci `{% block content %}`, ne do separátních souborů

## 1. Layout

### Fixní header + scrollovatelný obsah
```html
<div class="flex flex-col" style="height:calc(100vh - 3rem)">
    <div class="shrink-0"><!-- header, filtry, search --></div>
    <div class="flex-1 overflow-y-auto min-h-0"><!-- scrollovatelný obsah --></div>
</div>
```
- `min-h-0` je nutné aby flex child mohl být menší než obsah
- Filtry/search se **nescrollují** — musí být vždy viditelné

### Detail stránka
1. Šipka zpět: `<a href="{{ back_url }}" class="text-sm text-gray-500 hover:text-gray-700">&larr; Zpět</a>`
2. Titulek: `<h1 class="text-2xl font-bold text-gray-800">`
3. Badge pod titulem: `rounded-full` badge
4. Obsah v grid layoutu

## 2. Tabulky

### Sticky hlavičky
```html
<thead class="bg-gray-50 border-b-2 border-gray-300 sticky top-0 z-10">
```

### Řazení sloupců
- Klikací hlavičky s SVG šipkou (nahoru/dolů)
- Sort parametry: `sort` (název sloupce), `order` (`asc`/`desc`)

### Layout
- `table-layout: fixed` s `<colgroup>` pro přesné šířky sloupců
- Dlouhé názvy: `truncate` + `title` tooltip
- Souhrnný řádek: `<tfoot class="border-t-2 border-gray-300 bg-gray-50">`

### Řádkové akce — SVG ikony
- Upravit: `text-gray-400 hover:text-blue-600 hover:bg-blue-50`
- Smazat: `text-gray-400 hover:text-red-600 hover:bg-red-50`
- Stáhnout: `text-blue-600 hover:bg-blue-50`
- Velikost: `w-4 h-4`, padding `p-1`, `rounded`, vždy `title` tooltip

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
| **Zrušit** | `px-3 py-1.5 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 text-sm font-medium` | Cancel |
| **Danger** | `px-3 py-1.5 bg-red-600 text-white rounded-lg hover:bg-red-700 text-sm font-medium` | Smazat |
| **Success** | `px-3 py-1.5 bg-green-600 text-white rounded-lg hover:bg-green-700 text-sm font-medium` | Vytvořit, Potvrdit |

- Upravit/Přidat/Uložit = **vždy** světle modré (obrysové)
- Zelená (success) pouze pro finální akce

### Uložit/Zrušit — nahoře vedle nadpisu (ne dole)
```html
<div class="flex items-center justify-between mb-4">
    <h2 class="text-lg font-semibold text-gray-700">Nadpis</h2>
    <div class="flex items-center gap-2">
        <button type="submit" class="...světle modrá...">Uložit</button>
        <button type="button" class="...šedá...">Zrušit</button>
    </div>
</div>
```

## 4. Inline editace (info/form partial vzor)

- **Info partial** — read-only + tlačítko "Upravit"
- **Form partial** — editační formulář s Uložit/Zrušit nahoře
- Wrapper `<div id="section-id">` obsahuje `{% include %}` — žádný extra markup
- 3 endpointy: GET formulář, POST uložení (vrací info s `saved=True`), GET info (cancel)

## 5. Filtrační bubliny + search bar (společný kontejner)

Bubliny a search bar v jednom bílém kontejneru se stínem:

```html
<div class="bg-white rounded-lg shadow mb-2">
    <!-- Bubliny -->
    <div class="flex gap-2 p-3 pb-2">
        <a href="..." class="flex-1 block rounded p-2 text-center hover:bg-gray-50 transition-colors
                  {% if active %}ring-2 ring-gray-400{% endif %}">
            <p class="text-lg font-bold text-gray-800">{{ count }}</p>
            <p class="text-xs text-gray-500">Label</p>
        </a>
    </div>

    <!-- Druhý řádek bublin (volitelný): px-3 pb-2 -->

    <!-- Oddělovač -->
    <div class="border-t border-gray-100"></div>

    <!-- Search bar -->
    <div class="flex items-center gap-3 px-3 py-2">
        <div class="flex-1">
            <input type="text" name="q" class="w-full px-3 py-1.5 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-transparent text-xs">
        </div>
        <select class="px-3 py-1.5 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 text-xs h-[30px]">
        </select>
    </div>
</div>
```

### Pravidla
- Bubliny **nemají vlastní `shadow` ani `rounded-lg`** — kontejner řeší obojí
- Styl bublin: `flex-1 block rounded p-2 text-center hover:bg-gray-50 transition-colors`
- Barevné varianty (bg-gray-50, bg-blue-50, bg-orange-50) pro vizuální rozlišení typů
- Aktivní bublina: `ring-2 ring-{color}-400`
- Split bubliny (dvě hodnoty v jedné): vnitřní divider `w-px bg-gray-200`
- Search bar oddělený tenkou čarou `border-t border-gray-100`
- Select: `h-[30px]` pro shodnou výšku s inputem
- Dvě řady bublin: klik v 1. řadě resetuje 2. řadu na "Vše" (a obráceně)

## 6. Status badge

```html
<span class="px-2 py-1 text-xs font-medium bg-{color}-100 text-{color}-800 rounded-full">
```
- Šedá = draft/neutrální, zelená = active/success, modrá = info, červená = error, žlutá = warning
- Vždy `rounded-full`, nikdy `rounded`

## 7. Prázdné stavy

```html
<p class="text-center text-gray-500 text-sm py-8">
    Žádné záznamy. <a href="/pridej" class="text-blue-600 hover:underline">Přidat první</a>
</p>
```

## 8. Formátování

| Typ | Formát | Příklad |
|-----|--------|---------|
| Tisíce | `"{:,}".format(x).replace(",", " ")` | 1 234 567 |
| Procenta s +/- | `"{:+.2f}".format(diff)` | +1.23 |
| Datum | `strftime('%d.%m.%Y')` | 27.02.2026 |
| Chybějící hodnota | `—` (pomlčka) | — |

Barevné kódování: záporné `text-red-600`, kladné `text-blue-600`, nula `text-green-600`

## 9. Back URL navigace

- Odkaz na detail: `?back={{ list_url|urlencode }}`
- Propagovat `back` přes: filtrační bubliny, HTMX hidden inputy, řadící odkazy
- Obnova scroll pozice: řádky mají `id`, back URL obsahuje `#hash`, JS `scrollIntoView({block:'center'})`

## 10. HTMX vzory

- `hx-boost="true"` na `<body>` — všechny `<a>` a `<form>` automaticky AJAX
- `hx-boost="false"` povinné pro: file upload/download, `onsubmit="return confirm(...)"`
- Partial odpovědi: router vrací partial pro `HX-Request` (ne `HX-Boosted`)
- Vyhledávání: `hx-trigger="keyup changed delay:300ms"`, `hx-push-url="true"`
- Hidden inputy pro stav filtrů VEDLE inputu, NE uvnitř tbody

| Prvek | Vzor |
|-------|------|
| Filtrační bubliny | Plain `<a href>` (hx-boost swapne celou stránku) |
| Řazení sloupců | Plain `<a href>` |
| Vyhledávání | `hx-get` + `hx-target="#tbody-id"` |
| Inline editace | `hx-get`/`hx-post` + `hx-target="#section-id"` |

## 11. Potvrzení destruktivních akcí

- Standardní: `hx-confirm="Opravdu smazat?"`
- Kritické: textový input s klíčovým slovem + disabled tlačítko
