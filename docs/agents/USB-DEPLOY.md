# USB Deploy Agent – Přenos aplikace na jiný Mac

> Spouštěj když chceš přenést aplikaci na jiný Mac přes USB disk nebo síť.
> Agent provede přípravu, přenos a ověření na cílovém počítači.

---

## Cíl

Bezpečně přenést SVJ aplikaci na jiný Mac tak, aby fungovala na první pokus. Zahrnuje přípravu zdrojového Macu, kopírování na USB, setup cílového Macu a verifikaci.

---

## Známé problémy a řešení (lessons learned)

### 1. Starlette 1.0.0 breaking change
- **Problém**: `TemplateResponse("name", {"request": req})` nefunguje ve Starlette 1.0.0 — TypeError v Jinja2 LRUCache (`unhashable type: 'dict'`)
- **Řešení**: Projekt používá `requirements.txt` s pinovanými verzemi (starlette==0.49.3). Vždy instalovat přes `pip install -r requirements.txt`, NIKDY volné `pip install fastapi jinja2...`
- **Detekce**: Chyba `TypeError: cannot use 'tuple' as a dict key` nebo `unhashable type: 'dict'` při načtení jakékoliv stránky

### 2. Python 3.14 nekompatibilita
- **Problém**: Python 3.14 (bleeding edge) má breaking changes v Jinja2 LRUCache
- **Řešení**: Na cílovém Macu nainstalovat Python 3.12 přes Homebrew: `brew install python@3.12`
- **Minimum**: Python 3.9+, doporučeno 3.11 nebo 3.12

### 3. Homebrew na novém Macu
- **Problém**: Homebrew není předinstalovaný na macOS
- **Instalace**:
  ```bash
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  ```
- **Po instalaci** (Apple Silicon M1/M2/M3/M4):
  ```bash
  echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
  eval "$(/opt/homebrew/bin/brew shellenv)"
  ```
- Bez tohoto kroku `brew: command not found`

### 4. Port 8000 obsazený
- **Problém**: Předchozí proces stále běží na portu 8000
- **Řešení**: `lsof -ti :8000 | xargs kill`

### 5. macOS rsync
- **Problém**: Systémový rsync na macOS nepodporuje `--info=progress2`
- **Řešení**: Používat `--progress` místo `--info=progress2`

### 6. .venv je nepřenositelná
- **Pravidlo**: NIKDY nekopírovat `.venv/` — obsahuje absolutní cesty
- Na cílovém Macu se venv vytvoří automaticky přes `spustit.command`

### 7. SQLite WAL checkpoint
- **Pravidlo**: Před kopírováním DB VŽDY spustit `PRAGMA wal_checkpoint(TRUNCATE)`
- Jinak se WAL soubor nezkopíruje a data se ztratí
- Skript `pripravit_prenos.sh` to dělá automaticky

### 8. iCloud cesta s mezerami
- **Problém**: iCloud cesta obsahuje `Mobile Documents/com~apple~CloudDocs/` — mezery a speciální znaky
- **Řešení**: Vždy celou cestu obalit uvozovkami: `cd "/Users/mabe/Library/Mobile Documents/com~apple~CloudDocs/SVJ"`

---

## Instrukce

### Fáze 1: PŘÍPRAVA ZDROJOVÉHO MACU (~5 min)

#### 1.1 Ověř stav projektu
```bash
cd ~/Projects/SVJ
git status           # čistý strom?
pytest               # testy procházejí?
```

#### 1.2 Spusť přenosový skript
```bash
./pripravit_prenos.sh /Volumes/NAZEV_USB
```

Skript automaticky:
1. **Checkpoint SQLite** — sloučí WAL do hlavní DB
2. **Stáhne wheels** — offline balíčky z `requirements.txt`
3. **Zkopíruje projekt** — rsync bez `.venv/`, `.git/`, `__pycache__/`, `.env`
4. **Zkopíruje DATA** — z Dropboxu (`/Users/martinkoci/Library/CloudStorage/Dropbox/Dokumenty/SVJ/DATA`)

#### 1.3 Ověř výstup
- Zkontroluj velikost (~350 MB)
- Zkontroluj že `requirements.txt` je v kopii
- Zkontroluj že `spustit.command` je v kopii
- Zkontroluj že `data/svj.db` je v kopii
- Zkontroluj že `wheels/` obsahuje .whl soubory

### Fáze 2: SETUP CÍLOVÉHO MACU (~15 min)

#### 2.1 Zkontroluj systém
Na cílovém Macu v Terminálu:

```bash
python3 --version    # Potřeba 3.9+, ideálně 3.12
```

**Pokud Python chybí nebo je 3.14+:**
1. Nainstaluj Homebrew (pokud chybí):
   ```bash
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
   eval "$(/opt/homebrew/bin/brew shellenv)"
   ```
2. Nainstaluj Python 3.12:
   ```bash
   brew install python@3.12
   ```

#### 2.2 Zkopíruj projekt z USB
Zkopíruj složku `SVJ/` z USB na cílový Mac, např.:
```bash
cp -R /Volumes/NAZEV_USB/SVJ/ ~/SVJ/
```
Nebo přes Finder drag & drop.

#### 2.3 Spusť aplikaci
Dvakrát klikni na `spustit.command` ve Finderu.

Nebo v Terminálu:
```bash
cd ~/SVJ
chmod +x spustit.command
./spustit.command
```

Skript automaticky:
1. Zkontroluje Python, disk, DB, DATA, wheels
2. Vytvoří `.venv` s Python 3.12
3. Nainstaluje závislosti z `requirements.txt` (offline z wheels nebo online)
4. Vytvoří `.env` z šablony
5. Spustí server na `http://localhost:8000`
6. Otevře prohlížeč

### Fáze 3: VERIFIKACE (~5 min)

#### 3.1 Základní kontroly
- [ ] Dashboard se načte (`http://localhost:8000`)
- [ ] Sidebar navigace funguje (všechny položky)
- [ ] Vlastníci — seznam se zobrazí, hledání funguje
- [ ] Jednotky — seznam se zobrazí
- [ ] Platby — matice se načte

#### 3.2 SMTP nastavení (pokud potřeba odesílat emaily)
Jdi na **Nastavení** a nastav SMTP:

**Gmail:**
- Server: `smtp.gmail.com`
- Port: `587`
- Uživatel: `uctarna.svj@gmail.com`
- Heslo: App Password (16-znakový kód)
- Jméno: `Jiří Krátký`
- Email: `uctarna.svj@gmail.com`
- TLS: zaškrtnout

**Seznam.cz:**
- Server: `smtp.seznam.cz`
- Port: `465`
- Uživatel: `svj1098@seznam.cz`
- Heslo: heslo k účtu
- Jméno: `Jiří Krátký`
- Email: `svj1098@seznam.cz`
- TLS: zaškrtnout

#### 3.3 Odeslat testovací email
V Nastavení klikni na **Test spojení** — musí hlásit OK.

### Fáze 4: TROUBLESHOOTING

#### Aplikace nenaběhne
1. **Port obsazený**: `lsof -ti :8000 | xargs kill`
2. **Chybí Python**: Nainstalovat přes Homebrew (viz 2.1)
3. **Wheels nefungují** (jiná verze Pythonu): Skript automaticky stáhne online

#### TypeError / unhashable type / Jinja2 chyba
```bash
# Problém se Starlette verzí — přeinstaluj z requirements.txt:
.venv/bin/pip install -r requirements.txt
```

#### Email jde do skryté kopie místo Komu
- Opraveno v kódu (RFC 2047 enkódování hlaviček)
- Ověř že máš aktuální verzi kódu

#### Chyba 451 při odesílání emailu
- Dočasná chyba SMTP serveru — zkus znovu za minutu
- Klikni "Zopakovat neúspěšné" v rozesílce

#### LibreOffice nenalezen
- Volitelné — potřeba jen pro generování PDF lístků
- Instalace: `brew install --cask libreoffice`

---

## Spuštění

V Claude Code zadej:

```
Přečti soubor docs/agents/USB-DEPLOY.md a proveď přenos aplikace na USB.
Cíl: /Volumes/NAZEV_USB
```

Nebo pro setup na cílovém Macu:

```
Přečti soubor docs/agents/USB-DEPLOY.md a proveď setup na cílovém Macu.
Projekt je v: /cesta/k/SVJ/
```
