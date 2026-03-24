import csv
import io
from datetime import datetime
from io import BytesIO

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from openpyxl import Workbook
from openpyxl.styles import Font
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Space, SpaceStatus, SpaceTenant, Tenant
from app.utils import build_list_url, excel_auto_width, is_htmx_partial, templates, utcnow

from ._helpers import SORT_COLUMNS, _filter_spaces, _space_stats, logger

router = APIRouter()


# ── Create ────────────────────────────────────────────────────────────


@router.get("/novy-formular")
async def space_create_form(request: Request):
    """Formulář pro vytvoření nového prostoru."""
    return templates.TemplateResponse("spaces/partials/_create_form.html", {
        "request": request,
    })


@router.post("/novy")
async def space_create(
    request: Request,
    space_number: str = Form(...),
    designation: str = Form(...),
    section: str = Form(""),
    floor: str = Form(""),
    area: str = Form(""),
    status: str = Form("vacant"),
    blocked_reason: str = Form(""),
    note: str = Form(""),
    db: Session = Depends(get_db),
):
    """Vytvoření nového prostoru."""
    # Parse space_number
    try:
        space_number_int = int(space_number)
    except (ValueError, TypeError):
        return templates.TemplateResponse("spaces/partials/_create_form.html", {
            "request": request,
            "error": "Číslo prostoru musí být celé číslo.",
        })
    if space_number_int < 1 or space_number_int > 99999:
        return templates.TemplateResponse("spaces/partials/_create_form.html", {
            "request": request,
            "error": "Číslo prostoru musí být v rozsahu 1–99999.",
        })

    # Uniqueness
    existing = db.query(Space).filter(Space.space_number == space_number_int).first()
    if existing:
        return templates.TemplateResponse("spaces/partials/_create_form.html", {
            "request": request,
            "error": f"Prostor s číslem {space_number_int} již existuje.",
        })

    # Parse optional numerics
    floor_int = None
    if floor.strip():
        try:
            floor_int = int(floor.strip())
        except (ValueError, TypeError):
            return templates.TemplateResponse("spaces/partials/_create_form.html", {
                "request": request,
                "error": "Podlaží musí být celé číslo.",
            })

    area_float = None
    if area.strip():
        try:
            area_float = float(area.strip())
        except (ValueError, TypeError):
            return templates.TemplateResponse("spaces/partials/_create_form.html", {
                "request": request,
                "error": "Výměra musí být číslo.",
            })

    space_status = SpaceStatus(status) if status in [s.value for s in SpaceStatus] else SpaceStatus.VACANT

    space = Space(
        space_number=space_number_int,
        designation=designation.strip(),
        section=section.strip() or None,
        floor=floor_int,
        area=area_float,
        status=space_status,
        blocked_reason=blocked_reason.strip() or None,
        note=note.strip() or None,
        created_at=utcnow(),
    )
    db.add(space)
    db.commit()

    if request.headers.get("HX-Request"):
        return HTMLResponse(
            content=f'<p class="text-sm text-green-600 p-4">Prostor {space_number_int} vytvořen. '
                    f'<a href="/prostory/{space.id}" class="text-blue-600 hover:underline">Zobrazit</a></p>',
        )
    return RedirectResponse(f"/prostory/{space.id}", status_code=302)


# ── Detail ────────────────────────────────────────────────────────────


@router.get("/{space_id}/upravit-formular")
async def space_edit_form(
    space_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Inline edit formulář pro prostor."""
    space = db.query(Space).get(space_id)
    if not space:
        return RedirectResponse("/prostory", status_code=302)
    return templates.TemplateResponse("spaces/partials/_space_info.html", {
        "request": request,
        "space": space,
        "edit_mode": True,
    })


@router.get("/{space_id}/info")
async def space_info(
    space_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Display-only info sekce prostoru."""
    space = db.query(Space).get(space_id)
    if not space:
        return RedirectResponse("/prostory", status_code=302)
    return templates.TemplateResponse("spaces/partials/_space_info.html", {
        "request": request,
        "space": space,
        "edit_mode": False,
    })


@router.post("/{space_id}/upravit")
async def space_update(
    space_id: int,
    request: Request,
    designation: str = Form(...),
    section: str = Form(""),
    floor: str = Form(""),
    area: str = Form(""),
    status: str = Form("vacant"),
    blocked_reason: str = Form(""),
    note: str = Form(""),
    db: Session = Depends(get_db),
):
    """Uložení úprav prostoru."""
    space = db.query(Space).get(space_id)
    if not space:
        return RedirectResponse("/prostory", status_code=302)

    floor_int = None
    if floor.strip():
        try:
            floor_int = int(floor.strip())
        except (ValueError, TypeError):
            return templates.TemplateResponse("spaces/partials/_space_info.html", {
                "request": request, "space": space, "edit_mode": True,
                "error": "Podlaží musí být celé číslo.",
            })

    area_float = None
    if area.strip():
        try:
            area_float = float(area.strip())
        except (ValueError, TypeError):
            return templates.TemplateResponse("spaces/partials/_space_info.html", {
                "request": request, "space": space, "edit_mode": True,
                "error": "Výměra musí být číslo.",
            })

    space_status = SpaceStatus(status) if status in [s.value for s in SpaceStatus] else space.status

    space.designation = designation.strip()
    space.section = section.strip() or None
    space.floor = floor_int
    space.area = area_float
    space.status = space_status
    space.blocked_reason = blocked_reason.strip() or None
    space.note = note.strip() or None
    space.updated_at = utcnow()
    db.commit()

    if request.headers.get("HX-Request"):
        return templates.TemplateResponse("spaces/partials/_space_info.html", {
            "request": request,
            "space": space,
            "edit_mode": False,
            "saved": True,
        })
    return RedirectResponse(f"/prostory/{space_id}", status_code=302)


@router.post("/{space_id}/smazat")
async def space_delete(
    space_id: int,
    db: Session = Depends(get_db),
):
    """Smazání prostoru."""
    space = db.query(Space).get(space_id)
    if space:
        db.delete(space)
        db.commit()
    return RedirectResponse("/prostory?flash=deleted", status_code=302)


# ── List ──────────────────────────────────────────────────────────────


@router.get("/")
async def space_list(
    request: Request,
    q: str = Query("", alias="q"),
    stav: str = Query("", alias="stav"),
    sekce: str = Query("", alias="sekce"),
    sort: str = Query("space_number", alias="sort"),
    order: str = Query("asc", alias="order"),
    back: str = Query("", alias="back"),
    flash: str = Query("", alias="flash"),
    db: Session = Depends(get_db),
):
    """Seznam prostorů s filtry, hledáním a řazením."""
    spaces = _filter_spaces(db, q, stav, sekce, sort, order)

    list_url = build_list_url(request)

    # HTMX partial
    if is_htmx_partial(request):
        return templates.TemplateResponse("spaces/partials/_tbody.html", {
            "request": request,
            "spaces": spaces,
            "list_url": list_url,
        })

    stats = _space_stats(db)

    flash_message = None
    if flash == "deleted":
        flash_message = "Prostor byl smazán."

    return templates.TemplateResponse("spaces/list.html", {
        "request": request,
        "active_nav": "spaces",
        "spaces": spaces,
        "list_url": list_url,
        "back_url": back,
        "q": q,
        "stav": stav,
        "sekce": sekce,
        "sort": sort,
        "order": order,
        "stats": stats,
        "flash_message": flash_message,
    })


# ── Export ─────────────────────────────────────────────────────────────


@router.get("/exportovat/{fmt}")
async def space_export(
    fmt: str,
    q: str = Query("", alias="q"),
    stav: str = Query("", alias="stav"),
    sekce: str = Query("", alias="sekce"),
    sort: str = Query("space_number", alias="sort"),
    order: str = Query("asc", alias="order"),
    db: Session = Depends(get_db),
):
    """Export filtered spaces to Excel or CSV."""
    if fmt not in ("xlsx", "csv"):
        return RedirectResponse("/prostory", status_code=302)

    spaces = _filter_spaces(db, q, stav, sekce, sort, order)

    headers = ["Č. prostoru", "Označení", "Sekce", "Podlaží", "Výměra", "Stav", "Nájemce", "Měs. nájemné", "VS"]
    status_labels = {"rented": "Pronajato", "vacant": "Volné", "blocked": "Blokované"}

    def _row(s):
        at = s.active_tenant_rel
        tenant_name = at.tenant.display_name if at else ""
        rent = at.monthly_rent if at else ""
        vs = at.variable_symbol if at else ""
        return [
            s.space_number,
            s.designation or "",
            s.section or "",
            s.floor or "",
            s.area or "",
            status_labels.get(s.status.value, s.status.value) if s.status else "",
            tenant_name,
            rent,
            vs,
        ]

    timestamp = datetime.now().strftime("%Y%m%d")

    stav_labels = {"rented": "pronajate", "vacant": "volne", "blocked": "blokovane"}
    if stav and stav in stav_labels:
        suffix = f"_{stav_labels[stav]}"
    elif sekce:
        suffix = f"_sekce_{sekce}"
    elif q:
        suffix = "_hledani"
    else:
        suffix = "_vse"
    filename = f"prostory{suffix}_{timestamp}"

    if fmt == "xlsx":
        wb = Workbook()
        ws = wb.active
        ws.title = "Prostory"
        bold = Font(bold=True)

        for col, h in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=h)
            cell.font = bold

        for row_idx, s in enumerate(spaces, 2):
            for col_idx, val in enumerate(_row(s), 1):
                ws.cell(row=row_idx, column=col_idx, value=val)

        excel_auto_width(ws)

        buf = BytesIO()
        wb.save(buf)
        return Response(
            content=buf.getvalue(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}.xlsx"'},
        )
    else:
        buf = io.StringIO()
        writer = csv.writer(buf, delimiter=";")
        writer.writerow(headers)
        for s in spaces:
            writer.writerow(_row(s))
        return Response(
            content=buf.getvalue().encode("utf-8-sig"),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}.csv"'},
        )


# ── Detail (catch-all — must be last) ─────────────────────────────────


@router.get("/{space_id}")
async def space_detail(
    space_id: int,
    request: Request,
    back: str = Query("", alias="back"),
    db: Session = Depends(get_db),
):
    """Detail prostoru s nájemcem a historií."""
    space = db.query(Space).options(
        joinedload(Space.tenants).joinedload(SpaceTenant.tenant).joinedload(Tenant.owner)
    ).get(space_id)
    if not space:
        return RedirectResponse("/prostory", status_code=302)

    # Back label
    if "/platby/prehled" in back:
        back_label = "Zpět na matici plateb"
    elif "/platby/dluznici" in back:
        back_label = "Zpět na dlužníky"
    elif "/platby/prostor" in back:
        back_label = "Zpět na platby prostoru"
    elif "/platby" in back:
        back_label = "Zpět na platby"
    elif "/najemci/" in back:
        back_label = "Zpět na detail nájemce"
    elif back.startswith("/najemci"):
        back_label = "Zpět na seznam nájemců"
    elif back:
        back_label = "Zpět"
    else:
        back_label = "Zpět na seznam prostorů"

    # Active tenant + history
    active_rel = space.active_tenant_rel
    history = [st for st in space.tenants if not st.is_active]
    history.sort(key=lambda st: st.contract_end or st.created_at, reverse=True)

    return templates.TemplateResponse("spaces/detail.html", {
        "request": request,
        "active_nav": "spaces",
        "space": space,
        "active_rel": active_rel,
        "history": history,
        "back_url": back or "/prostory",
        "back_label": back_label,
    })
