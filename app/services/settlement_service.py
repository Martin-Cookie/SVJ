"""Vyúčtování — generování, detail, správa stavu."""

from datetime import datetime
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    Payment, PaymentDirection, PaymentMatchStatus,
    Prescription, PrescriptionItem, PrescriptionYear,
    Settlement, SettlementItem, SettlementStatus,
    UnitBalance,
)
from app.models.owner import OwnerUnit


def generate_settlements(db: Session, year: int) -> dict:
    """Vygeneruje vyúčtování pro všechny jednotky s předpisem v daném roce.

    Pro každou jednotku:
    - Celkový předpis = monthly_total × 12
    - Celkem zaplaceno = suma napárovaných příjmových plateb
    - Počáteční zůstatek (UnitBalance)
    - result_amount = předpis + zůstatek - zaplaceno
      (kladné = nedoplatek, záporné = přeplatek)
    - SettlementItems z PrescriptionItems (rozpad po kategoriích)

    Returns: {"created": int, "updated": int, "total": int}
    """
    py = db.query(PrescriptionYear).filter_by(year=year).first()
    if not py:
        return {"created": 0, "updated": 0, "total": 0}

    # Předpisy pro rok
    prescriptions = db.query(Prescription).filter_by(prescription_year_id=py.id).all()

    # Platby příjmové napárované per unit_id
    matched_statuses = [PaymentMatchStatus.AUTO_MATCHED, PaymentMatchStatus.MANUAL]
    paid_rows = (
        db.query(
            Payment.unit_id,
            func.sum(Payment.amount).label("total"),
        )
        .filter(
            Payment.direction == PaymentDirection.INCOME,
            Payment.match_status.in_(matched_statuses),
            Payment.unit_id.isnot(None),
            func.extract("year", Payment.date) == year,
        )
        .group_by(Payment.unit_id)
        .all()
    )
    paid_map = {row.unit_id: row.total or 0 for row in paid_rows}

    # Zůstatky
    balances = db.query(UnitBalance).filter_by(year=year).all()
    balance_map = {b.unit_id: b.opening_amount for b in balances}

    # Aktuální vlastník per unit
    owner_units = (
        db.query(OwnerUnit)
        .filter(OwnerUnit.valid_to.is_(None))
        .all()
    )
    owner_by_unit = {}
    for ou in owner_units:
        if ou.unit_id not in owner_by_unit:
            owner_by_unit[ou.unit_id] = ou.owner_id

    # Existující settlements pro tento rok — pro update
    existing = db.query(Settlement).filter_by(year=year).all()
    existing_map = {s.unit_id: s for s in existing}

    created = 0
    updated = 0

    for presc in prescriptions:
        if not presc.unit_id:
            continue

        unit_id = presc.unit_id
        monthly = presc.monthly_total or 0
        annual_prescription = monthly * 12
        total_paid = paid_map.get(unit_id, 0)
        opening = balance_map.get(unit_id, 0)

        # result_amount: kladné = nedoplatek, záporné = přeplatek
        result_amount = annual_prescription + opening - total_paid

        owner_id = owner_by_unit.get(unit_id)

        # Upsert settlement
        settlement = existing_map.get(unit_id)
        if settlement:
            settlement.owner_id = owner_id
            settlement.result_amount = round(result_amount, 2)
            settlement.variable_symbol = presc.variable_symbol
            settlement.status = SettlementStatus.GENERATED
            settlement.updated_at = datetime.utcnow()
            # Smazat staré items
            for item in settlement.items[:]:
                db.delete(item)
            updated += 1
        else:
            settlement = Settlement(
                year=year,
                unit_id=unit_id,
                owner_id=owner_id,
                result_amount=round(result_amount, 2),
                variable_symbol=presc.variable_symbol,
                status=SettlementStatus.GENERATED,
            )
            db.add(settlement)
            created += 1

        db.flush()  # aby settlement.id byl k dispozici

        # SettlementItems z PrescriptionItems
        items = (
            db.query(PrescriptionItem)
            .filter_by(prescription_id=presc.id)
            .order_by(PrescriptionItem.order)
            .all()
        )
        for pi in items:
            item_annual = (pi.amount or 0) * 12
            # Poměrné rozúčtování zaplacené částky podle podílu položky na celku
            if monthly > 0:
                ratio = (pi.amount or 0) / monthly
            else:
                ratio = 0
            item_paid = round(total_paid * ratio, 2)
            item_result = round(item_annual - item_paid, 2)

            si = SettlementItem(
                settlement_id=settlement.id,
                name=pi.name,
                distribution_key=pi.category.value if pi.category else "",
                cost_building=round(item_annual, 2),
                cost_unit=round(pi.amount or 0, 2),
                paid=item_paid,
                result=item_result,
            )
            db.add(si)

    db.commit()
    total = db.query(Settlement).filter_by(year=year).count()
    return {"created": created, "updated": updated, "total": total}


def get_settlement_detail(db: Session, settlement_id: int) -> Optional[dict]:
    """Detail jednoho vyúčtování s položkami + platby."""
    settlement = db.query(Settlement).get(settlement_id)
    if not settlement:
        return None

    # Platby napárované na tuto jednotku v daném roce
    matched_statuses = [PaymentMatchStatus.AUTO_MATCHED, PaymentMatchStatus.MANUAL]
    payments = (
        db.query(Payment)
        .filter(
            Payment.unit_id == settlement.unit_id,
            Payment.direction == PaymentDirection.INCOME,
            Payment.match_status.in_(matched_statuses),
            func.extract("year", Payment.date) == settlement.year,
        )
        .order_by(Payment.date)
        .all()
    )

    # Předpis
    py = db.query(PrescriptionYear).filter_by(year=settlement.year).first()
    prescription = None
    if py:
        prescription = db.query(Prescription).filter_by(
            prescription_year_id=py.id, unit_id=settlement.unit_id,
        ).first()

    monthly = prescription.monthly_total if prescription else 0
    annual = monthly * 12

    # Zůstatek
    balance = db.query(UnitBalance).filter_by(
        unit_id=settlement.unit_id, year=settlement.year,
    ).first()
    opening = balance.opening_amount if balance else 0

    total_paid = sum(p.amount for p in payments)

    return {
        "settlement": settlement,
        "settlement_items": settlement.items,
        "payments": payments,
        "prescription": prescription,
        "monthly": monthly,
        "annual": annual,
        "opening": opening,
        "total_paid": total_paid,
    }


def update_settlement_status(db: Session, settlement_id: int, new_status: str) -> Optional[Settlement]:
    """Změna stavu vyúčtování."""
    settlement = db.query(Settlement).get(settlement_id)
    if not settlement:
        return None

    try:
        settlement.status = SettlementStatus(new_status)
    except ValueError:
        return None

    settlement.updated_at = datetime.utcnow()
    db.commit()
    return settlement
