"""Číselníky a emailové šablony — CRUD operace."""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import CodeListItem, EmailTemplate
from app.services.code_list_service import (
    CODE_LIST_CATEGORIES, CODE_LIST_ORDER, get_all_code_lists,
)
from app.utils import templates

from ._helpers import _get_usage_count

router = APIRouter()


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
