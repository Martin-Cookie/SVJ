# Nové moduly / entity + Export dat

> Toto je detailní referenční dokument. Hlavní pravidla jsou v [CLAUDE.md](../CLAUDE.md).

## Nové moduly / entity

- Musí dodržovat VŠECHNY vzory od začátku:
  - Back URL navigace (router `back` param + `list_url` + šipka zpět v šabloně)
  - UI vzory z [UI_GUIDE.md](UI_GUIDE.md) (bubliny, sticky hlavičky, formátování, badge, ikony, inline editace)
  - HTMX partial odpovědi
- **Modul s více stránkami** (např. hlasování: detail, lístky, zpracování, neodevzdané):
  - Sdílený header jako partial (`_modul_header.html`) — stejný nadpis, bubliny, tlačítka na VŠECH stránkách
  - Aktivní bublina zvýrazněna `ring-2 ring-{color}-400`
  - Router: sdílená helper funkce pro výpočet dat bublin (volat ve všech endpointech)
  - Šablona předává `active_bubble` do partialu pro zvýraznění
- **Wizard stepper** — vícekrokový workflow (hlasování, rozesílání):
  - Router helper `_voting_wizard(voting, current_step)` vrací dict s `wizard_steps`, `wizard_current`, `wizard_label`
  - Router helper `_tax_wizard(...)` vrací dict s `wizard_steps`, `wizard_current`, `wizard_total` (bez `wizard_label`)
  - Plná varianta: `partials/wizard_stepper.html` — samostatný stepper nad obsahem
  - Kompaktní varianta: `partials/wizard_stepper_compact.html` — inline v kartě na seznamu
  - Stavy kroků: `done` (zelená), `active` (zelená), `current+done` (tmavší zelená s ring efektem), `pending` (šedá), `sending` (oranžová pulzace)
- **Sdílený progress bar pro dávkové odesílání** — `partials/_send_progress.html` + `partials/_send_progress_inner.html`:
  - Používá se v: nesrovnalosti (platby) i hromadné rozesílání (daně)
  - Vnější partial (`_send_progress.html`): polling div + tlačítka (Pozastavit/Pokračovat/Zrušit) **mimo polled oblast** + JS synchronizace stavu
  - Vnitřní partial (`_send_progress_inner.html`): progress bar, statistiky, stav — swapuje se HTMX pollingem (500ms)
  - **Tlačítka MUSÍ být mimo HTMX-polled oblast** — jinak `data-confirm` modal přestane fungovat (HTMX swap odstraní formulář z DOM během potvrzování)
  - Stav se synchronizuje přes hidden inputy (`#progress-done`, `#progress-paused`, `#progress-waiting`) + `htmx:afterSwap` event
  - Po dokončení (`done=True`) polling čeká 3 sekundy před redirectem (uživatel vidí výsledek)
  - Router helper `_*_eta(progress)` MUSÍ předávat `done` flag do šablony
  - Router `finished_at = time.monotonic()` se ukládá v `finally` bloku i v cancel endpointu
  - Volání: `{% with poll_url=..., pause_url=..., resume_url=..., cancel_url=..., cancel_label=..., cancel_confirm=... %}{% include "partials/_send_progress.html" %}{% endwith %}`
- Registrace v `app/main.py` (`include_router`)
- Export modelů v `app/models/__init__.py`
- Odkaz v sidebar (`base.html`) s `active_nav` kontrolou
- Přidání do README.md (popis modulu + API endpointy)
- Odkaz v sidebaru (`base.html`): top položky (Přehled, Import z Excelu), sekce Evidence (Vlastníci, Jednotky, Nájemci, Prostory), sekce Moduly (Hlasování, Rozesílání, Kontroly, Platby), sekce Systém (Administrace, Nastavení). Ikona `w-4 h-4 mr-2` SVG + text label

## Export dat (Excel + CSV)

- Export musí vždy odrážet **aktuální filtrovaný pohled** — ne všechna data
- Filtr se přenáší přes hidden input ve formuláři: `<input type="hidden" name="filtr" value="{{ filtr }}">`
- Export endpoint aplikuje **stejnou logiku filtrování** jako zobrazovací endpoint
- **URL vzor**: seznamové exporty na `/{modul}/exportovat/{fmt}`, detailové exporty (dokumenty patřící jedné entitě, např. matice plateb pro rok, hlasovací lístky) na `/{modul}/{id}/exportovat/{fmt}`. Vždy `{fmt}` jako poslední segment — přijímá `xlsx`/`csv`
- **Excel**: generování přes `openpyxl` (ne pandas): bold hlavička (`Font(bold=True)`), auto-width sloupců (max 45 znaků), žlutá `PatternFill` pro zvýraznění rozdílů. Response: `media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"`
- **CSV**: UTF-8 s BOM (`\ufeff` na začátku), středník jako oddělovač. Response: `media_type="text/csv; charset=utf-8"`, filename `{modul}_YYYYMMDD.csv`
- **Název souboru musí odrážet aktivní filtr/bublinu**:
  - Formát: `{modul}_{suffix}_{YYYYMMDD}.{fmt}` (s ID entity: `{modul}_{id}_{suffix}_{YYYYMMDD}`)
  - Suffix = český popis aktivního filtru bez diakritiky. Bez filtru = `_vsichni` / `_vsechny` / `_vse`
  - Suffixový dict se definuje přímo v export endpointu: `typ_labels = {"physical": "fyzicke", "legal": "pravnicke"}`
  - Logika: vzít **první neprázdný filtr** (priorita: typ → kontakt → stav → vlastnictví → sekce → hledání), přidat odpovídající suffix
  - Příklady: `vlastnici_fyzicke_20260309.xlsx`, `jednotky_sekce_A_20260309.csv`, `hlasovani_1_nezpracovane_20260309.xlsx`, `porovnani_rozdily_20260309.xlsx`, `vypis_3_nenaparovane_20260309.csv`
  - **Nikdy nepoužívat diakritiku v názvu** — HTTP `Content-Disposition` header kóduje latin-1
  - **Při přidání nového exportu s bublinami/filtry VŽDY přidat suffix logiku** — uživatel musí z názvu souboru poznat, co exportoval
- **Upload limity**: centralizované v `UPLOAD_LIMITS` dict v `app/utils.py`. Volání: `validate_upload(file, **UPLOAD_LIMITS["excel"])`. Při přidání nového uploadu přidat klíč do `UPLOAD_LIMITS`
- Formulář exportu musí mít `hx-boost="false"` (viz [UI_GUIDE.md § 14](UI_GUIDE.md))
