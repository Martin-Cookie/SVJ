"""Router pro nesrovnalosti — preview, odesílání upozornění."""

import asyncio
import logging
import threading
import time

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db, SessionLocal
from app.models import BankStatement, Payment
from app.utils import build_list_url, compute_eta, utcnow
from ._helpers import templates, compute_nav_stats, MONTH_NAMES_LONG, _discrepancy_progress, _discrepancy_lock

router = APIRouter()


# ── Řazení ────────────────────────────────────────────────────────────

SORT_COLUMNS_DISCREPANCY = {
    "datum": lambda d: d.payment_date,
    "odesilatel": lambda d: d.sender_name.lower(),
    "zaplaceno": lambda d: d.payment_amount,
    "predpis": lambda d: d.expected_amount,
    "vs_platby": lambda d: d.payment_vs,
    "vs_predpisu": lambda d: d.entity_vs,
    "prirazeno": lambda d: d.entity_label.lower(),
    "typ": lambda d: ",".join(d.types),
    "prijemce": lambda d: d.recipient_name.lower(),
    "email": lambda d: d.recipient_email.lower() if d.recipient_email else "zzz",
}


# ── Helpers ───────────────────────────────────────────────────────────


def _discrepancy_base_ctx(request, db, statement, discrepancies, back_url, sort, order):
    """Společný kontext pro nesrovnalosti preview stránku."""
    from app.services.payment_discrepancy import DISCREPANCY_LABELS, build_email_context
    from app.models import EmailTemplate, EmailLog, SvjInfo
    from app.utils import render_email_template

    # Řazení
    sort_key = SORT_COLUMNS_DISCREPANCY.get(sort, SORT_COLUMNS_DISCREPANCY["datum"])
    discrepancies.sort(key=sort_key, reverse=(order == "desc"))

    # Historie odeslaných upozornění pro tento výpis
    sent_logs = (
        db.query(EmailLog)
        .filter_by(module="payment_notice", reference_id=statement.id)
        .order_by(EmailLog.created_at.desc())
        .all()
    )

    # Filtrovat jen ty s emailem
    sendable = [d for d in discrepancies if d.recipient_email]

    # Načíst šablonu a SVJ info pro náhledy
    template = db.query(EmailTemplate).filter_by(name="Upozornění na nesrovnalost v platbě").first()
    svj = db.query(SvjInfo).first()
    svj_name = svj.name if svj else "SVJ"
    pf = statement.period_from
    month_name = MONTH_NAMES_LONG.get(pf.month, "") if pf else ""
    year = pf.year if pf else 0

    # Generovat náhledy pro sendable — dict payment_id → {subject, body}
    email_previews = {}
    for d in sendable:
        ctx_email = build_email_context(d, svj_name, month_name, year)
        subject = render_email_template(template.subject_template, ctx_email) if template else f"Upozornění na nesrovnalost v platbě za {month_name} {year}"
        body = render_email_template(template.body_template, ctx_email) if template else ""
        email_previews[d.payment_id] = {
            "subject": subject,
            "body": body,
        }

    return {
        "request": request,
        "active_nav": "platby",
        "active_tab": "vypisy",
        "statement": statement,
        "discrepancies": discrepancies,
        "sendable": sendable,
        "email_previews": email_previews,
        "discrepancy_labels": DISCREPANCY_LABELS,
        "template": template,
        "svj": svj,
        "sent_logs": sent_logs,
        "sort": sort,
        "order": order,
        "list_url": build_list_url(request),
        "back_url": back_url,
        "month_names": MONTH_NAMES_LONG,
        **(compute_nav_stats(db)),
    }


def _discrepancy_eta(progress: dict) -> dict:
    """Vypočítat ETA a formátovat progress pro šablonu."""
    eta = compute_eta(progress["sent"] + progress["failed"], progress["total"], progress["started_at"])
    return {
        "total": progress["total"],
        "sent": progress["sent"],
        "failed": progress["failed"],
        "current_recipient": progress.get("current_recipient", ""),
        "error": progress.get("error"),
        "paused": progress.get("paused", False),
        "waiting_batch_confirm": progress.get("waiting_batch_confirm", False),
        "batch_number": progress.get("batch_number", 0),
        "total_batches": progress.get("total_batches", 0),
        "done": progress.get("done", False),
        "elapsed": eta["elapsed"],
        "eta": eta["eta"],
    }


def _send_discrepancy_emails_batch(
    statement_id: int,
    recipient_data: list[dict],
    batch_size: int = 10,
    batch_interval: int = 5,
    confirm_each_batch: bool = False,
):
    """Background thread: odeslat upozornění na nesrovnalosti v dávkách."""
    from app.services.email_service import create_smtp_connection, send_email
    from app.models import EmailTemplate, SvjInfo
    from app.utils import render_email_template
    from app.services.payment_discrepancy import build_email_context

    db = SessionLocal()
    try:
        # Načíst šablonu a SVJ info
        template = db.query(EmailTemplate).filter_by(name="Upozornění na nesrovnalost v platbě").first()
        svj = db.query(SvjInfo).first()
        svj_name = svj.name if svj else "SVJ"
        statement = db.query(BankStatement).get(statement_id)
        pf = statement.period_from if statement else None
        month_name = MONTH_NAMES_LONG.get(pf.month, "") if pf else ""
        year = pf.year if pf else 0

        # Split into batches
        batches = []
        for i in range(0, len(recipient_data), batch_size):
            batches.append(recipient_data[i:i + batch_size])

        with _discrepancy_lock:
            _discrepancy_progress[statement_id]["total_batches"] = len(batches)

        # Počáteční prodleva 5s — uživatel vidí progress a může pozastavit/zrušit
        for _ in range(10):
            with _discrepancy_lock:
                if _discrepancy_progress[statement_id].get("done"):
                    return
            time.sleep(0.5)

        for batch_idx, batch in enumerate(batches):
            with _discrepancy_lock:
                _discrepancy_progress[statement_id]["batch_number"] = batch_idx + 1

            # Shared SMTP connection per batch
            smtp_conn = None
            try:
                smtp_conn = create_smtp_connection()
            except Exception:
                logger.warning("Failed to create shared SMTP connection, falling back to per-email")

            for rcpt in batch:
                # Check paused / done
                while True:
                    with _discrepancy_lock:
                        paused = _discrepancy_progress[statement_id].get("paused")
                        done = _discrepancy_progress[statement_id].get("done")
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

                with _discrepancy_lock:
                    if _discrepancy_progress[statement_id].get("done"):
                        if smtp_conn:
                            try:
                                smtp_conn.quit()
                            except Exception:
                                pass
                        return
                    _discrepancy_progress[statement_id]["current_recipient"] = rcpt["name"]

                # Render personalized email
                ctx_email = build_email_context(rcpt["disc"], svj_name, month_name, year)
                subject = render_email_template(template.subject_template, ctx_email) if template else f"Upozornění na nesrovnalost v platbě za {month_name} {year}"
                body = render_email_template(template.body_template, ctx_email) if template else ""
                body_html = body.replace("\n", "<br>")

                try:
                    result = send_email(
                        to_email=rcpt["email"],
                        to_name=rcpt["name"],
                        subject=subject,
                        body_html=body_html,
                        module="payment_notice",
                        reference_id=statement_id,
                        db=db,
                        smtp_server=smtp_conn,
                    )
                except Exception as exc:
                    logger.exception("Chyba při odesílání pro %s (%s)", rcpt["name"], rcpt["email"])
                    result = {"success": False, "error": str(exc)}
                    smtp_conn = None
                    try:
                        smtp_conn = create_smtp_connection()
                    except Exception:
                        logger.warning("Nepodařilo se obnovit SMTP spojení")

                with _discrepancy_lock:
                    if result.get("success"):
                        _discrepancy_progress[statement_id]["sent"] += 1
                        # Zaznamenat odeslání na platbu
                        try:
                            payment = db.query(Payment).get(rcpt["payment_id"])
                            if payment:
                                payment.notified_at = utcnow()
                                db.commit()
                        except Exception:
                            logger.warning("Failed to set notified_at for payment %s", rcpt["payment_id"])
                    else:
                        _discrepancy_progress[statement_id]["failed"] += 1
                        _discrepancy_progress[statement_id].setdefault("failed_ids", []).append(rcpt["payment_id"])

            # Close shared SMTP connection after batch
            if smtp_conn:
                try:
                    smtp_conn.quit()
                except Exception:
                    pass
                smtp_conn = None

            # After batch: wait for interval or confirm
            if batch_idx < len(batches) - 1:
                if confirm_each_batch:
                    # Pozastavit a čekat na potvrzení
                    with _discrepancy_lock:
                        _discrepancy_progress[statement_id]["waiting_batch_confirm"] = True
                    while True:
                        with _discrepancy_lock:
                            done = _discrepancy_progress[statement_id].get("done")
                            waiting = _discrepancy_progress[statement_id].get("waiting_batch_confirm")
                        if done:
                            return
                        if not waiting:
                            break
                        time.sleep(0.5)
                else:
                    for _ in range(batch_interval * 2):
                        with _discrepancy_lock:
                            done = _discrepancy_progress[statement_id].get("done")
                        if done:
                            return
                        time.sleep(0.5)

    except Exception as e:
        logger.exception("Error in batch discrepancy email sending for statement %s", statement_id)
        with _discrepancy_lock:
            _discrepancy_progress[statement_id]["error"] = str(e)
    finally:
        with _discrepancy_lock:
            _discrepancy_progress[statement_id]["done"] = True
            _discrepancy_progress[statement_id]["current_recipient"] = ""
            _discrepancy_progress[statement_id]["finished_at"] = time.monotonic()
        db.close()


# ── Endpointy ─────────────────────────────────────────────────────────


@router.get("/vypisy/{statement_id}/nesrovnalosti")
async def discrepancy_preview(
    request: Request,
    statement_id: int,
    sort: str = "datum",
    order: str = "asc",
    filtr: str = "",
    db: Session = Depends(get_db),
):
    """Preview nesrovnalostí — seznam příjemců a náhled emailu."""
    statement = db.query(BankStatement).get(statement_id)
    if not statement:
        return RedirectResponse("/platby/vypisy", status_code=302)

    from app.services.payment_discrepancy import detect_discrepancies

    all_discrepancies = detect_discrepancies(db, statement_id)

    # Bubble counts (před filtrací)
    all_sendable = [d for d in all_discrepancies if d.recipient_email]
    bubble_counts = {
        "vse": len(all_discrepancies),
        "s_emailem": len(all_sendable),
        "bez_emailu": len(all_discrepancies) - len(all_sendable),
        "odeslano": len([d for d in all_sendable if d.notified_at]),
        "neodeslano": len([d for d in all_sendable if not d.notified_at]),
    }

    # Filtrování
    if filtr == "s_emailem":
        discrepancies = [d for d in all_discrepancies if d.recipient_email]
    elif filtr == "bez_emailu":
        discrepancies = [d for d in all_discrepancies if not d.recipient_email]
    elif filtr == "odeslano":
        discrepancies = [d for d in all_discrepancies if d.recipient_email and d.notified_at]
    elif filtr == "neodeslano":
        discrepancies = [d for d in all_discrepancies if d.recipient_email and not d.notified_at]
    else:
        discrepancies = all_discrepancies

    back_url = request.query_params.get("back", f"/platby/vypisy/{statement_id}")

    ctx = _discrepancy_base_ctx(request, db, statement, discrepancies, back_url, sort, order)
    ctx["filtr"] = filtr
    ctx["bubble_counts"] = bubble_counts

    # Flash zprávy
    flash = request.query_params.get("flash", "")
    if flash == "sent":
        sent = request.query_params.get("sent", "0")
        failed = request.query_params.get("failed", "0")
        ctx["flash_message"] = f"Odesláno {sent} upozornění."
        if int(failed) > 0:
            ctx["flash_message"] += f" {failed} selhalo."
            ctx["flash_type"] = "warning"
    elif flash == "test_ok":
        ctx["flash_message"] = f"Testovací email odeslán na {request.query_params.get('email', '')}"
    elif flash == "test_fail":
        ctx["flash_message"] = f"Chyba: {request.query_params.get('err', 'neznámá chyba')}"
        ctx["flash_type"] = "error"
    elif flash == "settings_ok":
        ctx["flash_message"] = "Nastavení odesílání uloženo"

    return templates.TemplateResponse(request, "payments/nesrovnalosti_preview.html", ctx)


@router.post("/vypisy/{statement_id}/nesrovnalosti/nastaveni")
async def discrepancy_save_settings(
    request: Request,
    statement_id: int,
    db: Session = Depends(get_db),
):
    """Uložit sdílená nastavení odesílání."""
    from app.models import SvjInfo
    form = await request.form()
    svj = db.query(SvjInfo).first()
    if svj:
        svj.send_batch_size = max(1, min(100, int(form.get("send_batch_size", 10))))
        svj.send_batch_interval = max(1, min(60, int(form.get("send_batch_interval", 5))))
        svj.send_confirm_each_batch = form.get("send_confirm_each_batch") == "true"
        db.commit()
    back = form.get("back", "")
    back_param = f"&back={back}" if back else ""
    return RedirectResponse(f"/platby/vypisy/{statement_id}/nesrovnalosti?flash=settings_ok{back_param}", status_code=302)


@router.post("/vypisy/{statement_id}/nesrovnalosti/test")
async def discrepancy_test_email(
    request: Request,
    statement_id: int,
    test_email: str = Form(...),
    db: Session = Depends(get_db),
):
    """Odeslat testovací email s náhledem první nesrovnalosti."""
    from app.services.payment_discrepancy import detect_discrepancies, build_email_context
    from app.services.email_service import send_email
    from app.models import EmailTemplate, SvjInfo
    from app.utils import render_email_template

    statement = db.query(BankStatement).get(statement_id)
    if not statement:
        return RedirectResponse("/platby/vypisy", status_code=302)

    discrepancies = detect_discrepancies(db, statement_id)
    sendable = [d for d in discrepancies if d.recipient_email]

    if not sendable:
        url = f"/platby/vypisy/{statement_id}/nesrovnalosti?flash=test_fail&err=žádné+nesrovnalosti"
        return RedirectResponse(url, status_code=302)

    # Vzít první nesrovnalost pro test
    d = sendable[0]
    template = db.query(EmailTemplate).filter_by(name="Upozornění na nesrovnalost v platbě").first()
    svj = db.query(SvjInfo).first()
    svj_name = svj.name if svj else "SVJ"
    pf = statement.period_from
    month_name = MONTH_NAMES_LONG.get(pf.month, "") if pf else ""
    year = pf.year if pf else 0

    ctx_email = build_email_context(d, svj_name, month_name, year)
    subject = render_email_template(template.subject_template, ctx_email) if template else f"Upozornění na nesrovnalost v platbě za {month_name} {year}"
    body = render_email_template(template.body_template, ctx_email) if template else ""
    body_html = body.replace("\n", "<br>")

    result = await asyncio.to_thread(
        send_email,
        to_email=test_email.strip(),
        to_name="Test",
        subject=f"[TEST] {subject}",
        body_html=body_html,
        module="payment_notice",
        reference_id=statement_id,
        db=db,
    )

    form_data = await request.form()
    back = form_data.get("back", "")
    back_param = f"&back={back}" if back else ""

    if result.get("success"):
        statement.discrepancy_test_passed = True
        # Uložit testovací email do sdílených nastavení
        svj_info = db.query(SvjInfo).first()
        if svj_info:
            svj_info.send_test_email_address = test_email.strip()
        db.commit()
        url = f"/platby/vypisy/{statement_id}/nesrovnalosti?flash=test_ok&email={test_email.strip()}{back_param}"
    else:
        err = result.get("error", "neznámá chyba")[:100]
        url = f"/platby/vypisy/{statement_id}/nesrovnalosti?flash=test_fail&err={err}{back_param}"

    return RedirectResponse(url, status_code=302)


@router.post("/vypisy/{statement_id}/nesrovnalosti/odeslat")
async def discrepancy_send(
    request: Request,
    statement_id: int,
    db: Session = Depends(get_db),
):
    """Zahájit dávkové odesílání vybraných upozornění."""
    statement = db.query(BankStatement).get(statement_id)
    if not statement:
        return RedirectResponse("/platby/vypisy", status_code=302)

    # Test email musí být odeslán
    if not statement.discrepancy_test_passed:
        return RedirectResponse(f"/platby/vypisy/{statement_id}/nesrovnalosti", status_code=302)

    # Check no concurrent sending
    with _discrepancy_lock:
        progress = _discrepancy_progress.get(statement_id)
        if progress and not progress.get("done"):
            return RedirectResponse(f"/platby/vypisy/{statement_id}/nesrovnalosti/prubeh", status_code=302)

    from app.services.payment_discrepancy import detect_discrepancies

    form = await request.form()
    selected_ids = form.getlist("selected_ids")
    if not selected_ids:
        return RedirectResponse(f"/platby/vypisy/{statement_id}/nesrovnalosti", status_code=302)

    selected_set = set(int(x) for x in selected_ids)

    discrepancies = detect_discrepancies(db, statement_id)
    recipients = []
    for d in discrepancies:
        if d.payment_id in selected_set and d.recipient_email:
            recipients.append({
                "payment_id": d.payment_id,
                "name": d.recipient_name,
                "email": d.recipient_email,
                "disc": d,
            })

    if not recipients:
        return RedirectResponse(f"/platby/vypisy/{statement_id}/nesrovnalosti", status_code=302)

    # Sdílená nastavení odesílání
    from app.models import SvjInfo
    svj = db.query(SvjInfo).first()
    batch_size = svj.send_batch_size if svj and svj.send_batch_size else 10
    batch_interval = svj.send_batch_interval if svj and svj.send_batch_interval else 5
    confirm_batch = svj.send_confirm_each_batch if svj else False

    # Initialize progress
    with _discrepancy_lock:
        _discrepancy_progress[statement_id] = {
            "total": len(recipients),
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
            "failed_ids": [],
        }

    # Start background thread
    thread = threading.Thread(
        target=_send_discrepancy_emails_batch,
        args=(statement_id, recipients, batch_size, batch_interval, confirm_batch),
        daemon=True,
    )
    thread.start()

    return RedirectResponse(f"/platby/vypisy/{statement_id}/nesrovnalosti/prubeh", status_code=302)


@router.get("/vypisy/{statement_id}/nesrovnalosti/prubeh")
async def discrepancy_progress_page(
    request: Request,
    statement_id: int,
    db: Session = Depends(get_db),
):
    """Stránka s progress barem odesílání."""
    statement = db.query(BankStatement).get(statement_id)
    if not statement:
        return RedirectResponse("/platby/vypisy", status_code=302)

    with _discrepancy_lock:
        progress = _discrepancy_progress.get(statement_id)
        if not progress:
            return RedirectResponse(f"/platby/vypisy/{statement_id}/nesrovnalosti", status_code=302)
        progress = dict(progress)

    back_url = request.query_params.get("back", f"/platby/vypisy/{statement_id}")

    ctx = {
        "request": request,
        "active_nav": "platby",
        "active_tab": "vypisy",
        "statement": statement,
        "statement_id": statement_id,
        "back_url": back_url,
        "month_names": MONTH_NAMES_LONG,
        **_discrepancy_eta(progress),
        **(compute_nav_stats(db)),
    }
    return templates.TemplateResponse(request, "payments/nesrovnalosti_progress.html", ctx)


@router.get("/vypisy/{statement_id}/nesrovnalosti/prubeh-stav")
async def discrepancy_progress_status(
    request: Request,
    statement_id: int,
):
    """HTMX polling endpoint — vrací progress partial nebo redirect po dokončení."""
    with _discrepancy_lock:
        progress = _discrepancy_progress.get(statement_id)
        if not progress:
            response = HTMLResponse("")
            response.headers["HX-Redirect"] = f"/platby/vypisy/{statement_id}/nesrovnalosti"
            return response
        # Po dokončení počkat 3 sekundy, aby uživatel viděl výsledek
        if progress.get("done"):
            finished_at = progress.get("finished_at", 0)
            if time.monotonic() - finished_at >= 3:
                sent = progress["sent"]
                failed = progress["failed"]
                _discrepancy_progress.pop(statement_id, None)
                response = HTMLResponse("")
                response.headers["HX-Redirect"] = f"/platby/vypisy/{statement_id}/nesrovnalosti?flash=sent&sent={sent}&failed={failed}"
                return response
        progress = dict(progress)

    return templates.TemplateResponse(request, "partials/_send_progress_inner.html", {
        "statement_id": statement_id,
        "progress_label": "Odesílání upozornění",
        **_discrepancy_eta(progress),
    })


@router.post("/vypisy/{statement_id}/nesrovnalosti/pozastavit")
async def discrepancy_pause(statement_id: int):
    """Pozastavit odesílání."""
    with _discrepancy_lock:
        progress = _discrepancy_progress.get(statement_id)
        if progress and not progress.get("done"):
            progress["paused"] = True
    return RedirectResponse(f"/platby/vypisy/{statement_id}/nesrovnalosti/prubeh", status_code=302)


@router.post("/vypisy/{statement_id}/nesrovnalosti/pokracovat")
async def discrepancy_resume(statement_id: int):
    """Pokračovat v odesílání."""
    with _discrepancy_lock:
        progress = _discrepancy_progress.get(statement_id)
        if progress and not progress.get("done"):
            progress["paused"] = False
            progress["waiting_batch_confirm"] = False
    return RedirectResponse(f"/platby/vypisy/{statement_id}/nesrovnalosti/prubeh", status_code=302)


@router.post("/vypisy/{statement_id}/nesrovnalosti/zrusit")
async def discrepancy_cancel(statement_id: int):
    """Zrušit odesílání — zastavit thread."""
    with _discrepancy_lock:
        progress = _discrepancy_progress.get(statement_id)
        if progress and not progress.get("done"):
            progress["done"] = True
            progress["finished_at"] = time.monotonic()
    return RedirectResponse(f"/platby/vypisy/{statement_id}/nesrovnalosti/prubeh", status_code=302)
