import shutil
import zipfile
from datetime import datetime, date
from io import BytesIO
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.database import get_db
from app.models import (
    Ballot, BallotStatus, BallotVote, Owner, OwnerUnit, Voting,
    VotingItem, VotingStatus, VoteValue,
)
from app.services.word_parser import extract_voting_items

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/")
async def voting_list(request: Request, db: Session = Depends(get_db)):
    votings = db.query(Voting).order_by(Voting.created_at.desc()).all()
    return templates.TemplateResponse("voting/index.html", {
        "request": request,
        "active_nav": "voting",
        "votings": votings,
    })


@router.get("/nova")
async def voting_create_page(request: Request):
    return templates.TemplateResponse("voting/create.html", {
        "request": request,
        "active_nav": "voting",
    })


@router.post("/nova")
async def voting_create(
    request: Request,
    title: str = Form(...),
    description: str = Form(""),
    start_date: str = Form(""),
    end_date: str = Form(""),
    quorum_threshold: float = Form(0.5),
    partial_owner_mode: str = Form("shared"),
    file: UploadFile = File(None),
    db: Session = Depends(get_db),
):
    voting = Voting(
        title=title,
        description=description,
        quorum_threshold=quorum_threshold,
        partial_owner_mode=partial_owner_mode,
    )
    if start_date:
        voting.start_date = date.fromisoformat(start_date)
    if end_date:
        voting.end_date = date.fromisoformat(end_date)

    # Handle Word template upload
    if file and file.filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = settings.upload_dir / "word_templates" / f"{timestamp}_{file.filename}"
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as f:
            shutil.copyfileobj(file.file, f)
        voting.template_path = str(dest)

        # Extract voting items from template
        try:
            items = extract_voting_items(str(dest))
            db.add(voting)
            db.flush()
            for item_data in items:
                item = VotingItem(
                    voting_id=voting.id,
                    order=item_data["order"],
                    title=item_data["title"],
                    description=item_data.get("description", ""),
                )
                db.add(item)
        except Exception:
            db.add(voting)
            db.flush()
    else:
        db.add(voting)
        db.flush()

    # Calculate total votes
    total = db.query(func.sum(OwnerUnit.votes)).scalar() or 0
    voting.total_votes_possible = total

    db.commit()
    return RedirectResponse(f"/hlasovani/{voting.id}", status_code=302)


@router.get("/{voting_id}")
async def voting_detail(voting_id: int, request: Request, db: Session = Depends(get_db)):
    voting = db.query(Voting).options(
        joinedload(Voting.items),
        joinedload(Voting.ballots).joinedload(Ballot.owner),
        joinedload(Voting.ballots).joinedload(Ballot.votes),
    ).get(voting_id)
    if not voting:
        return RedirectResponse("/hlasovani", status_code=302)

    # Calculate results per item
    results = []
    for item in voting.items:
        votes_for = 0
        votes_against = 0
        for ballot in voting.ballots:
            if ballot.status != BallotStatus.PROCESSED:
                continue
            for bv in ballot.votes:
                if bv.voting_item_id == item.id:
                    if bv.vote == VoteValue.FOR:
                        votes_for += bv.votes_count
                    elif bv.vote == VoteValue.AGAINST:
                        votes_against += bv.votes_count

        total = voting.total_votes_possible or 1
        results.append({
            "item": item,
            "votes_for": votes_for,
            "votes_against": votes_against,
            "pct_for": round(votes_for / total * 100, 1) if total else 0,
            "pct_against": round(votes_against / total * 100, 1) if total else 0,
            "votes_missing": total - votes_for - votes_against,
            "pct_missing": round((total - votes_for - votes_against) / total * 100, 1) if total else 0,
        })

    # Status counts
    total_ballots = len(voting.ballots)
    status_counts = {s.value: 0 for s in BallotStatus}
    for b in voting.ballots:
        status_counts[b.status.value] += 1

    # Quorum check
    total_processed_votes = sum(
        b.total_votes for b in voting.ballots if b.status == BallotStatus.PROCESSED
    )
    quorum_reached = (
        total_processed_votes / voting.total_votes_possible >= voting.quorum_threshold
        if voting.total_votes_possible
        else False
    )

    return templates.TemplateResponse("voting/detail.html", {
        "request": request,
        "active_nav": "voting",
        "voting": voting,
        "results": results,
        "total_ballots": total_ballots,
        "status_counts": status_counts,
        "total_processed_votes": total_processed_votes,
        "quorum_reached": quorum_reached,
    })


@router.post("/{voting_id}/generovat")
async def generate_ballots(
    voting_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    voting = db.query(Voting).options(joinedload(Voting.items)).get(voting_id)
    if not voting:
        return RedirectResponse("/hlasovani", status_code=302)

    owners = db.query(Owner).filter_by(is_active=True).options(
        joinedload(Owner.units)
    ).all()

    created = 0
    for owner in owners:
        # Check if ballot already exists
        existing = db.query(Ballot).filter_by(
            voting_id=voting.id, owner_id=owner.id
        ).first()
        if existing:
            continue

        total_votes = sum(ou.votes for ou in owner.units)
        units_text = ", ".join(
            str(ou.unit.unit_number) for ou in owner.units
        )

        ballot = Ballot(
            voting_id=voting.id,
            owner_id=owner.id,
            total_votes=total_votes,
            units_text=units_text,
            status=BallotStatus.GENERATED,
        )

        db.add(ballot)
        db.flush()

        # Create empty vote records for each item
        for item in voting.items:
            bv = BallotVote(
                ballot_id=ballot.id,
                voting_item_id=item.id,
                votes_count=total_votes,
            )
            db.add(bv)

        created += 1

    if voting.status == VotingStatus.DRAFT:
        voting.status = VotingStatus.ACTIVE

    db.commit()
    return RedirectResponse(f"/hlasovani/{voting_id}", status_code=302)


@router.get("/{voting_id}/listky")
async def ballot_list(voting_id: int, request: Request, db: Session = Depends(get_db)):
    voting = db.query(Voting).options(
        joinedload(Voting.items),
        joinedload(Voting.ballots).joinedload(Ballot.owner),
    ).get(voting_id)
    if not voting:
        return RedirectResponse("/hlasovani", status_code=302)

    return templates.TemplateResponse("voting/ballots.html", {
        "request": request,
        "active_nav": "voting",
        "voting": voting,
    })


@router.get("/{voting_id}/zpracovani")
async def process_page(voting_id: int, request: Request, db: Session = Depends(get_db)):
    voting = db.query(Voting).options(
        joinedload(Voting.items),
        joinedload(Voting.ballots).joinedload(Ballot.owner),
        joinedload(Voting.ballots).joinedload(Ballot.votes),
    ).get(voting_id)
    if not voting:
        return RedirectResponse("/hlasovani", status_code=302)

    # Get ballots that need processing (generated or sent)
    unprocessed = [
        b for b in voting.ballots
        if b.status in (BallotStatus.GENERATED, BallotStatus.SENT, BallotStatus.RECEIVED)
    ]

    return templates.TemplateResponse("voting/process.html", {
        "request": request,
        "active_nav": "voting",
        "voting": voting,
        "unprocessed": unprocessed,
    })


@router.post("/{voting_id}/zpracovat/{ballot_id}")
async def process_ballot(
    voting_id: int,
    ballot_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    form_data = await request.form()
    ballot = db.query(Ballot).options(joinedload(Ballot.votes)).get(ballot_id)
    if not ballot or ballot.voting_id != voting_id:
        return RedirectResponse(f"/hlasovani/{voting_id}/zpracovani", status_code=302)

    for bv in ballot.votes:
        vote_key = f"vote_{bv.voting_item_id}"
        vote_value = form_data.get(vote_key)
        if vote_value:
            bv.vote = VoteValue(vote_value)
            bv.manually_verified = True

    ballot.status = BallotStatus.PROCESSED
    ballot.processed_at = datetime.utcnow()
    db.commit()

    if request.headers.get("HX-Request"):
        return templates.TemplateResponse("partials/ballot_processed.html", {
            "request": request,
            "ballot": ballot,
        })
    return RedirectResponse(f"/hlasovani/{voting_id}/zpracovani", status_code=302)


@router.post("/{voting_id}/stav")
async def update_voting_status(
    voting_id: int,
    status: str = Form(...),
    db: Session = Depends(get_db),
):
    voting = db.query(Voting).get(voting_id)
    if voting:
        voting.status = VotingStatus(status)
        voting.updated_at = datetime.utcnow()
        db.commit()
    return RedirectResponse(f"/hlasovani/{voting_id}", status_code=302)


@router.post("/{voting_id}/pridat-bod")
async def add_voting_item(
    voting_id: int,
    title: str = Form(...),
    description: str = Form(""),
    db: Session = Depends(get_db),
):
    voting = db.query(Voting).options(joinedload(Voting.items)).get(voting_id)
    if not voting:
        return RedirectResponse("/hlasovani", status_code=302)

    max_order = max((i.order for i in voting.items), default=0)
    item = VotingItem(
        voting_id=voting.id,
        order=max_order + 1,
        title=title,
        description=description,
    )
    db.add(item)
    db.commit()
    return RedirectResponse(f"/hlasovani/{voting_id}", status_code=302)


@router.get("/{voting_id}/neodevzdane")
async def not_submitted(voting_id: int, request: Request, db: Session = Depends(get_db)):
    voting = db.query(Voting).options(
        joinedload(Voting.ballots).joinedload(Ballot.owner),
    ).get(voting_id)
    if not voting:
        return RedirectResponse("/hlasovani", status_code=302)

    missing = [
        b for b in voting.ballots
        if b.status not in (BallotStatus.PROCESSED,)
    ]

    return templates.TemplateResponse("voting/not_submitted.html", {
        "request": request,
        "active_nav": "voting",
        "voting": voting,
        "missing": missing,
    })
