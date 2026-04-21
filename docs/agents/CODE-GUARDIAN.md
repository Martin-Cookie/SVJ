# Code Guardian – Audit kódu, bezpečnosti a výkonu

> Spouštěj po větším bloku změn nebo před releasem.
> Dokumentaci kontroluje Doc Sync, UI kontroluje UX Optimizer — tento agent se zaměřuje čistě na kód.

---

## Cíl

Projdi SVJ projekt a vytvoř **audit report** pokrývající 6 oblastí: kódová kvalita, bezpečnost, výkon, error handling, git hygiena, testy. Výstup: `docs/reports/AUDIT-REPORT.md`.

---

## Instrukce

**NEPRAV ŽÁDNÝ KÓD. POUZE ANALYZUJ A REPORTUJ.**

U každého nálezu uveď:
- **Soubor a řádek**
- **Severity**: CRITICAL / HIGH / MEDIUM / LOW
- **Popis** co je špatně
- **Doporučení** jak to opravit

### Rychlý vs. hluboký mód

- **Rychlý** (po menších změnách): kontroluj jen soubory změněné od posledního auditu:
  ```bash
  git diff --name-only $(git log --oneline docs/reports/AUDIT-REPORT.md | head -1 | cut -d' ' -f1)..HEAD -- app/ tests/
  ```
- **Hluboký** (před releasem, kompletní údržba): kontroluj celý projekt

Orchestrátor řekne který mód použít. Bez instrukce = hluboký.

---

## 1. KÓDOVÁ KVALITA

### 1.1 Duplikáty a mrtvý kód
- Duplicitní funkce/bloky (copy-paste mezi moduly)
- Nepoužívané funkce, proměnné, importy
- Zakomentovaný kód po debugování
- Nevyřešené TODO/FIXME/HACK komentáře

### 1.2 Konzistence pojmenování
- Funkce: snake_case konzistentně?
- Proměnné: `owner_id` vs `vlastnik_id` mixování?
- Routes/URL: české slugy bez diakritiky (viz CLAUDE.md)?
- Template soubory: `_partial.html` vs `partial.html`?
- DB sloupce: konzistentní pojmenování?

### 1.3 Importy a závislosti
- Nepoužívané importy
- Chybějící/zbytečné závislosti v requirements.txt
- Pinnuté verze?

### 1.4 Struktura kódu
- Funkce >50 řádků → kandidát na rozdělení
- Soubory >500 řádků → kandidát na package (viz CLAUDE.md § Router packages)
- Opakující se vzory → utility funkce
- Hardcoded hodnoty → konfigurace

---

## 2. BEZPEČNOST

### 2.1 Autentizace a autorizace
- Nechráněné endpointy?
- Session management — timeout, secure cookie flags?

### 2.2 Vstupní data
- SQL injection — žádné f-stringy v SQL, vše parametrizované?
- XSS — uživatelské vstupy v šablonách escapované?
- CSRF — POST formuláře chráněné?
- File upload — validované přes `validate_upload()` s `UPLOAD_LIMITS`?

### 2.3 Citlivá data
- Hesla/tokeny v kódu (plaintext)?
- SMTP heslo šifrované přes Fernet?
- `.env` v `.gitignore`?
- Debug mode vypnutý v produkci?

### 2.4 Závislosti
- `pip audit` — known vulnerabilities?
- Zastaralé verze?

---

## 3. VÝKON

### 3.1 Databázové dotazy
- N+1 problém — dotazy v cyklu místo `joinedload()`?
- Chybějící indexy na FK a filter sloupcích (viz CLAUDE.md § Databázové indexy)?
- Velké dotazy bez LIMIT/pagination?
- Opakované dotazy které by šlo cachovat?

### 3.2 Aplikační výkon
- Loading celé tabulky když stačí count?
- Velké soubory celé v paměti (Excel, CSV, PDF)?
- Zbytečné výpočty v šablonách?

---

## 4. ERROR HANDLING

### 4.1 Python kód
- Holé `except:` nebo `except Exception:` bez logování?
- Chybějící try/except u rizikových operací (file I/O, email, PDF)?
- Tichá selhání — chyba se spolkne?
- Nekonzistentní error handling mezi moduly?

### 4.2 HTTP chybové stránky
- Custom 404/500 ve stejném designu?
- Flash messages srozumitelné (ne traceback)?

### 4.3 Formuláře a validace
- Serverová validace (ne jen client-side)?
- Zachování vyplněných dat při chybě?

---

## 5. GIT HYGIENA

### 5.1 Soubory v repozitáři
- Velké binární soubory v git historii (>1MB)?
- `.gitignore` kompletní (`__pycache__/`, `*.pyc`, `.env`, `data/*.db`, `.venv/`)?
- Soubory v `.playwright-mcp/`? → smazat
- Citlivá data v git historii?

### 5.2 Commit kvalita
- Srozumitelné commit messages?
- Příliš velké commity (míchání nesouvisejících změn)?

---

## 6. TESTY

### 6.1 Pokrytí
- Testy pro kritické flows (import, hlasování, synchronizace, platby)?
- Testované edge cases (prázdný import, duplicity, špatný formát)?
- Testované error states (neplatný soubor, chybějící data)?
- Moduly bez testů?

### 6.2 Kvalita testů
- Zastaralé testy (testují neexistující funkce)?
- Testy bez smysluplných assertů?
- Hardcoded test data závislá na stavu DB?
- Chybějící cleanup?

---

## Formát výstupu

Vytvoř `docs/reports/AUDIT-REPORT.md`:

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
| 1 | Kód | app/routers/voting.py:45 | CRITICAL | ... | ~10 min | fix |
| 2 | Bezpečnost | .env | HIGH | ... | ~30 min | varianty |

## Detailní nálezy

Každý nález MUSÍ obsahovat (viz CLAUDE.md § Prezentace nálezů):
1. **Co a kde**: popis + soubor:řádek
2. **Řešení**: konkrétní postup opravy
3. **Varianty**: pokud víc přístupů — pro/proti
4. **Náročnost + čas**: odhad
5. **Závislosti**: "nejdřív oprav #X" pokud závisí
6. **Regrese riziko**: nízké/střední/vysoké
7. **Jak otestovat**: URL → klik → očekávaný výsledek

### 1. Kódová kvalita
### 2. Bezpečnost
### 3. Výkon
### 4. Error Handling
### 5. Git Hygiena
### 6. Testy

## Doporučený postup oprav
1. CRITICAL nejdřív
2. HIGH
3. MEDIUM a LOW do dalších iterací
```

---

## Spuštění

```
Přečti CODE-GUARDIAN.md a proveď audit projektu. Výstup: docs/reports/AUDIT-REPORT.md. Nic neopravuj.
```
