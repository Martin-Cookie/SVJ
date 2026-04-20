# Nasazení na USB (jiný počítač)

- Projekt se spouští přes `spustit.command` (macOS) — dvakrát kliknout ve Finderu
- Skript automaticky: zkontroluje Python, vytvoří `.venv`, nainstaluje závislosti, spustí aplikaci, otevře prohlížeč
- **Wheels (offline balíčky) jsou vázané na verzi Pythonu** — pokud má cílový počítač jinou verzi Pythonu, wheels nebudou fungovat a skript stáhne balíčky online
- `.venv/` se NIKDY nekopíruje na USB — obsahuje absolutní cesty a je nepřenositelná
- Skript automaticky ověří existující `.venv/` — pokud chybí uvicorn (poškozená/neúplná instalace), smaže ji a vytvoří znovu
- Skript používá `"$VENV_DIR/bin/python" -m uvicorn` místo holého `uvicorn` — zajistí správnou cestu k binárce
- Skript používá `"$VENV_DIR/bin/pip"` místo holého `pip` — zajistí instalaci do správného venv
- Požadavky na cílovém počítači: **Python 3.9+** (ověřit `python3 --version`), volitelně LibreOffice pro PDF lístky
- Pro přenos dat: zkopírovat `data/svj.db` a `data/uploads/` na USB
