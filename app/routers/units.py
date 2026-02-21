from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import cast, func, String
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Owner, OwnerUnit, Unit

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


SORT_COLUMNS = {
    "unit_number": Unit.unit_number,
    "building": Unit.building_number,
    "space_type": Unit.space_type,
    "section": Unit.section,
    "address": Unit.address,
    "lv": Unit.lv_number,
    "room_count": Unit.room_count,
    "floor_area": Unit.floor_area,
    "podil": Unit.podil_scd,
}


@router.get("/")
async def unit_list(
    request: Request,
    q: str = Query("", alias="q"),
    typ: str = Query("", alias="typ"),
    sekce: str = Query("", alias="sekce"),
    sort: str = Query("unit_number", alias="sort"),
    order: str = Query("asc", alias="order"),
    db: Session = Depends(get_db),
):
    query = db.query(Unit).options(
        joinedload(Unit.owners).joinedload(OwnerUnit.owner)
    )

    if q:
        search = f"%{q}%"
        query = query.filter(
            cast(Unit.unit_number, String).ilike(search)
            | Unit.building_number.ilike(search)
            | Unit.space_type.ilike(search)
            | Unit.section.ilike(search)
            | Unit.address.ilike(search)
            | Unit.owners.any(OwnerUnit.owner.has(Owner.name_with_titles.ilike(search)))
        )
    if typ:
        query = query.filter(Unit.space_type == typ)
    if sekce:
        query = query.filter(Unit.section == sekce)

    # Sorting
    if sort == "owners":
        units = query.all()
        units.sort(
            key=lambda u: (u.owners[0].owner.name_normalized if u.owners else ""),
            reverse=(order == "desc"),
        )
    else:
        sort_col = SORT_COLUMNS.get(sort, Unit.unit_number)
        if order == "desc":
            query = query.order_by(sort_col.desc().nulls_last())
        else:
            query = query.order_by(sort_col.asc().nulls_last())
        units = query.all()

    # HTMX partial
    is_htmx = request.headers.get("HX-Request")
    is_boosted = request.headers.get("HX-Boosted")
    if is_htmx and not is_boosted:
        return templates.TemplateResponse("partials/unit_table_body.html", {
            "request": request,
            "units": units,
        })

    # Stats
    total_units = db.query(Unit).count()
    total_scd = db.query(func.sum(Unit.podil_scd)).scalar() or 0

    type_counts_raw = (
        db.query(Unit.space_type, func.count(Unit.id))
        .filter(Unit.space_type.isnot(None))
        .group_by(Unit.space_type)
        .all()
    )
    type_counts = {st: cnt for st, cnt in type_counts_raw}

    sections = [
        r[0] for r in
        db.query(Unit.section).filter(Unit.section.isnot(None)).distinct().order_by(Unit.section).all()
    ]

    return templates.TemplateResponse("units/list.html", {
        "request": request,
        "active_nav": "units",
        "units": units,
        "q": q,
        "typ": typ,
        "sekce": sekce,
        "sort": sort,
        "order": order,
        "stats": {
            "total_units": total_units,
            "total_scd": total_scd,
            "type_counts": type_counts,
            "sections": sections,
        },
    })


@router.get("/{unit_id}")
async def unit_detail(
    unit_id: int,
    request: Request,
    back: str = Query("", alias="back"),
    db: Session = Depends(get_db),
):
    unit = db.query(Unit).options(
        joinedload(Unit.owners).joinedload(OwnerUnit.owner)
    ).get(unit_id)
    if not unit:
        return RedirectResponse("/jednotky", status_code=302)

    if "/vlastnici/" in back:
        back_label = "Zpět na detail vlastníka"
    elif "/synchronizace/" in back:
        back_label = "Zpět na porovnání"
    elif back:
        back_label = "Zpět"
    else:
        back_label = "Zpět na seznam jednotek"

    return templates.TemplateResponse("units/detail.html", {
        "request": request,
        "active_nav": "units",
        "unit": unit,
        "back_url": back or "/jednotky",
        "back_label": back_label,
    })
