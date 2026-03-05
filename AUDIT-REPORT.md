# SVJ Audit Report – 2026-03-05

## Souhrn
- **CRITICAL: 3**
- **HIGH: 7**
- **MEDIUM: 12**
- **LOW: 8**

**Celkem: 30 nálezů** (vs 42 v předchozím auditu 2026-03-03 — 12 opraveno, 0 nových kritických)

---

## Souhrnná tabulka

| # | Oblast | Soubor | Severity | Problém | Stav |
|---|--------|--------|----------|---------|------|
| 1 | Bezpečnost | celý projekt | CRITICAL | Žádná autentizace — 95 POST endpointů veřejných | Známý, plán v CLAUDE.md |
| 2 | Bezpečnost | celý projekt | CRITICAL | Žádná CSRF ochrana na POST formulářích | Známý, řešit s auth |
| 3 | Testy | celý projekt | CRITICAL | Žádné testy — nulové pokrytí | Známý |
| 4 | Kód | app/services/voting_import.py:33 | HIGH | Duplikát `_strip_diacritics()` — existuje v utils.py | NOVÝ |
| 5 | Kód | app/routers/voting.py (10×) | HIGH | Duplikát `has_processed = any(b.status.value == ...)` — 10 výskytů | NOVÝ |
| 6 | Bezpečnost | .env, settings_page.py | HIGH | SMTP heslo uloženo plaintext v .env | Známý |
| 7 | Error handling | app/routers/tax.py:694 | HIGH | PDF extrakce bez try/except — pád vlákna | Známý |
| 8 | Error handling | tax.py, owners.py | HIGH | Background thread chyby nelogované, uživatel dostane kryptickou hlášku | Známý |
| 9 | Error handling | všechny routery (28+×) | HIGH | `db.commit()` bez error handling — constraint violation = pád | Známý |
| 10 | Výkon | voting.py:696-850 | HIGH | Python-side filtrování lístků bez paginace — nebude škálovat | NOVÝ |
| 11 | Kód | voting.py (4×) | MEDIUM | Nekonzistentní timestamp: `datetime.now()` vs `datetime.utcnow()` | NOVÝ |
| 12 | Kód | voting.py (13×) | MEDIUM | `.status.value == "active"` místo enum porovnání | NOVÝ |
| 13 | Kód | voting.py:1555 řádků | MEDIUM | Příliš velký soubor — kandidát na rozdělení | Známý |
| 14 | Kód | voting_import.py:77 | MEDIUM | `import re` uvnitř funkce místo na úrovni modulu | NOVÝ |
| 15 | Bezpečnost | voting_import.py | MEDIUM | Import mapping JSON bez schema validace | NOVÝ |
| 16 | Bezpečnost | celý projekt | MEDIUM | Žádný rate limiting na endpointech | Známý |
| 17 | Bezpečnost | administration.py | MEDIUM | Zálohy bez šifrování (plaintext ZIP) | Známý |
| 18 | Error handling | 11 míst v routerech | MEDIUM | Tiché selhání file cleanup — `except: pass` bez logování | Známý |
| 19 | Error handling | backup_service.py, email_service.py | MEDIUM | File I/O bez error handling (disk full, permissions) | Známý |
| 20 | Error handling | owners.py, tax.py | MEDIUM | Žádná validace emailu před uložením do DB | Známý |
| 21 | Error handling | tax.py:2100 | MEDIUM | SMTP connection bez retry logiky | Známý |
| 22 | UI | ballots.html, detail.html, process.html | MEDIUM | Chybí explicitní `hx-swap="innerHTML"` na 3 search inputech | NOVÝ |
| 23 | Git | root projektu | MEDIUM | 6 binárních souborů (.png, .xlsx) v git historii | NOVÝ |
| 24 | Responsive | ballots.html | MEDIUM | Tabulka lístků přetéká na mobilech bez indikace | Známý |
| 25 | Kód | main.py:7 | LOW | Nepoužitý import `inspect` ze sqlalchemy | NOVÝ |
| 26 | Kód | voting.py:1042 | LOW | Hardcoded `vote_labels` dict — kandidát na konstantu | NOVÝ |
| 27 | Kód | voting.py:1006 | LOW | Lokální importy uvnitř funkce místo na úrovni modulu | NOVÝ |
| 28 | UI | ballot_detail.html, process_cards.html | LOW | Radio buttony bez explicitního `for`/`id` párování | Známý |
| 29 | UI | voting/index.html:156 | LOW | Chybí `aria-label` na DELETE modal inputu | Známý |
| 30 | Git | root projektu | LOW | 13 agent MD souborů v rootu — přesunout do docs/ | NOVÝ |

---

## Pozitivní nálezy (oproti minulému auditu)

| Oblast | Stav | Detail |
|--------|------|--------|
| SQL injection | SAFE | Všechny dotazy parametrizované přes SQLAlchemy ORM |
| XSS | SAFE | Jinja2 autoescape, `markupsafe.escape()` v Python HTML |
| Path traversal | SAFE | `is_safe_path()` s `resolve()` + `relative_to()` na všech download endpointech |
| Security headers | GOOD | X-Frame-Options, X-Content-Type-Options, Referrer-Policy |
| File upload | GOOD | Extension whitelist, size limit, safe filename construction |
| Custom error pages | GOOD | 404 + 500 s českými hláškami ve stylu aplikace |
| .env v .gitignore | GOOD | Citlivá data nejsou v repu |
| Debug mode | GOOD | `debug=False` jako default |

---

## Detailní nálezy

### 1. Kódová kvalita (7 nálezů)

**#4 Duplikát `_strip_diacritics`** (HIGH)
- `app/services/voting_import.py:33-35` definuje vlastní `_strip_diacritics()` — identická s `strip_diacritics()` v `app/utils.py:9-12`
- Fix: `from app.utils import strip_diacritics` a přejmenovat volání na řádku 278

**#5 Duplikát `has_processed`** (HIGH)
- `any(b.status.value == "processed" for b in voting.ballots)` se opakuje 10× v voting.py (řádky 50, 446, 727, 774, 861, 1297, 1381, 1408, 1485, 1545)
- Fix: Extrahovat do `_has_processed_ballots(voting)` helperu

**#11 Nekonzistentní timestamp** (MEDIUM)
- `datetime.now()` pro filenames (řádky 251, 304, 1087, 1424) vs `datetime.utcnow()` pro DB
- CLAUDE.md vyžaduje vždy `datetime.utcnow`

**#12 String vs enum porovnání** (MEDIUM)
- 13 výskytů `voting.status.value == "active"` místo `voting.status == VotingStatus.ACTIVE`

**#13 Velikost voting.py** (MEDIUM)
- 1555 řádků, 29 funkcí — kandidát na rozdělení (detail, ballots, import)

**#14 Late import** (MEDIUM)
- `import re` na řádku 77 uvnitř `_parse_value_list()` místo module-level

**#25-27 Drobnosti** (LOW)
- Nepoužitý `inspect` import v main.py, hardcoded `vote_labels`, lokální importy

### 2. Bezpečnost (7 nálezů)

**#1 Žádná autentizace** (CRITICAL) — 95 POST endpointů veřejných. Plán implementace v CLAUDE.md (role: admin, board, auditor, owner). Řešit jako poslední modul.

**#2 Žádná CSRF** (CRITICAL) — Žádné CSRF tokeny ve formulářích. Řešit společně s autentizací.

**#6 SMTP plaintext** (HIGH) — Heslo v `.env` bez šifrování. Přijatelné pro lokální deploy, řešit před cloud nasazením.

**#15 Import mapping bez validace** (MEDIUM) — JSON mapping z formuláře se parsuje bez schema validace. Přidat Pydantic model.

**#16 Žádný rate limiting** (MEDIUM) — Spam emailů/uploadů bez omezení. Řešit s autentizací.

**#17 Nešifrované zálohy** (MEDIUM) — ZIP bez hesla obsahuje celou DB. Přidat `pyminizip` šifrování.

### 3. Error handling (6 nálezů)

**#7 PDF extrakce** (HIGH) — `tax.py:694` volá `extract_owner_from_tax_pdf()` bez try/except. Pád vlákna = stuck processing.

**#8 Background thread chyby** (HIGH) — Chyby logované jen jako `str(e)` bez stack trace, uživatel dostane kryptickou hlášku.

**#9 `db.commit()` bez handling** (HIGH) — 28+ míst v routerech. Constraint violation = 500 error stránka.

**#18-21 Střední závažnost** (MEDIUM) — Tiché file cleanup, chybějící email validace, SMTP retry, file I/O handling.

### 4. UI / Šablony (3 nálezy)

**#22 Chybí `hx-swap`** (MEDIUM) — 3 search inputy bez explicitního `hx-swap="innerHTML"`. Funkční ale nejasné.

**#24 Responsive tabulky** (MEDIUM) — Tabulka lístků přetéká na mobilech.

**#28-29 Přístupnost** (LOW) — Radio buttony bez for/id, chybí aria-label na DELETE inputu.

### 5. Výkon (1 nález)

**#10 Python-side filtrování** (HIGH) — Lístky se filtrují a řadí v Pythonu po načtení VŠECH z DB. Pro 200+ lístků = pomalé. Řešení: přesunout filtrování do SQL, přidat paginaci.

### 6. Git (2 nálezy)

**#23 Binární soubory** (MEDIUM) — 5 PNG screenshotů + 1 XLSX v repu. Odebrat z gitu.

**#30 Agent soubory** (LOW) — 13 agent MD souborů v rootu. Přesunout do `docs/agents/`.

### 7. Testy (1 nález)

**#3 Nulové pokrytí** (CRITICAL) — Žádné testy. `pytest` v dev závislostech ale nevyužitý. Kritické pro refaktoring a údržbu.

---

## Srovnání s předchozím auditem (2026-03-03)

| Metrika | 2026-03-03 | 2026-03-05 | Změna |
|---------|------------|------------|-------|
| CRITICAL | 3 | 3 | = (stejné) |
| HIGH | 7 | 7 | = (2 nové, 2 opravené) |
| MEDIUM | 18 | 12 | -6 (opraveno) |
| LOW | 14 | 8 | -6 (opraveno) |
| **Celkem** | **42** | **30** | **-12** |

**Opraveno od minulého auditu:**
- Zip Slip zranitelnost (backup restore)
- Přístupnost: label/aria na formulářích (částečně)
- UI konzistence: sort hlavičky, badge styly
- Výkonnostní problémy: eager loading relací

**Nově nalezeno:**
- Duplikát `_strip_diacritics` (nový kód)
- Duplikát `has_processed` pattern (rozrostl se)
- Import mapping bez validace (nová funkce)
- Python-side filtrování lístků (nová funkce)

---

## Doporučený postup oprav

### Okamžitě (před dalším vývojem)
1. **#4** Import `strip_diacritics` z utils — 5 min
2. **#5** Extrahovat `_has_processed_ballots()` helper — 15 min
3. **#11** Sjednotit na `datetime.utcnow()` — 10 min
4. **#14** Přesunout `import re` na úroveň modulu — 2 min
5. **#25** Odstranit nepoužitý `inspect` import — 2 min

### Krátkodobě (tento sprint)
6. **#7** Try/except na PDF extrakci — 15 min
7. **#8** Logování chyb v background threadech — 30 min
8. **#22** Přidat `hx-swap="innerHTML"` — 5 min
9. **#15** Pydantic schema pro import mapping — 1 hod
10. **#23** Odstranit binární soubory z gitu — 10 min

### Střednědobě (další iterace)
11. **#10** SQL filtrování + paginace lístků — 2-4 hod
12. **#12** Enum porovnání místo string — 30 min
13. **#3** Základní test suite (import, PDF, backup) — 1-2 dny

### Až před nasazením
14. **#1 + #2** Autentizace + CSRF — 2-3 dny
15. **#6** Šifrování SMTP hesla — 2 hod
16. **#17** Šifrování záloh — 4 hod
