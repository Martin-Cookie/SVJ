"""Router pro rozesílku odečtů vodoměrů — preview, odesílání emailů.

Plná parita s nesrovnalostmi v platbách: checkboxy, bubliny, řazení,
inline náhled emailu, test email gating, notified_at tracking, historie.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session, joinedload

from app.database import SessionLocal, get_db
from app.models import (
    ActivityAction, Owner, OwnerUnit, Unit, WaterMeter, MeterType,
    log_activity,
)
from app.models.administration import EmailTemplate, SvjInfo
from app.models.common import EmailLog
from app.models.smtp_profile import SmtpProfile
from app.utils import build_list_url, compute_eta, render_email_template, templates, utcnow

from ._helpers import compute_consumption, compute_deviations

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory progress tracker for background email sending
_sending_progress: dict[str, dict] = {}
_sending_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Řazení
# ---------------------------------------------------------------------------

SORT_COLUMNS = {
    "prijemce": lambda r: r["name"].lower(),
    "email": lambda r: (r["email"] or "zzz").lower(),
    "jednotky": lambda r: r["unit_labels"].lower(),
    "spotreba_sv": lambda r: r["spotreba_sv"],
    "spotreba_tv": lambda r: r["spotreba_tv"],
    "odchylka_sv": lambda r: abs(r["odchylka_sv"]) if r["odchylka_sv"] is not None else -1,
    "odchylka_tv": lambda r: abs(r["odchylka_tv"]) if r["odchylka_tv"] is not None else -1,
    "vodomer": lambda r: r.get("meter_serials", "").lower(),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_recipients(db: Session) -> list[dict]:
    """Build recipient list: one entry per owner who has units with water meters.

    Each recipient gets aggregated consumption data for all their meters.
    """
    meters = db.query(WaterMeter).options(
        joinedload(WaterMeter.unit),
        joinedload(WaterMeter.readings),
    ).filter(WaterMeter.unit_id.isnot(None)).all()

    if not meters:
        return []

    deviations = compute_deviations(meters)

    # Compute type averages for email comparison
    _type_sums: dict[str, list[float]] = {}
    for m in meters:
        c = compute_consumption(m)
        if c is not None and c >= 0:
            _type_sums.setdefault(m.meter_type, []).append(c)
    type_avg = {
        mt: round(sum(vals) / len(vals), 1) if vals else 0
        for mt, vals in _type_sums.items()
    }

    # Group meters by unit_id
    unit_meters: dict[int, list] = {}
    for m in meters:
        unit_meters.setdefault(m.unit_id, []).append(m)

    # Load current owner-unit relationships
    owner_units = (
        db.query(OwnerUnit)
        .filter(OwnerUnit.valid_to.is_(None))
        .options(
            joinedload(OwnerUnit.owner),
            joinedload(OwnerUnit.unit),
        )
        .all()
    )

    # Build {owner_id: {owner, units: {unit_id: unit}}}
    owner_data: dict[int, dict] = {}
    for ou in owner_units:
        if ou.unit_id not in unit_meters:
            continue
        if ou.owner_id not in owner_data:
            owner_data[ou.owner_id] = {
                "owner": ou.owner,
                "unit_ids": set(),
            }
        owner_data[ou.owner_id]["unit_ids"].add(ou.unit_id)

    recipients = []
    for owner_id, data in owner_data.items():
        owner = data["owner"]
        units_info = []
        all_meter_serials = []
        all_meter_ids = []
        for uid in sorted(data["unit_ids"]):
            u_meters = unit_meters.get(uid, [])
            if not u_meters:
                continue
            unit = u_meters[0].unit
            meter_infos = []
            for m in u_meters:
                consumption = compute_consumption(m)
                dev_info = deviations.get(m.id, {})
                sorted_readings = sorted(m.readings, key=lambda r: r.reading_date) if m.readings else []
                last_reading = sorted_readings[-1] if sorted_readings else None
                prev_reading = sorted_readings[-2] if len(sorted_readings) >= 2 else None
                meter_infos.append({
                    "id": m.id,
                    "serial": m.meter_serial,
                    "type": "SV" if m.meter_type == MeterType.COLD else "TV",
                    "type_key": m.meter_type.value,
                    "location": m.location or "",
                    "last_value": last_reading.value if last_reading else None,
                    "last_date": last_reading.reading_date if last_reading else None,
                    "prev_value": prev_reading.value if prev_reading else None,
                    "prev_date": prev_reading.reading_date if prev_reading else None,
                    "consumption": consumption,
                    "deviation_pct": dev_info.get("deviation_pct"),
                    "notified_at": m.notified_at,
                })
                all_meter_serials.append(m.meter_serial)
                all_meter_ids.append(m.id)
            units_info.append({
                "unit_number": unit.unit_number,
                "unit_letter": u_meters[0].unit_letter or "",
                "meters": meter_infos,
            })

        # Aggregate consumption by type
        total_sv = sum(
            mi["consumption"] or 0
            for ui in units_info for mi in ui["meters"]
            if mi["type_key"] == "cold" and mi["consumption"] is not None
        )
        total_tv = sum(
            mi["consumption"] or 0
            for ui in units_info for mi in ui["meters"]
            if mi["type_key"] == "hot" and mi["consumption"] is not None
        )
        sv_devs = [
            mi["deviation_pct"] for ui in units_info for mi in ui["meters"]
            if mi["type_key"] == "cold" and mi["deviation_pct"] is not None
        ]
        tv_devs = [
            mi["deviation_pct"] for ui in units_info for mi in ui["meters"]
            if mi["type_key"] == "hot" and mi["deviation_pct"] is not None
        ]

        unit_labels = ", ".join(
            f"{ui['unit_number']}{ui['unit_letter']}" for ui in units_info
        )

        # Determine notified_at — from owner, not meters (shared units/SJM)
        latest_notified = owner.water_notified_at

        recipients.append({
            "owner_id": owner_id,
            "name": owner.display_name,
            "email": owner.email or "",
            "units": units_info,
            "unit_labels": unit_labels,
            "meter_serials": ", ".join(all_meter_serials),
            "meter_ids": all_meter_ids,
            "spotreba_sv": round(total_sv, 1),
            "spotreba_tv": round(total_tv, 1),
            "odchylka_sv": round(sum(sv_devs) / len(sv_devs), 1) if sv_devs else None,
            "odchylka_tv": round(sum(tv_devs) / len(tv_devs), 1) if tv_devs else None,
            "notified_at": latest_notified,
            "type_avg": type_avg,
        })

    recipients.sort(key=lambda r: r["name"])
    return recipients


def _fmt(val: float | None) -> str:
    """Format number with comma decimal separator (Czech)."""
    if val is None:
        return "—"
    return f"{val:.1f}".replace(".", ",")


def _build_email_context(rcpt: dict) -> dict:
    """Build email template context for a recipient.

    Includes per-meter reading data for HTML table (variant B).
    TV section is omitted when all TV consumption is 0.
    """
    type_avg = rcpt.get("type_avg", {})
    avg_sv = type_avg.get(MeterType.COLD, 0)
    avg_tv = type_avg.get(MeterType.HOT, 0)

    odecty_sv: list[dict] = []
    odecty_tv: list[dict] = []

    for ui in rcpt.get("units", []):
        for mi in ui["meters"]:
            if mi["consumption"] is None:
                continue  # meter without 2+ readings — skip

            avg = avg_sv if mi["type_key"] == "cold" else avg_tv
            dev = mi["deviation_pct"]

            if dev is not None and avg > 0:
                if dev > 5:
                    srovnani = f"\u25b2 +{dev:.0f}\u00a0%"
                elif dev < -5:
                    srovnani = f"\u25bc {dev:.0f}\u00a0%"
                else:
                    srovnani = f"\u2248 {dev:+.0f}\u00a0%"
            else:
                srovnani = "—"

            entry = {
                "cislo": mi["serial"],
                "predchozi": f"{_fmt(mi['prev_value'])} m\u00b3",
                "aktualni": f"{_fmt(mi['last_value'])} m\u00b3",
                "spotreba": f"{_fmt(mi['consumption'])} m\u00b3",
                "prumer": f"{_fmt(avg)} m\u00b3",
                "srovnani": srovnani,
            }

            if mi["type_key"] == "cold":
                odecty_sv.append(entry)
            else:
                odecty_tv.append(entry)

    # Skip TV entirely if all TV consumption is 0
    has_tv = any(
        mi["consumption"] and mi["consumption"] > 0
        for ui in rcpt.get("units", [])
        for mi in ui["meters"]
        if mi["type_key"] == "hot"
    )

    return {
        "jmeno": rcpt["name"],
        "jednotka": rcpt["unit_labels"],
        "spotreba_sv": str(rcpt["spotreba_sv"]),
        "spotreba_tv": str(rcpt["spotreba_tv"]),
        "odchylka_sv": f"{rcpt['odchylka_sv']:+.0f}" if rcpt["odchylka_sv"] is not None else "—",
        "odchylka_tv": f"{rcpt['odchylka_tv']:+.0f}" if rcpt["odchylka_tv"] is not None else "—",
        "vodomer": rcpt["meter_serials"],
        "obdobi": "",
        "odecty_sv": odecty_sv,
        "odecty_tv": odecty_tv if has_tv else [],
        "prumer_sv": _fmt(avg_sv),
        "prumer_tv": _fmt(avg_tv),
    }


def _sending_eta(progress: dict) -> dict:
    """Compute ETA fields from sending progress dict."""
    sent = progress["sent"]
    failed = progress["failed"]
    current = sent + failed
    eta = compute_eta(current, progress["total"], progress["started_at"])

    return {
        "total": progress["total"],
        "sent": sent,
        "failed": failed,
        "current": current,
        "current_recipient": progress.get("current_recipient", ""),
        "done": progress.get("done", False),
        "error": progress.get("error"),
        "paused": progress.get("paused", False),
        "waiting_batch_confirm": progress.get("waiting_batch_confirm", False),
        "batch_number": progress.get("batch_number", 0),
        "total_batches": progress.get("total_batches", 0),
        "elapsed": eta["elapsed"],
        "eta": eta["eta"],
    }


def _send_emails_batch(
    send_id: str,
    recipient_data: list[dict],
    batch_size: int,
    batch_interval: int,
    confirm_each_batch: bool,
    smtp_profile_id: Optional[int] = None,
):
    """Background thread: send water meter emails in batches."""
    from app.services.email_service import create_smtp_connection, send_email

    db = SessionLocal()
    try:
        template = db.query(EmailTemplate).filter_by(name="Odečty vodoměrů").first()

        batches = []
        for i in range(0, len(recipient_data), batch_size):
            batches.append(recipient_data[i:i + batch_size])

        with _sending_lock:
            _sending_progress[send_id]["total_batches"] = len(batches)

        # Počáteční prodleva 5s — uživatel vidí progress a může pozastavit/zrušit
        for _ in range(10):
            with _sending_lock:
                if _sending_progress[send_id].get("done"):
                    return
            time.sleep(0.5)

        for batch_idx, batch in enumerate(batches):
            with _sending_lock:
                _sending_progress[send_id]["batch_number"] = batch_idx + 1

            smtp_conn = None
            try:
                smtp_conn = create_smtp_connection(profile_id=smtp_profile_id)
            except Exception:
                logger.warning("Failed to create shared SMTP connection, falling back to per-email")

            for rcpt in batch:
                # Check paused / done
                while True:
                    with _sending_lock:
                        paused = _sending_progress[send_id].get("paused")
                        done = _sending_progress[send_id].get("done")
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
                    if _sending_progress[send_id].get("done"):
                        if smtp_conn:
                            try:
                                smtp_conn.quit()
                            except Exception:
                                pass
                        return
                    _sending_progress[send_id]["current_recipient"] = rcpt["name"]

                # Render personalized email
                ctx = _build_email_context(rcpt)
                subject = render_email_template(template.subject_template, ctx) if template else f"Odečty vodoměrů — {rcpt['unit_labels']}"
                body = render_email_template(template.body_template, ctx) if template else ""
                body_html = body.replace("\n", "<br>")

                try:
                    result = send_email(
                        to_email=rcpt["email"],
                        to_name=rcpt["name"],
                        subject=subject,
                        body_html=body_html,
                        module="water_notice",
                        db=db,
                        smtp_server=smtp_conn,
                        smtp_profile_id=smtp_profile_id,
                    )
                except Exception as exc:
                    logger.exception("Chyba při odesílání pro %s (%s)", rcpt["name"], rcpt["email"])
                    result = {"success": False, "error": str(exc)}
                    smtp_conn = None
                    try:
                        smtp_conn = create_smtp_connection(profile_id=smtp_profile_id)
                    except Exception:
                        logger.warning("Nepodařilo se obnovit SMTP spojení")

                with _sending_lock:
                    if result.get("success"):
                        _sending_progress[send_id]["sent"] += 1
                        # Zaznamenat odeslání — notified_at na vodoměrech i vlastníkovi
                        try:
                            now = utcnow()
                            for mid in rcpt["meter_ids"]:
                                meter = db.query(WaterMeter).get(mid)
                                if meter:
                                    meter.notified_at = now
                            owner = db.query(Owner).get(rcpt["owner_id"])
                            if owner:
                                owner.water_notified_at = now
                            db.commit()
                        except Exception:
                            logger.warning("Failed to set notified_at for owner %s", rcpt["owner_id"])
                            try:
                                db.rollback()
                            except Exception:
                                pass
                    else:
                        _sending_progress[send_id]["failed"] += 1
                        _sending_progress[send_id].setdefault("failed_ids", []).append(rcpt["owner_id"])

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
                    with _sending_lock:
                        _sending_progress[send_id]["waiting_batch_confirm"] = True
                    while True:
                        with _sending_lock:
                            done = _sending_progress[send_id].get("done")
                            waiting = _sending_progress[send_id].get("waiting_batch_confirm")
                        if done:
                            return
                        if not waiting:
                            break
                        time.sleep(0.5)
                else:
                    for _ in range(batch_interval * 2):
                        with _sending_lock:
                            done = _sending_progress[send_id].get("done")
                        if done:
                            return
                        time.sleep(0.5)

        # Log activity
        log_activity(db, ActivityAction.STATUS_CHANGED, "water_meters", "vodometry",
                     description=f"Rozesílka odečtů vodoměrů dokončena: {_sending_progress[send_id]['sent']} odesláno")
        db.commit()

    except Exception as e:
        logger.exception("Error in water meter batch email sending")
        with _sending_lock:
            _sending_progress[send_id]["error"] = str(e)
    finally:
        with _sending_lock:
            _sending_progress[send_id]["done"] = True
            _sending_progress[send_id]["current_recipient"] = ""
            _sending_progress[send_id]["finished_at"] = time.monotonic()
        db.close()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/rozeslat", response_class=HTMLResponse)
async def send_preview(request: Request, db: Session = Depends(get_db)):
    """Preview stránka rozesílky — příjemci, konfigurace, historie."""
    sort = request.query_params.get("sort", "prijemce")
    order = request.query_params.get("order", "asc")
    filtr = request.query_params.get("filtr", "")

    all_recipients = _build_recipients(db)

    # Bubble counts (před filtrací)
    all_sendable = [r for r in all_recipients if r["email"]]
    bubble_counts = {
        "vse": len(all_recipients),
        "s_emailem": len(all_sendable),
        "bez_emailu": len(all_recipients) - len(all_sendable),
        "odeslano": len([r for r in all_sendable if r["notified_at"]]),
        "neodeslano": len([r for r in all_sendable if not r["notified_at"]]),
    }

    # Filtrování
    if filtr == "s_emailem":
        recipients = [r for r in all_recipients if r["email"]]
    elif filtr == "bez_emailu":
        recipients = [r for r in all_recipients if not r["email"]]
    elif filtr == "odeslano":
        recipients = [r for r in all_recipients if r["email"] and r["notified_at"]]
    elif filtr == "neodeslano":
        recipients = [r for r in all_recipients if r["email"] and not r["notified_at"]]
    else:
        recipients = all_recipients

    # Řazení
    sort_key = SORT_COLUMNS.get(sort, SORT_COLUMNS["prijemce"])
    recipients.sort(key=sort_key, reverse=(order == "desc"))

    # Email template + previews
    template = db.query(EmailTemplate).filter_by(name="Odečty vodoměrů").first()
    svj = db.query(SvjInfo).first()

    email_previews = {}
    for r in all_sendable:
        ctx = _build_email_context(r)
        subject = render_email_template(template.subject_template, ctx) if template else f"Odečty vodoměrů — {r['unit_labels']}"
        body = render_email_template(template.body_template, ctx) if template else ""
        email_previews[r["owner_id"]] = {"subject": subject, "body": body}

    # SMTP profily
    smtp_profiles = db.query(SmtpProfile).order_by(SmtpProfile.is_default.desc(), SmtpProfile.id).all()

    # Historie odeslaných emailů
    sent_logs = (
        db.query(EmailLog)
        .filter_by(module="water_notice")
        .order_by(EmailLog.created_at.desc())
        .limit(200)
        .all()
    )

    ctx = {
        "active_nav": "water_meters",
        "recipients": recipients,
        "sendable": all_sendable,
        "email_previews": email_previews,
        "total_recipients": len(all_recipients),
        "with_email": len(all_sendable),
        "without_email": len(all_recipients) - len(all_sendable),
        "smtp_profiles": smtp_profiles,
        "svj": svj,
        "template": template,
        "sent_logs": sent_logs,
        "sort": sort,
        "order": order,
        "filtr": filtr,
        "bubble_counts": bubble_counts,
        "list_url": build_list_url(request),
    }

    # Flash zprávy
    flash = request.query_params.get("flash", "")
    if flash == "sent":
        sent = request.query_params.get("sent", "0")
        failed = request.query_params.get("failed", "0")
        ctx["flash_message"] = f"Odesláno {sent} upozornění."
        if int(failed) > 0:
            ctx["flash_message"] += f" {failed} selhalo."
            ctx["flash_type"] = "warning"
        else:
            ctx["flash_type"] = "success"
    elif flash == "test_ok":
        ctx["flash_message"] = f"Testovací email odeslán na {request.query_params.get('email', '')}"
        ctx["flash_type"] = "success"
    elif flash == "test_fail":
        ctx["flash_message"] = f"Chyba: {request.query_params.get('err', 'neznámá chyba')}"
        ctx["flash_type"] = "error"
    elif flash == "settings_ok":
        ctx["flash_message"] = "Nastavení odesílání uloženo"
        ctx["flash_type"] = "success"

    return templates.TemplateResponse(request, "water_meters/send.html", ctx)


@router.post("/rozeslat/nastaveni")
async def save_send_settings(
    request: Request,
    db: Session = Depends(get_db),
):
    """Uložit nastavení odesílání."""
    form = await request.form()
    svj = db.query(SvjInfo).first()
    if svj:
        svj.send_batch_size = max(1, min(100, int(form.get("send_batch_size", 10))))
        svj.send_batch_interval = max(1, min(60, int(form.get("send_batch_interval", 5))))
        svj.send_confirm_each_batch = form.get("send_confirm_each_batch") == "true"
        smtp_pid = form.get("smtp_profile_id")
        if smtp_pid:
            svj.smtp_profile_id = int(smtp_pid) if hasattr(svj, "smtp_profile_id") else None
        db.commit()

    return RedirectResponse("/vodometry/rozeslat?flash=settings_ok", status_code=302)


@router.post("/rozeslat/test")
async def send_test_email(
    request: Request,
    db: Session = Depends(get_db),
):
    """Odeslat testovací email s náhledem prvního příjemce."""
    import asyncio
    from app.services.email_service import send_email

    form = await request.form()
    test_email = form.get("test_email", "").strip()
    smtp_pid = form.get("smtp_profile_id")
    smtp_profile_id = int(smtp_pid) if smtp_pid else None

    if not test_email:
        return RedirectResponse("/vodometry/rozeslat?flash=test_fail&err=Chybí+email", status_code=302)

    recipients = _build_recipients(db)
    sendable = [r for r in recipients if r["email"]]

    if not sendable:
        return RedirectResponse("/vodometry/rozeslat?flash=test_fail&err=žádní+příjemci", status_code=302)

    # Vzít prvního příjemce pro realistický náhled
    rcpt = sendable[0]
    template = db.query(EmailTemplate).filter_by(name="Odečty vodoměrů").first()
    ctx = _build_email_context(rcpt)
    subject = render_email_template(template.subject_template, ctx) if template else f"Odečty vodoměrů — {rcpt['unit_labels']}"
    body = render_email_template(template.body_template, ctx) if template else ""
    body_html = body.replace("\n", "<br>")

    result = await asyncio.to_thread(
        send_email,
        to_email=test_email,
        to_name="Test",
        subject=f"[TEST] {subject}",
        body_html=body_html,
        module="water_notice",
        db=db,
        smtp_profile_id=smtp_profile_id,
    )

    svj = db.query(SvjInfo).first()
    if result.get("success"):
        if svj:
            svj.water_test_passed = True
            svj.send_test_email_address = test_email
        db.commit()
        return RedirectResponse(f"/vodometry/rozeslat?flash=test_ok&email={test_email}", status_code=302)
    else:
        err = result.get("error", "neznámá chyba")[:100]
        return RedirectResponse(f"/vodometry/rozeslat?flash=test_fail&err={err}", status_code=302)


@router.post("/rozeslat/odeslat")
async def start_batch_send(
    request: Request,
    db: Session = Depends(get_db),
):
    """Zahájit dávkové odesílání vybraných upozornění."""
    svj = db.query(SvjInfo).first()

    # Test email musí být odeslán
    if not svj or not svj.water_test_passed:
        return RedirectResponse("/vodometry/rozeslat", status_code=302)

    # Check no concurrent sending
    send_id = "water"
    with _sending_lock:
        progress = _sending_progress.get(send_id)
        if progress and not progress.get("done"):
            return RedirectResponse("/vodometry/rozeslat/prubeh", status_code=302)

    form = await request.form()
    selected_ids = form.getlist("selected_ids")
    if not selected_ids:
        return RedirectResponse("/vodometry/rozeslat", status_code=302)

    selected_set = set(int(x) for x in selected_ids)

    # Build recipients and filter to selected
    all_recipients = _build_recipients(db)

    # Cache invalid emails
    invalid_emails = set()
    for o in db.query(Owner).filter(Owner.email_invalid == True).all():  # noqa: E712
        for field in (o.email, o.email_secondary):
            if field:
                for e in field.replace(",", ";").split(";"):
                    e = e.strip().lower()
                    if e:
                        invalid_emails.add(e)

    recipients = []
    for r in all_recipients:
        if r["owner_id"] in selected_set and r["email"]:
            if r["email"].strip().lower() in invalid_emails:
                continue
            recipients.append(r)

    if not recipients:
        return RedirectResponse("/vodometry/rozeslat", status_code=302)

    batch_size = svj.send_batch_size or 10
    batch_interval = svj.send_batch_interval or 5
    confirm_batch = svj.send_confirm_each_batch or False

    log_activity(db, ActivityAction.STATUS_CHANGED, "water_meters", "vodometry",
                 description=f"Rozesílka odečtů vodoměrů zahájena: {len(recipients)} příjemců")
    db.commit()

    # Initialize progress
    with _sending_lock:
        _sending_progress[send_id] = {
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

    thread = threading.Thread(
        target=_send_emails_batch,
        args=(send_id, recipients, batch_size, batch_interval, confirm_batch),
        daemon=True,
    )
    thread.start()

    return RedirectResponse("/vodometry/rozeslat/prubeh", status_code=302)


@router.get("/rozeslat/prubeh", response_class=HTMLResponse)
async def sending_progress_page(request: Request):
    """Show progress page while emails are being sent."""
    send_id = "water"
    with _sending_lock:
        progress = _sending_progress.get(send_id)
        if not progress:
            return RedirectResponse("/vodometry/rozeslat", status_code=302)
        progress = dict(progress)

    return templates.TemplateResponse(request, "water_meters/sending.html", {
        "active_nav": "water_meters",
        **_sending_eta(progress),
    })


@router.get("/rozeslat/prubeh-stav", response_class=HTMLResponse)
async def sending_progress_status(request: Request):
    """HTMX polling endpoint — returns progress partial or redirect when done."""
    send_id = "water"
    with _sending_lock:
        progress = _sending_progress.get(send_id)
        if not progress:
            response = HTMLResponse("")
            response.headers["HX-Redirect"] = "/vodometry/rozeslat"
            return response
        if progress.get("done"):
            finished_at = progress.get("finished_at", 0)
            if time.monotonic() - finished_at >= 3:
                sent = progress["sent"]
                failed = progress["failed"]
                _sending_progress.pop(send_id, None)
                response = HTMLResponse("")
                response.headers["HX-Redirect"] = f"/vodometry/rozeslat?flash=sent&sent={sent}&failed={failed}"
                return response
        progress = dict(progress)

    return templates.TemplateResponse(request, "partials/_send_progress_inner.html", {
        "progress_label": "Odesílání odečtů vodoměrů",
        **_sending_eta(progress),
    })


@router.post("/rozeslat/pozastavit")
async def pause_sending():
    """Pause the sending process."""
    send_id = "water"
    with _sending_lock:
        progress = _sending_progress.get(send_id)
        if progress and not progress.get("done"):
            progress["paused"] = True
    return RedirectResponse("/vodometry/rozeslat/prubeh", status_code=302)


@router.post("/rozeslat/pokracovat")
async def resume_sending():
    """Resume the sending process (also confirms batch)."""
    send_id = "water"
    with _sending_lock:
        progress = _sending_progress.get(send_id)
        if progress and not progress.get("done"):
            progress["paused"] = False
            progress["waiting_batch_confirm"] = False
    return RedirectResponse("/vodometry/rozeslat/prubeh", status_code=302)


@router.post("/rozeslat/zrusit")
async def cancel_sending():
    """Cancel the sending process."""
    send_id = "water"
    with _sending_lock:
        progress = _sending_progress.get(send_id)
        if progress and not progress.get("done"):
            progress["done"] = True
            progress["finished_at"] = time.monotonic()
    return RedirectResponse("/vodometry/rozeslat/prubeh", status_code=302)
