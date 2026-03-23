"""Služba pro import předpisů z DOCX (evidenční listy z DOMSYS).

Formát: 530 tabulek, každá 25 řádků × 2 sloupce.
Row 0: nadpis "EVIDENČNÍ LIST platný od ..."
Row 1: SVJ info + VS | adresa + sekce + číslo jednotky
Row 2: číslo popisné, prostor, podíly | kontakty
Row 3: podíly (copy row 2) | typ vlastnictví + jméno vlastníka
Row 4: "Předpis plateb:" | ""
Row 5-21: položky předpisu (název | částka)
Row 22: CELKEM | celková částka
Row 23: poznámka
Row 24: datum zpracování
"""

from __future__ import annotations

import io
import re
import logging
from datetime import date
from typing import Optional, Tuple

from docx import Document

from app.models.payment import PrescriptionCategory

logger = logging.getLogger(__name__)

# Kategorizace položek předpisu
_FOND_OPRAV_KEYWORDS = ["fond oprav"]
_SLUZBY_KEYWORDS = [
    "vodné", "stočné", "odpad", "komun",
    "elektřina", "společná el",
    "výtah", "úklid", "ostraha",
    "komín",
]


def _categorize_item(name: str) -> PrescriptionCategory:
    """Kategorizuj položku předpisu podle názvu."""
    name_lower = name.lower()
    for kw in _FOND_OPRAV_KEYWORDS:
        if kw in name_lower:
            return PrescriptionCategory.FOND_OPRAV
    for kw in _SLUZBY_KEYWORDS:
        if kw in name_lower:
            return PrescriptionCategory.SLUZBY
    return PrescriptionCategory.PROVOZNI


def _parse_amount(text: str) -> float:
    """Parsuj částku z textu (formát '1 438' nebo '264')."""
    cleaned = text.strip().replace("\xa0", "").replace(" ", "")
    if not cleaned or cleaned == "0":
        return 0.0
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def _extract_vs(cell_text: str) -> str | None:
    """Extrahuj variabilní symbol z textu buňky."""
    match = re.search(r"Variabilní symbol:\s*(\d+)", cell_text)
    return match.group(1) if match else None


def _extract_space_number(cell_text: str) -> int | None:
    """Extrahuj číslo prostoru z textu buňky."""
    match = re.search(r"Číslo prostoru:\s*(\d+)", cell_text)
    return int(match.group(1)) if match else None


def _extract_section_and_unit(cell_text: str) -> tuple[str | None, str | None]:
    """Extrahuj sekci a číslo jednotky z adresy (formát 'A 111')."""
    match = re.search(r"([A-Z])\s+(\d+)\s*$", cell_text.strip(), re.MULTILINE)
    if match:
        return match.group(1), match.group(2)
    return None, None


def _extract_space_type(cell_text: str) -> str | None:
    """Extrahuj druh jednotky z textu."""
    match = re.search(r"Druh jednotky:\s*(.+?)(?:\n|$)", cell_text)
    return match.group(1).strip() if match else None


def _extract_owner_name(cell_text: str) -> str | None:
    """Extrahuj jméno/jména vlastníka z textu buňky."""
    match = re.search(r"Údaje o vlastníkovi:\s*\n(.+)", cell_text, re.DOTALL)
    if match:
        lines = match.group(1).strip().split("\n")
        names = [line.strip() for line in lines if line.strip()]
        return ", ".join(names) if names else None
    return None


def _extract_valid_from(cell_text: str) -> date | None:
    """Extrahuj datum platnosti z nadpisu."""
    # "EVIDENČNÍ LIST platný od 1. ledna 2026"
    months = {
        "ledna": 1, "února": 2, "března": 3, "dubna": 4,
        "května": 5, "června": 6, "července": 7, "srpna": 8,
        "září": 9, "října": 10, "listopadu": 11, "prosince": 12,
    }
    match = re.search(r"platný od\s+(\d+)\.\s*(\w+)\s+(\d{4})", cell_text, re.IGNORECASE)
    if match:
        day = int(match.group(1))
        month_name = match.group(2).lower()
        year = int(match.group(3))
        month = months.get(month_name)
        if month:
            return date(year, month, day)
    return None


def parse_prescription_docx(file_content: bytes, year: int) -> dict:
    """Parsuj DOCX s evidenčními listy předpisů.

    Returns:
        dict s klíči:
        - valid_from: date | None
        - prescriptions: list of dict (variable_symbol, space_number, section, ...)
    """
    doc = Document(io.BytesIO(file_content))

    valid_from = None
    prescriptions = []

    for table_idx, table in enumerate(doc.tables):
        rows = table.rows
        if len(rows) < 20:
            logger.debug("Table %d: skipping (only %d rows)", table_idx, len(rows))
            continue

        try:
            # Row 0: nadpis — extrahuj datum platnosti (jen z první tabulky)
            if valid_from is None:
                header_text = rows[0].cells[0].text
                valid_from = _extract_valid_from(header_text)

            # Row 1: VS + adresa + sekce
            row1_left = rows[1].cells[0].text
            row1_right = rows[1].cells[1].text

            vs = _extract_vs(row1_left)
            section, unit_display = _extract_section_and_unit(row1_right)

            # Row 2: číslo prostoru, druh jednotky
            row2_left = rows[2].cells[0].text
            space_number = _extract_space_number(row2_left)
            space_type = _extract_space_type(row2_left)

            # Row 3: typ vlastnictví + jméno vlastníka
            row3_right = rows[3].cells[1].text
            owner_name = _extract_owner_name(row3_right)

            # Rows 5-21: položky předpisu (row 4 = "Předpis plateb:")
            items = []
            monthly_total = 0.0

            for row in rows[5:]:
                cells = [cell.text.strip() for cell in row.cells]
                if len(cells) < 2:
                    continue

                name = cells[0]
                amount_text = cells[1]

                # Přeskoč prázdné, poznámky, datum
                if not name or not amount_text:
                    continue
                if name.startswith("V\xa0případě") or name.startswith("V případě"):
                    continue
                if name.startswith("Datum"):
                    continue

                # CELKEM řádek
                if name == "CELKEM":
                    monthly_total = _parse_amount(amount_text)
                    continue

                amount = _parse_amount(amount_text)
                items.append({
                    "name": name,
                    "amount": amount,
                    "category": _categorize_item(name).value,
                })

            # Fallback — spočítat total z položek
            if monthly_total == 0.0 and items:
                monthly_total = sum(i["amount"] for i in items)

            prescriptions.append({
                "variable_symbol": vs,
                "space_number": space_number,
                "section": section,
                "unit_display": unit_display,
                "space_type": space_type,
                "owner_name": owner_name,
                "monthly_total": monthly_total,
                "items": items,
            })

        except Exception as e:
            logger.warning("Table %d parse error: %s", table_idx, e)
            continue

    logger.info(
        "Parsed %d prescriptions from DOCX (year=%d, valid_from=%s)",
        len(prescriptions), year, valid_from,
    )

    return {
        "valid_from": valid_from,
        "prescriptions": prescriptions,
    }
