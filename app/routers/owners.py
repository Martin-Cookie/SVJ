import shutil
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import cast, func, String
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.database import get_db
from app.models import ImportLog, Owner, OwnerType, OwnerUnit, Unit
from app.services.excel_import import import_owners_from_excel, preview_owners_from_excel

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


SORT_COLUMNS = {
    "name": Owner.name_normalized,
    "type": Owner.owner_type,
    "email": Owner.email,
    "phone": Owner.phone,
    "podil": None,  # handled in Python — needs sum across units
    "jednotky": None,  # handled in Python
    "sekce": None,  # handled in Python
}


@router.get("/")
async def owner_list(
    request: Request,
    q: str = Query("", alias="q"),
    owner_type: str = Query("", alias="typ"),
    sekce: str = Query("", alias="sekce"),
    sort: str = Query("name", alias="sort"),
    order: str = Query("asc", alias="order"),
    db: Session = Depends(get_db),
):
    query = db.query(Owner).filter_by(is_active=True).options(
        joinedload(Owner.units).joinedload(OwnerUnit.unit)
    )
    if q:
        search = f"%{q}%"
        # Search across name, email, phone, birth number, company ID, unit number
        query = query.filter(
            Owner.name_with_titles.ilike(search)
            | Owner.name_normalized.ilike(search)
            | Owner.first_name.ilike(search)
            | Owner.last_name.ilike(search)
            | Owner.email.ilike(search)
            | Owner.phone.ilike(search)
            | Owner.birth_number.ilike(search)
            | Owner.company_id.ilike(search)
            | Owner.units.any(OwnerUnit.unit.has(cast(Unit.unit_number, String).ilike(search)))
        )
    if owner_type:
        query = query.filter(Owner.owner_type == owner_type)
    if sekce:
        query = query.filter(
            Owner.units.any(OwnerUnit.unit.has(Unit.section == sekce))
        )

    # Sorting
    sort_col = SORT_COLUMNS.get(sort)
    if sort == "podil":
        owners = query.all()
        owners.sort(
            key=lambda o: sum(ou.votes for ou in o.units),
            reverse=(order == "desc"),
        )
    elif sort == "jednotky":
        owners = query.all()
        owners.sort(
            key=lambda o: (o.units[0].unit.unit_number if o.units else 0),
            reverse=(order == "desc"),
        )
    elif sort == "sekce":
        owners = query.all()
        owners.sort(
            key=lambda o: (o.units[0].unit.section or "") if o.units else "",
            reverse=(order == "desc"),
        )
    elif sort_col is not None:
        if order == "desc":
            query = query.order_by(sort_col.desc().nulls_last())
        else:
            query = query.order_by(sort_col.asc().nulls_last())
        owners = query.all()
    else:
        owners = query.order_by(Owner.name_normalized).all()

    # Return partial only for targeted HTMX requests (search/filter), not boosted navigation
    is_htmx = request.headers.get("HX-Request")
    is_boosted = request.headers.get("HX-Boosted")
    if is_htmx and not is_boosted:
        return templates.TemplateResponse("partials/owner_table_body.html", {
            "request": request,
            "owners": owners,
        })

    # Stats for header
    all_owners = db.query(Owner).filter_by(is_active=True).count()
    total_units = db.query(Unit).count()
    type_counts_raw = (
        db.query(Owner.owner_type, func.count(Owner.id))
        .filter_by(is_active=True)
        .group_by(Owner.owner_type)
        .all()
    )
    type_counts = {ot.value: cnt for ot, cnt in type_counts_raw}
    sections = [
        r[0] for r in
        db.query(Unit.section).filter(Unit.section.isnot(None)).distinct().order_by(Unit.section).all()
    ]
    emails_count = db.query(Owner).filter(
        Owner.is_active == True,
        Owner.email.isnot(None),
        Owner.email != "",
    ).count()

    return templates.TemplateResponse("owners/list.html", {
        "request": request,
        "active_nav": "owners",
        "owners": owners,
        "q": q,
        "owner_type": owner_type,
        "sekce": sekce,
        "sort": sort,
        "order": order,
        "owner_types": OwnerType,
        "stats": {
            "total_owners": all_owners,
            "total_units": total_units,
            "type_counts": type_counts,
            "sections": sections,
            "emails_count": emails_count,
        },
    })


@router.get("/import")
async def import_page(request: Request, db: Session = Depends(get_db)):
    imports = db.query(ImportLog).filter_by(import_type="owners_excel").order_by(ImportLog.created_at.desc()).all()
    return templates.TemplateResponse("owners/import.html", {
        "request": request,
        "active_nav": "import",
        "imports": imports,
    })


@router.post("/import")
async def import_excel_preview(
    request: Request,
    file: UploadFile = File(...),
):
    """Step 1: Upload Excel, show preview of parsed data."""
    if not file.filename.endswith((".xlsx", ".xls")):
        return templates.TemplateResponse("owners/import.html", {
            "request": request,
            "active_nav": "import",
            "flash_message": "Nahrajte prosím soubor ve formátu .xlsx",
            "flash_type": "error",
        })

    # Save uploaded file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = settings.upload_dir / "excel" / f"{timestamp}_{file.filename}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Parse without saving to DB
    preview = preview_owners_from_excel(str(dest))

    return templates.TemplateResponse("owners/import_preview.html", {
        "request": request,
        "active_nav": "import",
        "preview": preview,
        "file_path": str(dest),
        "filename": file.filename,
    })


@router.post("/import/potvrdit")
async def import_excel_confirm(
    request: Request,
    file_path: str = Form(...),
    filename: str = Form(""),
    db: Session = Depends(get_db),
):
    """Step 2: Confirm preview and save to DB."""
    from app.models.owner import OwnerUnit

    # Clear existing owners
    db.query(OwnerUnit).delete()
    db.query(Owner).delete()
    db.query(Unit).delete()
    db.commit()

    # Import
    result = import_owners_from_excel(db, file_path)

    # Log the import
    log = ImportLog(
        filename=filename,
        file_path=file_path,
        import_type="owners_excel",
        rows_total=result["rows_processed"],
        rows_imported=result["owners_created"],
        rows_skipped=len(result["errors"]),
        errors="\n".join(result["errors"]) if result["errors"] else None,
    )
    db.add(log)
    db.commit()

    return templates.TemplateResponse("owners/import_result.html", {
        "request": request,
        "active_nav": "import",
        "result": result,
    })


@router.post("/import/{log_id}/smazat")
async def import_delete(
    log_id: int,
    db: Session = Depends(get_db),
):
    """Delete an import: remove data, log entry, and uploaded file."""
    from pathlib import Path

    log = db.query(ImportLog).filter_by(id=log_id, import_type="owners_excel").first()
    if not log:
        return RedirectResponse("/vlastnici/import", status_code=302)

    # Clear imported data
    db.query(OwnerUnit).delete()
    db.query(Owner).delete()
    db.query(Unit).delete()

    # Remove uploaded file
    try:
        p = Path(log.file_path)
        if p.exists():
            p.unlink()
    except Exception:
        pass

    # Remove log entry
    db.delete(log)
    db.commit()

    return RedirectResponse("/vlastnici/import", status_code=302)


@router.get("/{owner_id}")
async def owner_detail(
    owner_id: int,
    request: Request,
    back: str = Query("", alias="back"),
    db: Session = Depends(get_db),
):
    owner = db.query(Owner).options(
        joinedload(Owner.units).joinedload(OwnerUnit.unit)
    ).get(owner_id)
    if not owner:
        return RedirectResponse("/vlastnici", status_code=302)

    # Units not yet assigned to this owner
    assigned_unit_ids = [ou.unit_id for ou in owner.units]
    if assigned_unit_ids:
        available_units = db.query(Unit).filter(
            Unit.id.notin_(assigned_unit_ids)
        ).order_by(Unit.unit_number).all()
    else:
        available_units = db.query(Unit).order_by(Unit.unit_number).all()

    return templates.TemplateResponse("owners/detail.html", {
        "request": request,
        "active_nav": "owners",
        "owner": owner,
        "available_units": available_units,
        "back_url": back or "/vlastnici",
        "back_label": (
            "Zpět na detail jednotky" if "/jednotky/" in back
            else "Zpět na porovnání" if "/synchronizace/" in back
            else "Zpět na seznam vlastníků"
        ),
    })


@router.get("/{owner_id}/upravit-formular")
async def owner_edit_form(
    owner_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    owner = db.query(Owner).get(owner_id)
    if not owner:
        return RedirectResponse("/vlastnici", status_code=302)
    return templates.TemplateResponse("partials/owner_contact_form.html", {
        "request": request,
        "owner": owner,
    })


@router.get("/{owner_id}/info")
async def owner_info(
    owner_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    owner = db.query(Owner).get(owner_id)
    if not owner:
        return RedirectResponse("/vlastnici", status_code=302)
    return templates.TemplateResponse("partials/owner_contact_info.html", {
        "request": request,
        "owner": owner,
    })


def _address_context(owner, prefix):
    """Extract address fields for a given prefix (perm/corr)."""
    return {
        "prefix": prefix,
        "street": getattr(owner, f"{prefix}_street"),
        "district": getattr(owner, f"{prefix}_district"),
        "city": getattr(owner, f"{prefix}_city"),
        "zip": getattr(owner, f"{prefix}_zip"),
        "country": getattr(owner, f"{prefix}_country"),
    }


@router.get("/{owner_id}/adresa/{prefix}/upravit-formular")
async def owner_address_edit_form(
    owner_id: int,
    prefix: str,
    request: Request,
    db: Session = Depends(get_db),
):
    if prefix not in ("perm", "corr"):
        return RedirectResponse(f"/vlastnici/{owner_id}", status_code=302)
    owner = db.query(Owner).get(owner_id)
    if not owner:
        return RedirectResponse("/vlastnici", status_code=302)
    return templates.TemplateResponse("partials/owner_address_form.html", {
        "request": request,
        "owner": owner,
        **_address_context(owner, prefix),
    })


@router.get("/{owner_id}/adresa/{prefix}/info")
async def owner_address_info(
    owner_id: int,
    prefix: str,
    request: Request,
    db: Session = Depends(get_db),
):
    if prefix not in ("perm", "corr"):
        return RedirectResponse(f"/vlastnici/{owner_id}", status_code=302)
    owner = db.query(Owner).get(owner_id)
    if not owner:
        return RedirectResponse("/vlastnici", status_code=302)
    return templates.TemplateResponse("partials/owner_address_info.html", {
        "request": request,
        "owner": owner,
        **_address_context(owner, prefix),
    })


@router.post("/{owner_id}/adresa/{prefix}/upravit")
async def owner_address_update(
    owner_id: int,
    prefix: str,
    request: Request,
    street: str = Form(""),
    district: str = Form(""),
    city: str = Form(""),
    zip: str = Form(""),
    country: str = Form(""),
    db: Session = Depends(get_db),
):
    if prefix not in ("perm", "corr"):
        return RedirectResponse(f"/vlastnici/{owner_id}", status_code=302)
    owner = db.query(Owner).get(owner_id)
    if not owner:
        return RedirectResponse("/vlastnici", status_code=302)

    setattr(owner, f"{prefix}_street", street or None)
    setattr(owner, f"{prefix}_district", district or None)
    setattr(owner, f"{prefix}_city", city or None)
    setattr(owner, f"{prefix}_zip", zip or None)
    setattr(owner, f"{prefix}_country", country or None)
    owner.updated_at = datetime.utcnow()
    db.commit()

    if request.headers.get("HX-Request"):
        return templates.TemplateResponse("partials/owner_address_info.html", {
            "request": request,
            "owner": owner,
            "saved": True,
            **_address_context(owner, prefix),
        })
    return RedirectResponse(f"/vlastnici/{owner_id}", status_code=302)


@router.post("/{owner_id}/upravit")
async def owner_update(
    owner_id: int,
    request: Request,
    email: str = Form(""),
    email_secondary: str = Form(""),
    phone: str = Form(""),
    phone_landline: str = Form(""),
    db: Session = Depends(get_db),
):
    owner = db.query(Owner).get(owner_id)
    if owner:
        owner.email = email if email else None
        owner.email_secondary = email_secondary if email_secondary else None
        owner.phone = phone if phone else None
        owner.phone_landline = phone_landline if phone_landline else None
        owner.updated_at = datetime.utcnow()
        db.commit()

    if request.headers.get("HX-Request"):
        return templates.TemplateResponse("partials/owner_contact_info.html", {
            "request": request,
            "owner": owner,
            "saved": True,
        })
    return RedirectResponse(f"/vlastnici/{owner_id}", status_code=302)


def _owner_units_context(owner, db):
    """Helper to build context for owner_units_section partial."""
    assigned_unit_ids = [ou.unit_id for ou in owner.units]
    if assigned_unit_ids:
        available_units = db.query(Unit).filter(
            Unit.id.notin_(assigned_unit_ids)
        ).order_by(Unit.unit_number).all()
    else:
        available_units = db.query(Unit).order_by(Unit.unit_number).all()
    return available_units


@router.post("/{owner_id}/jednotky/pridat")
async def owner_add_unit(
    owner_id: int,
    request: Request,
    unit_id: str = Form(...),
    ownership_type: str = Form(""),
    share: str = Form("1.0"),
    votes: str = Form("0"),
    db: Session = Depends(get_db),
):
    owner = db.query(Owner).options(
        joinedload(Owner.units).joinedload(OwnerUnit.unit)
    ).get(owner_id)
    if not owner:
        return RedirectResponse("/vlastnici", status_code=302)

    # Check for duplicate
    unit_id_int = int(unit_id)
    exists = db.query(OwnerUnit).filter_by(
        owner_id=owner_id, unit_id=unit_id_int
    ).first()
    if not exists:
        ou = OwnerUnit(
            owner_id=owner_id,
            unit_id=unit_id_int,
            ownership_type=ownership_type or None,
            share=float(share) if share else 1.0,
            votes=int(votes) if votes else 0,
        )
        db.add(ou)
        db.commit()
        # Refresh owner to get updated units
        db.refresh(owner)

    if request.headers.get("HX-Request"):
        available_units = _owner_units_context(owner, db)
        return templates.TemplateResponse("partials/owner_units_section.html", {
            "request": request,
            "owner": owner,
            "available_units": available_units,
        })
    return RedirectResponse(f"/vlastnici/{owner_id}", status_code=302)


@router.post("/{owner_id}/jednotky/{ou_id}/odebrat")
async def owner_remove_unit(
    owner_id: int,
    ou_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    ou = db.query(OwnerUnit).filter_by(id=ou_id, owner_id=owner_id).first()
    if ou:
        db.delete(ou)
        db.commit()

    owner = db.query(Owner).options(
        joinedload(Owner.units).joinedload(OwnerUnit.unit)
    ).get(owner_id)

    if request.headers.get("HX-Request"):
        available_units = _owner_units_context(owner, db)
        return templates.TemplateResponse("partials/owner_units_section.html", {
            "request": request,
            "owner": owner,
            "available_units": available_units,
        })
    return RedirectResponse(f"/vlastnici/{owner_id}", status_code=302)
