# Cloud Deploy Agent – Nasazení do cloudu

> Spusť když budeš chtít přejít z lokálního/USB nasazení na cloudové.

---

## Cíl

Analyzovat připravenost SVJ aplikace pro cloud a připravit nasazení.

---

## Instrukce

### Fáze 1: ANALÝZA PŘIPRAVENOSTI

#### Závislosti na lokálním prostředí
- SQLite — cesta hardcoded nebo konfigurovatelná?
- Upload soubory — lokální filesystem nebo konfigurovatelné?
- LibreOffice — vyžadován? Pro které funkce?
- Absolutní cesty v kódu?
- `.env` — co je konfigurovatelné?

#### Bezpečnost pro internet
- Autentizace implementovaná? (bez ní NIKDY nevystavovat)
- HTTPS ready (X-Forwarded-For, X-Forwarded-Proto)?
- CSRF, rate limiting, session bezpečnost?
- Debug mode vypnutý?

#### Víceuživatelský přístup
- SQLite souběžné přístupy (WAL mode)?
- Session storage?

### Fáze 2: DOPORUČENÍ PLATFORMY

| Varianta | Kdy | Příklad | Cena | Pro | Proti |
|----------|-----|---------|------|-----|-------|
| **VPS** | Plná kontrola, SQLite stačí | Hetzner, DigitalOcean | od 100 Kč/měs | Jednoduché, levné | Ruční správa |
| **PaaS** | Nechceš spravovat server | Railway, Render, Fly.io | 0–500 Kč/měs | Auto deploy, HTTPS | SQLite problém (ephemeral FS) |
| **Docker** | Přenositelnost | docker-compose + nginx | — | Funguje všude stejně | Docker knowledge |

### Fáze 3: PŘÍPRAVA (po schválení varianty)

#### Společné
1. Dockerfile (Python 3.11-slim, uvicorn)
2. Environment variables: `DATABASE_URL`, `SECRET_KEY`, `SMTP_*`, `UPLOAD_DIR`, `DEBUG`
3. Healthcheck: `GET /health → {"status": "ok"}`
4. Produkční nastavení: `debug=False`, secure cookies, HTTPS redirect

#### VPS specifické
- `nginx.conf`, systemd service, Let's Encrypt, cron zálohy, ufw

#### PaaS specifické
- `Procfile`/`railway.toml`, persistent volume, env vars v dashboard

#### Docker specifické
- `docker-compose.yml`, volumes, nginx reverse proxy

### Fáze 4: REPORT

```
## Cloud Deploy Report – [datum]

### Připravenost
Autentizace: ... | HTTPS: ... | Konfigurovatelnost: ... | Bezpečnost: ...

### Doporučená platforma
[varianta] — [důvod]

### Potřebné změny
| # | Změna | Soubor | Složitost |

### Odhad nákladů
Hosting: X Kč/měs | Doména: X Kč/rok | SSL: zdarma
```

---

## Spuštění

```
Přečti CLOUD-DEPLOY.md a analyzuj připravenost pro cloud. Navrhni variantu a plán.
```
