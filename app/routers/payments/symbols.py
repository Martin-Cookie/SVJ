"""Router pro správu variabilních symbolů (VS → jednotka mapování)."""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import asc as sa_asc, desc as sa_desc
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import VariableSymbolMapping, Unit, Space, SymbolSource
from app.utils import build_list_url, is_htmx_partial, strip_diacritics
from ._helpers import templates, logger, compute_nav_stats

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
        joinedload(VariableSymbolMapping.unit),
        joinedload(VariableSymbolMapping.space),
    )

    # Filtry
    if q:
        # Escape SQL LIKE speciálních znaků
        q_escaped = q.replace("%", r"\%").replace("_", r"\_")
        q_ascii = strip_diacritics(q)
        q_ascii_escaped = q_ascii.replace("%", r"\%").replace("_", r"\_")
        query = query.filter(
            VariableSymbolMapping.variable_symbol.like(f"%{q_escaped}%", escape="\\")
            | VariableSymbolMapping.description.like(f"%{q_ascii_escaped}%", escape="\\")
        )

    if zdroj:
        query = query.filter(VariableSymbolMapping.source == zdroj)

    # Filtr typ entity
    entity = request.query_params.get("entita", "")
    if entity == "jednotky":
        query = query.filter(VariableSymbolMapping.unit_id.isnot(None))
    elif entity == "prostory":
        query = query.filter(VariableSymbolMapping.space_id.isnot(None))

    # Řazení
    col = SORT_COLUMNS.get(sort)
    if col is not None:
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

    # Jednotky a prostory pro formulář přidání
    units = db.query(Unit).order_by(Unit.unit_number).all()
    spaces = db.query(Space).order_by(Space.space_number).all()

    # Zdroje pro bubliny
    sources = db.query(VariableSymbolMapping.source).distinct().all()
    sources = sorted(set(s[0].value for s in sources if s[0]))

    list_url = build_list_url(request)
    back_url = request.query_params.get("back", "")

    # Flash zprávy
    flash_message = ""
    flash_param = request.query_params.get("flash", "")
    chyba = request.query_params.get("chyba", "")
    if flash_param == "ok":
        flash_message = "Variabilní symbol přidán."
    elif flash_param == "smazano":
        flash_message = "Variabilní symbol smazán."
    elif chyba == "duplicita":
        flash_message = "Variabilní symbol již existuje."
    elif chyba == "prazdny":
        flash_message = "Variabilní symbol nesmí být prázdný."

    # Count by entity type for bubbles
    unit_vs_count = db.query(VariableSymbolMapping).filter(VariableSymbolMapping.unit_id.isnot(None)).count()
    space_vs_count = db.query(VariableSymbolMapping).filter(VariableSymbolMapping.space_id.isnot(None)).count()

    ctx = {
        "request": request,
        "active_nav": "platby",
        "mappings": mappings,
        "units": units,
        "spaces": spaces,
        "sources": sources,
        "sort": sort,
        "order": order,
        "q": q,
        "zdroj": zdroj,
        "entita": entity,
        "unit_vs_count": unit_vs_count,
        "space_vs_count": space_vs_count,
        "list_url": list_url,
        "back_url": back_url,
        "flash_message": flash_message,
        "flash_type": "error" if chyba else "",
        "active_tab": "symboly",
        **(compute_nav_stats(db) if not is_htmx_partial(request) else {}),
    }

    if is_htmx_partial(request):
        return templates.TemplateResponse("payments/partials/symboly_tbody.html", ctx)

    return templates.TemplateResponse("payments/symboly.html", ctx)


def _symboly_redirect_url(form_data, flash: str = "", chyba: str = "") -> str:
    """Sestaví redirect URL zpět na symboly se zachováním filtrů."""
    params = []
    if flash:
        params.append(f"flash={flash}")
    if chyba:
        params.append(f"chyba={chyba}")
    for key in ("q", "sort", "order", "zdroj", "entita", "back"):
        val = form_data.get(key, "")
        if val:
            params.append(f"{key}={val}")
    qs = "&".join(params)
    return f"/platby/symboly?{qs}" if qs else "/platby/symboly"


@router.post("/symboly/pridat")
async def symbol_pridat(
    request: Request,
    variable_symbol: str = Form(...),
    entity_type: str = Form("unit"),
    unit_id: int = Form(0),
    space_id: int = Form(0),
    description: str = Form(""),
    db: Session = Depends(get_db),
):
    """Přidat nové VS mapování."""
    form_data = await request.form()

    # Validace VS — pouze číslice a alfanumerické znaky
    vs_clean = variable_symbol.strip()
    if not vs_clean:
        return RedirectResponse(_symboly_redirect_url(form_data, chyba="prazdny"), status_code=302)

    # Kontrola duplicity
    existing = db.query(VariableSymbolMapping).filter_by(variable_symbol=vs_clean).first()
    if existing:
        return RedirectResponse(_symboly_redirect_url(form_data, chyba="duplicita"), status_code=302)

    mapping = VariableSymbolMapping(
        variable_symbol=vs_clean,
        source=SymbolSource.MANUAL,
        description=description.strip() or None,
    )
    if entity_type == "space" and space_id:
        mapping.space_id = space_id
        mapping.unit_id = None
    else:
        mapping.unit_id = unit_id if unit_id else None
        mapping.space_id = None

    db.add(mapping)
    db.commit()
    return RedirectResponse(_symboly_redirect_url(form_data, flash="ok"), status_code=302)


@router.post("/symboly/{mapping_id}/upravit")
async def symbol_upravit(
    request: Request,
    mapping_id: int,
    variable_symbol: str = Form(""),
    entity_type: str = Form("unit"),
    unit_id: int = Form(0),
    space_id: int = Form(0),
    description: str = Form(""),
    db: Session = Depends(get_db),
):
    """Upravit existující VS mapování."""
    form_data = await request.form()
    mapping = db.query(VariableSymbolMapping).get(mapping_id)
    if not mapping:
        return RedirectResponse(_symboly_redirect_url(form_data, chyba="nenalezeno"), status_code=302)

    # Aktualizace VS pokud se změnil
    vs_clean = variable_symbol.strip()
    if vs_clean and vs_clean != mapping.variable_symbol:
        existing = db.query(VariableSymbolMapping).filter_by(variable_symbol=vs_clean).first()
        if existing:
            return RedirectResponse(_symboly_redirect_url(form_data, chyba="duplicita"), status_code=302)
        mapping.variable_symbol = vs_clean

    if entity_type == "space" and space_id:
        mapping.space_id = space_id
        mapping.unit_id = None
    else:
        mapping.unit_id = unit_id if unit_id else None
        mapping.space_id = None
    mapping.description = description.strip() or None
    db.commit()
    return RedirectResponse(_symboly_redirect_url(form_data, flash="upraveno"), status_code=302)


@router.post("/symboly/{mapping_id}/smazat")
async def symbol_smazat(
    request: Request,
    mapping_id: int,
    db: Session = Depends(get_db),
):
    """Smazat VS mapování."""
    form_data = await request.form()
    mapping = db.query(VariableSymbolMapping).get(mapping_id)
    if mapping:
        db.delete(mapping)
        db.commit()
    return RedirectResponse(_symboly_redirect_url(form_data, flash="smazano"), status_code=302)
