import re
from datetime import datetime

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import cast, func, Integer, or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    ImportLog, Owner, OwnerUnit, SyncRecord, SyncResolution,
    SyncSession, SyncStatus, Unit,
)
from app.services.owner_exchange import recalculate_unit_votes
from app.utils import templates, utcnow
from ._helpers import ALLOWED_UPDATE_FIELDS, _apply_owner_name_update, _build_contact_preview

router = APIRouter()


@router.post("/{session_id}/prijmout/{record_id}")
async def accept_change(
    session_id: int,
    record_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Přijetí navržené změny v synchronizačním záznamu."""
    record = db.query(SyncRecord).get(record_id)
    if record:
        record.resolution = SyncResolution.ACCEPTED
        db.commit()

    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(request, "partials/sync_row.html", {
            "record": record,
        })
    return RedirectResponse(f"/synchronizace/{session_id}", status_code=302)


@router.post("/{session_id}/odmitnout/{record_id}")
async def reject_change(
    session_id: int,
    record_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Odmítnutí navržené změny v synchronizačním záznamu."""
    record = db.query(SyncRecord).get(record_id)
    if record:
        record.resolution = SyncResolution.REJECTED
        db.commit()

    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(request, "partials/sync_row.html", {
            "record": record,
        })
    return RedirectResponse(f"/synchronizace/{session_id}", status_code=302)


@router.post("/{session_id}/upravit/{record_id}")
async def manual_edit(
    session_id: int,
    record_id: int,
    corrected_name: str = Form(...),
    request: Request = None,
    db: Session = Depends(get_db),
):
    """Ruční oprava jména v synchronizačním záznamu."""
    record = db.query(SyncRecord).get(record_id)
    if record:
        record.admin_corrected_name = corrected_name
        record.resolution = SyncResolution.MANUAL_EDIT
        db.commit()

    if request and request.headers.get("HX-Request"):
        return templates.TemplateResponse(request, "partials/sync_row.html", {
            "record": record,
        })
    return RedirectResponse(f"/synchronizace/{session_id}", status_code=302)


@router.post("/{session_id}/aktualizovat")
async def apply_selected_updates(
    session_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Apply selected CSV field updates to the database."""
    form = await request.form()

    # Parse form keys: update__{record_id}__{field} → {record_id: {field: value}}
    updates: dict[int, dict[str, str]] = {}
    for key, value in form.items():
        if not key.startswith("update__"):
            continue
        parts = key.split("__")
        if len(parts) != 3:
            continue
        _, record_id_str, field = parts
        if field not in ALLOWED_UPDATE_FIELDS:
            continue
        try:
            rid = int(record_id_str)
        except ValueError:
            continue
        updates.setdefault(rid, {})[field] = value

    session = db.query(SyncSession).get(session_id)
    if not session:
        return RedirectResponse("/synchronizace", status_code=302)

    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    csv_name = session.csv_filename

    success_count = 0
    error_count = 0
    change_details = []

    for record_id, fields in updates.items():
        record = db.query(SyncRecord).filter_by(
            id=record_id, session_id=session_id,
        ).first()
        if not record or not record.unit_number:
            error_count += 1
            continue

        short_num = record.unit_number
        unit = (
            db.query(Unit)
            .filter(
                Unit.unit_number == int(short_num)
            )
            .first()
        )
        if not unit:
            error_count += 1
            change_details.append(f"Jednotka {short_num}: nenalezena")
            continue

        owner_unit = db.query(OwnerUnit).filter_by(unit_id=unit.id).filter(OwnerUnit.valid_to.is_(None)).first()
        if not owner_unit:
            error_count += 1
            change_details.append(f"Jednotka {short_num}: vlastník nenalezen")
            continue

        changes = []
        for field, new_value in fields.items():
            if field == "owner_name":
                changes.extend(_apply_owner_name_update(db, unit, record, new_value))
            elif field == "ownership_type":
                old_val = record.excel_ownership_type or owner_unit.ownership_type or ""
                # Update ALL active OwnerUnits on this unit (not just the first)
                all_ous = db.query(OwnerUnit).filter_by(unit_id=unit.id).filter(OwnerUnit.valid_to.is_(None)).all()
                for aou in all_ous:
                    aou.ownership_type = new_value
                record.excel_ownership_type = new_value
                changes.append(f"vlastnictví: {old_val} → {new_value}")
            elif field == "space_type":
                old_val = record.excel_space_type or unit.space_type or ""
                unit.space_type = new_value
                record.excel_space_type = new_value
                changes.append(f"typ: {old_val} → {new_value}")
            elif field == "podil_scd":
                old_val = record.excel_podil_scd or unit.podil_scd
                unit.podil_scd = float(new_value)
                record.excel_podil_scd = float(new_value)
                recalculate_unit_votes(unit, db)
                changes.append(
                    f"podíl: {old_val} → {new_value}"
                )

        if changes:
            # Each change as separate log entry with source file and timestamp
            note_entries = [f"{ch} (z {csv_name}, {now})" for ch in changes]
            record.admin_note = (record.admin_note + "\n" if record.admin_note else "") + "\n".join(note_entries)
            record.resolution = SyncResolution.MANUAL_EDIT

            # Recalculate status after update — check all fields
            csv_parts = sorted(p.strip() for p in re.split(r'[;,]', record.csv_owner_name or '') if p.strip())
            excel_parts = sorted(p.strip() for p in re.split(r'[;,]', record.excel_owner_name or '') if p.strip())
            names_ok = csv_parts == excel_parts
            type_ok = (record.csv_space_type or '') == (record.excel_space_type or '')
            own_ok = (record.csv_ownership_type or '') == (record.excel_ownership_type or '')
            podil_ok = (record.excel_podil_scd or 0) == (record.csv_share or 0)
            if names_ok:
                record.status = SyncStatus.MATCH
                if type_ok and own_ok and podil_ok:
                    record.match_details = "100%"

            success_count += 1
            change_details.append(f"J. {short_num}: {', '.join(changes)}")

    # Batch log & recalculate session totals
    if updates:
        log = ImportLog(
            filename=f"sync_session_{session_id}",
            file_path=f"sync_update/{session_id}",
            import_type="sync_update",
            rows_total=len(updates),
            rows_imported=success_count,
            rows_skipped=error_count,
            errors="\n".join(change_details) if change_details else None,
        )
        db.add(log)

        # Recalculate session counts from current record statuses
        all_records = db.query(SyncRecord).filter_by(session_id=session_id).all()
        session.total_matches = sum(1 for r in all_records if r.status == SyncStatus.MATCH)
        session.total_name_order = sum(1 for r in all_records if r.status == SyncStatus.NAME_ORDER)
        session.total_differences = sum(1 for r in all_records if r.status == SyncStatus.DIFFERENCE)
        session.total_missing = sum(1 for r in all_records if r.status in (SyncStatus.MISSING_CSV, SyncStatus.MISSING_EXCEL))

    db.commit()
    filtr = form.get("filtr", "")
    url = f"/synchronizace/{session_id}"
    if filtr:
        url += f"?filtr={filtr}"
    return RedirectResponse(url, status_code=302)


@router.get("/{session_id}/nahled-kontaktu")
async def contacts_preview(
    session_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Preview contact transfers before applying."""
    session = db.query(SyncSession).get(session_id)
    if not session:
        return RedirectResponse("/synchronizace", status_code=302)

    preview = _build_contact_preview(session_id, db)
    back_url = f"/synchronizace/{session_id}"

    return templates.TemplateResponse(request, "sync/contacts_preview.html", {
        "active_nav": "kontroly",
        "session": session,
        "preview": preview,
        "total_email": sum(1 for p in preview if p["will_email"]),
        "total_phone": sum(1 for p in preview if p["will_phone"]),
        "back_url": back_url,
    })


@router.post("/{session_id}/aplikovat-kontakty")
async def apply_contacts(session_id: int, db: Session = Depends(get_db)):
    """Apply email and phone from CSV to matching owners."""
    records = (
        db.query(SyncRecord)
        .filter_by(session_id=session_id)
        .filter(SyncRecord.status == SyncStatus.MATCH)
        .all()
    )

    updated = 0
    seen_owners: set[int] = set()
    for record in records:
        if not record.unit_number:
            continue
        short_num = record.unit_number
        owner_units = (
            db.query(OwnerUnit)
            .join(OwnerUnit.unit)
            .filter(Unit.unit_number.endswith(f"/{short_num}") | (Unit.unit_number == short_num))
            .filter(OwnerUnit.valid_to.is_(None))
            .all()
        )

        for ou in owner_units:
            if ou.owner_id in seen_owners:
                continue
            seen_owners.add(ou.owner_id)

            owner = db.query(Owner).get(ou.owner_id)
            if not owner:
                continue

            changed = False
            if record.csv_email and not owner.email:
                owner.email = record.csv_email
                changed = True
            if record.csv_phone and not owner.phone:
                owner.phone = record.csv_phone
                changed = True

            if changed:
                owner.updated_at = utcnow()
                updated += 1

    db.commit()
    return RedirectResponse(f"/synchronizace/{session_id}", status_code=302)
