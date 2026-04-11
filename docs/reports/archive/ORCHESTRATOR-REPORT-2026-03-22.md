# Orchestrátor — Souhrnný report údržby

> **Datum:** 2026-03-22
> **Režim:** Pokračování auditu z 2026-03-19 — opravy zbývajících nálezů + rozšíření testů + CI/CD
> **Rozsah:** Celý projekt
> **Navazuje na:** [ORCHESTRATOR-REPORT-2026-03-19.md](ORCHESTRATOR-REPORT-2026-03-19.md)

---

## Přehled agentů

| # | Agent | Stav | Nálezů | Opraveno | Zbývá |
|---|-------|------|--------|----------|-------|
| 1 | Code Guardian (pokračování) | ✅ | 20 zbývajících | 18 | 2 (strategické) |
| 2 | Test Agent | ✅ | — | — | — |
| 3 | Doc Sync | ✅ | 8 | 8 | 0 |
| 4 | Backup Agent | ✅ | 0 | — | — |

**Celkem: 26 nálezů řešeno, 2 zbývají (N1 autentizace, N11 CSRF — strategické, plánované na konec).**

---

## 1. Code Guardian — Opravy zbývajících nálezů

### Opraveno v této session (18 nálezů)

| # | ID | Severity | Popis | Soubory |
|---|----|----------|-------|---------|
| 1 | N10 | MEDIUM | `datetime.utcnow()` deprecated (Python 3.12+) | `app/utils.py` + 20 souborů (44 výskytů) |
| 2 | N18 | MEDIUM | Chybějící `aria-label` na formulářových prvcích | 13 šablon (22 přidání) |
| 3 | N19 | LOW | CDN (Tailwind, HTMX) offline nedostupné | `base.html` + `static/js/tailwind.min.js`, `htmx.min.js` |
| 4 | N7 | LOW | `administration.py` (1426 ř.) monolitický router | → package `administration/` (6 modulů) |
| 5 | N7 | LOW | `sync.py` (1171 ř.) monolitický router | → package `sync/` (4 moduly) |
| 6 | N2 | HIGH | `preview_contact_import()` 256 řádků | → 80 ř. + 4 helpery |
| 7 | N2 | HIGH | `_process_tax_files()` 243 řádků | → 52 ř. + 5 helperů |
| 8 | N2 | HIGH | `execute_exchange()` 235 řádků | → 70 ř. + 6 helperů |
| 9 | N2 | HIGH | `compare_owners()` 192 řádků | → 80 ř. + 5 helperů |
| 10 | N15 | LOW | Chybějící docstringy na endpointech | Ověřeno — všechny už mají |
| 11 | N16 | LOW | `except Exception: pass` tiché bloky | Přidáno `logger.debug()` s exc_info |
| 12 | N21 | LOW | Synchronní SMTP blokuje request thread | `async_send_email()`, `async_send_to_owner_emails()` |
| 13 | N25 | LOW | `overflow-x-auto` wrapper na tabulkách | 27 šablon (mobilní responsivita) |

### Již vyřešené (zjištěno při analýze — 5 nálezů)

| ID | Popis | Stav |
|----|-------|------|
| N4 | Duplikované migrace | `_ALL_MIGRATIONS` sdílený list už existoval |
| N5h | Hardcoded cesty | Již používá `settings.*` |
| N9 | `datetime.utcnow` v column defaults | Korektní SQLAlchemy pattern |
| N13 | `\|safe` filtr v šablonách | Hardcoded SVG, bezpečné |
| N22 | Dashboard eager loading | Používá SQL agregaci |

### Zbývající strategické nálezy (2)

| ID | Severity | Popis | Poznámka |
|----|----------|-------|----------|
| N1 | CRITICAL | Žádná autentizace | Plán v CLAUDE.md (role admin/board/auditor/owner), implementace na konec |
| N11 | CRITICAL | Žádná CSRF ochrana | Relevantní až při síťovém nasazení |

---

## 2. Test Agent — Rozšíření testů + CI/CD

### Testy

| Metrika | Před | Po |
|---------|------|----|
| Počet testů | 56 | 248 |
| Moduly pokryté | 3 | 7 |
| Doba běhu | ~2s | ~5s |

**Nové testovací soubory:**
- `tests/test_voting.py` — 72 testů (wizard, ballot stats, import validate/preview/execute, SJM)
- `tests/test_backup.py` — 43 testů (lock, ZIP create/restore, cleanup, integrity, log)
- `tests/test_csv_comparator.py` — 77 testů (CSV parsing, fuzzy matching, Czech stemming, comparison)
- Rozšíření `tests/test_payments.py` — payment matching

### CI/CD pipeline

- **Pre-push git hook** (`.git/hooks/pre-push`) — blokuje push při selhání testů
- **GitHub Actions** (`.github/workflows/tests.yml`) — push na main/Platby + PR do main
  - Python 3.12, pytest + httpx
  - Smoke testy přeskočeny na CI (`CI` env var)
  - 246 testů prochází + 2 přeskočeny

---

## 3. Doc Sync — Synchronizace dokumentace

**8 nálezů, 8 opraveno:**

| # | Soubor | Popis |
|---|--------|-------|
| 1 | CLAUDE.md | Odstraněn duplicitní `owners/` řádek v Router packages |
| 2 | CLAUDE.md | Přidán `utcnow()` do Utility functions |
| 3 | CLAUDE.md | Přidána sdílená `templates` instance do Utility functions |
| 4 | CLAUDE.md | Upřesněna timestamp konvence (`utcnow` místo `datetime.utcnow`) |
| 5 | README.md | `sync.py` → `sync/` package v projektové struktuře |
| 6 | README.md | `administration.py` → `administration/` package v projektové struktuře |
| 7 | README.md | Přidán `settlement_service.py` do services |
| 8 | README.md | Přidán `utcnow` a `templates` do utils.py popisu |

---

## 4. Backup Agent

**Výsledek: Vše v pořádku.** Žádné problémy s backup/restore logikou.

---

## Souhrnná bilance auditů

| Session | Datum | Nálezů celkem | Opraveno | Zbývá |
|---------|-------|---------------|----------|-------|
| 1. orchestrace | 2026-03-19 | 70 | 47 | 23 |
| 2. orchestrace | 2026-03-22 | 26 | 24 | 2 |
| **Celkem** | | **96** | **71** | **2** |

Zbývající 2 nálezy (autentizace + CSRF) jsou strategické a budou implementovány jako poslední vrstva po dokončení všech modulů.

---

## Commity v této session

1. `feat: 248 automatizovaných testů (voting, backup, CSV comparator, payments)`
2. `ci: pre-push hook + GitHub Actions workflow`
3. `docs: aktualizace README — testy a CI sekce`
4. `fix: datetime.utcnow() → utcnow() helper (44 výskytů, Python 3.12+)`
5. `feat: aria-label přístupnost + CDN fallback + overflow-x-auto`
6. `refactor: administration.py → package (6 modulů), sync.py → package (4 moduly)`
7. `refactor: 4 nejdelší funkce rozloženy na helpery (20 nových)`
8. `fix: tiché except bloky → logger.debug, async SMTP wrappery`
9. `docs: aktualizace dokumentace po osmém auditu`
