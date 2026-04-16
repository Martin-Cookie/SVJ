from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

from fastapi import APIRouter, Depends, Form, Request, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import (
    Unit, WaterMeter, WaterReading, MeterType,
    ImportLog, ActivityAction, log_activity,
)
from app.models.administration import SvjInfo
from app.services.import_mapping import (
    WATER_METER_FIELD_DEFS, WATER_METER_FIELD_GROUPS,
    build_mapping_context, is_row_format, read_excel_headers,
    read_excel_sheet_names, validate_water_meter_mapping,
)
from app.utils import (
    build_import_wizard, is_safe_path, validate_upload, UPLOAD_LIMITS, templates,
)

from ._helpers import logger, parse_techem_xls, parse_water_readings_row_format, _parse_header_date

router = APIRouter()

# Temporary storage for parsed preview data (batch_id → data)
_preview_cache: dict[str, dict] = {}


def _load_water_mapping(db: Session) -> dict | None:
    """Load saved water meter mapping from SvjInfo."""
    svj = db.query(SvjInfo).first()
    if not svj:
        return None
    raw = getattr(svj, "water_meter_import_mapping", None)
    if raw:
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            pass
    return None


def _save_water_mapping(db: Session, mapping: dict):
    """Save water meter mapping to SvjInfo."""
    svj = db.query(SvjInfo).first()
    if svj:
        svj.water_meter_import_mapping = json.dumps(mapping, ensure_ascii=False)
        db.commit()


def _count_date_columns(file_path: str, sheet_name: str | None = None,
                        header_row: int = 1) -> int:
    """Count how many date columns are detected in the header row."""
    try:
        headers = read_excel_headers(file_path, sheet_name=sheet_name, header_row=header_row)
    except Exception:
        return 0
    count = 0
    for h in headers:
        if _parse_header_date(h):
            count += 1
    return count


# ---------------------------------------------------------------------------
# Step 1: Upload
# ---------------------------------------------------------------------------

@router.get("/import", response_class=HTMLResponse)
async def water_import_form(request: Request):
    flash = request.query_params.get("flash", "")
    flash_message = ""
    flash_type = ""
    if flash == "expired":
        flash_message = "Náhled vypršel. Nahrajte soubor znovu."
        flash_type = "error"

    return templates.TemplateResponse(request, "water_meters/import.html", {
        "active_nav": "water_meters",
        "flash_message": flash_message,
        "flash_type": flash_type,
        **build_import_wizard(1),
    })


@router.post("/import/nahrat")
async def water_import_upload(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    # Validate file
    err = await validate_upload(file, **UPLOAD_LIMITS["excel"])
    if err:
        return templates.TemplateResponse(request, "water_meters/import.html", {
            "active_nav": "water_meters",
            "flash_message": err,
            "flash_type": "error",
            **build_import_wizard(1),
        })

    # Save file
    upload_dir = settings.upload_dir / "water_meters"
    upload_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = file.filename or "import.xls"
    dest = upload_dir / f"{timestamp}_{filename}"
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Go to mapping page
    return _mapping_page(request, str(dest), filename, db)


# ---------------------------------------------------------------------------
# Step 2: Mapping
# ---------------------------------------------------------------------------

def _mapping_page(request: Request, file_path: str, filename: str, db: Session,
                  sheet_name: str | None = None, start_row: int | None = None):
    """Render the column mapping page."""
    sheets = read_excel_sheet_names(file_path)
    current_sheet = sheet_name or (sheets[0] if sheets else None)
    saved_mapping = _load_water_mapping(db)
    sr = start_row or (saved_mapping.get("start_row", 2) if saved_mapping else 2)
    header_row = max(1, sr - 1)
    headers = read_excel_headers(file_path, sheet_name=current_sheet, header_row=header_row)
    ctx = build_mapping_context(headers, WATER_METER_FIELD_DEFS, WATER_METER_FIELD_GROUPS, saved_mapping)

    # Count date columns detected
    date_columns_count = _count_date_columns(file_path, sheet_name=current_sheet, header_row=header_row)

    return templates.TemplateResponse(request, "water_meters/import_mapping.html", {
        "active_nav": "water_meters",
        **build_import_wizard(2),
        "file_path": file_path,
        "filename": filename,
        "sheets": sheets,
        "current_sheet": current_sheet,
        "start_row": sr,
        "date_columns_count": date_columns_count,
        **ctx,
    })


@router.post("/import/mapovani")
async def water_import_mapping_reload(
    request: Request,
    file_path: str = Form(...),
    filename: str = Form(...),
    sheet_name: str = Form(None),
    start_row: int = Form(2),
    db: Session = Depends(get_db),
):
    """Reload mapping page when user changes sheet or start row."""
    if not is_safe_path(Path(file_path), settings.upload_dir):
        return RedirectResponse("/vodometry/import", status_code=303)
    return _mapping_page(request, file_path, filename, db,
                         sheet_name=sheet_name, start_row=start_row)


# ---------------------------------------------------------------------------
# Step 3: Preview
# ---------------------------------------------------------------------------

@router.post("/import/nahled")
async def water_import_preview(
    request: Request,
    file_path: str = Form(...),
    filename: str = Form(...),
    mapping_json: str = Form(...),
    db: Session = Depends(get_db),
):
    """Parse XLS with mapping and show preview."""
    if not is_safe_path(Path(file_path), settings.upload_dir):
        return RedirectResponse("/vodometry/import", status_code=303)

    # Parse mapping
    try:
        mapping = json.loads(mapping_json)
    except (json.JSONDecodeError, TypeError):
        return templates.TemplateResponse(request, "water_meters/import.html", {
            "active_nav": "water_meters",
            "flash_message": "Neplatný formát mapování.",
            "flash_type": "error",
            **build_import_wizard(1),
        })

    # Validate
    err = validate_water_meter_mapping(mapping)
    if err:
        return templates.TemplateResponse(request, "water_meters/import.html", {
            "active_nav": "water_meters",
            "flash_message": err,
            "flash_type": "error",
            **build_import_wizard(1),
        })

    # Save mapping if requested
    if mapping.get("save"):
        _save_water_mapping(db, mapping)

    # Parse file with mapping — detect format
    sheet_name = mapping.get("sheet_name")
    start_row = mapping.get("start_row", 2)
    header_row = max(1, start_row - 1)

    try:
        if is_row_format(mapping):
            rows = parse_water_readings_row_format(
                file_path, mapping=mapping,
                sheet_name=sheet_name, header_row=header_row)
        else:
            rows = parse_techem_xls(
                file_path, mapping=mapping,
                sheet_name=sheet_name, header_row=header_row)
    except Exception as e:
        logger.error("Failed to parse XLS: %s", e)
        return templates.TemplateResponse(request, "water_meters/import.html", {
            "active_nav": "water_meters",
            "flash_message": f"Chyba při čtení souboru: {e}",
            "flash_type": "error",
            **build_import_wizard(1),
        })

    if not rows:
        return templates.TemplateResponse(request, "water_meters/import.html", {
            "active_nav": "water_meters",
            "flash_message": "Soubor neobsahuje žádná data.",
            "flash_type": "error",
            **build_import_wizard(1),
        })

    # Match unit_numbers against DB
    db_units = {u.unit_number: u for u in db.query(Unit).all()}
    for row in rows:
        un = row["unit_number"]
        row["unit_matched"] = un is not None and un in db_units
        row["unit_id"] = db_units[un].id if row["unit_matched"] else None

    # Store in preview cache
    batch_id = uuid4().hex[:12]
    _preview_cache[batch_id] = {
        "file_path": file_path,
        "filename": filename,
        "rows": rows,
    }

    return RedirectResponse(f"/vodometry/import/nahled/{batch_id}", status_code=303)


@router.get("/import/nahled/{batch_id}", response_class=HTMLResponse)
async def water_import_preview_page(request: Request, batch_id: str):
    data = _preview_cache.get(batch_id)
    if not data:
        return RedirectResponse("/vodometry/import?flash=expired", status_code=303)

    rows = data["rows"]
    matched = sum(1 for r in rows if r["unit_matched"])
    unmatched = len(rows) - matched
    total_readings = sum(len(r["readings"]) for r in rows)

    return templates.TemplateResponse(request, "water_meters/preview.html", {
        "active_nav": "water_meters",
        "batch_id": batch_id,
        "filename": data["filename"],
        "rows": rows,
        "total_meters": len(rows),
        "total_readings": total_readings,
        "matched": matched,
        "unmatched": unmatched,
        **build_import_wizard(3),
    })


# ---------------------------------------------------------------------------
# Step 4: Confirm
# ---------------------------------------------------------------------------

@router.post("/import/potvrdit/{batch_id}")
async def water_import_confirm(
    request: Request,
    batch_id: str,
    import_mode: str = Form("append"),
    db: Session = Depends(get_db),
):
    data = _preview_cache.pop(batch_id, None)
    if not data:
        return RedirectResponse("/vodometry/import?flash=expired", status_code=303)

    meters_data = data["rows"]
    file_path = data["file_path"]

    # Build unit lookup
    db_units = {u.unit_number: u for u in db.query(Unit).all()}

    # Track existing meters by serial to avoid duplicates
    existing_meters = {
        m.meter_serial: m
        for m in db.query(WaterMeter).all()
    }

    new_meters = 0
    new_readings = 0
    deleted_readings = 0
    unmatched_units = 0
    import_batch = batch_id

    for row in meters_data:
        serial = row["meter_serial"]
        if not serial:
            continue

        # Find or create WaterMeter
        meter = existing_meters.get(serial)
        if not meter:
            un = row["unit_number"]
            unit = db_units.get(un) if un else None

            meter_type_val = MeterType.COLD if row["meter_type"] == "cold" else MeterType.HOT
            meter = WaterMeter(
                unit_id=unit.id if unit else None,
                unit_number=un,
                unit_letter=row["unit_letter"],
                meter_serial=serial,
                meter_type=meter_type_val,
                location=row["location"] or None,
            )
            db.add(meter)
            db.flush()
            existing_meters[serial] = meter
            new_meters += 1

            if not unit:
                unmatched_units += 1
        else:
            # Update unit link if meter wasn't linked before
            if not meter.unit_id and row["unit_number"]:
                unit = db_units.get(row["unit_number"])
                if unit:
                    meter.unit_id = unit.id
                    meter.unit_number = row["unit_number"]
                    meter.unit_letter = row["unit_letter"]

        # Import readings for this meter
        if import_mode == "overwrite":
            # Delete all existing readings for this meter
            deleted = db.query(WaterReading).filter_by(meter_id=meter.id).delete()
            deleted_readings += deleted

        for reading_data in row.get("readings", []):
            rd = reading_data["date"]
            rv = reading_data["value"]
            if rd is None or rv is None:
                continue

            if import_mode == "overwrite":
                # All existing deleted — just add
                db.add(WaterReading(
                    meter_id=meter.id,
                    reading_date=rd,
                    value=rv,
                    import_batch=import_batch,
                ))
                new_readings += 1
            else:
                # Append mode — skip existing dates
                existing_reading = (
                    db.query(WaterReading)
                    .filter_by(meter_id=meter.id, reading_date=rd)
                    .first()
                )
                if not existing_reading:
                    db.add(WaterReading(
                        meter_id=meter.id,
                        reading_date=rd,
                        value=rv,
                        import_batch=import_batch,
                    ))
                    new_readings += 1

    total_readings_in_file = sum(len(r.get("readings", [])) for r in meters_data)

    # Log import
    db.add(ImportLog(
        import_type="water_meters",
        filename=data["filename"],
        file_path=file_path,
        rows_total=total_readings_in_file,
        rows_imported=new_readings,
        rows_skipped=total_readings_in_file - new_readings,
    ))

    mode_label = "přepsáno" if import_mode == "overwrite" else "doplněno"
    log_activity(db, ActivityAction.IMPORTED, "water_meter",
                 module="vodometry",
                 description=f"Import ({mode_label}) {new_readings} odečtů, {new_meters} nových vodoměrů z {data['filename']}")

    db.commit()

    # Build flash message
    parts = [f"{new_readings} odečtů pro {len(meters_data)} vodoměrů"]
    if import_mode == "overwrite" and deleted_readings:
        parts.append(f"{deleted_readings} smazáno")
    if new_meters:
        parts.append(f"{new_meters} nových vodoměrů")
    if unmatched_units:
        parts.append(f"{unmatched_units} nepřiřazeno")
    msg = quote("Importováno: " + ", ".join(parts))

    return RedirectResponse(f"/vodometry?flash=import_ok&msg={msg}", status_code=303)
