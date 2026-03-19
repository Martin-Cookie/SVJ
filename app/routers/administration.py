import io
import logging
import os
import re
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, Form, Query, Request, UploadFile, File
from fastapi.responses import FileResponse, RedirectResponse, Response
from sqlalchemy import case, func as sa_func
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.database import SessionLocal, engine, get_db
from app.models import (
    SvjInfo, SvjAddress, BoardMember, CodeListItem, EmailTemplate,
    Unit, OwnerUnit, Owner, Proxy,
    Voting, VotingItem, Ballot, BallotVote,
    TaxSession, TaxDocument, TaxDistribution,
    SyncSession, SyncRecord,
    ShareCheckSession, ShareCheckRecord, ShareCheckColumnMapping,
    EmailLog, ImportLog,
    ActivityLog, ActivityAction, log_activity,
)
from app.services.backup_service import (
    _rollback_from_safety,
    create_backup, restore_backup, restore_from_directory,
    log_restore, read_restore_log,
    acquire_restore_lock, release_restore_lock,
    get_backups_total_size,
)
from app.services.code_list_service import (
    CODE_LIST_CATEGORIES, CODE_LIST_ORDER, get_all_code_lists,
)
from app.services.data_export import (
    EXPORT_ORDER, _EXPORTS as EXPORT_CATEGORIES,
    export_category_xlsx, export_category_csv,
)
from app.services.owner_exchange import recalculate_unit_votes
from app.services.owner_service import find_duplicate_groups, merge_owners

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

def _get_code_list(db: Session, category: str):
    """Return code list items for a category, sorted by (order, value)."""
    return (
        db.query(CodeListItem)
        .filter_by(category=category)
        .order_by(CodeListItem.order, CodeListItem.value)
        .all()
    )


def _get_usage_count(db: Session, category: str, value: str) -> int:
    """Return number of records using a code list value."""
    meta = CODE_LIST_CATEGORIES.get(category)
    if not meta:
        return 0
    model = meta["model"]
    col = getattr(model, meta["column"])
    q = db.query(model).filter(col == value)
    if model == OwnerUnit:
        q = q.filter(OwnerUnit.valid_to.is_(None))
    return q.count()


DB_PATH = settings.database_path
UPLOADS_DIR = settings.upload_dir
GENERATED_DIR = settings.generated_dir
BACKUP_DIR = settings.backup_dir

# Sort priority: Předseda/Předsedkyně first, then Místopředseda, then others
# Use func.lower to handle case variations (člen vs Člen)
_role_lower = sa_func.lower(BoardMember.role)
_ROLE_SORT = case(
    (_role_lower.like("předseda%"), 0),
    (_role_lower.like("předsedkyně%"), 0),
    (_role_lower.like("místopředseda%"), 1),
    (_role_lower.like("místopředsedkyně%"), 1),
    else_=2,
)

from app.utils import UPLOAD_LIMITS, is_safe_path, is_valid_email, templates, validate_upload

router = APIRouter()


def _get_or_create_svj_info(db: Session) -> SvjInfo:
    info = db.query(SvjInfo).first()
    if not info:
        info = SvjInfo()
        db.add(info)
        db.flush()
    return info


@router.get("/")
async def administration_page(request: Request, db: Session = Depends(get_db)):
    """Hlavní stránka administrace s přehledem sekcí."""
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

    # Duplicate owner groups count
    duplicate_count = (
        db.query(sa_func.count())
        .select_from(
            db.query(Owner.name_normalized)
            .filter(Owner.is_active == True, Owner.name_normalized != "")
            .group_by(Owner.name_normalized)
            .having(sa_func.count(Owner.id) > 1)
            .subquery()
        )
        .scalar()
    ) or 0

    return templates.TemplateResponse("administration/index.html", {
        "request": request,
        "active_nav": "administration",
        "info": info,
        "board_count": board_count,
        "control_count": control_count,
        "backup_count": backup_count,
        "last_backup": last_backup,
        "code_list_total": code_list_total,
        "code_list_categories": CODE_LIST_CATEGORIES,
        "duplicate_count": duplicate_count,
    })


@router.get("/svj-info")
async def svj_info_page(request: Request, db: Session = Depends(get_db)):
    """Stránka informací o SVJ s adresami a členy výboru."""
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
    """Správa číselníků a emailových šablon."""
    code_lists = get_all_code_lists(db)
    code_list_usage = {}
    for cat in CODE_LIST_ORDER:
        for item in code_lists.get(cat, []):
            code_list_usage[item.id] = _get_usage_count(db, cat, item.value)

    email_templates = (
        db.query(EmailTemplate)
        .order_by(EmailTemplate.order, EmailTemplate.name)
        .all()
    )

    return templates.TemplateResponse("administration/code_lists.html", {
        "request": request,
        "active_nav": "administration",
        "code_lists": code_lists,
        "code_list_usage": code_list_usage,
        "code_list_categories": CODE_LIST_CATEGORIES,
        "code_list_order": CODE_LIST_ORDER,
        "email_templates": email_templates,
    })


@router.get("/zalohy")
async def backups_page(request: Request, chyba: str = Query(""), zprava: str = Query(""), db: Session = Depends(get_db)):
    """Stránka správy záloh s historií obnovení."""
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
    backups_total_size = get_backups_total_size(str(BACKUP_DIR))

    return templates.TemplateResponse("administration/backups.html", {
        "request": request,
        "active_nav": "administration",
        "backups": backups,
        "restore_log": restore_log,
        "default_backup_name": default_backup_name,
        "backups_total_size": backups_total_size,
        "chyba": chyba,
        "zprava": zprava,
    })


@router.get("/smazat")
async def purge_page(request: Request, db: Session = Depends(get_db)):
    """Stránka pro hromadné mazání dat podle kategorií."""
    purge_counts = _purge_counts(db)
    return templates.TemplateResponse("administration/purge.html", {
        "request": request,
        "active_nav": "administration",
        "purge_categories": _PURGE_CATEGORIES,
        "purge_order": _PURGE_ORDER,
        "purge_groups": _PURGE_GROUPS,
        "purge_counts": purge_counts,
    })


@router.get("/export")
async def export_page(request: Request, db: Session = Depends(get_db)):
    """Stránka pro export dat podle kategorií."""
    purge_counts = _purge_counts(db)
    return templates.TemplateResponse("administration/export.html", {
        "request": request,
        "active_nav": "administration",
        "export_categories": EXPORT_CATEGORIES,
        "export_order": EXPORT_ORDER,
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
    """Uložení základních informací o SVJ."""
    info = _get_or_create_svj_info(db)
    info.name = name.strip() or None
    info.building_type = building_type.strip() or None
    try:
        total_shares_int = int(total_shares) if total_shares.strip() else None
    except (ValueError, TypeError):
        total_shares_int = None
    if total_shares_int is not None and (total_shares_int < 1 or total_shares_int > 99999999):
        total_shares_int = None
    info.total_shares = total_shares_int
    info.updated_at = datetime.utcnow()
    db.commit()
    return RedirectResponse("/sprava/svj-info", status_code=302)


@router.post("/adresa/pridat")
async def add_address(
    request: Request,
    address: str = Form(...),
    db: Session = Depends(get_db),
):
    """Přidání nové adresy SVJ."""
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
    """Úprava existující adresy SVJ."""
    addr = db.query(SvjAddress).get(addr_id)
    if addr:
        addr.address = address.strip()
        db.commit()
    return RedirectResponse("/sprava/svj-info", status_code=302)


@router.post("/adresa/{addr_id}/smazat")
async def delete_address(addr_id: int, db: Session = Depends(get_db)):
    """Smazání adresy SVJ."""
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
    """Přidání nového člena výboru nebo kontrolního orgánu."""
    max_order = db.query(BoardMember).filter_by(group=group).count()
    member = BoardMember(
        name=name.strip(),
        role=role.strip() or None,
        email=(email.strip() if email.strip() and is_valid_email(email.strip()) else None),
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
    """Úprava údajů člena výboru."""
    member = db.query(BoardMember).get(member_id)
    if member:
        member.name = name.strip()
        member.role = role.strip() or None
        member.email = (email.strip() if email.strip() and is_valid_email(email.strip()) else None)
        member.phone = phone.strip() or None
        db.commit()
    return RedirectResponse("/sprava/svj-info", status_code=302)


@router.post("/clen/{member_id}/smazat")
async def delete_member(member_id: int, db: Session = Depends(get_db)):
    """Smazání člena výboru."""
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
    """Přidání nové hodnoty do číselníku."""
    value = value.strip()
    if not value or category not in CODE_LIST_CATEGORIES:
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
    """Úprava hodnoty v číselníku."""
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
    """Smazání nepoužívané hodnoty z číselníku."""
    item = db.query(CodeListItem).get(item_id)
    if not item:
        return RedirectResponse("/sprava/ciselniky", status_code=302)

    # Only delete if unused
    usage = _get_usage_count(db, item.category, item.value)
    if usage == 0:
        db.delete(item)
        db.commit()
    return RedirectResponse("/sprava/ciselniky", status_code=302)


# ---- Email template endpoints ----


@router.post("/sablona/pridat")
async def email_template_add(
    request: Request,
    name: str = Form(...),
    subject_template: str = Form(...),
    body_template: str = Form(""),
    db: Session = Depends(get_db),
):
    """Přidání nové emailové šablony."""
    name = name.strip()
    subject_template = subject_template.strip()
    if not name or not subject_template:
        return RedirectResponse("/sprava/ciselniky", status_code=302)

    existing = db.query(EmailTemplate).filter_by(name=name).first()
    if existing:
        return RedirectResponse("/sprava/ciselniky", status_code=302)

    max_order = db.query(EmailTemplate).count()
    tpl = EmailTemplate(
        name=name,
        subject_template=subject_template,
        body_template=body_template,
        order=max_order,
    )
    db.add(tpl)
    db.commit()
    return RedirectResponse("/sprava/ciselniky", status_code=302)


@router.post("/sablona/{tpl_id}/upravit")
async def email_template_edit(
    tpl_id: int,
    name: str = Form(...),
    subject_template: str = Form(...),
    body_template: str = Form(""),
    db: Session = Depends(get_db),
):
    """Úprava existující emailové šablony."""
    tpl = db.query(EmailTemplate).get(tpl_id)
    if not tpl:
        return RedirectResponse("/sprava/ciselniky", status_code=302)

    name = name.strip()
    subject_template = subject_template.strip()
    if not name or not subject_template:
        return RedirectResponse("/sprava/ciselniky", status_code=302)

    # Check duplicate name
    dup = db.query(EmailTemplate).filter(
        EmailTemplate.name == name, EmailTemplate.id != tpl_id
    ).first()
    if dup:
        return RedirectResponse("/sprava/ciselniky", status_code=302)

    tpl.name = name
    tpl.subject_template = subject_template
    tpl.body_template = body_template
    db.commit()
    return RedirectResponse("/sprava/ciselniky", status_code=302)


@router.post("/sablona/{tpl_id}/smazat")
async def email_template_delete(
    tpl_id: int,
    db: Session = Depends(get_db),
):
    """Smazání emailové šablony."""
    tpl = db.query(EmailTemplate).get(tpl_id)
    if tpl:
        db.delete(tpl)
        db.commit()
    return RedirectResponse("/sprava/ciselniky", status_code=302)


# ---- Backup endpoints ----


def _safety_backup() -> str:
    """Create a safety backup and return its filename."""
    zip_path = create_backup(str(DB_PATH), str(UPLOADS_DIR), str(GENERATED_DIR), str(BACKUP_DIR))
    return zip_path.name


@router.post("/zaloha/vytvorit")
async def backup_create(filename: str = Form(""), db: Session = Depends(get_db)):
    """Vytvoření nové zálohy databáze a souborů."""
    # Check if there is any data to backup
    total = sum(
        db.query(m).count()
        for m in (Owner, Unit, Voting, TaxSession, SyncSession, EmailLog, ImportLog, BoardMember)
    )
    if total == 0:
        return RedirectResponse("/sprava/zalohy?chyba=prazdna", status_code=302)

    name = filename.strip() or None
    create_backup(str(DB_PATH), str(UPLOADS_DIR), str(GENERATED_DIR), str(BACKUP_DIR), custom_name=name)

    # Log activity — backup is file-based, use separate session
    _db = SessionLocal()
    try:
        log_activity(_db, ActivityAction.CREATED, "backup", "sprava",
                     entity_name=name or "Automatická záloha")
        _db.commit()
    finally:
        _db.close()

    return RedirectResponse("/sprava/zalohy?zprava=vytvoreno", status_code=302)


@router.get("/zaloha/{filename}/stahnout")
async def backup_download(filename: str):
    """Stažení záložního souboru."""
    file_path = BACKUP_DIR / filename
    if not file_path.is_file() or not filename.endswith(".zip") or not is_safe_path(file_path, BACKUP_DIR):
        return RedirectResponse("/sprava/zalohy", status_code=302)
    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type="application/octet-stream",
    )


@router.post("/zaloha/{filename}/smazat")
async def backup_delete(filename: str):
    """Smazání záložního souboru."""
    file_path = BACKUP_DIR / filename
    if file_path.is_file() and filename.endswith(".zip") and is_safe_path(file_path, BACKUP_DIR):
        file_path.unlink()
    return RedirectResponse("/sprava/zalohy", status_code=302)


@router.post("/zaloha/{filename}/prejmenovat")
async def backup_rename(filename: str, new_name: str = Form(...)):
    """Rename an existing backup ZIP file."""
    file_path = BACKUP_DIR / filename
    if not file_path.is_file() or not filename.endswith(".zip") or not is_safe_path(file_path, BACKUP_DIR):
        return RedirectResponse("/sprava/zalohy", status_code=302)

    # Sanitize new_name: keep only safe chars
    safe = re.sub(r"[^\w\-.]", "_", new_name.strip())
    safe = safe.strip("._")
    if not safe:
        return RedirectResponse("/sprava/zalohy?chyba=nazev", status_code=302)
    if not safe.endswith(".zip"):
        safe += ".zip"

    new_path = BACKUP_DIR / safe
    if new_path.exists() and new_path != file_path:
        return RedirectResponse("/sprava/zalohy?chyba=duplicita", status_code=302)

    file_path.rename(new_path)
    return RedirectResponse("/sprava/zalohy", status_code=302)


@router.post("/zaloha/{filename}/obnovit")
async def backup_restore_existing(filename: str):
    """Restore from an existing backup in the backups directory."""
    file_path = BACKUP_DIR / filename
    if not file_path.is_file() or not filename.endswith(".zip") or not is_safe_path(file_path, BACKUP_DIR):
        return RedirectResponse("/sprava/zalohy", status_code=302)

    if not acquire_restore_lock(str(BACKUP_DIR)):
        return RedirectResponse("/sprava/zalohy?chyba=probihajici", status_code=302)

    try:
        # Track existing backups to find safety backup name
        existing = set(p.name for p in BACKUP_DIR.glob("*.zip")) if BACKUP_DIR.is_dir() else set()

        restore_backup(
            str(file_path), str(DB_PATH), str(UPLOADS_DIR),
            str(GENERATED_DIR), str(BACKUP_DIR),
        )
        new_backups = set(p.name for p in BACKUP_DIR.glob("*.zip")) - existing
        safety = next(iter(new_backups), "")
        log_restore(str(BACKUP_DIR), filename, "Existující záloha", safety_backup=safety)
        from app.main import run_post_restore_migrations
        warnings = run_post_restore_migrations()

        _db = SessionLocal()
        try:
            log_activity(_db, ActivityAction.RESTORED, "backup", "sprava",
                         entity_name=filename, description="Obnova z existující zálohy")
            _db.commit()
        finally:
            _db.close()

        zprava = "obnoveno_varovani" if warnings else "obnoveno"
        return RedirectResponse(f"/sprava/zalohy?zprava={zprava}", status_code=302)
    except ValueError:
        logger.exception("Validační chyba při obnově ze zálohy %s", filename)
        return RedirectResponse("/sprava/zalohy?chyba=neplatny", status_code=302)
    except Exception:
        logger.exception("Selhání obnovy ze zálohy %s", filename)
        return RedirectResponse("/sprava/zalohy?chyba=selhani", status_code=302)
    finally:
        release_restore_lock(str(BACKUP_DIR))


@router.post("/zaloha/obnovit")
async def backup_restore(file: UploadFile = File(...)):
    """Obnovení dat z nahraného ZIP záložního souboru."""
    err = await validate_upload(file, **UPLOAD_LIMITS["backup"])
    if err:
        return RedirectResponse("/sprava/zalohy?chyba=upload", status_code=302)

    if not acquire_restore_lock(str(BACKUP_DIR)):
        return RedirectResponse("/sprava/zalohy?chyba=probihajici", status_code=302)

    # Save uploaded file to temp location
    temp_path = BACKUP_DIR / "upload_temp.zip"
    os.makedirs(BACKUP_DIR, exist_ok=True)
    with open(temp_path, "wb") as f:
        f.write(await file.read())

    try:
        # Track which backups exist before restore (to find the safety backup name)
        existing = set(p.name for p in BACKUP_DIR.glob("*.zip")) if BACKUP_DIR.is_dir() else set()

        restore_backup(
            str(temp_path), str(DB_PATH), str(UPLOADS_DIR),
            str(GENERATED_DIR), str(BACKUP_DIR),
        )
        # Find safety backup created by restore_backup
        new_backups = set(p.name for p in BACKUP_DIR.glob("*.zip")) - existing
        safety = next(iter(new_backups), "")
        log_restore(str(BACKUP_DIR), file.filename or "upload.zip", "ZIP soubor", safety_backup=safety)

        from app.main import run_post_restore_migrations
        warnings = run_post_restore_migrations()

        _db = SessionLocal()
        try:
            log_activity(_db, ActivityAction.RESTORED, "backup", "sprava",
                         entity_name=file.filename or "upload.zip", description="Obnova z nahraného ZIP souboru")
            _db.commit()
        finally:
            _db.close()

        zprava = "obnoveno_varovani" if warnings else "obnoveno"
        return RedirectResponse(f"/sprava/zalohy?zprava={zprava}", status_code=302)
    except ValueError:
        logger.exception("Validační chyba při obnově z nahraného ZIP")
        return RedirectResponse("/sprava/zalohy?chyba=neplatny", status_code=302)
    except Exception:
        logger.exception("Selhání obnovy z nahraného ZIP")
        return RedirectResponse("/sprava/zalohy?chyba=selhani", status_code=302)
    finally:
        if temp_path.is_file():
            temp_path.unlink()
        release_restore_lock(str(BACKUP_DIR))


@router.post("/zaloha/obnovit-soubor")
async def backup_restore_db_file(file: UploadFile = File(...)):
    """Restore from an uploaded svj.db file (from an unzipped backup)."""
    err = await validate_upload(file, **UPLOAD_LIMITS["db"])
    if err:
        return RedirectResponse("/sprava/zalohy?chyba=upload", status_code=302)

    if not acquire_restore_lock(str(BACKUP_DIR)):
        return RedirectResponse("/sprava/zalohy?chyba=probihajici", status_code=302)

    try:
        safety = _safety_backup()

        # Dispose existing DB connections before overwriting
        engine.dispose()

        # Overwrite database
        db_content = await file.read()
        with open(str(DB_PATH), "wb") as f:
            f.write(db_content)

        # Validate SQLite integrity before proceeding
        try:
            conn = sqlite3.connect(str(DB_PATH))
            result = conn.execute("PRAGMA integrity_check").fetchone()
            conn.close()
            if result[0] != "ok":
                raise ValueError(f"SQLite integrity check failed: {result[0]}")
        except (sqlite3.DatabaseError, ValueError) as e:
            logger.error("Neplatný SQLite soubor: %s", e)
            _rollback_from_safety(
                str(Path(BACKUP_DIR) / safety), str(DB_PATH),
                str(UPLOADS_DIR), str(GENERATED_DIR),
            )
            return RedirectResponse("/sprava/zalohy?chyba=neplatny_db", status_code=302)

        log_restore(str(BACKUP_DIR), file.filename or "svj.db", "DB soubor", safety_backup=safety)
        from app.main import run_post_restore_migrations
        warnings = run_post_restore_migrations()

        _db = SessionLocal()
        try:
            log_activity(_db, ActivityAction.RESTORED, "backup", "sprava",
                         entity_name=file.filename or "svj.db", description="Obnova z DB souboru")
            _db.commit()
        finally:
            _db.close()

        zprava = "obnoveno_varovani" if warnings else "obnoveno"
        return RedirectResponse(f"/sprava/zalohy?zprava={zprava}", status_code=302)
    except Exception:
        logger.exception("Selhání obnovy z DB souboru")
        _rollback_from_safety(
            str(Path(BACKUP_DIR) / safety), str(DB_PATH),
            str(UPLOADS_DIR), str(GENERATED_DIR),
        )
        return RedirectResponse("/sprava/zalohy?chyba=selhani", status_code=302)
    finally:
        release_restore_lock(str(BACKUP_DIR))


@router.post("/zaloha/obnovit-slozku")
async def backup_restore_folder(files: List[UploadFile] = File(...)):
    """Restore from an uploaded backup folder (webkitdirectory).

    The browser sends all files from the selected folder. We look for svj.db
    and optionally uploads/ and generated/ subdirectories.
    """
    # Total size check (500 MB limit for folder uploads)
    total_size = 0
    for f in files:
        content = await f.read()
        total_size += len(content)
        await f.seek(0)
    if total_size > UPLOAD_LIMITS["folder"]["max_size_mb"] * 1024 * 1024:
        return RedirectResponse("/sprava/zalohy?chyba=upload", status_code=302)

    if not acquire_restore_lock(str(BACKUP_DIR)):
        return RedirectResponse("/sprava/zalohy?chyba=probihajici", status_code=302)

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
            # Path traversal protection: ensure target stays within tmp dir
            resolved = os.path.realpath(str(target))
            if not resolved.startswith(os.path.realpath(tmp) + os.sep) and resolved != os.path.realpath(tmp):
                logger.warning("Path traversal attempt blocked: %s", rel)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with open(str(target), "wb") as dst:
                dst.write(await f.read())

            if rel == "svj.db":
                db_found = True

        if not db_found:
            return RedirectResponse("/sprava/zalohy?chyba=neplatny", status_code=302)

        # Use service function with safety backup + rollback on failure
        restore_from_directory(
            tmp, str(DB_PATH), str(UPLOADS_DIR), str(GENERATED_DIR), str(BACKUP_DIR),
        )

        log_restore(str(BACKUP_DIR), folder_name or "složka", "Složka (Finder)")

        from app.main import run_post_restore_migrations
        warnings = run_post_restore_migrations()

        _db = SessionLocal()
        try:
            log_activity(_db, ActivityAction.RESTORED, "backup", "sprava",
                         entity_name=folder_name or "složka", description="Obnova ze složky (Finder)")
            _db.commit()
        finally:
            _db.close()

        zprava = "obnoveno_varovani" if warnings else "obnoveno"
        return RedirectResponse(f"/sprava/zalohy?zprava={zprava}", status_code=302)
    except Exception:
        logger.exception("Selhání obnovy ze složky")
        return RedirectResponse("/sprava/zalohy?chyba=selhani", status_code=302)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        release_restore_lock(str(BACKUP_DIR))


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
    # Logy — rozpad na 3 podkategorie
    "email_logs": {
        "label": "Email logy",
        "description": "Záznamy o odeslaných emailech",
        "models": [EmailLog],
    },
    "import_logs": {
        "label": "Import logy",
        "description": "Záznamy o provedených importech",
        "models": [ImportLog],
    },
    "activity_logs": {
        "label": "Aktivita",
        "description": "Logy aktivit uživatelů",
        "models": [ActivityLog],
    },
    # Administrace — rozpad na 4 podkategorie
    "svj_info": {
        "label": "SVJ info a adresy",
        "description": "Informace o SVJ a adresy",
        "models": [SvjAddress, SvjInfo],
    },
    "board": {
        "label": "Výbor",
        "description": "Členové výboru",
        "models": [BoardMember],
    },
    "code_lists": {
        "label": "Číselníky",
        "description": "Položky číselníků (typy vlastnictví, prostorů apod.)",
        "models": [CodeListItem],
    },
    "email_templates": {
        "label": "Email šablony",
        "description": "Šablony pro hromadné rozesílání",
        "models": [EmailTemplate],
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

_PURGE_ORDER = [
    "owners", "votings", "tax", "sync", "share_check",
    "email_logs", "import_logs", "activity_logs",
    "svj_info", "board", "code_lists", "email_templates",
    "backups", "restore_log",
]

# Seskupení pro šablonu — standalone položky bez label, skupiny s label
_PURGE_GROUPS = [
    {"cat_keys": ["owners"]},
    {"cat_keys": ["votings"]},
    {"cat_keys": ["tax"]},
    {"cat_keys": ["sync"]},
    {"cat_keys": ["share_check"]},
    {"label": "Logy", "cat_keys": ["email_logs", "import_logs", "activity_logs"]},
    {"label": "Administrace SVJ", "cat_keys": ["svj_info", "board", "code_lists", "email_templates"]},
    {"cat_keys": ["backups"]},
    {"cat_keys": ["restore_log"]},
]


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

    # Clean uploaded files per category (only delete subdirectories of deleted categories)
    _CATEGORY_UPLOAD_DIRS = {
        "owners": ["excel"],
        "votings": ["word_templates", "scanned_ballots"],
        "tax": ["tax_pdfs"],
        "sync": ["csv"],
        "share_check": ["share_check"],
    }
    for cat_key in categories:
        for subdir in _CATEGORY_UPLOAD_DIRS.get(cat_key, []):
            target = UPLOADS_DIR / subdir
            if target.is_dir():
                shutil.rmtree(target, ignore_errors=True)
                target.mkdir(parents=True, exist_ok=True)
    # Cascade: owners purge also cleans sync files
    if "owners" in categories and "sync" not in categories:
        csv_dir = UPLOADS_DIR / "csv"
        if csv_dir.is_dir():
            shutil.rmtree(csv_dir, ignore_errors=True)
            csv_dir.mkdir(parents=True, exist_ok=True)

    # Clean generated files (ballot PDFs etc.) only if votings are deleted
    if "votings" in categories and GENERATED_DIR.is_dir():
        shutil.rmtree(GENERATED_DIR, ignore_errors=True)
        GENERATED_DIR.mkdir(parents=True, exist_ok=True)

    # Delete backup ZIP files
    if "backups" in categories and BACKUP_DIR.is_dir():
        for f in BACKUP_DIR.glob("*.zip"):
            f.unlink(missing_ok=True)

    # Delete restore log
    if "restore_log" in categories:
        log_path = BACKUP_DIR / "restore_log.json"
        if log_path.is_file():
            log_path.unlink()

    log_activity(db, ActivityAction.DELETED, "system", "sprava",
                 description=f"Smazáno: {', '.join(categories)}")
    db.commit()
    return RedirectResponse("/sprava", status_code=302)


# ---- Bulk edit endpoints ----


@router.get("/hromadne-upravy")
async def bulk_edit_page(request: Request, db: Session = Depends(get_db)):
    """Stránka hromadných úprav polí jednotek a vazeb."""
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
    """Seznam unikátních hodnot pro hromadnou úpravu daného pole."""
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
    if pole in CODE_LIST_CATEGORIES:
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
    """Záznamy s konkrétní hodnotou pole pro hromadnou úpravu."""
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
    """Aplikování hromadné změny hodnoty na vybrané záznamy."""
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
                logger.debug("Cannot convert orientation_number filter '%s' to int", old_value)
        elif pole == "share":
            try:
                filter_value = float(old_value)
            except ValueError:
                logger.debug("Cannot convert share filter '%s' to float", old_value)
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


# ---------------------------------------------------------------------------
# Deduplikace vlastníků
# ---------------------------------------------------------------------------

@router.get("/duplicity")
async def duplicates_page(
    request: Request,
    db: Session = Depends(get_db),
    back: str = Query(""),
):
    """Stránka detekce a slučování duplicitních vlastníků."""
    groups = find_duplicate_groups(db)
    back_url = back or "/sprava"

    return templates.TemplateResponse("administration/duplicates.html", {
        "request": request,
        "active_nav": "administration",
        "groups": groups,
        "total_groups": len(groups),
        "total_extra": sum(len(g["owners"]) - 1 for g in groups),
        "back_url": back_url,
    })


@router.post("/duplicity/sloucit")
async def merge_duplicate_group(
    request: Request,
    db: Session = Depends(get_db),
):
    """Merge a single duplicate group — target_id + dup_ids from form."""
    form = await request.form()
    target_id = int(form.get("target_id", 0))
    dup_ids = [int(v) for v in form.getlist("dup_ids")]

    if not target_id or not dup_ids:
        return RedirectResponse("/sprava/duplicity", status_code=302)

    target = db.query(Owner).options(
        joinedload(Owner.units).joinedload(OwnerUnit.unit)
    ).get(target_id)
    if not target:
        return RedirectResponse("/sprava/duplicity", status_code=302)

    duplicates = []
    for did in dup_ids:
        dup = db.query(Owner).options(
            joinedload(Owner.units).joinedload(OwnerUnit.unit)
        ).get(did)
        if dup and dup.id != target.id:
            duplicates.append(dup)

    merge_owners(target, duplicates, db)
    db.commit()

    return RedirectResponse("/sprava/duplicity", status_code=302)


@router.post("/duplicity/sloucit-vse")
async def merge_all_duplicates(
    request: Request,
    db: Session = Depends(get_db),
):
    """Merge ALL duplicate groups at once using recommended targets."""

    groups = find_duplicate_groups(db)
    merged_count = 0

    for group in groups:
        rec_id = group["recommended_id"]
        target = db.query(Owner).options(
            joinedload(Owner.units).joinedload(OwnerUnit.unit)
        ).get(rec_id)
        if not target:
            continue

        duplicates = []
        for o in group["owners"]:
            if o.id != rec_id:
                dup = db.query(Owner).options(
                    joinedload(Owner.units).joinedload(OwnerUnit.unit)
                ).get(o.id)
                if dup:
                    duplicates.append(dup)

        if duplicates:
            merge_owners(target, duplicates, db)
            merged_count += 1

    db.commit()

    return RedirectResponse("/sprava/duplicity", status_code=302)
