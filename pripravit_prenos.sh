#!/bin/bash
# =============================================================================
# Příprava přenosu SVJ aplikace na jiný Mac
#
# Co dělá:
#   1. Checkpoint SQLite DB (sloučí WAL do hlavní DB)
#   2. Stáhne wheel balíčky pro offline instalaci
#   3. Zkopíruje projekt (bez .venv, .git, __pycache__)
#   4. Zkopíruje DATA adresář z Dropboxu
#   5. Zobrazí souhrn
#
# Použití:
#   ./pripravit_prenos.sh /Volumes/USB_DISK
#   ./pripravit_prenos.sh ~/Desktop/SVJ_prenos
# =============================================================================

set -e

cd "$(dirname "$0")"
PROJECT_DIR="$(pwd)"
DATA_SRC="${SVJ_DATA_SRC:-/Users/martinkoci/Library/CloudStorage/Dropbox/Dokumenty/SVJ/DATA}"

# Barvy
GREEN='\033[92m'
YELLOW='\033[93m'
RED='\033[91m'
BOLD='\033[1m'
DIM='\033[2m'
RESET='\033[0m'

echo ""
echo -e "${BOLD}════════════════════════════════════════════════${RESET}"
echo -e "${BOLD}  SVJ Správa — příprava přenosu na jiný Mac${RESET}"
echo -e "${BOLD}════════════════════════════════════════════════${RESET}"
echo ""

# --- Cílová složka ---
if [ -n "$1" ]; then
    TARGET_BASE="$1"
else
    echo -e "Zadej cílovou cestu (USB disk nebo složka):"
    echo -e "${DIM}  Příklad: /Volumes/USB_DISK${RESET}"
    echo -e "${DIM}  Příklad: ~/Desktop/SVJ_prenos${RESET}"
    echo ""
    read -p "Cesta: " TARGET_BASE
fi

# Expandovat ~ na domovský adresář
TARGET_BASE="${TARGET_BASE/#\~/$HOME}"

if [ ! -d "$TARGET_BASE" ]; then
    echo -e "${RED}CHYBA: Cílová cesta '$TARGET_BASE' neexistuje.${RESET}"
    exit 1
fi

TARGET="$TARGET_BASE/SVJ"
echo ""
echo -e "Cíl: ${BOLD}$TARGET${RESET}"

# Kontrola volného místa (potřeba ~350 MB)
AVAIL_KB=$(df -k "$TARGET_BASE" | tail -1 | awk '{print $4}')
AVAIL_MB=$((AVAIL_KB / 1024))
if [ "$AVAIL_MB" -lt 400 ]; then
    echo -e "${RED}CHYBA: Nedostatek místa — dostupné: ${AVAIL_MB} MB, potřeba: ~400 MB${RESET}"
    exit 1
fi
echo -e "Volné místo: ${GREEN}${AVAIL_MB} MB${RESET} (potřeba ~350 MB)"

# --- 1. Checkpoint SQLite ---
echo ""
echo -e "${BOLD}[1/4] Checkpoint SQLite databáze...${RESET}"
DB_FILE="$PROJECT_DIR/data/svj.db"
if [ -f "$DB_FILE" ]; then
    # Kontrola že server neběží
    if lsof "$DB_FILE" 2>/dev/null | grep -q python; then
        echo -e "${YELLOW}UPOZORNĚNÍ: Server pravděpodobně běží (DB je otevřená).${RESET}"
        echo -e "${YELLOW}Doporučuji nejdřív zastavit server (Ctrl+C).${RESET}"
        read -p "Pokračovat přesto? (a/n): " CONT
        if [ "$CONT" != "a" ]; then
            echo "Přerušeno."
            exit 0
        fi
    fi
    if command -v sqlite3 &>/dev/null; then
        sqlite3 "$DB_FILE" "PRAGMA wal_checkpoint(TRUNCATE);"
    else
        echo -e "  ${YELLOW}⚠ sqlite3 nenalezen — přeskakuji WAL checkpoint${RESET}"
    fi
    echo -e "  ${GREEN}✓${RESET} WAL sloučen do hlavní DB"
    DB_SIZE=$(du -h "$DB_FILE" | cut -f1)
    echo -e "  Velikost DB: $DB_SIZE"
else
    echo -e "  ${YELLOW}⚠ DB soubor nenalezen — přeskakuji${RESET}"
fi

# --- 2. Wheels ---
echo ""
echo -e "${BOLD}[2/4] Stahování wheel balíčků pro offline instalaci...${RESET}"
mkdir -p "$PROJECT_DIR/wheels"

# Zjistit verzi Pythonu pro správné wheels
PYTHON_VERSION=$(python3 --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')
echo -e "  Python verze: $PYTHON_VERSION"

pip3 download -d "$PROJECT_DIR/wheels" -r "$PROJECT_DIR/requirements.txt" \
    2>&1 | tail -3

WHEEL_COUNT=$(ls "$PROJECT_DIR/wheels/"*.whl 2>/dev/null | wc -l | tr -d ' ')
WHEEL_SIZE=$(du -sh "$PROJECT_DIR/wheels/" | cut -f1)
echo -e "  ${GREEN}✓${RESET} $WHEEL_COUNT balíčků ($WHEEL_SIZE)"

# --- 3. Kopírování projektu ---
echo ""
echo -e "${BOLD}[3/4] Kopírování projektu...${RESET}"

# Smazat předchozí kopii pokud existuje
if [ -d "$TARGET" ]; then
    echo -e "  ${YELLOW}Mažu předchozí kopii...${RESET}"
    rm -rf "$TARGET"
fi

mkdir -p "$TARGET"

rsync -a --progress \
    --exclude='.venv/' \
    --exclude='.git/' \
    --exclude='__pycache__/' \
    --exclude='.playwright-mcp/' \
    --exclude='*.pyc' \
    --exclude='.DS_Store' \
    --exclude='.env' \
    "$PROJECT_DIR/" "$TARGET/"

PROJECT_SIZE=$(du -sh "$TARGET" | cut -f1)
echo -e "  ${GREEN}✓${RESET} Projekt zkopírován ($PROJECT_SIZE)"

# --- 4. Kopírování DATA ---
echo ""
echo -e "${BOLD}[4/4] Kopírování DATA adresáře z Dropboxu...${RESET}"

if [ -d "$DATA_SRC" ]; then
    mkdir -p "$TARGET/DATA"
    rsync -a --progress \
        --exclude='.DS_Store' \
        "$DATA_SRC/" "$TARGET/DATA/"
    DATA_SIZE=$(du -sh "$TARGET/DATA" | cut -f1)
    echo -e "  ${GREEN}✓${RESET} DATA zkopírovány ($DATA_SIZE)"
else
    echo -e "  ${RED}✗ DATA adresář nenalezen: $DATA_SRC${RESET}"
    echo -e "  ${YELLOW}  Zkopíruj ručně na $TARGET/DATA/${RESET}"
fi

# --- Souhrn ---
TOTAL_SIZE=$(du -sh "$TARGET" | cut -f1)

echo ""
echo -e "${BOLD}════════════════════════════════════════════════${RESET}"
echo -e "${GREEN}${BOLD}  ✅ Přenos připraven!${RESET}"
echo -e "${BOLD}════════════════════════════════════════════════${RESET}"
echo ""
echo -e "  Cíl:           ${BOLD}$TARGET${RESET}"
echo -e "  Celková velikost: ${BOLD}$TOTAL_SIZE${RESET}"
echo ""
echo -e "  Obsah:"
echo -e "    ${GREEN}✓${RESET} Kód aplikace (bez .venv, .git)"
echo -e "    ${GREEN}✓${RESET} Databáze (svj.db + uploads + backups)"
echo -e "    ${GREEN}✓${RESET} Wheels pro offline instalaci ($WHEEL_COUNT balíčků)"
[ -d "$TARGET/DATA" ] && echo -e "    ${GREEN}✓${RESET} DATA z Dropboxu (Excely, PDF)"
echo ""
echo -e "  ${BOLD}Na cílovém Macu:${RESET}"
echo -e "    1. Zkopíruj složku ${BOLD}SVJ/${RESET} kam chceš"
echo -e "    2. Dvakrát klikni na ${BOLD}spustit.command${RESET}"
echo -e "    3. Skript zkontroluje vše potřebné a spustí aplikaci"
echo ""
