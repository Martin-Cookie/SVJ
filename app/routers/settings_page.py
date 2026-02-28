from typing import Optional

from dotenv import set_key
from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import EmailLog

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/")
async def settings_view(
    request: Request,
    db: Session = Depends(get_db),
    flash: Optional[str] = Query(None),
    flash_type: Optional[str] = Query(None),
):
    email_logs = (
        db.query(EmailLog)
        .order_by(EmailLog.created_at.desc())
        .limit(50)
        .all()
    )
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "active_nav": "settings",
        "settings": settings,
        "email_logs": email_logs,
        "flash_message": flash,
        "flash_type": flash_type or "success",
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

    return RedirectResponse(
        "/nastaveni?flash=Nastaven%C3%AD+ulo%C5%BEeno&flash_type=success",
        status_code=302,
    )
