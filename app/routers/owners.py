import shutil
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.database import get_db
from app.models import ImportLog, Owner, OwnerType, Unit
from app.services.excel_import import import_owners_from_excel, preview_owners_from_excel

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/")
async def owner_list(
    request: Request,
    q: str = Query("", alias="q"),
    owner_type: str = Query("", alias="typ"),
    db: Session = Depends(get_db),
):
    query = db.query(Owner).filter_by(is_active=True).options(
        joinedload(Owner.units)
    )
    if q:
        query = query.filter(
            Owner.name_with_titles.ilike(f"%{q}%")
            | Owner.name_normalized.ilike(f"%{q}%")
            | Owner.first_name.ilike(f"%{q}%")
            | Owner.last_name.ilike(f"%{q}%")
            | Owner.email.ilike(f"%{q}%")
        )
    if owner_type:
        query = query.filter(Owner.owner_type == owner_type)

    owners = query.order_by(Owner.name_normalized).all()

    # Check if HTMX request for search
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse("partials/owner_table_body.html", {
            "request": request,
            "owners": owners,
        })

    return templates.TemplateResponse("owners/list.html", {
        "request": request,
        "active_nav": "owners",
        "owners": owners,
        "q": q,
        "owner_type": owner_type,
        "owner_types": OwnerType,
    })


@router.get("/import")
async def import_page(request: Request):
    return templates.TemplateResponse("owners/import.html", {
        "request": request,
        "active_nav": "import",
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


@router.get("/{owner_id}")
async def owner_detail(owner_id: int, request: Request, db: Session = Depends(get_db)):
    owner = db.query(Owner).options(joinedload(Owner.units)).get(owner_id)
    if not owner:
        return RedirectResponse("/vlastnici", status_code=302)
    return templates.TemplateResponse("owners/detail.html", {
        "request": request,
        "active_nav": "owners",
        "owner": owner,
    })


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
        return templates.TemplateResponse("partials/owner_contact_form.html", {
            "request": request,
            "owner": owner,
            "saved": True,
        })
    return RedirectResponse(f"/vlastnici/{owner_id}", status_code=302)
