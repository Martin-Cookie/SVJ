from __future__ import annotations

import io
from datetime import date

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from openpyxl import Workbook
from sqlalchemy import String, cast, func
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import WaterMeter, WaterReading, MeterType, Unit
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
        joinedload(WaterMeter.unit),
        joinedload(WaterMeter.readings),
    )

    # Text search
    if q:
        search_ascii = f"%{strip_diacritics(q)}%"
        search = f"%{q}%"
        query = query.filter(
            WaterMeter.meter_serial.ilike(search)
            | WaterMeter.location.ilike(search)
            | cast(WaterMeter.unit_number, String).like(search)
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
    sort_col = SORT_COLUMNS.get(sort, WaterMeter.unit_number)
    if sort_col is not None:
        if order == "desc":
            query = query.order_by(sort_col.desc().nulls_last())
        else:
            query = query.order_by(sort_col.asc().nulls_last())

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
    elif sort == "spotreba":
        from ._helpers import compute_consumption
        def _consumption(m):
            c = compute_consumption(m)
            return c if c is not None else -1
        meters.sort(key=_consumption, reverse=(order == "desc"))
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

    headers_list = ["Jednotka", "Sekce", "Typ", "Sériové č.", "Umístění",
                    "Poslední odečet", "Hodnota (m3)", "Spotřeba (m3)", "Odchylka (%)"]

    from ._helpers import compute_consumption
    dev_map = compute_deviations(meters)

    rows_data = []
    for m in meters:
        last = max(m.readings, key=lambda r: r.reading_date) if m.readings else None
        consumption = compute_consumption(m)
        dev_info = dev_map.get(m.id, {})
        deviation = dev_info.get("deviation_pct")
        rows_data.append([
            m.unit_number or "",
            m.unit_letter or "",
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
