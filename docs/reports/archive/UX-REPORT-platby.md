# UX Analýza — Evidence plateb

> Analyzováno: 2026-03-19
> Rozsah: modul Platby — předpisy, VS symboly, bankovní výpisy, matice plateb, dlužníci, vyúčtování

## Souhrn

| Pohled | Kritické | Důležité | Drobné |
|--------|----------|----------|--------|
| Běžný uživatel | 1 | 3 | 3 |
| Business analytik | 0 | 2 | 2 |
| UI/UX designer | 0 | 1 | 3 |
| Performance analytik | 0 | 1 | 1 |
| Error recovery | 2 | 3 | 1 |
| Data quality | 1 | 2 | 2 |
| **Celkem (unikátní)** | **3** | **8** | **7** |

---

## Nálezy a návrhy

### Bankovní výpisy — import a párování

#### Nález #1: Výdajové platby se párují na jednotky přes VS
- **Severity:** KRITICKÉ
- **Pohled:** Data quality, Error recovery
- **Co a kde:** Funkce `match_payments()` páruje VŠECHNY nenapárované platby (příjmy i výdaje) na jednotky přes VS. Pokud SVJ zaplatí dodavateli a v platbě je VS shodný s mapováním → výdaj se chybně přiřadí k jednotce vlastníka.
- **Dopad:** Matice plateb, dlužníci a vyúčtování počítají jen příjmy (`Payment.direction == INCOME`), takže chybné přiřazení výdaje neovlivní výpočty. ALE v detailu výpisu se napárovaná výdajová platba zobrazí s odkazem na jednotku → matoucí pro uživatele.
- **Řešení:** V `match_payments()` přidat filtr `Payment.direction == PaymentDirection.INCOME` do query nenapárovaných plateb.
- **Varianty:** —
- **Kde v kódu:** `app/services/payment_matching.py` — query na řádku kde se načítají unmatched payments
- **Náročnost:** nízká ~5 min
- **Závislosti:** —
- **Regrese riziko:** nízké — výpočty (matice, dlužníci, vyúčtování) už filtrují na INCOME, takže oprava jen omezí chybné badge v UI
- **Rozhodnutí:** 🔧 jen opravit
- **Jak otestovat:** Import CSV s výdajovou platbou, jejíž VS odpovídá existujícímu mapování → po opravě výdaj zůstane unmatched

#### Nález #2: `period_from.year` crash pokud metadata chybí
- **Severity:** KRITICKÉ
- **Pohled:** Error recovery
- **Co a kde:** `statements.py` — po importu CSV se volá `meta.get("period_from").year`. Pokud CSV nemá standardní Fio hlavičku a `period_from` je `None`, dojde k `AttributeError` (crash serveru).
- **Dopad:** 500 chyba bez srozumitelné zprávy. Uživatel neví co je špatně.
- **Řešení:** Přidat guard: `year = meta["period_from"].year if meta.get("period_from") else datetime.utcnow().year`
- **Varianty:** Alternativně vrátit validační chybu s hláškou „CSV neobsahuje očekávanou hlavičku Fio banky."
- **Kde v kódu:** `app/routers/payments/statements.py:215`
- **Náročnost:** nízká ~5 min
- **Závislosti:** —
- **Regrese riziko:** nízké
- **Rozhodnutí:** 🔧 jen opravit
- **Jak otestovat:** Nahrát CSV bez Fio hlavičky → místo 500 chyby se zobrazí srozumitelná hláška

#### Nález #3: Ruční přiřazení — tichý fail pokud jednotka neexistuje
- **Severity:** DŮLEŽITÉ
- **Pohled:** Error recovery, Běžný uživatel
- **Co a kde:** `platba_prirazeni` v `statements.py` — pokud zadané číslo jednotky neodpovídá žádné `Unit`, platba zůstane nezměněná, ale redirect obsahuje `?flash=match_ok`. Uživatel vidí „Platba přiřazena" i když se nic nestalo.
- **Dopad:** Uživatel si myslí že přiřazení proběhlo. Platba zůstane nenapárovaná, dluh zůstane.
- **Řešení:** Zkontrolovat existenci jednotky před přiřazením. Pokud neexistuje → redirect s `?flash=match_fail&msg=Jednotka+nenalezena`.
- **Varianty:** —
- **Kde v kódu:** `app/routers/payments/statements.py` — endpoint `platba_prirazeni`
- **Náročnost:** nízká ~10 min
- **Závislosti:** —
- **Regrese riziko:** nízké
- **Rozhodnutí:** 🔧 jen opravit
- **Jak otestovat:** V detailu výpisu, u nenapárované platby zadat neexistující č. jednotky → po opravě se zobrazí chybová hláška místo falešného úspěchu

#### Nález #4: Force overwrite smaže i ručně přiřazené platby bez varování
- **Severity:** DŮLEŽITÉ
- **Pohled:** Běžný uživatel, Error recovery
- **Co a kde:** Při importu výpisu, který již existuje, dialog nabízí „Přepsat". Přepsání smaže starý `BankStatement` s cascade na platby — včetně těch, které uživatel ručně přiřadil (MANUAL match).
- **Dopad:** Ztráta ruční práce párování bez varování.
- **Řešení:** V potvrzovacím dialogu zobrazit počet ručně přiřazených plateb: „Výpis obsahuje X ručně přiřazených plateb, které budou ztraceny."
- **Varianty:** Alternativně zachovat ruční přiřazení přes VS mapování a po reimportu automaticky znovu napárovat.
- **Kde v kódu:** `app/routers/payments/statements.py` — `vypis_import_upload`, `app/templates/payments/vypis_import.html`
- **Náročnost:** střední ~20 min
- **Závislosti:** —
- **Regrese riziko:** nízké
- **Rozhodnutí:** ❓ potřeba rozhodnutí — varovat vs. zachovat ruční přiřazení
- **Jak otestovat:** Importovat výpis, ručně přiřadit platbu, znovu importovat stejný výpis → po opravě dialog upozorní na ruční přiřazení

---

### Předpisy — import a hledání

#### Nález #5: Hledání v předpisech nepoužívá `strip_diacritics`
- **Severity:** DŮLEŽITÉ
- **Pohled:** Běžný uživatel, Data quality
- **Co a kde:** `prescriptions.py` — proměnná `q_ascii` se vypočítá přes `strip_diacritics(q)`, ale nikdy se nepoužije. Skutečný filtr volá `Prescription.owner_name.ilike(f"%{q}%")` s neupravným `q`. Hledání „novak" nenajde „Novák".
- **Dopad:** Hledání v předpisech nefunguje pro české znaky — standardní chování celé aplikace (vždy `name_normalized + strip_diacritics`) je porušeno.
- **Řešení:** Vyměnit `.ilike(f"%{q}%")` za Python-side filtr s `strip_diacritics` na `owner_name`, nebo přidat `owner_name_normalized` sloupec do modelu `Prescription`.
- **Varianty:** Python-side filtr je jednodušší (data už v paměti), DB sloupec je čistší ale vyžaduje migraci.
- **Kde v kódu:** `app/routers/payments/prescriptions.py:216-222`
- **Náročnost:** nízká ~10 min
- **Závislosti:** —
- **Regrese riziko:** nízké
- **Rozhodnutí:** 🔧 jen opravit (Python-side filtr)
- **Jak otestovat:** Na `/platby/predpisy/{id}` hledat "novak" → po opravě najde "Novák"

#### Nález #6: Prázdný DOCX import nevyvolá varování
- **Severity:** DROBNÉ
- **Pohled:** Běžný uživatel
- **Co a kde:** Pokud `parse_prescription_docx` vrátí 0 předpisů (špatný formát dokumentu, prázdný soubor), `PrescriptionYear` se vytvoří s `total_units=0`. Uživatel vidí prázdný detail bez vysvětlení.
- **Dopad:** Uživatel neví jestli dokument neobsahoval data nebo jestli parsování selhalo.
- **Řešení:** Po parsování zkontrolovat počet předpisů. Pokud 0 → zobrazit varování „Žádné předpisy nebyly nalezeny v dokumentu. Zkontrolujte formát souboru."
- **Varianty:** —
- **Kde v kódu:** `app/routers/payments/prescriptions.py` — po volání `parse_prescription_docx`
- **Náročnost:** nízká ~5 min
- **Závislosti:** —
- **Regrese riziko:** nízké
- **Rozhodnutí:** 🔧 jen opravit
- **Jak otestovat:** Nahrát prázdný/nevalidní DOCX → po opravě se zobrazí varování

---

### Vyúčtování

#### Nález #7: Generování vyúčtování — žádná zpětná vazba
- **Severity:** DŮLEŽITÉ
- **Pohled:** Běžný uživatel, Business analytik
- **Co a kde:** `settlement.py` — `generate_settlements()` vrací `{"created": X, "updated": Y, "total": Z}`, ale výsledek je úplně ignorován. Po generování 530 vyúčtování uživatel vidí jen seznam bez hlášky.
- **Dopad:** Uživatel neví jestli se něco stalo, kolik vyúčtování bylo vytvořeno/aktualizováno.
- **Řešení:** Předat výsledek do redirect URL jako query parametry: `?created=X&updated=Y`. V šabloně zobrazit flash zprávu: „Vygenerováno X nových, aktualizováno Y vyúčtování."
- **Varianty:** —
- **Kde v kódu:** `app/routers/payments/settlement.py:209-213`
- **Náročnost:** nízká ~10 min
- **Závislosti:** —
- **Regrese riziko:** nízké
- **Rozhodnutí:** 🔧 jen opravit
- **Jak otestovat:** Kliknout „Generovat vyúčtování" → po opravě se zobrazí zelená hláška s počty
- **Mockup:**
  ```
  Současný stav:
  ┌────────────────────────────────────────────────┐
  │ Vyúčtování 2026           [Generovat vyúčtování]│
  │ 530 vyúčtování                                  │
  │                                                 │
  │ (seznam bez jakékoliv zpětné vazby)             │
  └────────────────────────────────────────────────┘

  Navrhovaný stav:
  ┌────────────────────────────────────────────────┐
  │ ✓ Vygenerováno 530 vyúčtování (0 aktualizováno)│
  │                                                 │
  │ Vyúčtování 2026           [Generovat vyúčtování]│
  │ 530 vyúčtování                                  │
  └────────────────────────────────────────────────┘
  ```

#### Nález #8: Změna stavu vyúčtování — žádné potvrzení
- **Severity:** DROBNÉ
- **Pohled:** Běžný uživatel
- **Co a kde:** Na detailu vyúčtování po kliknutí na „Označit jako zaplaceno" se stav změní a stránka se přenačte, ale bez flash zprávy.
- **Dopad:** Uživatel neví jestli se stav opravdu změnil (musí vizuálně zkontrolovat badge).
- **Řešení:** Po změně stavu přidat `?flash=stav_ok` a v šabloně zobrazit: „Stav změněn na Zaplaceno."
- **Varianty:** —
- **Kde v kódu:** `app/routers/payments/settlement.py` — `vyuctovani_zmena_stavu`
- **Náročnost:** nízká ~5 min
- **Závislosti:** —
- **Regrese riziko:** nízké
- **Rozhodnutí:** 🔧 jen opravit
- **Jak otestovat:** Změnit stav → po opravě se zobrazí zelená hláška

#### Nález #9: Dead code — `paid_monthly` v settlement_service
- **Severity:** DROBNÉ
- **Pohled:** Performance analytik
- **Co a kde:** `settlement_service.py:57-77` — proměnná `paid_monthly` se vypočítá (DB dotaz + iterace), ale nikdy se nepoužije. Zbytečný DB dotaz a paměť.
- **Dopad:** Minimální — mírně pomalejší generování.
- **Řešení:** Smazat blok kódu `paid_monthly` + odpovídající query.
- **Varianty:** —
- **Kde v kódu:** `app/services/settlement_service.py:57-77`
- **Náročnost:** nízká ~2 min
- **Závislosti:** —
- **Regrese riziko:** nízké
- **Rozhodnutí:** 🔧 jen opravit
- **Jak otestovat:** Generovat vyúčtování → stejný výsledek jako před odstraněním

---

### VS symboly + zůstatky — chybějící zpětná vazba

#### Nález #10: Žádná flash zpráva po úspěšném přidání VS/zůstatku
- **Severity:** DROBNÉ
- **Pohled:** Běžný uživatel
- **Co a kde:** Přidání VS symbolu (`symbols.py`) a přidání/smazání zůstatku (`balances.py`) přesměrují bez jakékoliv flash zprávy. Uživatel neví jestli operace proběhla.
- **Dopad:** Nejistota uživatele — musí hledat nový záznam v tabulce.
- **Řešení:** Přidat query parametr `?flash=ok` do redirect URL a v šabloně zobrazit zelenou hlášku.
- **Varianty:** —
- **Kde v kódu:** `app/routers/payments/symbols.py`, `app/routers/payments/balances.py`
- **Náročnost:** nízká ~10 min
- **Závislosti:** —
- **Regrese riziko:** nízké
- **Rozhodnutí:** 🔧 jen opravit
- **Jak otestovat:** Přidat VS/zůstatek → po opravě zelená hláška „Přidáno"

---

### Matice plateb a dlužníci

#### Nález #11: Hardcoded rok 2026 jako fallback
- **Severity:** DROBNÉ
- **Pohled:** Business analytik
- **Co a kde:** `overview.py:53,137` — pokud neexistuje žádný `PrescriptionYear`, fallback rok je hardcoded `2026`. V budoucnu bude zavádějící.
- **Dopad:** Minimální — nastane jen pokud nejsou žádné předpisy, ale projeví se od roku 2027+.
- **Řešení:** Nahradit `datetime.utcnow().year`.
- **Varianty:** —
- **Kde v kódu:** `app/routers/payments/overview.py:53,137`
- **Náročnost:** nízká ~2 min
- **Závislosti:** —
- **Regrese riziko:** nízké
- **Rozhodnutí:** 🔧 jen opravit
- **Jak otestovat:** —

#### Nález #12: Detail plateb jednotky vrací 404 místo redirect
- **Severity:** DROBNÉ
- **Pohled:** Error recovery
- **Co a kde:** `overview.py:200-203` — `platby_jednotka` vrací `error.html` s 404 pokud jednotka neexistuje. Všude jinde v projektu se používá redirect na seznam.
- **Dopad:** Nekonzistentní chování. Uživatel vidí chybovou stránku místo tichého přesměrování.
- **Řešení:** Nahradit `TemplateResponse("error.html", ...)` za `RedirectResponse("/platby/prehled", status_code=302)`.
- **Varianty:** —
- **Kde v kódu:** `app/routers/payments/overview.py:200-203`
- **Náročnost:** nízká ~2 min
- **Závislosti:** —
- **Regrese riziko:** nízké
- **Rozhodnutí:** 🔧 jen opravit
- **Jak otestovat:** Navštívit `/platby/jednotka/99999` → po opravě redirect na matici plateb

---

### Hromadné operace (chybějící)

#### Nález #13: Chybí hromadná změna stavu vyúčtování
- **Severity:** DŮLEŽITÉ
- **Pohled:** Business analytik, Performance analytik
- **Co a kde:** 530 vyúčtování se musí měnit jeden po jednom (klik na detail → klik na stav). Pro hromadné označení „odesláno" nebo „zaplaceno" musí uživatel kliknout 530×.
- **Dopad:** Nepoužitelné pro hromadné workflow. Uživatel bude frustrován.
- **Řešení:** Přidat hromadnou akci na seznamu vyúčtování: checkbox řádky + dropdown „Změnit stav na…" + tlačítko „Provést".
- **Varianty:** A) Checkboxy na řádcích (přesný výběr). B) „Změnit vše filtrované" (bez checkboxů, jednodušší).
- **Kde v kódu:** `app/routers/payments/settlement.py`, `app/templates/payments/vyuctovani.html`
- **Náročnost:** střední ~1 hod
- **Závislosti:** —
- **Regrese riziko:** nízké
- **Rozhodnutí:** ❓ potřeba rozhodnutí — checkboxy vs. hromadná akce na filtr
- **Mockup:**
  ```
  Současný stav:
  ┌────────────────────────────────────────────────┐
  │ Č. │ Vlastník │ Výsledek │ Stav    │ Akce      │
  │  1 │ Novák    │ 2 500 Kč │ Vyúčt.  │ Detail →  │
  │  2 │ Svoboda  │ 1 200 Kč │ Vyúčt.  │ Detail →  │
  │    (musím kliknout na každý zvlášť...)          │
  └────────────────────────────────────────────────┘

  Navrhovaný stav (varianta B):
  ┌────────────────────────────────────────────────┐
  │ [Vše 530] [Vygenerováno 530] [Odesláno 0]...  │
  │                                                 │
  │ Hromadná akce: [Změnit na ▼] [Provést]         │
  │ (změní stav všech 530 vyfiltrovaných)           │
  │                                                 │
  │ Č. │ Vlastník │ Výsledek │ Stav    │ Detail    │
  └────────────────────────────────────────────────┘
  ```

#### Nález #14: Chybí export vyúčtování do Excelu
- **Severity:** DŮLEŽITÉ
- **Pohled:** Business analytik
- **Co a kde:** Seznam vyúčtování nemá export. Uživatel potřebuje přehled nedoplatků/přeplatků v Excelu pro další zpracování (komunikace s vlastníky, účetnictví).
- **Dopad:** Uživatel musí data opisovat ručně nebo screenshotovat.
- **Řešení:** Přidat export tlačítko na stránku vyúčtování. Soubor: `vyuctovani_{rok}_{suffix}_{datum}.xlsx` s rozpadem po položkách.
- **Varianty:** A) Jednoduchý export (1 řádek = 1 vyúčtování). B) Detailní export (s rozpadem položek).
- **Kde v kódu:** nový endpoint `GET /platby/vyuctovani/exportovat`, nová logika v `settlement.py`
- **Náročnost:** střední ~45 min
- **Závislosti:** —
- **Regrese riziko:** nízké
- **Rozhodnutí:** ❓ potřeba rozhodnutí — jednoduchý vs. detailní export
- **Jak otestovat:** Kliknout „Export" → stáhne se xlsx se správnými daty

---

### Hledání v detailu výpisu

#### Nález #15: Search v detailu výpisu — diakritika v protiúčtu
- **Severity:** DROBNÉ
- **Pohled:** Běžný uživatel
- **Co a kde:** `statements.py` — hledání v detailu výpisu používá `.ilike()` na `counter_account_name`, `note`, `message`. Pro české znaky v protiúčtu (např. „Společenství") hledání „spolecenstvi" nenajde shodu.
- **Dopad:** Mírný — VS a částky se hledají správně, ale textové pole selhávají na diakritiku.
- **Řešení:** Přepsat hledání na Python-side filtr s `strip_diacritics` (data jsou už v paměti díky `.all()`).
- **Varianty:** —
- **Kde v kódu:** `app/routers/payments/statements.py` — search logika v `vypis_detail`
- **Náročnost:** nízká ~10 min
- **Závislosti:** —
- **Regrese riziko:** nízké
- **Rozhodnutí:** 🔧 jen opravit
- **Jak otestovat:** V detailu výpisu hledat „spolecenstvi" → po opravě najde „Společenství"

---

### Celkový modul — konzistence

#### Nález #16: Konvence počátečního zůstatku není vysvětlena uživateli
- **Severity:** DŮLEŽITÉ
- **Pohled:** Běžný uživatel, Data quality
- **Co a kde:** V celém modulu se používá konvence: kladný zůstatek = dluh, záporný = přeplatek. Ale v UI formuláři „Přidat zůstatek" chybí vysvětlení. Uživatel může zadat kladné číslo myslíce přeplatek → špatné vyúčtování.
- **Dopad:** Chybné vyúčtování u všech jednotek kde zůstatek zadal špatně.
- **Řešení:** Přidat nápovědu pod input pole: „Kladná částka = jednotka dluží SVJ. Záporná = SVJ dluží jednotce (přeplatek)."
- **Varianty:** Alternativně: dva inputy (dluh / přeplatek) s automatickou konverzí znaménka.
- **Kde v kódu:** `app/templates/payments/zustatky.html` — formulář přidání
- **Náročnost:** nízká ~5 min
- **Závislosti:** —
- **Regrese riziko:** nízké
- **Rozhodnutí:** 🔧 jen opravit (přidat hint text)
- **Jak otestovat:** Otevřít formulář „Přidat zůstatek" → pod inputem se zobrazí vysvětlení konvence

#### Nález #17: Chybí odkaz na vyúčtování z detailu plateb jednotky
- **Severity:** DROBNÉ
- **Pohled:** UI/UX designer, Business analytik
- **Co a kde:** Na stránce `/platby/jednotka/{id}` (detail plateb) není odkaz na vyúčtování dané jednotky, i když vyúčtování existuje. Uživatel musí jít zpět na seznam a hledat.
- **Dopad:** Mírný — chybí propojení mezi souvisejícími stránkami.
- **Řešení:** Přidat odkaz/tlačítko „Zobrazit vyúčtování" v headeru detailu plateb, pokud existuje settlement pro danou jednotku a rok.
- **Varianty:** —
- **Kde v kódu:** `app/routers/payments/overview.py` (přidat query na Settlement), `app/templates/payments/jednotka_platby.html`
- **Náročnost:** nízká ~10 min
- **Závislosti:** —
- **Regrese riziko:** nízké
- **Rozhodnutí:** 🔧 jen opravit
- **Jak otestovat:** Na detailu plateb jednotky se zobrazí odkaz „Vyúčtování" → klik přejde na detail vyúčtování

#### Nález #18: Index plateb — chybí statistiky na kartě Vyúčtování
- **Severity:** DROBNÉ
- **Pohled:** UI/UX designer
- **Co a kde:** Karta Vyúčtování na indexu ukazuje jen celkový počet. Ostatní karty mají bohatší info (počet nenapárovaných, celková částka apod.).
- **Dopad:** Minimální — uživatel musí kliknout na kartu aby viděl detail.
- **Řešení:** Přidat souhrn: nedoplatky/přeplatky celkem, počet nevyřízených.
- **Varianty:** —
- **Kde v kódu:** `app/routers/payments/__init__.py`, `app/templates/payments/index.html`
- **Náročnost:** nízká ~10 min
- **Závislosti:** —
- **Regrese riziko:** nízké
- **Rozhodnutí:** 🔧 jen opravit
- **Jak otestovat:** Na `/platby` karta Vyúčtování zobrazuje „530 · Nedoplatky: 149 125 Kč"

---

## Top 5 doporučení (podle dopadu)

| # | Návrh | Dopad | Složitost | Čas | Závisí na | Rozhodnutí | Priorita |
|---|-------|-------|-----------|-----|-----------|------------|----------|
| 1 | #1 Filtr INCOME v párování plateb | Vysoký | Nízká | ~5 min | — | 🔧 | HNED |
| 2 | #2 Guard `period_from` None crash | Vysoký | Nízká | ~5 min | — | 🔧 | HNED |
| 3 | #5 Diakritika v hledání předpisů | Střední | Nízká | ~10 min | — | 🔧 | HNED |
| 4 | #7 Flash zpráva po generování vyúčtování | Střední | Nízká | ~10 min | — | 🔧 | BRZY |
| 5 | #13 Hromadná změna stavu vyúčtování | Vysoký | Střední | ~1 hod | — | ❓ | BRZY |

---

## Quick wins (nízká složitost, okamžitý efekt)
- [ ] #1 — Filtr `INCOME` v `match_payments()` (~5 min)
- [ ] #2 — Guard `period_from is None` crash (~5 min)
- [ ] #5 — Diakritika v hledání předpisů (~10 min)
- [ ] #7 — Flash po generování vyúčtování (~10 min)
- [ ] #8 — Flash po změně stavu vyúčtování (~5 min)
- [ ] #9 — Dead code `paid_monthly` smazat (~2 min)
- [ ] #10 — Flash po přidání VS/zůstatku (~10 min)
- [ ] #11 — Hardcoded rok 2026 → `datetime.now().year` (~2 min)
- [ ] #12 — 404 → redirect v detailu plateb jednotky (~2 min)
- [ ] #16 — Hint konvence zůstatku v UI (~5 min)
