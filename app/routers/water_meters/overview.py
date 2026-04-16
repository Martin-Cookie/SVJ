from __future__ import annotations

import io
from datetime import date

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from openpyxl import Workbook
from sqlalchemy import String, cast, func
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import WaterMeter, WaterReading, MeterType, Unit, OwnerUnit, Owner, ActivityAction, log_activity
from app.utils import (
    build_list_url, excel_auto_width, is_htmx_partial,
    strip_diacritics, templates,
)

from ._helpers import compute_deviations

router = APIRouter()

SORT_COLUMNS = {
    "jednotka": WaterMeter.unit_number,
    "typ": WaterMeter.meter_type,
    "serial": WaterMeter.meter_serial,
    "umisteni": WaterMeter.location,
}


def _filter_meters(db: Session, q: str = "", typ: str = "", stav: str = "",
                   sort: str = "jednotka", order: str = "asc"):
    """Filter and sort water meters. Returns list with eager-loaded relations."""
    query = db.query(WaterMeter).options(
        joinedload(WaterMeter.unit).joinedload(Unit.owners).joinedload(OwnerUnit.owner),
        joinedload(WaterMeter.readings),
    )

    # Text search
    if q:
        search = f"%{q}%"
        query = query.outerjoin(WaterMeter.unit).filter(
            WaterMeter.meter_serial.ilike(search)
            | WaterMeter.location.ilike(search)
            | cast(WaterMeter.unit_number, String).like(search)
            | WaterMeter.unit_letter.ilike(search)
            | Unit.building_number.ilike(search)
        )

    # Bubble filters
    if typ == "sv":
        query = query.filter(WaterMeter.meter_type == MeterType.COLD)
    elif typ == "tv":
        query = query.filter(WaterMeter.meter_type == MeterType.HOT)

    if stav == "prirazeno":
        query = query.filter(WaterMeter.unit_id.isnot(None))
    elif stav == "neprirazeno":
        query = query.filter(WaterMeter.unit_id.is_(None))
    # vysoka_odchylka is filtered Python-side after query (needs computed values)

    # Sorting
    sort_col = SORT_COLUMNS.get(sort)
    if sort_col is not None:
        if order == "desc":
            query = query.order_by(sort_col.desc().nulls_last())
        else:
            query = query.order_by(sort_col.asc().nulls_last())
    elif sort == "jednotka" or sort not in (
        "hodnota", "datum", "odectu", "spotreba", "vlastnik", "odchylka", "katastral",
    ):
        # Default: sort by unit_letter, then unit_number
        if order == "desc":
            query = query.order_by(
                WaterMeter.unit_letter.desc().nulls_last(),
                WaterMeter.unit_number.desc().nulls_last(),
            )
        else:
            query = query.order_by(
                WaterMeter.unit_letter.asc().nulls_last(),
                WaterMeter.unit_number.asc().nulls_last(),
            )

    meters = query.all()

    # Python-side sort for computed columns
    if sort == "hodnota":
        def _last_val(m):
            if not m.readings:
                return -1
            return max(m.readings, key=lambda r: r.reading_date).value or 0
        meters.sort(key=_last_val, reverse=(order == "desc"))
    elif sort == "datum":
        def _last_date(m):
            if not m.readings:
                return date.min
            return max(r.reading_date for r in m.readings)
        meters.sort(key=_last_date, reverse=(order == "desc"))
    elif sort == "odectu":
        meters.sort(key=lambda m: len(m.readings), reverse=(order == "desc"))
    elif sort == "spotreba":
        from ._helpers import compute_consumption
        def _consumption(m):
            c = compute_consumption(m)
            return c if c is not None else -1
        meters.sort(key=_consumption, reverse=(order == "desc"))
    elif sort == "katastral":
        def _katastral(m):
            if m.unit:
                return m.unit.unit_number or 0
            return 0
        meters.sort(key=_katastral, reverse=(order == "desc"))
    elif sort == "vlastnik":
        def _owner_name(m):
            if m.unit and m.unit.current_owners:
                return m.unit.current_owners[0].owner.display_name.lower()
            return ""
        meters.sort(key=_owner_name, reverse=(order == "desc"))
    elif sort == "odchylka":
        # Need deviations — compute on the fly for sort
        all_for_dev = [m for m in meters]  # already loaded with readings
        dev_map = compute_deviations(all_for_dev)
        def _deviation(m):
            d = dev_map.get(m.id, {}).get("deviation_pct")
            return abs(d) if d is not None else -1
        meters.sort(key=_deviation, reverse=(order == "desc"))

    # Python-side filter for high deviation (needs computed values)
    if stav == "vysoka_odchylka":
        dev_map = compute_deviations(meters)
        meters = [
            m for m in meters
            if dev_map.get(m.id, {}).get("deviation_pct") is not None
            and abs(dev_map[m.id]["deviation_pct"]) > 50
        ]

    return meters


def _build_ctx(request: Request, meters: list, db: Session) -> dict:
    """Build common template context."""
    q = request.query_params.get("q", "")
    typ = request.query_params.get("typ", "")
    stav = request.query_params.get("stav", "")
    sort = request.query_params.get("sort", "jednotka")
    order = request.query_params.get("order", "asc")

    # Compute deviations for all displayed meters
    all_loaded = db.query(WaterMeter).options(
        joinedload(WaterMeter.readings),
    ).all()
    deviations = compute_deviations(all_loaded)

    # Bubble counts (on full dataset, not filtered)
    count_all = len(all_loaded)
    count_sv = sum(1 for m in all_loaded if m.meter_type == MeterType.COLD)
    count_tv = sum(1 for m in all_loaded if m.meter_type == MeterType.HOT)
    count_linked = sum(1 for m in all_loaded if m.unit_id is not None)
    count_unlinked = count_all - count_linked
    count_high_dev = sum(
        1 for m in all_loaded
        if deviations.get(m.id, {}).get("deviation_pct") is not None
        and abs(deviations[m.id]["deviation_pct"]) > 50
    )

    return {
        "active_nav": "water_meters",
        "meters": meters,
        "total_meters": len(meters),
        "deviations": deviations,
        "list_url": build_list_url(request),
        "q": q,
        "typ": typ,
        "stav": stav,
        "sort": sort,
        "order": order,
        "count_all": count_all,
        "count_sv": count_sv,
        "count_tv": count_tv,
        "count_linked": count_linked,
        "count_unlinked": count_unlinked,
        "count_high_dev": count_high_dev,
    }


@router.get("/", response_class=HTMLResponse)
async def water_meters_overview(request: Request, db: Session = Depends(get_db)):
    q = request.query_params.get("q", "")
    typ = request.query_params.get("typ", "")
    stav = request.query_params.get("stav", "")
    sort = request.query_params.get("sort", "jednotka")
    order = request.query_params.get("order", "asc")

    meters = _filter_meters(db, q=q, typ=typ, stav=stav, sort=sort, order=order)

    ctx = _build_ctx(request, meters, db)

    # Flash messages from query params
    flash = request.query_params.get("flash", "")
    msg = request.query_params.get("msg", "")
    if flash == "import_ok":
        ctx["flash_message"] = msg or "Import dokončen."
        ctx["flash_type"] = "success"

    if is_htmx_partial(request):
        return templates.TemplateResponse(request, "partials/water_meter_tbody.html", ctx)

    return templates.TemplateResponse(request, "water_meters/overview.html", ctx)


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

@router.get("/exportovat/{fmt}", response_class=StreamingResponse)
async def water_meters_export(
    request: Request,
    fmt: str,
    db: Session = Depends(get_db),
):
    q = request.query_params.get("q", "")
    typ = request.query_params.get("typ", "")
    stav = request.query_params.get("stav", "")
    sort = request.query_params.get("sort", "jednotka")
    order = request.query_params.get("order", "asc")

    meters = _filter_meters(db, q=q, typ=typ, stav=stav, sort=sort, order=order)

    # Filename suffix
    suffix = ""
    if typ:
        suffix += f"_{typ}"
    if stav:
        suffix += f"_{stav}"
    if not suffix:
        suffix = "_vsechny"

    headers_list = ["Jednotka", "Katastrální č.", "Sekce", "Vlastník", "Typ", "Sériové č.", "Umístění",
                    "Poslední odečet", "Hodnota (m3)", "Spotřeba (m3)", "Odchylka (%)"]

    from ._helpers import compute_consumption
    dev_map = compute_deviations(meters)

    rows_data = []
    for m in meters:
        last = max(m.readings, key=lambda r: r.reading_date) if m.readings else None
        consumption = compute_consumption(m)
        dev_info = dev_map.get(m.id, {})
        deviation = dev_info.get("deviation_pct")
        owner_names = ", ".join(
            ou.owner.display_name for ou in m.unit.current_owners
        ) if m.unit and m.unit.current_owners else ""
        rows_data.append([
            m.unit_number or "",
            m.unit.unit_number if m.unit else "",
            m.unit_letter or "",
            owner_names,
            "SV" if m.meter_type == MeterType.COLD else "TV",
            m.meter_serial,
            m.location or "",
            last.reading_date.strftime("%d.%m.%Y") if last else "",
            last.value if last else "",
            round(consumption, 3) if consumption is not None else "",
            round(deviation, 1) if deviation is not None else "",
        ])

    if fmt == "csv":
        import csv
        output = io.StringIO()
        writer = csv.writer(output, delimiter=";")
        writer.writerow(headers_list)
        for row in rows_data:
            writer.writerow(row)
        content = output.getvalue().encode("utf-8-sig")
        return StreamingResponse(
            io.BytesIO(content),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="vodometry{suffix}.csv"'},
        )

    # xlsx
    wb = Workbook()
    ws = wb.active
    ws.title = "Vodoměry"
    ws.append(headers_list)
    for row in rows_data:
        ws.append(row)
    excel_auto_width(ws)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="vodometry{suffix}.xlsx"'},
    )


# ---------------------------------------------------------------------------
# Detail
# ---------------------------------------------------------------------------

@router.get("/{meter_id}", response_class=HTMLResponse)
async def water_meter_detail(request: Request, meter_id: int, db: Session = Depends(get_db)):
    meter = (
        db.query(WaterMeter)
        .options(joinedload(WaterMeter.unit), joinedload(WaterMeter.readings))
        .get(meter_id)
    )
    if not meter:
        return RedirectResponse("/vodometry", status_code=303)

    readings = sorted(meter.readings, key=lambda r: r.reading_date, reverse=True)
    back = request.query_params.get("back", "/vodometry")

    # Units for assignment select, grouped by section
    all_units = (
        db.query(Unit)
        .order_by(Unit.building_number.asc())
        .all()
    )

    flash = request.query_params.get("flash", "")
    flash_message = ""
    flash_type = ""
    if flash == "assigned":
        flash_message = "Vodoměr přiřazen k jednotce."
        flash_type = "success"
    elif flash == "unlinked":
        flash_message = "Vodoměr odpojen od jednotky."
        flash_type = "success"

    return templates.TemplateResponse(request, "water_meters/detail.html", {
        "active_nav": "water_meters",
        "meter": meter,
        "readings": readings,
        "back": back,
        "all_units": all_units,
        "flash_message": flash_message,
        "flash_type": flash_type,
    })


@router.post("/{meter_id}/prirazeni")
async def water_meter_assign(
    request: Request,
    meter_id: int,
    unit_id: int = Form(None),
    action: str = Form("assign"),
    db: Session = Depends(get_db),
):
    meter = db.query(WaterMeter).get(meter_id)
    if not meter:
        return RedirectResponse("/vodometry", status_code=303)

    back = request.query_params.get("back", "/vodometry")

    if action == "unlink":
        old_unit = db.query(Unit).get(meter.unit_id) if meter.unit_id else None
        meter.unit_id = None
        log_activity(db, ActivityAction.UPDATED, "water_meter",
                     module="vodometry",
                     description=f"Vodoměr {meter.meter_serial} odpojen od jednotky {old_unit.building_number if old_unit else '?'}")
        db.commit()
        return RedirectResponse(f"/vodometry/{meter_id}?back={back}&flash=unlinked", status_code=303)

    if unit_id:
        unit = db.query(Unit).get(unit_id)
        if unit:
            meter.unit_id = unit.id
            log_activity(db, ActivityAction.UPDATED, "water_meter",
                         module="vodometry",
                         description=f"Vodoměr {meter.meter_serial} přiřazen k jednotce {unit.building_number}")
            db.commit()

    return RedirectResponse(f"/vodometry/{meter_id}?back={back}&flash=assigned", status_code=303)
