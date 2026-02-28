from typing import Optional
from unicodedata import category, normalize

from dotenv import set_key
from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import EmailLog, Owner

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _strip_diacritics(text: str) -> str:
    """Remove diacritics and lowercase for search."""
    nfkd = normalize("NFD", text)
    return "".join(c for c in nfkd if category(c) != "Mn").lower()


SORT_COLUMNS = {
    "date": EmailLog.created_at,
    "module": EmailLog.module,
    "recipient": EmailLog.recipient_name,
    "subject": EmailLog.subject,
    "status": EmailLog.status,
}


@router.get("/")
async def settings_view(
    request: Request,
    db: Session = Depends(get_db),
    q: str = Query(""),
    sort: str = Query("date"),
    order: str = Query("desc"),
):
    # Build query
    query = db.query(EmailLog)

    # Search
    if q:
        q_lower = q.lower()
        q_ascii = _strip_diacritics(q)
        # Fetch all then filter in Python (SQLite diacritics issue)
        all_logs = query.all()
        email_logs = [
            e for e in all_logs
            if q_lower in (e.recipient_email or "").lower()
            or q_ascii in _strip_diacritics(e.recipient_name or "")
            or q_lower in (e.subject or "").lower()
            or q_lower in (e.module or "").lower()
        ]
        # Sort in Python
        sort_key = {
            "date": lambda e: e.created_at or "",
            "module": lambda e: (e.module or "").lower(),
            "recipient": lambda e: _strip_diacritics(e.recipient_name or ""),
            "subject": lambda e: (e.subject or "").lower(),
            "status": lambda e: (e.status.value if e.status else ""),
        }
        key_fn = sort_key.get(sort, sort_key["date"])
        email_logs.sort(key=key_fn, reverse=(order == "desc"))
        email_logs = email_logs[:100]
    else:
        # SQL sort
        col = SORT_COLUMNS.get(sort, EmailLog.created_at)
        if order == "asc":
            query = query.order_by(col.asc().nulls_last())
        else:
            query = query.order_by(col.desc().nulls_last())
        email_logs = query.limit(100).all()

    # Build email → owner_id lookup for clickable recipients
    emails_in_log = {e.recipient_email for e in email_logs if e.recipient_email}
    owner_by_email = {}
    if emails_in_log:
        owners = db.query(Owner.id, Owner.email, Owner.email_secondary).filter(
            Owner.is_active == True
        ).all()
        for o in owners:
            if o.email:
                owner_by_email[o.email.lower()] = o.id
            if o.email_secondary:
                owner_by_email[o.email_secondary.lower()] = o.id

    # HTMX partial
    is_htmx = request.headers.get("HX-Request") and not request.headers.get("HX-Boosted")

    ctx = {
        "request": request,
        "active_nav": "settings",
        "settings": settings,
        "email_logs": email_logs,
        "owner_by_email": owner_by_email,
        "q": q,
        "sort": sort,
        "order": order,
    }

    if is_htmx:
        return templates.TemplateResponse("partials/settings_email_tbody.html", ctx)
    return templates.TemplateResponse("settings.html", ctx)


@router.get("/smtp/formular")
async def smtp_form(request: Request):
    return templates.TemplateResponse("partials/smtp_form.html", {
        "request": request,
        "settings": settings,
    })


@router.get("/smtp/info")
async def smtp_info(request: Request):
    return templates.TemplateResponse("partials/smtp_info.html", {
        "request": request,
        "settings": settings,
    })


@router.post("/smtp")
async def save_smtp(
    request: Request,
    smtp_host: str = Form(""),
    smtp_port: int = Form(587),
    smtp_user: str = Form(""),
    smtp_password: str = Form(""),
    smtp_from_name: str = Form(""),
    smtp_from_email: str = Form(""),
    smtp_use_tls: Optional[str] = Form(None),
):
    env_path = str(settings.base_dir / ".env")
    use_tls = smtp_use_tls == "true"

    set_key(env_path, "SMTP_HOST", smtp_host)
    set_key(env_path, "SMTP_PORT", str(smtp_port))
    set_key(env_path, "SMTP_USER", smtp_user)
    if smtp_password:  # empty = keep existing
        set_key(env_path, "SMTP_PASSWORD", smtp_password)
    set_key(env_path, "SMTP_FROM_NAME", smtp_from_name)
    set_key(env_path, "SMTP_FROM_EMAIL", smtp_from_email)
    set_key(env_path, "SMTP_USE_TLS", str(use_tls).lower())

    # Reload settings singleton in-place
    settings.smtp_host = smtp_host
    settings.smtp_port = smtp_port
    settings.smtp_user = smtp_user
    if smtp_password:
        settings.smtp_password = smtp_password
    settings.smtp_from_name = smtp_from_name
    settings.smtp_from_email = smtp_from_email
    settings.smtp_use_tls = use_tls

    return templates.TemplateResponse("partials/smtp_info.html", {
        "request": request,
        "settings": settings,
        "saved": True,
    })
