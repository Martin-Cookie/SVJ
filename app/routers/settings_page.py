from pathlib import Path
from typing import Optional

from dotenv import set_key
from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import EmailLog, Owner
from app.utils import build_list_url, is_htmx_partial, is_safe_path, setup_jinja_filters, strip_diacritics

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
setup_jinja_filters(templates)


def _parse_attachments(raw: Optional[str]) -> list:
    """Parse attachment_paths into list of {name, path, exists}.

    Supports both old format (just filenames) and new format (full paths).
    """
    if not raw:
        return []
    result = []
    for part in raw.split(", "):
        part = part.strip()
        if not part:
            continue
        p = Path(part)
        if p.is_absolute():
            result.append({"name": p.name, "path": str(p), "exists": p.exists()})
        else:
            # Old format — just filename, no path available
            result.append({"name": part, "path": "", "exists": False})
    return result


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
        q_ascii = strip_diacritics(q)
        # Fetch all then filter in Python (SQLite diacritics issue)
        all_logs = query.all()
        email_logs = [
            e for e in all_logs
            if q_lower in (e.recipient_email or "").lower()
            or q_ascii in strip_diacritics(e.recipient_name or "")
            or q_lower in (e.subject or "").lower()
            or q_lower in (e.module or "").lower()
        ]
        # Sort in Python
        sort_key = {
            "date": lambda e: e.created_at or "",
            "module": lambda e: (e.module or "").lower(),
            "recipient": lambda e: strip_diacritics(e.recipient_name or ""),
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

    # Parse attachments for each email log
    attachments_by_id = {e.id: _parse_attachments(e.attachment_paths) for e in email_logs}

    # HTMX partial
    # Build list_url for back navigation
    list_url = build_list_url(request)

    ctx = {
        "request": request,
        "active_nav": "settings",
        "settings": settings,
        "email_logs": email_logs,
        "owner_by_email": owner_by_email,
        "attachments_by_id": attachments_by_id,
        "list_url": list_url,
        "q": q,
        "sort": sort,
        "order": order,
    }

    if is_htmx_partial(request):
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


@router.get("/priloha/{log_id}/{filename}")
async def serve_attachment(
    log_id: int,
    filename: str,
    db: Session = Depends(get_db),
):
    """Serve an email attachment file for in-browser preview."""
    log = db.query(EmailLog).get(log_id)
    if not log or not log.attachment_paths:
        return RedirectResponse("/nastaveni", status_code=302)

    # Find matching path in attachment_paths
    for part in log.attachment_paths.split(", "):
        part = part.strip()
        p = Path(part)
        if p.name == filename and p.is_absolute() and p.exists():
            # Validate path is within allowed directories
            if is_safe_path(p, settings.upload_dir, settings.generated_dir):
                suffix = p.suffix.lower()
                media_types = {
                    ".pdf": "application/pdf",
                    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    ".xls": "application/vnd.ms-excel",
                    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    ".csv": "text/csv",
                }
                media_type = media_types.get(suffix, "application/octet-stream")
                return FileResponse(str(p), media_type=media_type, filename=p.name)

    return RedirectResponse("/nastaveni", status_code=302)
