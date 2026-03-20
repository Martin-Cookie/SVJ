"""Služba pro párování plateb na jednotky přes variabilní symboly.

Logika:
1. VS z platby → lookup v VariableSymbolMapping → unit_id (AUTO_MATCHED)
2. Fallback: jméno odesílatele + částka → SUGGESTED
3. Nenapárované: match_status=UNMATCHED
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.models import (
    VariableSymbolMapping, Prescription, Payment,
    PaymentDirection, PaymentMatchStatus, Unit, OwnerUnit,
)
from app.utils import strip_diacritics

logger = logging.getLogger(__name__)


def _find_name_matches(sender_words: set, name_lookup: list[dict]) -> list[dict]:
    """Najdi všechny shody jména odesílatele proti lookup tabulce.

    Shoda = alespoň jedno slovo delší než 3 znaky se shoduje.
    Vrací seznam všech matchů seřazený podle skóre (víc shodných slov = lepší).
    """
    significant_sender = {w for w in sender_words if len(w) > 3}
    if not significant_sender:
        return []

    matches = []
    for entry in name_lookup:
        significant_entry = {w for w in entry["words"] if len(w) > 3}
        if not significant_entry:
            continue

        common = significant_sender & significant_entry
        if not common:
            continue

        matches.append((len(common), entry))

    # Seřadit podle skóre (nejvíc shodných slov první)
    matches.sort(key=lambda x: x[0], reverse=True)
    return [entry for _, entry in matches]


def _check_amount_match(amount: float, monthly_total: Optional[float]) -> bool:
    """True pokud amount je násobek monthly_total (1-12×) s tolerancí ±1 Kč."""
    if not monthly_total or monthly_total <= 0:
        return False

    for n in range(1, 13):
        expected = monthly_total * n
        if abs(amount - expected) <= 1.0:
            return True
    return False


def match_payments(db: Session, statement_id: int, year: int) -> dict:
    """Napáruj platby z výpisu na jednotky přes VS + fallback jméno+částka.

    Args:
        db: databázová session
        statement_id: ID bankovního výpisu
        year: rok pro vyhledání předpisů

    Returns:
        dict s počty: matched, suggested, unmatched, total
    """
    # Načti VS mapování (aktivní)
    vs_map = {}
    for m in db.query(VariableSymbolMapping).filter_by(is_active=True).all():
        vs_map[m.variable_symbol] = m.unit_id

    # Načti předpisy pro rok
    prescriptions_by_vs = {}
    prescriptions_by_unit = {}
    all_prescriptions = []
    from app.models import PrescriptionYear
    py = db.query(PrescriptionYear).filter_by(year=year).first()
    if py:
        for p in db.query(Prescription).filter_by(prescription_year_id=py.id).all():
            if p.variable_symbol:
                prescriptions_by_vs[p.variable_symbol] = p
            if p.unit_id:
                prescriptions_by_unit[p.unit_id] = p
            all_prescriptions.append(p)

    # Načti aktuální vlastníky jednotek
    owner_by_unit = {}
    active_owner_units = db.query(OwnerUnit).filter(OwnerUnit.valid_to.is_(None)).all()
    for ou in active_owner_units:
        owner_by_unit[ou.unit_id] = ou.owner_id

    # 1. fáze: VS párování
    payments = (
        db.query(Payment)
        .filter_by(statement_id=statement_id, match_status=PaymentMatchStatus.UNMATCHED)
        .filter(Payment.direction == PaymentDirection.INCOME)
        .all()
    )

    matched = 0
    suggested = 0
    unmatched = 0

    for payment in payments:
        if not payment.vs:
            continue

        unit_id = vs_map.get(payment.vs)
        if not unit_id:
            continue

        payment.unit_id = unit_id
        payment.owner_id = owner_by_unit.get(unit_id)
        payment.match_status = PaymentMatchStatus.AUTO_MATCHED

        prescription = prescriptions_by_vs.get(payment.vs)
        if prescription:
            payment.prescription_id = prescription.id

        payment.assigned_month = payment.date.month if payment.date else None
        matched += 1

    db.flush()

    # 2. fáze: Fallback — jméno odesílatele + částka
    still_unmatched = [
        p for p in payments
        if p.match_status == PaymentMatchStatus.UNMATCHED and p.counter_account_name
    ]

    if still_unmatched:
        # Připravit name lookup z předpisů + vlastníků
        name_lookup = []
        seen_keys = set()  # deduplikace

        for presc in all_prescriptions:
            if presc.owner_name and presc.unit_id:
                norm = strip_diacritics(presc.owner_name)
                key = (norm, presc.unit_id)
                if key not in seen_keys:
                    seen_keys.add(key)
                    name_lookup.append({
                        "name_norm": norm,
                        "words": set(norm.split()),
                        "unit_id": presc.unit_id,
                        "monthly": presc.monthly_total,
                    })

        from app.models import Owner
        for ou in active_owner_units:
            owner = db.query(Owner).get(ou.owner_id)
            if not owner or not owner.name_normalized:
                continue
            key = (owner.name_normalized, ou.unit_id)
            if key not in seen_keys:
                seen_keys.add(key)
                presc = prescriptions_by_unit.get(ou.unit_id)
                name_lookup.append({
                    "name_norm": owner.name_normalized,
                    "words": set(owner.name_normalized.split()),
                    "unit_id": ou.unit_id,
                    "monthly": presc.monthly_total if presc else None,
                })

        for payment in still_unmatched:
            sender_norm = strip_diacritics(payment.counter_account_name)
            sender_words = set(sender_norm.split())

            candidates = _find_name_matches(sender_words, name_lookup)
            if not candidates:
                continue

            # Najít kandidáta kde částka odpovídá předpisu
            best = None
            for c in candidates:
                if _check_amount_match(payment.amount, c["monthly"]):
                    best = c
                    break

            # Pokud jen 1 jmenný kandidát a částka nesedí, přesto navrhnout
            if not best and len(candidates) == 1:
                best = candidates[0]

            if best:
                payment.unit_id = best["unit_id"]
                payment.owner_id = owner_by_unit.get(best["unit_id"])
                payment.match_status = PaymentMatchStatus.SUGGESTED
                payment.assigned_month = payment.date.month if payment.date else None

                presc = prescriptions_by_unit.get(best["unit_id"])
                if presc:
                    payment.prescription_id = presc.id

                suggested += 1

        db.flush()

    # Spočítat zbylé unmatched
    unmatched = sum(
        1 for p in payments if p.match_status == PaymentMatchStatus.UNMATCHED
    )

    logger.info(
        "Matching statement %d: %d matched, %d suggested, %d unmatched",
        statement_id, matched, suggested, unmatched,
    )

    return {
        "matched": matched,
        "suggested": suggested,
        "unmatched": unmatched,
        "total": len(payments),
    }
