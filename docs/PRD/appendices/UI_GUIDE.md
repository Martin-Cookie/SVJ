# UI Guide — konvence pro frontend

Tento soubor je **jediný zdroj pravdy** pro UI/frontend vzory a konvence. Stack: **FastAPI + Jinja2 + HTMX + Tailwind CSS (CDN)**.

> Backend pravidla (routery, SQLAlchemy, modely, URL konvence, workflow) jsou v [CLAUDE.md](../CLAUDE.md).

---

## 1. Layout

### Detail stránka
1. Šipka zpět (viz [Back link](#back-link) níže)
2. Titulek: `<h1 class="text-2xl font-bold text-gray-800">` + badge v `flex items-center gap-3`
3. Badge vedle titulku: `px-2 py-0.5 text-xs font-medium rounded-full` (typ osoby, propojení, RČ/IČ)
4. **Info karta** — 4-sloupcový grid pod header (viz [Detail entity — info karta](#detail-entity--info-karta))
5. Scrollovatelný obsah pod info kartou

### Detail entity — info karta (povinný vzor)

Každá entita s identifikací, kontakty a adresami (vlastníci, nájemci) MUSÍ používat tento layout:

```html
<div class="bg-white rounded-lg shadow mb-3">
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 divide-y md:divide-y-0 md:divide-x divide-gray-100">
        <div class="p-3" id="identity-section">{% include "partials/owner_identity_info.html" %}</div>
        <div class="p-3" id="contact-section">{% include "partials/owner_contact_info.html" %}</div>
        <div class="p-3" id="perm-address-section">{% include "partials/owner_address_info.html" %}</div>
        <div class="p-3" id="corr-address-section">{% include "partials/owner_address_info.html" %}</div>
        {# Nájemci: tenants/partials/_tenant_identity_info.html atd. #}
    </div>
</div>
```

**Pravidla:**
- Každý sloupec = samostatná sekce s vlastním HTMX inline editací (viz [§ 4](#4-inline-editace-infoform-partial-vzor))
- Sekce heading: `text-sm font-semibold text-gray-700`
- Data řádky: `space-y-1 text-xs`, každý řádek `flex justify-between` s `text-gray-500` label a `text-gray-900` value
- Edit tlačítko: `inline-flex items-center gap-1 px-2 py-1 text-xs font-medium text-blue-600 border border-blue-300 rounded hover:bg-blue-50` s tužkou SVG (`w-3 h-3`)
- **Propojená entita** (nájemce→vlastník): zobrazit data read-only + "Vlastník →" link místo edit tlačítka
- **Nepropojená entita**: zobrazit vlastní data + "Upravit" tlačítko per sekce
- Adresní sekce jsou parametrické (`prefix="perm"/"corr"`) — jeden partial, dva include s `{% with %}`
- Prázdné hodnoty vždy `—` (em-dash), nikdy skrývat řádek

### Back link
Zpětný odkaz na KAŽDÉ stránce s `back_url` — jednotný styl napříč celým projektem:
```html
{% if back_url %}
<div class="mb-3">
    <a href="{{ back_url }}" class="text-sm text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300">
        &larr; {{ back_label }}
    </a>
</div>
{% endif %}
```
- Vždy `text-sm` + `text-blue-600` + `&larr;` entita — nikdy SVG ikona, nikdy `text-xs`, nikdy `text-gray-*`
- Obaleno v `<div class="mb-3">` — nikdy `inline-flex`, nikdy bez wrapperu
- Dark mode: `dark:text-blue-400 dark:hover:text-blue-300`
- Label dynamický z routeru (viz [docs/NAVIGATION.md](NAVIGATION.md))

### Šířky stránek
| Typ stránky | Max-width | Příklad |
|-------------|-----------|---------|
| **Tabulka/seznam** (desítky řádků, řaditelné sloupce) | žádné omezení (full width) | vlastníci, jednotky, matice plateb, dlužníci, vyúčtování, předpisy roku |
| **Hub/index** (stat karty + přehled) | `max-w-6xl mx-auto` | `/platby`, přehled |
| **Detail entity** | `max-w-3xl mx-auto` nebo `max-w-4xl mx-auto` | detail předpisu, detail vyúčtování |
| **Formulář/import** | `max-w-2xl mx-auto` | import předpisů, import výpisů |
- Tabulkové stránky NIKDY nemají `max-w-*xl` — tabulka potřebuje celou šířku
- Detail a formuláře mají `mx-auto` pro centrování

### Fixní header + scrollovatelný obsah
```html
<div class="flex flex-col" style="height:calc(100vh - 3rem)">
    <div class="shrink-0"><!-- header, bubliny, search --></div>
    <div class="flex-1 overflow-y-auto overflow-x-hidden min-h-0"><!-- scrollovatelný obsah --></div>
</div>
```
- `3rem` = top+bottom padding z `<main class="p-6">`
- **`min-h-0`** je nutné aby flex child mohl být menší než obsah (bez toho se flex item roztáhne na výšku obsahu a overflow nefunguje)
- **`overflow-y-auto`** (NE `overflow-auto`) — explicitní osa je nutná pro správnou obnovu scroll pozice při HTMX boost navigaci. S `overflow-auto` HTMX neobnoví scroll pozici vnitřního kontejneru po návratu zpět
- **`overflow-x-hidden`** pro běžné tabulky. Pro široké tabulky (matice plateb) použít `overflow-x-auto`
- Bubliny/search se **nescrollují** — musí být vždy viditelné

---

## 2. Tabulky

> **Kdy použít tabulku vs karty:** Tabulkový layout (sort, search, bubliny, HTMX partial) je pro datové seznamy s desítkami/stovkami řádků (vlastníci, jednotky, lístky, logy). Pro malé admin seznamy (~5–15 položek, např. číselníky, emailové šablony, členové výboru) použít kompaktní layout — karty s inline edit (viz § 4 alternativní vzor).

### Sticky hlavičky
```html
<thead class="bg-gray-50 border-b-2 border-gray-300 sticky top-0 z-10">
```

### Řazení sloupců
- Klikací hlavičky s indikátorem směru (šipka SVG nahoru/dolů)
- Implementace přes `sort_th` macro (definované přímo v šabloně — dominantní přístup, 7 souborů) nebo `{% set _cols = [...] %}` + `{% for %}` cyklus (4 soubory)
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

### Stacked buňky (1 entita = více sub-záznamů)
- Když má entita v tabulce více souvisejících záznamů (vlastník → více jednotek, nájemce → více prostor), zobrazit **jeden řádek per entitu** a sub-záznamy naskládat pod sebou ve sloupcové buňce:
  ```html
  <td>
      <div class="flex flex-col gap-0.5">
          {% for rel in entity.active_rels %}
              <span>{{ rel.label }}</span>
          {% endfor %}
      </div>
  </td>
  ```
- Sub-záznamy ve více sloupcích (prostor / nájemné / VS) musí být **zarovnané pořadím** — každý sloupec iteruje stejný list ve stejném pořadí (řazení dle `space_number` / `unit_number`)
- Hledání musí prohledávat **všechny** sub-záznamy (ne jen první), řazení podle součtu (např. `rent`) sumuje přes celý list
- Export v tomto případě obvykle tvoří **1 řádek per sub-záznam** (per smlouva / per jednotka) — uvést v hlavičce exportu
- Používáno v: vlastníci (více jednotek), nájemci (více prostor)

---

## 3. Formuláře

### Input styly — 3 tiery

| Tier | CSS | Kde |
|------|-----|-----|
| **Full forms** | `px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500` | SMTP formulář, voting create, zálohy |
| **Inline edits** | `px-2 py-1.5 border border-gray-300 rounded text-xs focus:ring-2 focus:ring-blue-500` | Owner identity/contact/address forms |
| **Search bars** | `px-3 py-1.5 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-transparent text-xs` | Všechny search inputy |

### Tlačítka — kanonické styly

| Typ | CSS | Použití |
|-----|-----|---------|
| **Akce (světle modré)** | `px-3 py-1.5 text-sm font-medium text-blue-600 border border-blue-300 rounded-lg hover:bg-blue-50 transition-colors` | Upravit, Přidat, Uložit |
| **Akce malá (inline)** | `px-2 py-1 text-xs font-medium text-blue-600 border border-blue-300 rounded hover:bg-blue-50` | Uložit/Přidat v tabulkách |
| **Akce s ikonou** | + `inline-flex items-center gap-1` | Upravit/Přidat s SVG ikonou |
| **Zrušit** | `px-3 py-1.5 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 text-sm font-medium` | Zrušit (cancel) — varianta `bg-gray-100 hover:bg-gray-200` pro admin sekce |
| **Sekundární akce (plné modré)** | `px-3 py-1.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-medium transition-colors` | Export Excel, Vytvořit zálohu, Uložit mapping |
| **Danger** | `px-3 py-1.5 bg-red-600 text-white rounded-lg hover:bg-red-700 text-sm font-medium` | Smazat |
| **Success** | `px-3 py-1.5 bg-green-600 text-white rounded-lg hover:bg-green-700 text-sm font-medium` | Dokončit, Vytvořit, Potvrdit |

- Upravit, Přidat a Uložit musí být **vždy** světle modré (obrysové) — na všech úrovních
- Zelená (success) pouze pro finální akce (Dokončit, Vytvořit, Potvrdit)

### Tlačítka — vždy nahoře vedle nadpisu
Akční tlačítka (Uložit, Nahrát, Zrušit) se umísťují **nahoře vedle nadpisu** v flex kontejneru — nikdy dole pod formulářem. Platí pro inline editaci i upload formuláře.

```html
<div class="flex items-center justify-between mb-4">
    <h2 class="text-lg font-semibold text-gray-700">Nadpis</h2>
    <div class="flex items-center gap-2">
        <button type="submit" form="form-id"
                class="px-3 py-1.5 text-sm font-medium text-blue-600 border border-blue-300 rounded-lg hover:bg-blue-50 transition-colors">Uložit</button>
        <button type="button" class="px-3 py-1.5 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 text-sm font-medium">Zrušit</button>
    </div>
</div>
```

- Pokud je tlačítko **mimo** `<form>`, propojí se přes `form="id"` atribut
- Pokud je tlačítko **uvnitř** `<form>` (inline editace), `form` atribut není potřeba

### Zobrazení validační chyby ve formuláři
Při validační chybě (neplatný email, duplicita, rozsah mimo meze) router vrátí formulářovou šablonu s proměnnou `error`:
```html
{% if error %}
<div class="bg-red-50 border border-red-200 rounded-lg p-3 mb-3">
    <p class="text-sm text-red-800">{{ error }}</p>
</div>
{% endif %}
```
- Formulář zachová vyplněná pole přes `form_data` dict (viz [CLAUDE.md — Formulářová validace](../CLAUDE.md))
- Pro varování (ne chyby) se používá žlutý box: `bg-yellow-50 border-yellow-200 text-yellow-800`

### Varování při opuštění neuloženého formuláře
- Atribut `data-warn-unsaved` na `<form>` aktivuje `beforeunload` varování při neuložených změnách
- `app.js` sleduje `input` event na formuláři a nastavuje `_formDirty` flag
- Flag se resetuje při submit a při HTMX boosted navigaci (`htmx:beforeRequest`)
- Používáno na formulářích kde ztráta dat je bolestivá (voting create, settings)

### Upload formuláře — skryté tlačítko

Submit tlačítko je **skryté** (`hidden`) dokud uživatel nevybere soubor. Tlačítko je vedle nadpisu, formulář má `id` a tlačítko `form="id"`.

**Jednoduchý vzor** (jen soubor):
```html
<div class="flex items-center justify-between mb-3">
    <h2 class="text-sm font-semibold text-gray-700">Nahrát soubor</h2>
    <button id="submit-btn" type="submit" form="upload-form"
            class="hidden px-3 py-1.5 text-sm font-medium text-blue-600 border border-blue-300 rounded-lg hover:bg-blue-50 transition-colors">
        Nahrát a zpracovat
    </button>
</div>

<form id="upload-form" action="..." method="post" enctype="multipart/form-data" hx-boost="false">
    <input type="file" name="file" accept=".xlsx,.xls" required
           onchange="document.getElementById('submit-btn').classList.toggle('hidden', !this.files.length)">
</form>
```

**Vzor s více podmínkami** (soubor + povinné pole):
```html
<input type="text" id="title-input" required oninput="checkFormReady()">
<input type="file" id="file-input" required onchange="checkFormReady()">

<script>
function checkFormReady() {
    var hasFile = document.getElementById('file-input').files.length > 0;
    var hasTitle = document.getElementById('title-input').value.trim() !== '';
    document.getElementById('submit-btn').classList.toggle('hidden', !(hasFile && hasTitle));
}
</script>
```

**Vzor s webkitdirectory přepínáním** (soubor/adresář toggle):

Nativní `<input type="file">` neumožňuje změnit text tlačítka ("Vybrat soubor") ani placeholder ("není vybrán žádný soubor"). Proto se používá **custom wrapper**: skrytý input + `<label>` stylovaný jako tlačítko + `<span>` s textem.

```html
<div class="flex items-center">
    <label for="file-input" id="file-btn-label"
           class="inline-block py-2 px-4 rounded-lg text-sm font-medium bg-blue-50 text-blue-700 hover:bg-blue-100 cursor-pointer">
        Vybrat soubor
    </label>
    <span id="file-name" class="ml-4 text-sm text-gray-500">není vybrán žádný soubor</span>
</div>
<input type="file" id="file-input" name="files" accept=".pdf" multiple required
       onchange="updateFileName(this); checkFormReady()"
       class="hidden">
```

```javascript
function updateFileName(inp) {
    var nameEl = document.getElementById('file-name');
    var dirMode = document.getElementById('dir-toggle').checked;
    if (inp.files.length > 0) {
        nameEl.textContent = dirMode
            ? inp.files.length + ' souborů v adresáři'
            : (inp.files.length === 1 ? inp.files[0].name : inp.files.length + ' souborů');
    } else {
        nameEl.textContent = dirMode ? 'není vybrán žádný adresář' : 'není vybrán žádný soubor';
    }
}
function toggleDirMode(on) {
    var inp = document.getElementById('file-input');
    inp.value = '';  // reset výběru
    document.getElementById('file-btn-label').textContent = on ? 'Vybrat adresář' : 'Vybrat soubor';
    document.getElementById('file-name').textContent = on ? 'není vybrán žádný adresář' : 'není vybrán žádný soubor';
    // ... přepnutí atributů (webkitdirectory, accept, multiple) ...
    document.getElementById('submit-btn').classList.add('hidden');  // skrýt po resetu
}
```

**Vzor s AJAX prefill** (šablona předvyplní pole):
```javascript
// Po úspěšném AJAX prefill názvu:
if (!titleInput.value.trim() && meta.title) {
    titleInput.value = meta.title;
    document.getElementById('submit-btn').classList.toggle('hidden', !meta.title.trim());
}
```

**Vzor s XHR upload progress barem** (pro upload stovek souborů):

Standardní `<form>` submit neposkytuje zpětnou vazbu o průběhu uploadu. Pro velké uploady (stovky PDF) se používá `XMLHttpRequest` s `upload.onprogress`:

```html
<div id="upload-progress" class="hidden bg-white rounded-lg shadow p-6 max-w-2xl mt-4">
    <div class="flex justify-between items-center">
        <span class="text-sm font-medium text-gray-700">Nahrávání souborů na server...</span>
        <span id="upload-pct-text" class="text-sm text-gray-500">0 %</span>
    </div>
    <div class="relative w-full bg-gray-200 rounded-full h-5 overflow-hidden mt-2">
        <div id="upload-bar" class="bg-blue-600 h-5 rounded-full transition-all duration-300" style="width:0%"></div>
        <span id="upload-bar-text" class="absolute inset-0 flex items-center justify-center text-xs font-medium text-gray-700">0 %</span>
    </div>
    <p id="upload-status" class="text-xs text-gray-400 mt-2">Připravuji nahrání...</p>
</div>
```

```javascript
function startUpload() {
    var form = document.getElementById('upload-form');
    var fd = new FormData(form);
    var xhr = new XMLHttpRequest();
    document.getElementById('upload-progress').classList.remove('hidden');
    xhr.upload.onprogress = function(e) {
        if (e.lengthComputable) {
            var pct = Math.round(e.loaded / e.total * 100);
            document.getElementById('upload-bar').style.width = pct + '%';
            document.getElementById('upload-bar-text').textContent = pct + ' %';
            document.getElementById('upload-pct-text').textContent = pct + ' %';
        }
    };
    xhr.onload = function() { window.location.href = /* redirect URL */; };
    xhr.open('POST', form.action);
    xhr.send(fd);
}
```

- Submit tlačítko `type="button" onclick="startUpload()"` (ne `type="submit"`)
- Progress overlay se zobrazí ihned po kliknutí
- Po dokončení uploadu `xhr.onload` provede redirect na processing stránku
- Používáno v `tax/upload.html` a `tax/upload_additional.html`

### Lazy dropdown přes `<template>` element

Pro tabulky s mnoha řádky a opakovaným `<select>` (např. 221 řádků × 446 vlastníků = ~98 000 `<option>`) — options se renderují jednou v `<template>` a klonují na focus:

```html
<!-- Jednou na stránce (server-rendered, není v DOM) -->
<template id="owner-options">
    {% for owner in owners %}
    <option value="{{ owner.id }}">{{ owner.display_name }} (j. {{ units }})</option>
    {% endfor %}
</template>

<!-- V každém řádku tabulky -->
<select name="owner_id" onfocus="populateSelect(this)" class="...">
    <option value="">Vybrat...</option>
</select>
```

```javascript
function populateSelect(sel) {
    if (sel.options.length > 1) return;  // už naplněno
    var tpl = document.getElementById('owner-options');
    if (!tpl) return;
    var frag = tpl.content.cloneNode(true);
    sel.appendChild(frag);
}
```

- `<template>` obsah není součástí DOM → nezvyšuje počet elementů na stránce
- `cloneNode(true)` je bezpečný (DOM API, ne innerHTML)
- Používáno v `tax/matching.html` — snížení HTML z ~5 MB na ~924 KB

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
| `GET /{id}/{sekce}-formular` | Načtení formuláře | Form partial |
| `POST /{id}/{sekce}-upravit` | Uložení změn | Info partial s `saved=True` |
| `GET /{id}/{sekce}-info` | Zobrazení (cancel) | Info partial |

Pro adresy (parametrické): `GET /{id}/adresa/{prefix}/formular`, `POST /{id}/adresa/{prefix}/upravit`, `GET /{id}/adresa/{prefix}/info`

Pojmenování sekcí: `identita`, `kontakt`, `adresa/{perm|corr}` (čeština v URL, konzistentní napříč vlastníky i nájemci)

### Alternativní vzor (administrace — seznam položek)

Pro stránky s mnoha editovatelnými položkami (číselníky, šablony) — view i form jsou oba na stránce, přepínání přes CSS `hidden` class + JS:

```html
<!-- View mode -->
<span id="cl-val-42" class="text-sm cursor-pointer hover:text-blue-600"
      onclick="clStartEdit(42)">Hodnota</span>

<!-- Edit mode (hidden) -->
<form id="cl-edit-42" class="hidden"
      action="/entita/42/upravit" method="post" hx-boost="false">
    <input type="text" name="new_value" value="Hodnota" required
           onkeydown="if(event.key==='Escape'){event.preventDefault();clCancelEdit(42)}">
</form>
```

```javascript
function clStartEdit(id) {
    document.getElementById('cl-val-' + id).classList.add('hidden');
    document.getElementById('cl-actions-' + id).classList.add('hidden');
    var form = document.getElementById('cl-edit-' + id);
    form.classList.remove('hidden');
    var input = form.querySelector('input');
    input.focus();
    input.select();
}
function clCancelEdit(id) {
    document.getElementById('cl-edit-' + id).classList.add('hidden');
    document.getElementById('cl-val-' + id).classList.remove('hidden');
    document.getElementById('cl-actions-' + id).classList.remove('hidden');
}
```

- Formuláře používají standardní POST (`hx-boost="false"`) s redirect po uložení
- Enter odesílá formulář, Escape ruší editaci
- Vhodné pro kompaktní seznamy (číselníky, tagy) — ne pro velké formuláře s mnoha poli

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

### Accessibility — SVG ikony a tlačítka
- Dekorativní SVG ikony vždy `aria-hidden="true"` — konzistentně napříč celým projektem (42+ souborů)
- **Icon-only tlačítka** (bez viditelného textu) musí mít `aria-label` shodný s `title` atributem
- Error/flash zprávy vždy `role="alert"` pro screen readery

### Accessibility — modály a focus
- **ARIA atributy na modalech:**
  - Confirm/alert modaly: `role="alertdialog"`, `aria-modal="true"`, `aria-describedby="message-id"`
  - PDF/content modaly: `role="dialog"`, `aria-modal="true"`, `aria-labelledby="title-id"`
  - Backdrop overlay: `role="presentation"`
- **Focus trap** (`_trapFocus()` v `app.js`): Tab/Shift+Tab cyklí jen přes focusovatelné elementy uvnitř aktivního modalu
- **Focus restore** (`_restoreFocus()` v `app.js`): po zavření modalu se focus vrátí na element, který modal otevřel (`_modalTrigger`)
- Aktivní pro: `#pdf-modal`, `#confirm-modal`, `#send-confirm-modal`

---

## 6. Formulář přidání (toggle hidden)

Vzor pro "přidat novou položku" bez přechodu na jinou stránku:
1. Tlačítko `+ Přidat` (světle modré) — klik skryje Přidat a odkryje Uložit+Zrušit + formulář
2. **Uložit** a **Zrušit** se zobrazí na stejném místě (nahoře) — nahradí tlačítko Přidat
3. Po uložení/zrušení se Přidat vrátí zpět (HTMX swap nebo toggle)

### Zelený pruh — vizuální odlišení přidávacího formuláře

Každý standalone formulář pro přidání nové entity (vlastník, jednotka, prostor, nájemce, VS, zůstatek) MUSÍ mít **zelený levý pruh** `border-l-4 border-green-500`. Vizuálně odlišuje přidávací formulář od okolního obsahu a signalizuje uživateli „zde se vytváří nová položka".

```html
<!-- Standalone přidávací formulář -->
<div class="bg-white dark:bg-gray-800 rounded-lg shadow p-4 mb-3 border-l-4 border-green-500">
    <form ...>
        <h3 class="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">Nový ...</h3>
        <!-- fields -->
    </form>
</div>
```

- **Kde ANO**: samostatné karty pro přidání entity (vlastníci, jednotky, prostory, nájemci, VS, zůstatky)
- **Kde NE**: malé inline formuláře uvnitř existující karty (výbor, číselníky, adresy SVJ) — ty používají `border-t border-gray-200` jako separator

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

### `qs()` — querystring helper makro

Pro skládání odkazů s proměnlivým počtem query parametrů (bubliny, sort, search, back) použij lokální Jinja2 makro `qs()`, které vynechá prázdné hodnoty a automaticky urlencoduje. Čistší než ruční `?a={{a}}&b={{b}}` s `{% if %}` kolem každého páru — a odolnější vůči bugům typu `??` nebo `&&` v URL.

```jinja
{% macro qs(pairs) -%}
    {%- set parts = [] -%}
    {%- for k, v in pairs -%}{%- if v -%}{%- set _ = parts.append(k ~ '=' ~ (v|urlencode)) -%}{%- endif -%}{%- endfor -%}
    {%- if parts -%}?{{ parts|join('&') }}{%- endif -%}
{%- endmacro %}

<a href="/hlasovani{{ qs([('stav', stav), ('sort', current_sort), ('back', back_url)]) }}">
```

**Výhody:**
- Prázdné hodnoty se vynechají (žádné `?stav=&sort=`)
- `?` se vygeneruje jen když jsou parametry
- Automatický `urlencode` na každou hodnotu
- Čitelné — pořadí parametrů je deklarativní seznam dvojic

**Kde se používá:** `voting/index.html`, `payments/vypisy.html`. Preferovat pro nové seznamové stránky s více bublinami + řazením + search + back URL.

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
- **Sdílený progress bar** pro davkové odesílání (`_send_progress.html` + `_send_progress_inner.html`) — podrobný popis v [docs/NEW_MODULE_CHECKLIST.md](NEW_MODULE_CHECKLIST.md)

---

### Komplexní stránky — příklady

- **Nesrovnalosti v platbách** (`nesrovnalosti_preview.html`): checkboxy pro výběr nesrovnalostí + test email konfigurace + náhled emailu. Kombinuje hromadný výběr (§ 15), progress bar odesílání a inline nastavení emailu

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
- **Navigace (A):** back link v `<div class="mb-3">` (viz [Back link](#back-link) v sekci 1)
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
- Formulář v `bg-white rounded-lg shadow p-6 max-w-2xl` (viz [Šířky stránek](#šířky-stránek) v sekci 1)
- Submit tlačítko **vedle titulku** (zóna C vpravo), ne uvnitř formuláře — propojení přes `form="id"`
- U upload formulářů je tlačítko **skryté** dokud není vybrán soubor (viz sekce 3 → Upload formuláře)

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

> Logika stavů (done, active, current+done, pending, sending), pravidlo "all green when complete" a override pro dokumenty jsou v [docs/NEW_MODULE_CHECKLIST.md](NEW_MODULE_CHECKLIST.md).

### Dvě varianty stepperu
- **Plný stepper** (`partials/wizard_stepper.html`) — samostatný blok nad obsahem stránky, používá se na detail/workflow stránkách
- **Kompaktní stepper** (`partials/wizard_stepper_compact.html`) — inline v kartě na seznamu, kompaktnější layout pro přehled stavu entity
- Obě varianty sdílí stejný kontext z router helperu (`wizard_steps`, `wizard_current`, `wizard_label`)

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

## 12b. Tooltipy entit (povinný vzor)

Každý badge/odkaz/dropdown na entitu (jednotka, prostor) MUSÍ mít `title` tooltip se sjednoceným pořadím:

**Jméno · VS · Entita · Částka**

| Entita | Tooltip formát | Příklad |
|--------|---------------|---------|
| Jednotka | `jméno · VS: xxx · Jednotka: č. xxx · Předpis: xxx Kč/měs` | `Novák Jan · VS: 12345 · Jednotka: č. 171 · Předpis: 3 041 Kč/měs` |
| Prostor | `jméno · VS: xxx · Prostor: číslo — označení · Nájem: xxx Kč/měs` | `Movie s.r.o. · VS: 0512019 · Prostor: 10 — B1 02.06 · Nájem: 1 685 Kč/měs` |

- Jméno je podmíněné (`{% if ... %}`) — zobrazit jen když existuje
- Oddělovač: ` · ` (mezera-tečka-mezera)
- Částka vždy s filtrem `fmt_num` a suffixem `Kč/měs`
- Data pro tooltipy se připravují v routeru jako lookup dicty: `unit_owner_names`, `unit_vs`, `unit_monthly`, `space_tenant_names`, `space_vs`, `space_monthly`
- Tooltip musí být na VŠECH výskytech entity: badge (návrhy/napárované), `<a>` linky, `<select>` dropdown i `<option>` elementy
- **`<select>` dropdown**: `title` na `<select>` se nastavuje pro pre-selected hodnotu + `onchange="this.title=this.options[this.selectedIndex].title||''"` pro aktualizaci při změně výběru

## 12c. Suggestion dropdowny (přiřazení s předvýběrem)

Vzor pro dropdowny kde backend navrhuje předvybranou hodnotu (např. párování plateb → jednotka/prostor):

### Vizuální rozlišení
- **S návrhem** (pre-selected): `border-green-500 bg-green-50 dark:bg-green-900/20 dark:border-green-600` — dropdown je viditelný rovnou (ne schovaný za tlačítkem)
- **Bez návrhu**: `border-gray-300 dark:border-gray-600 dark:bg-gray-700` — skrytý za tlačítkem "přiřadit"

### Potvrzovací vzor
Dropdown NIKDY neodesílá formulář při změně (`onchange`). Vždy vyžaduje explicitní potvrzení:
```html
<form class="inline-flex items-center gap-1">
    <select class="w-64 text-xs border rounded px-1 py-0.5 ...">...</select>
    <button type="submit" class="px-1.5 py-0.5 bg-green-600 text-white rounded text-xs" title="Potvrdit">✓</button>
    <button type="button" class="px-1.5 py-0.5 bg-gray-200 text-gray-600 rounded text-xs" title="Zrušit">✕</button>
</form>
```

### Pořadí v dropdown options
Shodné s tooltip pořadím (§ 12b): **Jméno · Číslo · VS · Částka**, oddělovač ` · `:
- Jednotka: `Novák Jan · 501 · VS: 12345 · 3 041 Kč`
- Prostor: `Movie s.r.o. · 10 — B1 02.06 · VS: 0512019 · 1 685 Kč`

### Řazení
Dropdown je řazen **abecedně podle prvního zobrazeného atributu** (jméno vlastníka/nájemce). Entity bez jména na konec.

### Backend suggest map
Router buduje `suggest_map: dict[payment_id, entity_id]` přes sdílený helper `_build_suggest_map(payments, name_index)` — porovnání slov z `counter_account_name + note + message` proti indexu jmen.

### Barevné badge pro typ entity
- Jednotka: `bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300`
- Prostor: `bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-300`

---

## 13. Back URL navigace

> Kompletní logika back parametru (propagace, chaining, `list_url` vs `back_url`, `back_label`) je v [docs/NAVIGATION.md](NAVIGATION.md). Zde jsou jen UI/HTML specifika.

### Obnova scroll pozice — back URL (hash)

Mechanismus pro zachování přesné scroll pozice při navigaci seznam → detail → zpět.

#### Požadavky na šablonu
1. Řádky mají `id` (např. `id="owner-{{ owner.id }}"`)
2. Back URL obsahuje `#hash`: `?back={{ (list_url ~ '#owner-' ~ owner.id)|urlencode }}`
3. JS na stránce volá sdílenou funkci: `scrollToHash();` (definovaná v `app.js`)
4. **Scroll kontejner MUSÍ mít `overflow-y-auto overflow-x-hidden min-h-0`** (viz § 1 Fixní header)
5. **CSS `scroll-margin-top: 40px`** na `tr[id], div[id]` (`custom.css`) — browser nativně respektuje offset při hash scrollu a řádek se nezakryje sticky `<thead>` hlavičkou

#### Jak to funguje — dvouvrstvý mechanismus v `app.js`

Scroll pozice se obnovuje dvěma spolupracujícími mechanismy:

**1. Přesná pozice přes sessionStorage (primární):**
- Před navigací na detail: `htmx:beforeRequest` handler volá `_saveScrollPos()` — uloží `scrollTop` do sessionStorage pod klíčem `svj_scroll_{pathname}{search}`
- Po návratu: `MutationObserver` zavolá `_restoreScrollPos()` — obnoví přesnou pixel pozici
- Uživatel vidí seznam přesně tak, jak ho opustil — kliknutý řádek zůstane na stejném místě (uprostřed, dole, kdekoliv)

**2. Hash scroll přes `scrollToHash()` (fallback):**
- Pokud sessionStorage nemá uloženou pozici (první návštěva, vymazaný storage, přímý odkaz s hashem)
- `scrollToHash()` najde element dle `location.hash`, najde nejbližší `.overflow-y-auto` kontejner a nastaví `scrollTop = el.offsetTop - 40`
- Řádek se posune na **začátek** viditelné oblasti (pod sticky header)

#### HTMX boost a timing

HTMX boost navigace (`hx-boost="true"` na `<body>`) swapuje obsah `<body>` přes AJAX. Toto vytváří timing problém:

- **Inline `<script>` v šablonách se spustí PŘED dokončením body swapování** — operují nad starým DOM
- Proto `scrollToHash()` volaný z inline scriptu funguje jen při prvním načtení stránky (non-boost)
- Pro boost navigaci řeší scroll **MutationObserver** v `app.js`:
  1. Sleduje `document.body` s `{childList: true}`
  2. Jakmile HTMX vymění obsah body, observer detekuje změnu
  3. Pokud `location.hash` existuje a cílový element je v novém DOM:
     - Počká 80ms (browser dokončí layout)
     - Zkusí `_restoreScrollPos()` (přesná sessionStorage pozice)
     - Pokud sessionStorage nemá data → fallback na `scrollToHash()`

**HTMX config:** `<meta name="htmx-config" content='{"scrollIntoViewOnBoost":false}'>` v `base.html` zabrání HTMX výchozímu scrollu na začátek stránky.

**`htmx:afterSettle` handler:** Volá `_restoreScrollPos()` pouze pro non-hash navigaci (POST+redirect formuláře). Když URL obsahuje hash, nechá MutationObserver řešit scroll — ten má přístup k novému DOM.

#### Důležité implementační detaily

**Guard `top < 0` (ne `<= 0`):** Funkce `_restoreScrollPos()` akceptuje uloženou pozici `0` jako platnou. Prvních ~15 řádků v dlouhém seznamu je viditelných bez scrollu (`scrollTop = 0`). S guardem `<= 0` by se pro tyto řádky pozice neobnovila a fallback `scrollToHash()` by je posunul na začátek kontejneru.

**Proč ne `scrollIntoView({block:'center'})`:** Pro řádky blízko začátku seznamu se prohlížeč nedokáže vycentrovat (není dost obsahu nad nimi), takže degraduje na `block: 'start'` — řádek skončí přímo pod sticky thead a je neviditelný. Funkce `scrollToHash()` v `app.js` řeší offset manuálně.

**`app.js` MUSÍ být načten PŘED `{% block content %}`** — inline `<script>` v šablonách volají `scrollToHash()`, která musí být již definovaná. Proto je `<script src="app.js">` v `base.html` umístěn před `<main>` s content blokem.

**Proč `overflow-y-auto` a ne `overflow-auto`:** HTMX boost navigace obnoví scroll pozici vnitřního kontejneru POUZE pokud má explicitní `overflow-y-auto`. S `overflow-auto` se scroll pozice ztratí a element skočí na začátek tabulky. `min-h-0` je nutné aby flex-1 child respektoval výšku rodiče a vytvořil interní scrollbar.

#### Stránky používající tento mechanismus

| Stránka | Typ scroll restore | Row ID prefix |
|---------|-------------------|---------------|
| Vlastníci | seznam→detail→zpět | `owner-` |
| Jednotky | seznam→detail→zpět | `unit-` |
| Nájemci | seznam→detail→zpět | `tenant-` |
| Prostory | seznam→detail→zpět | `space-` |
| Symboly | inline edit (POST+redirect) | `vs-` |
| Vyúčtování | inline edit (POST+redirect) | dle entity |
| Předpisy detail | inline edit (POST+redirect) | dle entity |
| Dlužníci | inline edit (POST+redirect) | dle entity |
| Hlasování lístky | sub-detail navigace | `ballot-` |

### Obnova scroll pozice — POST+redirect (sessionStorage)

Pro stránky s inline formuláři (POST+redirect na stejnou stránku, např. platební modul), kde se má scroll pozice zachovat **na pixel přesně**:

1. **Redirect obsahuje `#hash`** — router přidá `#element-id` do redirect URL
2. **JS uloží scrollTop před submitem** do sessionStorage
3. **JS obnoví přesnou pozici** po načtení stránky (nebo fallback na scrollIntoView)
4. **Hash se stripne** přes `history.replaceState` — zabrání prohlížeči přeskočit na element

```javascript
(function() {
    var SC_KEY = 'svj_scroll_payment';
    var sc = document.querySelector('.flex-1.overflow-y-auto');
    var hash = location.hash;

    // Strip hash → zabrání browser auto-scroll na anchor
    if (hash) {
        history.replaceState(null, '', location.pathname + location.search);
    }

    // Uložit scroll před každým POST (delegovaný listener — chytí i dynamické formuláře)
    document.addEventListener('submit', function(e) {
        var form = e.target;
        if (form.getAttribute('hx-boost') === 'false' || form.closest('[hx-boost="false"]')) {
            if (sc) try { sessionStorage.setItem(SC_KEY, String(Math.round(sc.scrollTop))); } catch(e2) {}
        }
    });

    // Obnovit přesnou pozici (nebo fallback na scrollIntoView)
    if (hash && sc) {
        var saved;
        try { saved = sessionStorage.getItem(SC_KEY); sessionStorage.removeItem(SC_KEY); } catch(e) {}
        var top = saved !== null ? parseInt(saved, 10) : NaN;
        if (!isNaN(top) && top > 0) {
            sc.scrollTop = top;
        } else {
            var el = document.getElementById(hash.substring(1));
            if (el) {
                var container = el.closest('.overflow-y-auto');
                if (container) container.scrollTop = Math.max(0, el.offsetTop - 40);
                else el.scrollIntoView({block: 'center'});
            }
        }
        // Highlight řádku (žluté pozadí na 2s)
        var el = document.getElementById(hash.substring(1));
        if (el) {
            el.classList.add('bg-yellow-50', 'dark:bg-yellow-900/20');
            setTimeout(function() { el.classList.remove('bg-yellow-50', 'dark:bg-yellow-900/20'); }, 2000);
        }
    }
})();
```

**Klíčové body:**
- `history.replaceState` MUSÍ být před čímkoli jiným — jinak prohlížeč provede nativní scroll na anchor
- Delegovaný `document.addEventListener('submit', ...)` chytí i formuláře přidané dynamicky (toggle hidden)
- `SC_KEY` sdílený pro celý modul (všechny stránky plateb) — stačí jeden klíč

---

## 14. HTMX vzory

### hx-boost
- Na `<body>` je `hx-boost="true"` — všechny `<a>` a `<form>` automaticky AJAX
- **hx-boost="false"** povinné pro: file upload, file download, formuláře s `onsubmit="return confirm(...)"`

### Partial odpovědi
- Router vrací partial pro HTMX non-boosted requesty, plnou stránku jinak. Detekce: `is_htmx_partial(request)` z `app.utils` (viz [CLAUDE.md](../CLAUDE.md) § Utility funkce)
- Partial = jen `<tr>` řádky (tbody-only), ne celá tabulka

### Inline editace
| Prvek | Vzor |
|-------|------|
| Filtrační bubliny | Plain `<a href>` (hx-boost swapne celou stránku) |
| Řazení sloupců | Plain `<a href>` |
| Vyhledávání | `hx-get` + `hx-target="#tbody-id"` |
| Inline editace | `hx-get`/`hx-post` + `hx-target="#section-id"` |

### HTMX loading indicators
- Globální CSS v `custom.css` automaticky disable submit tlačítka během HTMX requestů:
  ```css
  .htmx-request button[type="submit"] { opacity: 0.5; pointer-events: none; }
  button[hx-post].htmx-request, button[hx-get].htmx-request { opacity: 0.5; pointer-events: none; }
  ```
- **Search input pulse**: `custom.css` animace `htmx-pulse` pulzuje border search inputu během HTMX requestu (vizuální feedback že se hledá):
  ```css
  .htmx-request input[type="text"][hx-get] { animation: htmx-pulse 1.5s ease-in-out infinite; }
  ```
- Žádné per-button spinnery — CSS pokryje všechny formuláře automaticky

### HTMX error handling
- `app.js` zachycuje `htmx:responseError` a `htmx:sendError`
- Zobrazí uživatelsky přívětivou českou chybovou hlášku s odkazem na reload
- Definováno globálně, neřeší se per-stránka

### Cache busting: app.js
- `base.html` načítá `app.js?v=N` — query string zabrání cachování staré verze
- **Při každé změně `app.js` inkrementovat `?v=N`** v `base.html`

### hx-push-url
- Všechny search inputy používají `hx-push-url="true"` — aktualizuje URL v prohlížeči při filtrování/hledání
- Umožňuje sdílení filtrované URL a navigaci zpět

### hx-confirm
```html
<button hx-confirm="Opravdu smazat?">Smazat</button>
```

### fetch() + innerHTML vs HTMX
- **`<script>` tagy v HTML vloženém přes `innerHTML` se NESPUSTÍ** — prohlížeč je ignoruje
- HTMX (`hx-get` + `hx-swap`) naopak skripty **vyhodnotí** — proto preferovat HTMX kde to jde
- Pokud je nutné použít fetch + innerHTML (např. expandovatelné řádky v tabulce), definovat JS funkce v nadřazené šabloně (té, která volá fetch)

---

## 15. Hromadný výběr (checkbox "Vybrat/Zrušit vše")

- **Vždy checkbox v hlavičce tabulky** (`<th>`), nikdy textový button "Vybrat vše" v toolbaru:
  ```html
  <th class="px-1 py-1.5 text-center">
      <input type="checkbox" id="xxx-toggle-all" onchange="xxxToggleAll(this.checked)">
  </th>
  ```
- JS vzor: `toggleAll(checked)` nastaví všechny checkboxy; `updateCount()` synchronizuje stav header checkboxu (`checked` / `indeterminate`):
  ```javascript
  function xxxUpdateCount() {
      var all = document.querySelectorAll('.xxx-checkbox');
      var checkedCount = document.querySelectorAll('.xxx-checkbox:checked').length;
      var toggle = document.getElementById('xxx-toggle-all');
      if (toggle) {
          toggle.checked = checkedCount === all.length && all.length > 0;
          toggle.indeterminate = checkedCount > 0 && checkedCount < all.length;
      }
  }
  ```
- Akční tlačítka (export, smazání, aktualizace) jsou `disabled` dokud není zaškrtnutý alespoň jeden checkbox
- Pokud se obsah (řádky s checkboxy) načítá dynamicky přes fetch/HTMX, **stav checkboxů se musí persistovat v sessionStorage**:
  - Klíč: `bulk_{field}_{value}` — unikátní pro každý kontext
  - Uložit: při každé změně checkboxu (`saveBulkChecks`)
  - Obnovit: po načtení nového HTML (`restoreBulkChecks`)
  - Select-all checkbox: synchronizovat `checked` / `indeterminate` stav po obnovení

---

## 16. Kolapsovatelné sekce

```html
<details class="mt-4 pt-4 border-t border-gray-200">
    <summary class="flex items-center gap-2 cursor-pointer select-none text-sm font-semibold text-gray-700">
        Název sekce
    </summary>
    <div class="mt-3">
        <!-- obsah sekce -->
    </div>
</details>
```

- Otevření z redirectu: query parametr + podmíněný `open` atribut: `{% if sekce == 'zalohy' %}open{% endif %}`
- Varianta s pozadím: `<details class="bg-white rounded-lg shadow mb-3">` (např. konfigurace na send stránce)

---

## 17. Potvrzení destruktivních akcí

### Custom confirm modal — `svjConfirm()` (primární vzor)

Projekt **nepoužívá** nativní `window.confirm()`. Všechna potvrzení jdou přes custom modal `#confirm-modal` v `base.html` s focus trap a focus restore.

**`data-confirm` atribut** — funguje na `<form>`, `<button>`, `<a>`:
```html
<form action="/endpoint" method="post"
      data-confirm="Opravdu smazat?\n\nTato akce je nevratná."
      hx-boost="false">
    <button type="submit">Smazat</button>
</form>
```
- Globální handler v `app.js` zachytí `submit`/`click` event → zavolá `svjConfirm(msg, callback)`
- `svjConfirm()` zobrazí `#confirm-modal` s textem, tlačítky Potvrdit/Zrušit a focus trap
- Podporuje víceřádkové zprávy přes `\n` (převedeno na `<br>`)
- `hx-boost="false"` je **povinné** na formulářích s potvrzením

**`hx-confirm` integrace** — `htmx:confirm` event handler automaticky přesměruje HTMX confirm na `svjConfirm()`:
```javascript
document.addEventListener('htmx:confirm', function(e) {
    e.preventDefault();
    svjConfirm(e.detail.question, function() { e.detail.issueRequest(); });
});
```
- Takže `<button hx-confirm="Smazat?">` také použije custom modal

### Kritické operace (purge, nevratné akce)
```html
<input type="text" id="confirm-input" placeholder="Napište DELETE pro potvrzení"
       oninput="document.getElementById('danger-btn').disabled = this.value !== 'DELETE'">
<button id="danger-btn" disabled
        class="px-3 py-1.5 bg-red-600 text-white rounded-lg hover:bg-red-700 text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed">
    Smazat data
</button>
```

### Delete confirmation modal (voting, tax)
Pro mazání uzavřených/odeslaných entit se používá custom modal s DELETE input:
- `openDeleteModal(id, name)` / `closeDeleteModal()` / `confirmDeleteModal()` — JS funkce v šabloně
- Modal obsahuje název entity + DELETE input + potvrzovací tlačítko
- Odlišný od `svjConfirm()` — vizuálně výraznější pro kritické akce

---

## 18. Export dat (UI pravidla)

- Formulář exportu musí mít `hx-boost="false"` — binární soubor (Excel/CSV/ZIP) nelze swapnout jako HTML
- Tlačítko exportu — dvě varianty:
  - **Kompaktní na seznamu** (vedle „Nový …"): `px-2.5 py-1.5 bg-gray-100 text-gray-600 rounded-lg hover:bg-gray-200 text-xs font-medium border border-gray-200` s textem `↓ Excel` / `↓ CSV`
  - **Plné na detailu/admin**: `bg-blue-600 text-white` (modré) nebo `bg-green-600 text-white` (zelené)
- Pokud je export filtrovaný: hidden inputy přenáší aktuální filtr do POST endpointu
- Více kategorií s checkboxy: vzor "Vybrat/Zrušit vše" (viz § 15)

---

## 18b. Flash zprávy — toast notifikace

Flash hlášky se zobrazují jako **toast** — fixní pozice vpravo nahoře, nepřesouvají obsah stránky.

### Implementace
- **Kontejner** v `base.html` (před `</body>`): `fixed top-4 right-4 z-50`, `pointer-events-none` (container) + `pointer-events-auto` (toast)
- **Animace**: CSS `animate-slide-in` v `custom.css` (slide-in zprava + fade-in, 0.3s)
- **Auto-dismiss**: `_autoDismiss()` v `app.js` — default 4s, konfigurovatelné přes `data-auto-dismiss="ms"`
  - `data-auto-dismiss` (bez hodnoty) = 4s auto-dismiss (success/info)
  - `data-auto-dismiss="0"` = nezanikne automaticky (chyby)
  - Po HTMX swapech (`htmx:afterSwap`) se auto-dismiss znovu aktivuje
- **Zavření**: tlačítko `×` na každém toastu s fade-out animací

### Barevné varianty
| Typ | CSS | Použití |
|-----|-----|---------|
| Success (default) | `bg-gray-800 text-white` | Uloženo, smazáno, vygenerováno |
| Error | `bg-red-600 text-white` | Chyby — nezanikne automaticky |
| Warning | `bg-yellow-500 text-white` | Varování |

### Jak přidat flash z routeru
Flash zpráva se předává přes **kontext** (ne query parametr):
```python
# V routeru — GET handler
flash_message = ""
flash_param = request.query_params.get("flash", "")
if flash_param == "ok":
    flash_message = "Zůstatek uložen."

ctx = { ..., "flash_message": flash_message }
```
- POST handler redirectuje s `?flash=ok`, GET handler přeloží na `flash_message` v kontextu
- **Nikdy nepsat inline flash bloky v šablonách** — vše řeší globální toast v `base.html`

---

## 18c. PDF náhled (modal)

- pdf.js z CDN načteno v šabloně, která ho potřebuje (aktuálně `tax/matching.html`), NE v `base.html`
- Worker URL se nastavuje vedle script tagu: `<script>pdfjsLib.GlobalWorkerOptions.workerSrc='https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';</script>`
- Verze pdf.js je na jednom místě (v šabloně) — při upgrade změnit obě URL (script + worker)
- Modal pro náhled PDF: `openPdfModal(url)` / `closePdfModal()` v `app.js`
- Vždy `hx-boost="false"` na odkazech na PDF soubory
- PDF canvas má `background:#fff` inline — zůstává bílý i v dark mode

---

## 18d. Client-side řazení tabulek (`sortTableCol`)

Třetí sorting pattern (vedle server-side `sort_th` macro a `_cols` loop) — čistě client-side JavaScript pro malé tabulky bez HTMX:

```html
<th onclick="sortTableCol(this)" data-col="0" data-type="text" data-sort-tbody="tbody-id">
    Sloupec <span class="sort-arrow"></span>
</th>
```

- `data-col` — index sloupce
- `data-type` — `"text"` nebo `"num"`
- `data-sort-tbody` — ID `<tbody>` elementu k řazení
- Definováno v `app.js`, používá se na stránkách bez server-side řazení (zálohy, import historie)

---

## 19. Dark mode

### Princip — CSS override (minimální změny v šablonách)

Dark mode funguje přes CSS specificitu: `.dark .bg-white` (0,2,0) > `.bg-white` (0,1,0) — bez `!important`. Třída `.dark` se přidává na `<html>` element. Všechny Tailwind utility třídy se přepisují v jednom CSS souboru.

**Soubory:**
- `app/static/css/dark-mode.css` — CSS pravidla (~300 řádků), jediný zdroj pravdy pro dark mode barvy
- `app/static/js/app.js` — `toggleTheme()`, `updateThemeUI()`, `initThemeUI()` funkce
- `app/templates/base.html` — anti-flash skript v `<head>`, přepínač v sidebar footer

### Přepínač

Tlačítko v patičce sidebaru (pod navigací, nad `</nav>`):
- **Light mode:** ikona měsíce + text „Tmavý režim"
- **Dark mode:** ikona slunce + text „Světlý režim"
- Stav uložen v `localStorage('svj-theme')`: `'dark'` / `'light'` / `null` (auto = OS preference)

### Anti-flash skript

Inline `<script>` v `<head>` PŘED Tailwind CDN — čte localStorage a přidá `.dark` třídu na `<html>` synchronně, než se vykreslí první frame. Zabraňuje bliknutí bílé stránky při načtení v dark mode.

### HTMX kompatibilita

- `hx-boost` swapuje `<body>`, `<html>` (s `.dark`) přežívá → dark mode zůstává
- HTMX partial swapy (`hx-target`) dědí `.dark` z `<html>` → nový obsah automaticky tmavý
- `initThemeUI()` v `htmx:afterSettle` handleru synchronizuje ikonu tlačítka po navigaci

### Barevná mapa (hlavní přechody)

| Light třída | Dark hodnota | Použití |
|-------------|-------------|---------|
| `bg-gray-50` | `#030712` (gray-950) | Pozadí stránky |
| `bg-white` | `#111827` (gray-900) | Karty, tabulky, modály |
| `bg-gray-100` | `#1f2937` (gray-800) | Hlavičky tabulek |
| `bg-gray-200` | `#374151` (gray-700) | Cancel tlačítka |
| `text-gray-800` | `#e5e7eb` (gray-200) | Nadpisy |
| `text-gray-700` | `#d1d5db` (gray-300) | Labely |
| `border-gray-200` | `#374151` (gray-700) | Standardní okraje |
| `bg-{color}-100` | `rgba({color}, 0.15)` | Badge pozadí |
| `text-{color}-800` | `{color}-300` | Badge text |

### Co se NEMĚNÍ (v dark mode funguje beze změn)

- **Sidebar** (`bg-gray-800`) — už je tmavý
- **Akční tlačítka** (`bg-green-600 text-white`, `bg-red-600 text-white`) — kontrastní
- **Progress bary** (`bg-blue-600`, `bg-green-500`) — výrazné barvy
- **Focus ring** (`focus:ring-blue-500`) — funguje v obou režimech (dark-mode.css jemně upravuje průhlednost)
- **Výjimka — delete modaly** (`voting/index.html`, `tax/index.html`) používají inline Tailwind `dark:` třídy (`dark:bg-gray-800`, `dark:text-gray-200` atd.) — jediná zdokumentovaná výjimka z CSS-only přístupu
- **Ring na bublinách** (`ring-{color}-400`) — funguje v obou
- **PDF canvas** (`background:#fff` inline) — obsah PDF zůstává bílý

### Přidání nové barvy/komponenty

1. Přidat Tailwind třídy do šablony normálně (light mode)
2. Přidat odpovídající `.dark .třída { ... }` pravidlo do `dark-mode.css`
3. Pro `file:` prefix (file input button) přidat `::file-selector-button` pravidlo
4. Pro `hover:` / `group-hover:` prefix escapovat tečky: `.dark .hover\:bg-gray-50:hover`

### File input (tlačítko „Vybrat soubor")

Tailwind `file:` prefix generuje `::file-selector-button` pseudo-element — `.dark .bg-*` CSS override ho nepokryje a Tailwind CDN nepodporuje `dark:file:` variantu. Proto file inputy používají vlastní CSS třídu `file-input` (+ `file-input-gray` pro šedou variantu) a cílený override v `dark-mode.css`:

```html
<!-- Modrý (standardní) — přidat class="file-input" -->
<input type="file" class="file-input block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4
       file:rounded-lg file:border-0 file:text-sm file:font-medium
       file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100">

<!-- Šedý (backups) — přidat class="file-input file-input-gray" -->
<input type="file" class="file-input file-input-gray w-full text-sm text-gray-600 file:mr-3 file:py-2 file:px-4
       file:rounded-lg file:border-0 file:text-sm file:font-medium
       file:bg-gray-100 file:text-gray-700 hover:file:bg-gray-200">
```

**Safari caveat:** `::file-selector-button` a `::-webkit-file-upload-button` MUSÍ být v oddělených CSS blocích. Safari invaliduje celý blok pokud comma-separated selektor obsahuje neznámý pseudo-element. V `dark-mode.css` je proto každý pseudo-element v samostatném pravidle.
