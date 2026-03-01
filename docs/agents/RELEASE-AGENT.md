# Release Agent – Příprava verze pro nasazení

> Spouštěj když chceš vydat novou verzi aplikace na USB nebo pro uživatele.
> Agent zkontroluje připravenost, připraví balíček a vytvoří changelog.

---

## Cíl

Připravit kompletní release balíček SVJ aplikace. Ověřit že vše funguje, vytvořit changelog a zabalit pro distribuci.

---

## Instrukce

### Fáze 1: PRE-RELEASE KONTROLA (nic neměň)

Projdi projekt a ověř připravenost k vydání:

#### 1.1 Kód
- Spusť všechny testy (`pytest`) — musí projít na 100%
- Žádné `TODO`, `FIXME`, `HACK` v kódu které blokují release
- Žádné hardcoded debug hodnoty (`print()`, `debug=True`, testovací emaily)
- Requirements.txt je kompletní a pinnutý

#### 1.2 Databáze
- Migrace fungují na čisté DB (smaž svj.db, spusť aplikaci, ověř že se vytvoří)
- Migrace fungují na existující DB (stávající svj.db se správně aktualizuje)
- Žádné breaking changes bez migračního skriptu

#### 1.3 Soubory
- `.gitignore` je kompletní (žádné citlivé soubory v repozitáři)
- `.env.example` existuje s placeholdery (ne skutečné hodnoty)
- `spustit.command` je aktuální a funguje
- `pripravit_usb.sh` je aktuální a funguje

#### 1.4 Dokumentace
- README.md je aktuální (instalace, spuštění, moduly)
- CLAUDE.md odpovídá realitě
- Changelog je připravený

#### 1.5 UI
- Spusť server a projdi KAŽDOU stránku v sidebar — žádné 500 chyby?
- Formuláře fungují (submit, validace)?
- Flash messages se zobrazují?

### Fáze 2: CHANGELOG

Porovnej aktuální stav s posledním tagem/release:

```bash
git log --oneline [poslední_tag]..HEAD
```

Vytvoř/aktualizuj `CHANGELOG.md`:

```markdown
## [verze] – YYYY-MM-DD

### Nové funkce
- [popis viditelný pro uživatele]

### Opravy
- [popis opravených chyb]

### Změny
- [změny v chování, UI úpravy]

### Technické
- [migrace, závislosti, interní změny]
```

### Fáze 3: PŘÍPRAVA BALÍČKU

Po schválení changelogu:

1. **Verze** — aktualizuj verzi v `app/main.py` nebo `pyproject.toml`
2. **Git tag:**
   ```bash
   git add -A
   git commit -m "release: vX.Y.Z"
   git tag -a vX.Y.Z -m "Release X.Y.Z – [stručný popis]"
   ```
3. **USB balíček** — spusť `pripravit_usb.sh` nebo připrav ručně:
   - Zkopíruj projekt (bez `.git/`, `__pycache__/`, `.venv/`, `data/svj.db`)
   - Přidej `wheels/` s offline balíčky pro aktuální Python
   - Přidej prázdný `data/` adresář
   - Ověř že `spustit.command` má executable flag: `chmod +x spustit.command`
4. **ZIP:** `SVJ-Sprava-vX.Y.Z.zip`
5. **Testovací spuštění** — rozbal ZIP do temp složky, spusť `spustit.command`, ověř funkčnost

### Fáze 4: REPORT

Na konci vypiš:

```
## Release Report – vX.Y.Z

### Pre-release kontrola
- Testy: ✅/❌ (X/Y prošlo)
- Čistá DB: ✅/❌
- Migrace existující DB: ✅/❌
- Všechny stránky: ✅/❌
- Dokumentace: ✅/❌

### Balíček
- ZIP: SVJ-Sprava-vX.Y.Z.zip (X MB)
- Git tag: vX.Y.Z
- Changelog: aktualizován

### Známé omezení
- [pokud nějaké jsou]
```

---

## Spuštění

V Claude Code zadej:

```
Přečti soubor RELEASE-AGENT.md a připrav release. Nejdřív proveď pre-release kontrolu, pak po schválení připrav balíček.
```
