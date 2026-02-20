from __future__ import annotations

"""
Export updated owner data to Excel.
"""
from pathlib import Path

from openpyxl import Workbook
from sqlalchemy.orm import Session

from app.models import Owner, OwnerUnit


def export_owners_to_excel(db: Session, output_path: str) -> str:
    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet1"

    # Header row
    headers = [
        "Vlastník", "Plná moc", "Jedn.", "Sub", "Podílů",
        "", "Hlasů", "", "", "", "", "", "", "Email", "Telefon",
    ]
    ws.append(headers)

    # Style header
    for cell in ws[1]:
        cell.font = cell.font.copy(bold=True)

    owners = (
        db.query(Owner)
        .filter_by(is_active=True)
        .order_by(Owner.name_normalized)
        .all()
    )

    for owner in owners:
        for ou in owner.units:
            row = [
                owner.name_with_titles,
                owner.proxy_raw or "",
                ou.unit.unit_number,
                ou.unit.sub_number or "",
                ou.share,
                "",
                ou.votes,
                "", "", "", "", "", "",
                owner.email or "",
                owner.phone or "",
            ]
            ws.append(row)

    # Auto-adjust column widths
    for col in ws.columns:
        max_len = 0
        for cell in col:
            if cell.value:
                max_len = max(max_len, len(str(cell.value)))
        ws.column_dimensions[col[0].column_letter].width = min(max_len + 2, 40)

    wb.save(output_path)
    return output_path
