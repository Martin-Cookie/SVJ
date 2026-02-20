from __future__ import annotations

"""
Excel import service for parsing owner data from Sheet1.

Column layout (0-indexed):
  A (0) = Owner name with titles
  B (1) = Proxy / representative
  C (2) = Unit number
  D (3) = Sub-number
  E (4) = Share (0-1)
  F (5) = (skip)
  G (6) = Votes
  ...
  N (13) = Registration (Ano/Ne)
"""
import re

from openpyxl import load_workbook
from sqlalchemy.orm import Session

from app.models.owner import Owner, OwnerType, OwnerUnit, Unit

SJM_SUFFIXES = ("SJM", "SJ")
LEGAL_PATTERNS = [
    r"s\.r\.o\.", r"a\.s\.", r"v\.o\.s\.", r"k\.s\.", r"z\.s\.",
    r"s\.r\.o$", r"a\.s$",
]
TITLE_PATTERNS = [
    r"\bIng\.\s*", r"\bMgr\.\s*", r"\bBc\.\s*", r"\bMUDr\.\s*",
    r"\bJUDr\.\s*", r"\bRNDr\.\s*", r"\bPhDr\.\s*", r"\bDoc\.\s*",
    r"\bProf\.\s*", r",?\s*Ph\.?D\.?\s*", r",?\s*CSc\.?\s*",
    r",?\s*MBA\s*", r"\bDiS\.\s*",
]


def detect_owner_type(name: str, share: float | None) -> OwnerType:
    stripped = name.strip()
    # Remove parenthetical notes for SJM detection
    clean = re.sub(r"\([^)]*\)", "", stripped).strip()
    if any(clean.upper().endswith(s) for s in SJM_SUFFIXES):
        return OwnerType.SJM
    if any(re.search(p, stripped, re.IGNORECASE) for p in LEGAL_PATTERNS):
        return OwnerType.LEGAL_ENTITY
    if share is not None and 0 < share < 1:
        return OwnerType.PARTIAL
    return OwnerType.PHYSICAL


def normalize_name(name: str) -> str:
    result = name.strip()
    for pattern in TITLE_PATTERNS:
        result = re.sub(pattern, " ", result, flags=re.IGNORECASE)
    result = " ".join(result.split()).strip(" ,")
    # Remove SJM suffix
    clean = re.sub(r"\([^)]*\)", "", result).strip()
    for s in SJM_SUFFIXES:
        if clean.upper().endswith(s):
            result = result[:result.upper().rfind(s)].strip(" ,")
            break
    return result.strip()


def import_owners_from_excel(db: Session, file_path: str) -> dict:
    wb = load_workbook(file_path, read_only=True, data_only=True)
    ws = wb.active
    if "Sheet1" in wb.sheetnames:
        ws = wb["Sheet1"]

    owner_groups: dict[str, list[dict]] = {}
    rows_processed = 0
    errors = []

    for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        if not row or not row[0]:
            continue
        name_raw = str(row[0]).strip()
        if not name_raw:
            continue

        proxy_raw = str(row[1]).strip() if len(row) > 1 and row[1] else ""
        unit_num = str(row[2]).strip() if len(row) > 2 and row[2] else ""
        sub_num = str(row[3]).strip() if len(row) > 3 and row[3] else ""

        try:
            share = float(row[4]) if len(row) > 4 and row[4] is not None else 1.0
        except (ValueError, TypeError):
            share = 1.0

        try:
            votes = int(row[6]) if len(row) > 6 and row[6] is not None else 0
        except (ValueError, TypeError):
            votes = 0

        if not unit_num:
            errors.append(f"Řádek {row_idx}: chybí číslo jednotky")
            continue

        if name_raw not in owner_groups:
            owner_groups[name_raw] = []

        owner_groups[name_raw].append({
            "row": row_idx,
            "proxy": proxy_raw,
            "unit_number": unit_num,
            "sub_number": sub_num,
            "share": share,
            "votes": votes,
        })
        rows_processed += 1

    owners_created = 0
    units_created = 0

    for name_raw, unit_rows in owner_groups.items():
        first_share = unit_rows[0]["share"]
        owner_type = detect_owner_type(name_raw, first_share)
        normalized = normalize_name(name_raw)
        proxy_raw = unit_rows[0]["proxy"]

        owner = Owner(
            name_with_titles=name_raw,
            name_normalized=normalized,
            owner_type=owner_type,
            proxy_raw=proxy_raw if proxy_raw else None,
        )
        db.add(owner)
        db.flush()
        owners_created += 1

        for unit_data in unit_rows:
            unit = db.query(Unit).filter_by(
                unit_number=unit_data["unit_number"],
                sub_number=unit_data["sub_number"] or None,
            ).first()
            if not unit:
                unit = Unit(
                    unit_number=unit_data["unit_number"],
                    sub_number=unit_data["sub_number"] or None,
                )
                db.add(unit)
                db.flush()
                units_created += 1

            owner_unit = OwnerUnit(
                owner_id=owner.id,
                unit_id=unit.id,
                share=unit_data["share"],
                votes=unit_data["votes"],
                excel_row_number=unit_data["row"],
            )
            db.add(owner_unit)

    db.commit()
    wb.close()

    return {
        "owners_created": owners_created,
        "units_created": units_created,
        "rows_processed": rows_processed,
        "errors": errors,
    }
