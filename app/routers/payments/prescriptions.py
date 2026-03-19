"""Router pro předpisy plateb — seznam, import DOCX, detail."""

from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request, UploadFile, File
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import (
    PrescriptionYear, Prescription, PrescriptionItem, Unit,
    VariableSymbolMapping, SymbolSource,
)
from app.utils import build_list_url, is_htmx_partial, validate_upload, UPLOAD_LIMITS
from ._helpers import templates, logger, compute_nav_stats

router = APIRouter()


# ── Seznam předpisů ────────────────────────────────────────────────────



@router.get("/predpisy")
async def predpisy_seznam(request: Request, db: Session = Depends(get_db)):
    """Seznam předpisů podle roku."""
    years = (
        db.query(PrescriptionYear)
        .order_by(PrescriptionYear.year.desc())
        .all()
    )
    list_url = build_list_url(request)
    back_url = request.query_params.get("back", "")

    ctx = {
        "request": request,
        "active_nav": "platby",
        "active_tab": "predpisy",
        "years": years,
        "list_url": list_url,
        "back_url": back_url,
        **compute_nav_stats(db),
    }
    return templates.TemplateResponse("payments/predpisy.html", ctx)


# ── Import předpisů z DOCX ────────────────────────────────────────────


@router.get("/predpisy/import")
async def predpisy_import_form(request: Request, db: Session = Depends(get_db)):
    """Formulář pro import předpisů z DOCX."""
    back_url = request.query_params.get("back", "")
    return templates.TemplateResponse("payments/predpisy_import.html", {
        "request": request,
        "active_nav": "platby",
        "back_url": back_url,
    })


@router.post("/predpisy/import")
async def predpisy_import_upload(
    request: Request,
    file: UploadFile = File(...),
    year: int = Form(...),
    db: Session = Depends(get_db),
):
    """Zpracování importu předpisů z DOCX."""
    from app.services.prescription_import import parse_prescription_docx

    # Validace souboru
    error = await validate_upload(file, **UPLOAD_LIMITS["docx"])
    if error:
        return templates.TemplateResponse("payments/predpisy_import.html", {
            "request": request,
            "active_nav": "platby",
            "error": error,
            "form_data": {"year": year},
        })

    # Kontrola duplicity roku
    existing = db.query(PrescriptionYear).filter_by(year=year).first()
    force = (await request.form()).get("force_overwrite")
    if existing and not force:
        return templates.TemplateResponse("payments/predpisy_import.html", {
            "request": request,
            "active_nav": "platby",
            "confirm_overwrite": True,
            "existing_year": existing,
            "form_data": {"year": year},
            "filename": file.filename,
        })

    # Smazat existující rok pokud přepisujeme
    if existing:
        db.delete(existing)
        db.flush()

    # Parsování DOCX
    try:
        file_content = await file.read()
        result = parse_prescription_docx(file_content, year)
    except Exception as e:
        logger.error("DOCX parse error: %s", e)
        return templates.TemplateResponse("payments/predpisy_import.html", {
            "request": request,
            "active_nav": "platby",
            "error": f"Chyba při čtení DOCX: {e}",
            "form_data": {"year": year},
        })

    # Uložení do DB
    prescription_year = PrescriptionYear(
        year=year,
        valid_from=result.get("valid_from"),
        description=f"Import z {file.filename}",
        source_filename=file.filename,
        total_units=len(result["prescriptions"]),
        total_monthly=sum(p["monthly_total"] for p in result["prescriptions"]),
    )
    db.add(prescription_year)
    db.flush()

    # Načíst mapování jednotek podle čísla prostoru
    units_by_number = {u.unit_number: u for u in db.query(Unit).all()}

    vs_created = 0
    matched_units = 0

    for p_data in result["prescriptions"]:
        # Najít jednotku podle čísla prostoru
        unit = units_by_number.get(p_data.get("space_number"))

        prescription = Prescription(
            prescription_year_id=prescription_year.id,
            unit_id=unit.id if unit else None,
            variable_symbol=p_data.get("variable_symbol"),
            space_number=p_data.get("space_number"),
            section=p_data.get("section"),
            space_type=p_data.get("space_type"),
            owner_name=p_data.get("owner_name"),
            monthly_total=p_data["monthly_total"],
        )
        db.add(prescription)
        db.flush()

        if unit:
            matched_units += 1

        # Položky předpisu
        for idx, item in enumerate(p_data.get("items", [])):
            db.add(PrescriptionItem(
                prescription_id=prescription.id,
                name=item["name"],
                amount=item["amount"],
                category=item["category"],
                order=idx,
            ))

        # Automatické vytvoření VS mapování
        vs = p_data.get("variable_symbol")
        if vs and unit:
            existing_vs = db.query(VariableSymbolMapping).filter_by(variable_symbol=vs).first()
            if not existing_vs:
                db.add(VariableSymbolMapping(
                    variable_symbol=vs,
                    unit_id=unit.id,
                    source=SymbolSource.AUTO,
                    description=f"Auto z předpisu {year}",
                ))
                vs_created += 1

    db.commit()

    return RedirectResponse(
        f"/platby/predpisy/{prescription_year.id}?flash=import_ok&matched={matched_units}"
        f"&total={len(result['prescriptions'])}&vs_created={vs_created}",
        status_code=302,
    )


# ── Detail předpisu (rok) ──────────────────────────────────────────────


SORT_COLUMNS = {
    "prostor": "space_number",
    "sekce": "section",
    "typ": "space_type",
    "vs": "variable_symbol",
    "castka": "monthly_total",
    "vlastnik": "owner_name",
}


@router.get("/predpisy/{year_id}")
async def predpisy_detail(
    request: Request,
    year_id: int,
    sort: str = "prostor",
    order: str = "asc",
    q: str = "",
    typ: str = "",
    db: Session = Depends(get_db),
):
    """Detail předpisů pro daný rok."""
    prescription_year = db.query(PrescriptionYear).get(year_id)
    if not prescription_year:
        return RedirectResponse("/platby/predpisy", status_code=302)

    query = (
        db.query(Prescription)
        .filter_by(prescription_year_id=year_id)
        .options(joinedload(Prescription.items), joinedload(Prescription.unit))
    )

    if typ:
        query = query.filter(Prescription.space_type == typ)

    # Řazení
    col = SORT_COLUMNS.get(sort, "space_number")
    if col:
        from sqlalchemy import asc as sa_asc, desc as sa_desc
        order_fn = sa_desc if order == "desc" else sa_asc
        query = query.order_by(order_fn(getattr(Prescription, col)).nulls_last())

    prescriptions = query.all()

    # Python-side search s diakritikou (Prescription nemá name_normalized)
    if q:
        from app.utils import strip_diacritics
        q_ascii = strip_diacritics(q)
        prescriptions = [
            p for p in prescriptions
            if q_ascii in strip_diacritics(p.owner_name or "")
            or q.lower() in (p.variable_symbol or "").lower()
            or q.lower() in (p.section or "").lower()
            or q in str(p.space_number or "")
        ]

    # Typy pro bubliny
    space_types = (
        db.query(Prescription.space_type)
        .filter_by(prescription_year_id=year_id)
        .filter(Prescription.space_type.isnot(None))
        .distinct()
        .all()
    )
    space_types = sorted(set(t[0] for t in space_types))

    # Flash zprávy z importu
    flash_message = ""
    flash_type = ""
    flash = request.query_params.get("flash", "")
    if flash == "import_ok":
        matched = request.query_params.get("matched", "0")
        total = request.query_params.get("total", "0")
        vs_created = request.query_params.get("vs_created", "0")
        flash_message = (
            f"Import dokončen: {total} předpisů, "
            f"{matched} napárováno na jednotky, "
            f"{vs_created} nových VS mapování."
        )

    list_url = build_list_url(request)
    back_url = request.query_params.get("back", "")

    ctx = {
        "request": request,
        "active_nav": "platby",
        "prescription_year": prescription_year,
        "prescriptions": prescriptions,
        "space_types": space_types,
        "sort": sort,
        "order": order,
        "q": q,
        "typ": typ,
        "list_url": list_url,
        "back_url": back_url,
        "flash_message": flash_message,
        "flash_type": flash_type,
    }

    if is_htmx_partial(request):
        return templates.TemplateResponse("payments/partials/predpisy_tbody.html", ctx)

    return templates.TemplateResponse("payments/predpisy_detail.html", ctx)


# ── Detail jednoho předpisu (jednotka) ─────────────────────────────────


@router.get("/predpisy/{year_id}/{prescription_id}")
async def predpis_jednotka_detail(
    request: Request,
    year_id: int,
    prescription_id: int,
    db: Session = Depends(get_db),
):
    """Detail jednoho předpisu (položky pro jednu jednotku)."""
    prescription = (
        db.query(Prescription)
        .filter_by(id=prescription_id, prescription_year_id=year_id)
        .options(joinedload(Prescription.items), joinedload(Prescription.unit))
        .first()
    )
    if not prescription:
        return RedirectResponse(f"/platby/predpisy/{year_id}", status_code=302)

    prescription_year = db.query(PrescriptionYear).get(year_id)
    list_url = build_list_url(request)
    back_url = request.query_params.get("back", "")

    return templates.TemplateResponse("payments/predpis_detail.html", {
        "request": request,
        "active_nav": "platby",
        "prescription_year": prescription_year,
        "prescription": prescription,
        "list_url": list_url,
        "back_url": back_url,
    })


# ── Smazání roku předpisů ─────────────────────────────────────────────


@router.post("/predpisy/{year_id}/smazat")
async def predpisy_smazat(
    request: Request,
    year_id: int,
    db: Session = Depends(get_db),
):
    """Smazání celého roku předpisů."""
    prescription_year = db.query(PrescriptionYear).get(year_id)
    if prescription_year:
        db.delete(prescription_year)
        db.commit()
    return RedirectResponse("/platby/predpisy", status_code=302)
