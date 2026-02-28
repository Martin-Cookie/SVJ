from __future__ import annotations

import logging
import re
import shutil
import threading
import time
from datetime import date, datetime
from pathlib import Path
from typing import List
from unicodedata import category, normalize

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import cast, Integer
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.database import SessionLocal, get_db
from app.models import (
    EmailDeliveryStatus, MatchStatus, Owner, OwnerUnit, SendStatus,
    TaxDistribution, TaxDocument, TaxSession, Unit,
)
from app.services.email_service import send_email
from app.services.owner_matcher import match_name
from app.services.pdf_extractor import (
    extract_owner_from_tax_pdf, parse_unit_from_filename,
)

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# In-memory progress tracker for background PDF processing
_processing_progress: dict[int, dict] = {}

# In-memory progress tracker for background email sending
_sending_progress: dict[int, dict] = {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TAX_WIZARD_STEPS = [
    {"label": "Nahrání PDF"},
    {"label": "Přiřazení"},
    {"label": "Rozesílka"},
    {"label": "Dokončeno"},
]


def _tax_wizard(session, current_step: int, has_documents: bool = False) -> dict:
    """Build wizard stepper context for tax workflow."""
    status = session.send_status.value
    # Determine max completed step based on session status
    if status == "completed":
        max_done = 4
    elif status in ("sending", "paused"):
        max_done = 2
    elif status == "ready":
        max_done = 2
    else:
        max_done = 0  # draft
    # If documents exist, step 1 (Nahrání PDF) is always done
    if has_documents and max_done < 1:
        max_done = 1

    steps = []
    for i, s in enumerate(_TAX_WIZARD_STEPS, 1):
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
        "wizard_total": len(_TAX_WIZARD_STEPS),
    }


def _strip_diacritics(text: str) -> str:
    """Remove diacritics and lowercase for search."""
    nfkd = normalize("NFD", text)
    return "".join(c for c in nfkd if category(c) != "Mn").lower()


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

    is_completed = doc.session.send_status == SendStatus.READY if doc.session.send_status else False

    return templates.TemplateResponse("partials/tax_match_row.html", {
        "request": request,
        "doc": doc,
        "owners": owners,
        "session": doc.session,
        "list_url": list_url,
        "unit_by_number": unit_by_number,
        "is_completed": is_completed,
    })


def _build_recipients(documents):
    """Deduplicate recipients across documents by owner_id (or ad_hoc key).

    Returns list of dicts:
        {key, name, email, docs: [{filename, file_path}], dist_ids: [int],
         owner_id: int|None, is_external: bool, email_status: str}
    """
    recipients = {}  # key -> recipient dict

    for doc in documents:
        for dist in doc.distributions:
            if dist.match_status == MatchStatus.UNMATCHED:
                continue

            # Build unique key
            if dist.owner_id:
                key = f"owner_{dist.owner_id}"
            else:
                key = f"ext_{dist.id}"

            if key not in recipients:
                # Determine email: dist.email_address_used → owner.email → None
                email = dist.email_address_used
                if not email and dist.owner:
                    email = dist.owner.email
                if not email and dist.ad_hoc_email:
                    email = dist.ad_hoc_email

                name = dist.owner.display_name if dist.owner else (dist.ad_hoc_name or "Neznámý")

                recipients[key] = {
                    "key": key,
                    "name": name,
                    "email": email,
                    "docs": [],
                    "dist_ids": [],
                    "owner_id": dist.owner_id,
                    "is_external": dist.owner_id is None,
                    "email_status": dist.email_status.value if dist.email_status else "pending",
                }

            recipients[key]["docs"].append({
                "id": doc.id,
                "filename": doc.filename,
                "file_path": doc.file_path,
            })
            recipients[key]["dist_ids"].append(dist.id)
            # Update email_status to worst status across distributions
            if dist.email_status and dist.email_status.value == "failed":
                recipients[key]["email_status"] = "failed"

    # Sort docs by filename (numeric part first) within each recipient
    for r in recipients.values():
        r["docs"].sort(key=lambda d: (int(''.join(c for c in d["filename"] if c.isdigit()) or '0'), d["filename"]))

    return sorted(recipients.values(), key=lambda r: r["name"])


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/")
async def tax_list(request: Request, back: str = Query("", alias="back"), stav: str = Query("", alias="stav"), db: Session = Depends(get_db)):
    sessions = (
        db.query(TaxSession)
        .options(
            joinedload(TaxSession.documents)
            .joinedload(TaxDocument.distributions),
        )
        .order_by(TaxSession.created_at.desc())
        .all()
    )
    list_url = str(request.url.path)
    if request.url.query:
        list_url += "?" + str(request.url.query)

    # Compute per-session stats for progress display
    session_stats = {}
    for s in sessions:
        total = len(s.documents)
        confirmed = 0
        for doc in s.documents:
            if doc.distributions and all(
                d.match_status in (MatchStatus.CONFIRMED, MatchStatus.MANUAL)
                for d in doc.distributions
            ):
                confirmed += 1
        # Determine wizard step for list view
        send_status = s.send_status.value if s.send_status else "draft"
        if send_status == "completed":
            wizard_step, wizard_label = 4, "Dokončeno"
        elif send_status in ("sending", "paused", "ready"):
            wizard_step, wizard_label = 3, "Rozesílka"
        elif total > 0 and confirmed < total:
            wizard_step, wizard_label = 2, "Přiřazení"
        elif total == 0:
            wizard_step, wizard_label = 1, "Nahrání PDF"
        else:
            wizard_step, wizard_label = 3, "Rozesílka"

        # Determine max_done for list wizard
        if send_status == "completed":
            list_max_done = 4
        elif send_status in ("sending", "paused", "ready"):
            list_max_done = 2
        else:
            list_max_done = 0
        # If documents exist, step 1 (Nahrání PDF) is always done
        if total > 0 and list_max_done < 1:
            list_max_done = 1

        # Build wizard steps for compact stepper
        wiz_steps = []
        for i, ws in enumerate(_TAX_WIZARD_STEPS, 1):
            if i < wizard_step:
                wiz_steps.append({"label": ws["label"], "status": "done"})
            elif i == wizard_step:
                wiz_steps.append({"label": ws["label"], "status": "done" if i <= list_max_done else "active"})
            else:
                wiz_steps.append({"label": ws["label"], "status": "pending"})

        session_stats[s.id] = {
            "total": total,
            "confirmed": confirmed,
            "pct": int(confirmed / total * 100) if total > 0 else 0,
            "wizard_step": wizard_step,
            "wizard_label": wizard_label,
            "wizard_steps": wiz_steps,
            "wizard_current": wizard_step,
            "wizard_total": len(_TAX_WIZARD_STEPS),
        }

    # Compute status counts for filter bubbles
    status_counts = {"all": len(sessions), "draft": 0, "ready": 0, "sending": 0, "completed": 0}
    session_status_map = {}
    for s in sessions:
        ss = s.send_status.value if s.send_status else "draft"
        if ss in ("sending", "paused"):
            cat = "sending"
        else:
            cat = ss
        status_counts[cat] = status_counts.get(cat, 0) + 1
        session_status_map[s.id] = cat

    # Filter sessions by status
    if stav and stav in ("draft", "ready", "sending", "completed"):
        sessions = [s for s in sessions if session_status_map[s.id] == stav]

    return templates.TemplateResponse("tax/index.html", {
        "request": request,
        "active_nav": "tax",
        "sessions": sessions,
        "back_url": back,
        "list_url": list_url,
        "session_stats": session_stats,
        "status_counts": status_counts,
        "current_stav": stav,
    })


@router.get("/nova")
async def tax_create_page(request: Request, db: Session = Depends(get_db)):
    from app.models import EmailTemplate
    # Wizard step 1 for new session (no session object yet, build manually)
    steps = [{"label": s["label"], "status": "active" if i == 0 else "pending"} for i, s in enumerate(_TAX_WIZARD_STEPS)]
    email_templates = (
        db.query(EmailTemplate)
        .order_by(EmailTemplate.order, EmailTemplate.name)
        .all()
    )
    return templates.TemplateResponse("tax/upload.html", {
        "request": request,
        "active_nav": "tax",
        "wizard_steps": steps,
        "wizard_current": 1,
        "wizard_total": len(_TAX_WIZARD_STEPS),
        "email_templates": email_templates,
    })


@router.post("/nova")
async def tax_create(
    request: Request,
    title: str = Form(...),
    email_subject: str = Form(""),
    email_body: str = Form(""),
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    year = datetime.now().year
    session = TaxSession(
        title=title,
        year=year,
        email_subject=email_subject or title,
        email_body=email_body,
    )
    db.add(session)
    db.flush()

    # Save PDF files to disk (fast I/O only — no extraction yet)
    upload_dir = settings.upload_dir / "tax_pdfs" / f"session_{session.id}"
    upload_dir.mkdir(parents=True, exist_ok=True)

    saved_files = []
    for file in files:
        if not file.filename or not file.filename.lower().endswith(".pdf"):
            continue
        basename = Path(file.filename).name
        dest = upload_dir / basename
        with open(dest, "wb") as f:
            shutil.copyfileobj(file.file, f)
        saved_files.append(str(dest))

    if not saved_files:
        db.rollback()
        return RedirectResponse("/dane", status_code=302)

    db.commit()

    # Initialize progress tracker
    import time as _time
    _processing_progress[session.id] = {
        "total": len(saved_files),
        "current": 0,
        "current_file": "",
        "done": False,
        "error": None,
        "started_at": _time.monotonic(),
    }

    # Start background processing thread
    thread = threading.Thread(
        target=_process_tax_files,
        args=(session.id, saved_files, year),
        daemon=True,
    )
    thread.start()

    return RedirectResponse(f"/dane/{session.id}/zpracovani", status_code=302)


@router.get("/{session_id}/upload")
async def tax_upload_page(
    session_id: int,
    request: Request,
    back: str = Query("", alias="back"),
    db: Session = Depends(get_db),
):
    """Upload additional PDFs to an existing session."""
    session = db.query(TaxSession).options(
        joinedload(TaxSession.documents),
    ).get(session_id)
    if not session:
        return RedirectResponse("/dane", status_code=302)

    has_documents = len(session.documents) > 0
    return templates.TemplateResponse("tax/upload_additional.html", {
        "request": request,
        "active_nav": "tax",
        "session": session,
        "has_documents": has_documents,
        "back_url": back or f"/dane/{session_id}",
        **_tax_wizard(session, 1, has_documents=has_documents),
    })


@router.post("/{session_id}/upload")
async def tax_upload_additional(
    session_id: int,
    request: Request,
    import_mode: str = Form("append"),
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    """Upload additional PDFs to an existing session with append/overwrite mode."""
    session = db.query(TaxSession).options(
        joinedload(TaxSession.documents).joinedload(TaxDocument.distributions),
    ).get(session_id)
    if not session:
        return RedirectResponse("/dane", status_code=302)

    # If overwrite mode, delete existing documents and files
    if import_mode == "overwrite":
        upload_dir = settings.upload_dir / "tax_pdfs" / f"session_{session_id}"
        for doc in session.documents:
            # Delete file from disk
            if doc.file_path:
                try:
                    Path(doc.file_path).unlink()
                except Exception:
                    pass
            # Delete distributions
            for dist in doc.distributions:
                db.delete(dist)
            db.delete(doc)
        db.flush()

    # Save new PDF files to disk
    upload_dir = settings.upload_dir / "tax_pdfs" / f"session_{session_id}"
    upload_dir.mkdir(parents=True, exist_ok=True)

    saved_files = []
    for file in files:
        if not file.filename or not file.filename.lower().endswith(".pdf"):
            continue
        basename = Path(file.filename).name
        dest = upload_dir / basename
        with open(dest, "wb") as f:
            shutil.copyfileobj(file.file, f)
        saved_files.append(str(dest))

    if not saved_files:
        return RedirectResponse(f"/dane/{session_id}", status_code=302)

    db.commit()

    # Initialize progress tracker
    import time as _time
    _processing_progress[session_id] = {
        "total": len(saved_files),
        "current": 0,
        "current_file": "",
        "done": False,
        "error": None,
        "started_at": _time.monotonic(),
    }

    # Start background processing thread
    thread = threading.Thread(
        target=_process_tax_files,
        args=(session_id, saved_files, session.year),
        daemon=True,
    )
    thread.start()

    return RedirectResponse(f"/dane/{session_id}/zpracovani", status_code=302)


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

        # Collect IDs of existing docs BEFORE processing (for later comparison)
        pre_existing_doc_ids = {
            d.id for d in db.query(TaxDocument.id).filter_by(session_id=session_id).all()
        }

        new_doc_ids = []
        for i, file_path in enumerate(file_paths):
            basename = Path(file_path).name
            _processing_progress[session_id]["current_file"] = basename

            unit_number, unit_letter = parse_unit_from_filename(basename)
            extracted = extract_owner_from_tax_pdf(file_path)

            # Prefer individual names from details section over combined "Vlastník:" line
            individual_names = [n for n in (extracted.get("owner_names") or []) if n]
            display_name = ", ".join(individual_names) if individual_names else extracted.get("owner_name")

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
                    global_matches = match_name(candidate, owner_dicts, threshold=0.75)
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
            new_docs = db.query(TaxDocument).filter(TaxDocument.id.in_(new_doc_ids)).all()
            for doc in new_docs:
                doc_dists = db.query(TaxDistribution).filter_by(document_id=doc.id).all()
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
        _processing_progress[session_id]["error"] = str(e)
        db.rollback()
    finally:
        _processing_progress[session_id]["done"] = True
        db.close()


def _progress_eta(progress: dict) -> dict:
    """Compute ETA fields from progress dict."""
    import time as _time

    total = progress["total"]
    current = progress["current"]
    pct = int(current / total * 100) if total > 0 else 0
    elapsed = _time.monotonic() - progress["started_at"]

    eta_text = ""
    if current > 0:
        per_file = elapsed / current
        remaining = (total - current) * per_file
        if remaining >= 60:
            mins = int(remaining // 60)
            secs = int(remaining % 60)
            eta_text = f"{mins} min {secs} s"
        else:
            eta_text = f"{int(remaining)} s"

    elapsed_text = ""
    if elapsed >= 60:
        elapsed_text = f"{int(elapsed // 60)} min {int(elapsed % 60)} s"
    else:
        elapsed_text = f"{int(elapsed)} s"

    return {
        "total": total,
        "current": current,
        "current_file": progress["current_file"],
        "pct": pct,
        "elapsed": elapsed_text,
        "eta": eta_text,
    }


@router.get("/{session_id}/zpracovani")
async def tax_processing(
    session_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Show progress page while PDFs are being processed in background."""
    progress = _processing_progress.get(session_id)
    if not progress or progress.get("done"):
        _processing_progress.pop(session_id, None)
        return RedirectResponse(f"/dane/{session_id}", status_code=302)

    session = db.query(TaxSession).get(session_id)
    if not session:
        return RedirectResponse("/dane", status_code=302)

    return templates.TemplateResponse("tax/processing.html", {
        "request": request,
        "active_nav": "tax",
        "session": session,
        **_progress_eta(progress),
    })


@router.get("/{session_id}/zpracovani-stav")
async def tax_processing_status(session_id: int, request: Request):
    """HTMX polling endpoint — returns progress partial or redirect when done."""
    progress = _processing_progress.get(session_id)
    if not progress or progress.get("done"):
        _processing_progress.pop(session_id, None)
        response = HTMLResponse("")
        response.headers["HX-Redirect"] = f"/dane/{session_id}"
        return response

    return templates.TemplateResponse("partials/tax_progress.html", {
        "request": request,
        **_progress_eta(progress),
    })


@router.get("/{session_id}")
async def tax_detail(
    session_id: int,
    request: Request,
    back: str = Query("", alias="back"),
    filtr: str = Query("", alias="filtr"),
    q: str = Query("", alias="q"),
    sort: str = Query("unit_number", alias="sort"),
    order: str = Query("asc", alias="order"),
    db: Session = Depends(get_db),
):
    session = db.query(TaxSession).get(session_id)
    if not session:
        return RedirectResponse("/dane", status_code=302)

    all_documents = (
        db.query(TaxDocument)
        .filter_by(session_id=session_id)
        .options(
            joinedload(TaxDocument.distributions)
            .joinedload(TaxDistribution.owner)
            .joinedload(Owner.units)
            .joinedload(OwnerUnit.unit),
        )
        .order_by(cast(TaxDocument.unit_number, Integer), TaxDocument.unit_letter)
        .all()
    )

    # Stats are always computed from ALL documents (unfiltered)
    stats = _session_stats(all_documents)

    # Compute missing units: units with current owners but no document in this session
    doc_unit_numbers = {d.unit_number for d in all_documents if d.unit_number}
    current_ous = (
        db.query(OwnerUnit)
        .filter(OwnerUnit.valid_to.is_(None))
        .options(joinedload(OwnerUnit.unit), joinedload(OwnerUnit.owner))
        .all()
    )
    missing_units = {}  # unit_number -> {"unit": Unit, "owners": [Owner]}
    for ou in current_ous:
        unum = str(ou.unit.unit_number)
        if unum not in doc_unit_numbers:
            if unum not in missing_units:
                missing_units[unum] = {"unit": ou.unit, "owners": []}
            missing_units[unum]["owners"].append(ou.owner)
    missing_list = sorted(missing_units.values(), key=lambda m: m["unit"].unit_number)
    stats["stat_missing"] = len(missing_list)

    # Apply filter
    if filtr == "confirmed":
        documents = [
            d for d in all_documents
            if d.distributions and all(
                x.match_status in (MatchStatus.CONFIRMED, MatchStatus.MANUAL)
                for x in d.distributions
            )
        ]
    elif filtr == "auto":
        documents = [
            d for d in all_documents
            if d.distributions and any(
                x.match_status == MatchStatus.AUTO_MATCHED for x in d.distributions
            ) and not all(
                x.match_status in (MatchStatus.CONFIRMED, MatchStatus.MANUAL)
                for x in d.distributions
            )
        ]
    elif filtr == "unmatched":
        documents = [
            d for d in all_documents
            if not d.distributions or any(
                x.match_status == MatchStatus.UNMATCHED for x in d.distributions
            )
        ]
    elif filtr == "missing":
        documents = []
    else:
        documents = all_documents

    # Search filtering
    if q:
        q_lower = q.lower()
        q_ascii = _strip_diacritics(q)
        documents = [
            d for d in documents
            if q_lower in (d.filename or "").lower()
            or q_lower in (d.extracted_owner_name or "").lower()
            or q_ascii in _strip_diacritics(d.extracted_owner_name or "")
            or q_lower in str(d.unit_number or "")
            or any(
                q_ascii in _strip_diacritics(dist.owner.display_name)
                for dist in d.distributions if dist.owner
            )
        ]

    # Sorting
    SORT_KEYS = {
        "filename": lambda d: (d.filename or "").lower(),
        "unit_number": lambda d: (int(d.unit_number) if d.unit_number and d.unit_number.isdigit() else 0, d.unit_letter or ""),
        "extracted": lambda d: (d.extracted_owner_name or "").lower(),
        "owner": lambda d: next(
            (_strip_diacritics(dist.owner.display_name) for dist in d.distributions if dist.owner),
            "zzz"
        ),
        "confidence": lambda d: next(
            (dist.match_confidence or 0 for dist in d.distributions if dist.match_confidence),
            0
        ),
    }
    sort_fn = SORT_KEYS.get(sort, SORT_KEYS["unit_number"])
    documents.sort(key=sort_fn, reverse=(order == "desc"))

    owners = (
        db.query(Owner)
        .filter_by(is_active=True)
        .options(joinedload(Owner.units).joinedload(OwnerUnit.unit))
        .order_by(Owner.name_normalized)
        .all()
    )

    back_url = back or "/dane"
    back_label = "Zpět na přehled" if back == "/" else "Zpět na rozesílání"

    list_url = str(request.url.path)
    if request.url.query:
        list_url += "?" + str(request.url.query)

    is_completed = session.send_status and session.send_status.value == "ready"

    # HTMX partial response — return only tbody
    is_htmx = request.headers.get("HX-Request")
    is_boosted = request.headers.get("HX-Boosted")
    if is_htmx and not is_boosted:
        return templates.TemplateResponse("partials/tax_table_body.html", {
            "request": request,
            "documents": documents,
            "owners": owners,
            "is_completed": is_completed,
            "list_url": list_url,
            "unit_by_number": _unit_by_number(db),
        })

    return templates.TemplateResponse("tax/matching.html", {
        "request": request,
        "active_nav": "tax",
        "session": session,
        "documents": documents,
        "owners": owners,
        "back_url": back_url,
        "back_label": back_label,
        "list_url": list_url,
        "filtr": filtr,
        "q": q,
        "sort": sort,
        "order": order,
        "is_completed": is_completed,
        "unit_by_number": _unit_by_number(db),
        "missing_list": missing_list,
        **stats,
        **_tax_wizard(session, 2, has_documents=len(documents) > 0),
    })


@router.post("/{session_id}/prejmenovat")
async def rename_session(
    session_id: int,
    request: Request,
    title: str = Form(...),
    db: Session = Depends(get_db),
):
    session = db.query(TaxSession).get(session_id)
    if not session:
        return RedirectResponse("/dane", status_code=302)

    session.title = title.strip()
    db.commit()

    from html import escape
    t = escape(session.title)
    return HTMLResponse(
        f'<div id="session-title-area">'
        f'<div class="flex items-center gap-2">'
        f'<h1 class="text-2xl font-bold text-gray-800">{t}</h1>'
        f'<button type="button" onclick="showTitleEdit()" class="text-gray-400 hover:text-gray-600" title="Přejmenovat">'
        f'<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">'
        f'<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" '
        f'd="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"/>'
        f'</svg></button></div>'
        f'<p class="text-sm text-green-600 mt-1">Uloženo</p>'
        f'<script>hideTitleEdit()</script>'
        f'</div>'
    )


@router.post("/{session_id}/dokoncit")
async def finalize_session(
    session_id: int,
    db: Session = Depends(get_db),
):
    """Lock the session — no more editing, can proceed to sending."""
    session = db.query(TaxSession).get(session_id)
    if session:
        session.send_status = SendStatus.READY
        db.commit()
    return RedirectResponse(f"/dane/{session_id}", status_code=302)


@router.post("/{session_id}/znovu-otevrit")
async def reopen_session(
    session_id: int,
    db: Session = Depends(get_db),
):
    """Unlock the session for further editing."""
    session = db.query(TaxSession).get(session_id)
    if session:
        session.send_status = SendStatus.DRAFT
        db.commit()
    return RedirectResponse(f"/dane/{session_id}", status_code=302)


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


# ---------------------------------------------------------------------------
# PDF serving
# ---------------------------------------------------------------------------

@router.get("/{session_id}/dokument/{doc_id}")
async def serve_document(
    session_id: int,
    doc_id: int,
    db: Session = Depends(get_db),
):
    """Serve a tax PDF file for in-browser viewing."""
    doc = db.query(TaxDocument).filter_by(id=doc_id, session_id=session_id).first()
    if not doc or not doc.file_path:
        return RedirectResponse(f"/dane/{session_id}", status_code=302)

    path = Path(doc.file_path)
    if not path.exists():
        return RedirectResponse(f"/dane/{session_id}", status_code=302)

    return FileResponse(path, media_type="application/pdf")


# ---------------------------------------------------------------------------
# Send preview endpoints
# ---------------------------------------------------------------------------

@router.get("/{session_id}/rozeslat")
async def tax_send_preview(
    session_id: int,
    request: Request,
    q: str = Query(""),
    filtr: str = Query(""),
    sort: str = Query("name"),
    order: str = Query("asc"),
    back: str = Query("", alias="back"),
    db: Session = Depends(get_db),
):
    session = db.query(TaxSession).get(session_id)
    if not session:
        return RedirectResponse("/dane", status_code=302)

    # If sending is in progress, redirect to progress page
    progress = _sending_progress.get(session_id)
    if progress and not progress.get("done"):
        return RedirectResponse(f"/dane/{session_id}/rozeslat/prubeh", status_code=302)

    # Edge case: DB says SENDING but no progress dict (server restart)
    if session.send_status == SendStatus.SENDING and not progress:
        session.send_status = SendStatus.PAUSED
        db.commit()

    documents = (
        db.query(TaxDocument)
        .filter_by(session_id=session_id)
        .options(
            joinedload(TaxDocument.distributions)
            .joinedload(TaxDistribution.owner)
            .joinedload(Owner.units)
            .joinedload(OwnerUnit.unit),
        )
        .order_by(cast(TaxDocument.unit_number, Integer), TaxDocument.unit_letter)
        .all()
    )

    all_recipients = _build_recipients(documents)
    total_recipients = len(all_recipients)
    with_email = sum(1 for r in all_recipients if r["email"])
    without_email = total_recipients - with_email

    # Count by status for filter pills
    count_pending = sum(1 for r in all_recipients if r["email_status"] in ("pending", "queued"))
    count_sent = sum(1 for r in all_recipients if r["email_status"] == "sent")
    count_failed = sum(1 for r in all_recipients if r["email_status"] == "failed")

    # Filter by status
    if filtr == "with_email":
        recipients = [r for r in all_recipients if r["email"]]
    elif filtr == "pending":
        recipients = [r for r in all_recipients if r["email_status"] in ("pending", "queued")]
    elif filtr == "sent":
        recipients = [r for r in all_recipients if r["email_status"] == "sent"]
    elif filtr == "failed":
        recipients = [r for r in all_recipients if r["email_status"] == "failed"]
    else:
        recipients = all_recipients

    # Search filtering
    if q:
        q_lower = q.lower()
        q_ascii = _strip_diacritics(q)
        recipients = [
            r for r in recipients
            if q_lower in r["name"].lower()
            or q_ascii in _strip_diacritics(r["name"])
            or q_lower in (r["email"] or "").lower()
            or any(q_lower in d["filename"].lower() for d in r["docs"])
        ]

    # Sorting
    SEND_SORT_KEYS = {
        "name": lambda r: _strip_diacritics(r["name"]),
        "email": lambda r: (r["email"] or "").lower(),
        "docs": lambda r: len(r["docs"]),
        "status": lambda r: r["email_status"],
    }
    sort_fn = SEND_SORT_KEYS.get(sort, SEND_SORT_KEYS["name"])
    recipients.sort(key=sort_fn, reverse=(order == "desc"))

    back_url = back or f"/dane/{session_id}"

    list_url = str(request.url.path)
    if request.url.query:
        list_url += "?" + str(request.url.query)

    ctx = {
        "request": request,
        "active_nav": "tax",
        "session": session,
        "recipients": recipients,
        "total_recipients": total_recipients,
        "with_email": with_email,
        "without_email": without_email,
        "count_pending": count_pending,
        "count_sent": count_sent,
        "count_failed": count_failed,
        "back_url": back_url,
        "list_url": list_url,
        "q": q,
        "filtr": filtr,
        "sort": sort,
        "order": order,
        "test_email_value": session.test_email_address or "",
        **_tax_wizard(session, 3),
    }

    if request.headers.get("HX-Request") and not request.headers.get("HX-Boosted"):
        return templates.TemplateResponse("partials/tax_send_body.html", ctx)

    return templates.TemplateResponse("tax/send.html", ctx)


@router.post("/{session_id}/rozeslat/email/{dist_id}")
async def update_recipient_email(
    session_id: int,
    dist_id: int,
    request: Request,
    email: str = Form(""),
    db: Session = Depends(get_db),
):
    dist = db.query(TaxDistribution).get(dist_id)
    if not dist:
        return RedirectResponse(f"/dane/{session_id}/rozeslat", status_code=302)

    email = email.strip()

    assignments_changed = False

    if dist.owner_id:
        session = db.query(TaxSession).get(session_id)
        all_docs = db.query(TaxDocument).filter_by(session_id=session_id).all()
        doc_ids = [d.id for d in all_docs]

        # Propagate to all distributions of this owner in this session
        sibling_dists = (
            db.query(TaxDistribution)
            .filter(
                TaxDistribution.document_id.in_(doc_ids),
                TaxDistribution.owner_id == dist.owner_id,
            )
            .all()
        )
        for d in sibling_dists:
            d.email_address_used = email or None

        # If owner has no email, save it to their profile too
        owner = db.query(Owner).get(dist.owner_id)
        if owner and email and not owner.email:
            owner.email = email

        # Auto-assign unmatched documents for units owned by this owner
        owner_unit_numbers = {
            str(ou.unit.unit_number)
            for ou in db.query(OwnerUnit)
            .filter_by(owner_id=dist.owner_id)
            .options(joinedload(OwnerUnit.unit))
            .all()
        }
        for doc in all_docs:
            if str(doc.unit_number) not in owner_unit_numbers:
                continue
            doc_dists = (
                db.query(TaxDistribution).filter_by(document_id=doc.id).all()
            )
            has_this_owner = any(d.owner_id == dist.owner_id for d in doc_dists)
            if has_this_owner:
                continue
            is_all_unmatched = all(
                d.match_status == MatchStatus.UNMATCHED for d in doc_dists
            )
            if not is_all_unmatched:
                continue
            # Remove unmatched placeholders
            for d in doc_dists:
                db.delete(d)
            # Find co-owners for this unit
            co_owner_ids = _find_coowners(
                dist.owner_id, str(doc.unit_number),
                session.year if session else None, db,
            )
            for oid in co_owner_ids:
                if oid == dist.owner_id:
                    dist_email = email or None
                else:
                    o = db.query(Owner).get(oid)
                    dist_email = o.email if o else None
                new_dist = TaxDistribution(
                    document_id=doc.id,
                    owner_id=oid,
                    match_status=MatchStatus.MANUAL,
                    email_address_used=dist_email,
                )
                db.add(new_dist)
                assignments_changed = True
    else:
        # Ad-hoc recipient
        dist.ad_hoc_email = email or None

    db.commit()

    # If new assignments were created, full page refresh is needed
    if assignments_changed:
        redirect_url = f"/dane/{session_id}/rozeslat"
        if request.headers.get("HX-Request"):
            return HTMLResponse(
                status_code=200,
                headers={"HX-Redirect": redirect_url},
            )
        return RedirectResponse(redirect_url, status_code=302)

    # Rebuild recipients for the updated row
    documents = (
        db.query(TaxDocument)
        .filter_by(session_id=session_id)
        .options(
            joinedload(TaxDocument.distributions)
            .joinedload(TaxDistribution.owner)
            .joinedload(Owner.units)
            .joinedload(OwnerUnit.unit),
        )
        .order_by(cast(TaxDocument.unit_number, Integer), TaxDocument.unit_letter)
        .all()
    )
    recipients = _build_recipients(documents)

    # Find the updated recipient
    if dist.owner_id:
        key = f"owner_{dist.owner_id}"
    else:
        key = f"ext_{dist.id}"

    recipient = next((r for r in recipients if r["key"] == key), None)
    if not recipient:
        return RedirectResponse(f"/dane/{session_id}/rozeslat", status_code=302)

    list_url = str(request.url.path)

    return templates.TemplateResponse("partials/tax_recipient_row.html", {
        "request": request,
        "r": recipient,
        "session": db.query(TaxSession).get(session_id),
        "list_url": list_url,
    })


@router.post("/{session_id}/rozeslat/test")
async def send_test_email(
    session_id: int,
    request: Request,
    test_email: str = Form(...),
    db: Session = Depends(get_db),
):
    session = db.query(TaxSession).get(session_id)
    if not session:
        return RedirectResponse("/dane", status_code=302)

    # Find the first document with a file
    first_doc = (
        db.query(TaxDocument)
        .filter_by(session_id=session_id)
        .order_by(TaxDocument.id)
        .first()
    )

    attachments = [first_doc.file_path] if first_doc else []

    result = send_email(
        to_email=test_email.strip(),
        to_name="Test",
        subject=session.email_subject or "Test email",
        body_html=session.email_body or "",
        attachments=attachments,
        module="tax",
        reference_id=session.id,
        db=db,
    )

    if result["success"]:
        flash_message = f"Testovací email odeslán na {test_email}"
        flash_type = "success"
        session.test_email_passed = True
        session.test_email_address = test_email.strip()
        db.commit()
    else:
        flash_message = f"Chyba při odesílání: {result['error']}"
        flash_type = "error"

    # Redirect back with flash
    documents = (
        db.query(TaxDocument)
        .filter_by(session_id=session_id)
        .options(
            joinedload(TaxDocument.distributions)
            .joinedload(TaxDistribution.owner)
            .joinedload(Owner.units)
            .joinedload(OwnerUnit.unit),
        )
        .all()
    )
    recipients = _build_recipients(documents)
    total_recipients = len(recipients)
    with_email = sum(1 for r in recipients if r["email"])

    all_recipients = recipients
    count_pending = sum(1 for r in all_recipients if r["email_status"] in ("pending", "queued"))
    count_sent = sum(1 for r in all_recipients if r["email_status"] == "sent")
    count_failed = sum(1 for r in all_recipients if r["email_status"] == "failed")

    back_url = f"/dane/{session_id}/rozeslat"
    return templates.TemplateResponse("tax/send.html", {
        "request": request,
        "active_nav": "tax",
        "session": session,
        "recipients": recipients,
        "total_recipients": total_recipients,
        "with_email": with_email,
        "without_email": total_recipients - with_email,
        "count_pending": count_pending,
        "count_sent": count_sent,
        "count_failed": count_failed,
        "back_url": f"/dane/{session_id}",
        "list_url": back_url,
        "flash_message": flash_message,
        "flash_type": flash_type,
        "test_email_value": test_email.strip(),
        **_tax_wizard(session, 3),
    })


@router.post("/{session_id}/rozeslat/nastaveni")
async def save_send_settings(
    session_id: int,
    request: Request,
    email_subject: str = Form(""),
    email_body: str = Form(""),
    send_batch_size: int = Form(10),
    send_batch_interval: int = Form(5),
    send_confirm_each_batch: bool = Form(False),
    test_email_inline: str = Form(""),
    db: Session = Depends(get_db),
):
    session = db.query(TaxSession).get(session_id)
    if not session:
        return RedirectResponse("/dane", status_code=302)

    session.email_subject = email_subject
    session.email_body = email_body
    session.send_batch_size = send_batch_size
    session.send_batch_interval = send_batch_interval
    session.send_confirm_each_batch = send_confirm_each_batch
    if test_email_inline.strip():
        session.test_email_address = test_email_inline.strip()
    session.send_status = SendStatus.READY
    db.commit()

    return RedirectResponse(f"/dane/{session_id}/rozeslat", status_code=302)


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


# ---------------------------------------------------------------------------
# Batch email sending
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)


def _sending_eta(progress: dict) -> dict:
    """Compute ETA fields from sending progress dict."""
    total = progress["total"]
    sent = progress["sent"]
    failed = progress["failed"]
    current = sent + failed
    pct = int(current / total * 100) if total > 0 else 0
    elapsed = time.monotonic() - progress["started_at"]

    eta_text = ""
    if current > 0:
        per_item = elapsed / current
        remaining = (total - current) * per_item
        if remaining >= 60:
            mins = int(remaining // 60)
            secs = int(remaining % 60)
            eta_text = f"{mins} min {secs} s"
        else:
            eta_text = f"{int(remaining)} s"

    elapsed_text = ""
    if elapsed >= 60:
        elapsed_text = f"{int(elapsed // 60)} min {int(elapsed % 60)} s"
    else:
        elapsed_text = f"{int(elapsed)} s"

    return {
        "total": total,
        "sent": sent,
        "failed": failed,
        "current": current,
        "pct": pct,
        "elapsed": elapsed_text,
        "eta": eta_text,
        "current_recipient": progress.get("current_recipient", ""),
        "done": progress.get("done", False),
        "error": progress.get("error"),
        "paused": progress.get("paused", False),
        "waiting_batch_confirm": progress.get("waiting_batch_confirm", False),
        "batch_number": progress.get("batch_number", 0),
        "total_batches": progress.get("total_batches", 0),
    }


def _send_emails_batch(session_id: int, recipient_data: list, email_subject: str,
                        email_body: str, batch_size: int, batch_interval: int,
                        confirm_each_batch: bool):
    """Background thread: send emails in batches."""
    db = SessionLocal()
    try:
        # Split into batches
        batches = []
        for i in range(0, len(recipient_data), batch_size):
            batches.append(recipient_data[i:i + batch_size])

        _sending_progress[session_id]["total_batches"] = len(batches)

        for batch_idx, batch in enumerate(batches):
            _sending_progress[session_id]["batch_number"] = batch_idx + 1

            for rcpt in batch:
                # Check paused
                while _sending_progress[session_id].get("paused"):
                    time.sleep(0.5)
                    if _sending_progress[session_id].get("done"):
                        return

                _sending_progress[session_id]["current_recipient"] = rcpt["name"]

                # Gather attachment file paths
                attachments = [d["file_path"] for d in rcpt["docs"]]

                # Send email
                result = send_email(
                    to_email=rcpt["email"],
                    to_name=rcpt["name"],
                    subject=email_subject,
                    body_html=email_body,
                    attachments=attachments,
                    module="tax",
                    reference_id=session_id,
                    db=db,
                )

                # Update distribution statuses in DB
                for dist_id in rcpt["dist_ids"]:
                    dist = db.query(TaxDistribution).get(dist_id)
                    if dist:
                        if result["success"]:
                            dist.email_status = EmailDeliveryStatus.SENT
                            dist.email_sent = True
                            dist.email_sent_at = datetime.utcnow()
                            dist.email_address_used = rcpt["email"]
                            dist.email_error = None
                        else:
                            dist.email_status = EmailDeliveryStatus.FAILED
                            dist.email_error = result.get("error", "Unknown error")
                            dist.email_address_used = rcpt["email"]

                db.commit()

                if result["success"]:
                    _sending_progress[session_id]["sent"] += 1
                else:
                    _sending_progress[session_id]["failed"] += 1

            # After batch: wait for confirmation or interval
            if batch_idx < len(batches) - 1:  # not last batch
                if confirm_each_batch:
                    _sending_progress[session_id]["waiting_batch_confirm"] = True
                    while _sending_progress[session_id].get("waiting_batch_confirm"):
                        time.sleep(0.5)
                        if _sending_progress[session_id].get("done"):
                            return
                else:
                    # Wait batch_interval seconds (but check for pause)
                    for _ in range(batch_interval * 2):
                        if _sending_progress[session_id].get("done"):
                            return
                        time.sleep(0.5)

        # Complete
        session = db.query(TaxSession).get(session_id)
        if session:
            session.send_status = SendStatus.COMPLETED
            db.commit()

    except Exception as e:
        logger.exception("Error in batch email sending for session %s", session_id)
        _sending_progress[session_id]["error"] = str(e)
    finally:
        _sending_progress[session_id]["done"] = True
        _sending_progress[session_id]["current_recipient"] = ""
        db.close()


@router.post("/{session_id}/rozeslat/odeslat")
async def start_batch_send(
    session_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Start batch email sending for selected recipients."""
    session = db.query(TaxSession).get(session_id)
    if not session:
        return RedirectResponse("/dane", status_code=302)

    if not session.test_email_passed:
        return RedirectResponse(f"/dane/{session_id}/rozeslat", status_code=302)

    # Check no concurrent sending
    progress = _sending_progress.get(session_id)
    if progress and not progress.get("done"):
        return RedirectResponse(f"/dane/{session_id}/rozeslat/prubeh", status_code=302)

    # Get selected keys from form
    form = await request.form()
    selected_keys = form.getlist("selected_keys")
    if not selected_keys:
        return RedirectResponse(f"/dane/{session_id}/rozeslat", status_code=302)

    # Build recipients
    documents = (
        db.query(TaxDocument)
        .filter_by(session_id=session_id)
        .options(
            joinedload(TaxDocument.distributions)
            .joinedload(TaxDistribution.owner)
            .joinedload(Owner.units)
            .joinedload(OwnerUnit.unit),
        )
        .all()
    )
    all_recipients = _build_recipients(documents)

    # Filter to selected
    selected_set = set(selected_keys)
    recipients_to_send = [r for r in all_recipients if r["key"] in selected_set and r["email"]]

    if not recipients_to_send:
        return RedirectResponse(f"/dane/{session_id}/rozeslat", status_code=302)

    # Mark distributions as QUEUED
    for rcpt in recipients_to_send:
        for dist_id in rcpt["dist_ids"]:
            dist = db.query(TaxDistribution).get(dist_id)
            if dist:
                dist.email_status = EmailDeliveryStatus.QUEUED

    session.send_status = SendStatus.SENDING
    db.commit()

    # Initialize progress
    _sending_progress[session_id] = {
        "total": len(recipients_to_send),
        "sent": 0,
        "failed": 0,
        "current_recipient": "",
        "done": False,
        "error": None,
        "started_at": time.monotonic(),
        "paused": False,
        "waiting_batch_confirm": False,
        "batch_number": 0,
        "total_batches": 0,
    }

    # Start background thread
    thread = threading.Thread(
        target=_send_emails_batch,
        args=(
            session_id,
            recipients_to_send,
            session.email_subject or "",
            session.email_body or "",
            session.send_batch_size or 10,
            session.send_batch_interval or 5,
            session.send_confirm_each_batch or False,
        ),
        daemon=True,
    )
    thread.start()

    return RedirectResponse(f"/dane/{session_id}/rozeslat/prubeh", status_code=302)


@router.get("/{session_id}/rozeslat/prubeh")
async def sending_progress_page(
    session_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Show progress page while emails are being sent."""
    session = db.query(TaxSession).get(session_id)
    if not session:
        return RedirectResponse("/dane", status_code=302)

    progress = _sending_progress.get(session_id)
    if not progress or progress.get("done"):
        _sending_progress.pop(session_id, None)
        return RedirectResponse(f"/dane/{session_id}/rozeslat", status_code=302)

    return templates.TemplateResponse("tax/sending.html", {
        "request": request,
        "active_nav": "tax",
        "session": session,
        **_sending_eta(progress),
        **_tax_wizard(session, 3),
    })


@router.get("/{session_id}/rozeslat/prubeh-stav")
async def sending_progress_status(
    session_id: int,
    request: Request,
):
    """HTMX polling endpoint — returns progress partial or redirect when done."""
    progress = _sending_progress.get(session_id)
    if not progress or progress.get("done"):
        _sending_progress.pop(session_id, None)
        response = HTMLResponse("")
        response.headers["HX-Redirect"] = f"/dane/{session_id}/rozeslat"
        return response

    return templates.TemplateResponse("partials/tax_send_progress.html", {
        "request": request,
        "session_id": session_id,
        **_sending_eta(progress),
    })


@router.post("/{session_id}/rozeslat/pozastavit")
async def pause_sending(
    session_id: int,
    db: Session = Depends(get_db),
):
    """Pause the sending process."""
    progress = _sending_progress.get(session_id)
    if progress and not progress.get("done"):
        progress["paused"] = True

    session = db.query(TaxSession).get(session_id)
    if session:
        session.send_status = SendStatus.PAUSED
        db.commit()

    return RedirectResponse(f"/dane/{session_id}/rozeslat/prubeh", status_code=302)


@router.post("/{session_id}/rozeslat/pokracovat")
async def resume_sending(
    session_id: int,
    db: Session = Depends(get_db),
):
    """Resume the sending process (also confirms batch)."""
    progress = _sending_progress.get(session_id)
    if progress and not progress.get("done"):
        progress["paused"] = False
        progress["waiting_batch_confirm"] = False

    session = db.query(TaxSession).get(session_id)
    if session:
        session.send_status = SendStatus.SENDING
        db.commit()

    return RedirectResponse(f"/dane/{session_id}/rozeslat/prubeh", status_code=302)


@router.post("/{session_id}/rozeslat/retry")
async def retry_failed(
    session_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Retry all failed recipients."""
    session = db.query(TaxSession).get(session_id)
    if not session:
        return RedirectResponse("/dane", status_code=302)

    # Check no concurrent sending
    progress = _sending_progress.get(session_id)
    if progress and not progress.get("done"):
        return RedirectResponse(f"/dane/{session_id}/rozeslat/prubeh", status_code=302)

    # Build recipients and filter to failed only
    documents = (
        db.query(TaxDocument)
        .filter_by(session_id=session_id)
        .options(
            joinedload(TaxDocument.distributions)
            .joinedload(TaxDistribution.owner)
            .joinedload(Owner.units)
            .joinedload(OwnerUnit.unit),
        )
        .all()
    )
    all_recipients = _build_recipients(documents)
    failed_recipients = [r for r in all_recipients if r["email_status"] == "failed" and r["email"]]

    if not failed_recipients:
        return RedirectResponse(f"/dane/{session_id}/rozeslat", status_code=302)

    # Reset failed distributions to QUEUED
    for rcpt in failed_recipients:
        for dist_id in rcpt["dist_ids"]:
            dist = db.query(TaxDistribution).get(dist_id)
            if dist and dist.email_status == EmailDeliveryStatus.FAILED:
                dist.email_status = EmailDeliveryStatus.QUEUED
                dist.email_error = None

    session.send_status = SendStatus.SENDING
    db.commit()

    # Initialize progress
    _sending_progress[session_id] = {
        "total": len(failed_recipients),
        "sent": 0,
        "failed": 0,
        "current_recipient": "",
        "done": False,
        "error": None,
        "started_at": time.monotonic(),
        "paused": False,
        "waiting_batch_confirm": False,
        "batch_number": 0,
        "total_batches": 0,
    }

    # Start background thread
    thread = threading.Thread(
        target=_send_emails_batch,
        args=(
            session_id,
            failed_recipients,
            session.email_subject or "",
            session.email_body or "",
            session.send_batch_size or 10,
            session.send_batch_interval or 5,
            session.send_confirm_each_batch or False,
        ),
        daemon=True,
    )
    thread.start()

    return RedirectResponse(f"/dane/{session_id}/rozeslat/prubeh", status_code=302)
