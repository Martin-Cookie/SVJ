# Code Guardian – Agent pro čistotu, bezpečnost a kvalitu projektu

> Tento prompt vlož do Claude Code jako jednorázový příkaz, nebo ulož jako soubor a odkazuj na něj.
> Spouštěj ručně po větším bloku změn nebo před pushem na GitHub.

---

## Cíl

Projdi celý SVJ projekt a vytvoř **audit report** pokrývající 4 oblasti: kód, dokumentaci, UI šablony a bezpečnost. Na konci vytvoř soubor `docs/reports/AUDIT-REPORT.md` s nálezem a prioritami.

---

## Instrukce

**NEPRAV ŽÁDNÝ KÓD. POUZE ANALYZUJ A REPORTUJ.**

Projdi postupně všechny 4 oblasti níže. U každého nálezu uveď:
- **Soubor a řádek** kde je problém
- **Severity**: CRITICAL / HIGH / MEDIUM / LOW
- **Popis** co je špatně
- **Doporučení** jak to opravit

Na konci vytvoř souhrnnou tabulku a seřaď podle severity.

---

## 1. KÓDOVÁ KVALITA

### 1.1 Duplikáty a mrtvý kód
- Najdi duplicitní funkce, metody nebo bloky kódu (copy-paste mezi moduly)
- Najdi nepoužívané funkce, proměnné, importy
- Najdi zakomentovaný kód který tam zůstal po debugování
- Najdi TODO/FIXME/HACK komentáře které nebyly vyřešeny

### 1.2 Konzistence pojmenování
- Funkce: jsou všechny snake_case? Nejsou mixované konvence?
- Proměnné: konzistentní pojmenování napříč moduly (např. `owner_id` vs `vlastnik_id`)
- Routes/URL: konzistentní vzor (`/vlastnici` vs `/owners`, `/hlasovani` vs `/voting`)
- Template soubory: konzistentní pojmenování (`_partial.html` vs `partial.html`)
- DB modely: konzistentní pojmenování sloupců

### 1.3 Importy a závislosti
- Nepoužívané importy v Python souborech
- Chybějící závislosti v requirements.txt
- Zbytečné/duplicitní závislosti
- Verze závislostí — jsou pinnuté?

### 1.4 Struktura kódu
- Příliš dlouhé funkce (>50 řádků) — kandidáti na rozdělelní
- Příliš dlouhé soubory (>500 řádků) — kandidáti na refaktoring
- Opakující se vzory které by mohly být utility funkce
- Hardcoded hodnoty které by měly být v konfiguraci

---

## 2. BEZPEČNOST

### 2.1 Autentizace a autorizace
- Jsou všechny chráněné endpointy skutečně chráněné? (middleware/dependency)
- Jsou role kontrolovány správně? (admin/editor/reader)
- Existují endpointy bez kontroly přihlášení?
- Session management — timeout, secure cookie flags?

### 2.2 Vstupní data
- SQL injection — jsou všechny DB dotazy parametrizované? (žádné f-stringy v SQL)
- XSS — jsou všechny uživatelské vstupy v šablonách escapované?
- CSRF — jsou POST formuláře chráněné?
- File upload — jsou validované typy a velikosti souborů?

### 2.3 Citlivá data
- Hesla v kódu nebo konfiguraci (plaintext)
- API klíče, tokeny v kódu
- SMTP heslo — jak je uloženo?
- .env soubor — je v .gitignore?
- Debug mode — je vypnutý v produkci?

### 2.4 Závislosti
- Spusť `pip audit` (nebo zkontroluj ručně known vulnerabilities)
- Zastaralé verze s bezpečnostními problémy?

---

## 3. DOKUMENTACE

### 3.1 CLAUDE.md
- Odpovídá CLAUDE.md skutečnému stavu projektu?
- Jsou tam popsané všechny moduly které existují?
- Jsou tam instrukce které už neplatí?
- Chybí důležité instrukce pro správnou práci s projektem?
- Je tam popsaný tech stack správně?
- Jsou tam popsané konvence (pojmenování, struktura)?

### 3.2 README.md
- Obsahuje funkční návod na instalaci a spuštění?
- Jsou kroky kompletní? (venv, pip install, migrace, spuštění)
- Odpovídá popis projektu realitě?
- Je tam seznam závislostí?
- Je tam popis struktury projektu?

### 3.3 Komentáře v kódu
- Komplexní funkce bez komentářů
- Zastaralé komentáře (popis neodpovídá kódu)
- Chybějící docstringy na důležitých funkcích/třídách
- Magické hodnoty bez vysvětlení (proč 0.6? proč 31 sloupců?)

### 3.4 API dokumentace
- Jsou všechny endpointy zdokumentované?
- Odpovídají parametry a návratové hodnoty realitě?
- Chybějící popis chybových stavů?

---

## 4. UI / ŠABLONY

### 4.1 Konzistence komponent
- Tlačítka: stejné třídy, barvy, velikosti napříč stránkami?
- Tabulky: stejný styl hlaviček, řádků, zebra striping?
- Formuláře: stejný styl inputů, labelů, validačních hlášek?
- Modaly/dialogy: konzistentní styl?
- Flash messages: konzistentní styl (success/error/warning)?
- Ikony: ze stejné sady? Konzistentní velikost?

### 4.2 HTMX interakce
- Jsou všechny hx-* atributy funkční?
- Správné hx-target a hx-swap hodnoty?
- Loading indikátory u HTMX requestů?
- Error handling u HTMX requestů (co se stane při 500)?
- Nejsou tam duplikátní HTMX handlery?

### 4.3 Responsive design
- Funguje sidebar na mobilech? (skrytí/hamburger menu)
- Tabulky na malých obrazovkách — horizontální scroll?
- Formuláře na mobilech — full width?
- Font velikosti čitelné na mobilech?
- Touch targets dostatečně velké? (min 44x44px)

### 4.4 Přístupnost (WCAG AA)
- Všechny inputy mají `<label>` nebo `aria-label`?
- Obrázky mají `alt` text?
- Dostatečný barevný kontrast? (min 4.5:1)
- Fokus viditelný u interaktivních prvků?
- Správné heading hierarchy (h1 → h2 → h3, ne přeskakování)?
- Formuláře mají error messages propojené s inputy?

---

## 5. VÝKON

### 5.1 Databázové dotazy
- N+1 problém — dotazy v cyklu místo JOIN nebo eager loading?
- Chybějící indexy na sloupcích používaných ve WHERE/ORDER BY?
- SELECT * místo výběru konkrétních sloupců?
- Velké dotazy bez LIMIT/pagination?
- Opakované dotazy které by šlo cachovat?

### 5.2 Aplikační výkon
- Zbytečné načítání dat (loading celé tabulky když potřebuji jen count)?
- Synchronní operace které by mohly být async (odesílání emailů)?
- Velké soubory načítané celé do paměti (Excel, CSV, PDF)?
- Template rendering — zbytečné výpočty v šablonách?

---

## 6. ERROR HANDLING

### 6.1 Python kód
- Holé `except:` nebo `except Exception:` bez logování?
- Chybějící try/except u rizikových operací (file I/O, email, PDF parsing)?
- Tichá selhání — chyba se spolkne a uživatel neví co se stalo?
- Nekonzistentní error handling mezi moduly?

### 6.2 HTTP chybové stránky
- Existuje custom 404 stránka?
- Existuje custom 500 stránka?
- Jsou chybové stránky ve stejném designu jako zbytek aplikace?
- Jsou error flash messages srozumitelné pro uživatele (ne traceback)?

### 6.3 Formuláře a validace
- Jsou všechny formuláře validovány na serveru (ne jen client-side)?
- Srozumitelné chybové hlášky u validace?
- Zachování vyplněných dat při chybě (ne reset formuláře)?

---

## 7. GIT HYGIENE

### 7.1 Soubory v repozitáři
- Velké binární soubory v git historii (PDF, Excel, obrázky >1MB)?
- Jsou v .gitignore: `__pycache__/`, `*.pyc`, `.env`, `data/*.db`, `venv/`?
- Jsou v repozitáři soubory které tam nepatří (lokální konfigurace, IDE soubory)?
- **Existují soubory v `.playwright-mcp/`?** (screenshoty, logy z testování) → smazat: `rm -rf .playwright-mcp/*.log .playwright-mcp/*.png .playwright-mcp/*.jpeg`
- Citlivá data v git historii (hesla, klíče v předchozích commitech)?

### 7.2 Commit kvalita
- Srozumitelné commit messages?
- Nejsou commity příliš velké (míchaní nesouvisejících změn)?

---

## 8. TESTY

### 8.1 Pokrytí
- Existují testy pro všechny kritické flows (import, hlasování, synchronizace)?
- Jsou testovány edge cases (prázdný import, duplicitní data, špatný formát)?
- Jsou testovány error states (neplatný soubor, chybějící data)?
- Pokrytí dle modulů — které moduly nemají žádné testy?

### 8.2 Kvalita testů
- Zastaralé testy které testují funkce co už neexistují?
- Testy které vždy projdou (neassertují nic smysluplného)?
- Hardcoded test data které závisí na stavu DB?
- Chybějící cleanup po testech (testovací data zůstávají)?

---

## Formát výstupu

Vytvoř soubor `docs/reports/AUDIT-REPORT.md` s tímto formátem:

```markdown
# SVJ Audit Report – [YYYY-MM-DD]

## Souhrn
- CRITICAL: X
- HIGH: X
- MEDIUM: X
- LOW: X

## Souhrnná tabulka

| # | Oblast | Soubor | Severity | Problém | Čas | Rozhodnutí |
|---|--------|--------|----------|---------|-----|------------|
| 1 | Kód | app/routers/voting.py:45 | CRITICAL | SQL injection v ... | ~10 min | 🔧 |
| 2 | Bezpečnost | .env | HIGH | SMTP heslo v plaintextu | ~30 min | ❓ varianty |
| ... | ... | ... | ... | ... | ... | ... |

Legenda: 🔧 = jen opravit, ❓ = potřeba rozhodnutí uživatele (více variant)

## Detailní nálezy

Každý nález MUSÍ obsahovat (viz CLAUDE.md § Prezentace nálezů):
1. **Co a kde**: popis + URL/stránka/akce kde se problém projevuje
2. **Řešení**: konkrétní postup opravy (ne vágní "vylepšit")
3. **Varianty**: pokud existuje víc přístupů — pro/proti
4. **Náročnost + čas**: nízká/střední/vysoká + odhad (~5 min, ~1 hod)
5. **Závislosti**: "nejdřív oprav #X" pokud na sobě závisí
6. **Regrese riziko**: nízké/střední/vysoké — může oprava rozbít něco?
7. **Jak otestovat**: krok za krokem (URL → klik → očekávaný výsledek)

### 1. Kódová kvalita
[detaily...]

### 2. Bezpečnost
[detaily...]

### 3. Dokumentace
[detaily...]

### 4. UI / Šablony
[detaily...]

### 5. Výkon
[detaily...]

### 6. Error Handling
[detaily...]

### 7. Git Hygiene
[detaily...]

### 8. Testy
[detaily...]

## Doporučený postup oprav
1. Nejdřív oprav CRITICAL
2. Pak HIGH
3. MEDIUM a LOW naplánuj do dalších iterací
```

---

## Spuštění

V Claude Code zadej:

```
Přečti soubor CODE-GUARDIAN.md a proveď kompletní audit projektu podle instrukcí. Výstupem je docs/reports/AUDIT-REPORT.md. Nic neopravuj, pouze reportuj.
```
