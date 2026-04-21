# Release Agent – Příprava verze pro nasazení

> Spouštěj před vydáním nové verze. Zkontroluje připravenost, vytvoří changelog a balíček.

---

## Cíl

Připravit release balíček SVJ aplikace: pre-release kontrola → changelog → git tag → ZIP.

---

## Instrukce

### Kontext od orchestrátora

Pokud orchestrátor předá výsledky (PASS/FAIL z P/R/V, nálezy z Code Guardian/Test Agent), ověř že CRITICAL nálezy jsou vyřešené. Pokud ne → varuj a navrhni odložení release.

### Fáze 1: PRE-RELEASE KONTROLA

#### Kód
- `pytest` — 100% PASSED
- Žádné blokující TODO/FIXME/HACK
- Žádné debug hodnoty (`print()`, `debug=True`, testovací emaily)
- `requirements.txt` kompletní a pinnutý

#### Databáze
- Migrace na čisté DB (smaž svj.db, spusť, ověř vytvoření)
- Migrace na existující DB (stávající svj.db se aktualizuje)

#### Soubory
- `.gitignore` kompletní, `.env.example` s placeholdery
- `spustit.command` aktuální + executable
- `pripravit_prenos.sh` aktuální

#### Dokumentace
- README.md, CLAUDE.md aktuální

#### UI
- Spusť server, projdi KAŽDOU stránku v sidebaru — žádné 500?

### Fáze 2: CHANGELOG

```bash
git log --oneline $(git describe --tags --abbrev=0 2>/dev/null || echo HEAD~20)..HEAD
```

Vytvoř/aktualizuj `CHANGELOG.md`:
```markdown
## [verze] – YYYY-MM-DD
### Nové funkce
### Opravy
### Změny
### Technické
```

### Fáze 3: BALÍČEK (po schválení)

1. Aktualizuj verzi v `pyproject.toml`
2. Git tag:
   ```bash
   git add -A && git commit -m "release: vX.Y.Z"
   git tag -a vX.Y.Z -m "Release X.Y.Z – [popis]"
   ```
3. USB balíček přes `pripravit_prenos.sh` nebo ručně (bez `.git/`, `__pycache__/`, `.venv/`, `data/svj.db`)
4. ZIP: `SVJ-Sprava-vX.Y.Z.zip`
5. Testovací spuštění — rozbal ZIP, spusť `spustit.command`, ověř funkčnost

### Fáze 4: REPORT

```
## Release Report – vX.Y.Z

### Pre-release kontrola
Testy: .../... | Čistá DB: ... | Migrace: ... | UI: ... | Docs: ...

### Balíček
ZIP: SVJ-Sprava-vX.Y.Z.zip (X MB) | Tag: vX.Y.Z | Changelog: aktualizován

### Známá omezení
[pokud jsou]
```

---

## Spuštění

```
Přečti RELEASE-AGENT.md a připrav release. Nejdřív pre-release kontrola, pak po schválení balíček.
```
