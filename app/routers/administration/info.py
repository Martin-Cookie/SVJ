"""SVJ info CRUD — hlavní stránka administrace, info o SVJ, adresy."""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import (
    SvjInfo, SvjAddress, BoardMember, CodeListItem, Owner,
    Unit, Voting, TaxSession, SyncSession, EmailLog, ImportLog,
)
from app.services.code_list_service import CODE_LIST_CATEGORIES
from app.utils import templates, utcnow

from ._helpers import (
    BACKUP_DIR,
    _ROLE_SORT,
    _get_or_create_svj_info,
)

logger = logging.getLogger(__name__)

router = APIRouter()


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
    info.updated_at = utcnow()
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
