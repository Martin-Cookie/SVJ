from __future__ import annotations

import logging
import re
from datetime import date, datetime

from app.utils import templates

logger = logging.getLogger(__name__)


def parse_unit_label(label: str) -> tuple[int | None, str]:
    """Parse Techem unit label to (unit_number, section_letter).

    Formats:
        'A 111'  → (111, 'A')
        'B 234'  → (234, 'B')
        'AK 11'  → (11, 'AK')
        '0'      → (None, '')
        ''       → (None, '')
    """
    if not label or label.strip() == "0":
        return None, ""
    label = label.strip()
    # Format: "A 111", "AK 11", "D 431"
    m = re.match(r"([A-Za-z]+)\s+(\d+)", label)
    if m:
        return int(m.group(2)), m.group(1).upper()
    # Fallback: just number "111"
    m = re.match(r"(\d+)", label)
    if m:
        return int(m.group(1)), ""
    return None, ""


def _parse_header_date(header: str) -> date | None:
    """Parse date from column header like '31.1.25' or '28.2.25'.

    Returns date object or None.
    """
    header = header.strip()
    for fmt in ("%d.%m.%y", "%d.%m.%Y", "%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(header, fmt).date()
        except ValueError:
            continue
    return None


def parse_techem_xls(file_path: str) -> list[dict]:
    """Parse Techem XLS file with monthly reading columns.

    Techem format has:
      - Fixed columns: unit label, user name, meter type, serial, etc.
      - Date columns (13+): monthly readings (31.1.25, 28.2.25, ...)

    Returns list of dicts, one per meter, each with keys:
        unit_label, unit_number, unit_letter, meter_serial,
        meter_type, location, user_name, readings: [{date, value}, ...]
    """
    import xlrd

    book = xlrd.open_workbook(file_path)
    sheet = book.sheet_by_index(0)

    if sheet.nrows < 2:
        return []

    headers = [str(sheet.cell_value(0, c)).strip() for c in range(sheet.ncols)]

    # Auto-detect fixed columns by header name
    col = {}
    date_columns = []  # [(col_index, date_object), ...]

    for i, h in enumerate(headers):
        hl = h.lower()
        if "zákazník" in hl and "číslo" in hl.lower().replace("zákazník", "").replace("jednotky", ""):
            # "Číslo jednotky Zákazník"
            col["unit_label"] = i
        elif "jméno" in hl and "2" not in h:
            col.setdefault("user_name", i)
        elif "typ přístroje" in hl or "typ měřidla" in hl:
            col["meter_type"] = i
        elif "číslo přístroje" in hl or "evidenční" in hl:
            col["meter_serial"] = i
        elif "poloha" in hl:
            col["location"] = i
        elif "místnost" in hl and "číslo" not in hl and "zkratka" not in hl:
            col.setdefault("room", i)
        else:
            # Try to parse as date (monthly reading columns)
            d = _parse_header_date(h)
            if d:
                date_columns.append((i, d))

    # Fallback: exact name matching for critical columns
    exact_map = {
        "Číslo jednotky Zákazník": "unit_label",
        "Jméno uživatele": "user_name",
        "Typ přístroje": "meter_type",
        "Číslo přístroje": "meter_serial",
        "Poloha": "location",
    }
    for i, h in enumerate(headers):
        for name, key in exact_map.items():
            if h == name and key not in col:
                col[key] = i

    # Sort date columns chronologically
    date_columns.sort(key=lambda x: x[1])

    rows = []
    for r in range(1, sheet.nrows):
        # Unit label
        unit_idx = col.get("unit_label", 7)
        raw_label = str(sheet.cell_value(r, unit_idx)).strip()
        unit_number, unit_letter = parse_unit_label(raw_label)

        # User name
        name_idx = col.get("user_name", 1)
        user_name = str(sheet.cell_value(r, name_idx)).strip()

        # Meter serial
        serial_idx = col.get("meter_serial", 11)
        meter_serial = str(sheet.cell_value(r, serial_idx)).strip()
        # Remove trailing .0 from numbers read as float
        if meter_serial.endswith(".0"):
            meter_serial = meter_serial[:-2]

        # Meter type
        type_idx = col.get("meter_type", 10)
        raw_type = str(sheet.cell_value(r, type_idx)).strip().upper()
        if "SV" in raw_type or "STUD" in raw_type:
            meter_type = "cold"
        elif "TV" in raw_type or "TEPL" in raw_type:
            meter_type = "hot"
        else:
            meter_type = "cold"

        # Location
        loc_idx = col.get("location")
        location = str(sheet.cell_value(r, loc_idx)).strip() if loc_idx is not None else ""

        # Skip rows without meter serial
        if not meter_serial:
            continue

        # Parse monthly readings
        readings = []
        for col_idx, col_date in date_columns:
            raw_val = sheet.cell_value(r, col_idx)
            if isinstance(raw_val, (int, float)) and raw_val != 0:
                readings.append({"date": col_date, "value": float(raw_val)})
            elif isinstance(raw_val, str):
                cleaned = raw_val.replace(",", ".").replace(" ", "").strip()
                if cleaned:
                    try:
                        readings.append({"date": col_date, "value": float(cleaned)})
                    except ValueError:
                        pass

        rows.append({
            "unit_label": raw_label,
            "unit_number": unit_number,
            "unit_letter": unit_letter,
            "meter_serial": meter_serial,
            "meter_type": meter_type,
            "location": location,
            "user_name": user_name,
            "readings": readings,
        })

    return rows
