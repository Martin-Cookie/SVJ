# Business Logic Audit — SVJ

> Datum: 2026-04-11
> Rozsah: výpočty podílů, matice plateb, import hlasování, párování plateb, tax workflow, nesrovnalosti, vyúčtování

## Shrnutí nálezů

| Priorita | Počet |
|---|---|
| Kritické | 4 |
| Vysoké | 6 |
| Střední | 7 |
| Nízké | 5 |
| **Celkem** | **22** |

---

## KRITICKÉ

### K1. `OwnerUnit.votes` ztrácí desetinnou přesnost podílu
**Co a kde:** `app/models/owner.py:139` — `votes = Column(Integer)`. V `app/services/owner_exchange.py:26` `recalculate_unit_votes()` dělá `total = int(unit.podil_scd or 0)` — přímá truncace float → int, teprve pak se rozdělí mezi spoluvlastníky. Jednotka s `podil_scd = 12212.5` ztratí `0.5` hned na začátku.
**Důsledek:** hlasovací váhy neodpovídají prohlášení vlastníka, kvórum se počítá špatně pro SVJ s necelými podíly. Celková suma `OwnerUnit.votes` NIKDY není rovna `declared_shares` z `SvjInfo.total_shares` pokud jsou podíly necelé.
**Srovnej:** `share_check_comparator.py:236` `_parse_share_value` podporuje float a `Unit.podil_scd` je `Float` — tedy DB drží přesnou hodnotu, ale voting ji zahazuje.
**Riziko regrese:** nízké (změna modelu + migrace).
**Rozhodnutí:** ❓ — potřeba ujasnit, zda SVJ používá celočíselné podíly (1098) nebo zlomky.

### K2. `excel_import.py:461` ukládá `votes = unit.podil_scd or 0` bez `int()` castingu
**Co a kde:** `app/services/excel_import.py:461-468` — `votes = unit_obj.podil_scd or 0` se vloží do `OwnerUnit.votes` (Integer sloupec). Navíc u SJM/spoluvlastnictví se PRVOTNÍ import rozdělí nerovnoměrně — celý podíl jednotky se přiřadí KAŽDÉMU spoluvlastníkovi (iterace je per-Excel-řádek, takže všichni dostanou plnou hodnotu).
**Důsledek:** po prvním importu duplicitní "votes" u SJM (každý spoluvlastník má plný podíl jednotky), teprve po ručním spuštění `recalculate_unit_votes` přes editaci jednotky se to opraví. Hlasování generované hned po importu bez editace jednotek → chybný `ballot.total_votes`, zdvojená kvóra.
**Riziko:** vysoké pro čerstvé instance. Doporučení: zavolat `recalculate_unit_votes(unit, db)` na konci importu pro každou vytvořenou jednotku.

### K3. Nesrovnalosti — hrubá kontrola `wrong_amount` bez rozpětí
**Co a kde:** `app/services/payment_discrepancy.py:215-222` a :245-252 — kontroluje jen přesné násobky 1–12× předpisu s tolerancí 50 haléřů. Pokud majitel zaplatí `11.5 × monthly` (polovina zálohy dopředu) nebo `1.2 × monthly`, systém to označí jako `wrong_amount`, ale upozornění jen řekne "zaplaceno X, předpis Y" — nerozliší mírný přeplatek/nedoplatek od úplně nesmyslné platby.
**Důsledek:** upozornění "Nesprávná výše platby" chodí i na legitimní zálohové platby a majitele to zbytečně trápí.
**Varianta:** kontrolovat rozdíl `abs(amount - round(amount/monthly)*monthly) < threshold` (tolerance v řádech 5 %).

### K4. `_phase3_vs_prefix_match` — hardcoded `VS_PREFIX = "1098"`
**Co a kde:** `app/services/payment_matching.py:38` — `VS_PREFIX = "1098"` je zadrátovaný prefix konkrétního SVJ. Pro jiné SVJ (např. prefix 1205) fáze 3 VS-prefix dekódování nikdy nematchne nic.
**Důsledek:** systém nelze nasadit na jiné SVJ bez editace kódu. Komentář v kódu to sám přiznává: *"Prefix VS pro toto SVJ"*.
**Řešení:** přesunout do `SvjInfo` (nový Column `vs_prefix`), načítat za runtime.

---

## VYSOKÉ

### V1. Matice plateb — `expected = monthly * len(months_with_data) + opening`
**Co a kde:** `app/services/payment_overview.py:135` a :360. `expected` se počítá jako `měsíční × počet měsíců s jakoukoliv platbou`, ne `× aktuální měsíc roku`. Pokud nikdo v březnu nezaplatil, `months_with_data` nezahrnuje březen a dlužník za březen "zmizí". Naopak platba v prosinci za listopad (zpožděná) "aktivuje" listopad pro VŠECHNY jednotky v matici.
**Důsledek:** seznam dlužníků je závislý na chování ostatních — nestabilní metrika. Doporučení: použít `today.month` nebo explicitní "current billing month" z SvjInfo.

### V2. `compute_payment_matrix` — předpisy bez `unit_id` tiše přeskočené
**Co a kde:** `payment_overview.py:47` — smyčka iteruje jen `presc_by_unit` a přeskočí předpisy bez `unit_id` (prostory). OK pro matici jednotek, ale `paid_map` plní se z `PaymentAllocation.unit_id` bez rozlišení typu — pokud alokace má `unit_id=None` a `space_id=X`, platba zmizí z matice jednotek i prostorů, pokud chybí paralelní záznam.

### V3. `_match_owner_by_sender` — fallback na `owners[0]` při neshodě
**Co a kde:** `payment_discrepancy.py:88` — pokud odesílatel nematchne žádného spoluvlastníka, upozornění půjde na **prvního** spoluvlastníka. U SJM to znamená: manžel zaplatil pod svým jménem, upozornění dostane manželka (pokud má menší `owner_id`).
**Řešení:** při neshodě zaslat všem spoluvlastníkům nebo označit jako `unknown_recipient` a nezasílat automaticky.

### V4. Settlement — přeplatek/nedoplatek se proporčně rozetře na fond oprav
**Co a kde:** `settlement_service.py:129-134` — `ratio = pi.amount / monthly`, `item_paid = total_paid * ratio`. Předpokládá, že vlastník platí proporčně na všechny položky. Pokud má přeplatek 12 000 Kč, linearně se rozetře i na `FOND_OPRAV` — to je **špatně**: fond oprav se kumuluje, nevyúčtovává se ročně.
**Doporučení:** ve vyúčtování rozdělovat jen `SLUZBY` (a `PROVOZNI`), `FOND_OPRAV` nechat s plným předpisem a přebytek hlásit jako zůstatek fondu.

### V5. Import hlasování — `name_lookup` duplikuje záznamy per jednotka
**Co a kde:** `payment_matching.py:466-502` — dvě smyčky (z `Prescription.owner_name` a `OwnerUnit.owner.name_normalized`) naplňují stejný `name_lookup` se stejným `unit_id`. `seen_keys` dedupuje přes normalizovaný string, ale pokud `presc.owner_name` má titul a `owner.name_normalized` nemá, oba projdou → jedna jednotka má 2 kandidáty a skóre se zdvojí.

### V6. `_find_multi_unit_match` — kombinační exploze bez limitu
**Co a kde:** `payment_matching.py:303-332` — `combinations(entries, 2..4)` × 12 měsíců. Pro vlastníka s 10 jednotkami: C(10,4)×12 = 2 520 iterací/platba. Nepřepadne, ale nefunguje pro 5+ jednotek (limit `range(2, 5)`), což u správce nebo SVJ s větším vlastníkem je realistické.

---

## STŘEDNÍ

### S1. `Unit.unit_number` Integer vs `TaxDocument.unit_number` String(20)
Typová nekonzistence napříč projektem. Při párování se dělá `str(doc.unit_number)` nebo `int(raw)` s try/except — fragilní pro speciální čísla ("1A", "01"). Viz CLAUDE.md "Pozor" sekce, ale problém přetrvává.

### S2. Voting import — `name in owner_norm` je substring match
**Kde:** `voting_import.py:326` — `if name and name in owner_norm` najde falešné shody pro krátká příjmení ("Nová" ⊂ "Novák"). Mělo by používat word-level porovnání jako `payment_matching._find_name_matches`.

### S3. `SettlementItem.distribution_key = category.value` (string)
**Kde:** `settlement_service.py:139` — Enum se ukládá jako string, historické data rozbijí při přejmenování enum hodnoty. Mělo by držet FK na enum nebo číselník.

### S4. `UnitBalance.unit_id` bez `ondelete` cascade
**Kde:** `payment.py:89` — FK nemá `ondelete="CASCADE"`. Smazání jednotky může selhat nebo nechat osiřelý zůstatek.

### S5. `detect_discrepancies` vrací `[]` tiše při `period_from is None`
**Kde:** `payment_discrepancy.py:108-110` — pokud výpis nemá rok, nevrátí chybu, jen prázdný seznam. UI neukáže "neimportovaný rok výpisu", uživatel netuší proč chybí nesrovnalosti.

### S6. Voting quorum bez fallbacku na sum(votes)
**Kde:** `voting/_helpers.py:128-132` — pokud `SvjInfo.total_shares` není nastaveno, `quorum_reached = False` vždy. Měl by být fallback na `sum(OwnerUnit.votes)` s warningem v UI.

### S7. `balance_import.py:178` — opakovaný import sčítá místo přepsání
`existing.opening_amount = (existing + amount)` — dvojí import stejného CSV zdvojí zůstatky. Mělo by být REPLACE nebo fail-on-duplicate.

---

## NÍZKÉ

### N1. `_extract_unit_from_vs` vrací první match, ne nejlepší
`payment_matching.py:373-390` — zkouší několik extrakčních variant, vrátí první existující jednotku. Mělo by vybrat podle skóre (jméno + částka).

### N2. `recalculate_unit_votes` — zbytky deterministicky prvním vlastníkům
`owner_exchange.py:34-37` — zbytek jde do prvních N vlastníků po sort. Pro SJM s 2 spoluvlastníky = vždy první v pořadí dostane "víc" hlasů. Malý ale systematický bias.

### N3. `SettlementItem.cost_building` vs `cost_unit` — matoucí názvy
Model `payment.py:291-293`. V service se používají jako "roční celkem" vs "měsíční". Názvy sugerují rozúčtování podle budova/jednotka.

### N4. Hardcoded tolerance `0.50` Kč v discrepancy
`payment_discrepancy.py:215, 245` — nekonfigurovatelné. Pro SVJ s haléřovými podíly může maskovat reálné chyby.

### N5. Tax sending — `str(doc.unit_number)` equality
`tax/sending.py:42, 62` — case-sensitive, nefunguje pro "1A" vs "1a" nebo "01" vs "1".

---

## Top 5 k okamžitému řešení

1. **K1/K2 Podíly a hlasy** — sjednotit `OwnerUnit.votes` s `Unit.podil_scd` (Float) a volat `recalculate_unit_votes` po importu
2. **K4 VS_PREFIX hardcoded** — přesunout do `SvjInfo`, jinak nelze nasadit na jiné SVJ
3. **V1 matice expected** — použít `today.month` místo `len(months_with_data)`
4. **V3 recipient fallback** — neposílat upozornění náhodnému spoluvlastníkovi
5. **V4 settlement ratio** — nevyúčtovávat přeplatek na fond oprav

## Soubory s nejvíc nálezy

- `app/services/payment_matching.py` — K4, V5, V6, N1
- `app/services/payment_overview.py` — V1, V2
- `app/services/payment_discrepancy.py` — K3, V3, S5, N4
- `app/services/owner_exchange.py` — K1, N2
- `app/services/settlement_service.py` — V4, S3, N3
- `app/services/excel_import.py` — K2
- `app/services/voting_import.py` — S2
