# PRD_UI — UI konvence (redestilát)

> **Klonovací spec, část 4/5 — Klíčové UI vzory.** Pro detaily (CSS třídy, animace, konkrétní HTMX handlery) konzultuj `appendices/UI_GUIDE.md`.  
> Navigace: [README](README.md) · [PRD](PRD.md) · [PRD_DATA_MODEL](PRD_DATA_MODEL.md) · [PRD_MODULES](PRD_MODULES.md) · **PRD_UI.md** · [PRD_ACCEPTANCE](PRD_ACCEPTANCE.md)

---

## 1. Tech stack UI

- **Tailwind CSS** z CDN (`cdn.tailwindcss.com`). Žádný build pipeline.
- **HTMX 2.0+** z CDN (`unpkg.com/htmx.org`). Boosted navigation, partial swaps.
- **Vanilla JS** (jediný soubor `app.js`). Žádný jQuery, žádné externí knihovny.
- **Jinja2** server-side rendering. Partials pro opakované struktury.
- **Dark mode** přes CSS override (`.dark .bg-white { ... }` v `dark-mode.css`). Toggle v sidebaru, uloženo v `localStorage`.
- **Ikony** — inline SVG. Žádné ikonové knihovny.
- **Fonts** — default Tailwind `font-sans` (system stack).

---

## 2. `base.html` — kostra

Sdílený layout pro všechny stránky. Bloky: `{% block title %}`, `{% block content %}`, `{% block extra_head %}`.

### Struktura

```
┌────────────────┬──────────────────────────────────────┐
│                │  (mobile hamburger) ☰                │
│                │                                        │
│   SIDEBAR      │           MAIN CONTENT                 │
│   (fixní)      │           {% block content %}          │
│                │                                        │
│   - Přehled    │                                        │
│   - Import     │                                        │
│   - Evidence   │                                        │
│   - Moduly     │                                        │
│   - Systém     │                                        │
│                │                                        │
│   🌙 Dark      │                                        │
└────────────────┴──────────────────────────────────────┘

[Flash toast top-right]
[Modals: PDF preview, svjConfirm]
```

### Sidebar

- **Šířka**: `md:w-44` (11rem). Mobile: skrytý, ukazuje se po kliknutí na hamburger.
- **Background**: šedo-bílá tmavá (`bg-gray-800` light, `bg-gray-900` dark).
- **Logo**: "SVJ Správa — Automatizace" (top).
- **Sekce**:
  1. **Přehled** → `/` (dashboard)
  2. **Import z Excelu** → výpis subpagů (vlastníci, kontakty, hlasy, zůstatky, předpisy, výpisy)
  3. **Evidence** → Vlastníci, Jednotky, Nájemci, Prostory
  4. **Moduly** → Hlasování, Rozesílání, Bounces, Kontroly, Platby, Vodoměry
  5. **Systém** → Administrace, Nastavení
- **Aktivní položka**: odlišena `bg-blue-600`.
- **Badge s dlužníky** (na položce Platby): `request.state.nav_debtor_count` počítán v middleware `inject_debtor_count()`.
- **Dark mode toggle** (bottom): přepíná `class="dark"` na `<html>`, ukládá `svj-theme` do localStorage.

### Main content

- `md:ml-44` (offset pro sidebar). `pt-14 md:pt-6` (padding-top pro mobile header).
- **Flash zprávy** — toasty v top-right, auto-dismiss za 4s (errors nezmizí).
- **HTMX boost**: všechny `<a>` se boostují, `scrollIntoViewOnBoost: false`.

### Modals

- **PDF preview** — inline modal s pdf.js, per-page render, scroll v modalu.
- **Custom confirm** — `svjConfirm()` místo `window.confirm()`. Focus trap (Tab cyklicky), Escape close, focus restore po zavření.

### CSS soubory

```html
<link rel="stylesheet" href="/static/css/custom.css?v=2">
<link rel="stylesheet" href="/static/css/dark-mode.css?v=2">
```

- **`custom.css`**: scroll margin pro hash anchors, HTMX animace (`.htmx-indicator`, `.htmx-request` opacity fade), toast slide-in, button disabled během requestu.
- **`dark-mode.css`**: override Tailwind classů pod `.dark` selector.

---

## 3. Layout stránek

### Detail stránka

```html
{% extends "base.html" %}
{% block content %}
  {% if back_url %}
    <div class="mb-3">
      <a href="{{ back_url }}" class="text-sm text-blue-600 hover:text-blue-800 dark:text-blue-400">
        &larr; {{ back_label }}
      </a>
    </div>
  {% endif %}

  <div class="flex items-center gap-3 mb-4">
    <h1 class="text-2xl font-bold text-gray-800">{{ entity.display_name }}</h1>
    <span class="px-2 py-0.5 text-xs font-medium rounded-full bg-blue-100 text-blue-700">
      {{ entity.type_label }}
    </span>
  </div>

  {# 4-sloupcová info karta #}
  <div class="bg-white rounded-lg shadow mb-3">
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 divide-y md:divide-y-0 md:divide-x">
      <div class="p-3">{% include "partials/owner_identity_info.html" %}</div>
      <div class="p-3">{% include "partials/owner_contact_info.html" %}</div>
      <div class="p-3">{% include "partials/owner_address_info.html" %}</div>
      <div class="p-3">{% include "partials/owner_address_info.html" %}</div>
    </div>
  </div>

  {# Scrollovatelný obsah #}
  ...
{% endblock %}
```

### Seznam s fixním headerem

```html
<div class="flex flex-col" style="height:calc(100vh - 3rem)">
  <div class="shrink-0">
    {# Header: titulek, search, bubliny, export, počet #}
    <h1>...</h1>
    <input type="search" hx-trigger="keyup changed delay:300ms" hx-target="#tbody" ...>
    <div class="flex gap-2">{# bubliny #}</div>
    <a href="/modul/exportovat/xlsx?...">↓ Excel</a>
    <a href="/modul/exportovat/csv?...">↓ CSV</a>
  </div>
  <div class="flex-1 overflow-y-auto overflow-x-hidden min-h-0">
    <table class="min-w-full">
      <thead class="bg-gray-50 sticky top-0 z-10">...</thead>
      <tbody id="tbody">{% include "modul/_tbody.html" %}</tbody>
    </table>
  </div>
</div>
```

**Klíčová pravidla**:
- `min-h-0` je nutné — jinak flex child přeteče a scroll nefunguje.
- `overflow-y-auto` (NE `overflow-auto`) — pro správnou obnovu scroll pozice při HTMX boost.
- Bubliny/search se **nescrollují**.

### Šířky

| Typ | Max-width |
|---|---|
| Tabulka/seznam | full width (žádný limit) |
| Hub/index (stat karty) | `max-w-6xl mx-auto` |
| Detail entity | `max-w-3xl` nebo `max-w-4xl mx-auto` |
| Formulář/import | `max-w-2xl mx-auto` |

---

## 4. Tabulky — povinný checklist

**Pro KAŽDOU datovou tabulku (desítky+ řádků)**:

1. ✅ **Sticky hlavička**: `<thead class="bg-gray-50 sticky top-0 z-10">`.
2. ✅ **Řaditelné sloupce**: KAŽDÝ sloupec, s šipkou nahoru/dolů. `sort`, `order` query params.
3. ✅ **Hledání**: HTMX input `hx-trigger="keyup changed delay:300ms"`, target `<tbody>`.
4. ✅ **Diacritics-insensitive**: přes `name_normalized` sloupec + `strip_diacritics()` z `app.utils`.
5. ✅ **Klikací entity**: každá reference na entitu (vlastník, jednotka) je `<a>`, ne plain text.
6. ✅ **Eager loading**: pokud zobrazujeme vlastníka přes `OwnerUnit`, router MUSÍ mít `joinedload(Ballot.owner).joinedload(Owner.units).joinedload(OwnerUnit.unit)`.
7. ✅ **HTMX partial**: search a sort aktualizují jen `<tbody>`, ne celou stránku.
8. ✅ **Export + počet**: v hlavičce `{{ items|length }} záznamů`, `↓ Excel`, `↓ CSV` tlačítka.

### Pro malé seznamy (~5–15 položek)

Použít **kompaktní layout karty s inline edit** (ne plnou tabulku):
- Viz číselníky, emailové šablony, členové výboru.
- Každá položka = karta s nadpisem + inline Upravit tlačítkem.

### Řádkové akce — ikony (SVG inline)

| Akce | CSS třída |
|---|---|
| Stáhnout | `text-blue-600 hover:bg-blue-50` |
| Smazat | `text-gray-400 hover:text-red-600 hover:bg-red-50` |
| Upravit | `text-gray-400 hover:text-blue-600 hover:bg-blue-50` |

Velikost: `w-4 h-4`, padding `p-1`, `rounded`. Vždy `title` atribut.

---

## 5. Formuláře

### Input tiery

| Tier | CSS | Použití |
|---|---|---|
| **Full** | `px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500` | Tvorba entit, SMTP form |
| **Inline** | `px-2 py-1.5 border border-gray-300 rounded text-xs focus:ring-2 focus:ring-blue-500` | Inline edit (detail) |
| **Search** | `px-3 py-1.5 border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 text-xs` | Search bary |

### Tlačítka

| Typ | CSS | Použití |
|---|---|---|
| **Akce (blue)** | `px-3 py-1.5 text-sm font-medium text-blue-600 border border-blue-300 rounded-lg hover:bg-blue-50` | Upravit, Přidat, Uložit |
| **Akce inline** | `px-2 py-1 text-xs font-medium text-blue-600 border border-blue-300 rounded hover:bg-blue-50` | Inline akce v tabulkách |
| **Akce s ikonou** | + `inline-flex items-center gap-1` | S SVG |
| **Zrušit** | `px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-100 rounded` | Sekundární |
| **Destruktivní** | `text-red-600 border-red-300 hover:bg-red-50` | Smazat |

### Vzor inline editace

```html
{# Display partial #}
<div id="identity-section">
  <h3 class="text-sm font-semibold text-gray-700 mb-2">Identita</h3>
  <div class="space-y-1 text-xs">
    <div class="flex justify-between">
      <span class="text-gray-500">Jméno:</span>
      <span class="text-gray-900">{{ owner.display_name }}</span>
    </div>
    ...
  </div>
  <button
    hx-get="/vlastnici/{{ owner.id }}/identita-formular"
    hx-target="#identity-section"
    hx-swap="outerHTML"
    class="mt-2 inline-flex items-center gap-1 px-2 py-1 text-xs text-blue-600 border border-blue-300 rounded hover:bg-blue-50">
    <svg class="w-3 h-3" ...>{# tužka #}</svg>
    Upravit
  </button>
</div>
```

Po kliknutí HTMX nahradí `#identity-section` form partialem. Form má `hx-post` na save endpoint, po úspěchu redirect (přes PRG nebo HTMX `HX-Redirect` header).

---

## 6. Bubliny (filtry)

Nad tabulkami. Aktivní = `ring-2 ring-blue-500`. Ne-aktivní = `bg-gray-100 text-gray-600 border-gray-200`.

```html
<div class="flex flex-wrap gap-2 mb-4">
  <a href="/vlastnici"
     class="flex-1 min-w-0 px-3 py-2 rounded-lg text-sm text-center {{ active_class('all') }}">
    Všichni ({{ counts.all }})
  </a>
  <a href="/vlastnici?typ=fyzicke"
     class="flex-1 min-w-0 px-3 py-2 rounded-lg text-sm text-center {{ active_class('fyzicke') }}">
    Fyzické ({{ counts.physical }})
  </a>
  ...
</div>
```

**Pravidla**:
- `flex-1` aby se dynamicky roztáhly do celé šířky.
- `min-w-0` aby text truncate fungoval.
- Propis filtrů do HTMX search přes `hx-include` nebo hidden inputy.

---

## 7. Badge

Vedle titulků, v řádcích tabulek pro status.

```html
<span class="px-2 py-0.5 text-xs font-medium rounded-full bg-{color}-100 text-{color}-700">
  {{ label }}
</span>
```

Barvy:
- **Blue** — aktivní, neutrální info (typ osoby, plán)
- **Green** — success, dokončeno, zaplaceno
- **Red** — chyba, dlužník, invalid email
- **Yellow** — warning, čeká, paused
- **Gray** — neutral, inactive

---

## 8. Flash zprávy

Toast v top-right, auto-dismiss za 4s (errors = 0 = nezmizí). Implementace v `app.js`.

```python
# V routeru:
from app.utils import flash_from_params
# Redirect s query parametry:
return RedirectResponse(f"/vlastnici?flash=owner_created&id={owner.id}", status_code=303)

# V GET handleru:
flash = flash_from_params(request, {
    "owner_created": ("Vlastník {id} vytvořen.", "success"),
    "owner_updated": ("Změny uloženy.", "success"),
    "validation_error": ("Chyba: {detail}", "error"),
})
# {{ flash }} v kontextu
```

Viz `docs/ROUTER_PATTERNS.md` pro přesný PRG pattern.

---

## 9. HTMX vzory

### Search → update tbody

```html
<input type="search"
       name="q"
       hx-get="/vlastnici"
       hx-trigger="keyup changed delay:300ms"
       hx-target="#tbody"
       hx-include="[name='typ'], [name='sekce']"
       hx-push-url="true">

<table>
  <tbody id="tbody">
    {% include "owners/_tbody.html" %}
  </tbody>
</table>
```

Router detekuje HTMX přes `is_htmx_partial(request)` → vrátí jen partial template:

```python
if is_htmx_partial(request):
    return templates.TemplateResponse("owners/_tbody.html", ctx)
return templates.TemplateResponse("owners/list.html", ctx)
```

### Sort kliknutím na hlavičku

```html
<th>
  <a href="?sort=name&order={{ 'desc' if current_sort == 'name' and current_order == 'asc' else 'asc' }}"
     hx-get="?sort=name&order=..."
     hx-target="#tbody"
     hx-push-url="true">
    Jméno
    {% if current_sort == 'name' %}
      {% if current_order == 'asc' %}↑{% else %}↓{% endif %}
    {% endif %}
  </a>
</th>
```

### Inline form

```html
{# Partial: form #}
<div id="identity-section">
  <form hx-post="/vlastnici/{{ id }}/identita-upravit"
        hx-target="#identity-section"
        hx-swap="outerHTML">
    <input name="first_name" value="{{ owner.first_name }}">
    <button type="submit">Uložit</button>
    <button type="button"
            hx-get="/vlastnici/{{ id }}/identita-info"
            hx-target="#identity-section"
            hx-swap="outerHTML">Zrušit</button>
  </form>
</div>
```

### Progress polling

```html
<div id="progress"
     hx-get="/rozesilani/{{ sid }}/rozeslat/prubeh-stav"
     hx-trigger="load, every 2s"
     hx-swap="outerHTML">
  {% include "partials/_send_progress_inner.html" %}
</div>
```

Po dokončení server vrátí response s `HX-Redirect: /rozesilani/{sid}` headerem → HTMX přesměruje.

---

## 10. Ikony (inline SVG)

Preferovat Heroicons-style outline SVG. Žádné icon fonty.

Příklady:
- **Tužka** (upravit): `<path d="M17.414 2.586a2 2 0 00-2.828 0L7 10.172V13h2.828l7.586-7.586a2 2 0 000-2.828z" />`
- **Koš** (smazat): `<path d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />`
- **Šipka dolů** (stáhnout): `<path d="M12 10v6m0 0l-3-3m3 3l3-3M3 17V7a2 2 0 012-2h6l2 2h6a2 2 0 012 2v10a2 2 0 01-2 2H5a2 2 0 01-2-2z" />`
- **Šipka levá** (zpět): používá se `&larr;` entity, ne SVG.

---

## 11. Dark mode

- Toggle v sidebaru bottom.
- Ukládá `svj-theme` v `localStorage` (`"light"` / `"dark"`).
- Na init přidá / odebere `class="dark"` na `<html>`.
- `dark-mode.css` override: `.dark .bg-white { background: #1f2937; }`, atd.

Přepínač kód (v `app.js`):
```js
const savedTheme = localStorage.getItem('svj-theme');
const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
const isDark = savedTheme === 'dark' || (!savedTheme && prefersDark);
if (isDark) document.documentElement.classList.add('dark');

document.getElementById('theme-toggle').addEventListener('click', () => {
  document.documentElement.classList.toggle('dark');
  localStorage.setItem('svj-theme', document.documentElement.classList.contains('dark') ? 'dark' : 'light');
});
```

---

## 12. Wizard stepper

Sdílený partial `partials/wizard_stepper.html`:

```html
{# Vstup: wizard_steps = [{"key": "upload", "label": "Nahrání", "status": "done|active|pending|sending"}, ...] #}
<ol class="flex items-center gap-4 mb-6">
  {% for step in wizard_steps %}
  <li class="flex items-center gap-2">
    <span class="w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium
                 {% if step.status == 'done' %}bg-green-600 text-white
                 {% elif step.status == 'active' %}bg-blue-600 text-white ring-4 ring-blue-100
                 {% elif step.status == 'sending' %}bg-yellow-500 text-white animate-pulse
                 {% else %}bg-gray-200 text-gray-500{% endif %}">
      {% if step.status == 'done' %}✓{% else %}{{ loop.index }}{% endif %}
    </span>
    <span class="text-sm {% if step.status == 'active' %}font-semibold{% endif %}">{{ step.label }}</span>
    {% if not loop.last %}<span class="text-gray-300">→</span>{% endif %}
  </li>
  {% endfor %}
</ol>
```

Helper v `app/utils.py`:
```python
def build_import_wizard(current_step: str) -> dict:
    steps = [
        {"key": "upload", "label": "Nahrání"},
        {"key": "mapping", "label": "Mapování"},
        {"key": "preview", "label": "Náhled"},
        {"key": "confirm", "label": "Potvrzení"},
    ]
    for s in steps:
        idx_current = next(i for i, x in enumerate(steps) if x["key"] == current_step)
        idx_this = steps.index(s)
        if idx_this < idx_current:
            s["status"] = "done"
        elif idx_this == idx_current:
            s["status"] = "active"
        else:
            s["status"] = "pending"
    return {"wizard_steps": steps, "wizard_current": current_step, "wizard_total": len(steps)}
```

Router volá `**build_import_wizard("mapping")` při renderu.

---

## 13. Partials (sdílené)

Klíčové partialy v `app/templates/partials/`:

| Partial | Účel |
|---|---|
| `wizard_stepper.html` | 4-step wizard (upload → mapping → preview → confirm) |
| `wizard_stepper_compact.html` | Kompaktní verze pro voting/tax |
| `import_mapping_fields.html` | Tabulka pro mapování sloupců z Excel |
| `import_mapping_js.html` | JS logika pro drag-drop mapování |
| `_send_progress.html` | Progress bar (wrap) |
| `_send_progress_inner.html` | Progress bar content (target pro HTMX) |
| `owner_identity_info.html` | Info karta identity (display) |
| `owner_identity_form.html` | Form pro inline edit identity |
| `owner_contact_info.html` | Info karta kontaktů |
| `owner_address_info.html` | Info karta adresy (parametrické `prefix`) |
| `smtp_profile_form.html` | SMTP profil form |
| `smtp_profile_card.html` | SMTP profil display |
| `flash.html` | Flash toast |

---

## 14. Back URL navigace

Detail entity má zpětný odkaz na výchozí seznam se zachovanými filtry. Viz `appendices/UI_GUIDE.md § Back link` a `docs/NAVIGATION.md` pro úplné podrobnosti.

**Kanonický kód**:
```html
{% if back_url %}
<div class="mb-3">
    <a href="{{ back_url }}"
       class="text-sm text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300">
        &larr; {{ back_label }}
    </a>
</div>
{% endif %}
```

- Vždy `text-sm`, vždy `&larr;` entita, vždy `text-blue-600`. Žádné SVG, žádné `text-xs`.
- Obaleno v `<div class="mb-3">`.
- `back_label` dynamicky dle `back_url` path (v routeru).

---

## 15. Scroll pozice

Při HTMX boost navigaci `<main>` ztratí scroll pozici — vrací se na začátek. Řešení:

```js
// V app.js
document.addEventListener('htmx:pushedIntoHistory', () => {
  const main = document.querySelector('[data-scroll-container]');
  if (main) sessionStorage.setItem('scroll-' + location.pathname, main.scrollTop);
});
document.addEventListener('htmx:afterSettle', () => {
  const main = document.querySelector('[data-scroll-container]');
  const saved = sessionStorage.getItem('scroll-' + location.pathname);
  if (main && saved) main.scrollTop = parseInt(saved);
});
```

Kontejner musí mít `overflow-y-auto` (ne `overflow-auto`) a atribut `data-scroll-container`.

---

## 16. Custom confirm modal

Místo `window.confirm()` použij `svjConfirm()`:

```html
<button onclick="svjConfirm('Opravdu smazat?', () => { htmx.trigger(this, 'confirmed'); })">
  Smazat
</button>
<form hx-post="..." hx-trigger="confirmed">...</form>
```

Nebo přes `data-confirm`:
```html
<button data-confirm="Opravdu smazat?" hx-post="..." hx-trigger="click">Smazat</button>
```

Globální handler v `app.js`:
```js
document.addEventListener('click', (e) => {
  const btn = e.target.closest('[data-confirm]');
  if (btn && !btn.dataset.confirmed) {
    e.preventDefault();
    svjConfirm(btn.dataset.confirm, () => {
      btn.dataset.confirmed = '1';
      btn.click();
    });
  }
});
```

Implementace modalu: focus trap (Tab cyklicky), Escape close, focus restore.

---

## 17. Beforeunload varování (nuložené změny)

```html
<form data-warn-unsaved>
  ...
</form>
```

V `app.js`:
```js
document.addEventListener('input', (e) => {
  const form = e.target.closest('[data-warn-unsaved]');
  if (form) form.dataset.dirty = '1';
});
window.addEventListener('beforeunload', (e) => {
  const dirty = document.querySelector('[data-warn-unsaved][data-dirty="1"]');
  if (dirty) { e.preventDefault(); e.returnValue = ''; }
});
```

---

## 18. Přílohy (kompletní UI konvence)

- `appendices/UI_GUIDE.md` — úplných 1700 řádků s každým detailem (barvy, animace, spacing, konkrétní HTMX snippety).
- `appendices/CLAUDE.md` — backend pravidla, router vzory, URL konvence.

---

## Next step

Pokračuj do [`PRD_ACCEPTANCE.md`](PRD_ACCEPTANCE.md) pro **Playwright test scénáře**.
