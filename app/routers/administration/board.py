"""Členové výboru a kontrolního orgánu — přidání, úprava, smazání."""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import BoardMember
from app.utils import is_valid_email

router = APIRouter()


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
