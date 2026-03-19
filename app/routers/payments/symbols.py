"""Router pro správu variabilních symbolů (VS → jednotka mapování)."""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import VariableSymbolMapping, Unit, SymbolSource
from app.utils import build_list_url, is_htmx_partial, strip_diacritics
from ._helpers import templates, logger

router = APIRouter()


SORT_COLUMNS = {
    "vs": VariableSymbolMapping.variable_symbol,
    "jednotka": None,  # Python-side sort
    "zdroj": VariableSymbolMapping.source,
    "popis": VariableSymbolMapping.description,
}


@router.get("/symboly")
async def symboly_seznam(
    request: Request,
    sort: str = "vs",
    order: str = "asc",
    q: str = "",
    zdroj: str = "",
    db: Session = Depends(get_db),
):
    """Seznam VS mapování."""
    query = db.query(VariableSymbolMapping).options(
        joinedload(VariableSymbolMapping.unit)
    )

    # Filtry
    if q:
        query = query.filter(
            VariableSymbolMapping.variable_symbol.like(f"%{q}%")
            | VariableSymbolMapping.description.ilike(f"%{q}%")
        )

    if zdroj:
        query = query.filter(VariableSymbolMapping.source == zdroj)

    # Řazení
    col = SORT_COLUMNS.get(sort)
    if col is not None:
        from sqlalchemy import asc as sa_asc, desc as sa_desc
        order_fn = sa_desc if order == "desc" else sa_asc
        query = query.order_by(order_fn(col).nulls_last())
    else:
        query = query.order_by(VariableSymbolMapping.variable_symbol)

    mappings = query.all()

    # Python-side sort pro jednotku
    if sort == "jednotka":
        mappings.sort(
            key=lambda m: m.unit.unit_number if m.unit else 0,
            reverse=(order == "desc"),
        )

    # Jednotky pro formulář přidání
    units = db.query(Unit).order_by(Unit.unit_number).all()

    # Zdroje pro bubliny
    sources = db.query(VariableSymbolMapping.source).distinct().all()
    sources = sorted(set(s[0].value for s in sources if s[0]))

    list_url = build_list_url(request)
    back_url = request.query_params.get("back", "")

    ctx = {
        "request": request,
        "active_nav": "platby",
        "mappings": mappings,
        "units": units,
        "sources": sources,
        "sort": sort,
        "order": order,
        "q": q,
        "zdroj": zdroj,
        "list_url": list_url,
        "back_url": back_url,
    }

    if is_htmx_partial(request):
        return templates.TemplateResponse("payments/partials/symboly_tbody.html", ctx)

    return templates.TemplateResponse("payments/symboly.html", ctx)


@router.post("/symboly/pridat")
async def symbol_pridat(
    request: Request,
    variable_symbol: str = Form(...),
    unit_id: int = Form(...),
    description: str = Form(""),
    db: Session = Depends(get_db),
):
    """Přidat nové VS mapování."""
    # Kontrola duplicity
    existing = db.query(VariableSymbolMapping).filter_by(variable_symbol=variable_symbol.strip()).first()
    if existing:
        return RedirectResponse("/platby/symboly?chyba=duplicita", status_code=302)

    db.add(VariableSymbolMapping(
        variable_symbol=variable_symbol.strip(),
        unit_id=unit_id,
        source=SymbolSource.MANUAL,
        description=description.strip() or None,
    ))
    db.commit()
    return RedirectResponse("/platby/symboly", status_code=302)


@router.post("/symboly/{mapping_id}/smazat")
async def symbol_smazat(
    request: Request,
    mapping_id: int,
    db: Session = Depends(get_db),
):
    """Smazat VS mapování."""
    mapping = db.query(VariableSymbolMapping).get(mapping_id)
    if mapping:
        db.delete(mapping)
        db.commit()
    return RedirectResponse("/platby/symboly", status_code=302)
