from datetime import date

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import cast, Integer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import SyncRecord, SyncResolution, SyncSession, SyncStatus
from app.services.owner_exchange import execute_exchange, prepare_exchange_preview
from app.utils import templates
from ._helpers import _exchange_stats

router = APIRouter()


@router.get("/{session_id}/vymena/{record_id}")
async def exchange_preview_single(
    session_id: int,
    record_id: int,
    filtr: str = "",
    request: Request = None,
    db: Session = Depends(get_db),
):
    """Preview owner exchange for a single unit."""
    session = db.query(SyncSession).get(session_id)
    if not session:
        return RedirectResponse("/synchronizace", status_code=302)

    previews = prepare_exchange_preview(db, [record_id])
    if not previews:
        return RedirectResponse(f"/synchronizace/{session_id}", status_code=302)

    stats = _exchange_stats(previews)
    back_url = f"/synchronizace/{session_id}"
    if filtr:
        back_url += f"?filtr={filtr}"
    back_url += f"#sync-{record_id}"

    return templates.TemplateResponse(request, "sync/exchange_preview.html", {
        "active_nav": "kontroly",
        "session": session,
        "previews": previews,
        "batch": False,
        "record_ids": [record_id],
        "stats": stats,
        "today": date.today().isoformat(),
        "back_url": back_url,
        "filtr": filtr,
    })


@router.post("/{session_id}/vymena/{record_id}/potvrdit")
async def exchange_confirm_single(
    session_id: int,
    record_id: int,
    exchange_date: str = Form(""),
    filtr: str = Form(""),
    db: Session = Depends(get_db),
):
    """Execute owner exchange for a single unit."""
    try:
        ed = date.fromisoformat(exchange_date) if exchange_date else date.today()
    except ValueError:
        ed = date.today()
    execute_exchange(db, [record_id], session_id, exchange_date=ed)
    url = f"/synchronizace/{session_id}"
    if filtr:
        url += f"?filtr={filtr}"
    url += f"#sync-{record_id}"
    return RedirectResponse(url, status_code=302)


@router.post("/{session_id}/vymena-hromadna")
async def exchange_preview_batch(
    session_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Preview batch owner exchange for all DIFFERENCE records."""
    session = db.query(SyncSession).get(session_id)
    if not session:
        return RedirectResponse("/synchronizace", status_code=302)

    form = await request.form()
    filtr = form.get("filtr", "")

    # Get all DIFFERENCE + PENDING records for this session
    records = (
        db.query(SyncRecord)
        .filter_by(session_id=session_id, status=SyncStatus.DIFFERENCE, resolution=SyncResolution.PENDING)
        .order_by(cast(SyncRecord.unit_number, Integer).asc())
        .all()
    )
    record_ids = [r.id for r in records]
    if not record_ids:
        url = f"/synchronizace/{session_id}"
        if filtr:
            url += f"?filtr={filtr}"
        return RedirectResponse(url, status_code=302)

    previews = prepare_exchange_preview(db, record_ids)
    record_ids = [p["record"].id for p in previews]

    stats = _exchange_stats(previews)

    back_url = f"/synchronizace/{session_id}"
    if filtr:
        back_url += f"?filtr={filtr}"

    return templates.TemplateResponse(request, "sync/exchange_preview.html", {
        "active_nav": "kontroly",
        "session": session,
        "previews": previews,
        "batch": True,
        "record_ids": record_ids,
        "stats": stats,
        "today": date.today().isoformat(),
        "back_url": back_url,
        "filtr": filtr,
    })


@router.post("/{session_id}/vymena-hromadna/potvrdit")
async def exchange_confirm_batch(
    session_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Execute batch owner exchange."""
    form = await request.form()
    raw_ids = form.get("record_ids", "")
    record_ids = [int(x) for x in raw_ids.split(",") if x.strip().isdigit()]
    exchange_date_str = form.get("exchange_date", "")
    filtr = form.get("filtr", "")
    try:
        ed = date.fromisoformat(exchange_date_str) if exchange_date_str else date.today()
    except ValueError:
        ed = date.today()
    if record_ids:
        execute_exchange(db, record_ids, session_id, exchange_date=ed)
    url = f"/synchronizace/{session_id}"
    if filtr:
        url += f"?filtr={filtr}"
    return RedirectResponse(url, status_code=302)
