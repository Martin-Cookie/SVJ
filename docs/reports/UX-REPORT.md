# UX Analyza -- Cela aplikace SVJ Sprava

> Analyzovano: 21.04.2026
> Rozsah: cela aplikace (vsechny moduly)
> Metoda: analyza kodu z 6 expertnich pohledu (hluboky mod) + 10 analytickych os
> Kontext: 2 commity od posledniho reportu (17.04.2026). Refaktoring agentu.

---

## Stav predchozich nalezu

Predchozi report (17.04.2026) mel 24 nalezu. Stav oprav:

| # | Nalez | Stav |
|---|-------|------|
| #1 | Titulky vodomeru chybi "- SVJ Sprava" | OPRAVENO — vsech 7 sablon ma suffix |
| #2 | Vodomerove aktivity pod "Administrace" na dashboardu | OPRAVENO — `_module_labels` obsahuje `water_meters` |
| #3 | Bublina "Bez emailu" neni vizualne odlisena | OPRAVENO — oranzove zvyrazneni implementovano |
| #4 | Odchylka TV sloupec prazdny | NERESENO — ceka na rozhodnuti (zda TV vodomery budou) |
| #5 | Vodomer detail chybi odkaz na vlastnika | NERESENO |
| #6 | Technicke nazvy modulu v historii emailu | OPRAVENO — `_email_module_labels` mapa v settings_email_tbody.html |
| #7 | Bounce check duplicitni zaznamy | NERESENO — ceka na rozhodnuti (dedup vs profil) |
| #8 | "Dluh" -> "Saldo" v detailu vlastnika | OPRAVENO — sloupec je nyni "Saldo" |
| #9 | Prazdny radek vlastnika | NERESENO — data issue v DB |
| #10 | Zustatky format "4766.0" | NERESENO |
| #11 | Matice plateb sloupec "Prevod" prazdny | NERESENO — ceka na rozhodnuti |
| #12 | Vyuctovani za nedokonceny rok bez varovani | NERESENO — kriticke, ceka na rozhodnuti |
| #13 | URL "/rozesilani" naming confusion | NERESENO — ceka na rozhodnuti |
| #14 | Rozesilka "Pokracovat" odkaz chybi | NERESENO |
| #15 | Tab styl v synchronizaci | INFORMATIVNI — zadna zmena potreba |
| #16 | Mobilni tabulky nective | CASTECNE — `overflow-x-auto` pridano na owners list |
| #17 | Technicke moduly v historii emailu | OPRAVENO — viz #6 |
| #18 | IMAP Odeslanych "Ne" u vsech profilu | INFORMATIVNI — ceka na rozhodnuti |
| #19 | Sidebar "Nastaveni" videt bez scrollu | INFORMATIVNI — akceptovatelny stav |
| #20 | Vyuctovani +/- prefix matouci | NERESENO — ceka na rozhodnuti |
| #21 | Nesrovnalosti bez celkoveho prehledu | NERESENO |
| #22 | Duplicitni SMTP profily | NERESENO — ceka na rozhodnuti |
| #23 | VS "???" bez tooltipa s navodem | NERESENO |
| #24 | Chybejici loading pri bounce checku | NERESENO |

**Opraveno: 8 z 24 (33%)** · Ceka na rozhodnuti: 7 · Nereseno: 7 · Informativni: 2

---

## Souhrn

| Pohled | Kriticke | Dulezite | Drobne |
|--------|----------|----------|--------|
| Bezny uzivatel | 1 | 3 | 2 |
| Business analytik | 1 | 2 | 1 |
| UI/UX designer | 0 | 2 | 2 |
| Performance analytik | 0 | 1 | 1 |
| Error recovery | 0 | 1 | 1 |
| Data quality | 0 | 1 | 1 |
| **Celkem** | **2** | **10** | **8** |

---

## Strukturalni analyza (nova)

### A. Empty states

**Stav: VYBORNY** — 7 z 8 hlavnich stranek ma empty state s akcni vyzvu (CTA).

| Stranka | Stav | Poznamka |
|---------|------|----------|
| Dashboard | VYBORNY | Onboarding "Vitejte v SVJ Sprava" s 3 CTA kroky |
| Vlastnici | DOBRY | "Zadni vlastnici. Importujte z Excelu" s odkazem |
| Jednotky | DOBRY | "Zadne jednotky. Importujte z Excelu" s odkazem |
| Prostory | DOBRY | "Zadne prostory. Kliknete na + Novy prostor" |
| Najemci | DOBRY | "Zadni najemci. Kliknete na + Novy najemce" |
| Vodometry | VYBORNY | Kontextualni — rozlisuje "zadna data" vs "zadne vysledky filtru" + SVG ikona |
| Hlasovani | DOBRY | "Nebylo vytvoreno zadne hlasovani" s CTA "Vytvorit" |
| Predpisy | SLABY | Pouze text "Nejsou importovany" — chybi CTA tlacitko |

### B. Destruktivni akce

**Stav: VYBORNY** — kompletni ochrana na vsech urovnich.

- Jednoduche smazani: `data-confirm` / `hx-confirm` dialogy
- Vysoko-rizikove: custom modal vyzadujici psani "DELETE" (purge, smazani hlasovani s listky)
- Purge data: checkboxy + kaskadove zavislosti (owners → votings/tax auto-select) + DELETE potvrzeni
- Obnova ze zalohy: jasne varovani o prepsani dat + automaticka pojistna zaloha

### C. Navigace / back URL

**Stav: VYBORNY** — konzistentni vzor na vsech strankach.

- Vsechny detail stranky: `← {{ back_label }}` s dynamickym `back_url`
- Zachovani URL chainu pro vicevrstvou navigaci (dashboard → seznam → detail → platby)
- Scroll anchor zachovan pri navratu do seznamu

### D. Loading indikatory

**Stav: VYBORNY** — real-time progress pro vsechny dlouhe operace.

| Operace | Indikator | Funkce |
|---------|-----------|--------|
| Rozesilka vodomeru | HTMX polling 500ms + progress bar + ETA | Pause/Resume/Cancel |
| Rozesilka dani | HTMX polling 500ms + progress bar + ETA | Pause/Resume/Cancel |
| Import kontaktu | Background thread + HTMX polling + faze | -- |
| Export (Excel/CSV) | Client-side "Generuji..." + opacity | -- |

### E. Import workflows

**Stav: SMISENY** — 4 moduly maji plny 4-krokovy wizard, 2 maji zkraceny 2-3 krokovy flow.

| Import | Kroky | Wizard stepper | Poznamka |
|--------|-------|----------------|----------|
| Vlastnici | 4 | Ano | Upload → Mapovani → Nahled → Potvrdit |
| Kontakty | 4 | Ano | + background processing s progress |
| Hlasovani | 4 | Ano | Plny wizard |
| Prostory | 4 | Ano | + volba replace/append |
| Bank. vypisy | 2-3 | Ne | Chybi stepper, podmineny flow |
| Predpisy | 2-3 | Ne | Chybi stepper, VS konflikty |

### F. Detekce duplicit

**Stav: SILNY** — komplexni pri vytvareni, slabsi pri importu.

| Entita | Kontrola | Pole | Override |
|--------|----------|------|---------|
| Vlastnik (create) | 4 pole | Jmeno, RC, IC, Email | `force_create=1` |
| Najemce (create) | 3 pole | RC, IC, Jmeno (jen bez owner_id) | `force_create=1` |
| VS mapovani | Presna shoda | variable_symbol | UI konflikt v predpisy importu |
| Prostory (import) | Slabe | Zadna kontrola duplicitnich cisel | -- |

### G. Hromadne operace

**Stav: DOBRY** — 5 stranek s bulk checkboxy, 2 chybi.

S checkboxy: Listky hlasovani (bulk reset), Vyuctovani (bulk stav), Rozesilka vodomeru, Porovnani dani, Kontrola podilu.

Chybi: Zpracovani listku (checkboxy existuji ale bez action baru), Transakce vypisu (zadne checkboxy pro hromadne prirazeni VS).

### H. Vychozi hodnoty formularu

**Stav: SLABY** — pouze 3 pole maji smysluplne defaults.

| Pole | Default | Hodnoceni |
|------|---------|-----------|
| Kvorum (hlasovani) | 50% | DOBRY + dynamicky vypocet |
| Typ vlastnika | Fyzicka osoba | DOBRY |
| Status prostoru | Volny | DOBRY |
| Rok (zustatky) | -- | CHYBI — mel by byt `datetime.now().year` |
| Datumy hlasovani | -- | CHYBI — mohl by byt 1.1./31.12. |
| Zacatek smlouvy | -- | CHYBI — mohl by byt dnesni datum |

### I. Klavesnicova navigace

**Stav: ZAKLADNI** — dobre modaly, zadne zkratky.

- Escape: zavre vsechny modaly (PDF viewer, confirm, send)
- Tab trap: spravne implementovan v modalech (focus uvnitr)
- Focus restore: po zavreni modalu se focus vrati na trigger element
- Chybi: `role="dialog"` + `aria-modal="true"`, klavesove zkratky pro akce

### J. Chybove zpravy

**Stav: DOBRY** — formularove chyby na urovni formulare, ne pole.

- Import chyby: jasne zobrazi co selhalo (VS konflikty s tabulkou, pocet chyb)
- Zalohy: 7 ruznych chybovych stavu (prazdna, nazev, duplicita, neplatny, selhani, probihajici, upload, neplatny_db)
- Chybi: pole-specificke inline validace (napr. "Email neni ve spravnem formatu")

---

## Pretrvavajici nalezy z predchoziho reportu

### Nalez #1 (drivejsi #12): Vyuctovani za nedokonceny rok bez varovani
- **Severity:** KRITICKE
- **Pohled:** Business analytik, Error recovery
- **Co a kde:** Vyuctovani za rok 2026 (aktualne probihajici) ukazuje 530 zaznamu s "nedoplatky" az 40 887 Kc — matematicky spravne ale zavadejici uprostred roku
- **Dopad:** Omylem odeslane vyuctovani = zmetek
- **Reseni:** Varovani "Rok 2026 jeste nekonci — vyuctovani je predbezne" + blokace hromadneho odeslani
- **Kde v kodu:** `app/routers/payments/settlement.py`, `app/templates/payments/settlement.html`
- **Narocnost:** stredni ~30 min
- **Rozhodnuti:** ❓ ceka na rozhodnuti uzivatele

### Nalez #2 (drivejsi #13): URL "/rozesilani" naming confusion
- **Severity:** KRITICKE
- **Pohled:** Bezny uzivatel
- **Co a kde:** URL `/rozesilani` zobrazuje "Hromadne rozesilani" — matouci navigace
- **Dopad:** Uzivatel hledajici modul skonci na spatne strance
- **Reseni:** Premysleni nad URL strukturou — potreba rozhodnuti uzivatele
- **Narocnost:** stredni ~20 min
- **Rozhodnuti:** ❓ ceka na rozhodnuti uzivatele

### Nalez #3 (drivejsi #5): Vodomer detail chybi odkaz na vlastnika
- **Severity:** DULEZITE
- **Pohled:** Bezny uzivatel
- **Co a kde:** `/vodometry/{id}` zobrazuje jednotku ale ne vlastnika
- **Reseni:** Pridat klikaci jmeno vlastnika do header sekce
- **Kde v kodu:** `app/templates/water_meters/detail.html`
- **Narocnost:** nizka ~15 min
- **Rozhodnuti:** 🔧 jen opravit

### Nalez #4 (drivejsi #9): Prazdny radek vlastnika v DB
- **Severity:** DULEZITE
- **Pohled:** Data quality
- **Co a kde:** Vlastnik bez jmena v DB — narusuje duveru v data
- **Reseni:** Identifikovat a opravit DB zaznam + pridat validaci
- **Narocnost:** nizka ~10 min
- **Rozhodnuti:** 🔧 jen opravit

### Nalez #5 (drivejsi #10): Zustatky format "4766.0"
- **Severity:** DROBNE
- **Pohled:** UI/UX designer
- **Co a kde:** Castky v poznamce zustatku maji tecku misto mezer + "Kc"
- **Reseni:** Formatovat pres `fmt_num` filtr
- **Kde v kodu:** `app/templates/payments/zustatky.html`
- **Narocnost:** nizka ~10 min
- **Rozhodnuti:** 🔧 jen opravit

### Nalez #6 (drivejsi #20): Vyuctovani +/- prefix matouci
- **Severity:** DULEZITE
- **Pohled:** Bezny uzivatel
- **Co a kde:** "+40 887 Kc nedoplatek" — prefix "+" u nedoplatku je kontraintuitivni
- **Reseni:** Nedoplatek bez "+", preplatek se zelene
- **Kde v kodu:** `app/templates/payments/settlement_detail.html`
- **Narocnost:** nizka ~15 min
- **Rozhodnuti:** ❓ ceka na rozhodnuti uzivatele

### Nalez #7 (drivejsi #21): Nesrovnalosti bez celkoveho prehledu
- **Severity:** DULEZITE
- **Pohled:** Business analytik
- **Co a kde:** 102 zaznamu bez souhrnu dle typu, bez celkove castky
- **Reseni:** Bubliny podle typu nesrovnalosti + sumacni radek
- **Narocnost:** stredni ~30 min
- **Rozhodnuti:** ❓ ceka na rozhodnuti uzivatele

### Nalez #8 (drivejsi #14): Rozesilka "Pokracovat" odkaz chybi
- **Severity:** DROBNE
- **Pohled:** Bezny uzivatel
- **Co a kde:** Rozpracovana session "Ceka na potvrzeni" — chybi rychla akce
- **Reseni:** Pridat "Pokracovat →" odkaz
- **Kde v kodu:** `app/templates/tax/index.html`
- **Narocnost:** nizka ~10 min
- **Rozhodnuti:** 🔧 jen opravit

### Nalez #9 (drivejsi #23): VS "???" bez tooltipa
- **Severity:** DROBNE
- **Pohled:** Data quality
- **Co a kde:** Cervene "???" u VS prostoru bez navodu jak opravit
- **Reseni:** Tooltip "Priradtez VS v Platby > Symboly" + klikaci odkaz
- **Kde v kodu:** `app/templates/spaces/index.html`
- **Narocnost:** nizka ~10 min
- **Rozhodnuti:** 🔧 jen opravit

### Nalez #10 (drivejsi #24): Bounce check chybi loading indikator
- **Severity:** DROBNE
- **Pohled:** Error recovery
- **Co a kde:** "Zkontrolovat nyni" — zadny feedback behem 10-30s kontroly
- **Reseni:** Progress bar (infrastruktura uz existuje)
- **Kde v kodu:** `app/routers/bounces.py`
- **Narocnost:** stredni ~30 min
- **Rozhodnuti:** 🔧 jen opravit

---

## Nove nalezy

### Nalez #11: Predpisy — chybi CTA v empty state
- **Severity:** DROBNE
- **Pohled:** UI/UX designer
- **Co a kde:** `/platby/predpisy` ukazuje "Nejsou importovany zadne predpisy" — jen text, zadne tlacitko
- **Dopad:** Uzivatel nevedi jak importovat
- **Reseni:** Pridat tlacitko "Importovat predpisy" s odkazem na upload
- **Kde v kodu:** `app/templates/payments/predpisy.html`
- **Narocnost:** nizka ~5 min
- **Rozhodnuti:** 🔧 jen opravit

### Nalez #12: Bank./predpisy import chybi wizard stepper
- **Severity:** DULEZITE
- **Pohled:** Bezny uzivatel
- **Co a kde:** Importy bank. vypisu a predpisu maji 2-3 kroky ale bez vizualniho stepperu. Ostatni importy (vlastnici, kontakty, hlasovani, prostory) maji plny wizard.
- **Dopad:** Nekonzistentni UX mezi importy
- **Reseni:** Pridat `wizard_stepper.html` include do bank/predpisy import sablon
- **Kde v kodu:** `app/templates/payments/vypis_import.html`, `app/templates/payments/predpisy_import.html`
- **Narocnost:** nizka ~20 min
- **Rozhodnuti:** 🔧 jen opravit

### Nalez #13: Formulare — chybi vychozi hodnoty pro rok a datumy
- **Severity:** DULEZITE
- **Pohled:** Bezny uzivatel, Performance analytik
- **Co a kde:** (1) Rok v zustatcich nema default. (2) Hlasovani datumy nemaji default. (3) Zacatek smlouvy prostoru nema default.
- **Dopad:** Zbytecne klikani pri vytvareni zaznamu (odhadem 2-3 kliky x stovky zaznamu)
- **Reseni:** Year → `datetime.now().year`, hlasovani → 1.1./31.12. aktualniho roku, smlouva → dnes
- **Kde v kodu:** Prislusne routery (balances, voting create, spaces create)
- **Narocnost:** nizka ~15 min celkem
- **Rozhodnuti:** 🔧 jen opravit

### Nalez #14: Zpracovani listku — checkboxy bez action baru
- **Severity:** DROBNE
- **Pohled:** Bezny uzivatel
- **Co a kde:** Na `/hlasovani/{id}/zpracovani` existuji `.ballot-cb` checkboxy ale chybi bulk action bar
- **Dopad:** Checkboxy jsou videt ale nefunguje hromadna akce
- **Reseni:** Pridat action bar (stejna logika jako ballots.html bulk reset)
- **Kde v kodu:** `app/templates/voting/process_cards.html`
- **Narocnost:** stredni ~30 min
- **Rozhodnuti:** ❓ ceka na rozhodnuti uzivatele

### Nalez #15: Chybi `role="dialog"` na modalech
- **Severity:** DROBNE
- **Pohled:** UI/UX designer
- **Co a kde:** Custom modaly (delete, PDF viewer, confirm) nemaji `role="dialog"` + `aria-modal="true"` + `aria-labelledby`
- **Dopad:** Screen readery nevedi ze jde o modal — pristupnost
- **Reseni:** Pridat ARIA atributy do modal HTML
- **Kde v kodu:** `app/static/js/app.js` (kde se vytvareji modal elementy)
- **Narocnost:** nizka ~15 min
- **Rozhodnuti:** 🔧 jen opravit

---

## Pozitivni nalezy (od posledniho reportu)

1. **Titulky vodomeru opraveny** — vsech 7 sablon ma "- SVJ Sprava" suffix
2. **Dashboard moduly** — vodomerove aktivity spravne pod "Vodometry"
3. **Bublina "Bez emailu" oranzova** — vizualne odlisena od beznych bublin
4. **"Dluh" → "Saldo"** — terminologie sjednocena v detailu vlastnika
5. **Technicke moduly v emailech** — prelozene do cestiny (`_email_module_labels` mapa)
6. **Mobilni tabulky** — `overflow-x-auto` pridano na owners list
7. **Destruktivni akce** — kompletni ochrana (data-confirm, DELETE modaly, kaskadove purge)
8. **Progress indikatory** — real-time pro vsechny dlouhe operace (rozesilka, import)
9. **Back navigace** — konzistentni vzor s `back_url` + `back_label` + scroll anchor
10. **Empty states** — 7 z 8 stranek s akcni vyzvou

---

## Top 5 doporuceni (podle dopadu)

| # | Navrh | Dopad | Slozitost | Cas | Rozhodnuti | Priorita |
|---|-------|-------|-----------|-----|------------|----------|
| 1 | **#1** Varovani pri vyuctovani za nedokonceny rok | Vysoky | Stredni | ~30 min | ❓ | HNED |
| 2 | **#13** Vychozi hodnoty ve formularich (rok, datumy) | Stredni | Nizka | ~15 min | 🔧 | HNED |
| 3 | **#12** Wizard stepper pro bank/predpisy import | Stredni | Nizka | ~20 min | 🔧 | BRZY |
| 4 | **#3** Odkaz na vlastnika v detailu vodomeru | Stredni | Nizka | ~15 min | 🔧 | BRZY |
| 5 | **#7** Souhrn nesrovnalosti dle typu | Stredni | Stredni | ~30 min | ❓ | BRZY |

---

## Quick wins (nizka slozitost, okamzity efekt)

- [ ] #3 Odkaz na vlastnika v detailu vodomeru (~15 min)
- [ ] #4 Smazat prazdny radek vlastnika z DB (~10 min)
- [ ] #5 Formatovat castky v poznamce zustatku (~10 min)
- [ ] #8 "Pokracovat →" odkaz u rozpracovane rozesilky (~10 min)
- [ ] #9 Tooltip s navodem k "???" u VS prostoru (~10 min)
- [ ] #11 CTA tlacitko v prazdnem stavu predpisu (~5 min)
- [ ] #13 Vychozi hodnoty ve formularich (~15 min)
- [ ] #15 ARIA atributy pro modaly (~15 min)

---

## Srovnani s predchozim reportem

| Metrika | 17.04.2026 | 21.04.2026 | Zmena |
|---------|-----------|-----------|-------|
| Kriticke | 4 | 2 | -2 (zlepseni) |
| Dulezite | 13 | 10 | -3 (zlepseni) |
| Drobne | 13 | 8 | -5 (zlepseni) |
| **Celkem** | **30** | **20** | **-10 (33% zlepseni)** |

Nove nalezy: #11-#15 (empty states, wizard stepper, defaults, checkboxy, ARIA). Opraveno z predchoziho reportu: 8 nalezu (#1, #2, #3, #6, #8, #15, #17 + castecne #16).
