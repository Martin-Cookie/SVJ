"""Router pro bankovní výpisy — import CSV, seznam, detail, párování."""

import asyncio
import logging
import threading
import time
from pathlib import Path

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, Form, Request, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import asc as sa_asc, desc as sa_desc, func
from sqlalchemy.orm import Session, joinedload

from app.database import get_db, SessionLocal
from app.config import settings
from app.models import (
    BankStatement, Owner, OwnerUnit, Payment, PaymentAllocation, PaymentDirection,
    PaymentMatchStatus, Space, SpaceTenant, Tenant, Unit,
)
from app.utils import build_list_url, compute_eta, is_htmx_partial, is_safe_path, validate_upload, strip_diacritics, utcnow, UPLOAD_LIMITS
from ._helpers import templates, compute_nav_stats, MONTH_NAMES_LONG, _discrepancy_progress, _discrepancy_lock

router = APIRouter()


def _build_suggest_map(
    payments: list,
    name_index: list[tuple[set, int]],
) -> dict[int, int]:
    """Vybudovat mapu payment_id → entity_id z name_index (words_set, entity_id).

    Pro každou UNMATCHED příjmovou platbu najde nejlepší shodu dle společných slov
    v counter_account_name + note + message.
    """
    suggest_map: dict[int, int] = {}
    for p in payments:
        if p.match_status != PaymentMatchStatus.UNMATCHED or p.direction != PaymentDirection.INCOME:
            continue
        text_parts = [p.counter_account_name or "", p.note or "", p.message or ""]
        sender_words = {w for w in strip_diacritics(" ".join(text_parts)).split() if len(w) > 2}
        if not sender_words:
            continue
        best_id = None
        best_score = 0
        for name_words, entity_id in name_index:
            common = sender_words & name_words
            if len(common) >= 1 and len(common) > best_score:
                best_score = len(common)
                best_id = entity_id
        if best_id and best_score >= 1:
            suggest_map[p.id] = best_id
    return suggest_map


# ── Seznam výpisů ──────────────────────────────────────────────────────


@router.get("/vypisy")
async def vypisy_seznam(request: Request, db: Session = Depends(get_db)):
    """Seznam importovaných bankovních výpisů."""
    statements = (
        db.query(BankStatement)
        .order_by(BankStatement.period_from.desc())
        .all()
    )

    # Statistiky pro všechny výpisy jedním dotazem
    stats_rows = (
        db.query(
            Payment.statement_id,
            func.count(Payment.id).label("total"),
            func.count(Payment.id).filter(Payment.match_status == PaymentMatchStatus.AUTO_MATCHED).label("matched"),
            func.count(Payment.id).filter(Payment.match_status == PaymentMatchStatus.SUGGESTED).label("suggested"),
            func.count(Payment.id).filter(Payment.match_status == PaymentMatchStatus.MANUAL).label("manual"),
            func.count(Payment.id).filter(Payment.match_status == PaymentMatchStatus.UNMATCHED).label("unmatched"),
        )
        .group_by(Payment.statement_id)
        .all()
    )
    stats_map = {r.statement_id: r for r in stats_rows}
    for stmt in statements:
        r = stats_map.get(stmt.id)
        stmt._stats = {
            "total": r.total if r else 0,
            "matched": (r.matched + r.manual) if r else 0,
            "suggested": r.suggested if r else 0,
            "unmatched": r.unmatched if r else 0,
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
        "month_names": MONTH_NAMES_LONG,
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
        "active_tab": "vypisy",
        "back_url": back_url,
        **compute_nav_stats(db),
    })


@router.post("/vypisy/import")
async def vypis_import_upload(
    request: Request,
    file: UploadFile = File(None),
    db: Session = Depends(get_db),
):
    """Zpracování importu bankovního výpisu z CSV."""
    from app.services.bank_import import parse_fio_csv
    from app.services.payment_matching import match_payments

    form_data = await request.form()
    force = form_data.get("force_overwrite")
    saved_path = form_data.get("saved_path", "")

    # Při force_overwrite použít uložený soubor
    if force and saved_path:
        saved_file = Path(saved_path)
        if not is_safe_path(saved_file, Path(settings.upload_dir) / "temp"):
            return templates.TemplateResponse("payments/vypis_import.html", {
                "request": request,
                "active_nav": "platby",
                "active_tab": "vypisy",
                "error": "Neplatná cesta k souboru.",
                **compute_nav_stats(db),
            })
        if not saved_file.is_file():
            return templates.TemplateResponse("payments/vypis_import.html", {
                "request": request,
                "active_nav": "platby",
                "active_tab": "vypisy",
                "error": "Uložený soubor expiroval. Nahrajte soubor znovu.",
                **compute_nav_stats(db),
            })
        file_content = saved_file.read_bytes()
        original_filename = saved_file.name.split("_", 2)[-1] if "_" in saved_file.name else saved_file.name
    else:
        # Nový upload — validace
        if not file or not file.filename:
            return templates.TemplateResponse("payments/vypis_import.html", {
                "request": request,
                "active_nav": "platby",
                "active_tab": "vypisy",
                "error": "Vyberte soubor CSV.",
                **compute_nav_stats(db),
            })
        error = await validate_upload(file, **UPLOAD_LIMITS["csv"])
        if error:
            return templates.TemplateResponse("payments/vypis_import.html", {
                "request": request,
                "active_nav": "platby",
                "active_tab": "vypisy",
                "error": error,
                **compute_nav_stats(db),
            })
        file_content = await file.read()
        original_filename = file.filename

    # Čtení a parsování
    try:
        result = parse_fio_csv(file_content, original_filename)
    except Exception as e:
        logger.error("CSV parse error: %s", e)
        return templates.TemplateResponse("payments/vypis_import.html", {
            "request": request,
            "active_nav": "platby",
            "active_tab": "vypisy",
            "error": f"Chyba při čtení CSV: {e}",
            **compute_nav_stats(db),
        })

    if result["errors"]:
        return templates.TemplateResponse("payments/vypis_import.html", {
            "request": request,
            "active_nav": "platby",
            "active_tab": "vypisy",
            "error": "Chyby při parsování: " + "; ".join(result["errors"][:5]),
            **compute_nav_stats(db),
        })

    if not result["transactions"]:
        return templates.TemplateResponse("payments/vypis_import.html", {
            "request": request,
            "active_nav": "platby",
            "active_tab": "vypisy",
            "error": "CSV neobsahuje žádné transakce.",
            **compute_nav_stats(db),
        })

    meta = result["metadata"]

    # Kontrola duplicity výpisu (podle období)
    existing = (
        db.query(BankStatement)
        .filter_by(period_from=meta.get("period_from"), period_to=meta.get("period_to"))
        .first()
    )
    if existing and not force:
        # Uložit soubor na disk pro pozdější použití
        temp_dir = Path(settings.upload_dir) / "temp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        timestamp = utcnow().strftime("%Y%m%d_%H%M%S")
        temp_path = temp_dir / f"{timestamp}_{original_filename}"
        temp_path.write_bytes(file_content)

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
            "active_tab": "vypisy",
            "confirm_overwrite": True,
            "existing": existing,
            "period_label": period_label,
            "filename": original_filename,
            "saved_path": str(temp_path),
            "transaction_count": len(result["transactions"]),
            "manual_count": manual_count,
            **compute_nav_stats(db),
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
    ts = utcnow().strftime("%Y%m%d_%H%M%S")
    dest_path = dest_dir / f"{ts}_{original_filename}"
    with open(dest_path, "wb") as f:
        f.write(file_content)

    # Vytvořit BankStatement
    statement = BankStatement(
        filename=original_filename,
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
    year = pf.year if pf else utcnow().year
    try:
        match_result = match_payments(db, statement.id, year)
    except Exception as e:
        logger.error("Matching failed for statement %d: %s", statement.id, e)
        match_result = {"matched": 0, "suggested": 0, "unmatched": inserted, "total": inserted}

    # Obnovit ruční přiřazení z předchozího importu
    restored = 0
    if manual_map:
        for payment in db.query(Payment).filter(
            Payment.statement_id == statement.id,
            Payment.operation_id.in_(list(manual_map.keys())),
        ).all():
            payment.unit_id = manual_map[payment.operation_id]
            payment.match_status = PaymentMatchStatus.MANUAL
            # Dual-write: vytvořit alokaci
            db.add(PaymentAllocation(
                payment_id=payment.id,
                unit_id=payment.unit_id,
                owner_id=payment.owner_id,
                prescription_id=payment.prescription_id,
                amount=payment.amount,
            ))
            restored += 1
        match_result["matched"] += restored

    statement.matched_count = match_result["matched"]
    db.commit()

    # Cleanup temp souboru
    if saved_path:
        try:
            Path(saved_path).unlink(missing_ok=True)
        except OSError:
            pass

    return RedirectResponse(
        f"/platby/vypisy/{statement.id}?flash=import_ok"
        f"&inserted={inserted}&skipped={skipped}"
        f"&matched={match_result['matched']}"
        f"&suggested={match_result.get('suggested', 0)}"
        f"&unmatched={match_result['unmatched']}",
        status_code=302,
    )


# ── Detail výpisu ──────────────────────────────────────────────────────


SORT_COLUMNS_PAYMENTS = {
    "datum": Payment.date,
    "castka": Payment.amount,
    "vs": Payment.vs,
    "protiucet": Payment.counter_account_name,
    "stav": Payment.match_status,
    "jednotka": None,  # Python-side sort
    "prostor": None,  # Python-side sort
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
    typ: str = "",
    db: Session = Depends(get_db),
):
    """Detail bankovního výpisu — seznam plateb."""
    statement = db.query(BankStatement).get(statement_id)
    if not statement:
        return RedirectResponse("/platby/vypisy", status_code=302)

    from app.models import PaymentAllocation as PA
    query = (
        db.query(Payment)
        .filter_by(statement_id=statement_id)
        .options(
            joinedload(Payment.unit),
            joinedload(Payment.space),
            joinedload(Payment.owner),
            joinedload(Payment.allocations).joinedload(PA.unit),
            joinedload(Payment.allocations).joinedload(PA.space),
        )
    )

    # Filtry (stav, směr, typ v SQL)
    if stav:
        query = query.filter(Payment.match_status == stav)

    if smer == "prijem":
        query = query.filter(Payment.direction == PaymentDirection.INCOME)
    elif smer == "vydej":
        query = query.filter(Payment.direction == PaymentDirection.EXPENSE)

    if typ == "jednotky":
        query = query.filter(Payment.unit_id.isnot(None))
    elif typ == "prostory":
        query = query.filter(Payment.space_id.isnot(None))

    # Řazení
    col = SORT_COLUMNS_PAYMENTS.get(sort, Payment.date)
    if col is not None:
        order_fn = sa_desc if order == "desc" else sa_asc
        query = query.order_by(order_fn(col).nulls_last())

    payments = query.all()

    # Python-side sort pro jednotka/prostor
    if sort in ("jednotka", "prostor"):
        def _unit_key(p):
            if p.unit:
                return p.unit.unit_number or 0
            for a in (p.allocations or []):
                if a.unit:
                    return a.unit.unit_number or 0
            return 0

        def _space_key(p):
            if p.space:
                return p.space.space_number or 0
            for a in (p.allocations or []):
                if a.space:
                    return a.space.space_number or 0
            return 0

        key_fn = _unit_key if sort == "jednotka" else _space_key
        payments.sort(key=key_fn, reverse=(order == "desc"))

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

    # Bubble counts (celkové počty bez filtrů — ale respektují typ filtr)
    typ_filter = []
    if typ == "jednotky":
        typ_filter.append(Payment.unit_id.isnot(None))
    elif typ == "prostory":
        typ_filter.append(Payment.space_id.isnot(None))

    all_payments_for_counts = (
        db.query(Payment.match_status, Payment.direction, func.count())
        .filter_by(statement_id=statement_id)
        .filter(*typ_filter)
        .group_by(Payment.match_status, Payment.direction)
        .all()
    )
    bubble_counts = {
        "vse": 0,
        "auto_matched": 0,
        "suggested": 0,
        "manual": 0,
        "unmatched": 0,
        "prijem": 0,
        "vydej": 0,
    }
    for status, direction, cnt in all_payments_for_counts:
        bubble_counts["vse"] += cnt
        bubble_counts[status.value] += cnt
        if direction == PaymentDirection.INCOME:
            bubble_counts["prijem"] += cnt
        else:
            bubble_counts["vydej"] += cnt

    # Typ bubble counts (celkové počty bez stav/smer filtrů)
    all_count = db.query(func.count()).filter(Payment.statement_id == statement_id).scalar() or 0
    unit_count = db.query(func.count()).filter(
        Payment.statement_id == statement_id, Payment.unit_id.isnot(None)
    ).scalar() or 0
    space_count = db.query(func.count()).filter(
        Payment.statement_id == statement_id, Payment.space_id.isnot(None)
    ).scalar() or 0
    typ_counts = {"vse": all_count, "jednotky": unit_count, "prostory": space_count}

    # Flash zprávy
    flash_message = ""
    flash_type = ""
    flash = request.query_params.get("flash", "")
    if flash == "import_ok":
        inserted = request.query_params.get("inserted", "0")
        skipped = request.query_params.get("skipped", "0")
        matched = request.query_params.get("matched", "0")
        suggested_count = request.query_params.get("suggested", "0")
        unmatched = request.query_params.get("unmatched", "0")
        flash_message = (
            f"Import dokončen: {inserted} plateb vloženo"
            + (f", {skipped} duplicit přeskočeno" if int(skipped) > 0 else "")
            + f", {matched} napárováno"
            + (f", {suggested_count} návrhů" if int(suggested_count) > 0 else "")
            + f", {unmatched} nenapárováno."
        )
    elif flash == "match_ok":
        flash_message = "Ruční přiřazení uloženo."
    elif flash == "match_fail":
        flash_message = "Jednotka s tímto číslem nebyla nalezena."
        flash_type = "error"
    elif flash == "confirmed":
        flash_message = "Návrh potvrzen."
    elif flash == "bulk_confirmed":
        count = request.query_params.get("count", "0")
        flash_message = f"Potvrzeno {count} návrhů."
    elif flash == "rejected":
        flash_message = "Návrh odmítnut."
    elif flash == "rematch_ok":
        matched = request.query_params.get("matched", "0")
        suggested_count = request.query_params.get("suggested", "0")
        flash_message = (
            f"Přepárování dokončeno: {matched} plateb napárováno"
            + (f", {suggested_count} návrhů" if int(suggested_count) > 0 else "")
            + "."
        )
    elif flash == "locked":
        flash_message = "Výpis je zamčený — párování nelze měnit."
        flash_type = "warning"
    elif flash == "lock_ok":
        flash_message = "Párování zamčeno."
    elif flash == "unlock_ok":
        flash_message = "Párování odemčeno."

    # Nesrovnalosti pro upozornění
    from app.services.payment_discrepancy import detect_discrepancies, DISCREPANCY_LABELS
    discrepancies = detect_discrepancies(db, statement_id)

    # Kandidáti pro nenapárované platby
    from app.services.payment_matching import compute_candidates
    from app.models import Prescription, PrescriptionYear
    pf = statement.period_from
    cand_year = pf.year if pf else utcnow().year
    candidates_map = compute_candidates(db, payments, cand_year, statement_id=statement.id)

    # Mapa unit_id → měsíční předpis + VS (pro tooltipy)
    unit_monthly = {}
    unit_vs = {}
    py = db.query(PrescriptionYear).filter_by(year=cand_year).first()
    if py:
        for presc in db.query(Prescription).filter_by(prescription_year_id=py.id).all():
            if presc.unit_id:
                if presc.monthly_total:
                    unit_monthly[presc.unit_id] = presc.monthly_total
                if presc.variable_symbol:
                    unit_vs[presc.unit_id] = presc.variable_symbol

    # Units + owner names for assignment dropdown
    all_units_list = db.query(Unit).order_by(Unit.unit_number).all()
    unit_owner_names = {}  # unit_id → owner display_name
    active_ous = db.query(OwnerUnit).filter(OwnerUnit.valid_to.is_(None)).all()
    all_owners = {o.id: o for o in db.query(Owner).all()}
    for ou in active_ous:
        owner = all_owners.get(ou.owner_id)
        if owner and owner.display_name:
            unit_owner_names[ou.unit_id] = owner.display_name
    # Řadit podle jména vlastníka (bez diakritiky), jednotky bez vlastníka na konec
    all_units_list.sort(key=lambda u: strip_diacritics(unit_owner_names.get(u.id, "zzz")))

    # Suggest map: payment_id → unit_id (pre-select based on counterparty name / message)
    unit_name_index = []  # list of (words_set, unit_id)
    for ou in active_ous:
        owner = all_owners.get(ou.owner_id)
        if owner and owner.name_normalized:
            words = {w for w in strip_diacritics(owner.name_normalized).split() if len(w) > 2}
            if words:
                unit_name_index.append((words, ou.unit_id))
    unit_suggest_map = _build_suggest_map(payments, unit_name_index)

    # Spaces + tenant names for assignment dropdown
    all_spaces = db.query(Space).order_by(Space.space_number).all()
    space_tenant_names = {}
    active_sts = (
        db.query(SpaceTenant)
        .filter_by(is_active=True)
        .options(joinedload(SpaceTenant.tenant).joinedload(Tenant.owner))
        .all()
    )
    space_monthly = {}  # space_id → monthly_rent
    space_vs = {}  # space_id → variable_symbol
    space_name_index = []  # (words_set, space_id)
    for st in active_sts:
        if st.monthly_rent:
            space_monthly[st.space_id] = st.monthly_rent
        if st.variable_symbol:
            space_vs[st.space_id] = st.variable_symbol
        if st.tenant:
            name = st.tenant.display_name
            if name:
                space_tenant_names[st.space_id] = name
                norm = strip_diacritics(name)
                words = {w for w in norm.split() if len(w) > 2}
                if words:
                    space_name_index.append((words, st.space_id))
    # Řadit podle jména nájemce (bez diakritiky), prostory bez nájemce na konec
    all_spaces.sort(key=lambda s: strip_diacritics(space_tenant_names.get(s.id, "zzz")))

    # Suggest map: payment_id → space_id (pre-select based on counterparty/message)
    space_suggest_map = _build_suggest_map(payments, space_name_index)

    list_url = build_list_url(request)
    back_url = request.query_params.get("back", "")

    ctx = {
        "request": request,
        "active_nav": "platby",
        "active_tab": "vypisy",
        "statement": statement,
        "payments": payments,
        "total_income": total_income,
        "total_expense": total_expense,
        "matched_count": matched_count,
        "candidates_map": candidates_map,
        "unit_monthly": unit_monthly,
        "unit_vs": unit_vs,
        "all_units_list": all_units_list,
        "unit_owner_names": unit_owner_names,
        "unit_suggest_map": unit_suggest_map,
        "all_spaces": all_spaces,
        "space_tenant_names": space_tenant_names,
        "space_monthly": space_monthly,
        "space_vs": space_vs,
        "space_suggest_map": space_suggest_map,
        "sort": sort,
        "order": order,
        "q": q,
        "stav": stav,
        "smer": smer,
        "typ": typ,
        "bubble_counts": bubble_counts,
        "typ_counts": typ_counts,
        "list_url": list_url,
        "back_url": back_url,
        "discrepancies": discrepancies,
        "discrepancy_labels": DISCREPANCY_LABELS,
        "flash_message": flash_message,
        "flash_type": flash_type,
        "month_names": MONTH_NAMES_LONG,
        **(compute_nav_stats(db) if not is_htmx_partial(request) else {}),
    }

    if is_htmx_partial(request):
        return templates.TemplateResponse("payments/partials/vypis_tbody.html", ctx)

    return templates.TemplateResponse("payments/vypis_detail.html", ctx)


# ── Ruční přiřazení platby ─────────────────────────────────────────────


def _detail_redirect_url(statement_id: int, form_data, flash: str = "", anchor: str = "") -> str:
    """Sestaví redirect URL zpět na detail výpisu se zachováním filtrů."""
    params = []
    if flash:
        params.append(f"flash={flash}")
    for key in ("q", "sort", "order", "stav", "smer", "typ", "back"):
        val = form_data.get(key, "")
        if val:
            params.append(f"{key}={val}")
    qs = "&".join(params)
    url = f"/platby/vypisy/{statement_id}?{qs}" if qs else f"/platby/vypisy/{statement_id}"
    if anchor:
        url += f"#{anchor}"
    return url


@router.post("/vypisy/{statement_id}/prirazeni/{payment_id}")
async def platba_prirazeni(
    request: Request,
    statement_id: int,
    payment_id: int,
    db: Session = Depends(get_db),
):
    """Ručně přiřadit platbu k jednotce/jednotkám (čísla oddělená čárkou)."""
    form_data = await request.form()

    # Zamčený výpis — nelze měnit
    statement = db.query(BankStatement).get(statement_id)
    if statement and statement.locked_at:
        return RedirectResponse(_detail_redirect_url(statement_id, form_data, "locked"), status_code=302)

    unit_id_raw = form_data.get("unit_id", "").strip()

    payment = db.query(Payment).filter_by(id=payment_id, statement_id=statement_id).first()
    if not payment:
        return RedirectResponse(_detail_redirect_url(statement_id, form_data), status_code=302)

    # Parsovat čísla jednotek (může být "5" nebo "5, 425")
    unit_numbers = []
    for part in unit_id_raw.replace(",", " ").split():
        part = part.strip()
        if part.isdigit():
            unit_numbers.append(int(part))
    if not unit_numbers:
        return RedirectResponse(
            _detail_redirect_url(statement_id, form_data, "match_fail", anchor=f"p-{payment_id}"),
            status_code=302,
        )

    # Najít jednotky
    units = db.query(Unit).filter(Unit.unit_number.in_(unit_numbers)).all()
    if not units or len(units) != len(set(unit_numbers)):
        return RedirectResponse(
            _detail_redirect_url(statement_id, form_data, "match_fail", anchor=f"p-{payment_id}"),
            status_code=302,
        )

    from app.models import OwnerUnit, Prescription, PrescriptionYear

    # Smazat staré alokace
    db.query(PaymentAllocation).filter_by(payment_id=payment.id).delete()

    if len(units) == 1:
        # Single-unit přiřazení
        unit = units[0]
        payment.unit_id = unit.id
        payment.match_status = PaymentMatchStatus.MANUAL

        ou = db.query(OwnerUnit).filter_by(unit_id=unit.id).filter(OwnerUnit.valid_to.is_(None)).first()
        if ou:
            payment.owner_id = ou.owner_id

        db.add(PaymentAllocation(
            payment_id=payment.id,
            unit_id=unit.id,
            owner_id=payment.owner_id,
            prescription_id=payment.prescription_id,
            amount=payment.amount,
        ))
    else:
        # Multi-unit přiřazení — rozdělit částku podle předpisů
        payment.unit_id = None
        payment.match_status = PaymentMatchStatus.MANUAL

        # Najít předpisy pro rozložení částky
        latest_py = db.query(PrescriptionYear).order_by(PrescriptionYear.year.desc()).first()
        prescriptions_map = {}
        if latest_py:
            for presc in db.query(Prescription).filter_by(prescription_year_id=latest_py.id).all():
                if presc.unit_id:
                    prescriptions_map[presc.unit_id] = presc

        total_monthly = sum(
            prescriptions_map[u.id].monthly_total
            for u in units if u.id in prescriptions_map and prescriptions_map[u.id].monthly_total
        ) or 1.0

        for unit in units:
            presc = prescriptions_map.get(unit.id)
            # Rozdělit částku proporcionálně podle předpisů
            if presc and presc.monthly_total and total_monthly > 0:
                alloc_amount = round(payment.amount * presc.monthly_total / total_monthly, 2)
            else:
                alloc_amount = round(payment.amount / len(units), 2)

            ou = db.query(OwnerUnit).filter_by(unit_id=unit.id).filter(OwnerUnit.valid_to.is_(None)).first()
            db.add(PaymentAllocation(
                payment_id=payment.id,
                unit_id=unit.id,
                owner_id=ou.owner_id if ou else None,
                prescription_id=presc.id if presc else None,
                amount=alloc_amount,
            ))

    db.commit()

    return RedirectResponse(
        _detail_redirect_url(statement_id, form_data, "match_ok", anchor=f"p-{payment_id}"),
        status_code=302,
    )


@router.post("/vypisy/{statement_id}/prirazeni-prostor/{payment_id}")
async def platba_prirazeni_prostor(
    request: Request,
    statement_id: int,
    payment_id: int,
    db: Session = Depends(get_db),
):
    """Ručně přiřadit platbu k prostoru (číslo prostoru)."""
    form_data = await request.form()

    statement = db.query(BankStatement).get(statement_id)
    if statement and statement.locked_at:
        return RedirectResponse(_detail_redirect_url(statement_id, form_data, "locked"), status_code=302)

    space_num_raw = form_data.get("space_id", "").strip()
    payment = db.query(Payment).filter_by(id=payment_id, statement_id=statement_id).first()
    if not payment:
        return RedirectResponse(_detail_redirect_url(statement_id, form_data), status_code=302)

    # Najít prostor podle čísla
    space = db.query(Space).filter_by(space_number=space_num_raw).first()
    if not space:
        return RedirectResponse(
            _detail_redirect_url(statement_id, form_data, "match_fail", anchor=f"p-{payment_id}"),
            status_code=302,
        )

    # Smazat staré alokace
    db.query(PaymentAllocation).filter_by(payment_id=payment.id).delete()

    payment.space_id = space.id
    payment.unit_id = None
    payment.match_status = PaymentMatchStatus.MANUAL

    db.add(PaymentAllocation(
        payment_id=payment.id,
        space_id=space.id,
        owner_id=payment.owner_id,
        amount=payment.amount,
    ))

    db.commit()

    return RedirectResponse(
        _detail_redirect_url(statement_id, form_data, "match_ok", anchor=f"p-{payment_id}"),
        status_code=302,
    )


# ── Potvrzení / odmítnutí návrhu ──────────────────────────────────────


@router.post("/vypisy/{statement_id}/potvrdit-vse")
async def platba_potvrdit_vse(
    request: Request,
    statement_id: int,
    db: Session = Depends(get_db),
):
    """Potvrdit všechny SUGGESTED přiřazení najednou (→ MANUAL)."""
    form_data = await request.form()

    statement = db.query(BankStatement).get(statement_id)
    if statement and statement.locked_at:
        return RedirectResponse(_detail_redirect_url(statement_id, form_data, "locked"), status_code=302)

    count = db.query(Payment).filter(
        Payment.statement_id == statement_id,
        Payment.match_status == PaymentMatchStatus.SUGGESTED,
    ).update({Payment.match_status: PaymentMatchStatus.MANUAL})
    db.commit()

    return RedirectResponse(
        _detail_redirect_url(statement_id, form_data, f"bulk_confirmed&count={count}"),
        status_code=302,
    )


@router.post("/vypisy/{statement_id}/potvrdit/{payment_id}")
async def platba_potvrdit(
    request: Request,
    statement_id: int,
    payment_id: int,
    db: Session = Depends(get_db),
):
    """Potvrdit navržené přiřazení (SUGGESTED → MANUAL)."""
    form_data = await request.form()

    # Zamčený výpis — nelze měnit
    statement = db.query(BankStatement).get(statement_id)
    if statement and statement.locked_at:
        return RedirectResponse(_detail_redirect_url(statement_id, form_data, "locked"), status_code=302)

    payment = db.query(Payment).filter_by(id=payment_id, statement_id=statement_id).first()
    if payment and payment.match_status == PaymentMatchStatus.SUGGESTED:
        payment.match_status = PaymentMatchStatus.MANUAL
        db.commit()

    return RedirectResponse(
        _detail_redirect_url(statement_id, form_data, "confirmed", anchor=f"p-{payment_id}"),
        status_code=302,
    )


@router.post("/vypisy/{statement_id}/odmitnout/{payment_id}")
async def platba_odmitnout(
    request: Request,
    statement_id: int,
    payment_id: int,
    db: Session = Depends(get_db),
):
    """Odmítnout navržené přiřazení (SUGGESTED → UNMATCHED)."""
    form_data = await request.form()

    # Zamčený výpis — nelze měnit
    statement = db.query(BankStatement).get(statement_id)
    if statement and statement.locked_at:
        return RedirectResponse(_detail_redirect_url(statement_id, form_data, "locked"), status_code=302)

    payment = db.query(Payment).filter_by(id=payment_id, statement_id=statement_id).first()
    if payment and payment.match_status == PaymentMatchStatus.SUGGESTED:
        payment.unit_id = None
        payment.space_id = None
        payment.owner_id = None
        payment.prescription_id = None
        payment.match_status = PaymentMatchStatus.UNMATCHED
        # Smazat alokace
        db.query(PaymentAllocation).filter_by(payment_id=payment.id).delete()
        db.commit()

    return RedirectResponse(
        _detail_redirect_url(statement_id, form_data, "rejected", anchor=f"p-{payment_id}"),
        status_code=302,
    )


# ── Přepárování výpisu ─────────────────────────────────────────────────


@router.post("/vypisy/{statement_id}/preparovat")
async def vypis_preparovat(
    request: Request,
    statement_id: int,
    db: Session = Depends(get_db),
):
    """Znovu spustit automatické párování pro výpis."""
    from app.services.payment_matching import match_payments

    form_data = await request.form()

    statement = db.query(BankStatement).get(statement_id)
    if not statement:
        return RedirectResponse("/platby/vypisy", status_code=302)

    # Zamčený výpis — nelze přepárovat
    if statement.locked_at:
        url = _detail_redirect_url(statement_id, form_data, "locked")
        return RedirectResponse(url, status_code=302)

    # Smazat alokace pro auto + suggested platby
    reset_payment_ids = [
        pid for (pid,) in db.query(Payment.id).filter(
            Payment.statement_id == statement_id,
            Payment.match_status.in_([PaymentMatchStatus.AUTO_MATCHED, PaymentMatchStatus.SUGGESTED]),
        ).all()
    ]
    if reset_payment_ids:
        db.query(PaymentAllocation).filter(
            PaymentAllocation.payment_id.in_(reset_payment_ids)
        ).delete(synchronize_session="fetch")

    # Reset auto + suggested (ponech ruční)
    db.query(Payment).filter(
        Payment.statement_id == statement_id,
        Payment.match_status.in_([PaymentMatchStatus.AUTO_MATCHED, PaymentMatchStatus.SUGGESTED]),
    ).update({
        Payment.unit_id: None,
        Payment.space_id: None,
        Payment.owner_id: None,
        Payment.prescription_id: None,
        Payment.match_status: PaymentMatchStatus.UNMATCHED,
    }, synchronize_session="fetch")
    db.flush()

    year = statement.period_from.year if statement.period_from else utcnow().year
    result = match_payments(db, statement_id, year)
    statement.matched_count = result["matched"]
    db.commit()

    url = _detail_redirect_url(
        statement_id, form_data,
        f"rematch_ok&matched={result['matched']}&suggested={result.get('suggested', 0)}",
    )
    return RedirectResponse(url, status_code=302)


# ── Smazání výpisu ─────────────────────────────────────────────────────


@router.post("/vypisy/{statement_id}/smazat")
async def vypis_smazat(
    request: Request,
    statement_id: int,
    db: Session = Depends(get_db),
):
    """Smazat bankovní výpis a jeho platby."""
    statement = db.query(BankStatement).get(statement_id)
    if statement and statement.locked_at:
        return RedirectResponse(f"/platby/vypisy/{statement_id}", status_code=302)
    if statement:
        # Smazat soubor
        if statement.file_path:
            try:
                Path(statement.file_path).unlink()
            except OSError:
                logger.debug("Nelze smazat soubor %s", statement.file_path, exc_info=True)
        db.delete(statement)
        db.commit()
    return RedirectResponse("/platby/vypisy", status_code=302)


# ── Zamčení / odemčení párování ──────────────────────────────────────


@router.post("/vypisy/{statement_id}/zamknout")
async def vypis_zamknout(
    request: Request,
    statement_id: int,
    db: Session = Depends(get_db),
):
    """Zamknout/odemknout párování výpisu."""
    form_data = await request.form()

    statement = db.query(BankStatement).get(statement_id)
    if not statement:
        return RedirectResponse("/platby/vypisy", status_code=302)

    if statement.locked_at:
        statement.locked_at = None
        flash = "unlock_ok"
    else:
        statement.locked_at = utcnow()
        flash = "lock_ok"
    db.commit()

    url = _detail_redirect_url(statement_id, form_data, flash)
    return RedirectResponse(url, status_code=302)


# ── Nesrovnalosti — preview a odeslání upozornění ────────────────────────


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

    return templates.TemplateResponse("payments/nesrovnalosti_preview.html", ctx)


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
    return templates.TemplateResponse("payments/nesrovnalosti_progress.html", ctx)


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

    return templates.TemplateResponse("partials/_send_progress_inner.html", {
        "request": request,
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
