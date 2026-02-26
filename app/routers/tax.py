from __future__ import annotations

import shutil
import threading
from datetime import date, datetime
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.database import SessionLocal, get_db
from app.models import (
    MatchStatus, Owner, OwnerUnit, SendStatus, TaxDistribution, TaxDocument, TaxSession, Unit,
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
                "filename": doc.filename,
                "file_path": doc.file_path,
            })
            recipients[key]["dist_ids"].append(dist.id)
            # Update email_status to worst status across distributions
            if dist.email_status and dist.email_status.value == "failed":
                recipients[key]["email_status"] = "failed"

    return sorted(recipients.values(), key=lambda r: r["name"])


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/")
async def tax_list(request: Request, back: str = Query("", alias="back"), db: Session = Depends(get_db)):
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
        session_stats[s.id] = {
            "total": total,
            "confirmed": confirmed,
            "pct": int(confirmed / total * 100) if total > 0 else 0,
        }

    return templates.TemplateResponse("tax/index.html", {
        "request": request,
        "active_nav": "tax",
        "sessions": sessions,
        "back_url": back,
        "list_url": list_url,
        "session_stats": session_stats,
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

            # Try auto-matching
            matched_owner = None
            confidence = 0.0

            names_to_try = []
            for n in extracted.get("owner_names") or []:
                if n:
                    names_to_try.append(n)
            if extracted.get("owner_name"):
                names_to_try.append(extracted["owner_name"])

            # First try: match by unit number + name
            if unit_number in unit_to_owners and names_to_try:
                for candidate in names_to_try:
                    matches = match_name(
                        candidate,
                        unit_to_owners[unit_number],
                        threshold=0.6,
                    )
                    if matches and matches[0]["confidence"] > confidence:
                        matched_owner = matches[0]
                        confidence = matches[0]["confidence"]

            # Second try: match against all owners by name only
            if not matched_owner and names_to_try:
                for candidate in names_to_try:
                    matches = match_name(candidate, owner_dicts, threshold=0.75)
                    if matches and matches[0]["confidence"] > confidence:
                        matched_owner = matches[0]
                        confidence = matches[0]["confidence"]

            if matched_owner:
                coowner_ids = _find_coowners(
                    matched_owner["owner_id"], unit_number, tax_year, db
                )
                for oid in coowner_ids:
                    dist = TaxDistribution(
                        document_id=doc.id,
                        owner_id=oid,
                        match_status=MatchStatus.AUTO_MATCHED,
                        match_confidence=confidence,
                    )
                    db.add(dist)
            else:
                dist = TaxDistribution(
                    document_id=doc.id,
                    owner_id=None,
                    match_status=MatchStatus.UNMATCHED,
                    match_confidence=None,
                )
                db.add(dist)

            _processing_progress[session_id]["current"] = i + 1

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
        .order_by(TaxDocument.unit_number, TaxDocument.unit_letter)
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
        "filtr": filtr,
        "unit_by_number": _unit_by_number(db),
        "missing_list": missing_list,
        **stats,
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
# Send preview endpoints
# ---------------------------------------------------------------------------

@router.get("/{session_id}/rozeslat")
async def tax_send_preview(
    session_id: int,
    request: Request,
    back: str = Query("", alias="back"),
    db: Session = Depends(get_db),
):
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

    recipients = _build_recipients(documents)
    total_recipients = len(recipients)
    with_email = sum(1 for r in recipients if r["email"])
    without_email = total_recipients - with_email

    back_url = back or f"/dane/{session_id}"

    list_url = str(request.url.path)
    if request.url.query:
        list_url += "?" + str(request.url.query)

    return templates.TemplateResponse("tax/send.html", {
        "request": request,
        "active_nav": "tax",
        "session": session,
        "recipients": recipients,
        "total_recipients": total_recipients,
        "with_email": with_email,
        "without_email": without_email,
        "back_url": back_url,
        "list_url": list_url,
    })


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

    if dist.owner_id:
        # Propagate to all distributions of this owner in this session
        doc_ids = [d.id for d in db.query(TaxDocument).filter_by(session_id=session_id).all()]
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
    else:
        # Ad-hoc recipient
        dist.ad_hoc_email = email or None

    db.commit()

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
        .order_by(TaxDocument.unit_number, TaxDocument.unit_letter)
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

    back_url = f"/dane/{session_id}/rozeslat"
    return templates.TemplateResponse("tax/send.html", {
        "request": request,
        "active_nav": "tax",
        "session": session,
        "recipients": recipients,
        "total_recipients": total_recipients,
        "with_email": with_email,
        "without_email": total_recipients - with_email,
        "back_url": f"/dane/{session_id}",
        "list_url": back_url,
        "flash_message": flash_message,
        "flash_type": flash_type,
    })


@router.post("/{session_id}/rozeslat/nastaveni")
async def save_send_settings(
    session_id: int,
    request: Request,
    email_subject: str = Form(""),
    email_body: str = Form(""),
    send_batch_size: int = Form(10),
    send_batch_interval: int = Form(5),
    db: Session = Depends(get_db),
):
    session = db.query(TaxSession).get(session_id)
    if not session:
        return RedirectResponse("/dane", status_code=302)

    session.email_subject = email_subject
    session.email_body = email_body
    session.send_batch_size = send_batch_size
    session.send_batch_interval = send_batch_interval
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
