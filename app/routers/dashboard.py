from fastapi import APIRouter, Depends, Query, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import EmailLog, Owner, OwnerUnit, SvjInfo, Unit, Voting, VotingStatus
from app.models.voting import Ballot, BallotStatus
from app.models.tax import TaxSession, TaxDistribution, EmailDeliveryStatus
from app.utils import strip_diacritics

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/prehled/rozdil-podilu")
async def shares_breakdown(request: Request, vse: int = 0, db: Session = Depends(get_db)):
    svj_info = db.query(SvjInfo).first()
    declared_shares = svj_info.total_shares if svj_info and svj_info.total_shares else 0

    # Per-unit: sum of active owner votes
    owner_votes_subq = (
        db.query(
            OwnerUnit.unit_id,
            func.sum(OwnerUnit.votes).label("owners_votes"),
        )
        .filter(OwnerUnit.valid_to.is_(None))
        .group_by(OwnerUnit.unit_id)
        .subquery()
    )

    rows = (
        db.query(
            Unit.id,
            Unit.unit_number,
            Unit.podil_scd,
            owner_votes_subq.c.owners_votes,
        )
        .outerjoin(owner_votes_subq, Unit.id == owner_votes_subq.c.unit_id)
        .order_by(Unit.unit_number)
        .all()
    )

    items = []
    total_units_scd = 0
    total_owners_votes = 0
    for unit_id, unit_number, podil_scd, owners_votes in rows:
        p = podil_scd or 0
        o = owners_votes or 0
        total_units_scd += p
        total_owners_votes += o
        items.append({
            "unit_id": unit_id,
            "unit_number": unit_number,
            "podil_scd": p,
            "owners_votes": o,
            "diff": o - p,
        })

    show_all = bool(vse)
    filtered_items = items if show_all else [i for i in items if i["diff"] != 0]

    return templates.TemplateResponse("dashboard_shares.html", {
        "request": request,
        "active_nav": "dashboard",
        "declared_shares": declared_shares,
        "total_units_scd": total_units_scd,
        "total_owners_votes": total_owners_votes,
        "diff_owners": total_owners_votes - declared_shares,
        "diff_units": total_units_scd - declared_shares,
        "items": filtered_items,
        "show_all": show_all,
        "total_count": len(items),
        "diff_count": len([i for i in items if i["diff"] != 0]),
    })


@router.get("/")
async def home(
    request: Request,
    q: str = Query(""),
    sort: str = Query("date"),
    order: str = Query("desc"),
    db: Session = Depends(get_db),
):
    owners_count = db.query(Owner).filter_by(is_active=True).count()
    units_count = db.query(Unit).count()
    active_votings_list = (
        db.query(Voting)
        .order_by(
            case(
                (Voting.status == VotingStatus.ACTIVE, 0),
                (Voting.status == VotingStatus.DRAFT, 1),
                (Voting.status == VotingStatus.CLOSED, 2),
                (Voting.status == VotingStatus.CANCELLED, 3),
            ),
            Voting.updated_at.desc(),
        )
        .all()
    )
    active_tax_sessions = (
        db.query(TaxSession)
        .order_by(TaxSession.created_at.desc())
        .all()
    )

    # Group votings by status: {status_value: {"count": N, "latest": Voting, "date": ..., "progress": ...}}
    voting_by_status = {}
    for v in active_votings_list:
        s = v.status.value
        if s not in voting_by_status:
            # Calculate progress for the latest voting of this status
            total_ballots = db.query(Ballot).filter_by(voting_id=v.id).count()
            processed_ballots = db.query(Ballot).filter_by(
                voting_id=v.id, status=BallotStatus.PROCESSED
            ).count()
            pct = round(processed_ballots / total_ballots * 100) if total_ballots else 0
            voting_by_status[s] = {
                "count": 0,
                "latest": v,
                "date": v.start_date or v.created_at,
                "processed": processed_ballots,
                "total_ballots": total_ballots,
                "progress_pct": pct,
            }
        voting_by_status[s]["count"] += 1

    # Group tax sessions by status
    tax_by_status = {}
    for t in active_tax_sessions:
        s = t.send_status.value
        if s not in tax_by_status:
            # Calculate send progress for the latest tax session of this status
            total_dists = db.query(TaxDistribution).join(TaxDistribution.document).filter(
                TaxDistribution.document.has(session_id=t.id)
            ).count()
            sent_dists = db.query(TaxDistribution).join(TaxDistribution.document).filter(
                TaxDistribution.document.has(session_id=t.id),
                TaxDistribution.email_status == EmailDeliveryStatus.SENT,
            ).count()
            tax_by_status[s] = {
                "count": 0,
                "latest": t,
                "date": t.created_at,
                "sent": sent_dists,
                "total_dists": total_dists,
            }
        tax_by_status[s]["count"] += 1

    recent_emails = (
        db.query(EmailLog)
        .order_by(EmailLog.created_at.desc())
        .limit(50)
        .all()
    )

    # Search filtering
    if q:
        q_lower = q.lower()
        q_ascii = strip_diacritics(q)
        recent_emails = [
            e for e in recent_emails
            if q_lower in (e.recipient_name or "").lower()
            or q_ascii in strip_diacritics(e.recipient_name or "")
            or q_lower in (e.recipient_email or "").lower()
            or q_lower in (e.subject or "").lower()
            or q_lower in (e.module or "").lower()
        ]

    # Sorting
    SORT_KEYS = {
        "date": lambda e: e.created_at,
        "module": lambda e: (e.module or "").lower(),
        "recipient": lambda e: strip_diacritics(e.recipient_name or e.recipient_email or ""),
        "subject": lambda e: (e.subject or "").lower(),
        "status": lambda e: e.status.value if e.status else "",
    }
    sort_fn = SORT_KEYS.get(sort, SORT_KEYS["date"])
    recent_emails.sort(key=sort_fn, reverse=(order == "desc"))

    # Share statistics
    svj_info = db.query(SvjInfo).first()
    declared_shares = svj_info.total_shares if svj_info and svj_info.total_shares else 0
    owners_scd = db.query(func.sum(OwnerUnit.votes)).filter(OwnerUnit.valid_to.is_(None)).scalar() or 0
    units_scd = db.query(func.sum(Unit.podil_scd)).scalar() or 0

    ctx = {
        "request": request,
        "active_nav": "dashboard",
        "owners_count": owners_count,
        "units_count": units_count,
        "active_votings": len(active_votings_list),
        "voting_by_status": voting_by_status,
        "active_tax_count": len(active_tax_sessions),
        "tax_by_status": tax_by_status,
        "recent_emails": recent_emails,
        "declared_shares": declared_shares,
        "owners_scd": owners_scd,
        "units_scd": units_scd,
        "q": q,
        "sort": sort,
        "order": order,
    }

    if request.headers.get("HX-Request") and not request.headers.get("HX-Boosted"):
        return templates.TemplateResponse("partials/dashboard_activity_body.html", ctx)

    return templates.TemplateResponse("dashboard.html", ctx)
