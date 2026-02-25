from __future__ import annotations

import shutil
from datetime import date, datetime
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.database import get_db
from app.models import (
    MatchStatus, Owner, OwnerUnit, TaxDistribution, TaxDocument, TaxSession, Unit,
)
from app.services.owner_matcher import match_name
from app.services.pdf_extractor import (
    extract_owner_from_tax_pdf, parse_unit_from_filename,
)

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _session_stats(documents):
    """Compute stat card numbers for the matching page."""
    stat_total = len(documents)
    stat_confirmed = 0
    stat_to_confirm = 0
    stat_unmatched = 0

    for doc in documents:
        if not doc.distributions:
            stat_unmatched += 1
            continue
        statuses = [d.match_status for d in doc.distributions]
        if all(s in (MatchStatus.CONFIRMED, MatchStatus.MANUAL) for s in statuses):
            stat_confirmed += 1
        elif any(s == MatchStatus.UNMATCHED for s in statuses) or not doc.distributions:
            stat_unmatched += 1
        else:
            # has at least one AUTO_MATCHED
            stat_to_confirm += 1

    return {
        "stat_total": stat_total,
        "stat_confirmed": stat_confirmed,
        "stat_to_confirm": stat_to_confirm,
        "stat_unmatched": stat_unmatched,
    }


def _find_coowners(owner_id: int, unit_number: str, tax_year: int | None, db: Session) -> list[int]:
    """Find co-owners on the same unit with overlapping period in the tax year.

    Returns list of owner_ids including the original.
    """
    if not unit_number:
        return [owner_id]

    unit = db.query(Unit).filter_by(unit_number=int(unit_number)).first()
    if not unit:
        return [owner_id]

    if tax_year:
        year_start = date(tax_year, 1, 1)
        year_end = date(tax_year, 12, 31)
    else:
        year_start = None
        year_end = None

    owner_ids = set()
    for ou in unit.owners:
        # Check period overlap with tax year
        if year_start and year_end:
            ou_from = ou.valid_from or date(1900, 1, 1)
            ou_to = ou.valid_to or date(2099, 12, 31)
            if ou_to < year_start or ou_from > year_end:
                continue
        else:
            # No tax year — only current owners
            if ou.valid_to is not None:
                continue
        owner_ids.add(ou.owner_id)

    # Always include the original matched owner
    owner_ids.add(owner_id)
    return list(owner_ids)


def _unit_by_number(db: Session) -> dict:
    """Build {unit_number_str: Unit} lookup for clickable unit links."""
    units = db.query(Unit).all()
    return {str(u.unit_number): u for u in units}


def _reload_doc_row(doc_id: int, session_id: int, request: Request, db: Session):
    """Reload a document with its distributions and return a partial row response."""
    doc = (
        db.query(TaxDocument)
        .filter_by(id=doc_id)
        .options(
            joinedload(TaxDocument.distributions)
            .joinedload(TaxDistribution.owner)
            .joinedload(Owner.units)
            .joinedload(OwnerUnit.unit),
        )
        .first()
    )
    owners = (
        db.query(Owner)
        .filter_by(is_active=True)
        .options(joinedload(Owner.units).joinedload(OwnerUnit.unit))
        .order_by(Owner.name_normalized)
        .all()
    )

    # Build list_url from current browser URL for back navigation
    from urllib.parse import urlparse
    current_url = request.headers.get("HX-Current-URL", "")
    if current_url:
        parsed = urlparse(current_url)
        list_url = parsed.path
        if parsed.query:
            list_url += "?" + parsed.query
    else:
        list_url = f"/dane/{session_id}"

    # Unit lookup for clickable unit links
    unit_by_number = _unit_by_number(db)

    return templates.TemplateResponse("partials/tax_match_row.html", {
        "request": request,
        "doc": doc,
        "owners": owners,
        "session": doc.session,
        "list_url": list_url,
        "unit_by_number": unit_by_number,
    })


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/")
async def tax_list(request: Request, back: str = Query("", alias="back"), db: Session = Depends(get_db)):
    sessions = db.query(TaxSession).order_by(TaxSession.created_at.desc()).all()
    list_url = str(request.url.path)
    if request.url.query:
        list_url += "?" + str(request.url.query)

    return templates.TemplateResponse("tax/index.html", {
        "request": request,
        "active_nav": "tax",
        "sessions": sessions,
        "back_url": back,
        "list_url": list_url,
    })


@router.get("/nova")
async def tax_create_page(request: Request):
    return templates.TemplateResponse("tax/upload.html", {
        "request": request,
        "active_nav": "tax",
        "current_year": datetime.now().year,
    })


@router.post("/nova")
async def tax_create(
    request: Request,
    title: str = Form(...),
    year: int = Form(None),
    email_subject: str = Form(""),
    email_body: str = Form(""),
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    session = TaxSession(
        title=title,
        year=year,
        email_subject=email_subject or f"Rozúčtování příjmů {year or ''}",
        email_body=email_body,
    )
    db.add(session)
    db.flush()

    # Save PDF files and process them
    upload_dir = settings.upload_dir / "tax_pdfs" / f"session_{session.id}"
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Get all owners for matching
    owners = db.query(Owner).filter_by(is_active=True).all()
    owner_dicts = [
        {"id": o.id, "name": o.display_name, "name_normalized": o.name_normalized}
        for o in owners
    ]

    # Build unit->owner mapping (only current)
    owner_units = db.query(OwnerUnit).filter(OwnerUnit.valid_to.is_(None)).all()
    unit_to_owners = {}
    for ou in owner_units:
        unit_num = str(ou.unit.unit_number)
        if unit_num not in unit_to_owners:
            unit_to_owners[unit_num] = []
        owner_data = next((o for o in owner_dicts if o["id"] == ou.owner_id), None)
        if owner_data:
            unit_to_owners[unit_num].append(owner_data)

    for file in files:
        if not file.filename or not file.filename.lower().endswith(".pdf"):
            continue

        # webkitdirectory sends relative paths (e.g. "dir/9A.pdf") — use basename only
        basename = Path(file.filename).name
        dest = upload_dir / basename
        with open(dest, "wb") as f:
            shutil.copyfileobj(file.file, f)

        unit_number, unit_letter = parse_unit_from_filename(basename)

        # Extract owner name from PDF
        extracted = extract_owner_from_tax_pdf(str(dest))

        doc = TaxDocument(
            session_id=session.id,
            filename=basename,
            unit_number=unit_number,
            unit_letter=unit_letter,
            file_path=str(dest),
            extracted_owner_name=extracted.get("owner_name"),
        )
        db.add(doc)
        db.flush()

        # Try auto-matching
        matched_owner = None
        confidence = 0.0

        # First try: match by unit number + name
        if unit_number in unit_to_owners and extracted.get("owner_name"):
            matches = match_name(
                extracted["owner_name"],
                unit_to_owners[unit_number],
                threshold=0.6,
            )
            if matches:
                matched_owner = matches[0]
                confidence = matches[0]["confidence"]

        # Second try: match against all owners by name only
        if not matched_owner and extracted.get("owner_name"):
            matches = match_name(extracted["owner_name"], owner_dicts, threshold=0.75)
            if matches:
                matched_owner = matches[0]
                confidence = matches[0]["confidence"]

        if matched_owner:
            # Find co-owners on the same unit
            coowner_ids = _find_coowners(
                matched_owner["owner_id"], unit_number, session.year, db
            )
            for oid in coowner_ids:
                dist = TaxDistribution(
                    document_id=doc.id,
                    owner_id=oid,
                    match_status=MatchStatus.AUTO_MATCHED,
                    match_confidence=confidence if oid == matched_owner["owner_id"] else None,
                )
                db.add(dist)
        else:
            # No match — create single UNMATCHED placeholder
            dist = TaxDistribution(
                document_id=doc.id,
                owner_id=None,
                match_status=MatchStatus.UNMATCHED,
                match_confidence=None,
            )
            db.add(dist)

    db.commit()
    return RedirectResponse(f"/dane/{session.id}", status_code=302)


@router.get("/{session_id}")
async def tax_detail(session_id: int, request: Request, back: str = Query("", alias="back"), db: Session = Depends(get_db)):
    session = db.query(TaxSession).get(session_id)
    if not session:
        return RedirectResponse("/dane", status_code=302)

    documents = (
        db.query(TaxDocument)
        .filter_by(session_id=session_id)
        .options(
            joinedload(TaxDocument.distributions)
            .joinedload(TaxDistribution.owner)
            .joinedload(Owner.units)
            .joinedload(OwnerUnit.unit),
        )
        .order_by(TaxDocument.unit_number, TaxDocument.unit_letter)
        .all()
    )

    owners = (
        db.query(Owner)
        .filter_by(is_active=True)
        .options(joinedload(Owner.units).joinedload(OwnerUnit.unit))
        .order_by(Owner.name_normalized)
        .all()
    )

    back_url = back or "/dane"
    back_label = "Zpět na přehled" if back == "/" else "Zpět na rozúčtování"

    list_url = str(request.url.path)
    if request.url.query:
        list_url += "?" + str(request.url.query)

    return templates.TemplateResponse("tax/matching.html", {
        "request": request,
        "active_nav": "tax",
        "session": session,
        "documents": documents,
        "owners": owners,
        "back_url": back_url,
        "back_label": back_label,
        "list_url": list_url,
        "unit_by_number": _unit_by_number(db),
        **_session_stats(documents),
    })


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
            match_confidence=1.0 if oid == owner_id else None,
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


@router.post("/{session_id}/smazat")
async def delete_session(
    session_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Delete session, its documents, distributions, and files from disk."""
    session = db.query(TaxSession).get(session_id)
    if not session:
        return RedirectResponse("/dane", status_code=302)

    # Delete files from disk
    upload_dir = settings.upload_dir / "tax_pdfs" / f"session_{session_id}"
    try:
        if upload_dir.exists():
            shutil.rmtree(upload_dir)
    except Exception:
        pass

    db.delete(session)
    db.commit()

    return RedirectResponse("/dane", status_code=302)
