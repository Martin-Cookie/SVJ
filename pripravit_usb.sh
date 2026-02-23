#!/bin/bash
# =============================================================================
# Příprava USB — stáhne wheel balíčky pro offline instalaci
# Spustit na TVÉM počítači před kopírováním na USB.
# =============================================================================

cd "$(dirname "$0")"

echo "Stahuji wheel balíčky pro offline instalaci..."
echo ""

# Vytvořit složku wheels
mkdir -p wheels

# Stáhnout všechny závislosti jako wheel soubory
pip download -d wheels fastapi uvicorn[standard] jinja2 python-multipart sqlalchemy pydantic-settings openpyxl python-docx docxtpl pdfplumber pytesseract Pillow unidecode 2>&1

if [ $? -eq 0 ]; then
    echo ""
    echo "Hotovo! Složka 'wheels/' obsahuje $(ls wheels/*.whl 2>/dev/null | wc -l | tr -d ' ') balíčků."
    echo ""
    echo "Nyní zkopíruj CELOU složku projektu na USB:"
    echo "  1. Smaž .venv/ (není přenositelná)"
    echo "  2. Zkopíruj vše ostatní na USB"
    echo ""
    echo "Kolega pak dvakrát klikne na 'spustit.command'"
else
    echo ""
    echo "CHYBA: Stahování selhalo."
fi
