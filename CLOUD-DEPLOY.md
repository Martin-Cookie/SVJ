# Cloud Deploy Agent – Nasazení SVJ aplikace do cloudu

> Spusť když budeš chtít přejít z lokálního/USB nasazení na cloudové.
> Agent analyzuje projekt, navrhne infrastrukturu a připraví nasazení.

---

## Cíl

Připravit SVJ aplikaci pro nasazení do cloudu — aby k ní měli členové SVJ přístup přes internet bez USB.

---

## Instrukce

### Fáze 1: ANALÝZA PŘIPRAVENOSTI

#### 1.1 Závislosti na lokálním prostředí
- SQLite databáze — cesta hardcoded nebo konfigurovatelná?
- Upload soubory — lokální filesystem nebo konfigurovatelné úložiště?
- LibreOffice — je vyžadován? Pro které funkce?
- `spustit.command` — macOS specifické věci?
- Absolutní cesty v kódu?
- `.env` konfigurace — co vše je konfigurovatelné?

#### 1.2 Bezpečnost pro internet
- Autentizace implementovaná? (bez ní NIKDY nevystavovat na internet)
- HTTPS — aplikace je připravená na proxy (X-Forwarded-For, X-Forwarded-Proto)?
- CSRF ochrana na formulářích?
- Rate limiting?
- Session bezpečnost (secure cookie, httponly, samesite)?
- Debug mode vypnutý?
- Citlivá data v kódu?

#### 1.3 Výkon pro víceuživatelský přístup
- SQLite zvládne souběžné přístupy? (WAL mode?)
- Session storage (in-memory vs persistent)?
- Statické soubory — CDN nebo lokální?

### Fáze 2: DOPORUČENÍ PLATFORMY

Na základě analýzy navrhni nejlepší variantu. Porovnej:

#### Varianta A: VPS (Virtual Private Server)
- **Kdy:** Plná kontrola, SQLite stačí, nízký provoz
- **Příklad:** Hetzner, DigitalOcean, Wedos
- **Cena:** od 100 Kč/měsíc
- **Stack:** Ubuntu + nginx + gunicorn/uvicorn + systemd + Let's Encrypt
- **Pro:** Jednoduché, levné, SQLite funguje přímo
- **Proti:** Ruční správa serveru, zálohy, aktualizace

#### Varianta B: PaaS (Platform as a Service)
- **Kdy:** Nechceš spravovat server, jednoduchý deploy
- **Příklad:** Railway, Render, Fly.io
- **Cena:** od 0 Kč (free tier) do 500 Kč/měsíc
- **Stack:** Dockerfile nebo buildpack, managed HTTPS
- **Pro:** Automatické deploye, HTTPS, škálování
- **Proti:** SQLite může být problém (ephemeral filesystem), potřeba persistent volume nebo přechod na PostgreSQL

#### Varianta C: Kontejner (Docker)
- **Kdy:** Chceš přenositelnost, reproducibilní prostředí
- **Stack:** Dockerfile + docker-compose + nginx
- **Pro:** Funguje všude stejně, snadná záloha
- **Proti:** Potřeba Docker knowledge

### Fáze 3: PŘÍPRAVA NASAZENÍ (po schválení varianty)

#### 3.1 Společné pro všechny varianty
1. **Dockerfile:**
   ```dockerfile
   FROM python:3.11-slim
   WORKDIR /app
   COPY requirements.txt .
   RUN pip install --no-cache-dir -r requirements.txt
   COPY . .
   RUN mkdir -p data data/uploads data/backups
   EXPOSE 8000
   CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
   ```

2. **Konfigurace přes environment variables:**
   - `DATABASE_URL` — cesta k DB
   - `SECRET_KEY` — pro session
   - `SMTP_*` — emailové nastavení
   - `UPLOAD_DIR` — cesta k uploadům
   - `DEBUG` — false v produkci

3. **Healthcheck endpoint:**
   ```python
   @app.get("/health")
   def health():
       return {"status": "ok"}
   ```

4. **Produkční nastavení:**
   - `debug=False`
   - Secure cookies
   - HTTPS redirect
   - Logging do souboru

#### 3.2 VPS specifické
- `nginx.conf` pro reverse proxy
- `systemd` service file pro auto-start
- Let's Encrypt certbot setup
- Cron pro zálohy
- Firewall (ufw) konfigurace

#### 3.3 PaaS specifické
- `Procfile` nebo `railway.toml` / `render.yaml`
- Persistent volume pro SQLite a uploads
- Environment variables v dashboard

#### 3.4 Docker specifické
- `docker-compose.yml`
- Volume pro data persistence
- nginx reverse proxy kontejner

### Fáze 4: TESTOVÁNÍ

1. Nasaď na staging prostředí
2. Ověř:
   - [ ] Login funguje
   - [ ] Všechny moduly přístupné
   - [ ] Import Excel/CSV funguje
   - [ ] Upload souborů funguje
   - [ ] Odesílání emailů funguje
   - [ ] Záloha/obnova funguje
   - [ ] HTTPS funguje
   - [ ] Výkon je přijatelný
3. Bezpečnostní kontrola:
   - [ ] Žádné citlivé soubory přístupné přes web
   - [ ] Debug mode vypnutý
   - [ ] HTTP redirectuje na HTTPS

### Fáze 5: REPORT

```
## Cloud Deploy Report – [datum]

### Analýza připravenosti
- Autentizace: ✅/❌
- HTTPS ready: ✅/❌
- Konfigurovatelnost: ✅/❌
- Bezpečnost: ✅/❌

### Doporučená platforma
[varianta] — [důvod]

### Potřebné změny v kódu
| # | Změna | Soubor | Složitost |
|---|-------|--------|-----------|
| 1 | ...   | ...    | nízká/střední/vysoká |

### Odhad nákladů
- Hosting: X Kč/měsíc
- Doména: X Kč/rok (volitelné)
- SSL: zdarma (Let's Encrypt)

### Postup nasazení
1. [krok]
2. [krok]
...
```

---

## Spuštění

V Claude Code zadej:

```
Přečti soubor CLOUD-DEPLOY.md a analyzuj připravenost projektu pro nasazení do cloudu. Navrhni nejlepší variantu a připrav plán.
```
