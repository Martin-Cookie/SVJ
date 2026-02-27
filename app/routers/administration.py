import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, Form, Query, Request, UploadFile, File
from fastapi.responses import FileResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import case
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import (
    SvjInfo, SvjAddress, BoardMember, CodeListItem,
    Unit, OwnerUnit, Owner, Proxy,
    Voting, VotingItem, Ballot, BallotVote,
    TaxSession, TaxDocument, TaxDistribution,
    SyncSession, SyncRecord,
    ShareCheckSession, ShareCheckRecord, ShareCheckColumnMapping,
    EmailLog, ImportLog,
)
from app.services.backup_service import (
    create_backup, restore_backup, restore_from_directory,
    log_restore, read_restore_log,
)
from app.services.data_export import (
    EXPORT_ORDER, _EXPORTS as EXPORT_CATEGORIES,
    export_category_xlsx, export_category_csv,
)
from app.main import run_post_restore_migrations

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

_CODE_LIST_CATEGORIES = {
    "space_type": {"label": "Typ prostoru", "model": Unit, "column": "space_type"},
    "section": {"label": "Sekce", "model": Unit, "column": "section"},
    "room_count": {"label": "Počet místností", "model": Unit, "column": "room_count"},
    "ownership_type": {"label": "Typ vlastnictví", "model": OwnerUnit, "column": "ownership_type"},
}

_CODE_LIST_ORDER = ["space_type", "section", "room_count", "ownership_type"]


def _get_code_list(db: Session, category: str):
    """Return code list items for a category, sorted by (order, value)."""
    return (
        db.query(CodeListItem)
        .filter_by(category=category)
        .order_by(CodeListItem.order, CodeListItem.value)
        .all()
    )


def _get_all_code_lists(db: Session) -> dict:
    """Return {category: [items]} for all code list categories."""
    items = (
        db.query(CodeListItem)
        .order_by(CodeListItem.category, CodeListItem.order, CodeListItem.value)
        .all()
    )
    result = {cat: [] for cat in _CODE_LIST_ORDER}
    for item in items:
        if item.category in result:
            result[item.category].append(item)
    return result


def _get_usage_count(db: Session, category: str, value: str) -> int:
    """Return number of records using a code list value."""
    meta = _CODE_LIST_CATEGORIES.get(category)
    if not meta:
        return 0
    model = meta["model"]
    col = getattr(model, meta["column"])
    q = db.query(model).filter(col == value)
    if model == OwnerUnit:
        q = q.filter(OwnerUnit.valid_to.is_(None))
    return q.count()


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
    info = db.query(SvjInfo).first()
    board_count = db.query(BoardMember).filter_by(group="board").count()
    control_count = db.query(BoardMember).filter_by(group="control").count()

    # Backup summary
    backup_count = 0
    last_backup = None
    if BACKUP_DIR.is_dir():
        backup_files = sorted(
            [f for f in BACKUP_DIR.iterdir() if f.suffix == ".zip"],
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )
        backup_count = len(backup_files)
        if backup_files:
            last_backup = datetime.fromtimestamp(backup_files[0].stat().st_mtime).strftime("%d.%m.%Y")

    # Code list total
    code_list_total = db.query(CodeListItem).count()

    return templates.TemplateResponse("administration/index.html", {
        "request": request,
        "active_nav": "administration",
        "info": info,
        "board_count": board_count,
        "control_count": control_count,
        "backup_count": backup_count,
        "last_backup": last_backup,
        "code_list_total": code_list_total,
        "code_list_categories": _CODE_LIST_CATEGORIES,
    })


@router.get("/svj-info")
async def svj_info_page(request: Request, db: Session = Depends(get_db)):
    info = db.query(SvjInfo).options(joinedload(SvjInfo.addresses)).first()
    if not info:
        info = SvjInfo()
        db.add(info)
        db.commit()
        db.refresh(info)

    board_members = db.query(BoardMember).filter_by(group="board").order_by(_ROLE_SORT, BoardMember.name).all()
    control_members = db.query(BoardMember).filter_by(group="control").order_by(_ROLE_SORT, BoardMember.name).all()

    return templates.TemplateResponse("administration/svj_info.html", {
        "request": request,
        "active_nav": "administration",
        "info": info,
        "board_members": board_members,
        "control_members": control_members,
    })


@router.get("/ciselniky")
async def code_lists_page(request: Request, db: Session = Depends(get_db)):
    code_lists = _get_all_code_lists(db)
    code_list_usage = {}
    for cat in _CODE_LIST_ORDER:
        for item in code_lists.get(cat, []):
            code_list_usage[item.id] = _get_usage_count(db, cat, item.value)

    return templates.TemplateResponse("administration/code_lists.html", {
        "request": request,
        "active_nav": "administration",
        "code_lists": code_lists,
        "code_list_usage": code_list_usage,
        "code_list_categories": _CODE_LIST_CATEGORIES,
        "code_list_order": _CODE_LIST_ORDER,
    })


@router.get("/zalohy")
async def backups_page(request: Request, chyba: str = Query(""), db: Session = Depends(get_db)):
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

    default_backup_name = f"svj_backup_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}"
    restore_log = read_restore_log(str(BACKUP_DIR))

    return templates.TemplateResponse("administration/backups.html", {
        "request": request,
        "active_nav": "administration",
        "backups": backups,
        "restore_log": restore_log,
        "default_backup_name": default_backup_name,
        "chyba": chyba,
    })


@router.get("/smazat")
async def purge_page(request: Request, db: Session = Depends(get_db)):
    purge_counts = _purge_counts(db)
    return templates.TemplateResponse("administration/purge.html", {
        "request": request,
        "active_nav": "administration",
        "purge_categories": _PURGE_CATEGORIES,
        "purge_order": _PURGE_ORDER,
        "purge_counts": purge_counts,
    })


@router.get("/export")
async def export_page(request: Request, db: Session = Depends(get_db)):
    purge_counts = _purge_counts(db)
    return templates.TemplateResponse("administration/export.html", {
        "request": request,
        "active_nav": "administration",
        "export_categories": EXPORT_CATEGORIES,
        "export_order": EXPORT_ORDER,
        "purge_categories": _PURGE_CATEGORIES,
        "purge_counts": purge_counts,
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
    return RedirectResponse("/sprava/svj-info", status_code=302)


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
    return RedirectResponse("/sprava/svj-info", status_code=302)


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
    return RedirectResponse("/sprava/svj-info", status_code=302)


@router.post("/adresa/{addr_id}/smazat")
async def delete_address(addr_id: int, db: Session = Depends(get_db)):
    addr = db.query(SvjAddress).get(addr_id)
    if addr:
        db.delete(addr)
        db.commit()
    return RedirectResponse("/sprava/svj-info", status_code=302)


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
    return RedirectResponse("/sprava/svj-info", status_code=302)


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
    return RedirectResponse("/sprava/svj-info", status_code=302)


@router.post("/clen/{member_id}/smazat")
async def delete_member(member_id: int, db: Session = Depends(get_db)):
    member = db.query(BoardMember).get(member_id)
    if member:
        db.delete(member)
        db.commit()
    return RedirectResponse("/sprava/svj-info", status_code=302)


# ---- Code list endpoints ----


@router.post("/ciselnik/pridat")
async def code_list_add(
    request: Request,
    category: str = Form(...),
    value: str = Form(...),
    db: Session = Depends(get_db),
):
    value = value.strip()
    if not value or category not in _CODE_LIST_CATEGORIES:
        return RedirectResponse("/sprava/ciselniky", status_code=302)

    # Check duplicate
    existing = db.query(CodeListItem).filter_by(category=category, value=value).first()
    if existing:
        return RedirectResponse("/sprava/ciselniky", status_code=302)

    max_order = db.query(CodeListItem).filter_by(category=category).count()
    item = CodeListItem(category=category, value=value, order=max_order)
    db.add(item)
    db.commit()
    return RedirectResponse("/sprava/ciselniky", status_code=302)


@router.post("/ciselnik/{item_id}/upravit")
async def code_list_edit(
    item_id: int,
    new_value: str = Form(...),
    db: Session = Depends(get_db),
):
    item = db.query(CodeListItem).get(item_id)
    if not item:
        return RedirectResponse("/sprava/ciselniky", status_code=302)

    # Only allow edit if unused
    usage = _get_usage_count(db, item.category, item.value)
    if usage > 0:
        return RedirectResponse("/sprava/ciselniky", status_code=302)

    new_value = new_value.strip()
    if not new_value:
        return RedirectResponse("/sprava/ciselniky", status_code=302)

    if new_value != item.value:
        # Check duplicate
        dup = db.query(CodeListItem).filter_by(
            category=item.category, value=new_value
        ).first()
        if dup:
            return RedirectResponse("/sprava/ciselniky", status_code=302)

        item.value = new_value

    db.commit()
    return RedirectResponse("/sprava/ciselniky", status_code=302)


@router.post("/ciselnik/{item_id}/smazat")
async def code_list_delete(
    item_id: int,
    db: Session = Depends(get_db),
):
    item = db.query(CodeListItem).get(item_id)
    if not item:
        return RedirectResponse("/sprava/ciselniky", status_code=302)

    # Only delete if unused
    usage = _get_usage_count(db, item.category, item.value)
    if usage == 0:
        db.delete(item)
        db.commit()
    return RedirectResponse("/sprava/ciselniky", status_code=302)


# ---- Backup endpoints ----


def _safety_backup() -> str:
    """Create a safety backup and return its filename."""
    zip_path = create_backup(str(DB_PATH), str(UPLOADS_DIR), str(GENERATED_DIR), str(BACKUP_DIR))
    return zip_path.name


@router.post("/zaloha/vytvorit")
async def backup_create(filename: str = Form(""), db: Session = Depends(get_db)):
    # Check if there is any data to backup
    total = sum(
        db.query(m).count()
        for m in (Owner, Unit, Voting, TaxSession, SyncSession, EmailLog, ImportLog, BoardMember)
    )
    if total == 0:
        return RedirectResponse("/sprava/zalohy?chyba=prazdna", status_code=302)

    name = filename.strip() or None
    create_backup(str(DB_PATH), str(UPLOADS_DIR), str(GENERATED_DIR), str(BACKUP_DIR), custom_name=name)
    return RedirectResponse("/sprava/zalohy", status_code=302)


@router.get("/zaloha/{filename}/stahnout")
async def backup_download(filename: str):
    file_path = BACKUP_DIR / filename
    if not file_path.is_file() or not filename.endswith(".zip"):
        return RedirectResponse("/sprava/zalohy", status_code=302)
    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type="application/octet-stream",
    )


@router.post("/zaloha/{filename}/smazat")
async def backup_delete(filename: str):
    file_path = BACKUP_DIR / filename
    if file_path.is_file() and filename.endswith(".zip"):
        file_path.unlink()
    return RedirectResponse("/sprava/zalohy", status_code=302)


@router.post("/zaloha/obnovit")
async def backup_restore(file: UploadFile = File(...)):
    # Save uploaded file to temp location
    temp_path = BACKUP_DIR / "upload_temp.zip"
    os.makedirs(BACKUP_DIR, exist_ok=True)
    with open(temp_path, "wb") as f:
        f.write(await file.read())

    # Track which backups exist before restore (to find the safety backup name)
    existing = set(p.name for p in BACKUP_DIR.glob("*.zip")) if BACKUP_DIR.is_dir() else set()

    try:
        restore_backup(
            str(temp_path), str(DB_PATH), str(UPLOADS_DIR),
            str(GENERATED_DIR), str(BACKUP_DIR),
        )
        # Find safety backup created by restore_backup
        new_backups = set(p.name for p in BACKUP_DIR.glob("*.zip")) - existing
        safety = next(iter(new_backups), "")
        log_restore(str(BACKUP_DIR), file.filename or "upload.zip", "ZIP soubor", safety_backup=safety)
    finally:
        if temp_path.is_file():
            temp_path.unlink()

    run_post_restore_migrations()
    return RedirectResponse("/sprava/zalohy", status_code=302)


@router.post("/zaloha/obnovit-adresar")
async def backup_restore_directory(dir_path: str = Form(...)):
    """Restore from an unzipped backup directory on local disk."""
    dir_path = dir_path.strip()
    if not dir_path or not Path(dir_path).is_dir():
        return RedirectResponse("/sprava/zalohy", status_code=302)

    existing = set(p.name for p in BACKUP_DIR.glob("*.zip")) if BACKUP_DIR.is_dir() else set()
    restore_from_directory(
        dir_path, str(DB_PATH), str(UPLOADS_DIR),
        str(GENERATED_DIR), str(BACKUP_DIR),
    )
    new_backups = set(p.name for p in BACKUP_DIR.glob("*.zip")) - existing
    safety = next(iter(new_backups), "")
    log_restore(str(BACKUP_DIR), dir_path, "Adresář", safety_backup=safety)
    run_post_restore_migrations()
    return RedirectResponse("/sprava/zalohy", status_code=302)


@router.post("/zaloha/obnovit-soubor")
async def backup_restore_db_file(file: UploadFile = File(...)):
    """Restore from an uploaded svj.db file (from an unzipped backup)."""
    if not file.filename or not file.filename.endswith(".db"):
        return RedirectResponse("/sprava/zalohy", status_code=302)

    safety = _safety_backup()

    # Overwrite database
    with open(str(DB_PATH), "wb") as f:
        f.write(await file.read())

    log_restore(str(BACKUP_DIR), file.filename or "svj.db", "DB soubor", safety_backup=safety)
    run_post_restore_migrations()
    return RedirectResponse("/sprava/zalohy", status_code=302)


@router.post("/zaloha/obnovit-slozku")
async def backup_restore_folder(files: List[UploadFile] = File(...)):
    """Restore from an uploaded backup folder (webkitdirectory).

    The browser sends all files from the selected folder. We look for svj.db
    and optionally uploads/ and generated/ subdirectories.
    """
    # Create a temp directory to receive the folder contents
    tmp = tempfile.mkdtemp(prefix="svj_restore_")
    folder_name = ""
    try:
        db_found = False
        for f in files:
            if not f.filename:
                continue
            # webkitRelativePath gives e.g. "folder_name/svj.db" or "folder_name/uploads/doc.pdf"
            # The first path component is the folder name — strip it
            parts = f.filename.replace("\\", "/").split("/")
            if len(parts) > 1:
                if not folder_name:
                    folder_name = parts[0]
                rel = "/".join(parts[1:])  # strip top-level folder name
            else:
                rel = parts[0]

            target = Path(tmp) / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            with open(str(target), "wb") as dst:
                dst.write(await f.read())

            if rel == "svj.db":
                db_found = True

        if not db_found:
            return RedirectResponse("/sprava/zalohy", status_code=302)

        safety = _safety_backup()

        # Restore database
        shutil.copy2(str(Path(tmp) / "svj.db"), str(DB_PATH))

        # Restore uploads if present
        src_uploads = Path(tmp) / "uploads"
        if src_uploads.is_dir():
            if UPLOADS_DIR.is_dir():
                shutil.rmtree(str(UPLOADS_DIR))
            shutil.copytree(str(src_uploads), str(UPLOADS_DIR))

        # Restore generated if present
        src_generated = Path(tmp) / "generated"
        if src_generated.is_dir():
            if GENERATED_DIR.is_dir():
                shutil.rmtree(str(GENERATED_DIR))
            shutil.copytree(str(src_generated), str(GENERATED_DIR))

        log_restore(str(BACKUP_DIR), folder_name or "složka", "Složka (Finder)", safety_backup=safety)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    run_post_restore_migrations()
    return RedirectResponse("/sprava/zalohy", status_code=302)


# ---- Export data ----


@router.get("/export/{category}/{fmt}")
async def export_data(category: str, fmt: str, db: Session = Depends(get_db)):
    """Download a data export in xlsx or csv format."""
    if category not in EXPORT_CATEGORIES or fmt not in ("xlsx", "csv"):
        return RedirectResponse("/sprava/export", status_code=302)

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
        return RedirectResponse("/sprava/export", status_code=302)

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
    "share_check": {
        "label": "Kontrola podílu",
        "description": "Kontroly podílů SČD — relace, záznamy, mapování sloupců",
        "models": [ShareCheckRecord, ShareCheckSession, ShareCheckColumnMapping],
    },
    "logs": {
        "label": "Logy",
        "description": "E-mailové logy, importní logy",
        "models": [EmailLog, ImportLog],
    },
    "administration": {
        "label": "Administrace SVJ",
        "description": "Informace o SVJ, adresy, členové výboru, číselníky",
        "models": [CodeListItem, SvjAddress, BoardMember, SvjInfo],
    },
    "backups": {
        "label": "Existující zálohy",
        "description": "ZIP soubory záloh v adresáři data/backups",
        "models": [],
    },
    "restore_log": {
        "label": "Historie obnovení",
        "description": "Záznam o provedených obnoveních ze záloh",
        "models": [],
    },
}

_PURGE_ORDER = ["owners", "votings", "tax", "sync", "share_check", "logs", "administration", "backups", "restore_log"]


def _purge_counts(db: Session) -> dict:
    """Return {category_key: total_row_count} for each purge category."""
    counts = {}
    for key in _PURGE_ORDER:
        cat = _PURGE_CATEGORIES[key]
        if key == "backups":
            counts[key] = len(list(BACKUP_DIR.glob("*.zip"))) if BACKUP_DIR.is_dir() else 0
        elif key == "restore_log":
            counts[key] = len(read_restore_log(str(BACKUP_DIR)))
        else:
            counts[key] = sum(db.query(m).count() for m in cat["models"])
    return counts


@router.post("/smazat-data")
async def purge_data(request: Request, db: Session = Depends(get_db)):
    """Delete selected data categories after DELETE confirmation."""
    form_data = await request.form()
    confirmation = form_data.get("confirmation", "").strip()
    categories = form_data.getlist("categories")

    if confirmation != "DELETE" or not categories:
        return RedirectResponse("/sprava/smazat", status_code=302)

    # Delete in safe order — children before parents
    for key in _PURGE_ORDER:
        if key not in categories:
            continue
        cat = _PURGE_CATEGORIES.get(key)
        if not cat:
            continue
        for model in cat["models"]:
            db.query(model).delete()

    # Cascade: owners → sync (sync records reference owners, useless without them)
    if "owners" in categories and "sync" not in categories:
        for model in _PURGE_CATEGORIES["sync"]["models"]:
            db.query(model).delete()

    # Clean uploaded / generated files if owners or votings are wiped
    if "owners" in categories or "votings" in categories:
        for dirname in (UPLOADS_DIR, GENERATED_DIR):
            if dirname.is_dir():
                shutil.rmtree(dirname, ignore_errors=True)
                dirname.mkdir(parents=True, exist_ok=True)

    # Delete backup ZIP files
    if "backups" in categories and BACKUP_DIR.is_dir():
        for f in BACKUP_DIR.glob("*.zip"):
            f.unlink(missing_ok=True)

    # Delete restore log
    if "restore_log" in categories:
        log_path = BACKUP_DIR / "restore_log.json"
        if log_path.is_file():
            log_path.unlink()

    db.commit()
    return RedirectResponse("/sprava", status_code=302)


# ---- Bulk edit endpoints ----


@router.get("/hromadne-upravy")
async def bulk_edit_page(request: Request, db: Session = Depends(get_db)):
    # Compute stats for each field
    field_stats = {}
    for key, info in _BULK_FIELDS.items():
        model = Unit if info["model"] == "unit" else OwnerUnit
        col = getattr(model, info["column"])
        base = db.query(model)
        if model == OwnerUnit:
            base = base.filter(OwnerUnit.valid_to.is_(None))
        total_count = base.count()
        unique_count = db.query(_sa_func.count(_sa_func.distinct(col))).select_from(model)
        if model == OwnerUnit:
            unique_count = unique_count.filter(OwnerUnit.valid_to.is_(None))
        unique_count = unique_count.filter(col.isnot(None)).scalar() or 0
        field_stats[key] = {
            "unique_count": unique_count,
            "total_count": total_count,
            "model_label": "jednotek" if info["model"] == "unit" else "vazeb",
        }

    return templates.TemplateResponse("administration/bulk_edit.html", {
        "request": request,
        "active_nav": "administration",
        "fields": _BULK_FIELDS,
        "field_stats": field_stats,
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

    base = db.query(col, _sa_func.count().label("cnt"))
    if model == OwnerUnit:
        base = base.filter(OwnerUnit.valid_to.is_(None))
    rows = base.group_by(col).order_by(_sa_func.count().desc()).all()

    values = [{"value": r[0], "count": r[1]} for r in rows]

    # Collect all existing non-null values for datalist suggestions
    suggestions = sorted(set(
        str(r[0]) for r in rows if r[0] is not None
    ))

    # Merge code list values into suggestions
    if pole in _CODE_LIST_CATEGORIES:
        cl_values = [
            item.value for item in _get_code_list(db, pole)
        ]
        suggestions = sorted(set(suggestions) | set(cl_values))

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

    back_url = f"/sprava/hromadne-upravy?pole={pole}&hodnota={hodnota}"

    if model == Unit:
        q = db.query(Unit).options(joinedload(Unit.owners).joinedload(OwnerUnit.owner))
        if is_null:
            q = q.filter(col.is_(None))
        else:
            q = q.filter(col == hodnota)
        records = q.order_by(Unit.unit_number).all()
        return templates.TemplateResponse("administration/bulk_edit_records.html", {
            "request": request, "records": records, "model_type": "unit",
            "back_url": back_url,
        })
    else:
        q = (
            db.query(OwnerUnit)
            .options(joinedload(OwnerUnit.owner), joinedload(OwnerUnit.unit))
            .filter(OwnerUnit.valid_to.is_(None))
        )
        if is_null:
            q = q.filter(col.is_(None))
        else:
            q = q.filter(col == hodnota)
        records = q.order_by(OwnerUnit.unit_id).all()
        return templates.TemplateResponse("administration/bulk_edit_records.html", {
            "request": request, "records": records, "model_type": "owner_unit",
            "back_url": back_url,
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

    # Recalculate votes when share changes
    if pole == "share":
        from app.services.owner_exchange import recalculate_unit_votes
        affected_ous = q.all()
        seen_units = set()
        for ou in affected_ous:
            if ou.unit_id not in seen_units:
                seen_units.add(ou.unit_id)
                unit = db.query(Unit).get(ou.unit_id)
                if unit:
                    recalculate_unit_votes(unit, db)

    db.commit()

    return RedirectResponse(
        f"/sprava/hromadne-upravy?pole={pole}", status_code=302
    )
