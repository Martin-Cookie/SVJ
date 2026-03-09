# UX Analyza -- Cela aplikace

> Analyzovano: 2026-03-09
> Rozsah: cela aplikace (dashboard, vlastnici, jednotky, hlasovani, dane/rozesilani, synchronizace, kontroly, sprava, nastaveni)
> Metoda: analyza zdrojoveho kodu (routery, sablony, modely, services)

## Souhrn

| Pohled | Kriticke | Dulezite | Drobne |
|--------|----------|----------|--------|
| Bezny uzivatel | 2 | 5 | 4 |
| Business analytik | 1 | 3 | 2 |
| UI/UX designer | 0 | 4 | 3 |
| Performance analytik | 1 | 2 | 2 |
| Error recovery | 2 | 3 | 1 |
| Data quality | 1 | 3 | 2 |
| **Celkem** | **7** | **20** | **14** |

---

## Nalezy a navrhy

### Dashboard

#### Nalez #1: Prazdny stav dashboardu nenavadi k akci
- **Severity:** DULEZITE
- **Pohled:** Bezny uzivatel
- **Co a kde:** Kdyz neni zadna aktivita (prazdna DB), dashboard zobrazi jen stat karty s nulami a zadny guidance. Sekce "Posledni aktivita" se vubec nezobrazi (podminka `{% if recent_activity or q %}`).
- **Dopad:** Novy uzivatel po instalaci vidi prazdnou stranku a nevi co delat dal.
- **Reseni:** Pridat onboarding blok pro prazdny stav -- "Zacnete importem dat z Excelu" s odkazem na `/vlastnici/import`, checklist prvnich kroku (1. Import vlastniku, 2. Zkontrolovat podily, 3. Zalozit hlasovani).
- **Kde v kodu:** `app/templates/dashboard.html:112` -- podminka `{% if recent_activity or q %}`
- **Narocnost:** nizka ~30 min
- **Rozhodnuti:** Opravit
- **Jak otestovat:** Smazat vsechna data (nebo cista DB), otevrit `/` -- melo by ukazat onboarding guide misto prazdna

#### Nalez #2: Dashboard stat karty nemaji tooltip/vysvetleni pro "Podily"
- **Severity:** DROBNE
- **Pohled:** Bezny uzivatel
- **Co a kde:** Na dashboardu se u karet Vlastnici a Jednotky zobrazuje "Podily: shoda" nebo "Delta XY", ale bez kontextu co to znamena.
- **Dopad:** Uzivatel bez znalosti SVJ terminologie nevi co "podily" znamenaji ani proc je tam delta.
- **Reseni:** Pridat `title` atribut na radek podilu s vysvetlenim, napr. "Porovnani podilu v evidenci s prohlasenim vlastnika".
- **Kde v kodu:** `app/templates/dashboard.html:25-27` a `44-46`
- **Narocnost:** nizka ~5 min
- **Rozhodnuti:** Opravit
- **Jak otestovat:** Najet mysi na "Podily: shoda" -- melo by se zobrazit vysvetleni

#### Nalez #3: Tabulka posledni aktivity nema prazdny stav pri hledani
- **Severity:** DROBNE
- **Pohled:** UI/UX designer
- **Co a kde:** Kdyz uzivatel hleda v aktivite a nic se nenajde, tbody je prazdna -- zadna zprava "Zadne vysledky".
- **Dopad:** Uzivatel nevedi, jestli se neco nacita nebo opravdu nic neni.
- **Reseni:** Pridat radek s `colspan` v partial `dashboard_activity_body.html` kdyz je `recent_activity` prazdny a `q` neprazdny.
- **Kde v kodu:** `app/templates/partials/dashboard_activity_body.html`
- **Narocnost:** nizka ~10 min
- **Rozhodnuti:** Opravit
- **Jak otestovat:** Na dashboardu zadat do hledani nesmyslny retezec -- melo by se zobrazit "Zadne vysledky"

---

### Vlastnici

#### Nalez #4: Vytvoreni noveho vlastnika -- neni validace duplicit
- **Severity:** KRITICKE
- **Pohled:** Data quality
- **Co a kde:** Endpoint `POST /vlastnici/novy` vytvori vlastnika bez kontroly, zda uz existuje se stejnym jmenem, RC nebo emailem. Zadna deduplikace.
- **Dopad:** Vzniknou duplicitni zaznamy, ktere pak znesnadnuji praci s daty (spatne soucty hlasu, vice listku pro jednoho cloveka).
- **Reseni:** Pred vlozenim zkontrolovat: (1) `name_normalized` shoda, (2) `birth_number` shoda, (3) `email` shoda. Pri nalezene shode zobrazit varovani "Vlastnik s podobnym jmenem/RC/emailem uz existuje" s odkazem na existujiciho.
- **Kde v kodu:** `app/routers/owners.py:53-107`
- **Narocnost:** stredni ~1 hod
- **Rozhodnuti:** Opravit
- **Jak otestovat:** Vytvorit vlastnika "Jan Novak", pak znovu "Jan Novak" -- melo by varovani o duplicite

#### Nalez #5: Email validace pri vytvoreni vlastnika -- ticha ztrata dat
- **Severity:** DULEZITE
- **Pohled:** Error recovery
- **Co a kde:** Kdyz uzivatel zada neplatny email pri vytvoreni vlastnika, system ticho email zahodi (`email_clean = ""`) a presmeruje s `?info=neplatny-email`. Uzivatel musi email zadat znovu rucne v detailu.
- **Dopad:** Uzivatel muze nevedet, ze email nebyl ulozen -- varovani je jemne a email je proste prazdny.
- **Reseni:** Misto zahozeni emailu vratit formular s chybou a predvyplnenymi daty, at uzivatel muze email opravit na miste.
- **Kde v kodu:** `app/routers/owners.py:82-87`
- **Narocnost:** stredni ~30 min
- **Rozhodnuti:** Opravit
- **Jak otestovat:** Zadat noveho vlastnika s emailem "test@" -- melo by zobrazit chybu s predvyplnenym formularem

#### Nalez #6: Seznam vlastniku -- bubliny kontaktu pouzivaji specialni znaky misto textu
- **Severity:** DROBNE
- **Pohled:** Bezny uzivatel
- **Co a kde:** Filtrovaci bubliny pro email/telefon pouzivaji HTML entity (`&#9993;` = obalka, `&#9742;` = telefon) s checkmarkem/krizkem. To je vizualne hure citelne nez text.
- **Dopad:** Uzivatel musi hadat co bublina znamena, zvlast na mensi obrazovce.
- **Reseni:** Pridat textovy label pod ikonu nebo pouzit tooltip: "S emailem", "Bez emailu", "S telefonem", "Bez telefonu".
- **Kde v kodu:** `app/templates/owners/list.html:83-101`
- **Narocnost:** nizka ~15 min
- **Rozhodnuti:** Opravit
- **Jak otestovat:** Otevrit `/vlastnici` a zkontrolovat, ze filtrovaci bubliny kontaktu jsou srozumitelne

#### Nalez #7: Detail vlastnika -- 4-sloupcovy grid je prilis husty na mensich obrazovkach
- **Severity:** DROBNE
- **Pohled:** UI/UX designer
- **Co a kde:** Detail vlastnika ma info strip `grid-cols-4` (identita, kontakt, trvala adresa, korespondencni adresa) bez responzivniho breakpointu.
- **Dopad:** Na uzkem okne (< 1200px) jsou sloupce prilis uzke a text se lame spatne.
- **Reseni:** Pridat breakpointy: `grid-cols-2 lg:grid-cols-4` nebo `grid-cols-1 md:grid-cols-2 lg:grid-cols-4`.
- **Kde v kodu:** `app/templates/owners/detail.html:38`
- **Narocnost:** nizka ~10 min
- **Rozhodnuti:** Opravit
- **Jak otestovat:** Zmensit okno prohlizece na < 1200px a otevrit detail vlastnika

---

### Jednotky

#### Nalez #8: Vytvoreni jednotky -- ticha ztrata dat u nespravneho cisla plochy
- **Severity:** DULEZITE
- **Pohled:** Error recovery
- **Co a kde:** Kdyz uzivatel zada neplatnou plochu nebo podil SCD (napr. text misto cisla), system hodnotu ticho ignoruje (`floor_area_float = None`) a vytvori jednotku bez teto hodnoty. Varovani se sice generuji, ale v HTMX odezve (`warn_html`) mohou byt snadno prehlednuta.
- **Dopad:** Uzivatel si mysli ze zadal vse spravne, ale data chybi.
- **Reseni:** (1) Pridat `type="number"` na inputy pro plochu a podil v sablone. (2) Zobrazit varovani vyrazneji -- banner s ikonou misto jemneho textu.
- **Kde v kodu:** `app/routers/units.py:86-108` (vytvoreni) a `312-328` (uprava)
- **Narocnost:** nizka ~20 min
- **Rozhodnuti:** Opravit
- **Jak otestovat:** Vytvorit jednotku s plochou "abc" -- melo by byt jasne varovani, ne ticha ztrata

#### Nalez #9: Jednotky -- chybi validace unikatnosti cisla budovy
- **Severity:** DROBNE
- **Pohled:** Data quality
- **Co a kde:** Unit cislo je validovane na unikatnost, ale cislo budovy ne. V SVJ muze byt vice budov se stejnym cislem, takze to neni problem, ale chybi upozorneni na podezrele hodnoty (napr. cislo budovy > 99999).
- **Dopad:** Minorni -- zadny data integrity problem, jen potencialne podivne hodnoty.
- **Reseni:** Pridat range kontrolu pro cislo budovy (1-99999) jako u cisla jednotky.
- **Kde v kodu:** `app/routers/units.py:46-57`
- **Narocnost:** nizka ~10 min
- **Rozhodnuti:** Drobne, neni priorita

---

### Hlasovani

#### Nalez #10: Generovani listku -- zadna zpetna vazba o prubehu
- **Severity:** DULEZITE
- **Pohled:** Performance analytik
- **Co a kde:** Endpoint `POST /{voting_id}/generovat` generuje listky synchronne -- pri 100+ vlastnicich muze trvat vice sekund. Zadny progress indicator, uzivatel nevedi co se deje.
- **Dopad:** Uzivatel muze kliknout znovu nebo si myslet ze se neco pokazilo.
- **Reseni:** (1) Pridat loading spinner na tlacitko (disable + text "Generuji..."), (2) Pro vetsi SVJ (500+ vlastniku) zvazit background thread s progress barem jako u dane/import.
- **Kde v kodu:** `app/routers/voting/session.py:403-591`
- **Narocnost:** nizka (spinner) ~15 min, stredni (background) ~2 hod
- **Rozhodnuti:** Hned udelat spinner, background az pokud bude potreba
- **Jak otestovat:** Kliknout na "Generovat listky" -- melo by zobrazit loading stav

#### Nalez #11: Hromadne zpracovani hlasu -- chybi feedback kolik se zpracovalo
- **Severity:** DULEZITE
- **Pohled:** Bezny uzivatel
- **Co a kde:** Endpoint `POST /{voting_id}/zpracovat-hromadne` zpracuje listky a presmeruje zpet, ale nerekne kolik listku bylo zpracovano.
- **Dopad:** Uzivatel nevi jestli se operace povedla a kolik listku bylo ovlivneno.
- **Reseni:** Pridat flash zpravu "Zpracovano X listku" pres query parametr do redirect URL.
- **Kde v kodu:** `app/routers/voting/ballots.py:316-358`
- **Narocnost:** nizka ~15 min
- **Rozhodnuti:** Opravit
- **Jak otestovat:** Hromadne zpracovat listky -- melo by se zobrazit "Zpracovano 5 listku"

#### Nalez #12: Mazani hlasovani -- nekonzistentni potvrzovaci mechanismus
- **Severity:** DULEZITE
- **Pohled:** Error recovery
- **Co a kde:** Pro koncept/aktivni hlasovani se pouziva `data-confirm` (jednoduchy browser confirm), pro uzavrene se pouziva specialni DELETE modal (nutno napsat "DELETE"). Dva ruzne vzory pro stejnou akci.
- **Dopad:** Uzivatel muze byt zmaten ruznym chovanim. U aktivniho hlasovani s daty staci jedno kliknuti, ale u uzavreneho je nutne psat DELETE.
- **Reseni:** Sjednotit -- pouzit DELETE modal pro vsechna hlasovani s daty (ballots > 0), jednoduchy confirm jen pro prazdne koncepty.
- **Kde v kodu:** `app/templates/voting/index.html:98-109`
- **Narocnost:** nizka ~20 min
- **Rozhodnuti:** Potreba rozhodnuti -- mozna je zamerne ruzne

#### Nalez #13: Import hlasu -- navigace zpet po importu chybi
- **Severity:** DROBNE
- **Pohled:** Bezny uzivatel
- **Co a kde:** Po uspesnem importu hlasu (import_result.html) neni jasny back odkaz ani tlacitko "Zpet na hlasovani" primo v kontextu vysledku.
- **Dopad:** Uzivatel musi pouzit sidebar nebo browser back.
- **Reseni:** Pridat tlacitko "Zobrazit vysledky" odkazujici na `/hlasovani/{voting_id}` a "Zpracovat dalsi" na `/hlasovani/{voting_id}/zpracovani`.
- **Kde v kodu:** `app/templates/voting/import_result.html`
- **Narocnost:** nizka ~10 min
- **Rozhodnuti:** Opravit
- **Jak otestovat:** Dokoncit import hlasu -- melo by byt jasne kam dal

#### Nalez #14: Stranka zpracovani -- konfiguracni slozitost pro hromadne operace
- **Severity:** DULEZITE
- **Pohled:** Business analytik
- **Co a kde:** Na strance zpracovani (`/hlasovani/{id}/zpracovani`) musi uzivatel u kazdeho listku jednotlive volit hlas pro kazdy bod. Chybi moznost "oznacit vse jako PRO/PROTI" pro typicke scenare kde vsichni hlasovali stejne.
- **Dopad:** Casove narocne pri desitce listku s vice body -- uzivatel musi klikat X * Y krat.
- **Reseni:** Pridat checkboxy pro vyber vice listku + hromadne radio "PRO/PROTI/Zdrzel se pro oznacene" (uz existuje `zpracovat-hromadne` endpoint, ale UI mozna neukazuje dostatecne).
- **Kde v kodu:** `app/routers/voting/ballots.py:316-358` (endpoint existuje), `app/templates/voting/process.html` (UI)
- **Narocnost:** stredni ~1 hod (UI vylepseni)
- **Rozhodnuti:** Potreba rozhodnuti -- overit jak casto se pouziva

---

### Dane / Hromadne rozesilani

#### Nalez #15: Rozesilka -- test email je POVINNY pred odeslanim, ale neni jasne proc
- **Severity:** DULEZITE
- **Pohled:** Bezny uzivatel
- **Co a kde:** Tlacitko "Odeslat" je zablokovane dokud neprojde testovaci email (`session.test_email_passed`), ale uzivatel neni informovan PROC je tlacitko disabled a CO ma udelat.
- **Dopad:** Uzivatel vidi sede tlacitko a nevedi jak ho aktivovat.
- **Reseni:** (1) Pridat tooltip na disabled tlacitko "Nejprve odeslte testovaci email". (2) Pridat vizualni indikator stavu testu (zelena fajfka / cerveny krizek).
- **Kde v kodu:** `app/routers/tax/sending.py:767` (kontrola), sablona `tax/send.html`
- **Narocnost:** nizka ~20 min
- **Rozhodnuti:** Opravit
- **Jak otestovat:** Otevrit rozesilku bez predchoziho testu -- melo by byt jasne ze je treba poslat test

#### Nalez #16: Rozesilka -- zmena obsahu emailu invaliduje test BEZ upozorneni
- **Severity:** KRITICKE
- **Pohled:** Error recovery
- **Co a kde:** V `save_send_settings` (radek 573-575) se pri zmene predmetu nebo tela emailu automaticky nastavi `test_email_passed = False`. Uzivatel neni upozornen ze test uz neplati a musi poslat novy.
- **Dopad:** Uzivatel zmeni text, chce odeslat, tlacitko je najednou disabled a nevedi proc.
- **Reseni:** Po ulozeni nastaveni zobrazit flash zpravu "Obsah emailu byl zmenen -- je nutne odeslat novy testovaci email." se zluytm pozadim.
- **Kde v kodu:** `app/routers/tax/sending.py:573-576`
- **Narocnost:** nizka ~15 min
- **Rozhodnuti:** Opravit
- **Jak otestovat:** (1) Poslat test email OK, (2) zmenit predmet, (3) ulozit -- melo by byt varovani + disabled tlacitko s vysvetlenim

#### Nalez #17: Prirazeni PDF -- nepotvrzena automaticka prirazeni jsou tiche
- **Severity:** DULEZITE
- **Pohled:** Business analytik
- **Co a kde:** Automaticke prirazeni PDF k vlastnikum (AUTO_MATCHED) jsou preskocena pri rozesilce, ale uzivatel se o tom dozvi az na strance rozesilky jako cislo "preskoceno X". Na strance prirazeni neni jasne kolik ceka na potvrzeni.
- **Dopad:** Uzivatel muze zapomenout potvrdit prirazeni a emaily se neposlou.
- **Reseni:** (1) Pridat vizualni varovani na strance prirazeni: "X dokumentu ceka na potvrzeni". (2) Pridat tlacitko "Potvrdit vsechna automaticka prirazeni".
- **Kde v kodu:** `app/routers/tax/session.py:361-538` (matching page), `app/routers/tax/_helpers.py:88-113` (stats)
- **Narocnost:** stredni ~45 min
- **Rozhodnuti:** Opravit
- **Jak otestovat:** Nahrat PDF, nechat automaticke prirazeni -- melo by byt jasne kolik ceka na potvrzeni a jak je hromadne potvrdit

#### Nalez #18: Rozesilka -- chybi "Odeslat vsem" / "Vybrat vsechny" checkbox
- **Severity:** DULEZITE
- **Pohled:** Performance analytik
- **Co a kde:** Na strance rozesilky musi uzivatel rucne zatrhnout kazdeho prijemce pro odeslani. Chybi "select all" checkbox v hlavicce.
- **Dopad:** Pri 50+ prijemcich je nutne 50+ kliknuti.
- **Reseni:** Pridat checkbox "Vybrat vse" v hlavicce tabulky ktery zatrh/odtrhne vsechny viditelne (filtrovane) checkboxy.
- **Kde v kodu:** `app/templates/tax/send.html`
- **Narocnost:** nizka ~20 min
- **Rozhodnuti:** Opravit
- **Jak otestovat:** Na strance rozesilky by mel byt checkbox "Vybrat vse" v hlavicce

#### Nalez #19: PDF nahrani -- chybi drag & drop
- **Severity:** DROBNE
- **Pohled:** UI/UX designer
- **Co a kde:** Upload PDF pouziva standardni `<input type="file">` s `webkitdirectory`. Chybi drag & drop zona.
- **Dopad:** Mene intuitivni nez drag & drop pro uzivatele zvykle na moderni webove aplikace.
- **Reseni:** Pridat drag & drop zonu kolem file inputu -- vizualni zona s textem "Pretahnete PDF soubory sem nebo kliknete pro vyber". Implementace pres vanilla JS `dragover`/`drop` eventy.
- **Kde v kodu:** `app/templates/tax/upload.html`
- **Narocnost:** stredni ~1 hod
- **Rozhodnuti:** Potreba rozhodnuti -- zavisi na priorite

---

### Synchronizace / Kontroly

#### Nalez #20: Synchronizace -- dva moduly na jedne strance mohou byt matouci
- **Severity:** DROBNE
- **Pohled:** Bezny uzivatel
- **Co a kde:** Stranka `/synchronizace` kombinuje dve nezavisle funkce: (1) Porovnani s CSV (synchronizace vlastniku) a (2) Kontrola podilu. Jsou na jedne strance s kotevnimi linky.
- **Dopad:** Uzivatel muze byt zmaten, ze jedna stranka dela dve veci. Nicmene jsou logicky spojene (kontroly dat).
- **Reseni:** Prijatelne jako je -- obe funkce jsou "kontroly" a patri k sobe. Mozna zlepsit vizualni oddeleni (vetsi nadpisy, jinak zbarvene sekce).
- **Kde v kodu:** `app/routers/sync.py:35-130`
- **Narocnost:** nizka ~15 min
- **Rozhodnuti:** Drobne, neni priorita

#### Nalez #21: Vymena vlastniku -- chybi undo / rollback moznost
- **Severity:** KRITICKE
- **Pohled:** Error recovery
- **Co a kde:** Kdyz uzivatel provede vymenu vlastniku (exchange), zmeny jsou okamzite commitovane a neni moznost je vratit zpet krome rucni opravy nebo obnoveni ze zalohy.
- **Dopad:** Spatna vymena (napr. spatne naparovane vlastniky) muze zpusobit ztratu dat.
- **Reseni:** (1) Pridat nahled pred vymenou (preview je uz implementovan), (2) Po vymene zobrazit souhrn s moznosti "Zrusit vymenu" (soft undo -- ulozit snapshot pred vymenou). (3) Minimalne zvyraznit ze akce je nevratna.
- **Kde v kodu:** `app/routers/sync.py` (exchange endpointy), `app/services/owner_exchange.py`
- **Narocnost:** vysoka ~3 hod (soft undo), nizka ~15 min (varovani)
- **Rozhodnuti:** Potreba rozhodnuti -- minimalne pridat varovani

---

### Administrace

#### Nalez #22: Smazat data -- chybi potvrzeni pro jednotlive kategorie
- **Severity:** KRITICKE
- **Pohled:** Error recovery
- **Co a kde:** Stranka "Smazat data" umoznuje hromadne mazani po kategoriich. Overit zda kazda kategorie ma dostatecne potvrzeni (hx-confirm nebo DELETE modal).
- **Dopad:** Nechcene smazani dat muze byt katastrofalni.
- **Reseni:** Overit ze VSECHNY destruktivni akce na strance purge maji bud `data-confirm` nebo DELETE modal pattern. Pro kategorie s vice nez 100 zaznamy pouzit DELETE modal.
- **Kde v kodu:** `app/templates/administration/purge.html`
- **Narocnost:** nizka ~20 min (audit + oprava)
- **Rozhodnuti:** Opravit
- **Jak otestovat:** Na `/sprava/smazat` zkusit smazat kazdou kategorii -- kazda by mela vyzadovat potvrzeni

#### Nalez #23: Hromadne upravy -- chybi indikace co se zmeni pred potvrzenim
- **Severity:** DULEZITE
- **Pohled:** Bezny uzivatel
- **Co a kde:** Hromadne upravy (bulk edit) meni pole pro vice zaznamu naraz. Chybi jasny nahled "Co se zmeni: X zaznamu bude mit hodnotu Y misto Z".
- **Dopad:** Uzivatel provede zmenu bez plne vedomosti o dopadu.
- **Reseni:** Pridat pocitadlo ovlivnenych zaznamu pred potvrzenim: "Tato operace zmeni pole 'Typ prostoru' u 15 jednotek z 'Byt' na 'Garaz'".
- **Kde v kodu:** `app/templates/administration/bulk_edit_records.html`
- **Narocnost:** stredni ~45 min
- **Rozhodnuti:** Opravit
- **Jak otestovat:** Na hromadnych upravach vybrat pole a hodnotu -- melo by ukazat kolik zaznamu bude ovlivneno

#### Nalez #24: Administrace index -- chybi popis co kazda sekce dela
- **Severity:** DROBNE
- **Pohled:** Bezny uzivatel
- **Co a kde:** Administrace index zobrazuje 7 karet s ikonami, ale popisky jsou velmi strucne ("Info o SVJ", "Ciselniky", "Zalohy"). Novy uzivatel nemuze vedet co presne kazda sekce obsahuje.
- **Dopad:** Uzivatel musi kliknout na kazdou kartu aby zjistil co obsahuje.
- **Reseni:** Pridat druhy radek popisu na kartach: "Info o SVJ" -> "Nazev, adresa, cleny vyboru", "Ciselniky" -> "Typy prostoru, sekce, typy vlastnictvi".
- **Kde v kodu:** `app/templates/administration/index.html:17-19`
- **Narocnost:** nizka ~15 min
- **Rozhodnuti:** Opravit

---

### Nastaveni

#### Nalez #25: SMTP heslo se neuklada kdyz je prazdne -- neni jasne
- **Severity:** DULEZITE
- **Pohled:** Bezny uzivatel
- **Co a kde:** V `save_smtp` (radek 170) se prazdne heslo ignoruje (`if smtp_password`). To zachova existujici heslo, ale uzivatel nevi ze pole "Heslo" je prazdne schvalne (pro zachovani) nebo ze heslo nebylo ulozeno.
- **Dopad:** Uzivatel muze chtet heslo smazat (napr. pri zmene SMTP) a nema jak.
- **Reseni:** (1) Pridat placeholder text "Ponechte prazdne pro zachovani stavajiciho hesla". (2) Pridat checkbox "Smazat heslo" pokud je potreba reset.
- **Kde v kodu:** `app/routers/settings_page.py:170`
- **Narocnost:** nizka ~15 min
- **Rozhodnuti:** Opravit
- **Jak otestovat:** Otevrit SMTP formular -- melo by byt jasne ze prazdne heslo = zachovat stavajici

#### Nalez #26: Email log -- limit 100 zaznamu bez paginace
- **Severity:** DROBNE
- **Pohled:** Performance analytik
- **Co a kde:** Email log na strance nastaveni zobrazuje maximalne 100 zaznamu (`EMAIL_LOG_LIMIT = 100`) bez moznosti paginace.
- **Dopad:** Po odeslani vice nez 100 emailu uzivatel nema pristup ke starsim zaznamum (krome SQL).
- **Reseni:** Pridat jednoduchou paginaci (jako u dane -- `stranka` parametr) nebo tlacitko "Nacist dalsi".
- **Kde v kodu:** `app/routers/settings_page.py:21, 84`
- **Narocnost:** stredni ~45 min
- **Rozhodnuti:** Potreba rozhodnuti -- 100 zaznamu je mozna dost

#### Nalez #27: SMTP test pripojeni chybi
- **Severity:** DULEZITE
- **Pohled:** Bezny uzivatel
- **Co a kde:** Po ulozeni SMTP nastaveni neni moznost otestovat pripojeni (ping SMTP serveru). Uzivatel se dozvi o chybe az pri pokusu o odeslani emailu.
- **Dopad:** Uzivatel nastavi spatne SMTP udaje a zjisti to az pri rozesilce.
- **Reseni:** Pridat tlacitko "Test pripojeni" vedle ulozit -- zavola `create_smtp_connection()` a zobrazi vysledek (OK/chyba).
- **Kde v kodu:** `app/routers/settings_page.py:137-190`, `app/services/email_service.py`
- **Narocnost:** nizka ~30 min
- **Rozhodnuti:** Opravit
- **Jak otestovat:** Ulozit SMTP nastaveni, kliknout "Test pripojeni" -- melo ukazat zda pripojeni funguje

---

### Globalni / Prurezove

#### Nalez #28: Sidebar nema mobilni responzivni verzi
- **Severity:** KRITICKE
- **Pohled:** UI/UX designer
- **Co a kde:** Sidebar je fixovany na `w-44` (176px) a main content ma `ml-44`. Na mobilnich zarizenich neni sidebar skryty ani transformovany na hamburger menu.
- **Dopad:** Na tabletu nebo telefonu je aplikace prakticky nepouzitelna -- sidebar zabira velkou cast obrazovky.
- **Reseni:** Pridat hamburger menu pro mobilni zarizeeni: sidebar skryty na `sm:` a nize, zobrazeny pres overlay po kliknuti na hamburger ikonu.
- **Kde v kodu:** `app/templates/base.html:22` (sidebar) a `131` (main content ml-44)
- **Narocnost:** stredni ~2 hod
- **Rozhodnuti:** Potreba rozhodnuti -- je aplikace pouzivana na mobilu?
- **Jak otestovat:** Otevrit aplikaci na telefonu nebo zmensit okno pod 640px

#### Nalez #29: Flash zpravy -- auto-dismiss bez moznosti zastavit
- **Severity:** DROBNE
- **Pohled:** Bezny uzivatel
- **Co a kde:** Flash zpravy maji `data-auto-dismiss` atribut ktery je automaticky skryje po casovem limitu. Uzivatel nema moznost zpravu "zastavit" nebo ji znovu zobrazit.
- **Dopad:** Dulezita chybova zprava muze zmizet driv nez ji uzivatel stihne precist.
- **Reseni:** (1) Chybove zpravy (`flash_type == 'error'`) by nemely automaticky mizet. (2) Pridat krizek pro manualni zavreni.
- **Kde v kodu:** `app/templates/base.html:135-141`, `app/static/js/app.js` (auto-dismiss logika)
- **Narocnost:** nizka ~15 min
- **Rozhodnuti:** Opravit
- **Jak otestovat:** Vyvolat chybovou zpravu -- mela by zustat dokud ji uzivatel nezavre

#### Nalez #30: Chybejici loading indikator pro HTMX requesty
- **Severity:** DULEZITE
- **Pohled:** Bezny uzivatel
- **Co a kde:** Kdyz uzivatel pise do vyhledavaciho pole, HTMX request bezi na pozadi ale neni vizualni indikator (spinner, skeleton). Jen se obsah tabulky najednou prepise.
- **Dopad:** Uzivatel nevi zda se neco deje, zvlast pri pomalejsim pripojeni.
- **Reseni:** Pridat HTMX class indicator: `hx-indicator` na search baru ktery ukaze spinner/pulzujici bar behem requestu. HTMX nativne podporuje class `htmx-request` na elementu.
- **Kde v kodu:** Vsechny search inputy -- `owners/list.html:150`, `units/list.html` (obdobne), `dashboard.html:124`, `settings.html:28`
- **Narocnost:** nizka ~30 min
- **Rozhodnuti:** Opravit
- **Jak otestovat:** Zadat text do hledani -- melo by byt jasne ze se neco nacita

#### Nalez #31: CSV export pouziva strednik ale nema hlavicku s oddelovacem
- **Severity:** DROBNE
- **Pohled:** Data quality
- **Co a kde:** V CLAUDE.md je specifikovano ze CSV pouziva strednik jako oddelovac, ale v kodu `owners.py:429` a `units.py:553` se pouziva `csv.writer(buf)` s defaultnim comma oddelovacem.
- **Dopad:** CSV export s carkou misto stredniku se v ceskem Excelu (ktery ocekava strednik) neotevre spravne.
- **Reseni:** Pridat `delimiter=';'` do `csv.writer(buf, delimiter=';')` ve vsech CSV exportech.
- **Kde v kodu:** `app/routers/owners.py:429`, `app/routers/units.py:553`
- **Narocnost:** nizka ~5 min
- **Rozhodnuti:** Opravit
- **Jak otestovat:** Exportovat vlastniky do CSV, otevrit v Excelu -- sloupce by mely byt spravne rozdelene

#### Nalez #32: Zadne potvrzeni pri opusteni neulozenho formulare
- **Severity:** DULEZITE
- **Pohled:** Error recovery
- **Co a kde:** Kdyz uzivatel vyplnuje formular (nove hlasovani, novy vlastnik, SMTP nastaveni) a klikne na sidebar odkaz, formular se zavle bez varovani.
- **Dopad:** Ztrata rozpracovanych dat -- uzivatel musi vse vyplnit znovu.
- **Reseni:** Pridat `beforeunload` event listener na stranky s formulari ktere nemaji `hx-boost`. Detekovat ze se formular zmenil (input event) a varovani zobrazit jen pri zmenach.
- **Kde v kodu:** Vsechny stranky s formulari: `voting/create.html`, `tax/upload.html`, `partials/smtp_form.html`
- **Narocnost:** stredni ~1 hod (globalni reseni)
- **Rozhodnuti:** Opravit
- **Jak otestovat:** Vyplnit formular noveho hlasovani, kliknout na sidebar -- melo by varovani "Maate neulozeene zmeny"

#### Nalez #33: Chybejici keyboard navigace / accessibility
- **Severity:** DULEZITE
- **Pohled:** UI/UX designer
- **Co a kde:** Filtrovaci bubliny jsou `<a>` tagy (OK pro keyboard), ale HTMX interaktivni prvky (inline edit, toggle) nemaji vzdy spravne `aria-label` atributy. Potvrzovaci modaly nemaji focus trap.
- **Dopad:** Uzivatele s asistivnimi technologiemi mohou mit problem s navigaci.
- **Reseni:** (1) Pridat `aria-label` na vsechny interaktivni prvky. (2) Pridat focus trap na modaly (confirm-modal, delete-modal, pdf-modal). (3) Pridat `role="dialog"` na modaly.
- **Kde v kodu:** `app/templates/base.html:149-186` (modaly), vsechny sablony s HTMX interakci
- **Narocnost:** stredni ~2 hod
- **Rozhodnuti:** Dulezite pro pristupnost

#### Nalez #34: Owner detail -- "Vlastnik od" pole neni strukturovane
- **Severity:** DROBNE
- **Pohled:** Data quality
- **Co a kde:** Pole `owner_since` je `String(50)` -- volny text. Neni datum, takze nelze radit, filtrovat ani validovat.
- **Dopad:** Nekonzistentni formaty (napr. "2020", "od roku 2020", "1.1.2020") znemoznuji automaticke zpracovani.
- **Reseni:** Priste zmenit na `Date` typ. Zatim neni kriticke -- pole se pouziva jen pro zobrazeni.
- **Kde v kodu:** `app/models/owner.py:56`
- **Narocnost:** stredni ~1 hod (vcetne migrace existujicich dat)
- **Rozhodnuti:** Drobne, neni priorita

#### Nalez #35: Vlastnici -- emails_count nepocita email_secondary
- **Severity:** DULEZITE
- **Pohled:** Data quality
- **Co a kde:** Na strance vlastniku se pocet "S emailem" pocita jen z `Owner.email`, ne z `Owner.email_secondary`. Ale filtr `s_emailem` pouziva `or_` s obema poli (radek 142-145). To znamena ze cislo v bublince muze byt MENSI nez skutecny pocet po filtraci.
- **Dopad:** Bublina ukazuje napr. 45, ale po kliknuti se zobrazi 52 vlastniku (7 ma jen sekundarni email).
- **Reseni:** Upravit `emails_count` query aby pocitala i `email_secondary`: pridat `or_` podminku jako ve filtru.
- **Kde v kodu:** `app/routers/owners.py:255-259`
- **Narocnost:** nizka ~10 min
- **Rozhodnuti:** Opravit
- **Jak otestovat:** Porovnat cislo v bublince "S emailem" s poctem zobrazenych po kliknuti na bublinu

#### Nalez #36: Voting list -- neoptimalni eager loading
- **Severity:** KRITICKE
- **Pohled:** Performance analytik
- **Co a kde:** Voting list endpoint (`GET /hlasovani/`) nacita VSECHNA hlasovani s `joinedload(Voting.ballots).joinedload(Ballot.votes)`. Pro kazde hlasovani pak v Pythonu iteruje vsechny listky a hlasy pro pocitani vysledku. Pri 10 hlasovanich s 200 listky a 5 body = 10000 BallotVote objektu v pameti.
- **Dopad:** Pomale nacitani stranky pri vice hlasovanich. Muze byt problem s pameti.
- **Reseni:** Pouzit SQL agregaci pro vysledky per-item (SUM, GROUP BY) misto Python iterace. Nebo precompute vysledky pri zpracovani listku a ulozit do voting/item modelu.
- **Kde v kodu:** `app/routers/voting/session.py:43-101`
- **Narocnost:** vysoka ~3 hod
- **Rozhodnuti:** Opravit pokud jsou problemove rychlosti
- **Jak otestovat:** Vytvorit 5+ hlasovani kazde s 50+ listky, otevrit `/hlasovani` -- merit cas nacitani

#### Nalez #37: Datum validace -- neplatne datumy se ticho ignoruji
- **Severity:** DULEZITE
- **Pohled:** Error recovery
- **Co a kde:** Pri vytvoreni hlasovani se neplatne datumy (`start_date`, `end_date`) ticho ignoruji -- `except ValueError: pass` (radek 205-206). Zadna zpetna vazba uzivateli.
- **Dopad:** Uzivatel zada datum, ale ten se neulozi. Zustane prazdny bez varovani.
- **Reseni:** Pri ValueError nastavit flash warning "Neplatny format datumu -- datum nebylo ulozeno".
- **Kde v kodu:** `app/routers/voting/session.py:200-206`
- **Narocnost:** nizka ~10 min
- **Rozhodnuti:** Opravit
- **Jak otestovat:** Zadat neplatne datum pri tvorbe hlasovani -- melo by byt varovani

---

## Top 5 doporuceni (podle dopadu)

| # | Navrh | Dopad | Slozitost | Cas | Zavisi na | Rozhodnuti | Priorita |
|---|-------|-------|-----------|-----|-----------|------------|----------|
| 1 | #31: CSV export -- opravit delimiter na strednik | Vysoky (rozbite CSV exporty v CZ Excelu) | Nizka | ~5 min | -- | Opravit | HNED |
| 2 | #35: Opravit emails_count aby pocital i email_secondary | Vysoky (nekonzistentni cisla v UI) | Nizka | ~10 min | -- | Opravit | HNED |
| 3 | #16: Flash zprava po invalidaci testu emailu | Vysoky (uzivatel nevi proc nemuze odeslat) | Nizka | ~15 min | -- | Opravit | HNED |
| 4 | #4: Validace duplicit pri tvorbe vlastnika | Vysoky (duplicity v datech) | Stredni | ~1 hod | -- | Opravit | BRZY |
| 5 | #29: Chybove flash zpravy by nemely auto-dismiss | Stredni (ztrata informace) | Nizka | ~15 min | -- | Opravit | HNED |

---

## Quick wins (nizka slozitost, okamzity efekt)

- [ ] #31: CSV export -- pridat `delimiter=';'` (~5 min)
- [ ] #35: emails_count -- pridat `email_secondary` do query (~10 min)
- [ ] #2: Dashboard podily -- pridat tooltip na "Podily: shoda" (~5 min)
- [ ] #29: Chybove flash zpravy -- neauto-dismiss pro `error` typ (~15 min)
- [ ] #16: Flash varovani po zmene obsahu emailu (~15 min)
- [ ] #37: Varovani pri neplatnem datumu (~10 min)
- [ ] #25: SMTP heslo -- pridat placeholder text (~15 min)
- [ ] #10: Loading spinner na tlacitko "Generovat listky" (~15 min)
- [ ] #11: Flash zprava po hromadnem zpracovani (~15 min)
- [ ] #3: Prazdny stav vyhledavani na dashboardu (~10 min)
