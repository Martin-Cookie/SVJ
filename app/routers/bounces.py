"""Kontrola nedoručených emailů (bounce check) — IMAP integrace."""

from __future__ import annotations

import logging
from datetime import datetime
from io import BytesIO

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import RedirectResponse, StreamingResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import BankStatement, BounceType, EmailBounce, Owner, TaxSession
from app.services.bounce_service import fetch_bounces, humanize_reason
from app.utils import (
    build_list_url,
    excel_auto_width,
    is_htmx_partial,
    strip_diacritics,
    templates,
    utcnow,
)

logger = logging.getLogger(__name__)

router = APIRouter()


SORT_COLUMNS = {
    "datum": EmailBounce.bounced_at,
    "email": EmailBounce.recipient_email,
    "vlastnik": Owner.name_normalized,
    "typ": EmailBounce.bounce_type,
    "duvod": EmailBounce.reason,
    "modul": EmailBounce.module,
    "vytvoreno": EmailBounce.created_at,
}

_TYPE_LABELS = {
    "hard": "hard",
    "soft": "soft",
    "unknown": "neznamy",
}

_MODULE_LABELS = {
    "tax": "Daně",
    "voting": "Hlasování",
    "payments": "Platby",
    "payment_notice": "Upozornění platby",
    "payment_discrepancy": "Nesrovnalosti",
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
            out[("tax", s.id)] = {"name": label, "url": f"/dane/{s.id}"}
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

    flash_message = None
    flash_type = None
    if flash == "ok":
        flash_message = f"Kontrola dokončena. Nových nedoručených: {new}"
    elif chyba:
        flash_message = chyba
        flash_type = "error"

    ctx = {
        "items": items,
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


@router.post("/rozesilani/bounces/zkontrolovat")
async def run_bounce_check(
    request: Request,
    db: Session = Depends(get_db),
):
    result = fetch_bounces(db)
    if result["success"]:
        return RedirectResponse(
            f"/rozesilani/bounces?flash=ok&new={result['new_count']}",
            status_code=302,
        )
    err = (result.get("error") or "Neznámá chyba")[:300]
    return RedirectResponse(
        f"/rozesilani/bounces?chyba={err}",
        status_code=302,
    )


@router.get("/rozesilani/bounces/exportovat/{fmt}")
async def export_bounces(
    fmt: str,
    request: Request,
    typ: str = Query(""),
    modul: str = Query(""),
    q: str = Query(""),
    db: Session = Depends(get_db),
):
    items = _filter_query(db, typ=typ, modul=modul, q=q).order_by(
        EmailBounce.bounced_at.desc().nulls_last()
    ).all()

    suffix = "vsechny"
    if typ:
        suffix = _TYPE_LABELS.get(typ, typ)
    elif modul:
        suffix = strip_diacritics(modul).replace(" ", "_")
    elif q:
        suffix = "hledani"

    today = utcnow().strftime("%Y%m%d")
    filename = f"bounces_{suffix}_{today}.{fmt}"

    headers_row = ["Datum", "Email", "Vlastník", "Typ", "Důvod", "Diagnostic", "Modul", "Reference", "Předmět"]

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
