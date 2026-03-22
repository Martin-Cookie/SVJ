"""Přehled plateb — matice, dlužníci, detail jednotky."""

from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import PrescriptionYear, Unit
from app.services.payment_overview import (
    compute_debtor_list,
    compute_payment_matrix,
    compute_unit_payment_detail,
)
from app.utils import build_list_url, is_htmx_partial, strip_diacritics

from ._helpers import templates, compute_nav_stats

router = APIRouter()

MONTH_NAMES = {
    1: "Led", 2: "Úno", 3: "Bře", 4: "Dub", 5: "Kvě", 6: "Čvn",
    7: "Čvc", 8: "Srp", 9: "Zář", 10: "Říj", 11: "Lis", 12: "Pro",
}


# ── Matice plateb ────────────────────────────────────────────────────


SORT_COLUMNS_MATRIX = {
    "cislo": None,     # Python sort
    "sekce": None,
    "vlastnik": None,
    "predpis": None,
    "celkem": None,
    "dluh": None,
}


@router.get("/prehled")
async def platby_prehled(
    request: Request,
    rok: int = Query(0),
    typ: str = Query(""),
    q: str = Query(""),
    sort: str = Query("cislo"),
    order: str = Query("asc"),
    back: str = Query("", alias="back"),
    db: Session = Depends(get_db),
):
    """Matice plateb — jednotky × měsíce."""
    # Výchozí rok = nejnovější PrescriptionYear
    if not rok:
        latest = db.query(PrescriptionYear).order_by(PrescriptionYear.year.desc()).first()
        rok = latest.year if latest else datetime.utcnow().year

    years = [y.year for y in db.query(PrescriptionYear).order_by(PrescriptionYear.year.desc()).all()]

    matrix = compute_payment_matrix(db, rok, space_type=typ)
    rows = matrix["units"]

    # Search
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

    # Sort
    sort_key = sort if sort in SORT_COLUMNS_MATRIX else "cislo"
    reverse = order == "desc"
    sort_fns = {
        "cislo": lambda r: r["unit"].unit_number or 0,
        "sekce": lambda r: (r["prescription"].section or "").lower(),
        "vlastnik": lambda r: strip_diacritics(r["owner"].display_name if r["owner"] else r["prescription"].owner_name or ""),
        "predpis": lambda r: r["monthly"],
        "celkem": lambda r: r["total_paid"],
        "dluh": lambda r: r["debt"],
    }
    rows.sort(key=sort_fns.get(sort_key, sort_fns["cislo"]), reverse=reverse)

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
        "back_url": back,
        "list_url": list_url,
        "month_names": MONTH_NAMES,
        "months_with_data": matrix["months_with_data"],
        "space_types": matrix["space_types"],
        "total_prescribed": matrix["total_prescribed"],
        "total_paid": matrix["total_paid"],
        "total_units": len(matrix["units"]),
        "active_tab": "prehled",
        **compute_nav_stats(db),
    }

    if is_htmx_partial(request):
        return templates.TemplateResponse("payments/partials/prehled_tbody.html", ctx)

    return templates.TemplateResponse("payments/prehled.html", ctx)


# ── Dlužníci ─────────────────────────────────────────────────────────


SORT_COLUMNS_DEBTORS = {
    "cislo": None,
    "vlastnik": None,
    "predpis": None,
    "zaplaceno": None,
    "dluh": None,
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
    """Seznam dlužníků."""
    if not rok:
        latest = db.query(PrescriptionYear).order_by(PrescriptionYear.year.desc()).first()
        rok = latest.year if latest else datetime.utcnow().year

    years = [y.year for y in db.query(PrescriptionYear).order_by(PrescriptionYear.year.desc()).all()]

    debtors, months_with_data = compute_debtor_list(db, rok)

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
        "back_url": back,
        "list_url": list_url,
        "months_with_data": months_with_data,
        "total_debt": sum(r["debt"] for r in debtors),
        "active_tab": "dluznici",
        **compute_nav_stats(db),
    }

    if is_htmx_partial(request):
        return templates.TemplateResponse("payments/partials/dluznici_tbody.html", ctx)

    return templates.TemplateResponse("payments/dluznici.html", ctx)


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
        rok = latest.year if latest else datetime.utcnow().year

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
        "month_names": MONTH_NAMES,
        **compute_nav_stats(db),
    })
