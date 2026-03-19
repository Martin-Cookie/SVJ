"""Vyúčtování — seznam, detail, generování, stav, mazání."""

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import (
    PrescriptionYear, Settlement, SettlementItem, SettlementStatus,
)
from app.services.settlement_service import (
    generate_settlements,
    get_settlement_detail,
    update_settlement_status,
)
from app.utils import build_list_url, is_htmx_partial, strip_diacritics

from ._helpers import templates

router = APIRouter()

# ── Pomocné ──────────────────────────────────────────────────────────

STATUS_LABELS = {
    "": "Vše",
    "generated": "Vygenerováno",
    "sent": "Odesláno",
    "paid": "Zaplaceno",
    "overdue": "Po splatnosti",
}

STATUS_COLORS = {
    "generated": ("bg-blue-100 text-blue-800", "dark:bg-blue-900 dark:text-blue-200"),
    "sent": ("bg-yellow-100 text-yellow-800", "dark:bg-yellow-900 dark:text-yellow-200"),
    "paid": ("bg-green-100 text-green-800", "dark:bg-green-900 dark:text-green-200"),
    "overdue": ("bg-red-100 text-red-800", "dark:bg-red-900 dark:text-red-200"),
}

SORT_COLUMNS = {
    "cislo": None,      # Python sort
    "vlastnik": None,
    "predpis": None,
    "zaplaceno": None,
    "vysledek": None,
    "stav": None,
}


# ── Seznam vyúčtování ────────────────────────────────────────────────


@router.get("/vyuctovani")
async def vyuctovani_seznam(
    request: Request,
    rok: int = Query(0),
    stav: str = Query(""),
    q: str = Query(""),
    sort: str = Query("cislo"),
    order: str = Query("asc"),
    back: str = Query("", alias="back"),
    db: Session = Depends(get_db),
):
    """Seznam vyúčtování s filtry, hledáním a řazením."""
    # Výchozí rok
    if not rok:
        latest = db.query(PrescriptionYear).order_by(PrescriptionYear.year.desc()).first()
        rok = latest.year if latest else 2026

    years = [y.year for y in db.query(PrescriptionYear).order_by(PrescriptionYear.year.desc()).all()]

    # Dotaz
    query = (
        db.query(Settlement)
        .filter_by(year=rok)
        .options(
            joinedload(Settlement.unit),
            joinedload(Settlement.owner),
            joinedload(Settlement.items),
        )
    )

    if stav and stav in STATUS_LABELS:
        try:
            query = query.filter(Settlement.status == SettlementStatus(stav))
        except ValueError:
            pass

    settlements = query.all()

    # Hledání
    if q:
        q_ascii = strip_diacritics(q)
        settlements = [
            s for s in settlements
            if q_ascii in strip_diacritics(str(s.unit.unit_number) if s.unit else "")
            or q_ascii in strip_diacritics(s.owner.display_name if s.owner else "")
            or q_ascii in strip_diacritics(s.variable_symbol or "")
        ]

    # Statistiky bublin (před sort/filter aby čísla odpovídala celému roku)
    all_year = db.query(Settlement).filter_by(year=rok).all()
    bubble_counts = {"": len(all_year)}
    for s_enum in SettlementStatus:
        bubble_counts[s_enum.value] = sum(1 for s in all_year if s.status == s_enum)

    # Souhrnné statistiky
    total_overpay = sum(abs(s.result_amount) for s in all_year if s.result_amount < 0)
    total_underpay = sum(s.result_amount for s in all_year if s.result_amount > 0)

    # Řazení
    sort_key = sort if sort in SORT_COLUMNS else "cislo"
    reverse = order == "desc"
    sort_fns = {
        "cislo": lambda s: s.unit.unit_number if s.unit else 0,
        "vlastnik": lambda s: strip_diacritics(s.owner.display_name if s.owner else ""),
        "predpis": lambda s: _annual_prescription(s),
        "zaplaceno": lambda s: _total_paid(s),
        "vysledek": lambda s: s.result_amount or 0,
        "stav": lambda s: s.status.value if s.status else "",
    }
    settlements.sort(key=sort_fns.get(sort_key, sort_fns["cislo"]), reverse=reverse)

    list_url = build_list_url(request)

    ctx = {
        "request": request,
        "active_nav": "platby",
        "settlements": settlements,
        "rok": rok,
        "years": years,
        "stav": stav,
        "q": q,
        "sort": sort_key,
        "order": order,
        "back_url": back,
        "list_url": list_url,
        "status_labels": STATUS_LABELS,
        "status_colors": STATUS_COLORS,
        "bubble_counts": bubble_counts,
        "total_overpay": total_overpay,
        "total_underpay": total_underpay,
    }

    if is_htmx_partial(request):
        return templates.TemplateResponse("payments/partials/vyuctovani_tbody.html", ctx)

    return templates.TemplateResponse("payments/vyuctovani.html", ctx)


def _annual_prescription(s: Settlement) -> float:
    """Celkový roční předpis = result + paid (pro sort)."""
    paid = _total_paid(s)
    return (s.result_amount or 0) + paid


def _total_paid(s: Settlement) -> float:
    """Celkem zaplaceno = sum(items.paid)."""
    return sum(item.paid or 0 for item in s.items)


# ── Detail vyúčtování ────────────────────────────────────────────────


@router.get("/vyuctovani/{settlement_id}")
async def vyuctovani_detail(
    settlement_id: int,
    request: Request,
    back: str = Query("", alias="back"),
    db: Session = Depends(get_db),
):
    """Detail jednoho vyúčtování."""
    detail = get_settlement_detail(db, settlement_id)
    if not detail:
        return RedirectResponse("/platby/vyuctovani", status_code=302)

    settlement = detail["settlement"]
    back_url = back or "/platby/vyuctovani"
    if "/platby/vyuctovani" in back_url and back_url != "/platby/vyuctovani":
        back_label = "Zpět na vyúčtování"
    elif "/jednotky/" in back_url:
        back_label = "Zpět na detail jednotky"
    else:
        back_label = "Zpět na vyúčtování"

    return templates.TemplateResponse("payments/vyuctovani_detail.html", {
        "request": request,
        "active_nav": "platby",
        "settlement": settlement,
        "detail": detail,
        "back_url": back_url,
        "back_label": back_label,
        "status_labels": STATUS_LABELS,
        "status_colors": STATUS_COLORS,
    })


# ── Generování vyúčtování ────────────────────────────────────────────


@router.post("/vyuctovani/generovat")
async def vyuctovani_generovat(
    request: Request,
    rok: int = Form(...),
    back: str = Form(""),
    db: Session = Depends(get_db),
):
    """Generování vyúčtování pro rok."""
    result = generate_settlements(db, rok)
    redirect_url = f"/platby/vyuctovani?rok={rok}"
    if back:
        redirect_url += f"&back={back}"
    return RedirectResponse(redirect_url, status_code=302)


# ── Změna stavu ──────────────────────────────────────────────────────


@router.post("/vyuctovani/{settlement_id}/stav")
async def vyuctovani_zmena_stavu(
    settlement_id: int,
    request: Request,
    novy_stav: str = Form(...),
    back: str = Form(""),
    db: Session = Depends(get_db),
):
    """Změna stavu vyúčtování."""
    settlement = update_settlement_status(db, settlement_id, novy_stav)
    if not settlement:
        return RedirectResponse("/platby/vyuctovani", status_code=302)

    redirect_url = f"/platby/vyuctovani/{settlement_id}"
    if back:
        redirect_url += f"?back={back}"
    return RedirectResponse(redirect_url, status_code=302)


# ── Smazání roku ─────────────────────────────────────────────────────


@router.post("/vyuctovani/smazat-rok")
async def vyuctovani_smazat_rok(
    request: Request,
    rok: int = Form(...),
    back: str = Form(""),
    db: Session = Depends(get_db),
):
    """Smazání všech vyúčtování roku."""
    settlements = db.query(Settlement).filter_by(year=rok).all()
    for s in settlements:
        db.delete(s)
    db.commit()

    redirect_url = "/platby/vyuctovani"
    if back:
        redirect_url += f"?back={back}"
    return RedirectResponse(redirect_url, status_code=302)
