from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.database import get_db
from app.models import (
    MatchStatus, Owner, OwnerUnit, TaxDistribution, TaxDocument, TaxSession,
)
from app.services.owner_matcher import match_name
from app.services.pdf_extractor import (
    extract_owner_from_tax_pdf, parse_unit_from_filename,
)

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


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
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    upload_dir = settings.upload_dir / "tax_pdfs" / f"session_{session.id}"
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Get all owners for matching
    owners = db.query(Owner).filter_by(is_active=True).all()
    owner_dicts = [
        {"id": o.id, "name": o.display_name, "name_normalized": o.name_normalized}
        for o in owners
    ]

    # Build unit->owner mapping
    owner_units = db.query(OwnerUnit).all()
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

        dest = upload_dir / file.filename
        with open(dest, "wb") as f:
            shutil.copyfileobj(file.file, f)

        unit_number, unit_letter = parse_unit_from_filename(file.filename)

        # Extract owner name from PDF
        extracted = extract_owner_from_tax_pdf(str(dest))

        doc = TaxDocument(
            session_id=session.id,
            filename=file.filename,
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

        dist = TaxDistribution(
            document_id=doc.id,
            owner_id=matched_owner["owner_id"] if matched_owner else None,
            match_status=(
                MatchStatus.AUTO_MATCHED if matched_owner else MatchStatus.UNMATCHED
            ),
            match_confidence=confidence if matched_owner else None,
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
        .options(joinedload(TaxDocument.distributions).joinedload(TaxDistribution.owner))
        .order_by(TaxDocument.unit_number, TaxDocument.unit_letter)
        .all()
    )

    owners = db.query(Owner).filter_by(is_active=True).order_by(Owner.name_normalized).all()

    matched = sum(1 for d in documents if d.distributions and d.distributions[0].match_status != MatchStatus.UNMATCHED)
    unmatched = len(documents) - matched

    back_url = back or "/dane"
    back_label = "Zpět na přehled" if back == "/" else "Zpět na rozúčtování"

    return templates.TemplateResponse("tax/matching.html", {
        "request": request,
        "active_nav": "tax",
        "session": session,
        "documents": documents,
        "owners": owners,
        "matched_count": matched,
        "unmatched_count": unmatched,
        "back_url": back_url,
        "back_label": back_label,
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
        dist = db.query(TaxDistribution).options(
            joinedload(TaxDistribution.owner),
            joinedload(TaxDistribution.document),
        ).get(dist_id)
        return templates.TemplateResponse("partials/tax_match_row.html", {
            "request": request,
            "doc": dist.document,
            "dist": dist,
            "owners": [],
        })
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

    dist = db.query(TaxDistribution).filter_by(document_id=doc_id).first()
    if dist:
        dist.owner_id = owner_id
        dist.match_status = MatchStatus.MANUAL
        dist.match_confidence = 1.0
    else:
        dist = TaxDistribution(
            document_id=doc_id,
            owner_id=owner_id,
            match_status=MatchStatus.MANUAL,
            match_confidence=1.0,
        )
        db.add(dist)

    db.commit()

    if request and request.headers.get("HX-Request"):
        dist = db.query(TaxDistribution).options(
            joinedload(TaxDistribution.owner),
            joinedload(TaxDistribution.document),
        ).get(dist.id)
        return templates.TemplateResponse("partials/tax_match_row.html", {
            "request": request,
            "doc": dist.document,
            "dist": dist,
            "owners": [],
        })
    return RedirectResponse(f"/dane/{session_id}", status_code=302)
