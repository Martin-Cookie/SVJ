# USB Deploy Agent – Přenos aplikace na jiný Mac

> Spouštěj pro přenos aplikace na jiný Mac přes USB nebo síť.

---

## Cíl

Bezpečně přenést SVJ aplikaci na jiný Mac tak, aby fungovala na první pokus.

---

## Známé problémy

| # | Problém | Řešení |
|---|---------|--------|
| 1 | Starlette 1.0.0 breaking change | Vždy `pip install -r requirements.txt`, nikdy volné `pip install` |
| 2 | Python 3.14 nekompatibilita | Instalovat Python 3.12: `brew install python@3.12` |
| 3 | Homebrew chybí | `/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"` + Apple Silicon: `echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile` |
| 4 | Port 8000 obsazený | `lsof -ti :8000 \| xargs kill` |
| 5 | macOS rsync | `--progress` místo `--info=progress2` |
| 6 | .venv nepřenositelná | NIKDY nekopírovat — vytvoří se automaticky přes `spustit.command` |
| 7 | SQLite WAL | Před kopírováním: `PRAGMA wal_checkpoint(TRUNCATE)`. `pripravit_prenos.sh` to dělá |
| 8 | iCloud cesta s mezerami | Celou cestu obalit uvozovkami |

---

## Instrukce

### Fáze 1: PŘÍPRAVA ZDROJOVÉHO MACU (~5 min)

1. Ověř stav: `git status` (čistý?), `pytest` (prochází?)
2. Spusť: `./pripravit_prenos.sh /Volumes/NAZEV_USB`
   - Checkpoint SQLite, stáhne wheels, rsync projektu (bez .venv/.git), kopie DATA z Dropboxu
3. Ověř výstup: ~350 MB, `requirements.txt`, `spustit.command`, `data/svj.db`, `wheels/*.whl`

### Fáze 2: SETUP CÍLOVÉHO MACU (~15 min)

1. **Python**: `python3 --version` → potřeba 3.9+, ideálně 3.12
   - Chybí/3.14+? → Homebrew + `brew install python@3.12`
2. **Kopíruj** z USB: `cp -R /Volumes/USB/SVJ/ ~/SVJ/`
3. **Spusť**: dvakrát klikni `spustit.command` (nebo `chmod +x && ./spustit.command`)
   - Auto: kontrola Python/disk/DB, vytvoření .venv, instalace závislostí, .env, server na :8000

### Fáze 3: VERIFIKACE (~5 min)

- [ ] Dashboard na `http://localhost:8000`
- [ ] Sidebar navigace funguje
- [ ] Vlastníci — seznam, hledání
- [ ] Jednotky — seznam
- [ ] Platby — matice

#### SMTP (pokud potřeba)
- **Gmail**: smtp.gmail.com:587, TLS, App Password
- **Seznam**: smtp.seznam.cz:465, TLS
- Test spojení v Nastavení

### Fáze 4: TROUBLESHOOTING

| Symptom | Fix |
|---------|-----|
| Nenaběhne | `lsof -ti :8000 \| xargs kill` nebo instalovat Python |
| TypeError/unhashable/Jinja2 | `.venv/bin/pip install -r requirements.txt` |
| Email do skryté kopie | Aktualizovat kód (RFC 2047 fix) |
| Chyba 451 SMTP | Zopakovat za minutu, "Zopakovat neúspěšné" |
| LibreOffice chybí | `brew install --cask libreoffice` (jen pro PDF lístky) |

---

## Spuštění

```
Přečti USB-DEPLOY.md a proveď přenos na USB. Cíl: /Volumes/NAZEV_USB
```

Pro setup na cílovém Macu:
```
Přečti USB-DEPLOY.md a proveď setup. Projekt: /cesta/k/SVJ/
```
