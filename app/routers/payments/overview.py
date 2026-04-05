"""Přehled plateb — matice, dlužníci, detail jednotky."""

from datetime import datetime
from io import BytesIO

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import RedirectResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import PrescriptionYear, Unit, Space
from app.services.payment_overview import (
    compute_debtor_list,
    compute_payment_matrix,
    compute_unit_payment_detail,
    compute_space_debtor_list,
    compute_space_payment_matrix,
    compute_space_payment_detail,
)
from app.utils import build_list_url, excel_auto_width, is_htmx_partial, strip_diacritics, utcnow

from ._helpers import templates, compute_nav_stats, MONTH_NAMES_SHORT

router = APIRouter()

MONTH_NAMES = MONTH_NAMES_SHORT


# ── Matice plateb ────────────────────────────────────────────────────


SORT_COLUMNS_MATRIX = {
    "cislo": None,     # Python sort
    "sekce": None,
    "vlastnik": None,
    "predpis": None,
    "prevod": None,
    "celkem": None,
    "dluh": None,
    # Měsíční sloupce m1–m12
    **{f"m{i}": None for i in range(1, 13)},
}


@router.get("/prehled")
async def platby_prehled(
    request: Request,
    rok: int = Query(0),
    typ: str = Query(""),
    q: str = Query(""),
    sort: str = Query("cislo"),
    order: str = Query("asc"),
    vse_mesice: int = Query(0, alias="vse_mesice"),
    back: str = Query("", alias="back"),
    db: Session = Depends(get_db),
):
    """Matice plateb — jednotky/prostory × měsíce."""
    entita = request.query_params.get("entita", "")
    show_all_months = bool(vse_mesice)

    # Výchozí rok = nejnovější PrescriptionYear
    if not rok:
        latest = db.query(PrescriptionYear).order_by(PrescriptionYear.year.desc()).first()
        rok = latest.year if latest else utcnow().year

    years = [y.year for y in db.query(PrescriptionYear).order_by(PrescriptionYear.year.desc()).all()]

    if entita == "prostory":
        matrix = compute_space_payment_matrix(db, rok)
        rows = matrix["rows"]

        if q:
            q_ascii = strip_diacritics(q)
            rows = [
                r for r in rows
                if q_ascii in strip_diacritics(str(r["space"].space_number))
                or q_ascii in strip_diacritics(r["space"].designation or "")
                or q_ascii in strip_diacritics(
                    r["tenant_rel"].tenant.display_name if r.get("tenant_rel") and r["tenant_rel"].tenant else ""
                )
            ]

        sort_key = sort if sort in SORT_COLUMNS_MATRIX else "cislo"
        reverse = order == "desc"
        sort_fns = {
            "cislo": lambda r: r["space"].space_number or "",
            "sekce": lambda r: "",
            "vlastnik": lambda r: strip_diacritics(
                r["tenant_rel"].tenant.display_name if r.get("tenant_rel") and r["tenant_rel"].tenant else ""
            ),
            "predpis": lambda r: r["monthly"],
            "prevod": lambda r: r.get("opening", 0),
            "celkem": lambda r: r["total_paid"],
            "dluh": lambda r: r["debt"],
        }
        for mi in range(1, 13):
            sort_fns[f"m{mi}"] = (lambda m: lambda r: r["months"].get(m, {}).get("paid", 0))(mi)
        rows.sort(key=sort_fns.get(sort_key, sort_fns["cislo"]), reverse=reverse)

        total_units = len(matrix["rows"])
        space_types = []
    else:
        matrix = compute_payment_matrix(db, rok, space_type=typ)
        rows = matrix["units"]

        if q:
            q_ascii = strip_diacritics(q)
            rows = [
                r for r in rows
                if q_ascii in strip_diacritics(str(r["unit"].unit_number))
                or q_ascii in strip_diacritics(r["owner"].display_name if r["owner"] else "")
                or q_ascii in strip_diacritics(r["prescription"].owner_name or "")
                or q_ascii in strip_diacritics(r["prescription"].variable_symbol or "")
                or q_ascii in strip_diacritics(r["prescription"].section or "")
            ]

        sort_key = sort if sort in SORT_COLUMNS_MATRIX else "cislo"
        reverse = order == "desc"
        sort_fns = {
            "cislo": lambda r: r["unit"].unit_number or 0,
            "sekce": lambda r: (r["prescription"].section or "").lower(),
            "vlastnik": lambda r: strip_diacritics(r["owner"].display_name if r["owner"] else r["prescription"].owner_name or ""),
            "predpis": lambda r: r["monthly"],
            "prevod": lambda r: r.get("opening", 0),
            "celkem": lambda r: r["total_paid"],
            "dluh": lambda r: r["debt"],
        }
        for mi in range(1, 13):
            sort_fns[f"m{mi}"] = (lambda m: lambda r: r["months"].get(m, {}).get("paid", 0))(mi)
        rows.sort(key=sort_fns.get(sort_key, sort_fns["cislo"]), reverse=reverse)

        total_units = len(matrix["units"])
        space_types = matrix["space_types"]

    list_url = build_list_url(request)

    ctx = {
        "request": request,
        "active_nav": "platby",
        "rows": rows,
        "rok": rok,
        "years": years,
        "typ": typ,
        "q": q,
        "sort": sort_key,
        "order": order,
        "entita": entita,
        "back_url": back,
        "list_url": list_url,
        "month_names": MONTH_NAMES,
        "months_with_data": matrix["months_with_data"],
        "show_all_months": show_all_months,
        "space_types": space_types,
        "total_prescribed": matrix["total_prescribed"],
        "total_paid": matrix["total_paid"],
        "total_units": total_units,
        "active_tab": "prehled",
        **(compute_nav_stats(db) if not is_htmx_partial(request) else {}),
    }

    if is_htmx_partial(request):
        return templates.TemplateResponse("payments/partials/prehled_tbody.html", ctx)

    return templates.TemplateResponse("payments/prehled.html", ctx)


# ── Export matice plateb ──────────────────────────────────────────────


@router.post("/prehled/exportovat")
async def matice_export(
    request: Request,
    rok: int = Form(0),
    typ: str = Form(""),
    q: str = Form(""),
    sort: str = Form("cislo"),
    order: str = Form("asc"),
    db: Session = Depends(get_db),
):
    """Export matice plateb do Excelu."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill

    if not rok:
        latest = db.query(PrescriptionYear).order_by(PrescriptionYear.year.desc()).first()
        rok = latest.year if latest else utcnow().year

    matrix = compute_payment_matrix(db, rok, space_type=typ)
    rows = matrix["units"]
    months_with_data = sorted(matrix["months_with_data"])

    if q:
        q_ascii = strip_diacritics(q)
        rows = [
            r for r in rows
            if q_ascii in strip_diacritics(str(r["unit"].unit_number))
            or q_ascii in strip_diacritics(r["owner"].display_name if r["owner"] else "")
            or q_ascii in strip_diacritics(r["prescription"].owner_name or "")
        ]

    sort_fns = {
        "cislo": lambda r: r["unit"].unit_number or 0,
        "sekce": lambda r: (r["prescription"].section or "").lower(),
        "vlastnik": lambda r: strip_diacritics(r["owner"].display_name if r["owner"] else r["prescription"].owner_name or ""),
        "predpis": lambda r: r["monthly"],
        "celkem": lambda r: r["total_paid"],
        "dluh": lambda r: r["debt"],
    }
    rows.sort(key=sort_fns.get(sort, sort_fns["cislo"]), reverse=(order == "desc"))

    wb = Workbook()
    ws = wb.active
    ws.title = f"Matice plateb {rok}"

    month_labels = ["Led", "Úno", "Bře", "Dub", "Kvě", "Čer", "Čvc", "Srp", "Zář", "Říj", "Lis", "Pro"]
    headers = ["Č. jedn.", "Sekce", "Vlastník", "Předpis/měs", "Převod"]
    for m in months_with_data:
        headers.append(month_labels[m - 1])
    headers += ["Celkem", "Dluh"]

    bold = Font(bold=True)
    red_fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")

    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.font = bold

    for i, r in enumerate(rows, 2):
        owner_name = ", ".join(o.display_name for o in r["owners"]) if r["owners"] else r["prescription"].owner_name or ""
        ws.cell(row=i, column=1, value=r["unit"].unit_number)
        ws.cell(row=i, column=2, value=r["prescription"].section or "")
        ws.cell(row=i, column=3, value=owner_name)
        ws.cell(row=i, column=4, value=r["monthly"])
        ws.cell(row=i, column=5, value=r.get("opening", 0))
        col = 6
        for m in months_with_data:
            paid = r["months"].get(m, {}).get("paid", 0)
            cell = ws.cell(row=i, column=col, value=paid)
            if paid < r["monthly"] and r["monthly"] > 0:
                cell.fill = red_fill
            col += 1
        ws.cell(row=i, column=col, value=r["total_paid"])
        debt_cell = ws.cell(row=i, column=col + 1, value=r["debt"])
        if r["debt"] > 0:
            debt_cell.fill = red_fill

    excel_auto_width(ws)

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)

    typ_suffix = f"_{strip_diacritics(typ)}" if typ else ""
    q_suffix = f"_hledani_{q}" if q else ""
    suffix = typ_suffix or q_suffix or "_vse"
    date_str = datetime.now().strftime("%Y%m%d")
    filename = f"matice_plateb_{rok}{suffix}_{date_str}.xlsx"

    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Dlužníci ─────────────────────────────────────────────────────────


SORT_COLUMNS_DEBTORS = {
    "cislo": None,
    "vlastnik": None,
    "predpis": None,
    "zaplaceno": None,
    "dluh": None,
    "mesice": None,
}


@router.get("/dluznici")
async def platby_dluznici(
    request: Request,
    rok: int = Query(0),
    q: str = Query(""),
    sort: str = Query("dluh"),
    order: str = Query("desc"),
    back: str = Query("", alias="back"),
    db: Session = Depends(get_db),
):
    """Seznam dlužníků — jednotky nebo prostory."""
    entita = request.query_params.get("entita", "")

    if not rok:
        latest = db.query(PrescriptionYear).order_by(PrescriptionYear.year.desc()).first()
        rok = latest.year if latest else utcnow().year

    years = [y.year for y in db.query(PrescriptionYear).order_by(PrescriptionYear.year.desc()).all()]

    if entita == "prostory":
        debtors, months_with_data = compute_space_debtor_list(db, rok)

        # Compute months_unpaid for sorting
        for r in debtors:
            r["months_unpaid"] = sum(
                1 for m in range(1, 13)
                if r["months"].get(m, {}).get("status") in ("unpaid", "partial")
                and m in months_with_data
            )

        if q:
            q_ascii = strip_diacritics(q)
            debtors = [
                r for r in debtors
                if q_ascii in strip_diacritics(str(r["space"].space_number))
                or q_ascii in strip_diacritics(r["space"].designation or "")
                or q_ascii in strip_diacritics(
                    r["tenant_rel"].tenant.display_name if r.get("tenant_rel") and r["tenant_rel"].tenant else ""
                )
            ]

        sort_key = sort if sort in SORT_COLUMNS_DEBTORS else "dluh"
        reverse = order == "desc"
        sort_fns = {
            "cislo": lambda r: r["space"].space_number or "",
            "vlastnik": lambda r: strip_diacritics(
                r["tenant_rel"].tenant.display_name if r.get("tenant_rel") and r["tenant_rel"].tenant else ""
            ),
            "predpis": lambda r: r["monthly"],
            "zaplaceno": lambda r: r["total_paid"],
            "dluh": lambda r: r["debt"],
            "mesice": lambda r: r["months_unpaid"],
        }
        debtors.sort(key=sort_fns.get(sort_key, sort_fns["dluh"]), reverse=reverse)
    else:
        debtors, months_with_data = compute_debtor_list(db, rok)

        # Compute months_unpaid for sorting
        for r in debtors:
            r["months_unpaid"] = sum(
                1 for m in range(1, 13)
                if r["months"].get(m, {}).get("status") in ("unpaid", "partial")
                and m in months_with_data
            )

        if q:
            q_ascii = strip_diacritics(q)
            debtors = [
                r for r in debtors
                if q_ascii in strip_diacritics(str(r["unit"].unit_number))
                or q_ascii in strip_diacritics(r["owner"].display_name if r["owner"] else "")
                or q_ascii in strip_diacritics(r["prescription"].owner_name or "")
            ]

        sort_key = sort if sort in SORT_COLUMNS_DEBTORS else "dluh"
        reverse = order == "desc"
        sort_fns = {
            "cislo": lambda r: r["unit"].unit_number or 0,
            "vlastnik": lambda r: strip_diacritics(r["owner"].display_name if r["owner"] else r["prescription"].owner_name or ""),
            "predpis": lambda r: r["monthly"],
            "zaplaceno": lambda r: r["total_paid"],
            "dluh": lambda r: r["debt"],
            "mesice": lambda r: r["months_unpaid"],
        }
        debtors.sort(key=sort_fns.get(sort_key, sort_fns["dluh"]), reverse=reverse)

    list_url = build_list_url(request)

    ctx = {
        "request": request,
        "active_nav": "platby",
        "debtors": debtors,
        "rok": rok,
        "years": years,
        "q": q,
        "sort": sort_key,
        "order": order,
        "entita": entita,
        "back_url": back,
        "list_url": list_url,
        "months_with_data": months_with_data,
        "total_debt": sum(r["debt"] for r in debtors),
        "active_tab": "dluznici",
        **(compute_nav_stats(db) if not is_htmx_partial(request) else {}),
    }

    if is_htmx_partial(request):
        return templates.TemplateResponse("payments/partials/dluznici_tbody.html", ctx)

    return templates.TemplateResponse("payments/dluznici.html", ctx)


# ── Export dlužníků ──────────────────────────────────────────────────


@router.post("/dluznici/exportovat")
async def dluznici_export(
    request: Request,
    rok: int = Form(0),
    q: str = Form(""),
    sort: str = Form("dluh"),
    order: str = Form("desc"),
    db: Session = Depends(get_db),
):
    """Export dlužníků do Excelu."""
    from openpyxl import Workbook
    from openpyxl.styles import Font

    if not rok:
        latest = db.query(PrescriptionYear).order_by(PrescriptionYear.year.desc()).first()
        rok = latest.year if latest else utcnow().year

    debtors, months_with_data_export = compute_debtor_list(db, rok)

    # Compute months_unpaid for sorting/export
    for r in debtors:
        r["months_unpaid"] = sum(
            1 for m in range(1, 13)
            if r["months"].get(m, {}).get("status") in ("unpaid", "partial")
            and m in months_with_data_export
        )

    if q:
        q_ascii = strip_diacritics(q)
        debtors = [
            r for r in debtors
            if q_ascii in strip_diacritics(str(r["unit"].unit_number))
            or q_ascii in strip_diacritics(r["owner"].display_name if r["owner"] else "")
            or q_ascii in strip_diacritics(r["prescription"].owner_name or "")
        ]

    sort_key = sort if sort in SORT_COLUMNS_DEBTORS else "dluh"
    reverse = order == "desc"
    sort_fns = {
        "cislo": lambda r: r["unit"].unit_number or 0,
        "vlastnik": lambda r: strip_diacritics(r["owner"].display_name if r["owner"] else r["prescription"].owner_name or ""),
        "predpis": lambda r: r["monthly"],
        "zaplaceno": lambda r: r["total_paid"],
        "dluh": lambda r: r["debt"],
        "mesice": lambda r: r["months_unpaid"],
    }
    debtors.sort(key=sort_fns.get(sort_key, sort_fns["dluh"]), reverse=reverse)

    wb = Workbook()
    ws = wb.active
    ws.title = f"Dlužníci {rok}"

    headers = ["Č. jednotky", "Vlastník", "Předpis/měs", "Zaplaceno", "Dluh", "Měsíce"]
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.font = Font(bold=True)

    for i, r in enumerate(debtors, 2):
        owner_name = ", ".join(o.display_name for o in r["owners"]) if r["owners"] else r["prescription"].owner_name or ""
        ws.cell(row=i, column=1, value=r["unit"].unit_number)
        ws.cell(row=i, column=2, value=owner_name)
        ws.cell(row=i, column=3, value=r["monthly"])
        ws.cell(row=i, column=4, value=r["total_paid"])
        ws.cell(row=i, column=5, value=r["debt"])
        ws.cell(row=i, column=6, value=r["months_unpaid"])

    excel_auto_width(ws)

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)

    suffix = f"_hledani_{q}" if q else "_vsichni"
    date_str = datetime.now().strftime("%Y%m%d")
    filename = f"dluznici_{rok}{suffix}_{date_str}.xlsx"

    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Detail plateb jednotky ───────────────────────────────────────────


@router.get("/jednotka/{unit_id}")
async def platby_jednotka(
    unit_id: int,
    request: Request,
    rok: int = Query(0),
    back: str = Query("", alias="back"),
    db: Session = Depends(get_db),
):
    """Platební detail jedné jednotky."""
    unit = db.query(Unit).get(unit_id)
    if not unit:
        return RedirectResponse("/platby/prehled", status_code=302)

    if not rok:
        latest = db.query(PrescriptionYear).order_by(PrescriptionYear.year.desc()).first()
        rok = latest.year if latest else utcnow().year

    years = [y.year for y in db.query(PrescriptionYear).order_by(PrescriptionYear.year.desc()).all()]

    detail = compute_unit_payment_detail(db, unit_id, rok)
    if not detail:
        return RedirectResponse("/platby/prehled", status_code=302)

    back_url = back or "/platby/prehled"
    if "/platby/prehled" in back_url:
        back_label = "Zpět na matici plateb"
    elif "/platby/dluznici" in back_url:
        back_label = "Zpět na dlužníky"
    elif "/jednotky/" in back_url:
        back_label = "Zpět na detail jednotky"
    else:
        back_label = "Zpět na platby"

    return templates.TemplateResponse("payments/jednotka_platby.html", {
        "request": request,
        "active_nav": "platby",
        "active_tab": "prehled",
        "unit": unit,
        "detail": detail,
        "rok": rok,
        "years": years,
        "back_url": back_url,
        "back_label": back_label,
        "hide_nav_back": True,
        "month_names": MONTH_NAMES,
        **(compute_nav_stats(db) if not is_htmx_partial(request) else {}),
    })


# ── Detail plateb prostoru ──────────────────────────────────────────


@router.get("/prostor/{space_id}")
async def platby_prostor(
    space_id: int,
    request: Request,
    rok: int = Query(0),
    back: str = Query("", alias="back"),
    db: Session = Depends(get_db),
):
    """Platební detail jednoho prostoru."""
    space = db.query(Space).get(space_id)
    if not space:
        return RedirectResponse("/platby/prehled?entita=prostory", status_code=302)

    if not rok:
        latest = db.query(PrescriptionYear).order_by(PrescriptionYear.year.desc()).first()
        rok = latest.year if latest else utcnow().year

    years = [y.year for y in db.query(PrescriptionYear).order_by(PrescriptionYear.year.desc()).all()]

    detail = compute_space_payment_detail(db, space_id, rok)
    if not detail:
        return RedirectResponse("/platby/prehled?entita=prostory", status_code=302)

    back_url = back or "/platby/prehled?entita=prostory"
    if "/platby/prehled" in back_url:
        back_label = "Zpět na matici plateb"
    elif "/platby/dluznici" in back_url:
        back_label = "Zpět na dlužníky"
    elif "/prostory/" in back_url:
        back_label = "Zpět na detail prostoru"
    else:
        back_label = "Zpět na platby"

    return templates.TemplateResponse("payments/prostor_platby.html", {
        "request": request,
        "active_nav": "platby",
        "active_tab": "prehled",
        "space": space,
        "detail": detail,
        "rok": rok,
        "years": years,
        "back_url": back_url,
        "back_label": back_label,
        "hide_nav_back": True,
        "month_names": MONTH_NAMES,
        **(compute_nav_stats(db) if not is_htmx_partial(request) else {}),
    })
