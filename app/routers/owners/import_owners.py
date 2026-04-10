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
from app.models import ActivityAction, ImportLog, Owner, OwnerUnit, Unit, log_activity
from app.services.excel_import import import_owners_from_excel, preview_owners_from_excel
from app.services.import_mapping import (
    OWNER_FIELD_DEFS, OWNER_FIELD_GROUPS,
    build_mapping_context, read_excel_headers, read_excel_sheet_names,
    validate_owner_mapping,
)
from app.utils import UPLOAD_LIMITS, build_import_wizard, is_safe_path, validate_upload

from ._helpers import (
    _load_owner_mapping,
    _save_owner_mapping,
    logger,
    templates,
)

router = APIRouter()


@router.get("/import")
async def import_page(
    request: Request,
    chyba: str = Query(""),
    chyba_kontakty: str = Query("", alias="chyba_kontakty"),
    chyba_kontakty_msg: str = Query("", alias="chyba_kontakty_msg"),
    db: Session = Depends(get_db),
):
    """Stránka importu vlastníků a kontaktů s historií importů."""
    imports = db.query(ImportLog).filter_by(import_type="owners_excel").order_by(ImportLog.created_at.desc()).all()
    contact_imports = db.query(ImportLog).filter_by(import_type="contacts_excel").order_by(ImportLog.created_at.desc()).all()
    owner_count = db.query(Owner).count()

    flash_message = None
    flash_type = None
    if chyba == "soubor_chybi":
        flash_message = "Nahraný soubor již neexistuje. Nahrajte soubor znovu."
        flash_type = "error"

    contact_flash = None
    if chyba_kontakty_msg:
        contact_flash = chyba_kontakty_msg
    elif chyba_kontakty == "format":
        contact_flash = "Nahrajte soubor ve formátu .xlsx"
    elif chyba_kontakty == "zpracovani":
        contact_flash = "Chyba při zpracování souboru"
    elif chyba_kontakty == "soubor_chybi":
        contact_flash = "Nahraný soubor již neexistuje. Nahrajte soubor znovu."

    return templates.TemplateResponse(request, "owners/import.html", {
        "active_nav": "import",
        "imports": imports,
        "contact_imports": contact_imports,
        "contact_flash": contact_flash,
        "flash_message": flash_message,
        "flash_type": flash_type,
        "owner_count": owner_count,
    })


@router.post("/import")
async def import_excel_upload(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Step 1: Upload Excel -> show mapping page."""
    err = await validate_upload(file, **UPLOAD_LIMITS["excel"]) if file.filename else "Nahrajte prosím soubor ve formátu .xlsx"
    if err:
        return templates.TemplateResponse(request, "owners/import.html", {
            "active_nav": "import",
            "flash_message": err,
            "flash_type": "error",
        })

    # Save uploaded file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = settings.upload_dir / "excel" / f"{timestamp}_{file.filename}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Read headers and show mapping page
    return _owner_mapping_page(request, str(dest), file.filename, db)


@router.post("/import/mapovani")
async def import_owner_mapping_reload(
    request: Request,
    file_path: str = Form(...),
    filename: str = Form(""),
    sheet_name: str = Form(""),
    start_row: int = Form(1),
    db: Session = Depends(get_db),
):
    """Reload mapping page with different sheet/start_row."""
    if not is_safe_path(Path(file_path), settings.upload_dir):
        return RedirectResponse("/vlastnici/import", status_code=302)
    return _owner_mapping_page(request, file_path, filename, db, sheet_name=sheet_name or None, start_row=start_row)


def _owner_mapping_page(
    request: Request,
    file_path: str,
    filename: str,
    db: Session,
    sheet_name: str | None = None,
    start_row: int | None = None,
):
    """Build and return owner mapping page context."""
    if not Path(file_path).exists():
        return RedirectResponse("/vlastnici/import?chyba=soubor_chybi", status_code=302)
    sheets = read_excel_sheet_names(file_path)
    current_sheet = sheet_name or (sheets[0] if sheets else None)

    # Determine header row (one above start_row)
    saved_mapping = _load_owner_mapping(db)
    sr = start_row or (saved_mapping or {}).get("start_row", 2)
    header_row = max(1, sr - 1)

    headers = read_excel_headers(file_path, sheet_name=current_sheet, header_row=header_row)

    ctx = build_mapping_context(headers, OWNER_FIELD_DEFS, OWNER_FIELD_GROUPS, saved_mapping)

    owner_count = db.query(Owner).count()

    return templates.TemplateResponse(request, "owners/owner_import_mapping.html", {
        "active_nav": "import",
        **build_import_wizard(2),
        "file_path": file_path,
        "filename": filename or Path(file_path).name,
        "sheets": sheets,
        "current_sheet": current_sheet,
        "start_row": sr,
        "owner_count": owner_count,
        **ctx,
    })


@router.post("/import/nahled")
async def import_excel_preview(
    request: Request,
    file_path: str = Form(...),
    filename: str = Form(""),
    mapping_json: str = Form(""),
    db: Session = Depends(get_db),
):
    """Step 2: Mapping -> preview parsed data."""
    if not is_safe_path(Path(file_path), settings.upload_dir):
        return RedirectResponse("/vlastnici/import", status_code=302)
    if not Path(file_path).exists():
        return RedirectResponse("/vlastnici/import?chyba=soubor_chybi", status_code=302)

    # Parse mapping
    mapping = None
    if mapping_json:
        try:
            mapping = json.loads(mapping_json)
        except json.JSONDecodeError:
            logger.debug("Failed to parse owner mapping JSON for preview", exc_info=True)

    if mapping:
        err = validate_owner_mapping(mapping)
        if err:
            return _owner_mapping_page(request, file_path, filename, db)

        # Save mapping if requested
        if mapping.pop("save", False):
            _save_owner_mapping(db, mapping)

    preview = preview_owners_from_excel(file_path, mapping=mapping)

    return templates.TemplateResponse(request, "owners/import_preview.html", {
        "active_nav": "import",
        **build_import_wizard(3),
        "preview": preview,
        "file_path": file_path,
        "filename": filename,
        "mapping_json": json.dumps(mapping, ensure_ascii=False) if mapping else "",
    })


@router.post("/import/potvrdit")
async def import_excel_confirm(
    request: Request,
    file_path: str = Form(...),
    filename: str = Form(""),
    mapping_json: str = Form(""),
    db: Session = Depends(get_db),
):
    """Step 3: Confirm preview and save to DB."""
    if not is_safe_path(Path(file_path), settings.upload_dir):
        return RedirectResponse("/vlastnici/import", status_code=302)
    if not Path(file_path).exists():
        return RedirectResponse("/vlastnici/import?chyba=soubor_chybi", status_code=302)

    # Parse mapping
    mapping = None
    if mapping_json:
        try:
            mapping = json.loads(mapping_json)
        except json.JSONDecodeError:
            logger.debug("Failed to parse owner mapping JSON for confirm", exc_info=True)

    # Clear existing owners
    db.query(OwnerUnit).delete()
    db.query(Owner).delete()
    db.query(Unit).delete()
    db.commit()

    # Import
    result = import_owners_from_excel(db, file_path, mapping=mapping)

    # Log the import
    log = ImportLog(
        filename=filename,
        file_path=file_path,
        import_type="owners_excel",
        rows_total=result["rows_processed"],
        rows_imported=result["owners_created"],
        rows_skipped=len(result["errors"]),
        errors="\n".join(result["errors"]) if result["errors"] else None,
    )
    db.add(log)
    log_activity(db, ActivityAction.IMPORTED, "import", "vlastnici",
                 entity_name="Import vlastníků",
                 description=f"{result['owners_created']} vlastníků, {result.get('units_created', 0)} jednotek")
    db.commit()

    return templates.TemplateResponse(request, "owners/import_result.html", {
        "active_nav": "import",
        "result": result,
    })


@router.post("/import/{log_id}/smazat")
async def import_delete(
    log_id: int,
    db: Session = Depends(get_db),
):
    """Delete an import log entry and its uploaded file (data remain intact)."""
    log = db.query(ImportLog).filter_by(id=log_id, import_type="owners_excel").first()
    if not log:
        return RedirectResponse("/vlastnici/import", status_code=302)

    # Remove uploaded file
    try:
        p = Path(log.file_path)
        if p.exists():
            p.unlink()
    except Exception:
        logger.debug("Failed to clean up file: %s", log.file_path)

    # Remove log entry only
    db.delete(log)
    db.commit()

    return RedirectResponse("/vlastnici/import", status_code=302)
