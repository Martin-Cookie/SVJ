# Orchestrátor Report — 2026-04-05

> Kompletní průchod celým projektem (6 agentů)

## Souhrn agentů

| # | Agent | Stav | Klíčové nálezy |
|---|-------|------|----------------|
| 1 | Code Guardian | Dokončen | 0 CRITICAL, 2 HIGH, 6 MEDIUM, 5 LOW (8/11 předchozích opraveno) |
| 2 | Doc Sync | Dokončen (analýza) | CLAUDE.md: 2 zastaralé + 5 chybějících, UI_GUIDE: 1+3+2 duplikáty, README: 4 chybějící |
| 3 | Test Agent | Dokončen | PASS — 298 pytest OK, 9/9 smoke, 5/5 funkční, exporty OK, back URL OK, N+1 OK |
| 4 | UX Optimizer | Dokončen | 6 kritických, 23 důležitých, 15 drobných (44 celkem) |
| 5 | Backup Agent | Dokončen | 0 HIGH (vše opraveno od minula), 8 LOW |
| 6 | Business Logic | Dokončen | Aktualizováno: +nesrovnalosti, sdílené odesílání, prostory/nájemci, zůstatky |

---

## Porovnání s předchozím reportem (2026-03-27)

| Oblast | Minule | Teď | Trend |
|--------|--------|-----|-------|
| Code Guardian HIGH+ | 1 HIGH | 2 HIGH (jiné) | ~ nové v novém kódu |
| Backup HIGH+ | 1 HIGH | 0 HIGH | ↑ opraveno |
| Testy | 248 passed | 298 passed | ↑ +50 testů |
| UX kritické | 4 | 6 | ~ nové moduly |
| Doc Sync | 12 úprav CLAUDE, 6 README | 7 CLAUDE, 6 UI_GUIDE, 4 README | ~ průběžné |

---

## Konsolidovaná tabulka — HIGH+ nálezy

| # | Zdroj | Nález | Severity | Čas | Rozhodnutí |
|---|-------|-------|----------|-----|------------|
| A1 | Audit N1 | `_count_debtors_fast` a `compute_debt_map` 90% duplicitní (130ř copy-paste) | HIGH | ~30 min | 🔧 |
| A2 | Audit N2 | `statements.py` 1653 řádků — nesrovnalosti (586ř) do samostatného `discrepancies.py` | HIGH | ~30 min | 🔧 |
| U1 | UX #1 | Dashboard zahlcený payment_notice emaily (1446 záznamů) | KRITICKÉ | ~1 hod | ❓ |
| U2 | UX #2 | Vyúčtování — všechny položky ukazují přeplatek (podezřelá logika) | KRITICKÉ | ~1 hod | 🔧 |
| U3 | UX #3 | Matice plateb — 9 prázdných měsíců zabírá místo | KRITICKÉ | ~2 hod | ❓ |
| U4 | UX #4 | Nájemci — duplicitní řádky pro propojené nájemce (31 místo ~20) | KRITICKÉ | ~30 min | 🔧 |
| U5 | UX #5 | Sidebar nemá mobilní verzi | KRITICKÉ | ~2 hod | ❓ |
| U6 | UX #6 | Chybějící audit trail | KRITICKÉ | ~4 hod | ❓ |

---

## Doc Sync — navržené úpravy (17 celkem)

### CLAUDE.md (7 úprav)
- ř. 298: Přidat upload podadresář `contracts/`
- ř. 384: Opravit počet migračních funkcí z 12 na 14
- Přidat `render_email_template()` do sekce Utility funkce
- Přidat zmínku o `payment_discrepancy.py` service (dataclass Discrepancy vzor)
- Přidat sdílená odesílací nastavení SvjInfo (send_batch_size atd.)
- Přidat `Payment.notified_at` sloupec
- Přidat `contracts/` upload podadresář

### UI_GUIDE.md (6 úprav)
- § 14: Nahradit přímý header přístup odkazem na `is_htmx_partial()`
- Přidat sekci o sdíleném progress bar partialu
- Přidat zmínku o nesrovnalosti layoutu
- Ověřit flash_type="info" variantu
- Deduplikovat HTMX partial popis (odkaz na CLAUDE.md)
- Deduplikovat back URL scroll popis

### README.md (4 úpravy)
- Přidat endpoint `POST /platby/vypisy/{id}/nesrovnalosti/nastaveni`
- Přidat `Payment.notified_at` do datového modelu
- Přidat SvjInfo send_* sloupce do datového modelu
- Přidat `render_email_template` do utils popisu

---

## Detailní reporty

| Report | Soubor |
|--------|--------|
| Code Guardian | `AUDIT-REPORT.md` |
| Test Agent | `TEST-REPORT.md` |
| UX Optimizer | `UX-REPORT.md` |
| Backup Agent | `BACKUP-REPORT.md` |
| Business Logic | `docs/BUSINESS-LOGIC.md` + `docs/BUSINESS-SUMMARY.md` |

---

## Doporučené další kroky

### Etapa 1 — Kód (HIGH, ~1 hod)
1. Refaktor `_count_debtors_fast` + `compute_debt_map` — sloučit do jedné funkce
2. Extrahovat nesrovnalosti z `statements.py` do `discrepancies.py`

### Etapa 2 — Dokumentace (~30 min)
3. Provést 17 Doc Sync úprav (CLAUDE.md, UI_GUIDE.md, README.md)

### Etapa 3 — UX quick wins (~100 min)
4. Dashboard — filtrovat/seskupit payment_notice emaily
5. Nájemci — deduplikovat propojené řádky
6. Matice plateb — skrýt prázdné měsíce
7. Vyúčtování — ověřit výpočetní logiku přeplatků

### Etapa 4 — UX velké změny (volitelné, ~8 hod)
8. Mobilní sidebar
9. Audit trail
