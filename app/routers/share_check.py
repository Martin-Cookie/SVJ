import shutil
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import (
    ImportLog, ShareCheckColumnMapping, ShareCheckRecord, ShareCheckResolution,
    ShareCheckSession, ShareCheckStatus, Unit,
)
from app.services.share_check_comparator import (
    compare_shares, get_file_headers, get_file_preview, parse_file, suggest_mapping,
)

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


SORT_COLUMNS = {
    "unit": ShareCheckRecord.unit_number,
    "db_share": ShareCheckRecord.db_share,
    "file_share": ShareCheckRecord.file_share,
    "status": ShareCheckRecord.status,
}


@router.get("/")
async def share_check_list(
    request: Request,
    back: str = Query("", alias="back"),
    db: Session = Depends(get_db),
):
    sessions = db.query(ShareCheckSession).order_by(ShareCheckSession.created_at.desc()).all()
    list_url = str(request.url.path)
    if request.url.query:
        list_url += "?" + str(request.url.query)

    return templates.TemplateResponse("share_check/index.html", {
        "request": request,
        "active_nav": "share_check",
        "sessions": sessions,
        "back_url": back,
        "list_url": list_url,
    })


@router.post("/nova")
async def share_check_upload(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    if not file.filename:
        return RedirectResponse("/kontrola-podilu", status_code=302)

    # Save file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = settings.upload_dir / "share_check" / f"{timestamp}_{file.filename}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Redirect to mapping page (PRG pattern)
    from urllib.parse import urlencode
    params = urlencode({"file_path": str(dest), "filename": file.filename})
    return RedirectResponse(f"/kontrola-podilu/mapovani?{params}", status_code=302)


@router.get("/mapovani")
async def share_check_mapping(
    request: Request,
    file_path: str = Query(...),
    filename: str = Query(...),
    db: Session = Depends(get_db),
):
    if not Path(file_path).is_file():
        return RedirectResponse("/kontrola-podilu", status_code=302)

    try:
        headers = get_file_headers(file_path)
    except Exception:
        return RedirectResponse("/kontrola-podilu", status_code=302)

    if not headers:
        return RedirectResponse("/kontrola-podilu", status_code=302)

    col_unit, col_share, from_history = suggest_mapping(headers, db)

    try:
        preview = get_file_preview(file_path)
    except Exception:
        preview = {}

    return templates.TemplateResponse("share_check/mapping.html", {
        "request": request,
        "active_nav": "share_check",
        "headers": headers,
        "col_unit": col_unit,
        "col_share": col_share,
        "from_history": from_history,
        "file_path": file_path,
        "filename": filename,
        "preview": preview,
    })


@router.post("/potvrdit-mapovani")
async def share_check_confirm_mapping(
    request: Request,
    file_path: str = Form(...),
    filename: str = Form(...),
    col_unit: str = Form(...),
    col_share: str = Form(...),
    db: Session = Depends(get_db),
):
    # Validate file exists
    if not Path(file_path).is_file():
        return RedirectResponse("/kontrola-podilu", status_code=302)

    # Parse file
    file_records = parse_file(file_path, col_unit, col_share)
    if not file_records:
        return RedirectResponse("/kontrola-podilu", status_code=302)

    # Compare with DB
    comparison = compare_shares(file_records, db)

    # Save/update column mapping
    existing = (
        db.query(ShareCheckColumnMapping)
        .filter_by(col_unit=col_unit, col_share=col_share)
        .first()
    )
    if existing:
        existing.used_count += 1
        existing.last_used_at = datetime.utcnow()
    else:
        mapping = ShareCheckColumnMapping(
            col_unit=col_unit,
            col_share=col_share,
        )
        db.add(mapping)

    # Create session
    session = ShareCheckSession(
        filename=filename,
        file_path=file_path,
        col_unit=col_unit,
        col_share=col_share,
        total_records=len(comparison),
        total_matches=sum(1 for c in comparison if c["status"] == ShareCheckStatus.MATCH),
        total_differences=sum(1 for c in comparison if c["status"] == ShareCheckStatus.DIFFERENCE),
        total_missing_db=sum(1 for c in comparison if c["status"] == ShareCheckStatus.MISSING_DB),
        total_missing_file=sum(1 for c in comparison if c["status"] == ShareCheckStatus.MISSING_FILE),
    )
    db.add(session)
    db.flush()

    for comp in comparison:
        record = ShareCheckRecord(
            session_id=session.id,
            unit_number=comp["unit_number"],
            db_share=comp["db_share"],
            file_share=comp["file_share"],
            status=comp["status"],
            resolution=(
                ShareCheckResolution.PENDING
                if comp["status"] != ShareCheckStatus.MATCH
                else ShareCheckResolution.SKIPPED
            ),
        )
        db.add(record)

    db.commit()
    return RedirectResponse(f"/kontrola-podilu/{session.id}", status_code=302)


@router.get("/{session_id}")
async def share_check_detail(
    session_id: int,
    request: Request,
    filtr: str = Query("", alias="filtr"),
    sort: str = Query("unit", alias="sort"),
    order: str = Query("asc", alias="order"),
    back: str = Query("", alias="back"),
    db: Session = Depends(get_db),
):
    session = db.query(ShareCheckSession).get(session_id)
    if not session:
        return RedirectResponse("/kontrola-podilu", status_code=302)

    base = db.query(ShareCheckRecord).filter_by(session_id=session_id)

    # Totals for bubbles
    total_match = session.total_matches
    total_diff = session.total_differences
    total_missing_db = session.total_missing_db
    total_missing_file = session.total_missing_file

    # Sum of shares per category
    def _share_sums(flt):
        r = db.query(
            func.sum(ShareCheckRecord.db_share),
            func.sum(ShareCheckRecord.file_share),
        ).filter_by(session_id=session_id).filter(flt).one()
        return r[0] or 0, r[1] or 0

    match_db, match_file = _share_sums(ShareCheckRecord.status == ShareCheckStatus.MATCH)
    diff_db, diff_file = _share_sums(ShareCheckRecord.status == ShareCheckStatus.DIFFERENCE)
    missing_db_db, missing_db_file = _share_sums(ShareCheckRecord.status == ShareCheckStatus.MISSING_DB)
    missing_file_db, missing_file_file = _share_sums(ShareCheckRecord.status == ShareCheckStatus.MISSING_FILE)

    total_db_share = (match_db + diff_db + missing_file_db)
    total_file_share = (match_file + diff_file + missing_db_file)

    # Filter
    query = base
    if filtr == "match":
        query = query.filter(ShareCheckRecord.status == ShareCheckStatus.MATCH)
    elif filtr == "rozdil":
        query = query.filter(ShareCheckRecord.status == ShareCheckStatus.DIFFERENCE)
    elif filtr == "chybi_db":
        query = query.filter(ShareCheckRecord.status == ShareCheckStatus.MISSING_DB)
    elif filtr == "chybi_soubor":
        query = query.filter(ShareCheckRecord.status == ShareCheckStatus.MISSING_FILE)

    # Sorting
    sort_col = SORT_COLUMNS.get(sort)
    if sort_col is not None:
        if order == "desc":
            query = query.order_by(sort_col.desc().nulls_last())
        else:
            query = query.order_by(sort_col.asc().nulls_last())
    else:
        query = query.order_by(ShareCheckRecord.unit_number.asc())

    records = query.all()

    # Build unit_number → unit_id mapping for clickable links
    unit_map = {}
    units = db.query(Unit.unit_number, Unit.id).all()
    for unit_num, unit_id in units:
        unit_map[unit_num] = unit_id

    back_url = back or "/kontrola-podilu"
    back_label = "Zpět na přehled" if back == "/" else "Zpět"

    return templates.TemplateResponse("share_check/compare.html", {
        "request": request,
        "active_nav": "share_check",
        "session": session,
        "records": records,
        "filtr": filtr,
        "sort": sort,
        "order": order,
        "back_url": back_url,
        "back_label": back_label,
        "total_match": total_match,
        "total_diff": total_diff,
        "total_missing_db": total_missing_db,
        "total_missing_file": total_missing_file,
        "match_db": match_db,
        "match_file": match_file,
        "diff_db": diff_db,
        "diff_file": diff_file,
        "missing_db_db": missing_db_db,
        "missing_db_file": missing_db_file,
        "missing_file_db": missing_file_db,
        "missing_file_file": missing_file_file,
        "total_db_share": total_db_share,
        "total_file_share": total_file_share,
        "unit_map": unit_map,
    })


@router.post("/{session_id}/smazat")
async def share_check_delete(session_id: int, db: Session = Depends(get_db)):
    session = db.query(ShareCheckSession).get(session_id)
    if session:
        try:
            p = Path(session.file_path)
            if p.exists():
                p.unlink()
        except Exception:
            pass
        db.delete(session)
        db.commit()
    return RedirectResponse("/kontrola-podilu", status_code=302)


@router.post("/{session_id}/aktualizovat")
async def share_check_apply_updates(
    session_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Batch update Unit.podil_scd from selected file values."""
    form = await request.form()

    session = db.query(ShareCheckSession).get(session_id)
    if not session:
        return RedirectResponse("/kontrola-podilu", status_code=302)

    # Collect record IDs from checkboxes: update__{record_id}
    record_ids = []
    for key in form.keys():
        if key.startswith("update__"):
            try:
                rid = int(key.split("__")[1])
                record_ids.append(rid)
            except (ValueError, IndexError):
                continue

    if not record_ids:
        filtr = form.get("filtr", "")
        url = f"/kontrola-podilu/{session_id}"
        if filtr:
            url += f"?filtr={filtr}"
        return RedirectResponse(url, status_code=302)

    success_count = 0
    change_details = []
    now = datetime.now().strftime("%d.%m.%Y %H:%M")

    for rid in record_ids:
        record = db.query(ShareCheckRecord).filter_by(
            id=rid, session_id=session_id,
        ).first()
        if not record or record.file_share is None:
            continue

        unit = db.query(Unit).filter_by(unit_number=record.unit_number).first()
        if not unit:
            continue

        old_val = unit.podil_scd
        unit.podil_scd = record.file_share
        record.db_share = record.file_share
        record.status = ShareCheckStatus.MATCH
        record.resolution = ShareCheckResolution.UPDATED
        record.admin_note = f"Aktualizováno {now}: {old_val} → {record.file_share}"

        success_count += 1
        change_details.append(f"J. {record.unit_number}: {old_val} → {record.file_share}")

    if record_ids:
        log = ImportLog(
            filename=f"share_check_{session_id}",
            file_path=f"share_check_update/{session_id}",
            import_type="share_check_update",
            rows_total=len(record_ids),
            rows_imported=success_count,
            rows_skipped=len(record_ids) - success_count,
            errors="\n".join(change_details) if change_details else None,
        )
        db.add(log)

        # Recalculate session totals
        all_records = db.query(ShareCheckRecord).filter_by(session_id=session_id).all()
        session.total_matches = sum(1 for r in all_records if r.status == ShareCheckStatus.MATCH)
        session.total_differences = sum(1 for r in all_records if r.status == ShareCheckStatus.DIFFERENCE)
        session.total_missing_db = sum(1 for r in all_records if r.status == ShareCheckStatus.MISSING_DB)
        session.total_missing_file = sum(1 for r in all_records if r.status == ShareCheckStatus.MISSING_FILE)

    db.commit()
    filtr = form.get("filtr", "")
    url = f"/kontrola-podilu/{session_id}"
    if filtr:
        url += f"?filtr={filtr}"
    return RedirectResponse(url, status_code=302)
