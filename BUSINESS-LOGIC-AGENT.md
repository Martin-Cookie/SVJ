# Business Logic Agent – Extrakce business logiky z kódu

> Spouštěj když potřebuješ zdokumentovat co aplikace dělá, před přepisem do nového stacku,
> nebo pro onboarding nového vývojáře / předání projektu.

---

## Cíl

Projít celý projekt a extrahovat veškerou business logiku, procesy, pravidla a skryté know-how
do strukturovaného dokumentu. Výstupem jsou DVA soubory:

1. **BUSINESS-LOGIC.md** — technický dokument pro vývojáře / Clauda
2. **BUSINESS-SUMMARY.md** — srozumitelný souhrn pro netechnického člověka

---

## Instrukce

**NEPRAV ŽÁDNÝ KÓD. POUZE ANALYZUJ A DOKUMENTUJ.**

Projdi VŠECHNY soubory projektu — modely, routery/API, services, šablony/komponenty, konfigurace, migrace, seed data. Čti kód řádek po řádku a hledej business logiku ukrytou v kódu.

---

## 1. BUSINESS PROCESY (workflow)

Pro každý hlavní modul/feature aplikace zdokumentuj kompletní workflow:

### Co hledat:
- Vícekoakové procesy (vytvoření → úprava → schválení → dokončení)
- Stavové automaty (draft → active → completed → archived)
- Uživatelské flow (co uživatel klikne, co se stane, kam je přesměrován)
- Podmíněné větvení (pokud X, tak Y, jinak Z)
- Automatické akce (co se děje na pozadí po uživatelské akci)

### Jak dokumentovat:
```markdown
### [Název procesu]

**Účel:** Co tento proces řeší

**Kroky:**
1. Uživatel udělá X
2. Systém zkontroluje Y
3. Pokud podmínka → krok 4a, jinak → krok 4b
4a. Systém vytvoří Z a notifikuje...
4b. Systém zobrazí chybu...

**Kde v kódu:** `soubor.py:funkce()` řádky XX-YY

**Stavový diagram:**
[stav1] → akce → [stav2] → akce → [stav3]
```

---

## 2. BUSINESS PRAVIDLA

### Co hledat:
- **Validační pravidla** — co se kontroluje při vstupu dat (formát, rozsah, povinnost, unikátnost)
- **Výpočetní pravidla** — vzorce, konverze, zaokrouhlování, měnové přepočty
- **Prahy a limity** — magická čísla v kódu (proč 0.6? proč 31 sloupců? proč 80 CZK?)
- **Pořadí operací** — co se musí stát před čím (FK závislosti, cascade)
- **Defaultní hodnoty** — co se nastaví když uživatel nevyplní pole
- **Formátovací pravidla** — jak se zobrazují data (datum, měna, procenta, jména)
- **Řazení a filtrování** — v jakém pořadí se data zobrazují, jak fungují filtry
- **Deduplikace** — jak se řeší duplicitní data
- **Párování/matching** — jak se propojují záznamy z různých zdrojů

### Jak dokumentovat:
```markdown
### [Název pravidla]

**Pravidlo:** [stručný popis co platí]
**Důvod:** [proč to pravidlo existuje — pokud je zřejmý z kódu/komentářů]
**Implementace:** [jak je to v kódu realizováno]
**Kde v kódu:** `soubor:řádek`
**Hodnoty:** [konkrétní čísla, prahy, konstanty]
```

---

## 3. DATOVÝ MODEL

### Co hledat:
- **Entity a jejich účel** — ne jen název tabulky, ale CO reprezentuje v business doméně
- **Relace a jejich sémantika** — ne jen FK, ale CO ta vazba znamená (vlastník VLASTNÍ jednotku, ne jen "owner_id → unit_id")
- **Constraints** — unique, not null, check, cascade delete — a PROČ existují
- **Enum hodnoty** — co každá hodnota znamená v business kontextu
- **Computed/derived atributy** — hodnoty které se nepočítají z DB ale za runtime
- **Temporální aspekty** — platnost záznamů, historické vs aktuální data
- **Soft delete vs hard delete** — co se archivuje vs co se maže

### Jak dokumentovat:
```markdown
### [Název entity]

**Business účel:** [co tato entita reprezentuje v reálném světě]
**Klíčové atributy:**
- `atribut` — [business význam, ne jen datový typ]
- `status` — [výčet hodnot + co každá znamená]

**Relace:**
- → [Entita2]: [business význam vazby] (1:N / M:N)

**Pravidla:**
- [co musí platit, co se nesmí stát]

**Životní cyklus:**
[vytvoření] → [stavy] → [ukončení/smazání]
```

---

## 4. EDGE CASES A WORKAROUNDY

### Co hledat:
- Komentáře `# POZOR`, `# HACK`, `# WORKAROUND`, `# BUG`, `# XXX`, `# FIXME`
- Try/except bloky s nestandardním chováním
- Podmínky které ošetřují speciální případy (`if typ == "SJM"`, `if currency != "CZK"`)
- Fallback hodnoty (`or 0`, `or ""`, `default=80`)
- Konverze typů (`int()`, `str()`, `cast()`) — často maskují nesrovnalosti v datech
- Platform-specific kód (macOS vs Linux cesty, locale specifika)
- Encoding workaroundy (BOM, UTF-8, diakritika)
- Hardcoded hodnoty které by měly být konfigurovatelné

### Jak dokumentovat:
```markdown
### [Název edge case]

**Problém:** [co se stane bez tohoto workaroundu]
**Příčina:** [proč problém vzniká]
**Řešení:** [jak je to ošetřeno v kódu]
**Kde v kódu:** `soubor:řádek`
**Riziko:** [co se stane když se tohle změní/odstraní]
```

---

## 5. INTEGRACE

### Co hledat:
- **Import dat** — z jakých zdrojů, jaký formát, jak se mapují sloupce, jak se řeší konflikty
- **Export dat** — do jakých formátů, co se exportuje, jaké filtry se aplikují
- **Externí API** — jaké služby se volají, autentizace, rate limity, fallbacky
- **Souborový systém** — kam se ukládají soubory, jaký naming, jak se čistí
- **Email/notifikace** — kdy se posílají, komu, jaký obsah, SMTP konfigurace
- **Tisk/PDF** — jak se generují, jaký layout, jaké knihovny

### Jak dokumentovat:
```markdown
### [Název integrace]

**Směr:** Import / Export / Obousměrná
**Zdroj/Cíl:** [odkud/kam data tečou]
**Formát:** [Excel, CSV, PDF, API, ...]
**Mapování:** [které sloupce/pole se jak mapují]
**Validace:** [co se kontroluje při importu]
**Chybové stavy:** [co se stane když import selže]
**Kde v kódu:** `soubor:funkce`
```

---

## Formát výstupu

### BUSINESS-LOGIC.md (technický)

```markdown
# Business logika — [Název projektu]

> Automaticky extrahováno z kódu dne [datum].
> Tento dokument popisuje veškerou business logiku implementovanou v aplikaci.

## Obsah
1. Business procesy
2. Business pravidla
3. Datový model
4. Edge cases a workaroundy
5. Integrace

---

## 1. Business procesy
### 1.1 [Proces A]
...
### 1.2 [Proces B]
...

## 2. Business pravidla
### 2.1 [Pravidlo A]
...

## 3. Datový model
### 3.1 [Entita A]
...

## 4. Edge cases a workaroundy
### 4.1 [Edge case A]
...

## 5. Integrace
### 5.1 [Integrace A]
...

---

## Appendix: Důležité konstanty a konfigurace

| Konstanta | Hodnota | Kde | Účel |
|-----------|---------|-----|------|
| ... | ... | ... | ... |
```

### BUSINESS-SUMMARY.md (netechnický)

```markdown
# Co aplikace dělá — [Název projektu]

> Srozumitelný popis pro netechnického člověka.
> Automaticky vytvořeno z analýzy kódu dne [datum].

## Přehled
[2-3 věty co aplikace řeší a pro koho je]

## Hlavní funkce

### [Funkce 1 — srozumitelný název]
[Popis co funkce dělá z pohledu uživatele, bez technických detailů.
Jaký problém řeší? Jak se používá? Co je výstup?]

### [Funkce 2]
...

## Jak spolu věci souvisí
[Popis hlavních vztahů: kdo vlastní co, co na čem závisí,
jaký je typický průběh práce s aplikací]

## Důležitá pravidla
[Pravidla která by měl znát každý kdo s aplikací pracuje,
bez technického žargonu]

## Omezení a specifika
[Co aplikace NEUMÍ, kde jsou hranice, na co si dát pozor]
```

---

## Spuštění

V Claude Code zadej:

```
Přečti soubor BUSINESS-LOGIC-AGENT.md a proveď kompletní extrakci business logiky z projektu. Výstupem jsou soubory BUSINESS-LOGIC.md a BUSINESS-SUMMARY.md. Nic v kódu neměň.
```
