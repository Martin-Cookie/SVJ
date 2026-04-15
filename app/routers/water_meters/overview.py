from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import WaterMeter, WaterReading
from app.utils import templates

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def water_meters_overview(request: Request, db: Session = Depends(get_db)):
    meters = (
        db.query(WaterMeter)
        .options(
            joinedload(WaterMeter.unit),
            joinedload(WaterMeter.readings),
        )
        .all()
    )

    # Flash messages from query params
    flash = request.query_params.get("flash", "")
    msg = request.query_params.get("msg", "")
    flash_message = ""
    flash_type = ""
    if flash == "import_ok":
        flash_message = msg or "Import dokončen."
        flash_type = "success"

    return templates.TemplateResponse(request, "water_meters/overview.html", {
        "active_nav": "water_meters",
        "meters": meters,
        "total_meters": len(meters),
        "flash_message": flash_message,
        "flash_type": flash_type,
    })
