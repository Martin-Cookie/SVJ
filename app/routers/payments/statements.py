"""Router pro bankovní výpisy — import CSV, seznam, detail, párování."""

import shutil
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request, UploadFile, File
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from app.database import get_db
from app.config import settings
from app.models import (
    BankStatement, Payment, PaymentDirection, PaymentMatchStatus,
    VariableSymbolMapping, Prescription, Unit, Owner,
)
from app.utils import build_list_url, is_htmx_partial, validate_upload, strip_diacritics
from ._helpers import templates, logger, compute_nav_stats

router = APIRouter()


# ── Seznam výpisů ──────────────────────────────────────────────────────


@router.get("/vypisy")
async def vypisy_seznam(request: Request, db: Session = Depends(get_db)):
    """Seznam importovaných bankovních výpisů."""
    statements = (
        db.query(BankStatement)
        .order_by(BankStatement.period_from.desc())
        .all()
    )

    # Statistiky pro každý výpis
    for stmt in statements:
        stats = (
            db.query(
                func.count(Payment.id).label("total"),
                func.count(Payment.id).filter(Payment.match_status == PaymentMatchStatus.AUTO_MATCHED).label("matched"),
                func.count(Payment.id).filter(Payment.match_status == PaymentMatchStatus.MANUAL).label("manual"),
                func.count(Payment.id).filter(Payment.match_status == PaymentMatchStatus.UNMATCHED).label("unmatched"),
            )
            .filter(Payment.statement_id == stmt.id)
            .first()
        )
        stmt._stats = {
            "total": stats.total,
            "matched": stats.matched + stats.manual,
            "unmatched": stats.unmatched,
        }

    list_url = build_list_url(request)
    back_url = request.query_params.get("back", "")

    ctx = {
        "request": request,
        "active_nav": "platby",
        "active_tab": "vypisy",
        "statements": statements,
        "list_url": list_url,
        "back_url": back_url,
        **compute_nav_stats(db),
    }
    return templates.TemplateResponse("payments/vypisy.html", ctx)


# ── Import CSV ─────────────────────────────────────────────────────────


@router.get("/vypisy/import")
async def vypis_import_form(request: Request, db: Session = Depends(get_db)):
    """Formulář pro import bankovního výpisu z CSV."""
    back_url = request.query_params.get("back", "")
    return templates.TemplateResponse("payments/vypis_import.html", {
        "request": request,
        "active_nav": "platby",
        "back_url": back_url,
    })


@router.post("/vypisy/import")
async def vypis_import_upload(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Zpracování importu bankovního výpisu z CSV."""
    from app.services.bank_import import parse_fio_csv
    from app.services.payment_matching import match_payments

    # Validace souboru
    error = await validate_upload(file, max_size_mb=10, allowed_extensions=[".csv"])
    if error:
        return templates.TemplateResponse("payments/vypis_import.html", {
            "request": request,
            "active_nav": "platby",
            "error": error,
        })

    # Čtení a parsování
    file_content = await file.read()
    try:
        result = parse_fio_csv(file_content, file.filename)
    except Exception as e:
        logger.error("CSV parse error: %s", e)
        return templates.TemplateResponse("payments/vypis_import.html", {
            "request": request,
            "active_nav": "platby",
            "error": f"Chyba při čtení CSV: {e}",
        })

    if result["errors"]:
        return templates.TemplateResponse("payments/vypis_import.html", {
            "request": request,
            "active_nav": "platby",
            "error": "Chyby při parsování: " + "; ".join(result["errors"][:5]),
        })

    if not result["transactions"]:
        return templates.TemplateResponse("payments/vypis_import.html", {
            "request": request,
            "active_nav": "platby",
            "error": "CSV neobsahuje žádné transakce.",
        })

    meta = result["metadata"]

    # Kontrola duplicity výpisu (podle období)
    existing = (
        db.query(BankStatement)
        .filter_by(period_from=meta.get("period_from"), period_to=meta.get("period_to"))
        .first()
    )
    form_data = await request.form()
    force = form_data.get("force_overwrite")
    if existing and not force:
        period_label = ""
        if meta.get("period_from"):
            period_label = f"{meta['period_from'].strftime('%d.%m.%Y')} – {meta['period_to'].strftime('%d.%m.%Y')}"
        # Počet ručně přiřazených plateb
        manual_count = (
            db.query(Payment)
            .filter(
                Payment.statement_id == existing.id,
                Payment.match_status == PaymentMatchStatus.MANUAL,
            )
            .count()
        )
        return templates.TemplateResponse("payments/vypis_import.html", {
            "request": request,
            "active_nav": "platby",
            "confirm_overwrite": True,
            "existing": existing,
            "period_label": period_label,
            "filename": file.filename,
            "transaction_count": len(result["transactions"]),
            "manual_count": manual_count,
        })

    # Zachování ručních přiřazení
    manual_map = {}
    if existing:
        preserve = form_data.get("preserve_manual")
        if preserve:
            manual_payments = (
                db.query(Payment.operation_id, Payment.unit_id, Payment.match_status)
                .filter(
                    Payment.statement_id == existing.id,
                    Payment.match_status == PaymentMatchStatus.MANUAL,
                    Payment.unit_id.isnot(None),
                    Payment.operation_id.isnot(None),
                )
                .all()
            )
            manual_map = {p.operation_id: p.unit_id for p in manual_payments}
        db.delete(existing)
        db.flush()

    # Uložit soubor
    dest_dir = settings.upload_dir / "csv"
    dest_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    dest_path = dest_dir / f"{ts}_{file.filename}"
    with open(dest_path, "wb") as f:
        f.write(file_content)

    # Vytvořit BankStatement
    statement = BankStatement(
        filename=file.filename,
        file_path=str(dest_path),
        bank_account=meta.get("bank_account"),
        period_from=meta.get("period_from"),
        period_to=meta.get("period_to"),
        opening_balance=meta.get("opening_balance"),
        closing_balance=meta.get("closing_balance"),
        total_income=meta.get("total_income", 0),
        total_expense=meta.get("total_expense", 0),
        transaction_count=len(result["transactions"]),
    )
    db.add(statement)
    db.flush()

    # Vložit transakce (s deduplikací přes operation_id)
    existing_ops = set(
        r[0] for r in db.query(Payment.operation_id).filter(
            Payment.operation_id.isnot(None)
        ).all()
    )

    inserted = 0
    skipped = 0
    for t in result["transactions"]:
        if t["operation_id"] in existing_ops:
            skipped += 1
            continue

        db.add(Payment(
            statement_id=statement.id,
            operation_id=t["operation_id"],
            date=t["date"],
            amount=t["amount"],
            direction=PaymentDirection.INCOME if t["direction"] == "income" else PaymentDirection.EXPENSE,
            counter_account=t["counter_account"],
            counter_account_name=t["counter_account_name"],
            bank_code=t["bank_code"],
            bank_name=t["bank_name"],
            ks=t["ks"],
            vs=t["vs"],
            ss=t["ss"],
            note=t["note"],
            message=t["message"],
            payment_type=t["payment_type"],
            match_status=PaymentMatchStatus.UNMATCHED,
        ))
        existing_ops.add(t["operation_id"])
        inserted += 1

    db.flush()

    # Automatické párování
    pf = meta.get("period_from")
    year = pf.year if pf else datetime.utcnow().year
    match_result = match_payments(db, statement.id, year)

    # Obnovit ruční přiřazení z předchozího importu
    restored = 0
    if manual_map:
        for payment in db.query(Payment).filter(
            Payment.statement_id == statement.id,
            Payment.operation_id.in_(list(manual_map.keys())),
        ).all():
            payment.unit_id = manual_map[payment.operation_id]
            payment.match_status = PaymentMatchStatus.MANUAL
            restored += 1
        match_result["matched"] += restored

    statement.matched_count = match_result["matched"]
    db.commit()

    return RedirectResponse(
        f"/platby/vypisy/{statement.id}?flash=import_ok"
        f"&inserted={inserted}&skipped={skipped}"
        f"&matched={match_result['matched']}&unmatched={match_result['unmatched']}",
        status_code=302,
    )


# ── Detail výpisu ──────────────────────────────────────────────────────


SORT_COLUMNS_PAYMENTS = {
    "datum": Payment.date,
    "castka": Payment.amount,
    "vs": Payment.vs,
    "protiucet": Payment.counter_account_name,
    "stav": Payment.match_status,
}


@router.get("/vypisy/{statement_id}")
async def vypis_detail(
    request: Request,
    statement_id: int,
    sort: str = "datum",
    order: str = "asc",
    q: str = "",
    stav: str = "",
    smer: str = "",
    db: Session = Depends(get_db),
):
    """Detail bankovního výpisu — seznam plateb."""
    statement = db.query(BankStatement).get(statement_id)
    if not statement:
        return RedirectResponse("/platby/vypisy", status_code=302)

    query = (
        db.query(Payment)
        .filter_by(statement_id=statement_id)
        .options(joinedload(Payment.unit), joinedload(Payment.owner))
    )

    # Filtry (stav, směr v SQL)
    if stav:
        query = query.filter(Payment.match_status == stav)

    if smer == "prijem":
        query = query.filter(Payment.direction == PaymentDirection.INCOME)
    elif smer == "vydej":
        query = query.filter(Payment.direction == PaymentDirection.EXPENSE)

    # Řazení
    col = SORT_COLUMNS_PAYMENTS.get(sort, Payment.date)
    if col is not None:
        from sqlalchemy import asc as sa_asc, desc as sa_desc
        order_fn = sa_desc if order == "desc" else sa_asc
        query = query.order_by(order_fn(col).nulls_last())

    payments = query.all()

    # Hledání Python-side (diakritika-safe)
    if q:
        q_ascii = strip_diacritics(q)
        payments = [
            p for p in payments
            if q in (p.vs or "")
            or q_ascii in strip_diacritics(p.counter_account_name or "")
            or q_ascii in strip_diacritics(p.note or "")
            or q_ascii in strip_diacritics(p.message or "")
        ]

    # Statistiky
    total_income = sum(p.amount for p in payments if p.direction == PaymentDirection.INCOME)
    total_expense = sum(p.amount for p in payments if p.direction == PaymentDirection.EXPENSE)
    matched_count = sum(1 for p in payments if p.match_status != PaymentMatchStatus.UNMATCHED)

    # Flash zprávy
    flash_message = ""
    flash_type = ""
    flash = request.query_params.get("flash", "")
    if flash == "import_ok":
        inserted = request.query_params.get("inserted", "0")
        skipped = request.query_params.get("skipped", "0")
        matched = request.query_params.get("matched", "0")
        unmatched = request.query_params.get("unmatched", "0")
        flash_message = (
            f"Import dokončen: {inserted} plateb vloženo"
            + (f", {skipped} duplicit přeskočeno" if int(skipped) > 0 else "")
            + f", {matched} napárováno, {unmatched} nenapárováno."
        )
    elif flash == "match_ok":
        flash_message = "Ruční přiřazení uloženo."
    elif flash == "match_fail":
        flash_message = "Jednotka s tímto číslem nebyla nalezena."
        flash_type = "error"
    elif flash == "rematch_ok":
        matched = request.query_params.get("matched", "0")
        flash_message = f"Přepárování dokončeno: {matched} plateb napárováno."

    list_url = build_list_url(request)
    back_url = request.query_params.get("back", "")

    ctx = {
        "request": request,
        "active_nav": "platby",
        "statement": statement,
        "payments": payments,
        "total_income": total_income,
        "total_expense": total_expense,
        "matched_count": matched_count,
        "sort": sort,
        "order": order,
        "q": q,
        "stav": stav,
        "smer": smer,
        "list_url": list_url,
        "back_url": back_url,
        "flash_message": flash_message,
        "flash_type": flash_type,
    }

    if is_htmx_partial(request):
        return templates.TemplateResponse("payments/partials/vypis_tbody.html", ctx)

    return templates.TemplateResponse("payments/vypis_detail.html", ctx)


# ── Ruční přiřazení platby ─────────────────────────────────────────────


@router.post("/vypisy/{statement_id}/prirazeni/{payment_id}")
async def platba_prirazeni(
    request: Request,
    statement_id: int,
    payment_id: int,
    unit_id: int = Form(...),
    db: Session = Depends(get_db),
):
    """Ručně přiřadit platbu k jednotce (unit_id = číslo jednotky)."""
    payment = db.query(Payment).filter_by(id=payment_id, statement_id=statement_id).first()
    if not payment:
        return RedirectResponse(f"/platby/vypisy/{statement_id}", status_code=302)

    # unit_id z formuláře je unit_number
    unit = db.query(Unit).filter_by(unit_number=unit_id).first()
    if not unit:
        return RedirectResponse(
            f"/platby/vypisy/{statement_id}?flash=match_fail",
            status_code=302,
        )

    payment.unit_id = unit.id
    payment.match_status = PaymentMatchStatus.MANUAL

    # Najdi vlastníka
    from app.models import OwnerUnit
    ou = (
        db.query(OwnerUnit)
        .filter_by(unit_id=unit.id)
        .filter(OwnerUnit.valid_to.is_(None))
        .first()
    )
    if ou:
        payment.owner_id = ou.owner_id

    db.commit()

    return RedirectResponse(f"/platby/vypisy/{statement_id}?flash=match_ok", status_code=302)


# ── Přepárování výpisu ─────────────────────────────────────────────────


@router.post("/vypisy/{statement_id}/preparovat")
async def vypis_preparovat(
    request: Request,
    statement_id: int,
    db: Session = Depends(get_db),
):
    """Znovu spustit automatické párování pro výpis."""
    from app.services.payment_matching import match_payments

    statement = db.query(BankStatement).get(statement_id)
    if not statement:
        return RedirectResponse("/platby/vypisy", status_code=302)

    # Reset nenapárovaných (ponech ruční)
    db.query(Payment).filter_by(
        statement_id=statement_id,
        match_status=PaymentMatchStatus.AUTO_MATCHED,
    ).update({
        Payment.unit_id: None,
        Payment.owner_id: None,
        Payment.prescription_id: None,
        Payment.match_status: PaymentMatchStatus.UNMATCHED,
    })
    db.flush()

    year = statement.period_from.year if statement.period_from else datetime.utcnow().year
    result = match_payments(db, statement_id, year)
    statement.matched_count = result["matched"]
    db.commit()

    return RedirectResponse(
        f"/platby/vypisy/{statement_id}?flash=rematch_ok&matched={result['matched']}",
        status_code=302,
    )


# ── Smazání výpisu ─────────────────────────────────────────────────────


@router.post("/vypisy/{statement_id}/smazat")
async def vypis_smazat(
    request: Request,
    statement_id: int,
    db: Session = Depends(get_db),
):
    """Smazat bankovní výpis a jeho platby."""
    statement = db.query(BankStatement).get(statement_id)
    if statement:
        # Smazat soubor
        if statement.file_path:
            try:
                Path(statement.file_path).unlink()
            except Exception:
                pass
        db.delete(statement)
        db.commit()
    return RedirectResponse("/platby/vypisy", status_code=302)
