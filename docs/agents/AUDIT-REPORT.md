# SVJ Audit Report – 2026-03-08 (post-refaktor)

## Souhrn
- **CRITICAL: 4** (3 známé + 1 nový)
- **HIGH: 4**
- **MEDIUM: 8**
- **LOW: 10**

**Celkem: 26 nálezů** (po opravě 20/33 z předchozího auditu)

---

## Souhrnná tabulka

| # | Oblast | Soubor | Severity | Problém | Stav |
|---|--------|--------|----------|---------|------|
| 1 | Bezpečnost | celý projekt | CRITICAL | Žádná autentizace | Známý, plán v CLAUDE.md |
| 2 | Bezpečnost | celý projekt | CRITICAL | Žádná CSRF ochrana | Známý, řešit s auth |
| 3 | Testy | celý projekt | CRITICAL | Žádné testy | Známý |
| 4 | Bezpečnost | administration.py:770 | CRITICAL | Path traversal v backup restore | **NOVÝ** |
| 5 | Výkon | tax/sending.py:232 | HIGH | N+1 query v loop (TaxDistribution) | **NOVÝ** |
| 6 | Konfigurace | 12 souborů | HIGH | Hardcoded upload size limits (50/100/200 MB) | **NOVÝ** |
| 7 | Dokumentace | README.md:385 | HIGH | Adresářový strom neodráží voting/ a tax/ packages | **NOVÝ** |
| 8 | Bezpečnost | email_service.py:66 | HIGH | File attachment read bez error handling | **NOVÝ** |
| 9 | Duplikáty | excel_import:163, contact_import:72 | MEDIUM | Duplicitní `_build_name_*()` funkce | **NOVÝ** |
| 10 | Konfigurace | main.py:494 | MEDIUM | Hardcoded multipart limits (5000) | **NOVÝ** |
| 11 | Dokumentace | CLAUDE.md | MEDIUM | Chybí dokumentace router package vzoru | **NOVÝ** |
| 12 | Git | .gitignore | MEDIUM | Chybí `.playwright-mcp/` a `data/svj.db*` | **NOVÝ** |
| 13 | Robustnost | tax/_helpers.py:137 | MEDIUM | int() cast bez try/except | **NOVÝ** |
| 14 | Robustnost | sync.py:174 | MEDIUM | File read jen UnicodeDecodeError, ne IOError | **NOVÝ** |
| 15 | Struktura | tax/sending.py:629 | MEDIUM | Funkce `_send_emails_batch()` 132 řádků | **NOVÝ** |
| 16 | Bezpečnost | config.py:7 | MEDIUM | Debug mode bez produkční ochrany | Existující |
| 17 | Pojmenování | voting/_helpers.py:28 | LOW | `_has_processed_ballots` — spíš model metoda | Info |
| 18 | Duplikáty | voting/_helpers, tax/_helpers | LOW | Paralelní wizard patterns | Info |
| 19 | Styl | owners.py:374 | LOW | Inline import (csv, io) | Info |
| 20 | Závislosti | owner_matcher.py:10 | LOW | Nepoužitý import unidecode | **NOVÝ** |
| 21 | Konfigurace | settings_page.py:82 | LOW | Hardcoded pagination limit | Info |
| 22 | Konfigurace | tax/_helpers.py:53 | LOW | Hardcoded wizard labels | Info |
| 23 | Git | .gitignore | LOW | SQLite WAL soubory (db-shm, db-wal) | **NOVÝ** |
| 24 | Git | root | LOW | PNG screenshoty v rootu (ignorované) | Info |
| 25 | Dokumentace | CLAUDE.md | LOW | Chybí TOC | Info |
| 26 | Testy | celý projekt | LOW | Chybí pytest.ini, CI/CD workflow | Info |

---

## Detailní nálezy

### CRITICAL

#### #4: Path traversal v backup restore
**Soubor:** `app/routers/administration.py:770-781`
**Popis:** Při obnově zálohy ze složky (webkitdirectory upload) se názvy souborů z uploadu používají bez validace cesty. Útočník může nahrát soubor s názvem `../../../data/uploads/shell.py` a zapsat mimo temp adresář.
**Doporučení:** Přidat validaci `is_safe_path(target, Path(tmp))` před zápisem, nebo `if ".." in rel: continue`.

### HIGH

#### #5: N+1 query v tax/sending.py
**Soubor:** `app/routers/tax/sending.py:232`
**Popis:** V loop přes `all_docs` se pro každý dokument dělá `db.query(TaxDistribution).filter_by(document_id=doc.id).all()` — klasický N+1 problém.
**Doporučení:** `all_docs = db.query(TaxDocument).filter_by(...).options(joinedload(TaxDocument.distributions)).all()`

#### #6: Hardcoded upload size limits
**Soubor:** 12 míst v routerech
**Popis:** `max_size_mb=50/100/200` rozptýleno po routerech. Změna politiky vyžaduje editaci 12 souborů.
**Doporučení:** Přesunout do `app/config.py` jako `UPLOAD_LIMITS` dict.

#### #7: README directory tree zastaralý
**Soubor:** `README.md:385-394`
**Popis:** Zobrazuje `voting.py` a `tax.py` jako single files, ale oba jsou nyní packages.
**Doporučení:** Aktualizovat adresářový strom.

#### #8: File attachment bez error handling
**Soubor:** `app/services/email_service.py:66`
**Popis:** `open(path, "rb")` v loop bez try/except. Pokud soubor zmizí mezi existence check a čtením, padne celá operace.
**Doporučení:** Wrapit v `try/except (IOError, OSError)` s `logger.warning` a `continue`.

### MEDIUM

#### #9-#16: Viz souhrnná tabulka

### LOW

#### #17-#26: Viz souhrnná tabulka

---

## Pozitivní nálezy

- ✅ Žádné SQL injection (ORM konzistentně)
- ✅ Žádné bare `except:` bez logování (opraveno v předchozím auditu)
- ✅ Kompletní databázové indexy (38 indexů v `_ensure_indexes()`)
- ✅ Správné joinedload v hlavních list endpointech
- ✅ Custom error stránky (404, 500, 409)
- ✅ Konzistentní snake_case, české URL
- ✅ Autoescaping v Jinja2 šablonách
- ✅ HTTP security headers (X-Frame-Options, X-Content-Type-Options, Referrer-Policy)
- ✅ Verze závislostí pinnuté v pyproject.toml
- ✅ Žádné TODO/FIXME/HACK komentáře

---

## Doporučený postup oprav

### Fáze 1 — Kritické (hned)
1. **#4** Path traversal v backup restore — bezpečnostní díra
2. **#12** Přidat .playwright-mcp/ a data/svj.db* do .gitignore
3. **#7** README aktualizovat directory tree

### Fáze 2 — Důležité
4. **#5** N+1 fix v tax/sending.py
5. **#8** Error handling v email_service.py
6. **#13** try/except na int() cast
7. **#14** Broader exception v sync.py file read

### Fáze 3 — Údržba
8. **#6** Upload limits do config.py
9. **#9** Konsolidace `_build_name_*` funkcí
10. **#11** Dokumentovat router package vzor v CLAUDE.md
11. **#20** Odstranit nepoužitý unidecode import
