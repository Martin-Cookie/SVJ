from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import case
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import SvjInfo, SvjAddress, BoardMember

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

    return templates.TemplateResponse("administration/index.html", {
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
