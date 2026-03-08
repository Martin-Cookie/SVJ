# UX Analýza — Celá aplikace

> Analyzováno: 2026-03-08
> Rozsah: Celá aplikace (7 modulů)

## Souhrn

| Pohled | Kritické | Důležité | Drobné |
|--------|----------|----------|--------|
| Běžný uživatel | 1 | 4 | 4 |
| Business analytik | 1 | 1 | 0 |
| UI/UX designer | 0 | 3 | 6 |
| Performance analytik | 2 | 1 | 1 |
| Error recovery | 1 | 3 | 1 |
| Data quality | 2 | 1 | 1 |
| **Celkem** | **7** | **13** | **13** |

---

## KRITICKÉ

### K1: Quorum — započítání neúplných hlasů
- **Modul:** Hlasování
- **Pohled:** Data quality
- **Problém:** `_ballot_stats()` sčítá hlasy ze všech zpracovaných lístků, i když u některých bodů nejsou vyplněny hlasy. Kvórum se tak nafukuje.
- **Kde:** `voting/_helpers.py:113-121`, `_voting_header.html:109-140`

### K2: Import přepisuje existující hlasy bez varování
- **Modul:** Hlasování
- **Pohled:** Error recovery + Data quality
- **Problém:** Excel import přepíše manuálně zpracované hlasy bez zobrazení "staré → nové" a bez potvrzení.
- **Kde:** `voting/import_votes.py:162-216`, `import_preview.html`

### K3: SJM — riziko dvojitého započtení hlasů
- **Modul:** Hlasování
- **Pohled:** Data quality
- **Problém:** Pokud Excel má separátní řádky pro oba manžele (SJM), import může přiřadit hlasy dvakrát.
- **Kde:** `voting/session.py:410-527`, `voting_import.py`

### K4: N+1 Python-side sort u vlastníků a jednotek
- **Modul:** Vlastníci, Jednotky
- **Pohled:** Performance
- **Problém:** Sort "Podíl SČD" a "Jednotky" načte všechny záznamy do paměti a řadí v Pythonu.
- **Kde:** `owners.py:145-162`, `units.py:370-382`

### K5: N+1 query v tax sending (TaxDistribution)
- **Modul:** Rozesílání
- **Pohled:** Performance
- **Problém:** V loop přes `all_docs` se pro každý dokument dělá separátní query na distributions.
- **Kde:** `tax/sending.py:232`

### K6: Error reporting nekonzistentní
- **Modul:** Sync, Share check, Tax
- **Pohled:** Běžný uživatel
- **Problém:** Některé moduly redirectují bez chybové zprávy. Uživatel neví proč operace selhala.
- **Kde:** `share_check.py:90,94`, `sync.py:144`

### K7: Ztráta pozice v tabulce po akci
- **Modul:** Rozesílání (matching)
- **Pohled:** Business analytik
- **Problém:** Po potvrzení přiřazení se uživatel vrátí na začátek tabulky bez zachování stránky/filtru.
- **Kde:** `tax/matching.py:92,113`, `matching.html`

---

## DŮLEŽITÉ (top 13)

| # | Modul | Problém | Pohled |
|---|-------|---------|-------|
| D1 | Hlasování | Chybí progress při Excel importu | Běžný uživatel |
| D2 | Hlasování | Chybí help text na import mapping | Běžný uživatel |
| D3 | Hlasování | Ballot detail nezobrazuje progress (3/5 bodů) | UX designer |
| D4 | Hlasování | Chybí bulk reset zpracovaných lístků | Performance |
| D5 | Hlasování | Snapshot warning bez jasné akce | Běžný uživatel |
| D6 | Rozesílání | Unmatched distribuce skryté v collapsed | UX designer |
| D7 | Rozesílání | Nejednoznačný stav po pauze/restartu | Error recovery |
| D8 | Kontroly | Back URL chaos (2 sekce, ztráta hashe) | UX designer |
| D9 | Vlastníci | Přetížení bublin filtru (3 řady) | Business analytik |
| D10 | Vlastníci | Email validace tiše nastaví NULL | Error recovery |
| D11 | Jednotky | Chybí CSS error states na formuláři | Error recovery |
| D12 | Dashboard | Tax sessions SQL — Python groupování | Performance |
| D13 | Vlastníci | Chybí flash zpráva po vytvoření | Běžný uživatel |

---

## DROBNÉ (top 13)

| # | Modul | Problém |
|---|-------|---------|
| Dr1 | Hlasování | Export jen pro CLOSED, ne ACTIVE |
| Dr2 | Hlasování | Wizard nevaliduje "0 bodů" |
| Dr3 | Hlasování | Quorum threshold bez preview potřebných hlasů |
| Dr4 | Hlasování | PDF download link chybí na ballot detail |
| Dr5 | Celá app | Nekonzistentní empty states |
| Dr6 | Vlastníci | Podíl sloupec bez tooltippu |
| Dr7 | Vlastníci | Secondary email/telefon skrytý v tabulce |
| Dr8 | Jednotky | Vlastník bez kontaktu v tabulce |
| Dr9 | Vlastníci | Export tlačítka bez loading state |
| Dr10 | Celá app | Zpět odkaz malý a šedý |
| Dr11 | Dashboard | Stat karty přetížené |
| Dr12 | Rozesílání | Test email bez client-side validace |
| Dr13 | Admin | Delete akce bez jednotného data-confirm |

---

## Top 5 doporučení (podle dopadu)

| # | Návrh | Dopad | Složitost | Priorita |
|---|-------|-------|-----------|----------|
| 1 | Import hlasování: zobrazit "staré → nové" hlasy a potvrzení | Vysoký | Střední | HNED |
| 2 | N+1 fix: SQL sort pro podíl/jednotky + joinedload distributions | Vysoký | Nízká | HNED |
| 3 | Konzistentní error reporting (flash zprávy ve všech modulech) | Vysoký | Nízká | BRZY |
| 4 | Ballot detail: progress bar + confirmation na reset | Střední | Nízká | BRZY |
| 5 | Matching: zachovat pozici v tabulce po akci | Střední | Střední | BRZY |

---

## Quick wins (nízká složitost, okamžitý efekt)

- [ ] Přidat `data-confirm` na reset_ballot
- [ ] Flash zpráva po vytvoření vlastníka/jednotky
- [ ] `type="email"` → JS validace s chybovou zprávou
- [ ] Tooltip na sloupec "Podíl SČD"
- [ ] Empty states: přidat CTA tlačítko ("Vytvořit" / "Importovat")
- [ ] Test email input: `type="email"` + disabled button
