from datetime import datetime

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import cast, func, String
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Owner, OwnerUnit, SvjInfo, Unit

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


@router.get("/nova-formular")
async def unit_create_form(request: Request):
    return templates.TemplateResponse("partials/unit_create_form.html", {
        "request": request,
    })


@router.post("/nova")
async def unit_create(
    request: Request,
    unit_number: str = Form(...),
    building_number: str = Form(""),
    space_type: str = Form(""),
    section: str = Form(""),
    address: str = Form(""),
    lv_number: str = Form(""),
    room_count: str = Form(""),
    floor_area: str = Form(""),
    podil_scd: str = Form(""),
    db: Session = Depends(get_db),
):
    # Parse unit_number
    try:
        unit_number_int = int(unit_number)
    except (ValueError, TypeError):
        return templates.TemplateResponse("partials/unit_create_form.html", {
            "request": request,
            "error": "Číslo jednotky musí být celé číslo.",
        })

    # Check uniqueness
    existing = db.query(Unit).filter(Unit.unit_number == unit_number_int).first()
    if existing:
        return templates.TemplateResponse("partials/unit_create_form.html", {
            "request": request,
            "error": f"Jednotka s číslem {unit_number_int} již existuje.",
        })

    unit = Unit(
        unit_number=unit_number_int,
        building_number=building_number or None,
        space_type=space_type or None,
        section=section or None,
        address=address or None,
        lv_number=int(lv_number) if lv_number else None,
        room_count=room_count or None,
        floor_area=float(floor_area) if floor_area else None,
        podil_scd=int(podil_scd) if podil_scd else None,
        created_at=datetime.utcnow(),
    )
    db.add(unit)
    db.commit()

    if request.headers.get("HX-Request"):
        return HTMLResponse(
            content=f'<p class="text-sm text-green-600 p-4">Jednotka {unit_number_int} vytvořena. <a href="/jednotky/{unit.id}" class="text-blue-600 hover:underline">Zobrazit</a></p>',
        )
    return RedirectResponse(f"/jednotky/{unit.id}", status_code=302)


@router.get("/{unit_id}/upravit-formular")
async def unit_edit_form(
    unit_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    unit = db.query(Unit).get(unit_id)
    if not unit:
        return RedirectResponse("/jednotky", status_code=302)
    return templates.TemplateResponse("partials/unit_edit_form.html", {
        "request": request,
        "unit": unit,
    })


@router.get("/{unit_id}/info")
async def unit_info(
    unit_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    unit = db.query(Unit).get(unit_id)
    if not unit:
        return RedirectResponse("/jednotky", status_code=302)
    return templates.TemplateResponse("partials/unit_info.html", {
        "request": request,
        "unit": unit,
    })


@router.post("/{unit_id}/upravit")
async def unit_update(
    unit_id: int,
    request: Request,
    unit_number: str = Form(...),
    building_number: str = Form(""),
    space_type: str = Form(""),
    section: str = Form(""),
    orientation_number: str = Form(""),
    address: str = Form(""),
    lv_number: str = Form(""),
    room_count: str = Form(""),
    floor_area: str = Form(""),
    podil_scd: str = Form(""),
    db: Session = Depends(get_db),
):
    unit = db.query(Unit).get(unit_id)
    if not unit:
        return RedirectResponse("/jednotky", status_code=302)

    # Parse and validate unit_number
    try:
        unit_number_int = int(unit_number)
    except (ValueError, TypeError):
        return templates.TemplateResponse("partials/unit_edit_form.html", {
            "request": request,
            "unit": unit,
            "error": "Číslo jednotky musí být celé číslo.",
        })

    # Check uniqueness (exclude self)
    existing = db.query(Unit).filter(
        Unit.unit_number == unit_number_int, Unit.id != unit_id
    ).first()
    if existing:
        return templates.TemplateResponse("partials/unit_edit_form.html", {
            "request": request,
            "unit": unit,
            "error": f"Jednotka s číslem {unit_number_int} již existuje.",
        })

    unit.unit_number = unit_number_int
    unit.building_number = building_number or None
    unit.space_type = space_type or None
    unit.section = section or None
    unit.orientation_number = int(orientation_number) if orientation_number else None
    unit.address = address or None
    unit.lv_number = int(lv_number) if lv_number else None
    unit.room_count = room_count or None
    unit.floor_area = float(floor_area) if floor_area else None
    unit.podil_scd = int(podil_scd) if podil_scd else None
    db.commit()

    if request.headers.get("HX-Request"):
        return templates.TemplateResponse("partials/unit_info.html", {
            "request": request,
            "unit": unit,
            "saved": True,
        })
    return RedirectResponse(f"/jednotky/{unit_id}", status_code=302)


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
    svj_info = db.query(SvjInfo).first()
    declared_shares = svj_info.total_shares if svj_info and svj_info.total_shares else 0

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
            "declared_shares": declared_shares,
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
