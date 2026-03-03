from fastapi import APIRouter, Depends, Query, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy import case, func
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import ActivityLog, EmailLog, Owner, OwnerUnit, SvjInfo, Unit, Voting, VotingStatus
from app.models.voting import Ballot, BallotStatus
from app.models.tax import TaxSession, TaxDistribution, EmailDeliveryStatus
from app.utils import setup_jinja_filters, strip_diacritics

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
setup_jinja_filters(templates)


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
        .options(joinedload(Voting.ballots).joinedload(Ballot.votes))
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
    svj_info = db.query(SvjInfo).first()
    declared_shares = svj_info.total_shares if svj_info else 0
    voting_by_status = {}
    for v in active_votings_list:
        s = v.status.value
        if s not in voting_by_status:
            # Calculate quorum percentage (same as detail page)
            processed = [b for b in v.ballots if b.status == BallotStatus.PROCESSED]
            voted = [b for b in processed if any(bv.vote is not None for bv in b.votes)]
            processed_votes = sum(b.total_votes for b in voted)
            quorum_pct = round(processed_votes / declared_shares * 100, 2) if declared_shares else 0
            voting_by_status[s] = {
                "count": 0,
                "latest": v,
                "date": v.start_date or v.created_at,
                "total_ballots": len(v.ballots),
                "quorum_pct": quorum_pct,
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

    # Unified activity: EmailLog + ActivityLog
    recent_emails = db.query(EmailLog).order_by(EmailLog.created_at.desc()).limit(30).all()
    recent_activity = db.query(ActivityLog).order_by(ActivityLog.created_at.desc()).limit(30).all()

    unified = []
    for e in recent_emails:
        unified.append({
            "type": "email",
            "created_at": e.created_at,
            "module": e.module or "",
            "description": e.subject or "",
            "detail": e.recipient_name or e.recipient_email or "",
            "status": e.status.value if e.status else "",
            "entity": e,
        })
    for a in recent_activity:
        unified.append({
            "type": "activity",
            "created_at": a.created_at,
            "module": a.module or "",
            "description": a.entity_name or "",
            "detail": a.description or "",
            "status": a.action.value if a.action else "",
            "entity": a,
        })

    # Sort combined and limit
    unified.sort(key=lambda x: x["created_at"] or x["created_at"], reverse=True)
    unified = unified[:50]

    # Search filtering
    if q:
        q_lower = q.lower()
        q_ascii = strip_diacritics(q)
        unified = [
            item for item in unified
            if q_lower in item["description"].lower()
            or q_ascii in strip_diacritics(item["description"])
            or q_lower in item["detail"].lower()
            or q_ascii in strip_diacritics(item["detail"])
            or q_lower in item["module"].lower()
        ]

    # Sorting
    SORT_KEYS = {
        "date": lambda x: x["created_at"],
        "module": lambda x: x["module"].lower(),
        "description": lambda x: strip_diacritics(x["description"]),
        "detail": lambda x: strip_diacritics(x["detail"]),
        "status": lambda x: x["status"],
    }
    sort_fn = SORT_KEYS.get(sort, SORT_KEYS["date"])
    unified.sort(key=sort_fn, reverse=(order == "desc"))

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
        "recent_activity": unified,
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
