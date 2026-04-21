# PRD_MODULES — Moduly, user stories a acceptance criteria

> **Klonovací spec, část 3/5 — Per-modul user stories + acceptance criteria + URL routy + workflow.**  
> Navigace: [README](README.md) · [PRD](PRD.md) · [PRD_DATA_MODEL](PRD_DATA_MODEL.md) · **PRD_MODULES.md** · [PRD_UI](PRD_UI.md) · [PRD_ACCEPTANCE](PRD_ACCEPTANCE.md)

---

## Obsah

1. [Dashboard `/`](#modul-1--dashboard-)
2. [Vlastníci `/vlastnici`](#modul-2--vlastníci-vlastnici)
3. [Jednotky `/jednotky`](#modul-3--jednotky-jednotky)
4. [Prostory `/prostory`](#modul-4--prostory-prostory)
5. [Nájemci `/najemci`](#modul-5--nájemci-najemci)
6. [Hlasování `/hlasovani`](#modul-6--hlasování-hlasovani)
7. [Rozesílání daní `/rozesilani`](#modul-7--rozesílání-daní-rozesilani)
8. [Bounces `/rozesilani/bounces`](#modul-8--bounces-rozesilanibounces)
9. [Synchronizace `/synchronizace`](#modul-9--synchronizace-synchronizace)
10. [Kontrola podílů `/kontrola-podilu`](#modul-10--kontrola-podílů-kontrola-podilu)
11. [Administrace `/sprava`](#modul-11--administrace-sprava)
12. [Nastavení `/nastaveni`](#modul-12--nastavení-nastaveni)
13. [Platby `/platby`](#modul-13--platby-platby)
14. [Vodoměry `/vodometry`](#modul-14--vodoměry-vodometry)

---

## Struktura každého modulu

Každý modul obsahuje:

- **Účel** — jednou větou.
- **User stories** (US-#) — "Jako [role] chci [akci], abych [přínos]."
- **Acceptance criteria** (AC-#) — měřitelné, pozorovatelné podmínky.
- **URL routy** — kompletní seznam endpointů s HTTP metodou a účelem.
- **Workflow kroky** (pro multi-step procesy).
- **Závislosti** — na jaké jiné moduly/modely modul navazuje.

---

## Modul 1 — Dashboard `/`

**Účel**: Přehledová stránka po přihlášení. Ukazuje aktuální stav SVJ (počty, platby, nedoručené e-maily) a poslední aktivity.

### User stories

- **US-1.1** — Jako předseda chci vidět hlavní metriky (počet vlastníků, jednotek, aktivních hlasování, dlužníků), abych věděl, jestli je potřeba něco udělat.
- **US-1.2** — Jako předseda chci vidět poslední aktivity (kdo byl přidán, co se importovalo, co bylo odesláno), abych měl audit trail.
- **US-1.3** — Jako předseda chci porovnání podílů (prohlášení vs evidence), abych okamžitě viděl, zda sedí součet SČD.

### Acceptance criteria

- **AC-1.1** — GET `/` vrací stránku s 7 stat kartami: Vlastníci, Jednotky, Nájemci, Prostory, Hlasování (s counts per status), Rozesílání (s counts per status), Platby (s dlužníky badge).
- **AC-1.2** — Klik na stat kartu naviguje na odpovídající seznam s aktivní bublinou.
- **AC-1.3** — Tabulka "Poslední aktivity" zobrazuje posledních 20 záznamů z `ActivityLog`, řazeno `created_at DESC`.
- **AC-1.4** — Pokud `SvjInfo.total_shares` je nastaveno a součet `OwnerUnit.share * Unit.podil_scd` se liší, zobrazí se warning badge s rozdílem v %.
- **AC-1.5** — GET `/prehled/rozdil-podilu` vrací tabulku per jednotka: deklarovaný podíl vs evidence + rozdíl.

### URL routy

| Metoda | Path | Funkce |
|---|---|---|
| GET | `/` | Dashboard home |
| GET | `/prehled/rozdil-podilu` | Porovnání podílů |
| GET | `/exportovat/{fmt}` | Export aktivity (xlsx/csv) |

### Závislosti

Všechny evidenční moduly (counts se berou z Owner, Unit, Tenant, Space, Voting, TaxSession, BankStatement). Closely related: `administration/info` (odkud `total_shares`).

---

## Modul 2 — Vlastníci `/vlastnici`

**Účel**: Správa vlastníků (fyzické + právnické osoby). CRUD, inline editace, import z Excelu, import kontaktů.

### User stories

- **US-2.1** — Jako předseda chci importovat seznam vlastníků z Excelu s automatickým namapováním sloupců, abych nemusel ručně psát 80 lidí.
- **US-2.2** — Jako předseda chci sloučit duplicitní vlastníky (stejný člověk přidán dvakrát s překlepem), aby evidence byla čistá.
- **US-2.3** — Jako předseda chci filtrovat seznam podle typu (fyzická/právnická), sekce domu, typu vlastnictví a kontaktních údajů.
- **US-2.4** — Jako předseda chci hledat vlastníky podle jména, e-mailu, telefonu, RČ/IČ nebo čísla jednotky — vše diacritics-insensitive.
- **US-2.5** — Jako předseda chci v detailu vlastníka vidět všechny aktuální i historické jednotky s prokliky.
- **US-2.6** — Jako předseda chci inline upravit kontakty a adresy vlastníka bez přechodu na edit stránku.
- **US-2.7** — Jako předseda chci exportovat filtrovaný seznam do Excelu/CSV s názvem souboru reflektujícím filtr.
- **US-2.8** — Jako předseda chci importovat aktualizované kontakty (e-maily, telefony) s párováním na existující vlastníky.

### Acceptance criteria

- **AC-2.1** — GET `/vlastnici` zobrazí tabulku všech vlastníků s sticky hlavičkou, sortovatelnými sloupci (jméno, typ, e-mail, telefon, podíl, jednotky, sekce, vodoměry), search inputem (`hx-trigger="keyup changed delay:300ms"`) a filtračními bublinami.
- **AC-2.2** — Diacritics-insensitive search: `Owner.name_normalized.like("%curl%")` — ne `name_with_titles.ilike()`.
- **AC-2.3** — Filtrační bubliny: typ (fyzická/právnická), sekce, vlastnictví (SJM, VL, SJVL, Výhradní, Podílové, Neuvedeno), s/bez e-mailu, s/bez telefonu, Bez jednotky.
- **AC-2.4** — Klik na jméno → `GET /vlastnici/{id}?back=...`. Detail obsahuje 4-sloupcovou info kartu (identita, kontakty, trvalá adresa, korespondenční adresa), tabulku jednotek s podíly, kolapsovatelnou historii vlastnictví.
- **AC-2.5** — Inline edit identity: tlačítko "Upravit" → HTMX vrátí form partial → Uložit → redirect nebo OOB swap. Po uložení se zkontrolují duplicity (same `name_normalized`) a nabídne sloučení.
- **AC-2.6** — Inline edit kontaktů (e-mail, e-mail 2, GSM, GSM 2, pevný) a dvou adres (trvalá, korespondenční) funguje stejně.
- **AC-2.7** — Přidání jednotky: dropdown nefilled jednotek, `ownership_type`, `share`, `votes` se zadávají ručně. Validace: podíl 0–1, součet podílů per jednotka nesmí přesáhnout 1.
- **AC-2.8** — Export: `GET /vlastnici/exportovat/xlsx?stav=aktivni` vrátí soubor `vlastnici_aktivni_YYYYMMDD.xlsx` s aktuálními sloupci seznamu.
- **AC-2.9** — Import: `POST /vlastnici/import` (upload) → redirect na mapování → uživatel vybere sheet, počáteční řádek, mapuje sloupce (31 polí v 6 skupinách: Jednotka, Vlastník, Trvalá adresa, Korespondenční adresa, Kontakty, Ostatní) → náhled → potvrzení.
- **AC-2.10** — Mapování se ukládá do `SvjInfo.owner_import_mapping` (JSON). Při dalším importu je předvyplněné.
- **AC-2.11** — Import kontaktů: stejný wizard pro import e-mailů a telefonů, 17 polí v 5 skupinách. Matching přes `name_normalized` + RČ/IČ fallback. Sekundární routing: když Excel má jiný e-mail než DB, nabídne doplnění do `email_secondary`.
- **AC-2.12** — Smazání vlastníka: cascade smaže `OwnerUnit`, `Ballot`, `TaxDistribution`, `Proxy`. ActivityLog zapíše `DELETED`.
- **AC-2.13** — Sloučení duplicit: POST `/vlastnici/{id}/sloucit` s `target_owner_id` → `OwnerUnit` se převedou, ostatní relace se přemapují, duplicitní Owner se smaže (nebo `is_active=False`). ActivityLog zapíše.

### URL routy

| Metoda | Path | Funkce |
|---|---|---|
| GET | `/vlastnici/` | Seznam |
| GET | `/vlastnici/exportovat/{fmt}` | Export (xlsx/csv) |
| GET | `/vlastnici/novy-formular` | Inline form (HTMX partial) |
| POST | `/vlastnici/novy` | Create |
| GET | `/vlastnici/{id}` | Detail |
| GET | `/vlastnici/{id}/identita-formular` | Inline edit identity (HTMX) |
| POST | `/vlastnici/{id}/identita-upravit` | Save identity |
| GET | `/vlastnici/{id}/upravit-formular` | Inline edit contacts (HTMX) |
| POST | `/vlastnici/{id}/upravit` | Save contacts |
| GET | `/vlastnici/{id}/adresa/{prefix}/upravit-formular` | Edit address (prefix=perm/corr) |
| POST | `/vlastnici/{id}/adresa/{prefix}/upravit` | Save address |
| POST | `/vlastnici/{id}/jednotky/pridat` | Add unit |
| POST | `/vlastnici/{id}/jednotky/{ou_id}/odebrat` | Remove unit |
| POST | `/vlastnici/{id}/sloucit` | Merge duplicates |
| GET | `/vlastnici/import` | Import page (history + upload) |
| POST | `/vlastnici/import` | Step 1: upload Excel |
| POST | `/vlastnici/import/mapovani` | Step 1b: reload mapping |
| POST | `/vlastnici/import/nahled` | Step 2: preview |
| POST | `/vlastnici/import/potvrdit` | Step 3: confirm |
| POST | `/vlastnici/import/{log_id}/smazat` | Delete import (rollback) |
| GET | `/vlastnici/import-kontaktu` | Contacts import page |
| POST | `/vlastnici/import-kontaktu` | Step 1 |
| POST | `/vlastnici/import-kontaktu/mapovani` | Reload mapping |
| POST | `/vlastnici/import-kontaktu/nahled` | Preview |
| GET | `/vlastnici/import-kontaktu/zpracovani` | Progress page |
| GET | `/vlastnici/import-kontaktu/zpracovani-stav` | HTMX polling |
| GET | `/vlastnici/import-kontaktu/nahled-vysledek` | Result preview |
| POST | `/vlastnici/import-kontaktu/potvrdit` | Confirm |

### Workflow: Import vlastníků (4 kroky)

```
Upload .xlsx
    ↓ detekce sheetu, startRow
Mapping (31 polí → sloupce Excel)
    ↓ uloží mapping do SvjInfo.owner_import_mapping
Preview (show 10 řádků + errors + stats)
    ↓ uživatel potvrdí
Confirm → vytvoří/aktualizuje Owner, Unit, OwnerUnit
    ↓ ImportLog + ActivityLog
Redirect na /vlastnici?q=imported&stav=aktivni
```

### Závislosti

- `Unit` — při importu se automaticky vytváří / aktualizuje
- `OwnerUnit` — propojení
- `CodeListItem` — pro `ownership_type`, `space_type`, `section`
- `ImportLog`, `ActivityLog`

---

## Modul 3 — Jednotky `/jednotky`

**Účel**: Správa jednotek (byty, garáže, sklepy). CRUD, inline editace, propojení s vlastníky.

### User stories

- **US-3.1** — Jako předseda chci vidět seznam jednotek s vyhledáváním a filtry (typ, sekce) a rychle vidět, kdo je vlastník.
- **US-3.2** — Jako předseda chci v detailu jednotky vidět všechny aktuální i historické vlastníky a upravit podíly.
- **US-3.3** — Jako předseda chci porovnání podílů (prohlášení vs evidence) v seznamu jednotek.

### Acceptance criteria

- **AC-3.1** — GET `/jednotky` zobrazí tabulku s sloupci: číslo, budova, typ, sekce, adresa, LV, místnosti, plocha, podíl.
- **AC-3.2** — Řazení: číslo jednotky je INTEGER, musí se řadit numericky, ne lexikograficky. `ORDER BY unit_number` (sloupec je INTEGER).
- **AC-3.3** — Filtry: typ (byt/nebytová/garáž...), sekce.
- **AC-3.4** — Search: číslo, budova, typ, sekce, adresa, vlastník (přes relationship + `name_normalized`, vč. historických).
- **AC-3.5** — Detail: info karta + tabulka vlastníků (aktuální + historičtí) s prokliky. Historičtí vlastníci v kolapsovatelné sekci s daty od/do.
- **AC-3.6** — Inline edit všech polí (číslo, budova, typ, sekce, adresa, LV, místnosti, plocha, podíl).
- **AC-3.7** — Smazání jednotky: cascade smaže `OwnerUnit`, `WaterMeter`, `Prescription` related. Konfirmační dialog.
- **AC-3.8** — Export: stejný vzor jako vlastníci.

### URL routy

| Metoda | Path | Funkce |
|---|---|---|
| GET | `/jednotky/` | Seznam |
| GET | `/jednotky/exportovat/{fmt}` | Export |
| GET | `/jednotky/nova-formular` | Form (HTMX) |
| POST | `/jednotky/nova` | Create |
| GET | `/jednotky/{id}` | Detail |
| GET | `/jednotky/{id}/info` | Info partial (HTMX) |
| GET | `/jednotky/{id}/upravit-formular` | Edit form |
| POST | `/jednotky/{id}/upravit` | Save |
| GET | `/jednotky/{id}/vlastnici-sekce` | Refresh section (HTMX) |
| GET | `/jednotky/{id}/vlastnik/{ou_id}/upravit-formular` | Inline edit podílu |
| POST | `/jednotky/{id}/vlastnik/{ou_id}/upravit` | Save podíl + type |

### Závislosti

`Owner`, `OwnerUnit`, `WaterMeter`, `CodeListItem`.

---

## Modul 4 — Prostory `/prostory`

**Účel**: Správa nebytových prostor (obchody, kanceláře) s možností pronájmu.

### User stories

- **US-4.1** — Jako předseda chci evidovat nebytové prostory s jejich stavem (pronajatý/volný/blokovaný).
- **US-4.2** — Jako předseda chci přidělit nájemce prostoru se smlouvou (od/do, měsíční nájem, VS, upload smlouvy PDF).
- **US-4.3** — Jako předseda chci importovat prostory z Excelu s wizardem.

### Acceptance criteria

- **AC-4.1** — GET `/prostory` — seznam prostor s bublinami: stav (RENTED/VACANT/BLOCKED), typ.
- **AC-4.2** — Detail: info karta + aktivní nájemce + historie nájmů.
- **AC-4.3** — Přidělit nájemce: inline form s dropdown existujících `Tenant` + "+ nový". Pole: contract_number, contract_start, contract_end, monthly_rent, variable_symbol, contract_path (upload).
- **AC-4.4** — Ukončit nájem: POST `/prostory/{id}/ukoncit-najem` s `end_date` → `SpaceTenant.is_active = False`, `Space.status = VACANT`.
- **AC-4.5** — Import: standardní 4-kroky.

### URL routy

| Metoda | Path | Funkce |
|---|---|---|
| GET | `/prostory/` | Seznam |
| GET | `/prostory/exportovat/{fmt}` | Export |
| GET | `/prostory/novy-formular` | Form |
| POST | `/prostory/novy` | Create |
| GET | `/prostory/{id}` | Detail |
| GET | `/prostory/{id}/info` | Info partial |
| GET | `/prostory/{id}/upravit-formular` | Edit form |
| POST | `/prostory/{id}/upravit` | Save |
| POST | `/prostory/{id}/smazat` | Delete |
| GET | `/prostory/{id}/najemce-formular` | Tenant form (HTMX) |
| GET | `/prostory/{id}/najemce-info` | Tenant info partial |
| POST | `/prostory/{id}/pridat-najemce` | Add tenant |
| POST | `/prostory/{id}/upravit-najemce` | Update tenant assignment |
| POST | `/prostory/{id}/ukoncit-najem` | End tenancy |
| GET | `/prostory/import` | Import page |
| POST | `/prostory/import` | Step 1 |
| POST | `/prostory/import/mapovani` | Step 1b |
| POST | `/prostory/import/nahled` | Step 2 |
| POST | `/prostory/import/potvrdit` | Step 3 |

### Závislosti

`Tenant`, `SpaceTenant`, `Owner` (optional link přes Tenant).

---

## Modul 5 — Nájemci `/najemci`

**Účel**: Správa osob/firem, které si pronajímají Prostory. Nájemci mohou (ale nemusí) být zároveň vlastníky (Owner).

### User stories

- **US-5.1** — Jako předseda chci evidovat nájemce. Pokud nájemce = vlastník, chci jen "linkovat" na existujícího Ownera, ne duplikovat data.
- **US-5.2** — Jako předseda chci vidět, který nájemce pronajímá jaké prostory (může být víc).

### Acceptance criteria

- **AC-5.1** — GET `/najemci` — seznam všech nájemců (aktivní i ukončení).
- **AC-5.2** — Detail: info karta + tabulka aktuálních nájmů + kolapsovatelná historie.
- **AC-5.3** — Pokud `tenant.owner_id IS NOT NULL`, zobrazit identita/kontakt/adresa **read-only** s odkazem "Vlastník →". Inline edit disabled.
- **AC-5.4** — Pokud není linked, plná inline edit (stejně jako Owner).

### URL routy

| Metoda | Path | Funkce |
|---|---|---|
| GET | `/najemci/` | Seznam |
| GET | `/najemci/novy-formular` | Form |
| POST | `/najemci/novy` | Create |
| GET | `/najemci/{id}` | Detail |
| GET | `/najemci/{id}/identita-formular` | Edit form |
| GET | `/najemci/{id}/identita-info` | Info partial |
| POST | `/najemci/{id}/identita-upravit` | Save identity |
| POST | `/najemci/{id}/upravit-kontakt` | Save contact |

### Závislosti

`Owner`, `Space`, `SpaceTenant`.

---

## Modul 6 — Hlasování `/hlasovani`

**Účel**: Správa hlasování per rollam. Workflow: nastavení → generování lístků → rozesílka → zpracování → výsledky → uzavření.

### User stories

- **US-6.1** — Jako předseda chci vytvořit hlasování, nahrát DOCX šablonu lístku, aplikace automaticky extrahuje body hlasování a metadata.
- **US-6.2** — Jako předseda chci vygenerovat personalizované PDF lístky (jeden per vlastník — pro SJM dva).
- **US-6.3** — Jako předseda chci zpracovat odpovědi (PRO/PROTI/Zdržel se) — individuálně nebo hromadně (vyber lístky + nastav hlasy).
- **US-6.4** — Jako předseda chci importovat výsledky z Excelu (např. elektronické hlasování) s 4-kroky: upload → mapování → náhled → potvrzení.
- **US-6.5** — Jako předseda chci vidět výsledky (PRO/PROTI/Zdržel se per bod, kvórum dosaženo ano/ne).
- **US-6.6** — Jako předseda chci opravit špatně zpracovaný lístek (reset + znovu).

### Acceptance criteria

- **AC-6.1** — Vytvoření: POST `/hlasovani/nova` s title, description, start_date, end_date, quorum_threshold (v %, uloží se jako 0–1). Uživatel může uploadovat DOCX — aplikace extrahuje metadata (název, popis, data) a body (regex: odstavce začínající "BOD #") a vyplní formulář.
- **AC-6.2** — Status workflow: `DRAFT` → generování lístků → stále `DRAFT` → změna na `ACTIVE` (uživatel) → zpracování → stále `ACTIVE` → `CLOSED` (uživatel) nebo `CANCELLED`.
- **AC-6.3** — Generování lístků: POST `/hlasovani/{id}/generovat` vytvoří `Ballot` pro každého `Owner` s aktivní `OwnerUnit` (SJM = 2 lístky). `total_votes` = součet hlasů vlastníka napříč jeho jednotkami. Vygeneruje PDF v `data/generated/ballots/` přes docxtpl.
- **AC-6.4** — Kvórum: v UI % (50.0), v DB float (0.5). Router **MUSÍ** dělit `/100` před uložením. Šablona **MUSÍ** násobit `*100` při zobrazení.
- **AC-6.5** — SJM párování při importu: pokud Excel řádek má hlasy, aplikují se na **všechny** `Ballot` jejichž vlastník sdílí danou jednotku. Pokud Excel řádek nemá hlasy (prázdný), jen na první lístek. Deduplikace přes `seen_ballots` set.
- **AC-6.6** — Wizard stepper: kompaktní kroky (Nastavení → Generování → Zpracování → Výsledky → Uzavření). Vizuální stav done/active/pending.
- **AC-6.7** — Seznam lístků: filtry podle stavu (draft/processed/undelivered), search vlastníka (diacritics-insensitive), sortovatelné sloupce (vlastník, jednotky, hlasy, stav).
- **AC-6.8** — Neodevzdané lístky: `GET /hlasovani/{id}/neodevzdane` — lístky s `status != PROCESSED` po uzávěrce. Export do Excelu.
- **AC-6.9** — Oprava lístku: tlačítko "Opravit" na detailu → reset `votes`, `status = RECEIVED` → nové zpracování.

### URL routy

| Metoda | Path | Funkce |
|---|---|---|
| GET | `/hlasovani/` | Seznam |
| GET | `/hlasovani/nova` | Create form |
| POST | `/hlasovani/nova/nahled-metadat` | AJAX: extract DOCX metadata |
| POST | `/hlasovani/nova` | Create |
| GET | `/hlasovani/{id}` | Detail |
| POST | `/hlasovani/{id}/generovat` | Generate ballots |
| POST | `/hlasovani/{id}/stav` | Change status |
| GET | `/hlasovani/{id}/exportovat` | Export results |
| POST | `/hlasovani/{id}/smazat` | Delete |
| POST | `/hlasovani/{id}/pridat-bod` | Add voting item |
| POST | `/hlasovani/{id}/bod/{item_id}/upravit` | Edit item |
| POST | `/hlasovani/{id}/smazat-bod/{item_id}` | Delete item |
| POST | `/hlasovani/{id}/bod/{item_id}/posunout` | Reorder item (up/down) |
| GET | `/hlasovani/{id}/listky` | Ballot list |
| GET | `/hlasovani/{id}/listek/{bid}` | Ballot detail |
| GET | `/hlasovani/{id}/zpracovani` | Processing page |
| POST | `/hlasovani/{id}/zpracovat/{bid}` | Process single |
| POST | `/hlasovani/{id}/zpracovat-hromadne` | Bulk process |
| POST | `/hlasovani/{id}/listek/{bid}/opravit` | Reset + reprocess |
| POST | `/hlasovani/{id}/listky/hromadny-reset` | Reset all |
| GET | `/hlasovani/{id}/listek/{bid}/pdf` | Download PDF |
| GET | `/hlasovani/{id}/neodevzdane` | Undelivered |
| GET | `/hlasovani/{id}/neodevzdane/exportovat` | Export undelivered |
| GET | `/hlasovani/{id}/import` | Import page |
| POST | `/hlasovani/{id}/import` | Step 1: upload |
| POST | `/hlasovani/{id}/import/mapovani` | Step 1b |
| POST | `/hlasovani/{id}/import/nahled` | Step 2: preview |
| POST | `/hlasovani/{id}/import/potvrdit` | Step 3: confirm |

### Workflow: Vytvoření + zpracování

```
Create voting (title, dates, quorum, DOCX template)
    ↓ extract metadata + items
Add/edit items (if needed)
    ↓
Generate ballots (1 per Owner-Unit kombinace, SJM = 2)
    ↓ PDF per ballot
Change status to ACTIVE
    ↓ send emails (z /rozesilani nebo mimo aplikaci)
Process ballots (single or bulk)
    ↓ each BallotVote: PRO/PROTI/ABSTAIN + votes_count
Status CLOSED
    ↓ compute results (sum per item, quorum %)
View results → Export
```

### Závislosti

`Owner`, `Unit`, `OwnerUnit` (pro generate), `Proxy`.

---

## Modul 7 — Rozesílání daní `/rozesilani`

**Účel**: Import PDF daňových rozúčtování, automatické matchování na vlastníky, hromadná e-mailová rozesílka.

### User stories

- **US-7.1** — Jako předseda chci nahrát 80 PDF (jeden per jednotka) s názvy souborů obsahujícími č. jednotky nebo jméno vlastníka.
- **US-7.2** — Jako předseda chci, aby aplikace automaticky spárovala PDF → vlastník (přes text v PDF nebo název souboru).
- **US-7.3** — Jako předseda chci ručně potvrdit / změnit párování, kde auto-match nebyl jistý.
- **US-7.4** — Jako předseda chci konfigurovat e-mail (subject, body z template) a hromadně odeslat všem vlastníkům s platným e-mailem.
- **US-7.5** — Jako předseda chci vidět progress odesílání (kolik odesláno, chyby), moci pozastavit a pokračovat.
- **US-7.6** — Jako předseda chci poslat testovací e-mail na vlastní adresu před spuštěním hromadné rozesílky.

### Acceptance criteria

- **AC-7.1** — GET `/rozesilani/` — seznam TaxSession s filtry podle stavu (draft/ready/sending/paused/completed).
- **AC-7.2** — Vytvoření: upload více PDF najednou → `TaxSession` + `TaxDocument` per PDF. Background processing: extract text, find owner.
- **AC-7.3** — Matching algoritmus: (a) extract unit_number z názvu souboru, match na `Unit`; (b) fuzzy match `extracted_owner_name` na `Owner.name_normalized`. Score 0–1. Auto-match pokud score > 0.8.
- **AC-7.4** — Ruční assign: POST `/rozesilani/{sid}/prirazeni/{doc_id}` s `owner_id`.
- **AC-7.5** — Potvrdit vše: POST `/rozesilani/{sid}/potvrdit-vse` — všechny AUTO_MATCHED → CONFIRMED.
- **AC-7.6** — Rozesílka: POST `/rozesilani/{sid}/rozeslat/odeslat` → background thread → progress dict → HTMX polling na `/rozeslat/prubeh-stav`.
- **AC-7.7** — Batch: posílá `send_batch_size` e-mailů, pauza `send_batch_interval` sekund. Pokud `send_confirm_each_batch`, čeká na manuální potvrzení mezi dávkami.
- **AC-7.8** — Pauza/resume/cancel: mění `send_status` a flagy v background threadu (cooperative cancellation).
- **AC-7.9** — Test e-mail: POST `/rozesilani/{sid}/rozeslat/test` pošle jeden e-mail na adresu z `test_email_address`. Výsledek nastaví `test_email_passed`.
- **AC-7.10** — Recovery: při startu aplikace `recover_stuck_sending_sessions()` najde sessions ve stavu SENDING (když aplikace spadla) a nastaví PAUSED.

### URL routy

| Metoda | Path | Funkce |
|---|---|---|
| GET | `/rozesilani/` | Seznam |
| GET | `/rozesilani/nova` | Create form |
| POST | `/rozesilani/nova` | Create (upload PDFs) |
| GET | `/rozesilani/{id}/upload` | Upload more PDFs |
| POST | `/rozesilani/{id}/upload` | Append/overwrite |
| GET | `/rozesilani/{id}` | Detail (matching + send) |
| GET | `/rozesilani/{id}/procesování` | Processing progress page |
| GET | `/rozesilani/{id}/procesování-stav` | HTMX polling |
| POST | `/rozesilani/{id}/prepočítat-skóre` | Recompute scores |
| GET | `/rozesilani/{id}/prepočítávání` | Recompute progress |
| GET | `/rozesilani/{id}/prepočítávání-stav` | HTMX polling |
| POST | `/rozesilani/{id}/potvrdit/{did}` | Confirm one match |
| POST | `/rozesilani/{id}/prirazeni/{did}` | Manual assign |
| POST | `/rozesilani/{id}/potvrdit-vse` | Confirm all |
| POST | `/rozesilani/{id}/potvrdit-vybrané` | Confirm selected |
| POST | `/rozesilani/{id}/odebrat/{did}` | Remove distribution |
| GET | `/rozesilani/{id}/rozeslat/export/{fmt}` | Export recipients |
| GET | `/rozesilani/{id}/rozeslat` | Send preview |
| POST | `/rozesilani/{id}/rozeslat/email/{did}` | Update email |
| POST | `/rozesilani/{id}/rozeslat/email-vyber/{did}` | Toggle email |
| POST | `/rozesilani/{id}/rozeslat/test` | Send test |
| POST | `/rozesilani/{id}/rozeslat/nastaveni` | Save settings |
| POST | `/rozesilani/{id}/rozeslat/odeslat` | Start batch |
| GET | `/rozesilani/{id}/rozeslat/prubeh` | Progress page |
| GET | `/rozesilani/{id}/rozeslat/prubeh-stav` | HTMX polling |
| POST | `/rozesilani/{id}/rozeslat/pozastavit` | Pause |
| POST | `/rozesilani/{id}/rozeslat/pokračovat` | Resume |
| POST | `/rozesilani/{id}/rozeslat/zrušit` | Cancel |

### Závislosti

`Owner`, `Unit`, `TaxSession`, `TaxDocument`, `TaxDistribution`, `SmtpProfile`, `EmailLog`, `EmailTemplate`.

---

## Modul 8 — Bounces `/rozesilani/bounces`

**Účel**: Kontrola nedoručených e-mailů přes IMAP. Aplikace se připojí k IMAP schránce, prohledá Inbox na DSN (Delivery Status Notification), identifikuje hard/soft bounces a spojí je s `EmailLog`.

### User stories

- **US-8.1** — Jako předseda chci po hromadné rozesílce zjistit, kterým vlastníkům e-mail nedorazil, abych je kontaktoval jinou cestou nebo opravil adresu.
- **US-8.2** — Jako předseda chci, aby aplikace automaticky označila `Owner.email_invalid = True` pro hard bounces.

### Acceptance criteria

- **AC-8.1** — GET `/rozesilani/bounces` — seznam bounces s filtry (typ, modul, stav, smtp profil).
- **AC-8.2** — POST `/rozesilani/bounces/zkontrolovat` spustí background IMAP check. Progress v `_bounce_progress` dict. HTMX polling.
- **AC-8.3** — Pro každý profil v `SmtpProfile` s vyplněným `imap_host`: připojí se přes IMAP SSL, prohledá Inbox za posledních 30 dní, parsuje DSN messages (RFC 3464), extrahuje `recipient_email`, `diagnostic_code`, `reason`, `subject`, `bounce_type`.
- **AC-8.4** — Matching na `EmailLog`: přes `recipient_email` + `subject` + časové okno. Link přes `email_log_id`.
- **AC-8.5** — Hard bounce (kód 5.x.x): `Owner.email_invalid = True`, `email_invalid_reason = <reason>`.
- **AC-8.6** — Deduplikace přes `imap_uid` — žádný duplikátní `EmailBounce` z té samé IMAP zprávy.

### URL routy

| Metoda | Path | Funkce |
|---|---|---|
| GET | `/rozesilani/bounces` | Seznam |
| POST | `/rozesilani/bounces/zkontrolovat` | Start IMAP check |
| GET | `/rozesilani/bounces/zkontrolovat/prubeh` | Progress page |
| GET | `/rozesilani/bounces/zkontrolovat/prubeh-stav` | HTMX polling |
| POST | `/rozesilani/bounces/zkontrolovat/zrusit` | Cancel |
| GET | `/rozesilani/bounces/exportovat/{fmt}` | Export |

### Závislosti

`EmailBounce`, `EmailLog`, `SmtpProfile`, `Owner`.

---

## Modul 9 — Synchronizace `/synchronizace`

**Účel**: Porovnání CSV ze SČD (seznam členů z katastru) s evidencí v DB. Detekce nových vlastníků, změn jmen, odchodů. Výměny vlastníků na jednotce.

### User stories

- **US-9.1** — Jako předseda chci nahrát CSV ze SČD a aplikace mi ukáže: co sedí, co se liší, kdo chybí v CSV (prodal), kdo chybí v DB (nový).
- **US-9.2** — Jako předseda chci jedním klikem "vyměnit vlastníka" — starý vlastník dostane `valid_to`, nový vlastník se vytvoří (nebo napaří se existující) a dostane `OwnerUnit` s dnešním `valid_from`.
- **US-9.3** — Jako předseda chci odmítnout některé návrhy (např. jen překlep, ne skutečná změna).

### Acceptance criteria

- **AC-9.1** — Upload CSV → `SyncSession` + `SyncRecord` per řádek. Status: MATCH / NAME_ORDER / DIFFERENCE / MISSING_CSV / MISSING_EXCEL.
- **AC-9.2** — Algoritmus: match přes číslo jednotky + fuzzy name. NAME_ORDER = stejné křestní/příjmení, jen obrácené pořadí.
- **AC-9.3** — Detail session: filter podle statusu, search, sort. Per řádek akce: Přijmout (aplikovat CSV data na Owner), Odmítnout (no-op), Ručně upravit jméno, Vyměnit vlastníka (viz US-9.2).
- **AC-9.4** — Výměna: single (POST `/synchronizace/{sid}/vymena/{rid}/potvrdit`) nebo batch (POST `/synchronizace/{sid}/vymena-hromadna/potvrdit`). Logika:
  1. Stávající `OwnerUnit` pro unit_number: set `valid_to = today`.
  2. Najít / vytvořit nového Ownera podle CSV jména.
  3. Vytvořit nový `OwnerUnit` s `valid_from = today`, `valid_to = NULL`, přenést `share` a `votes`.
  4. Log: `ActivityLog` per změna.
- **AC-9.5** — Preview před batch: GET `/synchronizace/{sid}/vymena-hromadna/nahled` zobrazí tabulku všech navržených výměn.

### URL routy

| Metoda | Path | Funkce |
|---|---|---|
| GET | `/synchronizace/` | Seznam |
| GET | `/synchronizace/nova` | Upload page |
| POST | `/synchronizace/nova` | Upload CSV → create session |
| GET | `/synchronizace/{id}` | Detail |
| POST | `/synchronizace/{id}/smazat` | Delete |
| POST | `/synchronizace/{id}/prijmout/{rid}` | Accept |
| POST | `/synchronizace/{id}/odmitnout/{rid}` | Reject |
| POST | `/synchronizace/{id}/upravit/{rid}` | Manual edit name |
| POST | `/synchronizace/{id}/aktualizovat` | Apply selected |
| GET | `/synchronizace/{id}/nahled-kontaktu` | Contact preview |
| GET | `/synchronizace/{id}/vymena/{rid}` | Exchange preview (single) |
| POST | `/synchronizace/{id}/vymena/{rid}/potvrdit` | Exchange confirm |
| POST | `/synchronizace/{id}/vymena-hromadna` | Batch preview |
| POST | `/synchronizace/{id}/vymena-hromadna/potvrdit` | Batch confirm |

### Závislosti

`Owner`, `Unit`, `OwnerUnit`, `csv_comparator` service, `owner_exchange` service.

---

## Modul 10 — Kontrola podílů `/kontrola-podilu`

**Účel**: Porovnání podílů vlastníků v Excelu s podíly v DB. Typicky jeden-time kontrola po importu.

### User stories

- **US-10.1** — Jako předseda chci nahrát Excel s podíly (např. od právníka) a porovnat s DB — identifikovat rozdíly.
- **US-10.2** — Jako předseda chci jedním klikem aktualizovat DB hodnotami z Excelu pro vybrané záznamy.

### Acceptance criteria

- **AC-10.1** — Upload → `ShareCheckSession`. Mapování: col_unit, col_share. Cache přes `ShareCheckColumnMapping`.
- **AC-10.2** — Per řádek: MATCH / DIFFERENCE / MISSING_DB / MISSING_FILE.
- **AC-10.3** — POST `/kontrola-podilu/{id}/aktualizovat` aplikuje vybrané změny na `OwnerUnit.share` nebo `Unit.podil_scd`.

### URL routy

| Metoda | Path | Funkce |
|---|---|---|
| GET | `/kontrola-podilu/` | Seznam |
| POST | `/kontrola-podilu/nova` | Upload |
| GET | `/kontrola-podilu/mapovani` | Mapping page |
| POST | `/kontrola-podilu/potvrdit-mapovani` | Confirm mapping |
| GET | `/kontrola-podilu/{id}` | Detail |
| POST | `/kontrola-podilu/{id}/exportovat` | Export |
| POST | `/kontrola-podilu/{id}/smazat` | Delete |
| POST | `/kontrola-podilu/{id}/aktualizovat` | Apply updates |

### Závislosti

`Owner`, `Unit`, `OwnerUnit`, `share_check_comparator` service.

---

## Modul 11 — Administrace `/sprava`

**Účel**: Systémové nastavení (SvjInfo, adresy, výbor), číselníky, e-mailové šablony, zálohy, purge, export.

### User stories

- **US-11.1** — Jako předseda chci nastavit základní údaje SVJ (název, IČO, adresa, celkový počet podílů).
- **US-11.2** — Jako předseda chci spravovat členy výboru (jméno, role, kontakt) — zobrazují se v e-mailech.
- **US-11.3** — Jako předseda chci upravovat číselníky (typy prostor, sekce, typy vlastnictví) v rámci projektu.
- **US-11.4** — Jako předseda chci šablony e-mailů (subject + body s Jinja2 placeholdery).
- **US-11.5** — Jako předseda chci zálohovat DB do ZIP souboru + obnovit z libovolné zálohy.
- **US-11.6** — Jako předseda chci vymazat celé kategorie dat (např. všechna hlasování) — potvrzení vyžadováno.
- **US-11.7** — Jako předseda chci exportovat kategorii dat (např. všechny vlastníky) do Excelu.
- **US-11.8** — Jako předseda chci hromadně upravit pole (např. nastavit "sekce = A" pro všechny jednotky s číslem 1–50).
- **US-11.9** — Jako předseda chci detekovat a sloučit duplicity (vlastník stejné jméno, stejné RČ).

### Acceptance criteria

- **AC-11.1** — `SvjInfo` je singleton: vždy max 1 záznam. Pokud neexistuje, vytvoří se při prvním přístupu.
- **AC-11.2** — Záloha: POST `/sprava/zaloha/vytvorit` → ZIP v `data/backups/svj_backup_YYYYMMDD_HHMMSS.zip` obsahující `svj.db` + `uploads/` + `generated/` + `.smtp_key`.
- **AC-11.3** — Obnova: POST `/sprava/zaloha/{filename}/obnovit` → rozbalí ZIP, nahradí `svj.db`, spustí `run_post_restore_migrations()`.
- **AC-11.4** — Purge: kategorie (vlastníci, jednotky, hlasování, platby, ...) + speciální (zálohy jako soubory, historie obnovení). Pořadí mazání (`_PURGE_ORDER`) respektuje FK závislosti.
- **AC-11.5** — Potvrzení: uživatel zapíše slovo "DELETE" do formuláře. Jinak 400.
- **AC-11.6** — Export kategorie: GET `/sprava/export/{category}/{fmt}` vrátí soubor. Hromadný export: POST `/sprava/export/hromadny` zabalí víc kategorií do ZIP.
- **AC-11.7** — Hromadné úpravy: GET `/sprava/hromadne-upravy` — zvolit entity, pole, filtrovat záznamy, zadat novou hodnotu, aplikovat.
- **AC-11.8** — Duplicity: GET `/sprava/duplicity` — aplikace detekuje duplicity (same `name_normalized` + same `birth_number` pro Owner; same `meter_serial` pro WaterMeter). Uživatel klikne "Sloučit".

### URL routy (výběr; kompletní viz router)

| Metoda | Path | Funkce |
|---|---|---|
| GET | `/sprava/` | Hlavní stránka administrace |
| GET | `/sprava/svj-info` | SvjInfo page |
| POST | `/sprava/info` | Save SvjInfo |
| POST | `/sprava/adresa/pridat` | Add address |
| POST | `/sprava/adresa/{id}/upravit` | Edit address |
| POST | `/sprava/adresa/{id}/smazat` | Delete address |
| POST | `/sprava/clen/pridat` | Add board member |
| POST | `/sprava/clen/{id}/upravit` | Edit |
| POST | `/sprava/clen/{id}/smazat` | Delete |
| GET | `/sprava/ciselniky` | Code lists page |
| POST | `/sprava/ciselnik/pridat` | Add item |
| POST | `/sprava/ciselnik/{id}/upravit` | Edit |
| POST | `/sprava/ciselnik/{id}/smazat` | Delete |
| POST | `/sprava/sablona/pridat` | Add email template |
| POST | `/sprava/sablona/{id}/upravit` | Edit |
| POST | `/sprava/sablona/{id}/smazat` | Delete |
| GET | `/sprava/zalohy` | Backups page |
| POST | `/sprava/zaloha/vytvorit` | Create backup |
| GET | `/sprava/zaloha/{filename}/stahnout` | Download |
| POST | `/sprava/zaloha/{filename}/smazat` | Delete |
| POST | `/sprava/zaloha/{filename}/prejmenovat` | Rename |
| POST | `/sprava/zaloha/{filename}/obnovit` | Restore |
| POST | `/sprava/zaloha/obnovit` | Restore from upload |
| POST | `/sprava/zaloha/obnovit-soubor` | Restore single file |
| POST | `/sprava/zaloha/obnovit-slozku` | Restore directory |
| GET | `/sprava/smazat` | Purge page |
| POST | `/sprava/smazat-data` | Purge |
| GET | `/sprava/export` | Export page |
| GET | `/sprava/export/{category}/{fmt}` | Export category |
| POST | `/sprava/export/hromadny` | Bulk export (ZIP) |
| GET | `/sprava/hromadne-upravy` | Bulk edit page |
| GET | `/sprava/hromadne-upravy/hodnoty` | HTMX: values dropdown |
| GET | `/sprava/hromadne-upravy/zaznamy` | HTMX: records |
| POST | `/sprava/hromadne-upravy/opravit` | Apply |
| GET | `/sprava/duplicity` | Duplicates page |
| POST | `/sprava/duplicity/sloucit` | Merge pair |
| POST | `/sprava/duplicity/sloucit-vse` | Merge all |

### Závislosti

Všechny ostatní moduly — administrace je "nad" nimi.

---

## Modul 12 — Nastavení `/nastaveni`

**Účel**: Správa SMTP profilů, historie e-mailů, globální nastavení odesílání.

### User stories

- **US-12.1** — Jako předseda chci spravovat víc SMTP profilů (Gmail, vlastní server, testovací) a jeden označit jako výchozí.
- **US-12.2** — Jako předseda chci otestovat SMTP profil (odešle testovací e-mail) před hromadnou rozesílkou.
- **US-12.3** — Jako předseda chci vidět historii všech odeslaných e-mailů s možností prohlížet přílohy.

### Acceptance criteria

- **AC-12.1** — SMTP profil CRUD přes HTMX partials (seznam = tabulka, klik na řádek → form inline, Uložit → swap na display).
- **AC-12.2** — Heslo šifrované Fernetem (klíč v `data/.smtp_key`). Pokud `.smtp_key` neexistuje, vygeneruje se při prvním uložení profilu.
- **AC-12.3** — Test: POST `/nastaveni/smtp/{id}/test` s `test_email` → pokus o odeslání → flash zpráva OK/error.
- **AC-12.4** — Seznam `EmailLog` s filtry: search (recipient_email, recipient_name, subject — diacritics-insensitive přes `name_normalized`), sort, module filter.
- **AC-12.5** — Přílohy: GET `/nastaveni/priloha/{log_id}/{filename}` — validace, že cesta je v povoleném adresáři (path traversal prevention), `FileResponse`.

### URL routy

| Metoda | Path | Funkce |
|---|---|---|
| GET | `/nastaveni/` | Main page |
| GET | `/nastaveni/exportovat/{fmt}` | Export email log |
| POST | `/nastaveni/odesilani` | Save global settings |
| GET | `/nastaveni/smtp/profily` | HTMX: list |
| GET | `/nastaveni/smtp/novy-formular` | HTMX: new form |
| GET | `/nastaveni/smtp/{id}/formular` | HTMX: edit form |
| GET | `/nastaveni/smtp/{id}/karta` | HTMX: display card |
| POST | `/nastaveni/smtp/novy` | Create |
| POST | `/nastaveni/smtp/{id}` | Update |
| POST | `/nastaveni/smtp/{id}/test` | Test |
| POST | `/nastaveni/smtp/{id}/vychozi` | Set default |
| POST | `/nastaveni/smtp/{id}/smazat` | Delete |
| GET | `/nastaveni/priloha/{log_id}/{filename}` | Download attachment |

### Závislosti

`SmtpProfile`, `EmailLog`, `SvjInfo` (pro global defaults).

---

## Modul 13 — Platby `/platby`

**Účel**: Největší a nejkomplexnější modul. Správa předpisů (roční plán plateb per jednotka), bankovních výpisů (import CSV z banky), mapování VS, počátečních zůstatků, matice plateb, dlužníků, vyúčtování, nesrovnalostí.

### Sub-moduly

- **Přehled** — matice jednotky × měsíce + seznam dlužníků
- **Předpisy** — import z DOCX, seznam per rok
- **Výpisy** — import CSV z Fio, přiřazování plateb na předpisy
- **Symboly** — mapování VS → jednotka/prostor
- **Zůstatky** — počáteční zůstatky per rok
- **Vyúčtování** — roční výkaz per jednotka (PDF)
- **Nesrovnalosti** — upozornění vlastníkům na chybné platby

### User stories (hlavní)

- **US-13.1** — Jako předseda chci naimportovat předpisy z DOCX tabulky a aplikace je rozpadne per jednotka + položka (provozní, fond oprav, služby).
- **US-13.2** — Jako předseda chci naimportovat CSV z Fio, aplikace automaticky spáruje platby na předpisy podle VS.
- **US-13.3** — Jako předseda chci ručně opravit nespárované platby — přiřadit platbu vlastníkovi nebo prostoru.
- **US-13.4** — Jako předseda chci vidět matici "jednotky × měsíce" s barevným odlišením (zaplaceno / nedoplatek / přeplatek).
- **US-13.5** — Jako předseda chci seznam dlužníků s výší dluhu a kontakty.
- **US-13.6** — Jako předseda chci vygenerovat roční vyúčtování per jednotka (PDF) s položkami (výtah, voda, úklid...) a výpočtem doplatek/přeplatek.
- **US-13.7** — Jako předseda chci upozornit vlastníky na nesrovnalosti (chybný VS, špatná částka, rozpad na víc VS) hromadným e-mailem.
- **US-13.8** — Jako předseda chci uzamknout bankovní výpis, aby se po účetní uzávěrce nedaly platby měnit.

### Acceptance criteria (výběr)

- **AC-13.1** — Matice plateb: `GET /platby/prehled?rok=2025` — tabulka jednotky × měsíce. Každá buňka: zelená (zaplaceno = `předpis`), červená (nedoplatek), modrá (přeplatek). Sort a search.
- **AC-13.2** — Dlužníci: `GET /platby/dluznici?rok=2025` — seznam jednotek s `result < 0`. Sloupec s výší dluhu, kontaktem.
- **AC-13.3** — Import předpisů: upload DOCX → `word_parser` extrahuje tabulku → vytvoří `PrescriptionYear` + `Prescription` per jednotka + `PrescriptionItem` per položka (kategorie: PROVOZNI / FOND_OPRAV / SLUZBY).
- **AC-13.4** — Import výpisu: upload CSV (Fio formát) → dynamic mapping → `BankStatement` + `Payment` per transakci. Matching přes `payment_matching` service: match `vs` na `Prescription.variable_symbol`, pak `date` (v rámci měsíce), pak `amount` (±Kč tolerance).
- **AC-13.5** — `PaymentAllocation`: pokud jedna platba pokrývá víc VS (např. 2 jednotky), rozpadne se na allocations.
- **AC-13.6** — Uzamčení výpisu: POST `/platby/vypisy/{sid}/zamknout` → `locked_at = now`. Po tomto se platby nedají měnit (server-side validace).
- **AC-13.7** — Vyúčtování: POST `/platby/vyuctovani/generovat` s `year` → per unit: `SettlementItem` podle `PrescriptionItem.name` → `result = cost_unit - paid`. PDF generated.
- **AC-13.8** — Nesrovnalosti: dataclass `Discrepancy` (neperzistuje), počítá on-the-fly:
  - `wrong_vs` — platba má VS, který nepatří do SVJ
  - `wrong_amount` — částka neodpovídá `prescription.monthly_total`
  - `combined` — jedna platba pokrývá víc měsíců
- **AC-13.9** — Rozesílka nesrovnalostí: stejný background pattern jako tax module (batch, pause/resume).
- **AC-13.10** — Symboly (VS mapování): CRUD. Automaticky vytvořené při importu předpisů (`source=AUTO`), manuálně přidané (`source=MANUAL`).
- **AC-13.11** — Zůstatky: import z Excelu nebo manuální přidání. Per jednotka-rok.

### URL routy (hlavní)

| Sub-modul | Metoda | Path | Funkce |
|---|---|---|---|
| Root | GET | `/platby/` | Redirect na `/platby/predpisy` |
| Přehled | GET | `/platby/prehled` | Matice |
| | GET | `/platby/prehled/exportovat/{fmt}` | Export |
| | GET | `/platby/dluznici` | Debtors |
| | GET | `/platby/dluznici/exportovat/{fmt}` | Export |
| | GET | `/platby/jednotka/{uid}` | Unit detail |
| | GET | `/platby/prostor/{sid}` | Space detail |
| Předpisy | GET | `/platby/predpisy` | Years list |
| | GET | `/platby/predpisy/import` | Import form |
| | POST | `/platby/predpisy/import` | Upload DOCX |
| | GET | `/platby/predpisy/{yid}` | Year detail |
| | GET | `/platby/predpisy/{yid}/exportovat/{fmt}` | Export |
| Výpisy | GET | `/platby/vypisy` | List |
| | GET | `/platby/vypisy/exportovat/{fmt}` | Export |
| | GET | `/platby/vypisy/import` | Import form |
| | POST | `/platby/vypisy/import` | Upload CSV |
| | GET | `/platby/vypisy/{sid}` | Detail |
| | GET | `/platby/vypisy/{sid}/soubor` | Download source |
| | GET | `/platby/vypisy/{sid}/exportovat/{fmt}` | Export |
| | POST | `/platby/vypisy/{sid}/prirazeni/{pid}` | Assign owner |
| | POST | `/platby/vypisy/{sid}/prirazeni-prostor/{pid}` | Assign space |
| | POST | `/platby/vypisy/{sid}/potvrdit-vse` | Confirm all |
| | POST | `/platby/vypisy/{sid}/potvrdit/{pid}` | Confirm one |
| | POST | `/platby/vypisy/{sid}/odmitnout/{pid}` | Reject |
| | POST | `/platby/vypisy/{sid}/preparovat` | Prepare for sending |
| | POST | `/platby/vypisy/{sid}/smazat` | Delete |
| | POST | `/platby/vypisy/{sid}/zamknout` | Lock |
| Symboly | GET | `/platby/symboly` | List |
| | GET | `/platby/symboly/exportovat/{fmt}` | Export |
| | POST | `/platby/symboly/pridat` | Add |
| | GET | `/platby/symboly/{mid}/upravit-formular` | Edit form |
| | GET | `/platby/symboly/{mid}/info` | Info partial |
| | POST | `/platby/symboly/{mid}/upravit` | Edit |
| | POST | `/platby/symboly/{mid}/smazat` | Delete |
| Zůstatky | GET | `/platby/zustatky` | List |
| | GET | `/platby/zustatky/exportovat/{fmt}` | Export |
| | POST | `/platby/zustatky/pridat` | Add |
| | GET | `/platby/zustatky/{bid}/upravit-formular` | Edit form |
| | GET | `/platby/zustatky/{bid}/info` | Info partial |
| | POST | `/platby/zustatky/{bid}/upravit` | Edit |
| | POST | `/platby/zustatky/{bid}/smazat` | Delete |
| | GET | `/platby/zustatky/vlastnici/{uid}` | HTMX dropdown |
| | GET | `/platby/zustatky/import` | Import form |
| | POST | `/platby/zustatky/import` | Upload |
| | GET | `/platby/zustatky/import/mapovani` | Mapping |
| | POST | `/platby/zustatky/import/mapovani` | Reload |
| | POST | `/platby/zustatky/import/nahled` | Preview |
| | POST | `/platby/zustatky/import/potvrdit` | Confirm |
| Vyúčtování | GET | `/platby/vyuctovani` | List |
| | GET | `/platby/vyuctovani/{sid}` | Detail |
| | POST | `/platby/vyuctovani/generovat` | Generate |
| | POST | `/platby/vyuctovani/{sid}/stav` | Change status |
| | POST | `/platby/vyuctovani/smazat-rok` | Delete year |
| | POST | `/platby/vyuctovani/hromadny-stav` | Bulk status |
| | POST | `/platby/vyuctovani/hromadny-stav-filtrovane` | Bulk filtered |
| | GET | `/platby/vyuctovani/exportovat/{fmt}` | Export |
| Nesrovnalosti | GET | `/platby/vypisy/{sid}/nesrovnalosti` | Preview |
| | POST | `/platby/vypisy/{sid}/nesrovnalosti/nastaveni` | Save settings |
| | POST | `/platby/vypisy/{sid}/nesrovnalosti/test` | Test |
| | POST | `/platby/vypisy/{sid}/nesrovnalosti/odeslat` | Send |
| | GET | `/platby/vypisy/{sid}/nesrovnalosti/prubeh` | Progress |
| | GET | `/platby/vypisy/{sid}/nesrovnalosti/prubeh-stav` | Poll |
| | POST | `/platby/vypisy/{sid}/nesrovnalosti/pozastavit` | Pause |
| | POST | `/platby/vypisy/{sid}/nesrovnalosti/pokracovat` | Resume |
| | POST | `/platby/vypisy/{sid}/nesrovnalosti/zrusit` | Cancel |

### Závislosti

Všechny předchozí moduly (Owner, Unit, Space, Tenant). Služby: `payment_matching`, `payment_overview`, `payment_discrepancy`, `bank_import`, `balance_import`, `prescription_import`, `word_parser`, `settlement_service`.

---

## Modul 14 — Vodoměry `/vodometry`

**Účel**: Import odečtů z Excelu, přiřazení jednotkám, rozesílka přehledu vlastníkům.

### User stories

- **US-14.1** — Jako předseda chci 2× ročně naimportovat Excel s odečty (č. jednotky, sériové číslo vodoměru, datum, stav).
- **US-14.2** — Jako předseda chci automaticky přiřadit vodoměry jednotkám dle sériového čísla.
- **US-14.3** — Jako předseda chci poslat vlastníkům přehled jejich odečtů (který vodoměr, kolik spotřeboval).

### Acceptance criteria

- **AC-14.1** — 4-kroky import: upload → mapping → preview → confirm.
- **AC-14.2** — Preview: tabulka odečtů, stat: "nově přiřazeno X vodoměrů", "nepárovatelné: Y".
- **AC-14.3** — Přiřazení: POST `/vodometry/{mid}/prirazeni` s `unit_id`.
- **AC-14.4** — Rozesílka: stejný pattern jako tax module (test, batch, pause/resume).

### URL routy

| Metoda | Path | Funkce |
|---|---|---|
| GET | `/vodometry/` | List |
| GET | `/vodometry/exportovat/{fmt}` | Export |
| GET | `/vodometry/{id}` | Detail |
| POST | `/vodometry/{id}/prirazeni` | Assign unit |
| GET | `/vodometry/import` | Import form |
| POST | `/vodometry/import/nahrat` | Upload |
| POST | `/vodometry/import/mapovani` | Reload mapping |
| POST | `/vodometry/import/nahled` | Preview |
| GET | `/vodometry/import/nahled/{bid}` | Preview page |
| POST | `/vodometry/import/potvrdit/{bid}` | Confirm |
| GET | `/vodometry/rozeslat` | Send preview |
| POST | `/vodometry/rozeslat/nastaveni` | Save settings |
| POST | `/vodometry/rozeslat/test` | Test |
| POST | `/vodometry/rozeslat/odeslat` | Send |
| GET | `/vodometry/rozeslat/prubeh` | Progress |
| GET | `/vodometry/rozeslat/prubeh-stav` | Poll |
| POST | `/vodometry/rozeslat/pozastavit` | Pause |
| POST | `/vodometry/rozeslat/pokracovat` | Resume |
| POST | `/vodometry/rozeslat/zrusit` | Cancel |

### Závislosti

`Unit`, `WaterMeter`, `WaterReading`, `SmtpProfile`, `EmailLog`.

---

## Sdílené vzory napříč moduly

### Multi-step import wizard (4 kroky)

Aplikováno v: **vlastníci**, **kontakty**, **hlasování** (import hlasů), **prostory**, **vodoměry**, **zůstatky**, **předpisy** (DOCX), **výpisy** (CSV).

```
┌─────────────┐   ┌──────────┐   ┌────────┐   ┌──────────┐
│  1. Upload  │ → │ 2. Map   │ → │ 3. Preview│ → │ 4. Confirm│
│   soubor    │   │ sloupce  │   │   data   │   │          │
└─────────────┘   └──────────┘   └────────┘   └──────────┘
```

- Cesta k souboru se předává **jako hidden field** (ne session).
- Mapování se ukládá do `SvjInfo.*_import_mapping` (JSON), předvyplní se při dalším importu.
- Wizard stepper partial `partials/wizard_stepper.html` — sdílený napříč moduly. Kontext z `build_import_wizard(step)` v `app/utils.py`.

### Background úlohy + progress polling

Aplikováno v: **rozesílání daní**, **vodoměry**, **nesrovnalosti**, **bounces**, **tax processing**.

```python
# Start
_progress_dict = {}
_progress_dict[session_id] = {"current": 0, "total": N, "started_at": utcnow(), "cancel": False}
thread = threading.Thread(target=_worker, args=(session_id, ...))
thread.start()

# Worker aktualizuje _progress_dict[session_id]["current"] += 1

# Pause/Resume/Cancel → flip flags, worker kooperativně kontroluje

# HTMX polling GET /*-stav:
# - pokud progress < total → vrátí partial s progress barem
# - pokud progress == total → vrátí HTMX-Redirect header na výsledkovou stránku
```

### Export pattern

Každá datová stránka (tabulka s desítkami řádků):
- V hlavičce `↓ Excel` + `↓ CSV` tlačítka se stejným stylem (`bg-gray-100 text-gray-600 border-gray-200`).
- Endpoint `/exportovat/{fmt}` přijímá `xlsx` | `csv`.
- Respektuje aktivní filtry (`q`, `stav`, `typ`, `sekce`, ...).
- Název souboru: `{modul}_{filter_suffix}_{YYYYMMDD}.{fmt}`, např. `vlastnici_aktivni_20260421.xlsx`.

### Back URL chain

Detail entity zná, odkud uživatel přišel:
- V odkazu: `<a href="/vlastnici/{id}?back=/vlastnici?typ=fyzicke">`
- V detailu: `back_url = request.query_params.get("back")`. Pokud je nastaveno, zobrazí se šipka `← Zpět na seznam vlastníků`.
- Label se počítá v routeru na základě `back_url` path matching.

Viz `docs/NAVIGATION.md` v originálu.

---

## Next step

Pokračuj do [`PRD_UI.md`](PRD_UI.md) pro **klíčové UI konvence** (redestilát). Detailní UI vzory jsou v `appendices/UI_GUIDE.md`.
