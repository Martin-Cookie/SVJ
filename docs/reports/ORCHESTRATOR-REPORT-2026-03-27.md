# Orchestrátor Report — 2026-03-27

> Kompletní průchod celým projektem (6 agentů)

## Souhrn agentů

| # | Agent | Stav | Klíčové nálezy |
|---|-------|------|----------------|
| 1 | Code Guardian | Dokončen | 0 CRITICAL, 1 HIGH, 5 MEDIUM, 5 LOW (9/13 předchozích opraveno) |
| 2 | Doc Sync | Dokončen (analýza) | CLAUDE.md: 5 zastaralých + 7 chybějících, README: 4 zastaralých + 2 chybějících |
| 3 | Test Agent | Dokončen | PASS — 248 pytest OK, 9/9 smoke, exporty OK, back URL OK |
| 4 | UX Optimizer | Dokončen | 4 kritické, 17 důležité, 14 drobné (34 celkem) |
| 5 | Backup Agent | Dokončen | 1 HIGH (engine.dispose), 2 MEDIUM, 5 LOW, 2 předchozí HIGH opraveny |
| 6 | Business Logic | Dokončen | Aktualizováno: +130 řádků (platby, prostory, nájemci, 13 payment modelů) |

---

## Konsolidovaná tabulka všech nálezů

### CRITICAL / HIGH priority

| # | Zdroj | Nález | Severity | Čas | Rozhodnutí |
|---|-------|-------|----------|-----|------------|
| A1 | Audit N1 | SMTP SSL logika duplikována v settings_page.py | HIGH | ~5 min | 🔧 |
| A2 | Backup #1 | engine.dispose() chybí před ZIP/složka restore | HIGH | ~5 min | 🔧 |
| U1 | UX #16 | Matice plateb — tabulka nekonečně široká (prázdné měsíce) | KRITICKÉ | ~2 hod | ❓ |
| U2 | UX #26 | Sidebar nemá mobilní verzi | KRITICKÉ | ~2 hod | ❓ |
| U3 | UX #19 | Vyúčtování — podezřelá data (vše přeplatky) | KRITICKÉ | ~1 hod | 🔧 |
| U4 | UX #1 | Dashboard zaplavený chybami rozesílky | KRITICKÉ/DŮLEŽITÉ | ~1 hod | ❓ |

### MEDIUM / DŮLEŽITÉ priority

| # | Zdroj | Nález | Čas | Rozhodnutí |
|---|-------|-------|-----|------------|
| A3 | Audit N5 | datetime.utcnow deprecated v 7 modelech | ~15 min | 🔧 |
| A4 | Audit N6 | datetime.utcnow() v dashboard.py | ~1 min | 🔧 |
| A5 | Audit N4 | Temp form nepřenáší hidden fields při polling | ~15 min | 🔧 |
| A6 | Audit N2 | Logger placement v email_service.py | ~2 min | 🔧 |
| A7 | Audit N3 | Return type annotation _create_smtp | ~2 min | 🔧 |
| B1 | Backup #3 | WAL checkpoint warning nepropagován uživateli | ~15 min | 🔧 |
| B2 | Backup #4 | Auto-cleanup může smazat důležité zálohy | ~20 min | 🔧 |
| U5 | UX #6 | Nájemci — duplicitní řádky pro propojené nájemce | ~1 hod | ❓ |
| U6 | UX #8 | Nájemci detail — nezobrazuje skutečný pronájem | ~30 min | 🔧 |
| U7 | UX #5 | Detail vlastníka — chybí celkový dluh za všechny jednotky | ~30 min | 🔧 |
| U8 | UX #14 | Rozesílka — 597 řádků bez filtrovacích bublin | ~20 min | 🔧 |
| U9 | UX #28 | HTMX search — chybí loading indikátor | ~30 min | 🔧 |
| U10 | UX #24 | Hromadné úpravy — chybí náhled změn | ~45 min | 🔧 |
| U11 | UX #12 | Hlasování — patičkový text v bodu hlasování | ~10 min | 🔧 |
| U12 | UX #13 | Rozesílka — pozastavená bez výrazného vizuálu | ~15 min | 🔧 |
| U13 | UX #17 | Dlužníci — 109 ukazuje na nezpracované platby | ~20 min | 🔧 |
| U14 | UX #30 | Předpisy 549 vs Jednotky 508 — nesedí počty | ~15 min | 🔧 |
| U15 | UX #33 | Import — „nahradí všech 512 vlastníků" je děsivé | ~10 min | 🔧 |
| U16 | UX #31 | Vyúčtování — hromadná změna bez potvrzení | ~10 min | 🔧 |
| U17 | UX #25 | Email log — limit 100 bez paginace | ~45 min | ❓ |
| U18 | UX #34 | Předpisy/matice — příliš mnoho bublin (11+) | ~45 min | ❓ |

### LOW / DROBNÉ priority

| # | Zdroj | Nález | Čas |
|---|-------|-------|-----|
| A8 | Audit N7 | Zbytkový Playwright log | ~1 min |
| A9 | Audit N8 | test_prostory.xlsx v kořeni | ~1 min |
| A10 | Audit N9 | Hardcoded Dropbox cesta | ~5 min |
| A11 | Audit N10 | Chybějící sqlite3 kontrola | ~2 min |
| A12 | Audit N11 | WHEEL_COUNT nedefinovaná | ~2 min |
| B3-7 | Backup #2,5-8 | Rollback .env, manifest verze, log, tabulky, auto-zálohy | ~30 min |
| U19 | UX #4 | Dluh bez vysvětlení | ~20 min |
| U20 | UX #7 | Nájemci detail — chybí UX text | ~15 min |
| U21 | UX #9 | Prostory „???" jako VS | ~15 min |
| U22 | UX #11 | Hlasování lístky — back link propagace | ~15 min |
| U23 | UX #15 | Platby nav — ořezaný text | ~10 min |
| U24 | UX #18 | Výpis detail — tooltip „Přeparovat" | ~5 min |
| U25 | UX #20 | Zůstatky — prázdná stránka bez guidance | ~10 min |
| U26 | UX #27 | Sidebar badge bez vysvětlení | ~5 min |
| U27 | UX #29 | Jednotky detail — „Zpět" bez kontextu | ~5 min |
| U28 | UX #32 | Jednotky detail — klikací badge | ~5 min |
| U29 | UX #3 | Dashboard — prázdný stav pro nového uživatele | ~30 min |
| U30 | UX #10 | Prostory — chybí bublina „S nájemcem" | ~15 min |
| U31 | UX #21 | Kontroly — taby vypadají jako tlačítka | ~10 min |

---

## Etapy oprav

### Etapa 0: Úklid a mechanické opravy (~25 min)
> Nulové riziko regrese. Žádné změny v logice.

| # | Co | Čas |
|---|---|-----|
| A8 | Smazat Playwright log + test_prostory.xlsx | ~2 min |
| A6 | Logger placement v email_service.py | ~2 min |
| A7 | Return type annotation _create_smtp | ~2 min |
| A3 | datetime.utcnow → utcnow() v 7 modelech + dashboard.py | ~16 min |
| A12 | WHEEL_COUNT inicializace v spustit.command | ~2 min |
| A11 | sqlite3 kontrola v pripravit_prenos.sh | ~2 min |

**Test:** `pytest tests/ -v` — všech 248 testů musí projít. Spustit server, otevřít dashboard.

---

### Etapa 1: HIGH priority opravy (~15 min)
> Nízké riziko. Opravy existující logiky bez nového kódu.

| # | Co | Čas |
|---|---|-----|
| A1 | SMTP duplikace — nahradit inline logiku voláním `_create_smtp()` | ~5 min |
| A2 | engine.dispose() před ZIP/složka restore (3 endpointy) | ~5 min |
| A5 | Temp form hidden fields při HTMX polling | ~5 min |

**Test:** (1) Nastavení → Test SMTP připojení (port 465 i 587). (2) Správa → Zálohy → vytvořit zálohu → obnovit ze zálohy. (3) Rozesílání → spustit rozesílku → kliknout „Zrušit" během odesílání.

---

### Etapa 2: Quick wins UX (~2 hod)
> Nízké riziko. Textové a vizuální změny, žádná změna v datové logice.

| # | Co | Čas |
|---|---|-----|
| U24 | Tooltip na „Přeparovat" | ~5 min |
| U26 | Tooltip na sidebar badge „109" | ~5 min |
| U27 | „Zpět" → „Zpět na seznam jednotek" | ~5 min |
| U28 | Zvýraznit klikací badge plateb | ~5 min |
| U23 | Opravit ořezaný text „VS mapov..." | ~10 min |
| U15 | Import varování → informativní text | ~10 min |
| U16 | Potvrzení pro hromadnou změnu vyúčtování | ~10 min |
| U25 | Zůstatky — informativní text | ~10 min |
| U21 | „???" jako VS — vizuální varování | ~15 min |
| U12 | Pozastavená rozesílka — vizuální odlišení | ~15 min |
| U20 | Nájemci detail — UX text propojený nájemce | ~15 min |
| U13 | Dlužníci — info o období dat | ~20 min |
| U14 | Předpisy — vysvětlit rozdíl počtů | ~15 min |

**Test:** Projít každou dotčenou stránku, ověřit texty, tooltipy, vizuální změny.

---

### Etapa 3: Datové opravy (~2 hod)
> Střední riziko. Změny v routerech a dotazech — důkladně testovat.

| # | Co | Čas |
|---|---|-----|
| U3 | Vyúčtování — ověřit a opravit logiku výpočtu | ~1 hod |
| U7 | Detail vlastníka — přidat celkový dluh | ~30 min |
| U6 | Nájemci detail — zobrazit skutečný pronájem | ~30 min |

**Test:** (1) Vyúčtování — porovnat výpočet s ručním výpočtem pro 3 jednotky. (2) Detail vlastníka — ověřit součet dluhu za všechny jednotky. (3) Detail nájemce — ověřit zobrazení prostoru.

---

### Etapa 4: UX středně složité (~2.5 hod)
> Střední riziko. Nový kód v šablonách a routerech.

| # | Co | Čas |
|---|---|-----|
| U9 | HTMX search loading indikátor (všechny stránky) | ~30 min |
| U8 | Rozesílka — filtrovací bubliny na přiřazení (597 řádků) | ~20 min |
| U11 | Hlasování — opravit patičkový text v datech | ~10 min |
| B1 | WAL checkpoint warning → feedback uživateli | ~15 min |
| B2 | Safety backup ochrana před auto-cleanup | ~20 min |
| U10 | Hromadné úpravy — náhled změn | ~45 min |
| U22 | Hlasování lístky — back link propagace | ~15 min |

**Test:** (1) Hledání na všech stránkách — vidět spinner. (2) Rozesílka detail → přiřazení → filtrovat bubliny. (3) Správa → Zálohy → ověřit safety backup prefix.

---

### Etapa 5: UX velké změny — potřeba rozhodnutí (~5-6 hod)
> Vyšší riziko. Nové UI komponenty, změny layoutu. Každou změnu diskutovat s uživatelem.

| # | Co | Čas | Rozhodnutí potřeba |
|---|---|-----|---|
| U1 | Matice plateb — skrýt prázdné měsíce + sticky sloupce | ~2 hod | Varianta A/B/C? |
| U4 | Dashboard — seskupit/filtrovat aktivitu | ~1 hod | Seskupení nebo bubliny? |
| U5 | Nájemci — řešit duplicitní řádky | ~1 hod | 1 řádek nebo seskupit? |
| U18 | Předpisy/matice — příliš mnoho bublin | ~45 min | Seskupit nebo dropdown? |
| U17 | Email log — paginace | ~45 min | Paginace nebo „Načíst další"? |

**Test:** Každou změnu testovat s reálnými daty (500+ řádků).

---

### Etapa 6: Responzivita (volitelné) (~2 hod)
> Střední riziko. Závisí na tom, zda se aplikace používá na mobilech.

| # | Co | Čas |
|---|---|-----|
| U2 | Sidebar — hamburger menu pro mobily | ~2 hod |

**Test:** Otevřít na mobilním zařízení / zmenšit okno prohlížeče pod 768px.

---

## Celkový odhad

| Etapa | Čas | Riziko | Prerekvizity |
|-------|-----|--------|-------------|
| 0: Úklid | ~25 min | Nulové | — |
| 1: HIGH opravy | ~15 min | Nízké | — |
| 2: Quick wins UX | ~2 hod | Nízké | — |
| 3: Datové opravy | ~2 hod | Střední | Etapa 0-1 |
| 4: UX středně složité | ~2.5 hod | Střední | Etapa 0-1 |
| 5: UX velké (rozhodnutí) | ~5-6 hod | Vyšší | Etapa 2-4 |
| 6: Responzivita | ~2 hod | Střední | Etapa 2 |

**Celkem: ~14-15 hodin** (etapy 0-4 jsou ~7 hod bez nutnosti rozhodnutí, etapy 5-6 vyžadují diskuzi)

---

## Doporučený postup

1. **Etapy 0 + 1 dohromady** — mechanické opravy, commit, test
2. **Etapa 2** — quick wins, commit po každé skupině
3. **Etapa 3** — datové opravy, commit jednotlivě (vyšší riziko)
4. **Etapa 4** — UX opravy, commit po skupinách
5. **Etapa 5** — diskuze s uživatelem o variantách, pak implementace
6. **Etapa 6** — až po rozhodnutí zda je mobilní verze potřeba
