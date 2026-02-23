#!/bin/bash
# =============================================================================
# SVJ Správa — spouštěcí skript pro macOS
# Stačí dvakrát kliknout na tento soubor ve Finderu.
# =============================================================================

# Přejít do složky kde je tento skript (USB/projekt)
cd "$(dirname "$0")"
PROJECT_DIR="$(pwd)"

echo "============================================"
echo "  SVJ Správa — spouštění aplikace"
echo "============================================"
echo ""
echo "Složka projektu: $PROJECT_DIR"
echo ""

# --- 1. Kontrola Pythonu ---
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
    echo "CHYBA: Python 3.9+ není nainstalovaný."
    echo ""
    echo "Nainstalujte Python z: https://www.python.org/downloads/"
    echo "Nebo přes Homebrew: brew install python@3.11"
    echo ""
    echo "Stiskněte Enter pro zavření..."
    read
    exit 1
fi

echo "Python: $($PYTHON --version) ($PYTHON)"

# --- 2. Virtuální prostředí ---
VENV_DIR="$PROJECT_DIR/.venv"

if [ -d "$VENV_DIR" ]; then
    # Ověřit, že uvicorn je nainstalovaný — pokud ne, smazat a vytvořit znovu
    if ! "$VENV_DIR/bin/python" -m uvicorn --version &>/dev/null; then
        echo "Virtuální prostředí poškozené (chybí závislosti), vytvářím znovu..."
        rm -rf "$VENV_DIR"
    fi
fi

if [ ! -d "$VENV_DIR" ]; then
    echo ""
    echo "Vytvářím virtuální prostředí..."
    "$PYTHON" -m venv "$VENV_DIR"
    if [ $? -ne 0 ]; then
        echo "CHYBA: Nepodařilo se vytvořit virtuální prostředí."
        echo "Stiskněte Enter pro zavření..."
        read
        exit 1
    fi
    echo "Virtuální prostředí vytvořeno."
    NEEDS_INSTALL=1
else
    echo "Virtuální prostředí: OK"
    NEEDS_INSTALL=0
fi

# Aktivovat venv
source "$VENV_DIR/bin/activate"

# --- 3. Instalace závislostí ---
if [ "$NEEDS_INSTALL" -eq 1 ]; then
    echo ""
    echo "Instaluji závislosti..."

    # Zkusit offline instalaci z wheels, pokud selže → online
    if [ -d "$PROJECT_DIR/wheels" ]; then
        echo "(zkouším offline režim z přibalených wheels...)"
        "$VENV_DIR/bin/pip" install --no-index --find-links "$PROJECT_DIR/wheels" "$PROJECT_DIR/wheels"/*.whl 2>/dev/null
        if [ $? -ne 0 ]; then
            echo "Offline instalace selhala (jiná verze Pythonu), zkouším online..."
            "$VENV_DIR/bin/pip" install fastapi "uvicorn[standard]" jinja2 python-multipart sqlalchemy pydantic-settings openpyxl python-docx docxtpl pdfplumber Pillow unidecode
        fi
    else
        "$VENV_DIR/bin/pip" install fastapi "uvicorn[standard]" jinja2 python-multipart sqlalchemy pydantic-settings openpyxl python-docx docxtpl pdfplumber Pillow unidecode
    fi

    if [ $? -ne 0 ]; then
        echo ""
        echo "CHYBA: Instalace závislostí selhala."
        echo "Zkontrolujte připojení k internetu a zkuste znovu."
        echo "Stiskněte Enter pro zavření..."
        read
        exit 1
    fi
    echo "Závislosti nainstalovány."
fi

# --- 4. Soubor .env ---
if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo ""
    echo "Vytvářím .env z šablony..."
    cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
    echo "Soubor .env vytvořen (výchozí nastavení)."
fi

# --- 5. Kontrola LibreOffice ---
LO_PATH=$(grep "^LIBREOFFICE_PATH=" "$PROJECT_DIR/.env" | cut -d= -f2)
if [ -n "$LO_PATH" ] && [ ! -f "$LO_PATH" ]; then
    echo ""
    echo "UPOZORNĚNÍ: LibreOffice nebyl nalezen na: $LO_PATH"
    echo "Generování PDF lístků nebude fungovat."
    echo "Nainstalujte z: https://www.libreoffice.org/download/"
fi

# --- 6. Spuštění ---
echo ""
echo "============================================"
echo "  Spouštím SVJ Správa na http://localhost:8000"
echo "============================================"
echo ""
echo "Pro ukončení stiskněte Ctrl+C"
echo ""

# Otevřít prohlížeč po 2 sekundách (na pozadí)
(sleep 2 && open "http://localhost:8000") &

# Spustit aplikaci
"$VENV_DIR/bin/python" -m uvicorn app.main:app --host 127.0.0.1 --port 8000

echo ""
echo "Aplikace ukončena."
echo "Stiskněte Enter pro zavření..."
read
