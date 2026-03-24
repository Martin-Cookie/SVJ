from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import ActivityAction, ImportLog, Space, log_activity
from app.services.import_mapping import (
    SPACE_FIELD_DEFS, SPACE_FIELD_GROUPS,
    build_mapping_context, detect_header_row, read_excel_headers,
    read_excel_sheet_names, validate_space_mapping,
)
from app.services.space_import import import_spaces_from_excel, preview_spaces_from_excel
from app.utils import UPLOAD_LIMITS, build_import_wizard, is_safe_path, validate_upload

from ._helpers import (
    _load_space_mapping,
    _save_space_mapping,
    logger,
    templates,
)

router = APIRouter()


# ── Step 1: Upload page ──────────────────────────────────────────────


@router.get("/import")
async def space_import_page(
    request: Request,
    chyba: str = Query(""),
    db: Session = Depends(get_db),
):
    """Stránka importu prostorů."""
    imports = (
        db.query(ImportLog)
        .filter_by(import_type="spaces_excel")
        .order_by(ImportLog.created_at.desc())
        .all()
    )
    space_count = db.query(Space).count()

    flash_message = None
    flash_type = None
    if chyba == "soubor_chybi":
        flash_message = "Nahraný soubor již neexistuje. Nahrajte soubor znovu."
        flash_type = "error"

    return templates.TemplateResponse("spaces/space_import.html", {
        "request": request,
        "active_nav": "spaces",
        **build_import_wizard(1),
        "imports": imports,
        "space_count": space_count,
        "flash_message": flash_message,
        "flash_type": flash_type,
    })


@router.post("/import")
async def space_import_upload(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Step 1: Upload Excel -> show mapping page."""
    err = await validate_upload(file, **UPLOAD_LIMITS["excel"]) if file.filename else "Nahrajte prosím soubor ve formátu .xlsx"
    if err:
        return templates.TemplateResponse("spaces/space_import.html", {
            "request": request,
            "active_nav": "spaces",
            **build_import_wizard(1),
            "flash_message": err,
            "flash_type": "error",
            "imports": [],
            "space_count": 0,
        })

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = settings.upload_dir / "excel" / f"{timestamp}_{file.filename}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    return _space_mapping_page(request, str(dest), file.filename, db)


# ── Step 2: Mapping ──────────────────────────────────────────────────


@router.post("/import/mapovani")
async def space_import_mapping_reload(
    request: Request,
    file_path: str = Form(...),
    filename: str = Form(""),
    sheet_name: str = Form(""),
    start_row: int = Form(1),
    db: Session = Depends(get_db),
):
    """Reload mapping page with different sheet/start_row."""
    if not is_safe_path(Path(file_path), settings.upload_dir):
        return RedirectResponse("/prostory/import", status_code=302)
    return _space_mapping_page(request, file_path, filename, db, sheet_name=sheet_name or None, start_row=start_row)


def _space_mapping_page(
    request: Request,
    file_path: str,
    filename: str,
    db: Session,
    sheet_name=None,
    start_row=None,
):
    """Build and return space mapping page context."""
    if not Path(file_path).exists():
        return RedirectResponse("/prostory/import?chyba=soubor_chybi", status_code=302)
    sheets = read_excel_sheet_names(file_path)
    current_sheet = sheet_name or (sheets[0] if sheets else None)

    saved_mapping = _load_space_mapping(db)

    # Always auto-detect header row from file content for best results
    detected_header, detected_start = detect_header_row(
        file_path, SPACE_FIELD_DEFS, sheet_name=current_sheet,
    )
    if start_row:
        sr = start_row
    elif saved_mapping and saved_mapping.get("start_row"):
        sr = saved_mapping["start_row"]
    else:
        sr = detected_start
    # Use detected header_row (it finds the row with best column matches)
    header_row = detected_header

    headers = read_excel_headers(file_path, sheet_name=current_sheet, header_row=header_row)

    ctx = build_mapping_context(headers, SPACE_FIELD_DEFS, SPACE_FIELD_GROUPS, saved_mapping)

    space_count = db.query(Space).count()

    return templates.TemplateResponse("spaces/space_import_mapping.html", {
        "request": request,
        "active_nav": "spaces",
        **build_import_wizard(2),
        "file_path": file_path,
        "filename": filename or Path(file_path).name,
        "sheets": sheets,
        "current_sheet": current_sheet,
        "start_row": sr,
        "space_count": space_count,
        **ctx,
    })


# ── Step 3: Preview ──────────────────────────────────────────────────


@router.post("/import/nahled")
async def space_import_preview(
    request: Request,
    file_path: str = Form(...),
    filename: str = Form(""),
    mapping_json: str = Form(""),
    db: Session = Depends(get_db),
):
    """Step 2: Mapping -> preview parsed data."""
    if not is_safe_path(Path(file_path), settings.upload_dir):
        return RedirectResponse("/prostory/import", status_code=302)
    if not Path(file_path).exists():
        return RedirectResponse("/prostory/import?chyba=soubor_chybi", status_code=302)

    mapping = None
    if mapping_json:
        try:
            mapping = json.loads(mapping_json)
        except json.JSONDecodeError:
            logger.debug("Failed to parse space mapping JSON for preview", exc_info=True)

    if mapping:
        err = validate_space_mapping(mapping)
        if err:
            return _space_mapping_page(request, file_path, filename, db)

        if mapping.pop("save", False):
            _save_space_mapping(db, mapping)

    preview = preview_spaces_from_excel(file_path, mapping=mapping, db=db)

    space_count = db.query(Space).count()

    return templates.TemplateResponse("spaces/space_import_preview.html", {
        "request": request,
        "active_nav": "spaces",
        **build_import_wizard(3),
        "preview": preview,
        "file_path": file_path,
        "filename": filename,
        "mapping_json": json.dumps(mapping, ensure_ascii=False) if mapping else "",
        "space_count": space_count,
    })


# ── Step 4: Confirm ──────────────────────────────────────────────────


@router.post("/import/potvrdit")
async def space_import_confirm(
    request: Request,
    file_path: str = Form(...),
    filename: str = Form(""),
    mapping_json: str = Form(""),
    import_mode: str = Form("append"),
    owner_overrides_json: str = Form(""),
    db: Session = Depends(get_db),
):
    """Step 3: Confirm preview and save to DB."""
    if not is_safe_path(Path(file_path), settings.upload_dir):
        return RedirectResponse("/prostory/import", status_code=302)
    if not Path(file_path).exists():
        return RedirectResponse("/prostory/import?chyba=soubor_chybi", status_code=302)

    mapping = None
    if mapping_json:
        try:
            mapping = json.loads(mapping_json)
        except json.JSONDecodeError:
            logger.debug("Failed to parse space mapping JSON for confirm", exc_info=True)

    # Parse owner overrides (space_number → owner_id)
    owner_overrides = None
    if owner_overrides_json:
        try:
            raw = json.loads(owner_overrides_json)
            owner_overrides = {int(k): int(v) for k, v in raw.items() if v}
        except (json.JSONDecodeError, ValueError):
            logger.debug("Failed to parse owner overrides JSON", exc_info=True)

    # Replace mode: delete all existing spaces, tenants, contracts first
    if import_mode == "replace":
        from app.models import SpaceTenant, Tenant, VariableSymbolMapping, Prescription
        # Delete in FK order
        db.query(SpaceTenant).delete()
        db.query(Tenant).delete()
        db.query(VariableSymbolMapping).filter(
            VariableSymbolMapping.space_id.isnot(None)
        ).delete(synchronize_session=False)
        db.query(Prescription).filter(
            Prescription.space_id.isnot(None)
        ).delete(synchronize_session=False)
        db.query(Space).delete()
        db.flush()

    result = import_spaces_from_excel(db, file_path, mapping=mapping,
                                      owner_overrides=owner_overrides)

    # Log the import
    log = ImportLog(
        filename=filename,
        file_path=file_path,
        import_type="spaces_excel",
        rows_total=result["rows_processed"],
        rows_imported=result["spaces_created"],
        rows_skipped=len(result["errors"]),
        errors="\n".join(result["errors"]) if result["errors"] else None,
    )
    db.add(log)
    log_activity(db, ActivityAction.IMPORTED, "import", "prostory",
                 entity_name="Import prostorů",
                 description=f"{result['spaces_created']} prostorů, {result['tenants_created']} nájemců")
    db.commit()

    return RedirectResponse(
        f"/prostory?flash=import_ok&imported={result['spaces_created']}&tenants={result['tenants_created']}",
        status_code=302,
    )


@router.post("/import/{log_id}/smazat")
async def space_import_delete(
    log_id: int,
    db: Session = Depends(get_db),
):
    """Delete an import log entry and its uploaded file."""
    log = db.query(ImportLog).filter_by(id=log_id, import_type="spaces_excel").first()
    if not log:
        return RedirectResponse("/prostory/import", status_code=302)

    try:
        p = Path(log.file_path)
        if p.exists():
            p.unlink()
    except Exception:
        logger.debug("Failed to clean up file: %s", log.file_path)

    db.delete(log)
    db.commit()

    return RedirectResponse("/prostory/import", status_code=302)
