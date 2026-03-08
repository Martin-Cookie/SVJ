from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    MatchStatus,
    TaxDistribution, TaxDocument, TaxSession,
)

from ._helpers import (
    logger, templates,
    _find_coowners, _reload_doc_row,
)

router = APIRouter()


@router.post("/{session_id}/potvrdit/{dist_id}")
async def confirm_match(
    session_id: int,
    dist_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    dist = db.query(TaxDistribution).get(dist_id)
    if dist:
        dist.match_status = MatchStatus.CONFIRMED
        db.commit()

    if request.headers.get("HX-Request"):
        return _reload_doc_row(dist.document_id, session_id, request, db)
    return RedirectResponse(f"/dane/{session_id}", status_code=302)


@router.post("/{session_id}/prirazeni/{doc_id}")
async def manual_assign(
    session_id: int,
    doc_id: int,
    owner_id: int = Form(...),
    request: Request = None,
    db: Session = Depends(get_db),
):
    doc = db.query(TaxDocument).get(doc_id)
    if not doc:
        return RedirectResponse(f"/dane/{session_id}", status_code=302)

    session = db.query(TaxSession).get(session_id)

    # Delete existing UNMATCHED/AUTO_MATCHED distributions
    db.query(TaxDistribution).filter(
        TaxDistribution.document_id == doc_id,
        TaxDistribution.match_status.in_([MatchStatus.UNMATCHED, MatchStatus.AUTO_MATCHED]),
    ).delete(synchronize_session="fetch")

    # Find co-owners for the selected owner
    coowner_ids = _find_coowners(owner_id, doc.unit_number, session.year if session else None, db)
    for oid in coowner_ids:
        dist = TaxDistribution(
            document_id=doc_id,
            owner_id=oid,
            match_status=MatchStatus.MANUAL,
            match_confidence=1.0,
        )
        db.add(dist)

    db.commit()

    if request and request.headers.get("HX-Request"):
        return _reload_doc_row(doc_id, session_id, request, db)
    return RedirectResponse(f"/dane/{session_id}", status_code=302)


@router.post("/{session_id}/potvrdit-vse")
async def confirm_all(
    session_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Confirm all AUTO_MATCHED distributions in the session."""
    docs = db.query(TaxDocument).filter_by(session_id=session_id).all()
    doc_ids = [d.id for d in docs]
    if doc_ids:
        db.query(TaxDistribution).filter(
            TaxDistribution.document_id.in_(doc_ids),
            TaxDistribution.match_status == MatchStatus.AUTO_MATCHED,
        ).update({"match_status": MatchStatus.CONFIRMED}, synchronize_session="fetch")
        db.commit()

    return RedirectResponse(f"/dane/{session_id}", status_code=302)


@router.post("/{session_id}/potvrdit-vybrane")
async def confirm_selected(
    session_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Confirm selected AUTO_MATCHED distributions by dist_ids from checkboxes."""
    form = await request.form()
    dist_ids = form.getlist("dist_ids")
    dist_ids = [int(x) for x in dist_ids if x]

    if dist_ids:
        db.query(TaxDistribution).filter(
            TaxDistribution.id.in_(dist_ids),
            TaxDistribution.match_status == MatchStatus.AUTO_MATCHED,
        ).update({"match_status": MatchStatus.CONFIRMED}, synchronize_session="fetch")
        db.commit()

    return RedirectResponse(f"/dane/{session_id}", status_code=302)


@router.post("/{session_id}/odebrat/{dist_id}")
async def remove_distribution(
    session_id: int,
    dist_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Remove one owner from a document. If no distributions remain, create UNMATCHED."""
    dist = db.query(TaxDistribution).get(dist_id)
    if not dist:
        return RedirectResponse(f"/dane/{session_id}", status_code=302)

    doc_id = dist.document_id
    db.delete(dist)
    db.flush()

    # Check if any distributions remain
    remaining = db.query(TaxDistribution).filter_by(document_id=doc_id).count()
    if remaining == 0:
        placeholder = TaxDistribution(
            document_id=doc_id,
            owner_id=None,
            match_status=MatchStatus.UNMATCHED,
            match_confidence=None,
        )
        db.add(placeholder)

    db.commit()

    if request.headers.get("HX-Request"):
        return _reload_doc_row(doc_id, session_id, request, db)
    return RedirectResponse(f"/dane/{session_id}", status_code=302)


@router.post("/{session_id}/pridat-externi/{doc_id}")
async def add_external_recipient(
    session_id: int,
    doc_id: int,
    ext_name: str = Form(...),
    ext_email: str = Form(""),
    request: Request = None,
    db: Session = Depends(get_db),
):
    """Add an ad-hoc external recipient to a document."""
    doc = db.query(TaxDocument).get(doc_id)
    if not doc:
        return RedirectResponse(f"/dane/{session_id}", status_code=302)

    # Remove UNMATCHED placeholder if present
    db.query(TaxDistribution).filter(
        TaxDistribution.document_id == doc_id,
        TaxDistribution.match_status == MatchStatus.UNMATCHED,
    ).delete(synchronize_session="fetch")

    dist = TaxDistribution(
        document_id=doc_id,
        owner_id=None,
        match_status=MatchStatus.MANUAL,
        match_confidence=None,
        ad_hoc_name=ext_name.strip(),
        ad_hoc_email=ext_email.strip() or None,
    )
    db.add(dist)
    db.commit()

    if request and request.headers.get("HX-Request"):
        return _reload_doc_row(doc_id, session_id, request, db)
    return RedirectResponse(f"/dane/{session_id}", status_code=302)
