#!/bin/bash
# =============================================================================
# SVJ Správa — spouštěcí skript pro macOS
# Stačí dvakrát kliknout na tento soubor ve Finderu.
#
# Skript automaticky:
#   1. Zkontroluje systémové požadavky (Python, místo na disku)
#   2. Vytvoří virtuální prostředí (pokud chybí)
#   3. Nainstaluje závislosti (offline z wheels nebo online)
#   4. Zkontroluje databázi a DATA adresář
#   5. Spustí aplikaci a otevře prohlížeč
# =============================================================================

# Přejít do složky kde je tento skript (USB/projekt)
cd "$(dirname "$0")"
PROJECT_DIR="$(pwd)"

# Barvy
GREEN='\033[92m'
YELLOW='\033[93m'
RED='\033[91m'
BOLD='\033[1m'
DIM='\033[2m'
RESET='\033[0m'

echo ""
echo -e "${BOLD}════════════════════════════════════════════════${RESET}"
echo -e "${BOLD}  SVJ Správa — spouštění aplikace${RESET}"
echo -e "${BOLD}════════════════════════════════════════════════${RESET}"
echo ""
echo -e "Složka projektu: $PROJECT_DIR"
echo ""

ERRORS=0
WARNINGS=0

# =============================================================================
# KONTROLY SYSTÉMU
# =============================================================================
echo -e "${BOLD}Kontrola systému...${RESET}"
echo ""

# --- 1. Python ---
PYTHON=""
for cmd in python3.12 python3.11 python3.10 python3.9 python3; do
    if command -v "$cmd" &>/dev/null; then
        version=$("$cmd" --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')
        major=$(echo "$version" | cut -d. -f1)
        minor=$(echo "$version" | cut -d. -f2)
        if [ "$major" -ge 3 ] && [ "$minor" -ge 9 ]; then
            PYTHON="$cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo -e "  ${RED}✗ Python 3.9+${RESET} — CHYBÍ"
    echo -e "    Nainstalujte z: ${BOLD}https://www.python.org/downloads/${RESET}"
    echo -e "    Nebo: ${BOLD}brew install python@3.11${RESET}"
    ERRORS=$((ERRORS + 1))
else
    echo -e "  ${GREEN}✓${RESET} Python: $($PYTHON --version) ($(which $PYTHON))"
fi

# --- 2. Místo na disku ---
AVAIL_KB=$(df -k "$PROJECT_DIR" | tail -1 | awk '{print $4}')
AVAIL_MB=$((AVAIL_KB / 1024))
if [ "$AVAIL_MB" -lt 200 ]; then
    echo -e "  ${RED}✗ Místo na disku${RESET} — ${AVAIL_MB} MB volných (potřeba min. 200 MB)"
    ERRORS=$((ERRORS + 1))
else
    echo -e "  ${GREEN}✓${RESET} Místo na disku: ${AVAIL_MB} MB volných"
fi

# --- 3. Databáze ---
if [ -f "$PROJECT_DIR/data/svj.db" ]; then
    DB_SIZE=$(du -h "$PROJECT_DIR/data/svj.db" | cut -f1)
    echo -e "  ${GREEN}✓${RESET} Databáze: svj.db ($DB_SIZE)"
else
    echo -e "  ${YELLOW}⚠ Databáze${RESET} — soubor data/svj.db nenalezen (vytvoří se prázdná při spuštění)"
    WARNINGS=$((WARNINGS + 1))
fi

# --- 4. DATA adresář ---
if [ -d "$PROJECT_DIR/DATA" ]; then
    DATA_COUNT=$(find "$PROJECT_DIR/DATA" -type f | wc -l | tr -d ' ')
    DATA_SIZE=$(du -sh "$PROJECT_DIR/DATA" | cut -f1)
    echo -e "  ${GREEN}✓${RESET} DATA adresář: $DATA_COUNT souborů ($DATA_SIZE)"
else
    echo -e "  ${YELLOW}⚠ DATA adresář${RESET} — složka DATA/ chybí (importy nebudou dostupné)"
    WARNINGS=$((WARNINGS + 1))
fi

# --- 5. Uploads ---
if [ -d "$PROJECT_DIR/data/uploads" ]; then
    UPLOAD_COUNT=$(find "$PROJECT_DIR/data/uploads" -type f | wc -l | tr -d ' ')
    echo -e "  ${GREEN}✓${RESET} Uploads: $UPLOAD_COUNT souborů"
else
    echo -e "  ${DIM}  ○ Uploads: prázdné (vytvoří se automaticky)${RESET}"
fi

# --- 6. Wheels ---
if [ -d "$PROJECT_DIR/wheels" ]; then
    WHEEL_COUNT=$(ls "$PROJECT_DIR/wheels/"*.whl 2>/dev/null | wc -l | tr -d ' ')
    if [ "$WHEEL_COUNT" -gt 0 ]; then
        echo -e "  ${GREEN}✓${RESET} Offline balíčky: $WHEEL_COUNT wheels"
    else
        echo -e "  ${YELLOW}⚠ Offline balíčky${RESET} — složka wheels/ je prázdná (potřeba internet)"
        WARNINGS=$((WARNINGS + 1))
    fi
else
    echo -e "  ${YELLOW}⚠ Offline balíčky${RESET} — chybí (potřeba internet pro instalaci)"
    WARNINGS=$((WARNINGS + 1))
fi

# --- 7. LibreOffice (volitelné) ---
LO_PATHS=(
    "/Applications/LibreOffice.app/Contents/MacOS/soffice"
    "$HOME/Applications/LibreOffice.app/Contents/MacOS/soffice"
)
LO_FOUND=""
for lp in "${LO_PATHS[@]}"; do
    if [ -f "$lp" ]; then
        LO_FOUND="$lp"
        break
    fi
done

if [ -n "$LO_FOUND" ]; then
    echo -e "  ${GREEN}✓${RESET} LibreOffice: nalezen"
else
    echo -e "  ${DIM}  ○ LibreOffice: nenalezen (volitelné — jen pro PDF lístky)${RESET}"
fi

# --- 8. Síťové připojení (pokud chybí wheels) ---
if [ ! -d "$PROJECT_DIR/wheels" ] || [ "${WHEEL_COUNT:-0}" -eq 0 ]; then
    if ping -c 1 -W 2 pypi.org &>/dev/null; then
        echo -e "  ${GREEN}✓${RESET} Internet: dostupný (pro stažení závislostí)"
    else
        echo -e "  ${RED}✗ Internet${RESET} — nedostupný a chybí offline balíčky"
        ERRORS=$((ERRORS + 1))
    fi
fi

# --- Výsledek kontrol ---
echo ""
if [ "$ERRORS" -gt 0 ]; then
    echo -e "${RED}${BOLD}  ✗ Nalezeny chyby ($ERRORS). Aplikaci nelze spustit.${RESET}"
    echo ""
    echo "Stiskněte Enter pro zavření..."
    read
    exit 1
fi

if [ "$WARNINGS" -gt 0 ]; then
    echo -e "${YELLOW}  ⚠ $WARNINGS upozornění (nekritické, aplikace poběží)${RESET}"
fi

echo -e "${GREEN}  ✓ Systém OK${RESET}"

# =============================================================================
# INSTALACE
# =============================================================================

# --- Virtuální prostředí ---
VENV_DIR="$PROJECT_DIR/.venv"

if [ -d "$VENV_DIR" ]; then
    # Ověřit, že uvicorn je nainstalovaný — pokud ne, smazat a vytvořit znovu
    if ! "$VENV_DIR/bin/python" -m uvicorn --version &>/dev/null; then
        echo ""
        echo "Virtuální prostředí poškozené (chybí závislosti), vytvářím znovu..."
        rm -rf "$VENV_DIR"
    fi
fi

if [ ! -d "$VENV_DIR" ]; then
    echo ""
    echo -e "${BOLD}Vytvářím virtuální prostředí...${RESET}"
    "$PYTHON" -m venv "$VENV_DIR"
    if [ $? -ne 0 ]; then
        echo -e "${RED}CHYBA: Nepodařilo se vytvořit virtuální prostředí.${RESET}"
        echo "Stiskněte Enter pro zavření..."
        read
        exit 1
    fi
    echo -e "  ${GREEN}✓${RESET} Virtuální prostředí vytvořeno"
    NEEDS_INSTALL=1
else
    NEEDS_INSTALL=0
fi

# Aktivovat venv
source "$VENV_DIR/bin/activate"

# --- Instalace závislostí ---
if [ "$NEEDS_INSTALL" -eq 1 ]; then
    echo ""
    echo -e "${BOLD}Instaluji závislosti...${RESET}"

    # Zkusit offline instalaci z wheels, pokud selže → online z requirements.txt
    if [ -d "$PROJECT_DIR/wheels" ] && [ "$(ls "$PROJECT_DIR/wheels/"*.whl 2>/dev/null | wc -l)" -gt 0 ]; then
        echo "  (offline režim z přibalených wheels...)"
        "$VENV_DIR/bin/pip" install --no-index --find-links "$PROJECT_DIR/wheels" "$PROJECT_DIR/wheels"/*.whl 2>/dev/null
        if [ $? -ne 0 ]; then
            echo -e "  ${YELLOW}Offline instalace selhala (jiná verze Pythonu?), zkouším online...${RESET}"
            "$VENV_DIR/bin/pip" install -r "$PROJECT_DIR/requirements.txt"
        fi
    else
        echo "  (online režim...)"
        "$VENV_DIR/bin/pip" install -r "$PROJECT_DIR/requirements.txt"
    fi

    if [ $? -ne 0 ]; then
        echo ""
        echo -e "${RED}CHYBA: Instalace závislostí selhala.${RESET}"
        echo "Zkontrolujte připojení k internetu a zkuste znovu."
        echo "Stiskněte Enter pro zavření..."
        read
        exit 1
    fi
    echo -e "  ${GREEN}✓${RESET} Závislosti nainstalovány"
fi

# --- .env ---
if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo ""
    echo "Vytvářím .env z šablony..."
    cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"

    # Doplnit LibreOffice cestu pokud nalezen
    if [ -n "$LO_FOUND" ]; then
        sed -i '' "s|LIBREOFFICE_PATH=.*|LIBREOFFICE_PATH=$LO_FOUND|" "$PROJECT_DIR/.env"
    fi

    echo -e "  ${GREEN}✓${RESET} .env vytvořen (výchozí nastavení)"
fi

# =============================================================================
# SPUŠTĚNÍ
# =============================================================================
echo ""
echo -e "${BOLD}════════════════════════════════════════════════${RESET}"
echo -e "${GREEN}${BOLD}  Spouštím SVJ Správa na http://localhost:8000${RESET}"
echo -e "${BOLD}════════════════════════════════════════════════${RESET}"
echo ""
echo -e "Pro ukončení stiskněte ${BOLD}Ctrl+C${RESET}"
echo ""

# Otevřít prohlížeč po 2 sekundách (na pozadí)
(sleep 2 && open "http://localhost:8000") &

# Spustit aplikaci
"$VENV_DIR/bin/python" -m uvicorn app.main:app --host 127.0.0.1 --port 8000

echo ""
echo "Aplikace ukončena."
echo "Stiskněte Enter pro zavření..."
read
