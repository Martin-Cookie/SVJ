# Backup Agent – Kontrola integrity záloh a obnovy

> Spouštěj periodicky nebo před důležitými změnami v DB struktuře.
> Agent ověří že zálohovací a obnovovací mechanismus funguje správně.

---

## Cíl

Ověřit že zálohy jsou kompletní, obnova funguje a data se neztratí. Záloha která nejde obnovit je k ničemu.

---

## Instrukce

### Fáze 1: ANALÝZA ZÁLOHOVACÍHO SYSTÉMU

#### 1.1 Zálohovací kód
- Projdi zálohovací endpoint/funkci — co přesně se zálohuje?
- Zálohuje se:
  - [ ] Databáze (`svj.db`)
  - [ ] Upload soubory (`data/uploads/`)
  - [ ] Konfigurace (`.env`, nastavení SMTP)
  - [ ] Generované soubory (`data/generated/`)
- Formát zálohy (ZIP, folder, jiné)?
- Kam se ukládají zálohy?
- Je záloha pojmenovaná s timestampem?

#### 1.2 Obnovovací kód
- Projdi obnovovací endpoint/funkci
- Ověří se integrita zálohy před obnovou?
- Co se stane se stávajícími daty při obnově? (přepíše / mergne / selže)
- Funguje obnova ze zálohy vytvořené starší verzí aplikace?

### Fáze 2: TESTOVÁNÍ (na kopii, ne na produkčních datech)

#### 2.1 Vytvoření zálohy
1. Spusť zálohovací funkci
2. Ověř že ZIP/složka obsahuje VŠECHNY potřebné soubory
3. Ověř velikost — odpovídá očekávání?
4. Ověř že záloha jde otevřít/rozbalit bez chyb

#### 2.2 Obnova ze zálohy
1. Zkopíruj aktuální `data/` jako `data_backup_test/`
2. Smaž `data/svj.db`
3. Spusť obnovu ze zálohy
4. Spusť aplikaci — funguje?
5. Zkontroluj:
   - Počet vlastníků — stejný?
   - Počet jednotek — stejný?
   - Počet hlasování — stejný?
   - Upload soubory — přítomné?
   - SMTP nastavení — zachované?
6. Vrať původní data: `mv data_backup_test/* data/`

#### 2.3 Migrace při obnově
- Vytvoř zálohu
- Přidej nový sloupec do modelu (simulace nové verze)
- Obnov ze zálohy staré verze
- Funguje migrace automaticky?
- Neztrácí se data v nových sloupcích?

#### 2.4 Edge cases
- Co se stane při obnově poškozené zálohy? (graceful error nebo crash?)
- Co se stane při obnově zálohy z jiného SVJ? (jiná data)
- Co se stane když během obnovy dojde místo na disku?
- Funguje záloha/obnova na USB (jiný počítač)?

### Fáze 3: REPORT

```
## Backup Integrity Report – [datum]

### Zálohovací systém
- Formát: [ZIP/folder/...]
- Obsah: DB ✅/❌ | Uploads ✅/❌ | Config ✅/❌ | Generated ✅/❌
- Cesta: [kam se ukládají]

### Test vytvoření zálohy
- Záloha vytvořena: ✅/❌
- Velikost: X MB
- Obsah kompletní: ✅/❌

### Test obnovy
- Obnova proběhla: ✅/❌
- Data konzistentní: ✅/❌
  - Vlastníci: [počet] ✅/❌
  - Jednotky: [počet] ✅/❌
  - Hlasování: [počet] ✅/❌
  - Soubory: ✅/❌
- Migrace při obnově: ✅/❌

### Nalezené problémy
| # | Problém | Severity | Doporučení |
|---|---------|----------|------------|
| 1 | ...     | ...      | ...        |

### Doporučení
- [co zlepšit v zálohovacím systému]
```

---

## Spuštění

V Claude Code zadej:

```
Přečti soubor BACKUP-AGENT.md a proveď kontrolu integrity zálohovacího systému. POZOR: testuj na kopiích dat, nikdy na produkčních.
```
