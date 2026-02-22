import json
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
from app.services.voting_import import (
    read_excel_headers, preview_voting_import, execute_voting_import,
)

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _ballot_stats(voting):
    """Compute ballot statistics for status bubbles."""
    total_ballots = len(voting.ballots)
    status_counts = {s.value: 0 for s in BallotStatus}
    for b in voting.ballots:
        status_counts[b.status.value] += 1
    total_processed_votes = sum(
        b.total_votes for b in voting.ballots if b.status == BallotStatus.PROCESSED
    )
    quorum_reached = (
        total_processed_votes / voting.total_votes_possible >= voting.quorum_threshold
        if voting.total_votes_possible
        else False
    )
    return {
        "total_ballots": total_ballots,
        "status_counts": status_counts,
        "total_processed_votes": total_processed_votes,
        "quorum_reached": quorum_reached,
    }


@router.get("/")
async def voting_list(
    request: Request,
    back: str = Query("", alias="back"),
    stav: str = Query("", alias="stav"),
    db: Session = Depends(get_db),
):
    q = db.query(Voting).options(
        joinedload(Voting.items),
        joinedload(Voting.ballots).joinedload(Ballot.votes),
    )
    if stav:
        q = q.filter(Voting.status == stav)
    votings = q.order_by(Voting.created_at.desc()).all()

    # Count per status (always from all votings, not filtered)
    all_votings = db.query(Voting).all()
    status_counts = {"all": len(all_votings)}
    for v in all_votings:
        status_counts[v.status.value] = status_counts.get(v.status.value, 0) + 1

    # Compute stats per voting
    voting_stats = {}
    for voting in votings:
        total = voting.total_votes_possible or 1
        processed = [b for b in voting.ballots if b.status == BallotStatus.PROCESSED]
        processed_votes = sum(b.total_votes for b in processed)

        # Per-item results
        item_results = []
        for item in voting.items:
            votes_for = 0
            votes_against = 0
            votes_abstain = 0
            for b in processed:
                for bv in b.votes:
                    if bv.voting_item_id == item.id:
                        if bv.vote == VoteValue.FOR:
                            votes_for += bv.votes_count
                        elif bv.vote == VoteValue.AGAINST:
                            votes_against += bv.votes_count
                        elif bv.vote == VoteValue.ABSTAIN:
                            votes_abstain += bv.votes_count
            item_results.append({
                "item": item,
                "votes_for": votes_for,
                "votes_against": votes_against,
                "votes_abstain": votes_abstain,
                "pct_for": round(votes_for / total * 100, 1) if total else 0,
                "pct_against": round(votes_against / total * 100, 1) if total else 0,
            })

        voting_stats[voting.id] = {
            "processed_count": len(processed),
            "processed_votes": processed_votes,
            "quorum_pct": round(processed_votes / total * 100, 1) if total else 0,
            "quorum_reached": processed_votes / total >= voting.quorum_threshold if total else False,
            "item_results": item_results,
        }

    list_url = str(request.url.path)
    if request.url.query:
        list_url += "?" + str(request.url.query)

    return templates.TemplateResponse("voting/index.html", {
        "request": request,
        "active_nav": "voting",
        "votings": votings,
        "voting_stats": voting_stats,
        "status_counts": status_counts,
        "current_stav": stav,
        "back_url": back,
        "list_url": list_url,
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
async def voting_detail(
    voting_id: int,
    request: Request,
    back: str = Query(""),
    q: str = Query(""),
    sort: str = Query("order"),
    order: str = Query("asc"),
    db: Session = Depends(get_db),
):
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

    # Search filter
    if q:
        q_lower = q.lower()
        results = [r for r in results if q_lower in r["item"].title.lower()]

    # Sort results
    sort_keys = {
        "order": lambda r: r["item"].order,
        "votes_for": lambda r: r["votes_for"],
        "pct_for": lambda r: r["pct_for"],
        "votes_against": lambda r: r["votes_against"],
        "pct_against": lambda r: r["pct_against"],
        "votes_missing": lambda r: r["votes_missing"],
    }
    key_fn = sort_keys.get(sort, sort_keys["order"])
    results.sort(key=key_fn, reverse=(order == "desc"))

    back_url = back or "/hlasovani"
    back_label = "Zpět na přehled" if back == "/" else "Zpět na hlasování"

    ctx = {
        "request": request,
        "active_nav": "voting",
        "voting": voting,
        "results": results,
        "back_url": back_url,
        "back_label": back_label,
        "active_bubble": "",
        "q": q,
        "sort": sort,
        "order": order,
        **_ballot_stats(voting),
    }

    # HTMX partial: return only the results table
    if request.headers.get("HX-Request") and not request.headers.get("HX-Boosted"):
        return templates.TemplateResponse("voting/detail_results.html", ctx)

    return templates.TemplateResponse("voting/detail.html", ctx)


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
async def ballot_list(
    voting_id: int,
    request: Request,
    stav: str = Query(""),
    q: str = Query(""),
    sort: str = Query("owner"),
    order: str = Query("asc"),
    db: Session = Depends(get_db),
):
    voting = db.query(Voting).options(
        joinedload(Voting.items),
        joinedload(Voting.ballots).joinedload(Ballot.owner),
        joinedload(Voting.ballots).joinedload(Ballot.votes),
    ).get(voting_id)
    if not voting:
        return RedirectResponse("/hlasovani", status_code=302)

    # Filter by status
    ballots = list(voting.ballots)
    if stav:
        ballots = [b for b in ballots if b.status.value == stav]

    # Search filter
    if q:
        q_lower = q.lower()
        ballots = [
            b for b in ballots
            if q_lower in (b.owner.name_with_titles or "").lower()
            or q_lower in (b.units_text or "").lower()
        ]

    # Sort
    sort_keys = {
        "owner": lambda b: (b.owner.name_normalized or "").lower(),
        "units": lambda b: b.units_text or "",
        "votes": lambda b: b.total_votes,
        "status": lambda b: b.status.value,
    }
    key_fn = sort_keys.get(sort, sort_keys["owner"])
    ballots = sorted(ballots, key=key_fn, reverse=(order == "desc"))

    ctx = {
        "request": request,
        "active_nav": "voting",
        "voting": voting,
        "ballots": ballots,
        "current_stav": stav,
        "active_bubble": stav or "all",
        "q": q,
        "sort": sort,
        "order": order,
        **_ballot_stats(voting),
    }

    # HTMX partial: return only the table
    if request.headers.get("HX-Request") and not request.headers.get("HX-Boosted"):
        return templates.TemplateResponse("voting/ballots_table.html", ctx)

    return templates.TemplateResponse("voting/ballots.html", ctx)


@router.get("/{voting_id}/listek/{ballot_id}")
async def ballot_detail(
    voting_id: int,
    ballot_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    ballot = db.query(Ballot).options(
        joinedload(Ballot.owner),
        joinedload(Ballot.votes).joinedload(BallotVote.voting_item),
        joinedload(Ballot.voting).joinedload(Voting.items),
    ).filter_by(id=ballot_id, voting_id=voting_id).first()
    if not ballot:
        return RedirectResponse(f"/hlasovani/{voting_id}/listky", status_code=302)

    return templates.TemplateResponse("voting/ballot_detail.html", {
        "request": request,
        "active_nav": "voting",
        "voting": ballot.voting,
        "ballot": ballot,
    })


@router.get("/{voting_id}/zpracovani")
async def process_page(
    voting_id: int,
    request: Request,
    q: str = Query(""),
    db: Session = Depends(get_db),
):
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

    # Search filter
    if q:
        q_lower = q.lower()
        unprocessed = [
            b for b in unprocessed
            if q_lower in (b.owner.name_with_titles or "").lower()
            or q_lower in (b.units_text or "").lower()
        ]

    ctx = {
        "request": request,
        "active_nav": "voting",
        "voting": voting,
        "unprocessed": unprocessed,
        "active_bubble": "",
        "q": q,
        **_ballot_stats(voting),
    }

    if request.headers.get("HX-Request") and not request.headers.get("HX-Boosted"):
        return templates.TemplateResponse("voting/process_cards.html", ctx)

    return templates.TemplateResponse("voting/process.html", ctx)


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
    # If submitted from ballot detail, redirect there; otherwise to bulk processing
    referer = request.headers.get("referer", "")
    if f"/listek/{ballot_id}" in referer:
        return RedirectResponse(f"/hlasovani/{voting_id}/listek/{ballot_id}", status_code=302)
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


@router.post("/{voting_id}/smazat-bod/{item_id}")
async def delete_voting_item(
    voting_id: int,
    item_id: int,
    db: Session = Depends(get_db),
):
    item = db.query(VotingItem).filter_by(id=item_id, voting_id=voting_id).first()
    if item:
        db.delete(item)
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
async def not_submitted(
    voting_id: int,
    request: Request,
    q: str = Query(""),
    db: Session = Depends(get_db),
):
    voting = db.query(Voting).options(
        joinedload(Voting.ballots).joinedload(Ballot.owner),
    ).get(voting_id)
    if not voting:
        return RedirectResponse("/hlasovani", status_code=302)

    missing = [
        b for b in voting.ballots
        if b.status not in (BallotStatus.PROCESSED,)
    ]

    # Search filter
    if q:
        q_lower = q.lower()
        missing = [
            b for b in missing
            if q_lower in (b.owner.name_with_titles or "").lower()
            or q_lower in (b.units_text or "").lower()
        ]

    ctx = {
        "request": request,
        "active_nav": "voting",
        "voting": voting,
        "missing": missing,
        "active_bubble": "neodevzdane",
        "q": q,
        **_ballot_stats(voting),
    }

    if request.headers.get("HX-Request") and not request.headers.get("HX-Boosted"):
        return templates.TemplateResponse("voting/not_submitted_table.html", ctx)

    return templates.TemplateResponse("voting/not_submitted.html", ctx)


# --- Import voting results from Excel ---


@router.get("/{voting_id}/import")
async def import_upload_page(
    voting_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    voting = db.query(Voting).options(
        joinedload(Voting.items),
        joinedload(Voting.ballots),
    ).get(voting_id)
    if not voting:
        return RedirectResponse("/hlasovani", status_code=302)

    saved_mapping = None
    if voting.import_column_mapping:
        try:
            saved_mapping = json.loads(voting.import_column_mapping)
        except (json.JSONDecodeError, TypeError):
            pass

    return templates.TemplateResponse("voting/import_upload.html", {
        "request": request,
        "active_nav": "voting",
        "voting": voting,
        "saved_mapping": saved_mapping,
        "active_bubble": "",
        **_ballot_stats(voting),
    })


@router.post("/{voting_id}/import")
async def import_upload(
    voting_id: int,
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    voting = db.query(Voting).options(
        joinedload(Voting.items),
        joinedload(Voting.ballots),
    ).get(voting_id)
    if not voting:
        return RedirectResponse("/hlasovani", status_code=302)

    if not file.filename or not file.filename.endswith((".xlsx", ".xls")):
        return templates.TemplateResponse("voting/import_upload.html", {
            "request": request,
            "active_nav": "voting",
            "voting": voting,
            "saved_mapping": None,
            "active_bubble": "",
            "flash_message": "Nahrajte soubor ve formátu .xlsx",
            "flash_type": "error",
            **_ballot_stats(voting),
        })

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = settings.upload_dir / "excel" / f"{timestamp}_{file.filename}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    headers = read_excel_headers(str(dest))

    # Load saved mapping if available
    saved_mapping = None
    if voting.import_column_mapping:
        try:
            saved_mapping = json.loads(voting.import_column_mapping)
        except (json.JSONDecodeError, TypeError):
            pass

    return templates.TemplateResponse("voting/import_mapping.html", {
        "request": request,
        "active_nav": "voting",
        "voting": voting,
        "headers": headers,
        "file_path": str(dest),
        "filename": file.filename,
        "saved_mapping": saved_mapping,
        "active_bubble": "",
        **_ballot_stats(voting),
    })


@router.post("/{voting_id}/import/nahled")
async def import_preview(
    voting_id: int,
    request: Request,
    file_path: str = Form(...),
    mapping_json: str = Form(...),
    db: Session = Depends(get_db),
):
    voting = db.query(Voting).options(
        joinedload(Voting.items),
        joinedload(Voting.ballots).joinedload(Ballot.owner).joinedload(Owner.units).joinedload(OwnerUnit.unit),
        joinedload(Voting.ballots).joinedload(Ballot.votes),
    ).get(voting_id)
    if not voting:
        return RedirectResponse("/hlasovani", status_code=302)

    try:
        mapping = json.loads(mapping_json)
    except (json.JSONDecodeError, TypeError):
        return RedirectResponse(f"/hlasovani/{voting_id}/import", status_code=302)

    # Save mapping for next time (already at preview step)
    voting.import_column_mapping = mapping_json
    db.commit()

    preview = preview_voting_import(file_path, mapping, voting, db)

    # Build item lookup for template
    item_lookup = {item.id: item for item in voting.items}

    return templates.TemplateResponse("voting/import_preview.html", {
        "request": request,
        "active_nav": "voting",
        "voting": voting,
        "preview": preview,
        "mapping": mapping,
        "mapping_json": mapping_json,
        "file_path": file_path,
        "item_lookup": item_lookup,
        "active_bubble": "",
        **_ballot_stats(voting),
    })


@router.post("/{voting_id}/import/potvrdit")
async def import_confirm(
    voting_id: int,
    request: Request,
    file_path: str = Form(...),
    mapping_json: str = Form(...),
    db: Session = Depends(get_db),
):
    voting = db.query(Voting).options(
        joinedload(Voting.items),
        joinedload(Voting.ballots).joinedload(Ballot.owner).joinedload(Owner.units).joinedload(OwnerUnit.unit),
        joinedload(Voting.ballots).joinedload(Ballot.votes),
    ).get(voting_id)
    if not voting:
        return RedirectResponse("/hlasovani", status_code=302)

    try:
        mapping = json.loads(mapping_json)
    except (json.JSONDecodeError, TypeError):
        return RedirectResponse(f"/hlasovani/{voting_id}/import", status_code=302)

    result = execute_voting_import(file_path, mapping, voting, db)

    return templates.TemplateResponse("voting/import_result.html", {
        "request": request,
        "active_nav": "voting",
        "voting": voting,
        "result": result,
        "active_bubble": "",
        **_ballot_stats(voting),
    })
