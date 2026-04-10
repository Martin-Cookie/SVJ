# UX Audit Report — SVJ

> Analyzováno: 2026-04-11
> Rozsah: technický audit šablon (konzistence, back URL, tabulky, dark mode, destruktivní akce)
> Metoda: statická analýza 155 šablon v `app/templates/`

---

## Souhrn

| Kategorie | Kritické | Důležité | Drobné |
|-----------|----------|----------|--------|
| Back URL propagace | 0 | 4 | 2 |
| Tabulky (checklist) | 0 | 2 | 0 |
| Dark mode | 0 | 0 | 0 |
| Destruktivní akce / data-confirm | 0 | 0 | 0 |
| Export (hx-boost=false) | 0 | 0 | 0 |
| Scroll kontejnery | 0 | 0 | 0 |
| **Celkem** | **0** | **6** | **2** |

Celkově je projekt ve velmi dobré kondici. Exporty (36 odkazů) mají konzistentně `hx-boost="false"`, destruktivní akce mají všude `data-confirm` nebo `hx-confirm`, `bg-white` bez dark variant se nevyskytuje (řeší se globálně přes `.dark .bg-white` v `dark-mode.css` + 109 explicitních `dark:` override), hlavní listovací stránky (vlastníci, jednotky, prostory, nájemci) mají sort/search/export/sticky. Nálezy jsou lokalizované na několik partials a jednu admin stránku.

---

## Nálezy

### #1 — Odkaz na vlastníka bez `?back=` v detailech nájemce

- **Severity:** DŮLEŽITÉ
- **Pohled:** Běžný uživatel (ztratí šipku zpět)
- **Co a kde:** 4 partials v `app/templates/tenants/partials/`:
  - `_tenant_contact_info.html:4`
  - `_tenant_address_info.html:4`
  - `_tenant_identity_info.html:4`
  - `_tenant_info.html:5`

  Všechny mají `<a href="/vlastnici/{{ tenant.owner_id }}">` bez `?back=`.
- **Dopad:** Uživatel se z detailu nájemce dostane na vlastníka, ale po kliknutí na „Zpět" skočí na seznam vlastníků místo zpět na nájemce. Rozbité mentální modely navigace.
- **Řešení:** Přidat `?back={{ (list_url or ('/najemci/' ~ tenant.id))|urlencode }}` do href. Zajistit, že router předává `list_url` do kontextu těchto partials (detail nájemce). Ověřit, že `owners/detail.html` router má `back_label` větev pro `/najemci/`.
- **Kde v kódu:** `app/templates/tenants/partials/_tenant_contact_info.html:4`, `_tenant_address_info.html:4`, `_tenant_identity_info.html:4`, `_tenant_info.html:5`
- **Náročnost:** nízká ~10 min
- **Závislosti:** —
- **Regrese riziko:** nízké
- **Rozhodnutí:** 🔧 jen opravit
- **Jak otestovat:** `/najemci/{id}` → kliknout na „Upravit u vlastníka" → na detailu vlastníka kliknout šipku zpět → musí skočit na detail nájemce, ne na `/vlastnici`

---

### #2 — Odkazy na vlastníky v `administration/duplicates.html` bez `?back=`

- **Severity:** DŮLEŽITÉ
- **Pohled:** Běžný uživatel
- **Co a kde:** `app/templates/administration/duplicates.html:83` — `<a href="/vlastnici/{{ o.id }}">`. Po přechodu na vlastníka chybí šipka zpět na stránku duplicit.
- **Dopad:** Uživatel prohlížející duplicity ztratí kontext po kliknutí na vlastníka. Musí ručně přes sidebar zpět do Administrace → Duplicity.
- **Řešení:** `?back=/sprava/duplicity`. Přidat větev v `owners/detail.html` routeru pro `back_label = "Zpět na duplicity"`.
- **Kde v kódu:** `app/templates/administration/duplicates.html:83`
- **Náročnost:** nízká ~5 min
- **Závislosti:** —
- **Regrese riziko:** nízké
- **Rozhodnutí:** 🔧 jen opravit
- **Jak otestovat:** `/sprava/duplicity` → kliknout na jméno vlastníka → šipka zpět musí vést na duplicity

---

### #3 — Odkaz na duplicit v `owner_create_form.html` bez `?back=` (target="_blank" — akceptovatelné)

- **Severity:** DROBNÉ
- **Pohled:** UI/UX designer
- **Co a kde:** `app/templates/partials/owner_create_form.html:48` — `<a href="/vlastnici/{{ dup.id }}" target="_blank">`.
- **Dopad:** Protože je `target="_blank"` (otevírá nový tab), chybějící `back` není kritické — uživatel tab zavře. Konzistentně by ale měl mít back.
- **Řešení:** Ponechat `target="_blank"` a nechat být, nebo přidat `?back=/vlastnici/novy` pro konzistenci.
- **Kde v kódu:** `app/templates/partials/owner_create_form.html:48`
- **Náročnost:** nízká ~2 min
- **Rozhodnutí:** ❓ rozhodnutí uživatele (prkotinové)

---

### #4 — Odkaz na duplicitního nájemce v `_create_form.html` bez `?back=`

- **Severity:** DROBNÉ (má `target="_blank"`)
- **Pohled:** UI/UX designer
- **Co a kde:** `app/templates/tenants/partials/_create_form.html:14` — `<a href="/najemci/{{ dup.id }}" target="_blank">`.
- **Dopad:** Stejně jako #3 — nový tab, low impact.
- **Řešení:** Volitelně přidat `?back=/najemci/novy`.
- **Kde v kódu:** `app/templates/tenants/partials/_create_form.html:14`
- **Náročnost:** nízká ~2 min
- **Rozhodnutí:** ❓

---

### #5 — `administration/duplicates.html` nemá sort/search/export

- **Severity:** DŮLEŽITÉ (porušuje checklist tabulek)
- **Pohled:** Business analytik + Data quality
- **Co a kde:** `app/templates/administration/duplicates.html` — zobrazuje seznam duplicitních skupin, ale nemá: (a) řaditelné sloupce, (b) HTMX hledání, (c) export, (d) počet záznamů v hlavičce. Layout je „skupiny v kartách" — což je akceptovatelné pro ~5–15 položek, ale při 50+ duplicitách je neovladatelné.
- **Dopad:** Při velkém počtu duplicit (import z JSON, staré SVJ) je stránka nepřehledná. Chybí hledání podle jména a export pro offline revizi.
- **Řešení:** Podle CLAUDE.md § Tabulky — pokud očekáváme <15 skupin, ponechat kartový layout (hraniční případ). Pokud víc, převést na tabulku s checkboxem pro hromadné sloučení, search podle jména, export. Nejdřív zjistit očekávaný objem dat u reálných SVJ.
- **Kde v kódu:** `app/templates/administration/duplicates.html`
- **Náročnost:** střední ~45 min (nebo nízká ~10 min jen search + export)
- **Závislosti:** —
- **Regrese riziko:** nízké
- **Rozhodnutí:** ❓ potřeba rozhodnutí uživatele (kartový vs tabulkový layout podle objemu)

---

### #6 — `administration/backups.html` nemá sort/search

- **Severity:** DŮLEŽITÉ (hraniční — admin seznam)
- **Pohled:** Business analytik
- **Co a kde:** `app/templates/administration/backups.html` zobrazuje seznam záloh (ZIP souborů) bez `sticky top-0`, bez řazení, bez search.
- **Dopad:** Při 50+ zálohách (po měsících běhu) je vyhledání staré zálohy obtížné.
- **Řešení:** Podle CLAUDE.md § Tabulky spadá do „malé admin seznamy" → kompaktní layout OK, ale stálo by za to přidat alespoň řazení podle data/velikosti (client-side přes `sortTableCol` z `app.js`) a search podle názvu souboru.
- **Kde v kódu:** `app/templates/administration/backups.html`
- **Náročnost:** nízká ~15 min
- **Závislosti:** —
- **Regrese riziko:** nízké
- **Rozhodnutí:** ❓ rozhodnutí uživatele

---

### #7 — Nekonzistence: `voting/_voting_header.html:47,50` (Import, Zpracování) bez `?back=`

- **Severity:** DŮLEŽITÉ
- **Pohled:** Běžný uživatel
- **Co a kde:** `app/templates/voting/_voting_header.html:47` (`/hlasovani/{id}/import`) a `:50` (`/hlasovani/{id}/zpracovani`). Tyto akční tlačítka v hlavičce hlasování neposílají `?back=`.
- **Dopad:** Po importu/zpracování uživatel ztratí kontext aktuálního hlasování (např. při příchodu z dashboardu). Pokud jde o wizard, back je sekundární, ale konzistentnější by bylo ho předávat.
- **Řešení:** Doplnit `?back={{ (list_url or '/hlasovani')|urlencode }}` — nebo ověřit, že wizard import/zpracování má vlastní explicitní „Hotovo/Zpět" v UI.
- **Kde v kódu:** `app/templates/voting/_voting_header.html:47,50`
- **Náročnost:** nízká ~5 min
- **Rozhodnutí:** ❓ (závisí na wizard flow)

---

### #8 — `voting/import_result.html` linky bez back

- **Severity:** DROBNÉ
- **Pohled:** Běžný uživatel
- **Co a kde:** `app/templates/voting/import_result.html:48-49` — `/hlasovani/{id}` a `/hlasovani/{id}/zpracovani` bez `?back=`. Wizard končí, ale konzistence by seděla.
- **Dopad:** Drobné — wizard skončil, uživatel pokračuje explicitní akcí.
- **Řešení:** Přidat `?back=/hlasovani` nebo ponechat.
- **Kde v kódu:** `app/templates/voting/import_result.html:48-49`
- **Rozhodnutí:** ❓

---

## Top 5 doporučení (podle dopadu)

| # | Návrh | Dopad | Složitost | Čas | Závisí na | Rozhodnutí | Priorita |
|---|-------|-------|-----------|-----|-----------|------------|----------|
| 1 | Doplnit `?back=` do 4 tenant partials (odkazy na vlastníka z detailu nájemce) | Vysoký | Nízká | ~10 min | — | 🔧 | HNED |
| 2 | Doplnit `?back=/sprava/duplicity` do `duplicates.html:83` + back_label větev | Vysoký | Nízká | ~5 min | — | 🔧 | HNED |
| 3 | Rozhodnout layout `administration/duplicates.html` (kartový vs tabulkový) + případně doplnit search/export | Střední | Střední | ~45 min | — | ❓ | BRZY |
| 4 | Client-side sort + search v `administration/backups.html` | Střední | Nízká | ~15 min | — | ❓ | BRZY |
| 5 | Sjednotit back propagaci v `voting/_voting_header.html` (import/zpracování) | Nízký | Nízká | ~5 min | — | 🔧 | POZDĚJI |

---

## Quick wins (nízká složitost, okamžitý efekt)

- [ ] **#1**: přidat `?back=` do 4 tenant partials (~10 min, 🔧)
- [ ] **#2**: přidat `?back=/sprava/duplicity` do `duplicates.html:83` (~5 min, 🔧)
- [ ] **#7**: sjednotit back propagaci v hlavičce hlasování (~5 min, 🔧)

---

## Co funguje výborně

- **Exporty**: 36 odkazů na `/exportovat/*`, **všechny** mají `hx-boost="false"` ✓
- **Destruktivní akce**: všechny DELETE formuláře mají `data-confirm` / `hx-confirm` / custom modal ✓
- **Dark mode**: žádný `bg-white` bez dark variant — řeší globální override v `dark-mode.css` + explicitní `dark:bg-gray-800` (109 výskytů) ✓
- **Hlavní listy** (vlastníci, jednotky, prostory, nájemci, hlasování, platby): mají sort, search, export, sticky header, `overflow-y-auto` + `min-h-0` ✓
- **Sticky headers**: 29 výskytů `sticky top-0` ve 28 souborech — všechny datové tabulky pokryté
- **Back URL propagace**: u hlavních entitních odkazů (`owner_row.html`, `unit_owners.html`, `share_check_row.html`, `settings_email_tbody.html`) je zavedené chaining `?back={{ list_url|urlencode }}` včetně hash fragmentů ✓
