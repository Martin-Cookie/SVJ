from __future__ import annotations

"""Import kontaktních údajů vlastníků z Excelu.

Excel formát (KontaktyVlastnici):
- Sheet "ZU", data od řádku 7 (hlavičky v řádcích 4-6)
- Sloupce (0-indexed):
  15: Titul před, 16: Jméno, 17: Příjmení, 18: Titul za
  19: RČ / IČ
  20-24: Trvalá adresa (ulice, část obce, obec, PSČ, země)
  25-29: Korespondenční adresa (ulice, část obce, obec, PSČ, země)
  30: GSM, 31: Pevný telefon, 32: Email
"""
from unicodedata import category, normalize

from openpyxl import load_workbook
from sqlalchemy.orm import Session

from app.models import Owner


def _strip_diacritics(text: str) -> str:
    nfkd = normalize("NFD", text)
    return "".join(c for c in nfkd if category(c) != "Mn").lower()


# Mapování Excel sloupců (1-indexed, openpyxl) → Owner polí
# col 15=titul před, 16=jméno, 17=příjmení, 18=titul za, 19=RČ/IČ
# col 20-24=trvalá adresa, 25-29=koresp. adresa, 30=GSM, 31=pevný, 32=email
_CONTACT_FIELDS = [
    {"col": 32, "field": "email", "label": "Email"},
    {"col": 30, "field": "phone", "label": "Telefon (GSM)"},
    {"col": 31, "field": "phone_landline", "label": "Pevný telefon"},
    {"col": 19, "field": "birth_number", "label": "Rodné číslo / IČ"},
    # Trvalá adresa
    {"col": 20, "field": "perm_street", "label": "Trvalá ulice"},
    {"col": 21, "field": "perm_district", "label": "Trvalá část obce"},
    {"col": 22, "field": "perm_city", "label": "Trvalá obec"},
    {"col": 23, "field": "perm_zip", "label": "Trvalé PSČ"},
    {"col": 24, "field": "perm_country", "label": "Trvalá země"},
    # Korespondenční adresa
    {"col": 25, "field": "corr_street", "label": "Koresp. ulice"},
    {"col": 26, "field": "corr_district", "label": "Koresp. část obce"},
    {"col": 27, "field": "corr_city", "label": "Koresp. obec"},
    {"col": 28, "field": "corr_zip", "label": "Koresp. PSČ"},
    {"col": 29, "field": "corr_country", "label": "Koresp. země"},
]


def _normalize_phone(phone: str) -> str:
    """Normalize phone for comparison: strip non-digit chars, remove +420/00420 prefix."""
    if not phone:
        return ""
    digits = "".join(c for c in phone if c.isdigit() or c == "+")
    if digits.startswith("+420"):
        digits = digits[4:]
    elif digits.startswith("00420"):
        digits = digits[5:]
    elif digits.startswith("420") and len(digits) > 9:
        digits = digits[3:]
    return digits


def _format_phone_for_db(phone: str) -> str:
    """Format phone for DB storage: add +420 prefix for 9-digit CZ numbers."""
    if not phone:
        return ""
    digits = "".join(c for c in phone if c.isdigit())
    if len(digits) == 9:
        return f"+420{digits}"
    if len(digits) == 12 and digits.startswith("420"):
        return f"+{digits}"
    return phone.strip()


def _build_normalized_name(first_name: str | None, last_name: str | None) -> str:
    """Build normalized name for matching: 'příjmení jméno' → stripped lowercase."""
    parts = []
    if last_name:
        parts.append(last_name.strip())
    if first_name:
        parts.append(first_name.strip())
    return _strip_diacritics(" ".join(parts))


def preview_contact_import(file_path: str, db: Session) -> dict:
    """Parse Excel and return preview of changes.

    Returns dict with keys:
    - rows: list of dicts with excel_row, excel_name, owner_id, owner_name, matched, changes
    - stats: total_rows, matched_count, unmatched_count, with_changes, changes_by_field
    """
    wb = load_workbook(file_path, data_only=True)

    # Try sheet "ZU" first, fallback to first sheet
    if "ZU" in wb.sheetnames:
        ws = wb["ZU"]
    else:
        ws = wb.active

    # Pre-load all data rows into list of tuples (row_num, cells...)
    # This avoids read_only/max_row issues
    data_rows = []
    for row in ws.iter_rows(min_row=7, values_only=False):
        # Extract cell values as dict keyed by column index (1-based)
        cells = {}
        for cell in row:
            if cell.value is not None:
                val = str(cell.value).strip()
                if val:
                    cells[cell.column] = val
        if cells:
            data_rows.append((row[0].row, cells))

    wb.close()

    # Build owner lookup by normalized name
    owners = db.query(Owner).filter_by(is_active=True).all()
    owner_by_name = {}
    owner_by_rc = {}
    for o in owners:
        if o.name_normalized:
            key = o.name_normalized.strip()
            if key not in owner_by_name:
                owner_by_name[key] = o
        if o.birth_number:
            rc_key = o.birth_number.replace(" ", "").replace("/", "")
            owner_by_rc[rc_key] = o

    rows = []
    seen_owners = set()  # Track owners to avoid duplicates
    changes_by_field = {}

    for row_num, cells in data_rows:
        first_name = cells.get(16)   # col P = jméno
        last_name = cells.get(17)    # col Q = příjmení

        if not first_name and not last_name:
            continue

        excel_name = " ".join(filter(None, [
            cells.get(15),  # titul před
            last_name,
            first_name,
            cells.get(18),  # titul za
        ]))

        # Match to DB owner
        norm_name = _build_normalized_name(first_name, last_name)
        owner = owner_by_name.get(norm_name)

        # Fallback: try RČ/IČ
        if not owner:
            rc_raw = cells.get(19)  # col S = RČ/IČ
            if rc_raw:
                rc_key = rc_raw.replace(" ", "").replace("/", "")
                owner = owner_by_rc.get(rc_key)

        # Skip duplicate rows for same owner (keep first occurrence)
        if owner and owner.id in seen_owners:
            continue
        if owner:
            seen_owners.add(owner.id)

        # Compare fields
        changes = []
        if owner:
            for fdef in _CONTACT_FIELDS:
                excel_val = cells.get(fdef["col"])
                if not excel_val:
                    continue
                current_val = getattr(owner, fdef["field"], None) or ""
                # Phone fields: normalize before comparison
                if fdef["field"] in ("phone", "phone_landline"):
                    if _normalize_phone(current_val) == _normalize_phone(excel_val):
                        continue
                elif current_val and current_val.strip() == excel_val.strip():
                    continue
                changes.append({
                    "field": fdef["field"],
                    "label": fdef["label"],
                    "current": current_val,
                    "new": excel_val,
                    "is_overwrite": bool(current_val.strip()),
                })
                changes_by_field[fdef["field"]] = changes_by_field.get(fdef["field"], 0) + 1

        rows.append({
            "excel_row": row_num,
            "excel_name": excel_name,
            "owner_id": owner.id if owner else None,
            "owner_name": owner.display_name if owner else None,
            "matched": owner is not None,
            "changes": changes,
        })

    matched_count = sum(1 for r in rows if r["matched"])
    with_changes = sum(1 for r in rows if r["matched"] and r["changes"])

    return {
        "rows": rows,
        "stats": {
            "total_rows": len(rows),
            "matched_count": matched_count,
            "unmatched_count": len(rows) - matched_count,
            "with_changes": with_changes,
            "changes_by_field": changes_by_field,
        },
    }


def execute_contact_import(
    file_path: str,
    db: Session,
    selected_owner_ids: list[int],
    overwrite_existing: bool = False,
) -> dict:
    """Execute the import for selected owners.

    Returns dict with owners_updated, fields_updated, per_field counts.
    """
    # Re-run preview to get current data
    preview = preview_contact_import(file_path, db)

    selected_set = set(selected_owner_ids)
    owners_updated = 0
    fields_updated = 0
    per_field = {}

    for row in preview["rows"]:
        if not row["matched"] or row["owner_id"] not in selected_set:
            continue
        if not row["changes"]:
            continue

        owner = db.query(Owner).get(row["owner_id"])
        if not owner:
            continue

        updated = False
        for change in row["changes"]:
            # Skip overwrites unless explicitly requested
            if change["is_overwrite"] and not overwrite_existing:
                continue

            value = change["new"]
            # Format phone numbers for DB storage
            if change["field"] in ("phone", "phone_landline"):
                value = _format_phone_for_db(value)
            setattr(owner, change["field"], value)
            updated = True
            fields_updated += 1
            per_field[change["field"]] = per_field.get(change["field"], 0) + 1

        if updated:
            owners_updated += 1

    # db.commit() is called by the router
    return {
        "owners_updated": owners_updated,
        "fields_updated": fields_updated,
        "per_field": per_field,
    }
