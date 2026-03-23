from __future__ import annotations

import json
import shutil
import threading
import time as _time
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal, get_db
from app.models import ActivityAction, ImportLog, log_activity
from app.services.contact_import import preview_contact_import, execute_contact_import
from app.services.import_mapping import (
    CONTACT_FIELD_DEFS, CONTACT_FIELD_GROUPS,
    build_mapping_context, read_excel_headers, read_excel_sheet_names,
    validate_contact_mapping,
)
from app.utils import UPLOAD_LIMITS, build_import_wizard, compute_eta, is_safe_path, validate_upload

from ._helpers import (
    _load_contact_mapping,
    _save_contact_mapping,
    logger,
    templates,
)

router = APIRouter()

# In-memory progress tracker for contact import background processing
_contact_import_progress: dict[str, dict] = {}


@router.get("/import-kontaktu")
async def contact_import_page():
    """Redirect to unified import page (contacts section)."""
    return RedirectResponse("/vlastnici/import#kontakty", status_code=302)


@router.post("/import-kontaktu")
async def contact_import_upload(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Nahrání Excel souboru s kontakty a přesměrování na mapování."""
    if not file.filename:
        return RedirectResponse("/vlastnici/import?chyba_kontakty=format#kontakty", status_code=302)

    err = await validate_upload(file, **UPLOAD_LIMITS["excel"])
    if err:
        return RedirectResponse(f"/vlastnici/import?chyba_kontakty_msg={quote(err)}#kontakty", status_code=302)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = settings.upload_dir / "excel" / f"{timestamp}_{file.filename}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Show mapping page instead of directly processing
    return _contact_mapping_page(request, str(dest), file.filename, db)


@router.post("/import-kontaktu/mapovani")
async def contact_mapping_reload(
    request: Request,
    file_path: str = Form(...),
    filename: str = Form(""),
    sheet_name: str = Form(""),
    start_row: int = Form(1),
    db: Session = Depends(get_db),
):
    """Reload contact mapping page with different sheet/start_row."""
    if not is_safe_path(Path(file_path), settings.upload_dir):
        return RedirectResponse("/vlastnici/import#kontakty", status_code=302)
    return _contact_mapping_page(request, file_path, filename, db, sheet_name=sheet_name or None, start_row=start_row)


def _contact_mapping_page(
    request: Request,
    file_path: str,
    filename: str,
    db: Session,
    sheet_name: str | None = None,
    start_row: int | None = None,
):
    """Build and return contact mapping page context."""
    if not Path(file_path).exists():
        return RedirectResponse("/vlastnici/import?chyba_kontakty=soubor_chybi#kontakty", status_code=302)
    sheets = read_excel_sheet_names(file_path)
    current_sheet = sheet_name or (sheets[0] if sheets else None)

    saved_mapping = _load_contact_mapping(db)
    sr = start_row or (saved_mapping or {}).get("start_row", 7)
    header_row = max(1, sr - 1)

    headers = read_excel_headers(file_path, sheet_name=current_sheet, header_row=header_row)

    ctx = build_mapping_context(headers, CONTACT_FIELD_DEFS, CONTACT_FIELD_GROUPS, saved_mapping)

    return templates.TemplateResponse("owners/contact_import_mapping.html", {
        "request": request,
        "active_nav": "owners",
        **build_import_wizard(2),
        "file_path": file_path,
        "filename": filename or Path(file_path).name,
        "sheets": sheets,
        "current_sheet": current_sheet,
        "start_row": sr,
        **ctx,
    })


@router.post("/import-kontaktu/nahled")
async def contact_import_mapping_submit(
    request: Request,
    file_path: str = Form(...),
    filename: str = Form(""),
    mapping_json: str = Form(""),
    db: Session = Depends(get_db),
):
    """Step 2 -> 3: Mapping -> start background processing."""
    if not is_safe_path(Path(file_path), settings.upload_dir):
        return RedirectResponse("/vlastnici/import#kontakty", status_code=302)
    if not Path(file_path).exists():
        return RedirectResponse("/vlastnici/import?chyba_kontakty=soubor_chybi#kontakty", status_code=302)

    # Parse mapping
    mapping = None
    if mapping_json:
        try:
            mapping = json.loads(mapping_json)
        except json.JSONDecodeError:
            logger.debug("Failed to parse contact mapping JSON for preview", exc_info=True)

    if mapping:
        err = validate_contact_mapping(mapping)
        if err:
            return _contact_mapping_page(request, file_path, filename, db)

        # Save mapping if requested
        if mapping.pop("save", False):
            _save_contact_mapping(db, mapping)

    file_key = Path(file_path).name

    # Initialize progress tracker
    _contact_import_progress[file_key] = {
        "done": False,
        "error": None,
        "result": None,
        "file_path": file_path,
        "filename": filename,
        "mapping": mapping,
        "started_at": _time.monotonic(),
        "total": 0,
        "current": 0,
        "phase": "Připravuji...",
    }

    # Start background processing thread
    thread = threading.Thread(
        target=_run_contact_preview,
        args=(file_key, file_path),
        daemon=True,
    )
    thread.start()

    return RedirectResponse(f"/vlastnici/import-kontaktu/zpracovani?soubor={quote(file_key)}", status_code=302)


def _run_contact_preview(file_key: str, file_path: str):
    """Background thread: parse Excel and compare with DB."""
    db = SessionLocal()
    try:
        progress = _contact_import_progress[file_key]
        mapping = progress.get("mapping")
        result = preview_contact_import(file_path, db, progress=progress, mapping=mapping)
        progress["result"] = result
    except Exception as e:
        logger.exception("Contact import failed for %s", file_key)
        _contact_import_progress[file_key]["error"] = str(e)
    finally:
        _contact_import_progress[file_key]["done"] = True
        db.close()


def _contact_progress_ctx(progress: dict) -> dict:
    """Compute progress context for contact import templates."""

    total = progress.get("total", 0)
    current = progress.get("current", 0)
    eta = compute_eta(current, total, progress["started_at"])
    return {
        "total": total,
        "current": current,
        **eta,
        "phase": progress.get("phase", "Připravuji..."),
    }


@router.get("/import-kontaktu/zpracovani")
async def contact_import_processing(
    request: Request,
    soubor: str = Query("", alias="soubor"),
):
    """Progress page -- HTMX polls /import-kontaktu/zpracovani-stav."""
    progress = _contact_import_progress.get(soubor)
    if not progress:
        return RedirectResponse("/vlastnici/import#kontakty", status_code=302)
    if progress.get("done"):
        return RedirectResponse(f"/vlastnici/import-kontaktu/nahled-vysledek?soubor={quote(soubor)}", status_code=302)

    return templates.TemplateResponse("owners/contact_import_processing.html", {
        "request": request,
        "active_nav": "owners",
        "file_key": soubor,
        **_contact_progress_ctx(progress),
    })


@router.get("/import-kontaktu/zpracovani-stav")
async def contact_import_status(
    request: Request,
    soubor: str = Query("", alias="soubor"),
):
    """HTMX polling endpoint -- returns progress partial or HX-Redirect when done."""
    progress = _contact_import_progress.get(soubor)
    if not progress:
        response = HTMLResponse("")
        response.headers["HX-Redirect"] = "/vlastnici/import#kontakty"
        return response

    if progress.get("done"):
        response = HTMLResponse("")
        response.headers["HX-Redirect"] = f"/vlastnici/import-kontaktu/nahled-vysledek?soubor={quote(soubor)}"
        return response

    return templates.TemplateResponse("partials/contact_import_progress.html", {
        "request": request,
        **_contact_progress_ctx(progress),
    })


@router.get("/import-kontaktu/nahled-vysledek")
async def contact_import_preview_page(
    request: Request,
    soubor: str = Query("", alias="soubor"),
):
    """Show preview from cached result after background processing."""
    data = _contact_import_progress.pop(soubor, None)
    if not data or not data.get("result"):
        # Check for error
        if data and data.get("error"):
            return RedirectResponse(f"/vlastnici/import?chyba_kontakty=zpracovani#kontakty", status_code=302)
        return RedirectResponse("/vlastnici/import#kontakty", status_code=302)

    mapping = data.get("mapping")
    mapping_json_str = json.dumps(mapping, ensure_ascii=False) if mapping else ""

    return templates.TemplateResponse("owners/contact_import_preview.html", {
        "request": request,
        "active_nav": "owners",
        **build_import_wizard(3),
        "preview": data["result"],
        "file_path": data["file_path"],
        "filename": data.get("filename", ""),
        "mapping_json": mapping_json_str,
    })


@router.get("/import-kontaktu/znovu")
async def contact_import_rerun(
    request: Request,
    soubor: str = Query("", alias="soubor"),
    db: Session = Depends(get_db),
):
    """Re-run preview for an already uploaded file."""
    if not soubor or not is_safe_path(Path(soubor), settings.upload_dir) or not Path(soubor).is_file():
        return RedirectResponse("/vlastnici/import#kontakty", status_code=302)

    file_key = Path(soubor).name
    saved_mapping = _load_contact_mapping(db)

    _contact_import_progress[file_key] = {
        "done": False,
        "error": None,
        "result": None,
        "file_path": soubor,
        "filename": Path(soubor).name,
        "mapping": saved_mapping,
        "started_at": _time.monotonic(),
        "total": 0,
        "current": 0,
        "phase": "Připravuji...",
    }

    thread = threading.Thread(
        target=_run_contact_preview,
        args=(file_key, soubor),
        daemon=True,
    )
    thread.start()

    return RedirectResponse(f"/vlastnici/import-kontaktu/zpracovani?soubor={quote(file_key)}", status_code=302)


@router.post("/import-kontaktu/potvrdit")
async def contact_import_confirm(
    request: Request,
    file_path: str = Form(...),
    overwrite: str = Form(""),
    mapping_json: str = Form(""),
    db: Session = Depends(get_db),
):
    """Potvrzení a provedení importu kontaktů pro vybrané vlastníky."""
    if not is_safe_path(Path(file_path), settings.upload_dir):
        return RedirectResponse("/vlastnici/import#kontakty", status_code=302)
    if not Path(file_path).exists():
        return RedirectResponse("/vlastnici/import?chyba_kontakty=soubor_chybi#kontakty", status_code=302)

    form_data = await request.form()
    selected = [int(v) for v in form_data.getlist("selected_owners")]

    if not selected:
        return RedirectResponse("/vlastnici/import#kontakty", status_code=302)

    # Parse mapping
    mapping = None
    if mapping_json:
        try:
            mapping = json.loads(mapping_json)
        except json.JSONDecodeError:
            logger.debug("Failed to parse contact mapping JSON for confirm", exc_info=True)

    result = execute_contact_import(file_path, db, selected, overwrite_existing=bool(overwrite), mapping=mapping)

    # Log the import
    log = ImportLog(
        filename=Path(file_path).name,
        file_path=file_path,
        import_type="contacts_excel",
        rows_total=result["owners_updated"] + (len(selected) - result["owners_updated"]),
        rows_imported=result["owners_updated"],
        rows_skipped=len(selected) - result["owners_updated"],
    )
    db.add(log)
    log_activity(db, ActivityAction.IMPORTED, "import", "vlastnici",
                 entity_name="Import kontaktů",
                 description=f"{result['owners_updated']} vlastníků, {result['fields_updated']} polí")
    db.commit()

    return templates.TemplateResponse("owners/contact_import_result.html", {
        "request": request,
        "active_nav": "owners",
        "result": result,
        "file_path": file_path,
    })


@router.post("/import-kontaktu/{log_id}/smazat")
async def contact_import_delete(
    log_id: int,
    db: Session = Depends(get_db),
):
    """Delete a contact import log entry and its uploaded file."""
    log = db.query(ImportLog).filter_by(id=log_id, import_type="contacts_excel").first()
    if not log:
        return RedirectResponse("/vlastnici/import", status_code=302)

    try:
        p = Path(log.file_path)
        if p.exists():
            p.unlink()
    except Exception:
        logger.debug("Failed to clean up file: %s", log.file_path)

    db.delete(log)
    db.commit()

    return RedirectResponse("/vlastnici/import", status_code=302)
