import os
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request, UploadFile, File
from fastapi.responses import FileResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import case
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import (
    SvjInfo, SvjAddress, BoardMember, Unit, OwnerUnit, Owner, Proxy,
    Voting, VotingItem, Ballot, BallotVote,
    TaxSession, TaxDocument, TaxDistribution,
    SyncSession, SyncRecord,
    EmailLog, ImportLog,
)
from app.services.backup_service import create_backup, restore_backup
from app.services.data_export import (
    EXPORT_ORDER, _EXPORTS as EXPORT_CATEGORIES,
    export_category_xlsx, export_category_csv,
)

# Field mapping for bulk edit
_BULK_FIELDS = {
    "space_type": {"label": "Typ prostoru", "model": "unit", "column": "space_type"},
    "section": {"label": "Sekce", "model": "unit", "column": "section"},
    "room_count": {"label": "Počet místností", "model": "unit", "column": "room_count"},
    "ownership_type": {"label": "Vlastnictví druh", "model": "owner_unit", "column": "ownership_type"},
    "share": {"label": "Vlastnictví/Podíl", "model": "owner_unit", "column": "share"},
    "address": {"label": "Adresa", "model": "unit", "column": "address"},
    "orientation_number": {"label": "Orientační číslo", "model": "unit", "column": "orientation_number"},
}

DATA_DIR = Path("data")
DB_PATH = DATA_DIR / "svj.db"
UPLOADS_DIR = DATA_DIR / "uploads"
GENERATED_DIR = DATA_DIR / "generated"
BACKUP_DIR = DATA_DIR / "backups"

# Sort priority: Předseda/Předsedkyně first, then Místopředseda, then others
# Use func.lower to handle case variations (člen vs Člen)
from sqlalchemy import func as _sa_func
_role_lower = _sa_func.lower(BoardMember.role)
_ROLE_SORT = case(
    (_role_lower.like("předseda%"), 0),
    (_role_lower.like("předsedkyně%"), 0),
    (_role_lower.like("místopředseda%"), 1),
    (_role_lower.like("místopředsedkyně%"), 1),
    else_=2,
)

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _get_or_create_svj_info(db: Session) -> SvjInfo:
    info = db.query(SvjInfo).first()
    if not info:
        info = SvjInfo()
        db.add(info)
        db.flush()
    return info


@router.get("/")
async def administration_page(request: Request, db: Session = Depends(get_db)):
    info = db.query(SvjInfo).options(joinedload(SvjInfo.addresses)).first()
    if not info:
        info = SvjInfo()
        db.add(info)
        db.commit()
        db.refresh(info)

    board_members = db.query(BoardMember).filter_by(group="board").order_by(_ROLE_SORT, BoardMember.name).all()
    control_members = db.query(BoardMember).filter_by(group="control").order_by(_ROLE_SORT, BoardMember.name).all()

    # Backup files list
    backups = []
    if BACKUP_DIR.is_dir():
        for f in sorted(BACKUP_DIR.iterdir(), reverse=True):
            if f.suffix == ".zip":
                stat = f.stat()
                backups.append({
                    "filename": f.name,
                    "size": stat.st_size,
                    "created": datetime.fromtimestamp(stat.st_mtime),
                })

    purge_counts = _purge_counts(db)

    return templates.TemplateResponse("administration/index.html", {
        "request": request,
        "active_nav": "administration",
        "info": info,
        "board_members": board_members,
        "control_members": control_members,
        "backups": backups,
        "purge_categories": _PURGE_CATEGORIES,
        "purge_order": _PURGE_ORDER,
        "purge_counts": purge_counts,
        "export_categories": EXPORT_CATEGORIES,
        "export_order": EXPORT_ORDER,
    })


@router.post("/info")
async def update_svj_info(
    request: Request,
    name: str = Form(""),
    building_type: str = Form(""),
    total_shares: str = Form(""),
    db: Session = Depends(get_db),
):
    info = _get_or_create_svj_info(db)
    info.name = name.strip() or None
    info.building_type = building_type.strip() or None
    info.total_shares = int(total_shares) if total_shares.strip() else None
    info.updated_at = datetime.utcnow()
    db.commit()
    return RedirectResponse("/sprava", status_code=302)


@router.post("/adresa/pridat")
async def add_address(
    request: Request,
    address: str = Form(...),
    db: Session = Depends(get_db),
):
    info = _get_or_create_svj_info(db)
    max_order = db.query(SvjAddress).filter_by(svj_info_id=info.id).count()
    addr = SvjAddress(
        svj_info_id=info.id,
        address=address.strip(),
        order=max_order,
    )
    db.add(addr)
    db.commit()
    return RedirectResponse("/sprava", status_code=302)


@router.post("/adresa/{addr_id}/upravit")
async def edit_address(
    addr_id: int,
    address: str = Form(...),
    db: Session = Depends(get_db),
):
    addr = db.query(SvjAddress).get(addr_id)
    if addr:
        addr.address = address.strip()
        db.commit()
    return RedirectResponse("/sprava", status_code=302)


@router.post("/adresa/{addr_id}/smazat")
async def delete_address(addr_id: int, db: Session = Depends(get_db)):
    addr = db.query(SvjAddress).get(addr_id)
    if addr:
        db.delete(addr)
        db.commit()
    return RedirectResponse("/sprava", status_code=302)


@router.post("/clen/pridat")
async def add_member(
    request: Request,
    name: str = Form(...),
    role: str = Form(""),
    email: str = Form(""),
    phone: str = Form(""),
    group: str = Form("board"),
    db: Session = Depends(get_db),
):
    max_order = db.query(BoardMember).filter_by(group=group).count()
    member = BoardMember(
        name=name.strip(),
        role=role.strip() or None,
        email=email.strip() or None,
        phone=phone.strip() or None,
        group=group,
        order=max_order,
    )
    db.add(member)
    db.commit()
    return RedirectResponse("/sprava", status_code=302)


@router.post("/clen/{member_id}/upravit")
async def edit_member(
    member_id: int,
    name: str = Form(...),
    role: str = Form(""),
    email: str = Form(""),
    phone: str = Form(""),
    db: Session = Depends(get_db),
):
    member = db.query(BoardMember).get(member_id)
    if member:
        member.name = name.strip()
        member.role = role.strip() or None
        member.email = email.strip() or None
        member.phone = phone.strip() or None
        db.commit()
    return RedirectResponse("/sprava", status_code=302)


@router.post("/clen/{member_id}/smazat")
async def delete_member(member_id: int, db: Session = Depends(get_db)):
    member = db.query(BoardMember).get(member_id)
    if member:
        db.delete(member)
        db.commit()
    return RedirectResponse("/sprava", status_code=302)


# ---- Backup endpoints ----


@router.post("/zaloha/vytvorit")
async def backup_create():
    create_backup(str(DB_PATH), str(UPLOADS_DIR), str(GENERATED_DIR), str(BACKUP_DIR))
    return RedirectResponse("/sprava", status_code=302)


@router.get("/zaloha/{filename}/stahnout")
async def backup_download(filename: str):
    file_path = BACKUP_DIR / filename
    if not file_path.is_file() or not filename.endswith(".zip"):
        return RedirectResponse("/sprava", status_code=302)
    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type="application/zip",
    )


@router.post("/zaloha/{filename}/smazat")
async def backup_delete(filename: str):
    file_path = BACKUP_DIR / filename
    if file_path.is_file() and filename.endswith(".zip"):
        file_path.unlink()
    return RedirectResponse("/sprava", status_code=302)


@router.post("/zaloha/obnovit")
async def backup_restore(file: UploadFile = File(...)):
    # Save uploaded file to temp location
    temp_path = BACKUP_DIR / "upload_temp.zip"
    os.makedirs(BACKUP_DIR, exist_ok=True)
    with open(temp_path, "wb") as f:
        f.write(await file.read())

    try:
        restore_backup(
            str(temp_path), str(DB_PATH), str(UPLOADS_DIR),
            str(GENERATED_DIR), str(BACKUP_DIR),
        )
    finally:
        if temp_path.is_file():
            temp_path.unlink()

    return RedirectResponse("/sprava", status_code=302)


# ---- Export data ----


@router.get("/export/{category}/{fmt}")
async def export_data(category: str, fmt: str, db: Session = Depends(get_db)):
    """Download a data export in xlsx or csv format."""
    if category not in EXPORT_CATEGORIES or fmt not in ("xlsx", "csv"):
        return RedirectResponse("/sprava", status_code=302)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{category}_{timestamp}.{fmt}"

    if fmt == "xlsx":
        content = export_category_xlsx(db, category)
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        content = export_category_csv(db, category)
        media = "text/csv; charset=utf-8"

    return Response(
        content=content,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/export/hromadny")
async def export_bulk(request: Request, db: Session = Depends(get_db)):
    """Download a ZIP with exports for selected categories."""
    import io
    import zipfile

    form_data = await request.form()
    categories = form_data.getlist("categories")
    fmt = form_data.get("fmt", "xlsx")
    if fmt not in ("xlsx", "csv"):
        fmt = "xlsx"

    categories = [c for c in categories if c in EXPORT_CATEGORIES]
    if not categories:
        return RedirectResponse("/sprava", status_code=302)

    # Single category — download directly
    if len(categories) == 1:
        cat = categories[0]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{cat}_{timestamp}.{fmt}"
        if fmt == "xlsx":
            content = export_category_xlsx(db, cat)
            media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        else:
            content = export_category_csv(db, cat)
            media = "text/csv; charset=utf-8"
        return Response(
            content=content, media_type=media,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    # Multiple categories — pack into ZIP
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for cat in categories:
            if fmt == "xlsx":
                data = export_category_xlsx(db, cat)
            else:
                data = export_category_csv(db, cat)
            zf.writestr(f"{cat}.{fmt}", data)

    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="export_{timestamp}.zip"'},
    )


# ---- Purge data ----

# Categories available for deletion, in display order.
# Each value lists the models to delete (order matters for FK constraints).
_PURGE_CATEGORIES = {
    "owners": {
        "label": "Vlastníci a jednotky",
        "description": "Vlastníci, jednotky, vazby vlastník-jednotka, plné moci",
        "models": [Proxy, OwnerUnit, Owner, Unit],
    },
    "votings": {
        "label": "Hlasování",
        "description": "Hlasování, body hlasování, hlasovací lístky, hlasy",
        "models": [BallotVote, Ballot, VotingItem, Voting],
    },
    "tax": {
        "label": "Daňové podklady",
        "description": "Daňové relace, dokumenty, distribuce",
        "models": [TaxDistribution, TaxDocument, TaxSession],
    },
    "sync": {
        "label": "Synchronizace",
        "description": "Synchronizační relace a záznamy",
        "models": [SyncRecord, SyncSession],
    },
    "logs": {
        "label": "Logy",
        "description": "E-mailové logy, importní logy",
        "models": [EmailLog, ImportLog],
    },
    "administration": {
        "label": "Administrace SVJ",
        "description": "Informace o SVJ, adresy, členové výboru",
        "models": [SvjAddress, BoardMember, SvjInfo],
    },
}

_PURGE_ORDER = ["owners", "votings", "tax", "sync", "logs", "administration"]


def _purge_counts(db: Session) -> dict:
    """Return {category_key: total_row_count} for each purge category."""
    counts = {}
    for key in _PURGE_ORDER:
        cat = _PURGE_CATEGORIES[key]
        total = sum(db.query(m).count() for m in cat["models"])
        counts[key] = total
    return counts


@router.post("/smazat-data")
async def purge_data(request: Request, db: Session = Depends(get_db)):
    """Delete selected data categories after DELETE confirmation."""
    form_data = await request.form()
    confirmation = form_data.get("confirmation", "").strip()
    categories = form_data.getlist("categories")

    if confirmation != "DELETE" or not categories:
        return RedirectResponse("/sprava", status_code=302)

    # Delete in safe order — children before parents
    for key in _PURGE_ORDER:
        if key not in categories:
            continue
        cat = _PURGE_CATEGORIES.get(key)
        if not cat:
            continue
        for model in cat["models"]:
            db.query(model).delete()

    # Clean uploaded / generated files if owners or votings are wiped
    if "owners" in categories or "votings" in categories:
        for dirname in (UPLOADS_DIR, GENERATED_DIR):
            if dirname.is_dir():
                import shutil
                shutil.rmtree(dirname, ignore_errors=True)
                dirname.mkdir(parents=True, exist_ok=True)

    db.commit()
    return RedirectResponse("/sprava", status_code=302)


# ---- Bulk edit endpoints ----


@router.get("/hromadne-upravy")
async def bulk_edit_page(request: Request):
    return templates.TemplateResponse("administration/bulk_edit.html", {
        "request": request,
        "active_nav": "administration",
        "fields": _BULK_FIELDS,
    })


@router.get("/hromadne-upravy/hodnoty")
async def bulk_edit_values(request: Request, pole: str, db: Session = Depends(get_db)):
    field_info = _BULK_FIELDS.get(pole)
    if not field_info:
        return templates.TemplateResponse("administration/bulk_edit_values.html", {
            "request": request, "values": [], "field_key": pole, "field_label": "",
        })

    model = Unit if field_info["model"] == "unit" else OwnerUnit
    col = getattr(model, field_info["column"])

    rows = (
        db.query(col, _sa_func.count().label("cnt"))
        .group_by(col)
        .order_by(_sa_func.count().desc())
        .all()
    )

    values = [{"value": r[0], "count": r[1]} for r in rows]

    # Collect all existing non-null values for datalist suggestions
    suggestions = sorted(set(
        str(r[0]) for r in rows if r[0] is not None
    ))

    return templates.TemplateResponse("administration/bulk_edit_values.html", {
        "request": request,
        "values": values,
        "field_key": pole,
        "field_label": field_info["label"],
        "suggestions": suggestions,
    })


@router.get("/hromadne-upravy/zaznamy")
async def bulk_edit_records(
    request: Request, pole: str, hodnota: str = "", db: Session = Depends(get_db),
):
    field_info = _BULK_FIELDS.get(pole)
    if not field_info:
        return templates.TemplateResponse("administration/bulk_edit_records.html", {
            "request": request, "records": [], "model_type": "",
        })

    is_null = hodnota == "__null__"
    model = Unit if field_info["model"] == "unit" else OwnerUnit
    col = getattr(model, field_info["column"])

    if model == Unit:
        q = db.query(Unit).options(joinedload(Unit.owners).joinedload(OwnerUnit.owner))
        if is_null:
            q = q.filter(col.is_(None))
        else:
            q = q.filter(col == hodnota)
        records = q.order_by(Unit.unit_number).all()
        return templates.TemplateResponse("administration/bulk_edit_records.html", {
            "request": request, "records": records, "model_type": "unit",
        })
    else:
        q = (
            db.query(OwnerUnit)
            .options(joinedload(OwnerUnit.owner), joinedload(OwnerUnit.unit))
        )
        if is_null:
            q = q.filter(col.is_(None))
        else:
            q = q.filter(col == hodnota)
        records = q.order_by(OwnerUnit.unit_id).all()
        return templates.TemplateResponse("administration/bulk_edit_records.html", {
            "request": request, "records": records, "model_type": "owner_unit",
        })


@router.post("/hromadne-upravy/opravit")
async def bulk_edit_apply(
    request: Request,
    db: Session = Depends(get_db),
):
    form_data = await request.form()
    pole = form_data.get("pole", "")
    old_value = form_data.get("old_value", "")
    new_value = form_data.get("new_value", "")
    is_null = form_data.get("is_null", "")
    ids = form_data.getlist("ids")

    field_info = _BULK_FIELDS.get(pole)
    if not field_info:
        return RedirectResponse("/sprava/hromadne-upravy", status_code=302)

    model = Unit if field_info["model"] == "unit" else OwnerUnit
    col = getattr(model, field_info["column"])

    # Build filter
    if ids:
        # Filter by selected record IDs
        record_ids = [int(i) for i in ids]
        q = db.query(model).filter(model.id.in_(record_ids))
    elif is_null == "1":
        q = db.query(model).filter(col.is_(None))
    else:
        # Convert old_value for numeric columns
        filter_value = old_value
        if pole == "orientation_number":
            try:
                filter_value = int(old_value)
            except ValueError:
                pass
        elif pole == "share":
            try:
                filter_value = float(old_value)
            except ValueError:
                pass
        q = db.query(model).filter(col == filter_value)

    # Set new value (empty string → None)
    final_value = new_value.strip() if new_value.strip() else None

    # Type conversions for numeric fields
    if pole == "orientation_number" and final_value is not None:
        try:
            final_value = int(final_value)
        except ValueError:
            return RedirectResponse(
                f"/sprava/hromadne-upravy?pole={pole}", status_code=302
            )
    if pole == "share" and final_value is not None:
        try:
            final_value = float(final_value)
        except ValueError:
            return RedirectResponse(
                f"/sprava/hromadne-upravy?pole={pole}", status_code=302
            )

    q.update({col: final_value}, synchronize_session="fetch")
    db.commit()

    return RedirectResponse(
        f"/sprava/hromadne-upravy?pole={pole}", status_code=302
    )
