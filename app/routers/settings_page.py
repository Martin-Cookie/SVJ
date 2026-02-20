from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import EmailLog

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/")
async def settings_view(request: Request, db: Session = Depends(get_db)):
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
    })
