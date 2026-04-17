"""Kontrola nedoručených emailů (bounce check) — IMAP integrace."""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from io import BytesIO

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.database import SessionLocal, get_db
from app.models import BankStatement, BounceType, EmailBounce, Owner, TaxSession
from app.services.bounce_service import (
    _fetch_bounces_for_account,
    get_imap_accounts,
    humanize_reason,
)
from app.utils import (
    build_list_url,
    compute_eta,
    excel_auto_width,
    is_htmx_partial,
    strip_diacritics,
    templates,
    utcnow,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# ── Background bounce check progress ──
_bounce_progress: dict | None = None
_bounce_lock = threading.Lock()


SORT_COLUMNS = {
    "datum": EmailBounce.bounced_at,
    "email": EmailBounce.recipient_email,
    "vlastnik": Owner.name_normalized,
    "typ": EmailBounce.bounce_type,
    "duvod": EmailBounce.reason,
    "modul": EmailBounce.module,
    "profil": EmailBounce.smtp_profile_name,
    "vytvoreno": EmailBounce.created_at,
}

_TYPE_LABELS = {
    "hard": "hard",
    "soft": "soft",
    "unknown": "neznamy",
}

_MODULE_LABELS = {
    "tax": "Rozesílání",
    "voting": "Hlasování",
    "payments": "Platby",
    "payment_notice": "Upozornění platby",
    "payment_discrepancy": "Nesrovnalosti",
    "water_notice": "Vodoměry",
}


def _filter_query(
    db: Session,
    typ: str = "",
    modul: str = "",
    q: str = "",
):
    query = db.query(EmailBounce).options(joinedload(EmailBounce.owner))

    if typ in ("hard", "soft", "unknown"):
        query = query.filter(EmailBounce.bounce_type == BounceType(typ))

    if modul:
        query = query.filter(EmailBounce.module == modul)

    if q:
        like = f"%{q.lower()}%"
        like_ascii = f"%{strip_diacritics(q)}%"
        query = query.outerjoin(Owner, EmailBounce.owner_id == Owner.id).filter(
            or_(
                EmailBounce.recipient_email.ilike(like),
                EmailBounce.reason.ilike(like),
                EmailBounce.subject.ilike(like),
                Owner.name_normalized.like(like_ascii),
            )
        )
    return query


def _counts(db: Session):
    base = db.query(EmailBounce)
    return {
        "total": base.count(),
        "hard": base.filter(EmailBounce.bounce_type == BounceType.HARD).count(),
        "soft": base.filter(EmailBounce.bounce_type == BounceType.SOFT).count(),
        "unknown": base.filter(EmailBounce.bounce_type == BounceType.UNKNOWN).count(),
    }


def _module_counts(db: Session):
    rows = (
        db.query(EmailBounce.module, EmailBounce.id)
        .filter(EmailBounce.module.isnot(None))
        .all()
    )
    out: dict[str, int] = {}
    for mod, _ in rows:
        out[mod] = out.get(mod, 0) + 1
    return out


def _resolve_references(db: Session, items: list[EmailBounce]) -> dict:
    """Batch lookup reference entit (TaxSession, BankStatement) pro link v sloupci Modul.

    Vrací dict {(module, ref_id): {"name": str, "url": str}}.
    """
    tax_ids: set[int] = set()
    stmt_ids: set[int] = set()
    for b in items:
        if not b.reference_id:
            continue
        if b.module == "tax":
            tax_ids.add(b.reference_id)
        elif b.module == "payment_notice":
            stmt_ids.add(b.reference_id)

    out: dict = {}
    if tax_ids:
        for s in db.query(TaxSession).filter(TaxSession.id.in_(tax_ids)).all():
            label = s.title
            if s.year:
                label = f"{s.title} ({s.year})"
            out[("tax", s.id)] = {"name": label, "url": f"/rozesilani/{s.id}"}
    if stmt_ids:
        for st in db.query(BankStatement).filter(BankStatement.id.in_(stmt_ids)).all():
            if st.period_from and st.period_to:
                label = f"{st.filename} ({st.period_from.strftime('%d.%m.%Y')}–{st.period_to.strftime('%d.%m.%Y')})"
            else:
                label = st.filename
            out[("payment_notice", st.id)] = {
                "name": label,
                "url": f"/platby/vypisy/{st.id}/nesrovnalosti",
            }
    return out


def _last_check(db: Session) -> datetime | None:
    last = db.query(EmailBounce).order_by(EmailBounce.created_at.desc()).first()
    return last.created_at if last else None


@router.get("/rozesilani/bounces")
async def bounces_page(
    request: Request,
    typ: str = Query(""),
    modul: str = Query(""),
    q: str = Query(""),
    sort: str = Query("datum"),
    order: str = Query("desc"),
    flash: str = Query(""),
    new: int = Query(0),
    chyba: str = Query(""),
    db: Session = Depends(get_db),
):
    query = _filter_query(db, typ=typ, modul=modul, q=q)

    sort_col = SORT_COLUMNS.get(sort, EmailBounce.bounced_at)
    if sort == "vlastnik":
        query = query.outerjoin(Owner, EmailBounce.owner_id == Owner.id)
    if order == "asc":
        query = query.order_by(sort_col.asc().nulls_last(), EmailBounce.id.desc())
    else:
        query = query.order_by(sort_col.desc().nulls_last(), EmailBounce.id.desc())

    items = query.all()

    unique_keys: set = set()
    for b in items:
        key = (b.owner_id, (b.recipient_email or "").lower()) if b.owner_id else ("noown", (b.recipient_email or "").lower())
        unique_keys.add(key)
    unique_count = len(unique_keys)

    flash_message = None
    flash_type = None
    if flash == "ok":
        flash_message = f"Kontrola dokončena. Nových nedoručených: {new}"
    elif chyba:
        flash_message = chyba
        flash_type = "error"

    ctx = {
        "items": items,
        "unique_count": unique_count,
        "counts": _counts(db),
        "module_counts": _module_counts(db),
        "module_labels": _MODULE_LABELS,
        "references": _resolve_references(db, items),
        "reason_labels": {
            b.id: humanize_reason(b.reason or b.diagnostic_code, b.bounce_type)
            for b in items
        },
        "typ": typ,
        "modul": modul,
        "q": q,
        "sort": sort,
        "order": order,
        "last_check": _last_check(db),
        "list_url": build_list_url(request),
        "flash_message": flash_message,
        "flash_type": flash_type,
        "active_nav": "bounces",
    }

    if is_htmx_partial(request):
        return templates.TemplateResponse(request, "bounces/_table.html", ctx)
    return templates.TemplateResponse(request, "bounces/index.html", ctx)


def _run_bounce_check_thread():
    """Background thread — kontrola bounces pro všechny IMAP účty."""
    db = SessionLocal()
    try:
        accounts = get_imap_accounts(db)
        if not accounts:
            with _bounce_lock:
                if _bounce_progress:
                    _bounce_progress["error"] = "Žádný IMAP účet nakonfigurován"
                    _bounce_progress["done"] = True
                    _bounce_progress["finished_at"] = time.monotonic()
            return

        existing_uids = {
            row[0] for row in
            db.query(EmailBounce.imap_uid).filter(EmailBounce.imap_uid.isnot(None)).all()
        }

        with _bounce_lock:
            if _bounce_progress:
                _bounce_progress["total_accounts"] = len(accounts)

        for acc_idx, acc in enumerate(accounts):
            with _bounce_lock:
                if _bounce_progress and _bounce_progress.get("cancelled"):
                    break
                if _bounce_progress:
                    _bounce_progress["current_account"] = acc_idx + 1
                    _bounce_progress["account_name"] = acc["name"]
                    _bounce_progress["account_scanned"] = 0
                    _bounce_progress["account_total"] = 0
                    _bounce_progress["status"] = f"Připojování k {acc['name']}…"

            def on_progress(scanned, total, new_count):
                with _bounce_lock:
                    if _bounce_progress:
                        _bounce_progress["account_scanned"] = scanned
                        _bounce_progress["account_total"] = total
                        _bounce_progress["new_count"] += new_count - _bounce_progress.get("_last_new", 0)
                        _bounce_progress["_last_new"] = new_count
                        _bounce_progress["status"] = f"{acc['name']}: {scanned}/{total} emailů"

            def cancelled():
                with _bounce_lock:
                    return bool(_bounce_progress and _bounce_progress.get("cancelled"))

            with _bounce_lock:
                if _bounce_progress:
                    _bounce_progress["_last_new"] = 0

            result = _fetch_bounces_for_account(
                db, acc, existing_uids,
                mark_invalid=True,
                on_progress=on_progress,
                cancelled=cancelled,
            )

            with _bounce_lock:
                if _bounce_progress:
                    _bounce_progress["scanned"] += result["scanned"]
                    if result["error"]:
                        errors = _bounce_progress.get("errors", [])
                        errors.append(result["error"])
                        _bounce_progress["errors"] = errors

    except Exception as exc:
        logger.exception("Bounce check thread selhal: %s", exc)
        with _bounce_lock:
            if _bounce_progress:
                _bounce_progress["error"] = str(exc)
    finally:
        db.close()
        with _bounce_lock:
            if _bounce_progress:
                _bounce_progress["done"] = True
                _bounce_progress["finished_at"] = time.monotonic()
                _bounce_progress["status"] = "Dokončeno"


@router.post("/rozesilani/bounces/zkontrolovat")
async def run_bounce_check(
    request: Request,
    db: Session = Depends(get_db),
):
    global _bounce_progress

    # Already running?
    with _bounce_lock:
        if _bounce_progress and not _bounce_progress.get("done"):
            return RedirectResponse("/rozesilani/bounces/zkontrolovat/prubeh", status_code=302)

    with _bounce_lock:
        _bounce_progress = {
            "total_accounts": 0,
            "current_account": 0,
            "account_name": "",
            "account_scanned": 0,
            "account_total": 0,
            "new_count": 0,
            "scanned": 0,
            "errors": [],
            "error": None,
            "done": False,
            "cancelled": False,
            "started_at": time.monotonic(),
            "finished_at": None,
            "status": "Načítání IMAP účtů…",
        }

    thread = threading.Thread(target=_run_bounce_check_thread, daemon=True)
    thread.start()

    return RedirectResponse("/rozesilani/bounces/zkontrolovat/prubeh", status_code=302)


@router.get("/rozesilani/bounces/zkontrolovat/prubeh")
async def bounce_check_progress_page(request: Request):
    """Stránka s progress barem kontroly bounces."""
    with _bounce_lock:
        if not _bounce_progress:
            return RedirectResponse("/rozesilani/bounces", status_code=302)
        progress = dict(_bounce_progress)

    return templates.TemplateResponse(request, "bounces/progress.html", {
        "active_nav": "bounces",
        **_bounce_eta(progress),
    })


@router.get("/rozesilani/bounces/zkontrolovat/prubeh-stav")
async def bounce_check_progress_status(request: Request):
    """HTMX polling — vrací progress partial nebo redirect po dokončení."""
    global _bounce_progress

    with _bounce_lock:
        if not _bounce_progress:
            response = HTMLResponse("")
            response.headers["HX-Redirect"] = "/rozesilani/bounces"
            return response

        if _bounce_progress.get("done"):
            finished_at = _bounce_progress.get("finished_at", 0)
            if time.monotonic() - finished_at >= 3:
                new_count = _bounce_progress.get("new_count", 0)
                errors = _bounce_progress.get("errors", [])
                _bounce_progress = None
                url = f"/rozesilani/bounces?flash=ok&new={new_count}"
                if errors:
                    url += f"&chyba={'%3B '.join(e[:100] for e in errors[:3])}"
                response = HTMLResponse("")
                response.headers["HX-Redirect"] = url
                return response

        progress = dict(_bounce_progress)

    return templates.TemplateResponse(request, "bounces/_progress_inner.html", {
        **_bounce_eta(progress),
    })


@router.post("/rozesilani/bounces/zkontrolovat/zrusit")
async def cancel_bounce_check():
    """Zrušit probíhající kontrolu."""
    with _bounce_lock:
        if _bounce_progress and not _bounce_progress.get("done"):
            _bounce_progress["cancelled"] = True
            _bounce_progress["status"] = "Rušení…"

    return RedirectResponse("/rozesilani/bounces/zkontrolovat/prubeh", status_code=302)


def _bounce_eta(progress: dict) -> dict:
    """Compute ETA + flatten progress dict for templates."""
    current = progress.get("account_scanned", 0)
    total = progress.get("account_total", 0)
    eta = compute_eta(current, total, progress.get("started_at", time.monotonic()))

    return {
        "total_accounts": progress.get("total_accounts", 0),
        "current_account": progress.get("current_account", 0),
        "account_name": progress.get("account_name", ""),
        "account_scanned": current,
        "account_total": total,
        "new_count": progress.get("new_count", 0),
        "scanned": progress.get("scanned", 0),
        "status": progress.get("status", ""),
        "done": progress.get("done", False),
        "cancelled": progress.get("cancelled", False),
        "error": progress.get("error"),
        "errors": progress.get("errors", []),
        **eta,
    }


@router.get("/rozesilani/bounces/exportovat/{fmt}")
async def export_bounces(
    fmt: str,
    request: Request,
    typ: str = Query(""),
    modul: str = Query(""),
    q: str = Query(""),
    dedup: int = Query(0),
    db: Session = Depends(get_db),
):
    items = _filter_query(db, typ=typ, modul=modul, q=q).order_by(
        EmailBounce.bounced_at.desc().nulls_last()
    ).all()

    if dedup:
        seen: set = set()
        unique: list[EmailBounce] = []
        for b in items:
            key = (b.owner_id, (b.recipient_email or "").lower()) if b.owner_id else ("noown", (b.recipient_email or "").lower())
            if key in seen:
                continue
            seen.add(key)
            unique.append(b)
        items = unique

    suffix = "vsechny"
    if typ:
        suffix = _TYPE_LABELS.get(typ, typ)
    elif modul:
        suffix = strip_diacritics(modul).replace(" ", "_")
    elif q:
        suffix = "hledani"
    if dedup:
        suffix = f"{suffix}_unikatni" if suffix != "vsechny" else "unikatni"

    today = utcnow().strftime("%Y%m%d")
    filename = f"bounces_{suffix}_{today}.{fmt}"

    headers_row = ["Datum", "Email", "Vlastník", "Typ", "Důvod", "Diagnostic", "Modul", "Reference", "Profil", "Předmět"]

    def _row(b: EmailBounce) -> list[str]:
        return [
            b.bounced_at.strftime("%d.%m.%Y %H:%M") if b.bounced_at else "",
            b.recipient_email or "",
            b.owner.display_name if b.owner else "",
            b.bounce_type.value if b.bounce_type else "",
            (b.reason or "")[:300],
            (b.diagnostic_code or "")[:300],
            _MODULE_LABELS.get(b.module or "", b.module or ""),
            str(b.reference_id) if b.reference_id else "",
            b.smtp_profile_name or "",
            (b.subject or "")[:300],
        ]

    if fmt == "xlsx":
        from openpyxl import Workbook
        from openpyxl.styles import Font

        wb = Workbook()
        ws = wb.active
        ws.title = "Nedoručené"
        ws.append(headers_row)
        for cell in ws[1]:
            cell.font = Font(bold=True)
        for b in items:
            ws.append(_row(b))
        excel_auto_width(ws)

        buf = BytesIO()
        wb.save(buf)
        buf.seek(0)
        return StreamingResponse(
            buf,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    if fmt == "csv":
        import csv

        buf = BytesIO()
        text_buf = []
        text_buf.append("\ufeff" + ";".join(headers_row))
        for b in items:
            row = _row(b)
            text_buf.append(";".join('"' + (c or "").replace('"', '""') + '"' for c in row))
        data = "\r\n".join(text_buf).encode("utf-8")
        return StreamingResponse(
            BytesIO(data),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    return RedirectResponse("/rozesilani/bounces", status_code=302)
