from __future__ import annotations

"""
Compare CSV export from sousede.cz with Excel owner data.
Handles format differences: titles, SJM format, comma in company names.
"""
import csv
import re
from difflib import SequenceMatcher
from io import StringIO

from app.models.sync import SyncStatus
from app.services.owner_matcher import normalize_for_matching


def parse_sousede_csv(csv_content: str) -> list[dict]:
    """Parse CSV from sousede.cz. Tries multiple delimiters and column names."""
    # Try to detect delimiter
    first_line = csv_content.split("\n")[0]
    delimiter = ";" if ";" in first_line else ","

    reader = csv.DictReader(StringIO(csv_content), delimiter=delimiter)

    # Map possible column names to standard keys
    column_mapping = {
        "unit_number": [
            "Název jednotky", "nazev_jednotky", "Cislo jednotky",
            "cislo_jednotky", "Jednotka",
        ],
        "owners": [
            "Vlastníci jednotky", "Vlastnici jednotky", "vlastnici",
            "Vlastníci", "Vlastnici",
        ],
        "ownership_type": [
            "Typ vlastnictví", "Typ vlastnictvi", "typ_vlastnictvi",
        ],
        "share": [
            "Podíl na domu", "Podil na domu", "podil_na_domu",
        ],
        "email": [
            "Hlavní kontaktní e-mail", "Hlavni kontaktni e-mail",
            "Email", "email", "E-mail",
        ],
        "phone": [
            "Hlavní kontaktní telefon", "Hlavni kontaktni telefon",
            "Telefon", "telefon",
        ],
    }

    records = []
    for row in reader:
        record = {}
        for key, candidates in column_mapping.items():
            for candidate in candidates:
                if candidate in row:
                    record[key] = row[candidate].strip() if row[candidate] else ""
                    break
            if key not in record:
                record[key] = ""

        # Extract unit number from format "1098/14" -> "14"
        unit_raw = record.get("unit_number", "")
        if "/" in unit_raw:
            record["unit_number"] = unit_raw.split("/")[-1].strip()

        if record.get("unit_number"):
            records.append(record)

    return records


def compare_owners(
    csv_records: list[dict],
    excel_data: list[dict],
) -> list[dict]:
    """
    Compare CSV records against Excel owner data.
    excel_data: [{"unit_number": str, "owner_name": str, "name_normalized": str,
                  "owner_type": str}]
    Returns comparison results with status.
    """
    results = []

    # Group Excel data by unit number
    excel_by_unit: dict[str, list[dict]] = {}
    for ed in excel_data:
        unit = ed["unit_number"]
        excel_by_unit.setdefault(unit, []).append(ed)

    csv_units_seen = set()

    for csv_rec in csv_records:
        unit = csv_rec["unit_number"]
        csv_units_seen.add(unit)
        csv_owners_raw = csv_rec.get("owners", "")
        csv_type = csv_rec.get("ownership_type", "")

        if unit not in excel_by_unit:
            results.append({
                "unit_number": unit,
                "csv_owner_name": csv_owners_raw,
                "excel_owner_name": None,
                "csv_ownership_type": csv_type,
                "excel_ownership_type": None,
                "excel_space_type": None,
                "excel_podil_scd": None,
                "csv_email": csv_rec.get("email", ""),
                "csv_phone": csv_rec.get("phone", ""),
                "status": SyncStatus.MISSING_EXCEL,
                "match_details": "Jednotka nalezena v CSV, ale ne v Excelu",
            })
            continue

        excel_entries = excel_by_unit[unit]
        # Combine all Excel owner names for this unit
        excel_names_combined = "; ".join(e["owner_name"] for e in excel_entries)
        excel_type = excel_entries[0].get("owner_type", "")
        excel_space_type = excel_entries[0].get("space_type", "")
        excel_podil_scd = excel_entries[0].get("podil_scd", 0)
        excel_ownership_type_raw = excel_entries[0].get("ownership_type", "")

        csv_norm = normalize_for_matching(csv_owners_raw)
        excel_norm = normalize_for_matching(excel_names_combined)

        # Compare names
        ratio = SequenceMatcher(None, csv_norm, excel_norm).ratio()

        # Also try comparing as sets of name parts
        csv_parts = set(csv_norm.replace(",", " ").split())
        excel_parts = set(excel_norm.replace(",", " ").split())
        connectors = {"a", "and", "und", "sjm", "sj"}
        csv_parts -= connectors
        excel_parts -= connectors

        if csv_parts and excel_parts:
            parts_overlap = len(csv_parts & excel_parts) / len(csv_parts | excel_parts)
        else:
            parts_overlap = 0.0

        best_ratio = max(ratio, parts_overlap)

        # Determine status
        if best_ratio >= 0.85:
            status = SyncStatus.MATCH
        elif best_ratio >= 0.3:
            status = SyncStatus.DIFFERENCE
        else:
            status = SyncStatus.DIFFERENCE

        # Check ownership type mismatch
        type_mismatch = False
        if csv_type and excel_type:
            csv_type_norm = csv_type.lower()
            if ("sjm" in csv_type_norm and excel_type != "sjm") or \
               ("sjm" not in csv_type_norm and excel_type == "sjm"):
                type_mismatch = True

        details = f"Shoda jmen: {best_ratio:.0%}"
        if type_mismatch:
            details += f" | Typ vlastnictví se liší (CSV: {csv_type}, Excel: {excel_type})"

        results.append({
            "unit_number": unit,
            "csv_owner_name": csv_owners_raw,
            "excel_owner_name": excel_names_combined,
            "csv_ownership_type": csv_type,
            "excel_ownership_type": excel_type,
            "excel_space_type": excel_space_type,
            "excel_podil_scd": excel_podil_scd,
            "csv_email": csv_rec.get("email", ""),
            "csv_phone": csv_rec.get("phone", ""),
            "status": status,
            "match_details": details,
        })

    # Find units in Excel but not in CSV
    for unit_key, entries in excel_by_unit.items():
        if unit_key not in csv_units_seen:
            for ee in entries:
                results.append({
                    "unit_number": unit_key,
                    "csv_owner_name": None,
                    "excel_owner_name": ee["owner_name"],
                    "csv_ownership_type": None,
                    "excel_ownership_type": ee.get("owner_type", ""),
                    "excel_space_type": ee.get("space_type", ""),
                    "excel_podil_scd": ee.get("podil_scd", 0),
                    "csv_email": "",
                    "csv_phone": "",
                    "status": SyncStatus.MISSING_CSV,
                    "match_details": "Jednotka v Excelu, ale ne v CSV",
                })

    # Sort: differences first, then missing, then matches
    status_order = {
        SyncStatus.DIFFERENCE: 0,
        SyncStatus.MISSING_EXCEL: 1,
        SyncStatus.MISSING_CSV: 2,
        SyncStatus.MATCH: 3,
    }
    results.sort(key=lambda r: (status_order.get(r["status"], 4), r["unit_number"]))

    return results
