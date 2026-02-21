import shutil
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.database import get_db
from app.models import (
    ImportLog, Owner, OwnerUnit, SyncRecord, SyncResolution, SyncSession,
    SyncStatus, Unit,
)
from app.services.csv_comparator import compare_owners, parse_sousede_csv
from app.services.excel_export import export_owners_to_excel

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/")
async def sync_list(request: Request, db: Session = Depends(get_db)):
    sessions = db.query(SyncSession).order_by(SyncSession.created_at.desc()).all()
    return templates.TemplateResponse("sync/index.html", {
        "request": request,
        "active_nav": "sync",
        "sessions": sessions,
    })


@router.get("/nova")
async def sync_create_page(request: Request):
    return templates.TemplateResponse("sync/upload.html", {
        "request": request,
        "active_nav": "sync",
    })


@router.post("/nova")
async def sync_create(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    if not file.filename:
        return RedirectResponse("/synchronizace/nova", status_code=302)

    # Save CSV
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = settings.upload_dir / "csv" / f"{timestamp}_{file.filename}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Read CSV content - try multiple encodings
    csv_content = None
    for encoding in ["utf-8", "cp1250", "latin-1"]:
        try:
            with open(dest, "r", encoding=encoding) as f:
                csv_content = f.read()
            break
        except UnicodeDecodeError:
            continue

    if not csv_content:
        return templates.TemplateResponse("sync/upload.html", {
            "request": request,
            "active_nav": "sync",
            "flash_message": "Nepodařilo se přečíst CSV soubor.",
            "flash_type": "error",
        })

    csv_records = parse_sousede_csv(csv_content)

    # Get current Excel data
    owners = db.query(Owner).filter_by(is_active=True).options(
        joinedload(Owner.units)
    ).all()

    excel_data = []
    for owner in owners:
        for ou in owner.units:
            # Strip building prefix from unit number (e.g. "1098/14" -> "14")
            # to match CSV format which uses short unit numbers
            unit_num = ou.unit.unit_number
            if "/" in unit_num:
                unit_num = unit_num.split("/")[-1].strip()
            excel_data.append({
                "unit_number": unit_num,
                "owner_name": owner.name_with_titles,
                "name_normalized": owner.name_normalized,
                "owner_type": owner.owner_type.value,
                "space_type": ou.unit.space_type or "",
                "podil_scd": ou.unit.podil_scd or 0,
                "ownership_type": ou.ownership_type or "",
            })

    # Compare
    comparison = compare_owners(csv_records, excel_data)

    # Create session and records
    session = SyncSession(
        csv_filename=file.filename,
        csv_path=str(dest),
        total_records=len(comparison),
        total_matches=sum(1 for c in comparison if c["status"] == SyncStatus.MATCH),
        total_name_order=sum(1 for c in comparison if c["status"] == SyncStatus.NAME_ORDER),
        total_differences=sum(1 for c in comparison if c["status"] == SyncStatus.DIFFERENCE),
        total_missing=sum(
            1 for c in comparison
            if c["status"] in (SyncStatus.MISSING_CSV, SyncStatus.MISSING_EXCEL)
        ),
    )
    db.add(session)
    db.flush()

    for comp in comparison:
        record = SyncRecord(
            session_id=session.id,
            unit_number=comp["unit_number"],
            csv_owner_name=comp.get("csv_owner_name"),
            excel_owner_name=comp.get("excel_owner_name"),
            csv_ownership_type=comp.get("csv_ownership_type"),
            excel_ownership_type=comp.get("excel_ownership_type"),
            csv_space_type=comp.get("csv_space_type"),
            excel_space_type=comp.get("excel_space_type"),
            excel_podil_scd=comp.get("excel_podil_scd"),
            csv_share=comp.get("csv_share"),
            csv_email=comp.get("csv_email", ""),
            csv_phone=comp.get("csv_phone", ""),
            status=comp["status"],
            match_details=comp.get("match_details"),
            resolution=(
                SyncResolution.ACCEPTED
                if comp["status"] in (SyncStatus.MATCH, SyncStatus.NAME_ORDER)
                else SyncResolution.PENDING
            ),
        )
        db.add(record)

    db.commit()
    return RedirectResponse(f"/synchronizace/{session.id}", status_code=302)


@router.get("/{session_id}")
async def sync_detail(
    session_id: int,
    request: Request,
    filtr: str = Query("", alias="filtr"),
    db: Session = Depends(get_db),
):
    session = db.query(SyncSession).get(session_id)
    if not session:
        return RedirectResponse("/synchronizace", status_code=302)

    query = db.query(SyncRecord).filter_by(session_id=session_id)
    if filtr == "match":
        query = query.filter(SyncRecord.status == SyncStatus.MATCH)
    elif filtr == "name_order":
        query = query.filter(SyncRecord.status == SyncStatus.NAME_ORDER)
    elif filtr == "difference":
        query = query.filter(SyncRecord.status == SyncStatus.DIFFERENCE)
    elif filtr == "missing":
        query = query.filter(SyncRecord.status.in_([SyncStatus.MISSING_CSV, SyncStatus.MISSING_EXCEL]))
    records = query.order_by(SyncRecord.id).all()

    return templates.TemplateResponse("sync/compare.html", {
        "request": request,
        "active_nav": "sync",
        "session": session,
        "records": records,
        "filtr": filtr,
    })


@router.post("/{session_id}/prijmout/{record_id}")
async def accept_change(
    session_id: int,
    record_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    record = db.query(SyncRecord).get(record_id)
    if record:
        record.resolution = SyncResolution.ACCEPTED
        db.commit()

    if request.headers.get("HX-Request"):
        return templates.TemplateResponse("partials/sync_row.html", {
            "request": request,
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
    record = db.query(SyncRecord).get(record_id)
    if record:
        record.resolution = SyncResolution.REJECTED
        db.commit()

    if request.headers.get("HX-Request"):
        return templates.TemplateResponse("partials/sync_row.html", {
            "request": request,
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
    record = db.query(SyncRecord).get(record_id)
    if record:
        record.admin_corrected_name = corrected_name
        record.resolution = SyncResolution.MANUAL_EDIT
        db.commit()

    if request and request.headers.get("HX-Request"):
        return templates.TemplateResponse("partials/sync_row.html", {
            "request": request,
            "record": record,
        })
    return RedirectResponse(f"/synchronizace/{session_id}", status_code=302)


@router.post("/{session_id}/exportovat")
async def export_excel(session_id: int, db: Session = Depends(get_db)):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = settings.generated_dir / "exports" / f"vlastnici_{timestamp}.xlsx"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    export_owners_to_excel(db, str(output_path))
    return FileResponse(
        str(output_path),
        filename=f"vlastnici_{timestamp}.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


ALLOWED_UPDATE_FIELDS = {"ownership_type", "space_type", "podil_scd"}


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
                Unit.unit_number.endswith(f"/{short_num}")
                | (Unit.unit_number == short_num)
            )
            .first()
        )
        if not unit:
            error_count += 1
            change_details.append(f"Jednotka {short_num}: nenalezena")
            continue

        owner_unit = db.query(OwnerUnit).filter_by(unit_id=unit.id).first()
        if not owner_unit:
            error_count += 1
            change_details.append(f"Jednotka {short_num}: vlastník nenalezen")
            continue

        changes = []
        for field, new_value in fields.items():
            if field == "ownership_type":
                old_val = owner_unit.ownership_type or ""
                owner_unit.ownership_type = new_value
                changes.append(f"vlastnictví: {old_val} → {new_value}")
            elif field == "space_type":
                old_val = unit.space_type or ""
                unit.space_type = new_value
                changes.append(f"typ: {old_val} → {new_value}")
            elif field == "podil_scd":
                old_val = unit.podil_scd
                unit.podil_scd = int(new_value)
                changes.append(
                    f"podíl: {old_val} → {new_value}"
                )

        if changes:
            record.admin_note = (record.admin_note + "; " if record.admin_note else "") + ", ".join(changes)
            record.resolution = SyncResolution.MANUAL_EDIT
            success_count += 1
            change_details.append(f"J. {short_num}: {', '.join(changes)}")

    # Batch log
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

    db.commit()
    return RedirectResponse(f"/synchronizace/{session_id}", status_code=302)


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
    for record in records:
        if not record.unit_number:
            continue
        # Find owner by unit number — record has short number (e.g. "14"),
        # DB has full KN number (e.g. "1098/14"), so search with LIKE suffix
        short_num = record.unit_number
        owner_unit = (
            db.query(OwnerUnit)
            .join(OwnerUnit.unit)
            .filter(Unit.unit_number.endswith(f"/{short_num}") | (Unit.unit_number == short_num))
            .first()
        )
        if not owner_unit:
            continue

        owner = db.query(Owner).get(owner_unit.owner_id)
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
            owner.updated_at = datetime.utcnow()
            updated += 1

    db.commit()
    return RedirectResponse(f"/synchronizace/{session_id}", status_code=302)
