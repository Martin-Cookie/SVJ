# SVJ Audit Report – 2026-04-12

Code Guardian — 11. audit. Navazuje na [audit z 2026-04-11](archive/). Od posledního auditu 5 commitů: docs restructuring (CLAUDE.md split do 4 docs/ souborů), Dluh→Saldo refactoring, multi-SMTP profily, inline editace zůstatků, tooltip v matici plateb. Kontrola stavu 13 nálezů z předchozího auditu + scan nových problémů.

## Souhrn

- **CRITICAL**: 0
- **HIGH**: 1
- **MEDIUM**: 5
- **LOW**: 5

## Status předchozích nálezů (audit 2026-04-11)

| # | Původní severity | Problém | Status |
|---|------------------|---------|--------|
| 1 | HIGH | N^2 lookup v `_prepare_owner_lookup` | **OPRAVENO** (commit 2ea0a16) |
| 2 | HIGH | Křehký `_back\|replace` v `vypisy.html` | **OPRAVENO** (commit 2ea0a16, `qs()` macro) |
| 3 | MEDIUM | `_sort_suffix[1:]` v `voting/index.html` | **OPRAVENO** (commit 2ea0a16, `qs()` macro) |
| 4 | MEDIUM | `tax_recompute_scores` opakované `match_name` | **OPRAVENO** (commit 2ea0a16, memo cache) |
| 5 | MEDIUM | `\|safe` SVG šipky v voting šablonách | **OPRAVENO** (commit a959ef3, `_sort_icon.html` partial) |
| 6 | MEDIUM | F-string v SQL v backup_service | **OPRAVENO** (commit 2ea0a16, whitelist assert) |
| 7 | MEDIUM | Nepoužitá `as e` v except | **OPRAVENO** (commit 2ea0a16). Zbývající `as e` v `processing.py:309` je legitimní (`str(e)` na řádku 312) |
| 8 | MEDIUM | Balast v `docs/reports/` | **OPRAVENO** (commit a959ef3, přesun do `archive/`) |
| 9 | LOW | `owner_update` generický název | **OTEVŘENO** → přeneseno jako #9 |
| 10 | LOW | Emoji v bounce badges | **ČÁSTEČNĚ** — `_table.html` opraveno (a959ef3), ale `index.html` stále obsahuje 🔴🟡⚪ → přeneseno jako #10 |
| 11 | LOW | Docstring `_stem_czech_surname` | **OPRAVENO** (commit 2ea0a16) |
| 12 | LOW | `_group_key_counts` konvence | **OPRAVENO** (commit 2ea0a16, rename na `grouped_emails`) |
| 13 | LOW | `test_owner_matcher.py` neexistuje | **OPRAVENO** (commit 2ea0a16, 10 nových testů) |

**Skóre**: 10 z 13 plně opraveno, 1 částečně, 2 přeneseno.

## Souhrnná tabulka — aktuální nálezy

| # | Oblast | Soubor | Severity | Problém | Čas | Rozhodnutí |
|---|--------|--------|----------|---------|-----|------------|
| 1 | Dokumentace | `docs/UI_GUIDE.md:632,707,184` | HIGH | Zlomené křížové odkazy do CLAUDE.md po docs restructuringu — sekce přesunuty do `docs/` souborů, ale UI_GUIDE odkazuje na původní § názvy | ~15 min | 🔧 |
| 2 | Dokumentace | `docs/ROUTER_PATTERNS.md:72` | MEDIUM | Příklad kódu používá deprecated TemplateResponse API (`"request": request` v context dict), ale téhož soubor na řádku 40 dokumentuje nový API styl | ~5 min | 🔧 |
| 3 | Bezpečnost | `app/models/smtp_profile.py:18` | MEDIUM | SMTP hesla uložena jako base64 (ne šifrování) — snadno dekódovatelná z DB dump/zálohy | ~30 min | ❓ |
| 4 | Kód / Konvence | `app/main.py:_ensure_indexes()` | MEDIUM | Chybí indexy pro nový model `SmtpProfile` (`is_default`) a FK sloupce `smtp_profile_id` na `tax_sessions` a `bank_statements` | ~5 min | 🔧 |
| 5 | Kód | `app/templates/voting/index.html:18` + `payments/vypisy.html:8` | MEDIUM | `qs()` Jinja macro duplikováno ve 2 šablonách — kandidát na sdílený partial | ~10 min | ❓ |
| 6 | Git Hygiene | `.playwright-mcp/` | MEDIUM | 50 souborů (logy, screenshoty, yml snapshoty, .crx) zůstalo po testování — celkem ~9 MB | ~1 min | 🔧 |
| 7 | Kód / UX | `app/routers/owners/crud.py:725` | LOW | Endpoint `owner_update` přijímá pouze kontakty — název je generický (přeneseno z předchozího auditu #9) | ~15 min | ❓ |
| 8 | UI | `app/templates/bounces/index.html:79,84,89` | LOW | Emoji v bublinkách (🔴🟡⚪) — `_table.html` opraveno, ale `index.html` zůstalo (přeneseno z #10, částečná oprava) | ~5 min | 🔧 |
| 9 | Testy | `tests/test_smtp_profile.py` neexistuje | LOW | Nový model `SmtpProfile` + 15 endpointů v `settings_page.py` bez testů. CRUD, default toggle, password obfuskace, IMAP save-to-sent | ~45 min | 🔧 |
| 10 | UI / Konzistence | Dluh vs Saldo terminologie | LOW | Refaktoring Dluh→Saldo provedeno v `/platby/prehled` a `/platby/dluznici`, ale `/vlastnici`, `/jednotky` a `units/detail.html` stále zobrazují „Dluh" | ~15 min | ❓ |
| 11 | Dokumentace | `docs/UI_GUIDE.md:57` | LOW | Inline reference `viz CLAUDE.md § Navigace a back URL` bez odkazu — čtenář nemůže kliknout (oproti jiným řádkům kde je `[text](link)`) | ~2 min | 🔧 |

Legenda: 🔧 = jen opravit, ❓ = potřeba rozhodnutí uživatele

## Detailní nálezy

### 1. Dokumentace

#### #1 Zlomené křížové odkazy v UI_GUIDE.md po docs restructuringu (HIGH)

- **Co a kde**: Commit `b4563ce` přesunul 4 velké sekce z CLAUDE.md do samostatných souborů v `docs/`:
  - `§ Navigace a back URL` → `docs/NAVIGATION.md`
  - `§ Router vzory` (vč. Formulářová validace) → `docs/ROUTER_PATTERNS.md`
  - `§ Nové moduly / entity` (vč. Wizard stepper) → `docs/NEW_MODULE_CHECKLIST.md`
  - `§ Uživatelské role` → `docs/USER_ROLES.md`

  Ale `docs/UI_GUIDE.md` stále odkazuje na původní umístění v CLAUDE.md:
  - **Řádek 184**: `viz [CLAUDE.md — Formulářová validace](../CLAUDE.md)` — sekce přesunuta do `docs/ROUTER_PATTERNS.md`
  - **Řádek 632**: `podrobný popis v [CLAUDE.md](../CLAUDE.md) § Nové moduly / entity` — obsah přesunut do `docs/NEW_MODULE_CHECKLIST.md`
  - **Řádek 707**: `jsou v [CLAUDE.md § Wizard stepper](../CLAUDE.md)` — sekce „Wizard stepper" v CLAUDE.md nikdy neexistovala jako heading; wizard detaily jsou v `docs/NEW_MODULE_CHECKLIST.md`
  - **Řádek 788**: `je v [CLAUDE.md § Navigace a back URL](../CLAUDE.md)` — CLAUDE.md stále má heading, ale jako stub (redirect na `docs/NAVIGATION.md`). Odkaz funkční ale nepřímý

  CLAUDE.md zachovává stub headingy s `> Viz docs/...`, takže cesty fyzicky nekončí 404, ale čtenář je veden na stub místo na skutečný obsah. Řádek 707 je nejhorší — heading „Wizard stepper" v CLAUDE.md vůbec neexistuje.

- **Řešení**: Aktualizovat 4 odkazy v UI_GUIDE.md aby ukazovaly přímo na nové soubory:
  - `[CLAUDE.md — Formulářová validace](../CLAUDE.md)` → `[ROUTER_PATTERNS.md — Formulářová validace](ROUTER_PATTERNS.md)`
  - `[CLAUDE.md](../CLAUDE.md) § Nové moduly / entity` → `[NEW_MODULE_CHECKLIST.md](NEW_MODULE_CHECKLIST.md)`
  - `[CLAUDE.md § Wizard stepper](../CLAUDE.md)` → `[NEW_MODULE_CHECKLIST.md § Wizard stepper](NEW_MODULE_CHECKLIST.md)`
  - `[CLAUDE.md § Navigace a back URL](../CLAUDE.md)` → `[NAVIGATION.md](NAVIGATION.md)`
- **Náročnost**: nízká, ~15 min (4 řádky, ale ověřit že nezůstaly další).
- **Regrese**: nulové — jen dokumentace.
- **Test**: Otevřít UI_GUIDE.md na GitHubu, kliknout na 4 opravené odkazy — musí vést na správný heading.

#### #2 Deprecated TemplateResponse API v příkladu (MEDIUM)

- **Co a kde**: `docs/ROUTER_PATTERNS.md:72` — příklad kódu v sekci „Formulářová validace" používá starý API styl:
  ```python
  return templates.TemplateResponse("partials/owner_create_form.html", {
      "request": request,  # <-- deprecated
  })
  ```
  Přitom téhož soubor na řádku 40 dokumentuje správný styl (request jako první arg).
- **Řešení**: opravit příklad na `templates.TemplateResponse(request, "partials/...", {...})`.
- **Čas**: ~5 min.
- **Regrese**: nulové.

#### #11 Inline reference bez odkazu (LOW)

- **Co a kde**: `docs/UI_GUIDE.md:57` — text `viz CLAUDE.md § Navigace a back URL` je plain text bez `[odkazu](cesta)`. Ostatní podobné reference v souboru jsou klikací.
- **Řešení**: přepsat na `viz [NAVIGATION.md](NAVIGATION.md)`.
- **Čas**: ~2 min.

### 2. Bezpečnost

#### #3 SMTP hesla jako base64 (MEDIUM)

- **Co a kde**: `app/models/smtp_profile.py:18` — sloupec `smtp_password_b64` ukládá SMTP hesla jako base64. Funkce `encode_smtp_password()` / `decode_smtp_password()` v `app/utils.py:24-31` používají prostý `base64.b64encode()` / `b64decode()`. Kdokoli s přístupem k `data/svj.db` (záloha, USB přenos) může hesla okamžitě přečíst.
- **Řešení — varianty**:
  - **(a) Fernet šifrování** (`cryptography.Fernet`) s klíčem v `.env` — hesla v DB nečitelná bez klíče. Klíč se generuje při prvním spuštění. ~30 min.
  - **(b) Ponechat base64 + dokumentovat riziko** — pro lokální desktop aplikaci přijatelné, protože celý DB soubor je na stejném disku jako `.env` s heslem. ~5 min.
  - **(c) Systémový keyring** (`keyring` knihovna) — nejbezpečnější, ale platform-dependent. ~1 hod.
- **Doporučení**: Varianta (b) pro teď + komentář v kódu. Fernet (a) při nasazení na síti.
- **Regrese**: při (a) nutná migrace existujících hesel.

### 3. Kódová kvalita

#### #4 Chybějící indexy pro SmtpProfile (MEDIUM)

- **Co a kde**: `app/main.py:_ensure_indexes()` — model `SmtpProfile` má `index=True` na `is_default` (řádek 23 modelu), ale odpovídající `CREATE INDEX IF NOT EXISTS` chybí v `_ensure_indexes()`. Stejně tak FK sloupce `smtp_profile_id` přidané migrací na `tax_sessions` a `bank_statements` nemají indexy.
- **Řešení**: přidat 3 řádky do `_INDEXES`:
  ```python
  ("ix_smtp_profiles_is_default", "smtp_profiles", "is_default"),
  ("ix_tax_sessions_smtp_profile_id", "tax_sessions", "smtp_profile_id"),
  ("ix_bank_statements_smtp_profile_id", "bank_statements", "smtp_profile_id"),
  ```
- **Čas**: ~5 min.
- **Regrese**: nulové — `CREATE INDEX IF NOT EXISTS` je idempotentní.
- **Test**: restart serveru, ověřit v logu `Added index ix_smtp_profiles_is_default`.

#### #5 Duplicitní `qs()` Jinja macro (MEDIUM)

- **Co a kde**: `app/templates/voting/index.html:18` a `app/templates/payments/vypisy.html:8` — identický `qs()` macro pro sestavení query stringu. Zavedeno v commitu 2ea0a16 jako fix pro křehký `_back` pattern.
- **Řešení — varianty**:
  - **(a) Sdílený partial** `partials/_qs_macro.html` + `{% from "..." import qs %}` — čistší, ale Jinja2 `import` má omezení s request kontextem.
  - **(b) Jinja2 global function** registrovaná v `setup_jinja_filters()` v `app/utils.py` — nejčistší řešení.
  - **(c) Ponechat** — duplikát ve 2 souborech je akceptovatelný, dokud se nerozšíří dál.
- **Čas**: (a) ~10 min, (b) ~15 min.
- **Regrese**: nízké, ale potřeba otestovat obě stránky.

#### #7 `owner_update` generický název (LOW, přeneseno)

- **Co a kde**: `app/routers/owners/crud.py:725` — endpoint `owner_update` přijímá pouze kontaktní údaje (email, telefon), ale název naznačuje obecnou aktualizaci.
- **Řešení**: přejmenovat na `owner_update_contact`. Endpoint URL (`/{owner_id}/upravit`) se nemění.
- **Čas**: ~15 min (grep + rename funkce).
- **Regrese**: nízké — interní Python název, neovlivňuje URL.

### 4. UI / Šablony

#### #8 Emoji v bounces index.html bublinkách (LOW, přeneseno)

- **Co a kde**: `app/templates/bounces/index.html:79,84,89` — `🔴 Hard`, `🟡 Soft`, `⚪ Neznámé`. Commit a959ef3 opravil `_table.html` (badge v řádcích tabulky), ale bubliny v hlavičce stránky zůstaly s emoji.
- **Řešení**: nahradit emoji za SVG dots (stejný vzor jako v `_table.html`): `<span class="w-2 h-2 rounded-full bg-red-500 inline-block mr-1"></span>Hard`.
- **Čas**: ~5 min.
- **Test**: `/nastaveni` → sekce Bounces → ověřit že bubliny mají SVG tečky místo emoji.

#### #10 Terminologická nekonzistence Dluh vs Saldo (LOW)

- **Co a kde**: Commit `4efa6ab` přejmenoval „Dluh" na „Saldo" v platebních přehledech (`/platby/prehled`, `/platby/dluznici`). Ale starší sloupce v `/vlastnici` (řádek 195 `list.html`) a `/jednotky` (řádek 154 `list.html`) stále zobrazují „Dluh". Stejně tak `units/detail.html:25,27` zobrazuje badge „Dluh X Kč".
- **Řešení — varianty**:
  - **(a) Sjednotit na „Saldo" všude** — konzistentní, ale uživatelé zvyklí na „Dluh".
  - **(b) Ponechat „Dluh" v evidenci, „Saldo" v platbách** — v evidenci je kontextuálně jasnější, v platbách je saldo přesnější (může být kladné = přeplatek).
  - **(c) Přejmenovat na „Nedoplatek" v evidenci** — kontext nenaznačuje přeplatek.
- **Doporučení**: Varianta (b) — záměrný rozdíl dle kontextu. Přidat komentář do CLAUDE.md.
- **Čas**: ~15 min pro sjednocení, ~5 min pro dokumentaci varianty (b).

### 5. Výkon

Žádné nové výkonnostní problémy. Předchozí #1 (N^2 lookup) a #4 (match_name opakování) opraveny.

### 6. Error Handling

Bez nových nálezů. Globální handlery v `main.py` funkční. Nové SMTP endpointy mají `except Exception as e` s logováním a uživatelskou chybovou hláškou.

### 7. Git Hygiene

#### #6 Playwright remnants (MEDIUM)

- **Co a kde**: `.playwright-mcp/` obsahuje ~50 souborů z testování (console logy, page snapshoty YML, screenshoty PNG, Chrome extension CRX). Celkem ~9 MB.
- **Řešení**: `rm -rf .playwright-mcp/*.log .playwright-mcp/*.png .playwright-mcp/*.yml .playwright-mcp/*.crx` (per CLAUDE.md workflow pravidlo).
- **Čas**: ~1 min.
- **Poznámka**: Soubory nejsou v gitu (`.gitignore` je zachytává), ale zabírají disk a signalizují nedokončený úklid.

### 8. Testy

#### #9 Chybějící testy pro SmtpProfile (LOW)

- **Co a kde**: Nový model `SmtpProfile` + 15+ endpointů v `settings_page.py` (CRUD profilu, default toggle, test email, delete). Žádný testovací soubor `test_smtp_profile.py`. Nový model je kritický pro odesílání emailů (daně, nesrovnalosti).
- **Řešení**: vytvořit `tests/test_smtp_profile.py` s testy:
  - Vytvoření profilu + ověření base64 hesla
  - Default toggle (nastavení + odebrání)
  - Smazání posledního profilu (musí selhat s flash)
  - Password placeholder (••••••••) nesmí přepsat heslo
- **Čas**: ~45 min.
- **Regrese**: nulové — nové testy.

## Doporučený postup oprav

### Fáze 1 — okamžité (< 30 min)

1. **#1** Opravit 4 křížové odkazy v UI_GUIDE.md (15 min, HIGH)
2. **#6** Smazat `.playwright-mcp/` remnants (1 min, MEDIUM)
3. **#4** Přidat 3 chybějící indexy do `_ensure_indexes()` (5 min, MEDIUM)
4. **#2** Opravit deprecated TemplateResponse příklad v ROUTER_PATTERNS.md (5 min, MEDIUM)

### Fáze 2 — plánované (~75 min)

5. **#5** Deduplikovat `qs()` macro (10-15 min, vyžaduje rozhodnutí)
6. **#8** Emoji → SVG dots v bounces index.html (5 min)
7. **#9** Testy pro SmtpProfile (45 min)
8. **#11** Inline reference bez odkazu (2 min)

### Fáze 3 — nice-to-have / rozhodnutí

9. **#3** SMTP hesla base64 → šifrování (rozhodnutí: varianta a/b/c)
10. **#7** `owner_update` rename (breaking change bez přínosu, skip)
11. **#10** Dluh vs Saldo terminologie (rozhodnutí: varianta a/b/c)

## Celkový verdikt

**Projekt je ve výborném stavu.** Z 13 nálezů předchozího auditu bylo 10 opraveno do 24 hodin (commit 2ea0a16 + a959ef3). Kódová kvalita, bezpečnost i error handling jsou na dobré úrovni.

Hlavní problém tohoto auditu: **docs restructuring (b4563ce) zanechal 4 zlomené křížové odkazy** v UI_GUIDE.md — sekce přesunuté z CLAUDE.md do docs/ souborů, ale zpětné odkazy nebyly aktualizovány. Oprava je triviální (~15 min).

Nový model SmtpProfile je dobře implementovaný (migrace, seed, CRUD), ale chybí index v `_ensure_indexes()` a testovací pokrytí.

**Doporučení**: opravit #1 a #4 dnes (20 min), zbytek naplánovat. SMTP password šifrování (#3) konzultovat s uživatelem.
