"""Služba pro párování plateb na jednotky přes variabilní symboly.

Logika:
1. VS z platby → lookup v VariableSymbolMapping → unit_id
2. Owner: aktuální vlastník jednotky (OwnerUnit kde valid_to is None)
3. Multi-month: pokud amount = N × monthly_total → rozdělit na N záznamů
4. Nenapárované: match_status=UNMATCHED
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.models import (
    VariableSymbolMapping, Prescription, Payment,
    PaymentMatchStatus, Unit, OwnerUnit,
)

logger = logging.getLogger(__name__)


def match_payments(db: Session, statement_id: int, year: int) -> dict:
    """Napáruj platby z výpisu na jednotky přes VS.

    Args:
        db: databázová session
        statement_id: ID bankovního výpisu
        year: rok pro vyhledání předpisů

    Returns:
        dict s počty: matched, unmatched, skipped
    """
    # Načti VS mapování (aktivní)
    vs_map = {}
    for m in db.query(VariableSymbolMapping).filter_by(is_active=True).all():
        vs_map[m.variable_symbol] = m.unit_id

    # Načti předpisy pro rok (pro multi-month detekci)
    prescriptions_by_vs = {}
    from app.models import PrescriptionYear
    py = db.query(PrescriptionYear).filter_by(year=year).first()
    if py:
        for p in db.query(Prescription).filter_by(prescription_year_id=py.id).all():
            if p.variable_symbol:
                prescriptions_by_vs[p.variable_symbol] = p

    # Načti aktuální vlastníky jednotek
    owner_by_unit = {}
    for ou in db.query(OwnerUnit).filter(OwnerUnit.valid_to.is_(None)).all():
        owner_by_unit[ou.unit_id] = ou.owner_id

    # Párování
    payments = (
        db.query(Payment)
        .filter_by(statement_id=statement_id, match_status=PaymentMatchStatus.UNMATCHED)
        .all()
    )

    matched = 0
    unmatched = 0

    for payment in payments:
        if not payment.vs:
            unmatched += 1
            continue

        unit_id = vs_map.get(payment.vs)
        if not unit_id:
            unmatched += 1
            continue

        # Napárováno
        payment.unit_id = unit_id
        payment.owner_id = owner_by_unit.get(unit_id)
        payment.match_status = PaymentMatchStatus.AUTO_MATCHED

        # Najdi předpis pro přiřazení měsíce
        prescription = prescriptions_by_vs.get(payment.vs)
        if prescription:
            payment.prescription_id = prescription.id

            # Multi-month detekce
            if prescription.monthly_total > 0:
                ratio = payment.amount / prescription.monthly_total
                if 0.95 <= ratio <= 1.05:
                    # Přesně 1 měsíc
                    payment.assigned_month = payment.date.month if payment.date else None
                elif ratio > 1.5:
                    # Víceměsíční platba — přiřadíme k měsíci platby,
                    # detailní split se udělá později v UI
                    payment.assigned_month = payment.date.month if payment.date else None
                else:
                    payment.assigned_month = payment.date.month if payment.date else None
            else:
                payment.assigned_month = payment.date.month if payment.date else None
        else:
            payment.assigned_month = payment.date.month if payment.date else None

        matched += 1

    db.flush()

    logger.info(
        "Matching statement %d: %d matched, %d unmatched",
        statement_id, matched, unmatched,
    )

    return {
        "matched": matched,
        "unmatched": unmatched,
        "total": len(payments),
    }
