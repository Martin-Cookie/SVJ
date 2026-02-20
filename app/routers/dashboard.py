from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import EmailLog, Owner, Unit, Voting, VotingStatus

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/")
async def home(request: Request, db: Session = Depends(get_db)):
    owners_count = db.query(Owner).filter_by(is_active=True).count()
    units_count = db.query(Unit).count()
    active_votings = db.query(Voting).filter_by(status=VotingStatus.ACTIVE).count()
    recent_emails = (
        db.query(EmailLog)
        .order_by(EmailLog.created_at.desc())
        .limit(10)
        .all()
    )
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "active_nav": "dashboard",
        "owners_count": owners_count,
        "units_count": units_count,
        "active_votings": active_votings,
        "recent_emails": recent_emails,
    })
