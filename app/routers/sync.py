import shutil
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.database import get_db
from app.models import (
    Owner, OwnerUnit, SyncRecord, SyncResolution, SyncSession, SyncStatus, Unit,
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
            })

    # Compare
    comparison = compare_owners(csv_records, excel_data)

    # Create session and records
    session = SyncSession(
        csv_filename=file.filename,
        csv_path=str(dest),
        total_records=len(comparison),
        total_matches=sum(1 for c in comparison if c["status"] == SyncStatus.MATCH),
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
            csv_email=comp.get("csv_email", ""),
            csv_phone=comp.get("csv_phone", ""),
            status=comp["status"],
            match_details=comp.get("match_details"),
            resolution=(
                SyncResolution.ACCEPTED
                if comp["status"] == SyncStatus.MATCH
                else SyncResolution.PENDING
            ),
        )
        db.add(record)

    db.commit()
    return RedirectResponse(f"/synchronizace/{session.id}", status_code=302)


@router.get("/{session_id}")
async def sync_detail(session_id: int, request: Request, db: Session = Depends(get_db)):
    session = db.query(SyncSession).get(session_id)
    if not session:
        return RedirectResponse("/synchronizace", status_code=302)

    records = (
        db.query(SyncRecord)
        .filter_by(session_id=session_id)
        .order_by(SyncRecord.id)
        .all()
    )

    return templates.TemplateResponse("sync/compare.html", {
        "request": request,
        "active_nav": "sync",
        "session": session,
        "records": records,
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
