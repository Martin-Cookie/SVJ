from __future__ import annotations

"""
Export owner data to Excel in the same format as the import file.
Columns A-AE matching SVJ_Evidence_Vlastniku_CLEAN.xlsx structure.
"""
from openpyxl import Workbook
from sqlalchemy.orm import Session

from app.models import Owner, OwnerUnit


def export_owners_to_excel(db: Session, output_path: str) -> str:
    wb = Workbook()
    ws = wb.active
    ws.title = "Vlastnici_SVJ"

    # Header row matching import columns A-AE
    headers = [
        "Číslo jednotky (KN)", "Číslo prostoru (stavební)", "Podíl na SČD",
        "Podlahová plocha (m²)", "Počet místností", "Druh prostoru",
        "Sekce domu", "Číslo orientační", "Adresa jednotky", "LV číslo",
        "Typ vlastnictví", "Jméno", "Příjmení / název", "Titul",
        "Rodné číslo / IČ",
        "Trvalá adresa – ulice", "Trvalá adresa – část obce",
        "Trvalá adresa – město", "Trvalá adresa – PSČ", "Trvalá adresa – stát",
        "Koresp. adresa – ulice", "Koresp. adresa – část obce",
        "Koresp. adresa – město", "Koresp. adresa – PSČ", "Koresp. adresa – stát",
        "Telefon GSM", "Telefon pevný",
        "Email (Evidence 2024)", "Email (Kontakty)",
        "Vlastník od", "Poznámka",
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
        # Determine RC/IČ value
        birth_or_ic = owner.company_id or owner.birth_number or ""

        for ou in owner.units:
            unit = ou.unit
            row = [
                unit.unit_number,
                unit.building_number or "",
                unit.podil_scd,
                unit.floor_area,
                unit.room_count or "",
                unit.space_type or "",
                unit.section or "",
                unit.orientation_number,
                unit.address or "",
                unit.lv_number,
                ou.ownership_type or "",
                owner.first_name,
                owner.last_name or "",
                owner.title or "",
                birth_or_ic,
                owner.perm_street or "",
                owner.perm_district or "",
                owner.perm_city or "",
                owner.perm_zip or "",
                owner.perm_country or "",
                owner.corr_street or "",
                owner.corr_district or "",
                owner.corr_city or "",
                owner.corr_zip or "",
                owner.corr_country or "",
                owner.phone or "",
                owner.phone_landline or "",
                owner.email or "",
                owner.email_secondary or "",
                owner.owner_since or "",
                owner.note or "",
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
