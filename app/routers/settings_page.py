import logging
import smtplib
from pathlib import Path
from typing import Optional

from dotenv import set_key
from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session

from sqlalchemy import or_

from app.config import settings
from app.database import get_db
from app.models import EmailLog, Owner
from app.utils import build_list_url, is_htmx_partial, is_safe_path, strip_diacritics, templates

logger = logging.getLogger(__name__)

router = APIRouter()



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
    """Stránka nastavení s historií odeslaných emailů a SMTP konfigurací."""
    # Build query
    query = db.query(EmailLog)

    # Search — SQL filter for email/subject/module + diacritics-insensitive name via name_normalized
    if q:
        q_pattern = f"%{q}%"
        q_ascii = f"%{strip_diacritics(q)}%"
        query = query.filter(
            or_(
                EmailLog.recipient_email.ilike(q_pattern),
                EmailLog.recipient_name.ilike(q_pattern),
                EmailLog.name_normalized.like(q_ascii),
                EmailLog.subject.ilike(q_pattern),
                EmailLog.module.ilike(q_pattern),
            )
        )

    # SQL sort + limit
    col = SORT_COLUMNS.get(sort, EmailLog.created_at)
    if order == "asc":
        query = query.order_by(col.asc().nulls_last())
    else:
        query = query.order_by(col.desc().nulls_last())
    email_logs = query.all()

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
    """Formulář pro editaci SMTP nastavení."""
    return templates.TemplateResponse("partials/smtp_form.html", {
        "request": request,
        "settings": settings,
    })


@router.get("/smtp/info")
async def smtp_info(request: Request):
    """Zobrazení aktuálního SMTP nastavení (read-only)."""
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
    """Uložení SMTP konfigurace do .env souboru."""
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


@router.post("/smtp/test")
async def test_smtp_connection(request: Request):
    """Test SMTP connection and return result as partial HTML."""
    try:
        if settings.smtp_host in ("smtp.example.com", ""):
            return templates.TemplateResponse("partials/smtp_info.html", {
                "request": request,
                "settings": settings,
                "smtp_test_error": "SMTP server není nakonfigurován.",
            })
        from app.services.email_service import _create_smtp
        server = _create_smtp(settings.smtp_host, settings.smtp_port, settings.smtp_use_tls, timeout=10)
        if settings.smtp_user:
            server.login(settings.smtp_user, settings.smtp_password)
        server.quit()
        return templates.TemplateResponse("partials/smtp_info.html", {
            "request": request,
            "settings": settings,
            "smtp_test_ok": True,
        })
    except smtplib.SMTPAuthenticationError:
        return templates.TemplateResponse("partials/smtp_info.html", {
            "request": request,
            "settings": settings,
            "smtp_test_error": "Přihlášení selhalo — zkontrolujte uživatele a heslo.",
        })
    except Exception as e:
        logger.warning("SMTP test failed: %s", e)
        return templates.TemplateResponse("partials/smtp_info.html", {
            "request": request,
            "settings": settings,
            "smtp_test_error": "Připojení k SMTP serveru selhalo.",
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
