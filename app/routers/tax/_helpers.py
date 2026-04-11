from __future__ import annotations

import logging
import threading
from datetime import date
from urllib.parse import urlparse

from fastapi import Request
from sqlalchemy import cast, Integer
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.database import SessionLocal
from app.models import (
    MatchStatus, Owner, OwnerUnit, SendStatus,
    TaxDistribution, TaxDocument, TaxSession, Unit,
)
from app.utils import build_wizard_steps, templates

logger = logging.getLogger(__name__)

# In-memory progress tracker for background PDF processing
_processing_progress: dict[int, dict] = {}
_processing_lock = threading.Lock()

# In-memory progress tracker for background email sending
_sending_progress: dict[int, dict] = {}
_sending_lock = threading.Lock()


def recover_stuck_sending_sessions():
    """Reset any SENDING sessions to PAUSED on startup (server restart recovery)."""
    db = SessionLocal()
    try:
        stuck = db.query(TaxSession).filter_by(send_status=SendStatus.SENDING).all()
        for s in stuck:
            logger.warning("Recovering stuck SENDING session %s → PAUSED", s.id)
            s.send_status = SendStatus.PAUSED
        if stuck:
            db.commit()
    finally:
        db.close()


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
    is_sending = status in ("sending", "paused")
    # Determine max completed step based on session status
    if status == "completed":
        max_done = 4
    elif is_sending:
        max_done = 2
    elif status == "ready":
        max_done = 2
    else:
        max_done = 0  # draft
    # If documents exist, step 1 (Nahrání PDF) is always done
    if has_documents and max_done < 1:
        max_done = 1

    sending_step = 3 if is_sending else None
    steps = build_wizard_steps(_TAX_WIZARD_STEPS, current_step, max_done, sending_step)

    return {
        "wizard_steps": steps,
        "wizard_current": current_step,
        "wizard_total": len(_TAX_WIZARD_STEPS),
    }


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

    try:
        unit_num = int(unit_number)
    except (ValueError, TypeError):
        return [owner_id]
    unit = db.query(Unit).filter_by(unit_number=unit_num).first()
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
            .joinedload(TaxDistribution.owner),
        )
        .first()
    )

    # Build list_url from current browser URL for back navigation
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

    is_locked = doc.session.send_status in (SendStatus.READY, SendStatus.SENDING, SendStatus.PAUSED, SendStatus.COMPLETED) if doc.session.send_status else False

    return templates.TemplateResponse(request, "partials/tax_match_row.html", {
        "doc": doc,
        "session": doc.session,
        "list_url": list_url,
        "unit_by_number": unit_by_number,
        "is_locked": is_locked,
    })


def _build_recipients(documents):
    """Deduplicate recipients across documents by owner_id (or ad_hoc key).

    Returns list of dicts:
        {key, name, email, docs: [{filename, file_path}], dist_ids: [int],
         owner_id: int|None, is_external: bool, email_status: str,
         primary_email: str|None, secondary_email: str|None,
         selected_emails: [str], has_dual_email: bool}
    """
    recipients = {}  # key -> recipient dict

    for doc in documents:
        for dist in doc.distributions:
            if dist.match_status in (MatchStatus.UNMATCHED, MatchStatus.AUTO_MATCHED):
                continue

            # Build unique key
            if dist.owner_id:
                key = f"owner_{dist.owner_id}"
            else:
                key = f"ext_{dist.id}"

            if key not in recipients:
                owner = dist.owner
                owner_email_invalid = bool(owner and owner.email_invalid)
                primary_email = owner.email if owner else None
                secondary_email = owner.email_secondary if owner else None

                # Determine selected_emails from email_address_used or defaults
                if dist.email_address_used:
                    selected_emails = [e.strip() for e in dist.email_address_used.split(",") if e.strip()]
                elif primary_email:
                    selected_emails = [primary_email]
                elif secondary_email:
                    selected_emails = [secondary_email]
                elif dist.ad_hoc_email:
                    selected_emails = [dist.ad_hoc_email]
                else:
                    selected_emails = []

                # Hard bounce flag — vyloučit z rozesílky (vlastník má email_invalid)
                if owner_email_invalid:
                    selected_emails = []

                # has_dual_email: both present and different
                has_dual_email = bool(
                    primary_email and secondary_email
                    and primary_email.strip().lower() != secondary_email.strip().lower()
                )

                # Backward-compatible email field
                email = ",".join(selected_emails) if selected_emails else None

                name = owner.display_name if owner else (dist.ad_hoc_name or "Neznámý")

                recipients[key] = {
                    "key": key,
                    "name": name,
                    "email": email,
                    "primary_email": primary_email,
                    "secondary_email": secondary_email,
                    "selected_emails": selected_emails,
                    "has_dual_email": has_dual_email,
                    "docs": [],
                    "dist_ids": [],
                    "owner_id": dist.owner_id,
                    "is_external": dist.owner_id is None,
                    "email_status": dist.email_status.value if dist.email_status else "pending",
                    "email_invalid": owner_email_invalid,
                }

            dist_status = dist.email_status.value if dist.email_status else "pending"
            recipients[key]["docs"].append({
                "id": doc.id,
                "filename": doc.filename,
                "file_path": doc.file_path,
                "dist_id": dist.id,
                "sent": dist_status == "sent",
            })
            recipients[key]["dist_ids"].append(dist.id)
            # Update email_status: failed > pending > queued > sent
            current = recipients[key]["email_status"]
            if dist_status == "failed":
                recipients[key]["email_status"] = "failed"
            elif dist_status in ("pending", "queued") and current == "sent":
                recipients[key]["email_status"] = "pending"

    # Sort docs by filename (numeric part first) within each recipient
    for r in recipients.values():
        r["docs"].sort(key=lambda d: (int(''.join(c for c in d["filename"] if c.isdigit()) or '0'), d["filename"]))

    return sorted(recipients.values(), key=lambda r: r["name"])
