from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

from fastapi import APIRouter, Depends, Request, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import (
    Unit, WaterMeter, WaterReading, MeterType,
    ImportLog, ActivityAction, log_activity,
)
from app.utils import (
    build_import_wizard, validate_upload, UPLOAD_LIMITS, templates,
)

from ._helpers import logger, parse_techem_xls

router = APIRouter()

# Temporary storage for parsed preview data (batch_id → data)
_preview_cache: dict[str, dict] = {}


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

    # Parse XLS
    try:
        rows = parse_techem_xls(str(dest))
    except Exception as e:
        logger.error("Failed to parse Techem XLS: %s", e)
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
        "file_path": str(dest),
        "filename": filename,
        "rows": rows,
    }

    return RedirectResponse(f"/vodometry/import/nahled/{batch_id}", status_code=303)


# ---------------------------------------------------------------------------
# Step 2: Preview
# ---------------------------------------------------------------------------

@router.get("/import/nahled/{batch_id}", response_class=HTMLResponse)
async def water_import_preview(request: Request, batch_id: str):
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
        **build_import_wizard(2),
    })


# ---------------------------------------------------------------------------
# Step 3: Confirm
# ---------------------------------------------------------------------------

@router.post("/import/potvrdit/{batch_id}")
async def water_import_confirm(
    request: Request,
    batch_id: str,
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

        # Import all monthly readings for this meter
        for reading_data in row.get("readings", []):
            rd = reading_data["date"]
            rv = reading_data["value"]
            if rd is None or rv is None:
                continue

            existing_reading = (
                db.query(WaterReading)
                .filter_by(meter_id=meter.id, reading_date=rd)
                .first()
            )
            if existing_reading:
                if existing_reading.value != rv:
                    existing_reading.value = rv
                    existing_reading.import_batch = import_batch
            else:
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

    log_activity(db, ActivityAction.IMPORTED, "water_meter",
                 module="vodometry",
                 description=f"Import {new_readings} odečtů, {new_meters} nových vodoměrů z {data['filename']}")

    db.commit()

    # Build flash message
    parts = [f"{new_readings} odečtů pro {len(meters_data)} vodoměrů"]
    if new_meters:
        parts.append(f"{new_meters} nových vodoměrů")
    if unmatched_units:
        parts.append(f"{unmatched_units} nepřiřazeno")
    msg = quote("Importováno: " + ", ".join(parts))

    return RedirectResponse(f"/vodometry?flash=import_ok&msg={msg}", status_code=303)
