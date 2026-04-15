from __future__ import annotations

import re
import threading
import time as _time
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.database import SessionLocal, get_db
from app.models import (
    MatchStatus, Owner, OwnerUnit, SendStatus,
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
    _recompute_progress, _recompute_lock,
    _tax_wizard,
)

router = APIRouter()


def _prepare_owner_lookup(db: Session, tax_year) -> tuple[list[dict], dict[str, list[dict]]]:
    """Load active owners and build unit→owners map filtered by tax year.

    Returns (owner_dicts, unit_to_owners).
    """
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
    owner_by_id = {o["id"]: o for o in owner_dicts}
    unit_to_owners: dict[str, list[dict]] = {}
    for ou in owner_units:
        unit_num = str(ou.unit.unit_number)
        if unit_num not in unit_to_owners:
            unit_to_owners[unit_num] = []
        owner_data = owner_by_id.get(ou.owner_id)
        if owner_data:
            unit_to_owners[unit_num].append(owner_data)

    return owner_dicts, unit_to_owners


def _process_single_pdf(file_path: str, session_id: int, db: Session) -> tuple:
    """Extract owner info from a single PDF and create TaxDocument.

    Returns (doc, extracted) where doc is the flushed TaxDocument
    and extracted is the raw extraction dict.
    """
    basename = Path(file_path).name
    unit_number, unit_letter = parse_unit_from_filename(basename)
    try:
        extracted = extract_owner_from_tax_pdf(file_path)
    except Exception:
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
    return doc, extracted


def _auto_match_distributions(
    doc: TaxDocument,
    extracted: dict,
    unit_to_owners: dict[str, list[dict]],
    owner_dicts: list[dict],
    db: Session,
) -> None:
    """Match extracted names to owners and create TaxDistribution records."""
    # Try auto-matching — match each name from PDF individually
    individual_names = [n for n in (extracted.get("owner_names") or []) if n]
    # Fallback to combined "Vlastník:" line if no individual names
    if not individual_names and extracted.get("owner_name"):
        individual_names = [extracted["owner_name"]]

    matched_ids: set = set()  # avoid duplicates

    for candidate in individual_names:
        is_sjm = bool(re.match(r"^SJM?\s", candidate, re.IGNORECASE))

        # First try: match against owners on this unit
        local_matches = []
        if doc.unit_number in unit_to_owners:
            matches = match_name(
                candidate,
                unit_to_owners[doc.unit_number],
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


def _propagate_assignments(
    db: Session,
    pre_existing_doc_ids: set[int],
    new_doc_ids: list[int],
) -> None:
    """Copy assignments from pre-existing docs to unmatched new docs with same unit."""
    if not pre_existing_doc_ids:
        return

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


def _propagate_emails(
    db: Session,
    all_doc_ids: list[int],
    owner_emails: dict[int, str],
) -> None:
    """Propagate email_address_used from existing distributions to newly matched ones."""
    if not owner_emails:
        return

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


def _process_tax_files(session_id: int, file_paths: list, tax_year):
    """Background thread: extract text from PDFs and match owners."""
    db = SessionLocal()
    try:
        owner_dicts, unit_to_owners = _prepare_owner_lookup(db, tax_year)

        # Collect IDs of existing docs BEFORE processing (for later comparison)
        pre_existing_doc_ids = {
            d.id for d in db.query(TaxDocument.id).filter_by(session_id=session_id).all()
        }

        new_doc_ids = []
        for i, file_path in enumerate(file_paths):
            with _processing_lock:
                _processing_progress[session_id]["current_file"] = Path(file_path).name

            doc, extracted = _process_single_pdf(file_path, session_id, db)
            new_doc_ids.append(doc.id)
            _auto_match_distributions(doc, extracted, unit_to_owners, owner_dicts, db)

            with _processing_lock:
                _processing_progress[session_id]["current"] = i + 1

        db.flush()

        # --- Post-processing: propagate existing assignments to new documents ---
        _propagate_assignments(db, pre_existing_doc_ids, new_doc_ids)

        # Build owner_emails map for email propagation
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
        owner_emails: dict[int, str] = {}
        for d in existing_dists:
            if d.owner_id not in owner_emails:
                owner_emails[d.owner_id] = d.email_address_used

        _propagate_emails(db, all_doc_ids, owner_emails)

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

    return templates.TemplateResponse(request, "tax/processing.html", {
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
                return templates.TemplateResponse(request, "partials/tax_progress.html", {
                    "error": error,
                    **_progress_eta(progress),
                })
            _processing_progress.pop(session_id, None)
            response = HTMLResponse("")
            response.headers["HX-Redirect"] = f"/dane/{session_id}"
            return response
        progress = dict(progress)  # snapshot under lock

    return templates.TemplateResponse(request, "partials/tax_progress.html", {
        "error": None,
        **_progress_eta(progress),
    })


def _find_best_match(
    cand_texts: list[str],
    unit_number: str | None,
    unit_to_owners: dict[str, list[dict]],
    owner_dicts: list[dict],
) -> dict | None:
    """Najde nejlepší match pro kandidátní texty — stejná dvoustupňová logika
    jako _auto_match_distributions (local unit → global fallback).
    Vrací {"owner_id", "confidence"} nebo None."""
    best_match = None
    best_conf = 0.0

    for cand in cand_texts:
        # 1) Local unit match (threshold 0.6)
        if unit_number and unit_number in unit_to_owners:
            local = match_name(cand, unit_to_owners[unit_number], threshold=0.6)
            if local and local[0]["confidence"] > best_conf:
                best_match = local[0]
                best_conf = local[0]["confidence"]

        # 2) Global match (threshold 0.75, require_stem_overlap)
        global_matches = match_name(cand, owner_dicts, threshold=0.75,
                                    require_stem_overlap=True)
        if global_matches and global_matches[0]["confidence"] > best_conf:
            best_match = global_matches[0]
            best_conf = global_matches[0]["confidence"]

    return best_match


def _recompute_scores_thread(session_id: int, tax_year):
    """Background thread: přepřiřazení vlastníků k PDF dokumentům."""
    db = SessionLocal()
    try:
        owner_dicts, unit_to_owners = _prepare_owner_lookup(db, tax_year)

        docs = (
            db.query(TaxDocument)
            .filter_by(session_id=session_id)
            .options(
                joinedload(TaxDocument.distributions).joinedload(TaxDistribution.owner)
            )
            .all()
        )

        # Spočítat distribuce k zpracování (AUTO_MATCHED + UNMATCHED)
        work_items = []
        for doc in docs:
            if not doc.extracted_owner_name:
                continue
            candidates = [p.strip() for p in doc.extracted_owner_name.split(",") if p.strip()]
            if not candidates:
                candidates = [doc.extracted_owner_name]
            cand_texts = list(dict.fromkeys([doc.extracted_owner_name, *candidates]))
            unit_num = str(doc.unit_number) if doc.unit_number else None

            for dist in doc.distributions:
                if dist.match_status in (MatchStatus.CONFIRMED, MatchStatus.MANUAL):
                    continue
                work_items.append((dist, cand_texts, unit_num))

        with _recompute_lock:
            _recompute_progress[session_id]["total"] = len(work_items)

        reassigned = 0
        newly_matched = 0
        score_updated = 0

        for i, (dist, cand_texts, unit_num) in enumerate(work_items):
            best = _find_best_match(cand_texts, unit_num, unit_to_owners, owner_dicts)

            if dist.match_status == MatchStatus.UNMATCHED:
                if best:
                    dist.owner_id = best["owner_id"]
                    dist.match_confidence = best["confidence"]
                    dist.match_status = MatchStatus.AUTO_MATCHED
                    newly_matched += 1

            elif dist.match_status == MatchStatus.AUTO_MATCHED:
                if best:
                    old_owner_id = dist.owner_id
                    old_conf = dist.match_confidence or 0
                    if best["owner_id"] != old_owner_id:
                        dist.owner_id = best["owner_id"]
                        dist.match_confidence = best["confidence"]
                        reassigned += 1
                    elif best["confidence"] > old_conf + 0.001:
                        dist.match_confidence = best["confidence"]
                        score_updated += 1

            with _recompute_lock:
                _recompute_progress[session_id]["current"] = i + 1

        db.commit()

        total = reassigned + newly_matched + score_updated
        with _recompute_lock:
            _recompute_progress[session_id]["result"] = {
                "total": total,
                "reassigned": reassigned,
                "newly": newly_matched,
            }
    except Exception as e:
        logger.exception("Recompute scores failed for session %s", session_id)
        with _recompute_lock:
            _recompute_progress[session_id]["error"] = str(e)
        db.rollback()
    finally:
        with _recompute_lock:
            _recompute_progress[session_id]["done"] = True
        db.close()


@router.post("/{session_id}/prepocitat-skore")
def tax_recompute_scores(session_id: int, db: Session = Depends(get_db)):
    """Spustí přepřiřazení vlastníků k PDF na pozadí s progress barem."""
    session = db.query(TaxSession).get(session_id)
    if not session:
        return RedirectResponse("/dane", status_code=302)
    if session.send_status in (SendStatus.READY, SendStatus.SENDING,
                                SendStatus.PAUSED, SendStatus.COMPLETED):
        return RedirectResponse(f"/dane/{session_id}?flash=locked", status_code=302)

    with _recompute_lock:
        _recompute_progress[session_id] = {
            "current": 0,
            "total": 0,
            "started_at": _time.monotonic(),
            "done": False,
            "error": None,
            "result": None,
        }

    t = threading.Thread(
        target=_recompute_scores_thread,
        args=(session_id, session.year),
        daemon=True,
    )
    t.start()

    return RedirectResponse(
        f"/dane/{session_id}/prepocitavani", status_code=302
    )


@router.get("/{session_id}/prepocitavani")
async def tax_recompute_progress_page(
    session_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Stránka s progress barem přepočtu přiřazení."""
    with _recompute_lock:
        progress = _recompute_progress.get(session_id)
        if not progress or progress.get("done"):
            result = progress.get("result", {}) if progress else {}
            _recompute_progress.pop(session_id, None)
            n = result.get("total", 0)
            reassigned = result.get("reassigned", 0)
            newly = result.get("newly", 0)
            return RedirectResponse(
                f"/dane/{session_id}?flash=prematched&n={n}"
                f"&reassigned={reassigned}&newly={newly}",
                status_code=302,
            )
        progress = dict(progress)

    session = db.query(TaxSession).get(session_id)
    if not session:
        return RedirectResponse("/dane", status_code=302)

    eta = compute_eta(progress["current"], progress["total"], progress["started_at"])

    return templates.TemplateResponse(request, "tax/recompute_progress.html", {
        "active_nav": "tax",
        "session": session,
        "error": progress.get("error"),
        "total": progress["total"],
        "current": progress["current"],
        "current_file": "přiřazení vlastníků",
        "progress_title": "Přepočet přiřazení vlastníků",
        **eta,
        **_tax_wizard(session, 2, has_documents=True),
    })


@router.get("/{session_id}/prepocitavani-stav")
async def tax_recompute_progress_status(session_id: int, request: Request):
    """HTMX polling endpoint — progress přepočtu přiřazení."""
    with _recompute_lock:
        progress = _recompute_progress.get(session_id)
        if not progress:
            response = HTMLResponse("")
            response.headers["HX-Redirect"] = f"/dane/{session_id}"
            return response
        if progress.get("done"):
            error = progress.get("error")
            if error:
                progress = dict(progress)
                _recompute_progress.pop(session_id, None)
                eta = compute_eta(progress["current"], progress["total"], progress["started_at"])
                return templates.TemplateResponse(request, "partials/tax_progress.html", {
                    "error": error,
                    "total": progress["total"],
                    "current": progress["current"],
                    "current_file": None,
                    **eta,
                })
            result = progress.get("result", {})
            _recompute_progress.pop(session_id, None)
            n = result.get("total", 0)
            reassigned = result.get("reassigned", 0)
            newly = result.get("newly", 0)
            response = HTMLResponse("")
            response.headers["HX-Redirect"] = (
                f"/dane/{session_id}?flash=prematched&n={n}"
                f"&reassigned={reassigned}&newly={newly}"
            )
            return response
        progress = dict(progress)

    eta = compute_eta(progress["current"], progress["total"], progress["started_at"])
    return templates.TemplateResponse(request, "partials/tax_progress.html", {
        "error": None,
        "total": progress["total"],
        "current": progress["current"],
        "current_file": "přiřazení vlastníků",
        "progress_title": "Přepočet přiřazení vlastníků",
        **eta,
    })
