from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ActivityLog, EmailLog, Owner, OwnerUnit, SvjInfo, Unit, Voting, BankStatement, Payment, PaymentDirection, PaymentMatchStatus
from app.models.voting import Ballot, BallotStatus, BallotVote
from app.models.tax import TaxDocument, TaxSession, TaxDistribution, EmailDeliveryStatus
from app.utils import strip_diacritics, templates

router = APIRouter()


@router.get("/prehled/rozdil-podilu")
async def shares_breakdown(request: Request, vse: int = 0, db: Session = Depends(get_db)):
    """Porovnání podílů dle prohlášení vs. evidence vlastníků."""
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
    """Hlavní přehledová stránka se statistikami a poslední aktivitou."""
    owners_count = db.query(Owner).filter_by(is_active=True).count()
    units_count = db.query(Unit).count()
    # Voting stats: count per status (lightweight)
    svj_info = db.query(SvjInfo).first()
    declared_shares = svj_info.total_shares if svj_info and svj_info.total_shares else 0

    voting_counts = (
        db.query(Voting.status, func.count(Voting.id))
        .group_by(Voting.status)
        .all()
    )
    total_votings = sum(c for _, c in voting_counts)

    # Nejnovější hlasování per status — bez eager loadingu ballots+votes
    voting_by_status = {}
    for status, count in voting_counts:
        latest = (
            db.query(Voting)
            .filter(Voting.status == status)
            .order_by(Voting.updated_at.desc())
            .first()
        )
        if latest:
            # SQL agregace: počet lístků a kvórum (suma hlasů zpracovaných lístků s ≥1 hlasem)
            total_ballots = db.query(func.count(Ballot.id)).filter(
                Ballot.voting_id == latest.id
            ).scalar() or 0

            # Kvórum: suma total_votes z PROCESSED lístků, které mají ≥1 BallotVote.vote IS NOT NULL
            voted_ballots_subq = (
                db.query(Ballot.id)
                .join(BallotVote, BallotVote.ballot_id == Ballot.id)
                .filter(
                    Ballot.voting_id == latest.id,
                    Ballot.status == BallotStatus.PROCESSED,
                    BallotVote.vote.isnot(None),
                )
                .distinct()
                .subquery()
            )
            processed_votes = (
                db.query(func.coalesce(func.sum(Ballot.total_votes), 0))
                .filter(Ballot.id.in_(db.query(voted_ballots_subq.c.id)))
                .scalar()
            ) or 0

            quorum_pct = round(processed_votes / declared_shares * 100, 2) if declared_shares else 0
            voting_by_status[status.value] = {
                "count": count,
                "latest": latest,
                "date": latest.start_date or latest.created_at,
                "total_ballots": total_ballots,
                "quorum_pct": quorum_pct,
            }

    # Tax sessions — count per status in one query
    tax_status_counts = (
        db.query(TaxSession.send_status, func.count(TaxSession.id))
        .group_by(TaxSession.send_status)
        .all()
    )

    # Latest session per status (one query per status)
    latest_session_ids = {}
    tax_by_status = {}
    for status, count in tax_status_counts:
        latest = (
            db.query(TaxSession)
            .filter(TaxSession.send_status == status)
            .order_by(TaxSession.created_at.desc())
            .first()
        )
        if latest:
            s = status.value
            latest_session_ids[latest.id] = s
            tax_by_status[s] = {
                "count": count,
                "latest": latest,
                "date": latest.created_at,
                "sent": 0,
                "total_dists": 0,
            }

    # Single query for distribution stats of latest sessions per status
    if latest_session_ids:
        dist_stats = (
            db.query(
                TaxDocument.session_id,
                func.count(TaxDistribution.id),
                func.sum(case(
                    (TaxDistribution.email_status == EmailDeliveryStatus.SENT, 1),
                    else_=0,
                )),
            )
            .join(TaxDistribution.document)
            .filter(TaxDocument.session_id.in_(latest_session_ids.keys()))
            .group_by(TaxDocument.session_id)
            .all()
        )
        for session_id, total, sent in dist_stats:
            s = latest_session_ids[session_id]
            tax_by_status[s]["total_dists"] = total
            tax_by_status[s]["sent"] = sent or 0

    # Unified activity: EmailLog + ActivityLog
    recent_emails = db.query(EmailLog).order_by(EmailLog.created_at.desc()).limit(30).all()
    recent_activity = db.query(ActivityLog).order_by(ActivityLog.created_at.desc()).limit(30).all()

    unified = []
    # URL mapování pro entity_type → detail stránka
    _entity_urls = {
        "voting": "/hlasovani/{id}",
        "tax_session": "/dane/{id}",
        "owner": "/vlastnici/{id}",
    }

    for e in recent_emails:
        url = f"/dane/{e.reference_id}" if e.reference_id else ""
        unified.append({
            "type": "email",
            "created_at": e.created_at,
            "module": e.module or "",
            "description": e.subject or "",
            "detail": e.recipient_name or e.recipient_email or "",
            "status": e.status.value if e.status else "",
            "url": url,
            "entity": e,
        })
    for a in recent_activity:
        url_tpl = _entity_urls.get(a.entity_type, "")
        url = url_tpl.format(id=a.entity_id) if url_tpl and a.entity_id else ""
        unified.append({
            "type": "activity",
            "created_at": a.created_at,
            "module": a.module or "",
            "description": a.entity_name or "",
            "detail": a.description or "",
            "status": a.action.value if a.action else "",
            "url": url,
            "entity": a,
        })

    # Sort combined and limit
    unified.sort(key=lambda x: x["created_at"] or datetime.min, reverse=True)
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

    # Share statistics (svj_info + declared_shares already loaded above)
    owners_scd = db.query(func.sum(OwnerUnit.votes)).filter(OwnerUnit.valid_to.is_(None)).scalar() or 0
    units_scd = db.query(func.sum(Unit.podil_scd)).scalar() or 0

    # Payment stats
    statement_count = db.query(BankStatement).count()
    matched_statuses = [PaymentMatchStatus.AUTO_MATCHED, PaymentMatchStatus.MANUAL]
    matched_payments = db.query(Payment).filter(
        Payment.direction == PaymentDirection.INCOME,
        Payment.match_status.in_(matched_statuses),
    ).count()
    unmatched_payments = db.query(Payment).filter_by(
        match_status=PaymentMatchStatus.UNMATCHED,
        direction=PaymentDirection.INCOME,
    ).count()
    total_income = db.query(
        func.coalesce(func.sum(Payment.amount), 0)
    ).filter(
        Payment.direction == PaymentDirection.INCOME,
        Payment.match_status.in_(matched_statuses),
    ).scalar() or 0

    ctx = {
        "request": request,
        "active_nav": "dashboard",
        "owners_count": owners_count,
        "units_count": units_count,
        "active_votings": total_votings,
        "voting_by_status": voting_by_status,
        "active_tax_count": sum(c for _, c in tax_status_counts),
        "tax_by_status": tax_by_status,
        "recent_activity": unified,
        "declared_shares": declared_shares,
        "owners_scd": owners_scd,
        "units_scd": units_scd,
        "q": q,
        "sort": sort,
        "order": order,
        "statement_count": statement_count,
        "matched_payments": matched_payments,
        "unmatched_payments": unmatched_payments,
        "total_income": total_income,
    }

    if request.headers.get("HX-Request") and not request.headers.get("HX-Boosted"):
        return templates.TemplateResponse("partials/dashboard_activity_body.html", ctx)

    return templates.TemplateResponse("dashboard.html", ctx)
