import logging

from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    Ballot, BallotStatus, BallotVote, SvjInfo, VotingStatus,
)
from app.utils import setup_jinja_filters


logger = logging.getLogger(__name__)

templates = Jinja2Templates(directory="app/templates")
setup_jinja_filters(templates)


_VOTING_WIZARD_STEPS = [
    {"label": "Nastavení"},
    {"label": "Generování lístků"},
    {"label": "Zpracování"},
    {"label": "Výsledky"},
    {"label": "Uzavření"},
]


def _has_processed_ballots(voting) -> bool:
    """Check if voting has any processed ballots."""
    return any(b.status == BallotStatus.PROCESSED for b in voting.ballots)


def _voting_wizard(voting, current_step: int = None) -> dict:
    """Build wizard stepper context for voting workflow.
    current_step: 1-based step number for the current page.
                  If None, auto-computed from voting state (for list view).
    """
    status = voting.status
    has_processed = _has_processed_ballots(voting)

    # Auto-compute current_step if not provided (list view)
    if current_step is None:
        has_items = len(voting.items) > 0
        has_ballots = len(voting.ballots) > 0
        all_processed = has_ballots and all(
            b.status == BallotStatus.PROCESSED for b in voting.ballots
        )
        if status == VotingStatus.CLOSED:
            current_step = 5
        elif status == VotingStatus.ACTIVE and all_processed:
            current_step = 5
        elif status == VotingStatus.ACTIVE:
            current_step = 3
        elif status == VotingStatus.DRAFT and has_items:
            current_step = 2
        else:
            current_step = 1

    # Determine max completed step based on voting status
    if status == VotingStatus.CLOSED:
        max_done = 5
    elif status == VotingStatus.ACTIVE:
        max_done = 4 if has_processed else 2
    else:  # draft
        max_done = 1 if voting.items else 0

    steps = []
    for i, s in enumerate(_VOTING_WIZARD_STEPS, 1):
        if i < current_step and i <= max_done:
            step_status = "done"
        elif i == current_step:
            step_status = "done" if i <= max_done else "active"
        elif i <= max_done:
            step_status = "done"
        else:
            step_status = "pending"
        steps.append({"label": s["label"], "status": step_status})

    return {
        "wizard_steps": steps,
        "wizard_current": current_step,
        "wizard_total": len(_VOTING_WIZARD_STEPS),
        "wizard_label": _VOTING_WIZARD_STEPS[current_step - 1]["label"],
    }


def _get_declared_shares(db: Session) -> int:
    """Get total declared shares from SVJ administration settings."""
    svj_info = db.query(SvjInfo).first()
    return svj_info.total_shares if svj_info and svj_info.total_shares else 0


def _ballot_stats(voting, db: Session):
    """Compute ballot statistics for status bubbles using SQL aggregation."""
    # SQL aggregation for counts and votes — avoids loading all ballots
    rows = db.query(
        Ballot.status,
        func.count(Ballot.id),
        func.coalesce(func.sum(Ballot.total_votes), 0),
    ).filter(
        Ballot.voting_id == voting.id
    ).group_by(Ballot.status).all()

    status_counts = {s.value: 0 for s in BallotStatus}
    total_ballots = 0
    total_generated_votes = 0
    for status, cnt, votes_sum in rows:
        status_counts[status.value] = cnt
        total_ballots += cnt
        total_generated_votes += votes_sum

    # Processed votes: ballots with status=processed that have actual votes
    processed_with_votes = db.query(
        func.coalesce(func.sum(Ballot.total_votes), 0)
    ).filter(
        Ballot.voting_id == voting.id,
        Ballot.status == BallotStatus.PROCESSED,
        Ballot.id.in_(
            db.query(BallotVote.ballot_id).filter(BallotVote.vote.isnot(None))
        ),
    ).scalar()

    declared_shares = _get_declared_shares(db)
    quorum_reached = (
        processed_with_votes / declared_shares >= voting.quorum_threshold
        if declared_shares
        else False
    )
    return {
        "total_ballots": total_ballots,
        "status_counts": status_counts,
        "total_processed_votes": processed_with_votes,
        "total_generated_votes": total_generated_votes,
        "declared_shares": declared_shares,
        "quorum_reached": quorum_reached,
    }
