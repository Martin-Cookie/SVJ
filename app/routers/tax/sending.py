from __future__ import annotations

import re
import threading
import time
from datetime import datetime

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import cast, Integer
from sqlalchemy.orm import Session, joinedload

from app.database import SessionLocal, get_db
from app.models import (
    EmailDeliveryStatus, MatchStatus, Owner, OwnerUnit, SendStatus,
    TaxDistribution, TaxDocument, TaxSession,
    ActivityAction, log_activity,
)
from app.services.email_service import create_smtp_connection, send_email
from app.utils import build_list_url, strip_diacritics

from ._helpers import (
    logger, templates,
    _sending_progress, _sending_lock,
    _tax_wizard, _build_recipients, _find_coowners,
)

router = APIRouter()


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
    with _sending_lock:
        progress = _sending_progress.get(session_id)
        sending_in_progress = progress and not progress.get("done")
    if sending_in_progress:
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
            .joinedload(TaxDistribution.owner),
        )
        .order_by(cast(TaxDocument.unit_number, Integer), TaxDocument.unit_letter)
        .all()
    )

    # Count skipped AUTO_MATCHED distributions
    skipped_auto_count = sum(
        1 for doc in documents
        for dist in doc.distributions
        if dist.match_status == MatchStatus.AUTO_MATCHED
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
    elif filtr == "no_email":
        recipients = [r for r in all_recipients if not r["email"]]
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
        q_ascii = strip_diacritics(q)
        recipients = [
            r for r in recipients
            if q_lower in r["name"].lower()
            or q_ascii in strip_diacritics(r["name"])
            or q_lower in (r["email"] or "").lower()
            or any(q_lower in d["filename"].lower() for d in r["docs"])
        ]

    # Sorting
    SEND_SORT_KEYS = {
        "name": lambda r: strip_diacritics(r["name"]),
        "email": lambda r: (r["email"] or "").lower(),
        "docs": lambda r: len(r["docs"]),
        "status": lambda r: r["email_status"],
    }
    sort_fn = SEND_SORT_KEYS.get(sort, SEND_SORT_KEYS["name"])
    recipients.sort(key=sort_fn, reverse=(order == "desc"))

    back_url = back or f"/dane/{session_id}"

    list_url = build_list_url(request)

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
        "all_documents": documents,
        "skipped_auto_count": skipped_auto_count,
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

    # Basic email format validation (#26)
    if email and not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
        # Return current row unchanged with no update
        documents = (
            db.query(TaxDocument)
            .filter_by(session_id=session_id)
            .options(joinedload(TaxDocument.distributions).joinedload(TaxDistribution.owner))
            .all()
        )
        recipients = _build_recipients(documents)
        key = f"owner_{dist.owner_id}" if dist.owner_id else f"ext_{dist.id}"
        recipient = next((r for r in recipients if r["key"] == key), None)
        if recipient:
            return templates.TemplateResponse("partials/tax_recipient_row.html", {
                "request": request,
                "r": recipient,
                "session": db.query(TaxSession).get(session_id),
                "list_url": build_list_url(request),
            })
        return RedirectResponse(f"/dane/{session_id}/rozeslat", status_code=302)

    assignments_changed = False

    if dist.owner_id:
        session = db.query(TaxSession).get(session_id)
        all_docs = (
            db.query(TaxDocument)
            .filter_by(session_id=session_id)
            .options(joinedload(TaxDocument.distributions))
            .all()
        )
        doc_ids = [d.id for d in all_docs]

        # Propagate to all distributions of this owner in this session
        # Skip SENT distributions to preserve historical record (#12)
        sibling_dists = (
            db.query(TaxDistribution)
            .filter(
                TaxDistribution.document_id.in_(doc_ids),
                TaxDistribution.owner_id == dist.owner_id,
            )
            .all()
        )
        for d in sibling_dists:
            if d.email_status != EmailDeliveryStatus.SENT:
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

    # Rebuild only the relevant recipient row (optimized — no full rebuild)
    if dist.owner_id:
        key = f"owner_{dist.owner_id}"
        # Load only documents for this owner
        relevant_dists = (
            db.query(TaxDistribution)
            .filter(
                TaxDistribution.document_id.in_(
                    db.query(TaxDocument.id).filter_by(session_id=session_id)
                ),
                TaxDistribution.owner_id == dist.owner_id,
            )
            .options(joinedload(TaxDistribution.document))
            .all()
        )
        owner = db.query(Owner).get(dist.owner_id)
        if not owner:
            return RedirectResponse(f"/dane/{session_id}/rozeslat", status_code=302)

        # Build recipient dict manually
        docs_list = []
        dist_ids = []
        used_email = None
        email_status = "pending"
        for rd in relevant_dists:
            docs_list.append({
                "id": rd.document_id,
                "filename": rd.document.original_filename or rd.document.filename or "",
                "file_path": rd.document.file_path,
            })
            dist_ids.append(rd.id)
            if rd.email_address_used:
                used_email = rd.email_address_used
            if rd.email_status:
                email_status = rd.email_status.value if hasattr(rd.email_status, 'value') else rd.email_status

        primary_email = owner.email or ""
        secondary_email = owner.email_secondary or ""
        final_email = used_email or primary_email or secondary_email or ""

        recipient = {
            "key": key,
            "name": owner.display_name,
            "email": final_email,
            "primary_email": primary_email,
            "secondary_email": secondary_email,
            "selected_emails": [e.strip() for e in final_email.split(",") if e.strip()] if final_email else [],
            "has_dual_email": bool(primary_email and secondary_email and primary_email != secondary_email),
            "docs": docs_list,
            "dist_ids": dist_ids,
            "owner_id": owner.id,
            "is_external": False,
            "email_status": email_status,
        }
    else:
        key = f"ext_{dist.id}"
        doc = db.query(TaxDocument).get(dist.document_id) if dist.document_id else None
        recipient = {
            "key": key,
            "name": dist.ad_hoc_name or "Externí příjemce",
            "email": dist.ad_hoc_email or "",
            "primary_email": dist.ad_hoc_email or "",
            "secondary_email": "",
            "selected_emails": [dist.ad_hoc_email] if dist.ad_hoc_email else [],
            "has_dual_email": False,
            "docs": [{"id": doc.id, "filename": doc.original_filename or doc.filename or "", "file_path": doc.file_path}] if doc else [],
            "dist_ids": [dist.id],
            "owner_id": None,
            "is_external": True,
            "email_status": dist.email_status.value if dist.email_status and hasattr(dist.email_status, 'value') else "pending",
        }

    list_url = build_list_url(request)
    session_obj = db.query(TaxSession).get(session_id)

    return templates.TemplateResponse("partials/tax_recipient_row.html", {
        "request": request,
        "r": recipient,
        "session": session_obj,
        "list_url": list_url,
    })


@router.post("/{session_id}/rozeslat/email-vyber/{dist_id}")
async def toggle_recipient_email(
    session_id: int,
    dist_id: int,
    request: Request,
    email: str = Form(""),
    checked: str = Form("true"),
    db: Session = Depends(get_db),
):
    """Toggle an individual email address on/off for a recipient."""
    dist = db.query(TaxDistribution).get(dist_id)
    if not dist:
        return RedirectResponse(f"/dane/{session_id}/rozeslat", status_code=302)

    email = email.strip()
    is_checked = checked == "true"

    # Parse current selected emails
    current = set()
    if dist.email_address_used:
        current = {e.strip() for e in dist.email_address_used.split(",") if e.strip()}

    # Add or remove email
    if is_checked and email:
        current.add(email)
    elif not is_checked and email:
        current.discard(email)

    new_value = ",".join(sorted(current)) if current else None

    # Propagate to all sibling distributions of same owner in this session
    # Skip distributions that are already SENT to preserve historical record (#6)
    if dist.owner_id:
        all_docs = (
            db.query(TaxDocument)
            .filter_by(session_id=session_id)
            .options(joinedload(TaxDocument.distributions))
            .all()
        )
        doc_ids = [d.id for d in all_docs]
        sibling_dists = (
            db.query(TaxDistribution)
            .filter(
                TaxDistribution.document_id.in_(doc_ids),
                TaxDistribution.owner_id == dist.owner_id,
            )
            .all()
        )
        for d in sibling_dists:
            if d.email_status != EmailDeliveryStatus.SENT:
                d.email_address_used = new_value
    else:
        if dist.email_status != EmailDeliveryStatus.SENT:
            dist.email_address_used = new_value

    db.commit()

    # Rebuild and return updated row
    documents = (
        db.query(TaxDocument)
        .filter_by(session_id=session_id)
        .options(
            joinedload(TaxDocument.distributions)
            .joinedload(TaxDistribution.owner),
        )
        .order_by(cast(TaxDocument.unit_number, Integer), TaxDocument.unit_letter)
        .all()
    )
    recipients = _build_recipients(documents)

    key = f"owner_{dist.owner_id}" if dist.owner_id else f"ext_{dist.id}"
    recipient = next((r for r in recipients if r["key"] == key), None)
    if not recipient:
        return RedirectResponse(f"/dane/{session_id}/rozeslat", status_code=302)

    list_url = build_list_url(request)

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
    test_doc_id: int = Form(0),
    email_subject: str = Form(""),
    email_body: str = Form(""),
    db: Session = Depends(get_db),
):
    session = db.query(TaxSession).get(session_id)
    if not session:
        return RedirectResponse("/dane", status_code=302)

    # Save subject and body from the form (user may not have clicked Uložit)
    if email_subject:
        session.email_subject = email_subject
    if email_body:
        session.email_body = email_body
    if email_subject or email_body:
        db.commit()

    # Find specific or first document for test attachment
    if test_doc_id:
        test_doc = db.query(TaxDocument).filter_by(
            id=test_doc_id, session_id=session_id
        ).first()
    else:
        test_doc = None
    if not test_doc:
        test_doc = (
            db.query(TaxDocument)
            .filter_by(session_id=session_id)
            .order_by(TaxDocument.id)
            .first()
        )

    attachments = [test_doc.file_path] if test_doc else []

    import asyncio
    result = await asyncio.to_thread(
        send_email,
        to_email=test_email.strip(),
        to_name="Test",
        subject=f"[TEST] {session.email_subject or 'Test email'}",
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
            .joinedload(TaxDistribution.owner),
        )
        .all()
    )

    skipped_auto_count = sum(
        1 for doc in documents
        for dist in doc.distributions
        if dist.match_status == MatchStatus.AUTO_MATCHED
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
        "all_documents": documents,
        "skipped_auto_count": skipped_auto_count,
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

    # Invalidate test if email content changed (#8)
    if (email_subject != (session.email_subject or "")
            or email_body != (session.email_body or "")):
        session.test_email_passed = False

    session.email_subject = email_subject
    session.email_body = email_body
    session.send_batch_size = send_batch_size
    session.send_batch_interval = send_batch_interval
    session.send_confirm_each_batch = send_confirm_each_batch
    if test_email_inline.strip():
        session.test_email_address = test_email_inline.strip()
    # Only set READY if session is already past DRAFT (i.e. matching was finalized) (#4)
    if session.send_status != SendStatus.DRAFT:
        session.send_status = SendStatus.READY
    db.commit()

    return RedirectResponse(f"/dane/{session_id}/rozeslat?config=open", status_code=302)


# ---------------------------------------------------------------------------
# Batch email sending
# ---------------------------------------------------------------------------


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

        with _sending_lock:
            _sending_progress[session_id]["total_batches"] = len(batches)

        for batch_idx, batch in enumerate(batches):
            with _sending_lock:
                _sending_progress[session_id]["batch_number"] = batch_idx + 1

            # Create shared SMTP connection per batch (#25)
            smtp_conn = None
            try:
                smtp_conn = create_smtp_connection()
            except Exception:
                logger.warning("Failed to create shared SMTP connection, falling back to per-email")

            for rcpt in batch:
                # Check paused
                while True:
                    with _sending_lock:
                        paused = _sending_progress[session_id].get("paused")
                        done = _sending_progress[session_id].get("done")
                    if not paused:
                        break
                    if done:
                        if smtp_conn:
                            try:
                                smtp_conn.quit()
                            except Exception:
                                pass
                        return
                    time.sleep(0.5)

                with _sending_lock:
                    _sending_progress[session_id]["current_recipient"] = rcpt["name"]

                # Gather only unsent attachment file paths
                unsent_docs = [d for d in rcpt["docs"] if not d.get("sent")]
                attachments = [d["file_path"] for d in unsent_docs] if unsent_docs else [d["file_path"] for d in rcpt["docs"]]
                unsent_dist_ids = [d["dist_id"] for d in unsent_docs] if unsent_docs else rcpt["dist_ids"]

                # Send email (reuse shared SMTP connection)
                result = send_email(
                    to_email=rcpt["email"],
                    to_name=rcpt["name"],
                    subject=email_subject,
                    body_html=email_body,
                    attachments=attachments,
                    module="tax",
                    reference_id=session_id,
                    db=db,
                    smtp_server=smtp_conn,
                )

                # Update only unsent distribution statuses in DB
                for dist_id in unsent_dist_ids:
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

                with _sending_lock:
                    if result["success"]:
                        _sending_progress[session_id]["sent"] += 1
                    else:
                        _sending_progress[session_id]["failed"] += 1

            # Close shared SMTP connection after batch
            if smtp_conn:
                try:
                    smtp_conn.quit()
                except Exception:
                    pass
                smtp_conn = None

            # After batch: wait for confirmation or interval
            if batch_idx < len(batches) - 1:  # not last batch
                if confirm_each_batch:
                    with _sending_lock:
                        _sending_progress[session_id]["waiting_batch_confirm"] = True
                    while True:
                        with _sending_lock:
                            waiting = _sending_progress[session_id].get("waiting_batch_confirm")
                            done = _sending_progress[session_id].get("done")
                        if not waiting:
                            break
                        if done:
                            return
                        time.sleep(0.5)
                else:
                    # Wait batch_interval seconds (but check for pause)
                    for _ in range(batch_interval * 2):
                        with _sending_lock:
                            done = _sending_progress[session_id].get("done")
                        if done:
                            return
                        time.sleep(0.5)

        # Complete
        session = db.query(TaxSession).get(session_id)
        if session:
            session.send_status = SendStatus.COMPLETED
            db.commit()

    except Exception as e:
        logger.exception("Error in batch email sending for session %s", session_id)
        with _sending_lock:
            _sending_progress[session_id]["error"] = str(e)
    finally:
        with _sending_lock:
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
    with _sending_lock:
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
            .joinedload(TaxDistribution.owner),
        )
        .all()
    )
    all_recipients = _build_recipients(documents)

    # Filter to selected
    selected_set = set(selected_keys)
    recipients_to_send = [r for r in all_recipients if r["key"] in selected_set and r["email"]]

    if not recipients_to_send:
        return RedirectResponse(f"/dane/{session_id}/rozeslat", status_code=302)

    # Mark only unsent distributions as QUEUED
    for rcpt in recipients_to_send:
        unsent_dist_ids = [d["dist_id"] for d in rcpt["docs"] if not d.get("sent")]
        target_ids = unsent_dist_ids if unsent_dist_ids else rcpt["dist_ids"]
        for dist_id in target_ids:
            dist = db.query(TaxDistribution).get(dist_id)
            if dist and dist.email_status != EmailDeliveryStatus.SENT:
                dist.email_status = EmailDeliveryStatus.QUEUED

    session.send_status = SendStatus.SENDING
    log_activity(db, ActivityAction.STATUS_CHANGED, "tax_session", "dane",
                 entity_id=session.id, entity_name=session.title,
                 description=f"Rozesílka zahájena: {len(recipients_to_send)} příjemců")
    db.commit()

    # Initialize progress
    with _sending_lock:
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

    with _sending_lock:
        progress = _sending_progress.get(session_id)
        if not progress or progress.get("done"):
            _sending_progress.pop(session_id, None)
            return RedirectResponse(f"/dane/{session_id}/rozeslat", status_code=302)
        progress = dict(progress)  # snapshot under lock

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
    with _sending_lock:
        progress = _sending_progress.get(session_id)
        if not progress or progress.get("done"):
            _sending_progress.pop(session_id, None)
            response = HTMLResponse("")
            response.headers["HX-Redirect"] = f"/dane/{session_id}/rozeslat"
            return response
        progress = dict(progress)  # snapshot under lock

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
    with _sending_lock:
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
    with _sending_lock:
        progress = _sending_progress.get(session_id)
        if progress and not progress.get("done"):
            progress["paused"] = False
            progress["waiting_batch_confirm"] = False

    session = db.query(TaxSession).get(session_id)
    if session:
        session.send_status = SendStatus.SENDING
        db.commit()

    return RedirectResponse(f"/dane/{session_id}/rozeslat/prubeh", status_code=302)


@router.post("/{session_id}/rozeslat/zrusit")
async def cancel_sending(
    session_id: int,
    db: Session = Depends(get_db),
):
    """Cancel the sending process — stop thread, reset QUEUED distributions to PENDING."""
    with _sending_lock:
        progress = _sending_progress.get(session_id)
        if progress and not progress.get("done"):
            progress["done"] = True  # signal thread to stop

    # Reset QUEUED distributions back to PENDING
    queued_dists = (
        db.query(TaxDistribution)
        .join(TaxDistribution.document)
        .filter(
            TaxDocument.session_id == session_id,
            TaxDistribution.email_status == EmailDeliveryStatus.QUEUED,
        )
        .all()
    )
    for dist in queued_dists:
        dist.email_status = EmailDeliveryStatus.PENDING

    session = db.query(TaxSession).get(session_id)
    if session:
        session.send_status = SendStatus.PAUSED
        db.commit()

    return RedirectResponse(f"/dane/{session_id}/rozeslat", status_code=302)


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
    with _sending_lock:
        progress = _sending_progress.get(session_id)
        if progress and not progress.get("done"):
            return RedirectResponse(f"/dane/{session_id}/rozeslat/prubeh", status_code=302)

    # Build recipients and filter to failed only
    documents = (
        db.query(TaxDocument)
        .filter_by(session_id=session_id)
        .options(
            joinedload(TaxDocument.distributions)
            .joinedload(TaxDistribution.owner),
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
    with _sending_lock:
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
