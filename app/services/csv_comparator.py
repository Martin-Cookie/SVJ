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
    """Parse CSV from sousede.cz or internal export. Tries multiple delimiters and column names."""
    # Strip BOM (byte order mark) if present
    csv_content = csv_content.lstrip("\ufeff")

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
        "space_type": [
            "Typ jednoky", "Typ jednotky", "typ_jednotky",
            "Druh prostoru",
        ],
        "ownership_type": [
            "Typ vlastnictví", "Typ vlastnictvi", "typ_vlastnictvi",
        ],
        "share": [
            "Podíl na domu", "Podil na domu", "podil_na_domu",
            "Podíl SČD",
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

        # Internal export: combine Příjmení + Jméno if no unified owners column
        if not record.get("owners"):
            last_name = (row.get("Příjmení") or "").strip()
            first_name = (row.get("Jméno") or "").strip()
            if last_name or first_name:
                record["owners"] = f"{last_name} {first_name}".strip()

        # Extract unit number from format "1098/14" -> "14"
        unit_raw = record.get("unit_number", "")
        if "/" in unit_raw:
            record["unit_number"] = unit_raw.split("/")[-1].strip()

        if record.get("unit_number"):
            records.append(record)

    # Merge rows with the same unit_number (internal export has one row per co-owner)
    merged: dict[str, dict] = {}
    for rec in records:
        unit = rec["unit_number"]
        if unit not in merged:
            merged[unit] = rec
        else:
            # Append owner name with separator
            existing_owners = merged[unit].get("owners", "")
            new_owner = rec.get("owners", "")
            if new_owner and new_owner not in existing_owners:
                merged[unit]["owners"] = f"{existing_owners}, {new_owner}" if existing_owners else new_owner

    return list(merged.values())


def _compare_structured_names(
    csv_owners_raw: str,
    excel_entries: list[dict],
) -> str | None:
    """
    Compare CSV names (format 'příjmení jméno') against structured DB fields.

    Returns:
        "match" - all names match structurally
        "name_order" - names are swapped (first_name/last_name in DB)
        None - cannot determine, fall back to fuzzy matching
    """
    # Split CSV into individual owners (comma or semicolon separated)
    csv_names = re.split(r'\s*[;,]\s*', csv_owners_raw.strip())
    csv_names = [n.strip() for n in csv_names if n.strip()]

    # Get structured names from DB entries
    db_names = [
        (e.get("first_name", ""), e.get("last_name", ""))
        for e in excel_entries
    ]

    # Only attempt structured comparison when counts match
    if not csv_names or not db_names or len(csv_names) != len(db_names):
        return None

    # Skip if any DB entry lacks structured data
    if any(not first and not last for first, last in db_names):
        return None

    all_match = True
    any_swapped = False
    used_db = set()

    for csv_name in csv_names:
        # CSV format: "příjmení jméno" → first word = last_name, rest = first_name
        csv_parts = csv_name.strip().split(None, 1)
        if not csv_parts:
            return None
        csv_last = normalize_for_matching(csv_parts[0])
        csv_first = normalize_for_matching(csv_parts[1]) if len(csv_parts) > 1 else ""

        found = False
        for i, (db_first, db_last) in enumerate(db_names):
            if i in used_db:
                continue
            db_first_n = normalize_for_matching(db_first)
            db_last_n = normalize_for_matching(db_last)

            if csv_first == db_first_n and csv_last == db_last_n:
                found = True
                used_db.add(i)
                break
            elif csv_first == db_last_n and csv_last == db_first_n:
                any_swapped = True
                found = True
                used_db.add(i)
                break

        if not found:
            all_match = False
            break

    if not all_match:
        return None  # fallback to fuzzy

    if any_swapped:
        return "name_order"
    return "match"


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
        csv_space_type = csv_rec.get("space_type", "")
        # Extract share: "12212/4103391" -> 12212 or plain "3051" -> 3051
        csv_share_raw = csv_rec.get("share", "")
        csv_share = None
        if csv_share_raw:
            try:
                if "/" in csv_share_raw:
                    csv_share = int(csv_share_raw.split("/")[0].strip())
                else:
                    csv_share = int(float(csv_share_raw))
            except (ValueError, TypeError):
                pass

        if unit not in excel_by_unit:
            results.append({
                "unit_number": unit,
                "csv_owner_name": csv_owners_raw,
                "excel_owner_name": None,
                "csv_ownership_type": csv_type,
                "excel_ownership_type": None,
                "csv_space_type": csv_space_type,
                "excel_space_type": None,
                "excel_podil_scd": None,
                "csv_share": csv_share,
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

        # Compare as sets of name parts (handles different order and separators)
        # Split on commas, semicolons, and whitespace
        separators = re.compile(r"[,;\s]+")
        csv_parts = set(separators.split(csv_norm))
        excel_parts = set(separators.split(excel_norm))
        connectors = {"a", "and", "und", "sjm", "sj", ""}
        csv_parts -= connectors
        excel_parts -= connectors

        if csv_parts and excel_parts:
            parts_overlap = len(csv_parts & excel_parts) / len(csv_parts | excel_parts)
        else:
            parts_overlap = 0.0

        best_ratio = max(ratio, parts_overlap)

        # Compare as sorted individual names (handles SJM pairs in different order/separator)
        csv_individuals = sorted(
            " ".join(sorted(normalize_for_matching(n).split()))
            for n in re.split(r'\s*[;,]\s*', csv_owners_raw) if n.strip()
        )
        excel_individuals = sorted(
            " ".join(sorted(normalize_for_matching(n).split()))
            for n in re.split(r'\s*[;,]\s*', excel_names_combined) if n.strip()
        )
        individuals_match = csv_individuals == excel_individuals

        # Check share mismatch
        share_mismatch = (
            csv_share is not None
            and excel_podil_scd
            and csv_share != excel_podil_scd
        )

        # Determine status: try structured comparison first, then fuzzy fallback
        structured_result = _compare_structured_names(csv_owners_raw, excel_entries)

        # When names are equivalent (structurally or all word-parts identical),
        # unify displayed strings so the UI doesn't offer a spurious name-change
        # checkbox.  Covers: structured match, different separators (, vs ;),
        # different owner ordering, and minor diacritics/title differences.
        if structured_result == "match" or parts_overlap == 1.0 or individuals_match:
            excel_names_combined = csv_owners_raw

        # Status reflects name comparison only; share/type differences are
        # captured in match_details and shown via field checkboxes in the UI.
        exact_string_match = csv_norm == excel_norm
        if structured_result == "match" or parts_overlap == 1.0 or individuals_match:
            status = SyncStatus.MATCH
        elif structured_result == "name_order":
            status = SyncStatus.NAME_ORDER
        elif best_ratio >= 0.85 and exact_string_match:
            status = SyncStatus.MATCH
        elif best_ratio >= 0.85:
            # Names are the same people, just in different order/format
            status = SyncStatus.NAME_ORDER
        else:
            status = SyncStatus.DIFFERENCE

        # Check ownership type mismatch
        type_mismatch = False
        if csv_type and excel_type:
            csv_type_norm = csv_type.lower()
            if ("sjm" in csv_type_norm and excel_type != "sjm") or \
               ("sjm" not in csv_type_norm and excel_type == "sjm"):
                type_mismatch = True

        details = f"{best_ratio:.0%}"
        if share_mismatch:
            details += " | Podíl se liší"
        if type_mismatch:
            details += " | Typ se liší"

        results.append({
            "unit_number": unit,
            "csv_owner_name": csv_owners_raw,
            "excel_owner_name": excel_names_combined,
            "csv_ownership_type": csv_type,
            "excel_ownership_type": excel_ownership_type_raw,
            "csv_space_type": csv_space_type,
            "excel_space_type": excel_space_type,
            "excel_podil_scd": excel_podil_scd,
            "csv_share": csv_share,
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
                    "excel_ownership_type": ee.get("ownership_type", ""),
                    "excel_space_type": ee.get("space_type", ""),
                    "excel_podil_scd": ee.get("podil_scd", 0),
                    "csv_share": None,
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
