# SVJ Audit Report – 2026-03-08

## Souhrn
- **CRITICAL: 3**
- **HIGH: 8**
- **MEDIUM: 14**
- **LOW: 8**

**Celkem: 33 nálezů** (vs 30 v předchozím auditu 2026-03-05 — nové nálezy z exportů a rozesílky)

---

## Souhrnná tabulka

| # | Oblast | Soubor | Severity | Problém | Stav |
|---|--------|--------|----------|---------|------|
| 1 | Bezpečnost | celý projekt | CRITICAL | Žádná autentizace — 95+ POST endpointů veřejných | Známý, plán v CLAUDE.md |
| 2 | Bezpečnost | celý projekt | CRITICAL | Žádná CSRF ochrana na POST formulářích | Známý, řešit s auth |
| 3 | Testy | celý projekt | CRITICAL | Žádné testy — nulové pokrytí | Známý |
| 4 | Kód | owners.py, units.py, voting_import.py | HIGH | Duplikát `_strip_diacritics()` — existuje v utils.py (3 soubory) | Rozšířen |
| 5 | Kód | app/routers/voting.py (10×) | HIGH | Duplikát `has_processed = any(b.status.value == ...)` — 10 výskytů | Známý |
| 6 | Bezpečnost | .env, settings_page.py | HIGH | SMTP heslo uloženo plaintext v .env | Známý |
| 7 | Error handling | app/routers/tax.py:694 | HIGH | PDF extrakce bez try/except — pád vlákna | Známý |
| 8 | Error handling | tax.py, owners.py | HIGH | Background thread chyby nelogované, uživatel dostane kryptickou hlášku | Známý |
| 9 | Error handling | všechny routery (28+×) | HIGH | `db.commit()` bez error handling — constraint violation = pád | Známý |
| 10 | Výkon | voting.py:696-850 | HIGH | Python-side filtrování lístků bez paginace | Známý |
| 11 | Kód | tax.py (2522 řádků) | HIGH | Největší soubor — obtížná údržba, kandidát na rozdělení | NOVÝ |
| 12 | Bezpečnost | owners.py:557 | HIGH | Path traversal v contact_import_rerun — chybí `is_safe_path()` | NOVÝ |
| 13 | Kód | 7 souborů | MEDIUM | Duplicitní Excel auto-width pattern — 7 kopií stejného kódu | NOVÝ |
| 14 | Kód | voting.py (4×) | MEDIUM | Nekonzistentní timestamp: `datetime.now()` vs `datetime.utcnow()` | Známý |
| 15 | Kód | voting.py (13×) | MEDIUM | `.status.value == "active"` místo enum porovnání | Známý |
| 16 | Kód | voting.py:1555 řádků | MEDIUM | Druhý největší soubor — kandidát na rozdělení | Známý |
| 17 | Kód | voting_import.py:77 | MEDIUM | `import re` uvnitř funkce místo na úrovni modulu | Známý |
| 18 | Bezpečnost | voting_import.py | MEDIUM | Import mapping JSON bez schema validace | Známý |
| 19 | Bezpečnost | celý projekt | MEDIUM | Žádný rate limiting na endpointech | Známý |
| 20 | Bezpečnost | administration.py | MEDIUM | Zálohy bez šifrování (plaintext ZIP) | Známý |
| 21 | Error handling | 11 míst v routerech | MEDIUM | Tiché selhání file cleanup — `except: pass` bez logování | Známý |
| 22 | Error handling | owners.py, tax.py | MEDIUM | Žádná validace emailu před uložením do DB | Známý |
| 23 | Error handling | tax.py:2100 | MEDIUM | SMTP connection bez retry logiky | Známý |
| 24 | Error handling | několik routerů | MEDIUM | `date.fromisoformat()` bez try/except — nevalidní datum = 500 | Známý |
| 25 | UI | ~30 tabulek | MEDIUM | Nekonzistentní thead styly (border, sticky) | NOVÝ |
| 26 | UI | různé šablony | MEDIUM | 4 různé styly flash zpráv | NOVÝ |
| 27 | Výkon | tax.py email log | MEDIUM | Email log search načítá všechny záznamy, filtruje v Pythonu | NOVÝ |
| 28 | UI | ballots.html, detail.html | MEDIUM | Chybí explicitní `hx-swap="innerHTML"` na search inputech | Známý |
| 29 | Kód | main.py:7 | LOW | Nepoužitý import `inspect` ze sqlalchemy | Známý |
| 30 | Kód | 12 souborů | LOW | Nepoužívané importy (HTTPException, Optional, List) | NOVÝ |
| 31 | Kód | tax.py | LOW | Logger definován uprostřed souboru místo za importy | NOVÝ |
| 32 | UI | různé šablony | LOW | Nekonzistentní date formatting, border-radius, padding | Známý |
| 33 | Git | root projektu | LOW | 13 agent MD souborů v rootu — přesunout do docs/ | Známý |

---

## Pozitivní nálezy

| Oblast | Stav | Detail |
|--------|------|--------|
| SQL injection | SAFE | Všechny dotazy parametrizované přes SQLAlchemy ORM |
| XSS | SAFE | Jinja2 autoescape, `markupsafe.escape()` v Python HTML |
| Path traversal | SAFE | `is_safe_path()` na download endpointech (kromě #12) |
| Security headers | GOOD | X-Frame-Options, X-Content-Type-Options, Referrer-Policy |
| File upload | GOOD | Extension whitelist, size limit, safe filename construction |
| Custom error pages | GOOD | 404 + 500 s českými hláškami |
| .env v .gitignore | GOOD | Citlivá data nejsou v repu |
| Export filtrování | GOOD | Nové export endpointy správně přenáší filtry (owners, units) |
| Refaktored filter logic | GOOD | `_filter_owners()` a `_filter_units()` extrahované — DRY pattern |

---

## Srovnání s předchozím auditem (2026-03-05)

| Metrika | 2026-03-05 | 2026-03-08 | Změna |
|---------|------------|------------|-------|
| CRITICAL | 3 | 3 | = (stejné) |
| HIGH | 7 | 8 | +1 (tax.py velikost, path traversal) |
| MEDIUM | 12 | 14 | +2 (Excel duplikát, UI konzistence) |
| LOW | 8 | 8 | = |
| **Celkem** | **30** | **33** | **+3** |

**Nově nalezeno (2026-03-08):**
- #11: tax.py narostl na 2522 řádků (nový HIGH)
- #12: Path traversal v contact_import_rerun (nový HIGH)
- #13: Excel auto-width pattern duplicated 7× (nový MEDIUM)
- #25: Nekonzistentní thead styly ~30 tabulek (nový MEDIUM)
- #26: 4 různé flash message styly (nový MEDIUM)
- #27: Email log search — full table scan (nový MEDIUM)
- #30: 12 unused imports (nový LOW)
- #31: Logger misplaced v tax.py (nový LOW)
- #4: Duplikát `_strip_diacritics` rozšířen o owners.py a units.py (nové soubory)

**Z předchozího auditu opraveno:**
- Binární soubory v gitu (odstraněno)
- Radio buttony bez for/id (opraveno)
- Responsive tabulky (zlepšeno)

---

## Doporučený postup oprav

### Okamžitě (bezpečnost)
1. **#12** Path traversal v contact_import_rerun — přidat `is_safe_path()` validaci — 5 min

### Krátkodobě (kvalita kódu)
2. **#4** Import `strip_diacritics` z utils (3 soubory) — 5 min
3. **#13** Extrahovat Excel auto-width helper do utils.py — 15 min
4. **#30** Vyčistit unused imports — 10 min
5. **#31** Přesunout logger v tax.py — 2 min
6. **#5** Extrahovat `_has_processed_ballots()` — 15 min
7. **#14** Sjednotit na `datetime.utcnow()` — 10 min

### Střednědobě (robustnost)
8. **#7** Try/except na PDF extrakci — 15 min
9. **#8** Logování chyb v background threadech — 30 min
10. **#24** Ošetřit `date.fromisoformat()` — 15 min
11. **#27** SQL filtrování email logů — 30 min
12. **#25** Sjednotit thead styly — 1 hod
13. **#26** Sjednotit flash message partial — 30 min

### Dlouhodobě (architektura)
14. **#11** Rozdělit tax.py na menší moduly — 2+ hod
15. **#16** Rozdělit voting.py — 2+ hod
16. **#10** SQL filtrování + paginace lístků — 2-4 hod
17. **#3** Základní test suite — 1-2 dny
18. **#1 + #2** Autentizace + CSRF — 2-3 dny (plán v CLAUDE.md)
