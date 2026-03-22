"""Router pro počáteční zůstatky jednotek."""

from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session, joinedload
from app.database import get_db
from app.models import UnitBalance, Unit, BalanceSource
from app.utils import build_list_url, is_htmx_partial
from ._helpers import templates, logger, compute_nav_stats

router = APIRouter()


@router.get("/zustatky")
async def zustatky_seznam(
    request: Request,
    rok: int = 0,
    sort: str = "jednotka",
    order: str = "asc",
    db: Session = Depends(get_db),
):
    """Seznam počátečních zůstatků."""
    # Dostupné roky
    years = (
        db.query(UnitBalance.year)
        .distinct()
        .order_by(UnitBalance.year.desc())
        .all()
    )
    years = [y[0] for y in years]

    # Pokud rok není zadán, použít nejnovější; pokud žádné zůstatky, aktuální rok
    if rok == 0:
        rok = years[0] if years else datetime.utcnow().year

    query = (
        db.query(UnitBalance)
        .options(joinedload(UnitBalance.unit))
    )
    if rok:
        query = query.filter(UnitBalance.year == rok)

    balances = query.all()

    # Řazení
    if sort == "jednotka":
        balances.sort(key=lambda b: b.unit.unit_number if b.unit else 0, reverse=(order == "desc"))
    elif sort == "castka":
        balances.sort(key=lambda b: b.opening_amount, reverse=(order == "desc"))

    # Jednotky pro formulář
    units = db.query(Unit).order_by(Unit.unit_number).all()
    existing_unit_ids = {b.unit_id for b in balances}

    total_dluh = sum(b.opening_amount for b in balances if b.opening_amount > 0)
    total_preplatek = sum(b.opening_amount for b in balances if b.opening_amount < 0)

    list_url = build_list_url(request)
    back_url = request.query_params.get("back", "")

    # Flash zprávy z query parametru → globální toast
    flash_param = request.query_params.get("flash", "")
    flash_message = ""
    flash_type = ""
    if flash_param == "ok":
        flash_message = "Zůstatek uložen."
    elif flash_param == "smazano":
        flash_message = "Zůstatek smazán."
    elif flash_param == "chyba_rok":
        flash_message = "Rok musí být mezi 2020 a 2040."
        flash_type = "error"

    ctx = {
        "request": request,
        "active_nav": "platby",
        "balances": balances,
        "units": units,
        "years": years,
        "rok": rok,
        "sort": sort,
        "order": order,
        "existing_unit_ids": existing_unit_ids,
        "total_dluh": total_dluh,
        "total_preplatek": total_preplatek,
        "list_url": list_url,
        "back_url": back_url,
        "flash_message": flash_message,
        "flash_type": flash_type,
        "active_tab": "zustatky",
        **compute_nav_stats(db),
    }

    if is_htmx_partial(request):
        return templates.TemplateResponse("payments/partials/zustatky_tbody.html", ctx)

    return templates.TemplateResponse("payments/zustatky.html", ctx)


@router.post("/zustatky/pridat")
async def zustatek_pridat(
    request: Request,
    unit_id: int = Form(...),
    year: int = Form(...),
    opening_amount: float = Form(...),
    note: str = Form(""),
    db: Session = Depends(get_db),
):
    """Přidat/aktualizovat počáteční zůstatek."""
    if year < 2020 or year > 2040:
        return RedirectResponse("/platby/zustatky?flash=chyba_rok", status_code=302)

    existing = (
        db.query(UnitBalance)
        .filter_by(unit_id=unit_id, year=year)
        .first()
    )
    if existing:
        existing.opening_amount = opening_amount
        existing.note = note.strip() or None
        existing.source = BalanceSource.MANUAL
    else:
        db.add(UnitBalance(
            unit_id=unit_id,
            year=year,
            opening_amount=opening_amount,
            source=BalanceSource.MANUAL,
            note=note.strip() or None,
        ))
    db.commit()
    return RedirectResponse(f"/platby/zustatky?rok={year}&flash=ok", status_code=302)


@router.post("/zustatky/{balance_id}/smazat")
async def zustatek_smazat(
    request: Request,
    balance_id: int,
    db: Session = Depends(get_db),
):
    """Smazat zůstatek."""
    balance = db.query(UnitBalance).get(balance_id)
    rok = balance.year if balance else 0
    if balance:
        db.delete(balance)
        db.commit()
    return RedirectResponse(f"/platby/zustatky?rok={rok}&flash=smazano", status_code=302)
