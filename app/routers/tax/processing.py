from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.database import SessionLocal, get_db
from app.models import (
    MatchStatus, Owner, OwnerUnit,
    TaxDistribution, TaxDocument, TaxSession,
)
from app.utils import compute_eta
from app.services.owner_matcher import match_name
from app.services.pdf_extractor import (
    extract_owner_from_tax_pdf, parse_unit_from_filename,
)

from ._helpers import (
    logger, templates,
    _processing_progress, _processing_lock,
    _tax_wizard,
)

router = APIRouter()


def _process_tax_files(session_id: int, file_paths: list, tax_year):
    """Background thread: extract text from PDFs and match owners."""
    db = SessionLocal()
    try:
        # Load owners for matching
        owners = db.query(Owner).filter_by(is_active=True).all()
        owner_dicts = [
            {"id": o.id, "name": o.display_name, "name_normalized": o.name_normalized}
            for o in owners
        ]

        # Build unit->owner mapping — include owners overlapping with tax year
        if tax_year:
            year_start = date(tax_year, 1, 1)
            year_end = date(tax_year, 12, 31)
            owner_units = (
                db.query(OwnerUnit)
                .options(joinedload(OwnerUnit.unit))
                .filter(
                    or_(OwnerUnit.valid_to.is_(None), OwnerUnit.valid_to >= year_start),
                    or_(OwnerUnit.valid_from.is_(None), OwnerUnit.valid_from <= year_end),
                )
                .all()
            )
        else:
            owner_units = (
                db.query(OwnerUnit)
                .options(joinedload(OwnerUnit.unit))
                .all()
            )
        unit_to_owners = {}
        for ou in owner_units:
            unit_num = str(ou.unit.unit_number)
            if unit_num not in unit_to_owners:
                unit_to_owners[unit_num] = []
            owner_data = next((o for o in owner_dicts if o["id"] == ou.owner_id), None)
            if owner_data:
                unit_to_owners[unit_num].append(owner_data)

        # Collect IDs of existing docs BEFORE processing (for later comparison)
        pre_existing_doc_ids = {
            d.id for d in db.query(TaxDocument.id).filter_by(session_id=session_id).all()
        }

        new_doc_ids = []
        for i, file_path in enumerate(file_paths):
            basename = Path(file_path).name
            with _processing_lock:
                _processing_progress[session_id]["current_file"] = basename

            unit_number, unit_letter = parse_unit_from_filename(basename)
            try:
                extracted = extract_owner_from_tax_pdf(file_path)
            except Exception as e:
                logger.exception("PDF extraction failed: %s", basename)
                extracted = {"full_text": "", "owner_name": None, "owner_names": []}

            # Prefer individual names from details section over combined "Vlastník:" line
            individual_names = [n for n in (extracted.get("owner_names") or []) if n]
            display_name = ", ".join(individual_names) if individual_names else extracted.get("owner_name")
            # Limit display name length (safety against malformed PDF parsing)
            if display_name and len(display_name) > 300:
                display_name = display_name[:297] + "..."

            doc = TaxDocument(
                session_id=session_id,
                filename=basename,
                unit_number=unit_number,
                unit_letter=unit_letter,
                file_path=file_path,
                extracted_owner_name=display_name,
            )
            db.add(doc)
            db.flush()
            new_doc_ids.append(doc.id)

            # Try auto-matching — match each name from PDF individually
            individual_names = [n for n in (extracted.get("owner_names") or []) if n]
            # Fallback to combined "Vlastník:" line if no individual names
            if not individual_names and extracted.get("owner_name"):
                individual_names = [extracted["owner_name"]]

            matched_ids = set()  # avoid duplicates

            for candidate in individual_names:
                is_sjm = bool(re.match(r"^SJM?\s", candidate, re.IGNORECASE))

                # First try: match against owners on this unit
                local_matches = []
                if unit_number in unit_to_owners:
                    matches = match_name(
                        candidate,
                        unit_to_owners[unit_number],
                        threshold=0.6,
                    )
                    if is_sjm:
                        local_matches = matches      # SJM → all matches above threshold
                    elif matches:
                        local_matches = [matches[0]]  # Normal → best only

                # For non-SJM: also try global match
                if not is_sjm:
                    global_matches = match_name(candidate, owner_dicts, threshold=0.75, require_stem_overlap=True)
                    if global_matches:
                        if not local_matches or global_matches[0]["confidence"] > local_matches[0]["confidence"]:
                            local_matches = [global_matches[0]]

                for m in local_matches:
                    if m["owner_id"] not in matched_ids:
                        matched_ids.add(m["owner_id"])
                        dist = TaxDistribution(
                            document_id=doc.id,
                            owner_id=m["owner_id"],
                            match_status=MatchStatus.AUTO_MATCHED,
                            match_confidence=m["confidence"],
                        )
                        db.add(dist)

                if not local_matches:
                    dist = TaxDistribution(
                        document_id=doc.id,
                        owner_id=None,
                        match_status=MatchStatus.UNMATCHED,
                        match_confidence=None,
                    )
                    db.add(dist)

            if not individual_names:
                dist = TaxDistribution(
                    document_id=doc.id,
                    owner_id=None,
                    match_status=MatchStatus.UNMATCHED,
                    match_confidence=None,
                )
                db.add(dist)

            with _processing_lock:
                _processing_progress[session_id]["current"] = i + 1

        db.flush()

        # --- Post-processing: propagate existing assignments to new documents ---

        # 1) For unmatched new docs, copy assignments from existing docs with same unit
        if pre_existing_doc_ids:
            # Build unit -> distributions map from pre-existing docs
            old_dists = (
                db.query(TaxDistribution)
                .filter(
                    TaxDistribution.document_id.in_(list(pre_existing_doc_ids)),
                    TaxDistribution.match_status != MatchStatus.UNMATCHED,
                )
                .all()
            )
            # Map: (unit_number, unit_letter) -> list of dists
            unit_assignments = {}
            old_doc_map = {d.id: d for d in db.query(TaxDocument).filter(
                TaxDocument.id.in_(list(pre_existing_doc_ids))
            ).all()}
            for d in old_dists:
                old_doc = old_doc_map.get(d.document_id)
                if old_doc:
                    key = (old_doc.unit_number, old_doc.unit_letter)
                    unit_assignments.setdefault(key, []).append(d)

            # Check new unmatched docs
            new_docs = db.query(TaxDocument).options(
                joinedload(TaxDocument.distributions)
            ).filter(TaxDocument.id.in_(new_doc_ids)).all()
            for doc in new_docs:
                doc_dists = doc.distributions
                is_unmatched = all(d.match_status == MatchStatus.UNMATCHED for d in doc_dists)
                if not is_unmatched:
                    continue

                key = (doc.unit_number, doc.unit_letter)
                if key not in unit_assignments:
                    continue

                # Remove unmatched placeholders
                for d in doc_dists:
                    db.delete(d)

                # Replicate existing assignments (owner or external)
                for existing in unit_assignments[key]:
                    new_dist = TaxDistribution(
                        document_id=doc.id,
                        owner_id=existing.owner_id,
                        match_status=MatchStatus.AUTO_MATCHED,
                        match_confidence=existing.match_confidence,
                        email_address_used=existing.email_address_used,
                        ad_hoc_name=existing.ad_hoc_name,
                        ad_hoc_email=existing.ad_hoc_email,
                    )
                    db.add(new_dist)
                db.flush()

        # 2) Propagate email_address_used from existing distributions to newly matched ones
        all_doc_ids = list(pre_existing_doc_ids) + new_doc_ids
        existing_dists = (
            db.query(TaxDistribution)
            .filter(
                TaxDistribution.document_id.in_(all_doc_ids),
                TaxDistribution.owner_id.isnot(None),
                TaxDistribution.email_address_used.isnot(None),
            )
            .all()
        )
        # Build map: owner_id -> email_address_used
        owner_emails = {}
        for d in existing_dists:
            if d.owner_id not in owner_emails:
                owner_emails[d.owner_id] = d.email_address_used

        if owner_emails:
            new_dists = (
                db.query(TaxDistribution)
                .filter(
                    TaxDistribution.document_id.in_(all_doc_ids),
                    TaxDistribution.owner_id.in_(list(owner_emails.keys())),
                    TaxDistribution.email_address_used.is_(None),
                )
                .all()
            )
            for d in new_dists:
                d.email_address_used = owner_emails[d.owner_id]

        db.commit()
    except Exception as e:
        logger.exception("PDF processing failed for session %s", session_id)
        with _processing_lock:
            _processing_progress[session_id]["error"] = str(e)
        db.rollback()
        # Cleanup orphaned files on disk (#28)
        for fp in file_paths:
            try:
                Path(fp).unlink(missing_ok=True)
            except Exception:
                logger.debug("Failed to clean up temp file: %s", fp)
    finally:
        with _processing_lock:
            _processing_progress[session_id]["done"] = True
        db.close()


def _progress_eta(progress: dict) -> dict:
    """Compute ETA fields from progress dict."""

    eta = compute_eta(progress["current"], progress["total"], progress["started_at"])
    return {
        "total": progress["total"],
        "current": progress["current"],
        "current_file": progress["current_file"],
        **eta,
    }


@router.get("/{session_id}/zpracovani")
async def tax_processing(
    session_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Show progress page while PDFs are being processed in background."""
    with _processing_lock:
        progress = _processing_progress.get(session_id)
        if not progress or progress.get("done"):
            _processing_progress.pop(session_id, None)
            return RedirectResponse(f"/dane/{session_id}", status_code=302)
        progress = dict(progress)  # snapshot under lock

    session = db.query(TaxSession).get(session_id)
    if not session:
        return RedirectResponse("/dane", status_code=302)

    return templates.TemplateResponse("tax/processing.html", {
        "request": request,
        "active_nav": "tax",
        "session": session,
        "error": progress.get("error"),
        **_progress_eta(progress),
        **_tax_wizard(session, 1),
    })


@router.get("/{session_id}/zpracovani-stav")
async def tax_processing_status(session_id: int, request: Request):
    """HTMX polling endpoint — returns progress partial or redirect when done."""
    with _processing_lock:
        progress = _processing_progress.get(session_id)
        if not progress:
            response = HTMLResponse("")
            response.headers["HX-Redirect"] = f"/dane/{session_id}"
            return response
        if progress.get("done"):
            error = progress.get("error")
            if error:
                # Show error in progress partial — don't redirect
                progress = dict(progress)
                _processing_progress.pop(session_id, None)
                return templates.TemplateResponse("partials/tax_progress.html", {
                    "request": request,
                    "error": error,
                    **_progress_eta(progress),
                })
            _processing_progress.pop(session_id, None)
            response = HTMLResponse("")
            response.headers["HX-Redirect"] = f"/dane/{session_id}"
            return response
        progress = dict(progress)  # snapshot under lock

    return templates.TemplateResponse("partials/tax_progress.html", {
        "request": request,
        "error": None,
        **_progress_eta(progress),
    })
