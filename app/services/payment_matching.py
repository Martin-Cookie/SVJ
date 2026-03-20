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
    VariableSymbolMapping, Prescription, Payment, PaymentAllocation,
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


def _check_amount_match(amount: float, monthly_total: Optional[float], tolerance: float = 1.0) -> bool:
    """True pokud amount je násobek monthly_total (1-12×) s tolerancí ±tolerance Kč."""
    if not monthly_total or monthly_total <= 0:
        return False

    for n in range(1, 13):
        expected = monthly_total * n
        if abs(amount - expected) <= tolerance:
            return True
    return False


def _find_multi_unit_match(amount: float, candidates: list[dict],
                           tolerance: float = 1.0) -> Optional[list[dict]]:
    """Zkusit najít kombinaci jednotek jednoho vlastníka kde součet předpisů = amount.

    Seskupí kandidáty podle owner_id, pro každého vlastníka s 2+ jednotkami
    zkouší kombinace (2-4) kde sum(monthly * n) = amount ± tolerance.
    """
    from itertools import combinations

    # Seskupit podle owner_id
    by_owner: dict[int, list[dict]] = {}
    for c in candidates:
        oid = c.get("owner_id")
        if not oid or not c.get("monthly") or c["monthly"] <= 0:
            continue
        by_owner.setdefault(oid, []).append(c)

    for owner_id, entries in by_owner.items():
        if len(entries) < 2:
            continue

        # Zkusit kombinace 2-4 jednotek
        for size in range(2, min(len(entries) + 1, 5)):
            for combo in combinations(entries, size):
                combo_sum = sum(e["monthly"] for e in combo)
                # Zkusit n-násobek (1-12 měsíců)
                for n in range(1, 13):
                    expected = combo_sum * n
                    if abs(amount - expected) <= tolerance:
                        return list(combo)
    return None


def _create_allocation(db: Session, payment: Payment, unit_id: int,
                       owner_id: Optional[int], prescription_id: Optional[int],
                       amount: float) -> None:
    """Vytvořit PaymentAllocation záznam (dual-write)."""
    db.add(PaymentAllocation(
        payment_id=payment.id,
        unit_id=unit_id,
        owner_id=owner_id,
        prescription_id=prescription_id,
        amount=amount,
    ))


def match_payments(db: Session, statement_id: int, year: int,
                   tolerance: float = 1.0) -> dict:
    """Napáruj platby z výpisu na jednotky přes VS + fallback jméno+částka.

    Args:
        db: databázová session
        statement_id: ID bankovního výpisu
        year: rok pro vyhledání předpisů
        tolerance: tolerance shody částky v Kč (výchozí ±1)

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

        # Dual-write: vytvořit alokaci
        _create_allocation(
            db, payment, unit_id, payment.owner_id,
            payment.prescription_id, payment.amount,
        )
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
                        "owner_id": owner_by_unit.get(presc.unit_id),
                        "monthly": presc.monthly_total,
                        "prescription_id": presc.id,
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
                    "owner_id": ou.owner_id,
                    "monthly": presc.monthly_total if presc else None,
                    "prescription_id": presc.id if presc else None,
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
                if _check_amount_match(payment.amount, c["monthly"], tolerance):
                    best = c
                    break

            if best:
                # Single-unit match
                payment.unit_id = best["unit_id"]
                payment.owner_id = owner_by_unit.get(best["unit_id"])
                payment.match_status = PaymentMatchStatus.SUGGESTED
                payment.assigned_month = payment.date.month if payment.date else None

                presc = prescriptions_by_unit.get(best["unit_id"])
                if presc:
                    payment.prescription_id = presc.id

                _create_allocation(
                    db, payment, best["unit_id"], payment.owner_id,
                    payment.prescription_id, payment.amount,
                )
                suggested += 1
            else:
                # Zkusit multi-unit match (součet předpisů více jednotek)
                multi = _find_multi_unit_match(payment.amount, candidates, tolerance)
                if multi:
                    # Multi-unit → Payment.unit_id = None, N alokací
                    payment.unit_id = None
                    payment.owner_id = multi[0].get("owner_id")
                    payment.match_status = PaymentMatchStatus.SUGGESTED
                    payment.assigned_month = payment.date.month if payment.date else None

                    for entry in multi:
                        _create_allocation(
                            db, payment, entry["unit_id"],
                            entry.get("owner_id"),
                            entry.get("prescription_id"),
                            entry["monthly"],
                        )
                    suggested += 1
                elif len(candidates) == 1:
                    # Pokud jen 1 jmenný kandidát a částka nesedí, přesto navrhnout
                    best = candidates[0]
                    payment.unit_id = best["unit_id"]
                    payment.owner_id = owner_by_unit.get(best["unit_id"])
                    payment.match_status = PaymentMatchStatus.SUGGESTED
                    payment.assigned_month = payment.date.month if payment.date else None

                    presc = prescriptions_by_unit.get(best["unit_id"])
                    if presc:
                        payment.prescription_id = presc.id

                    _create_allocation(
                        db, payment, best["unit_id"], payment.owner_id,
                        payment.prescription_id, payment.amount,
                    )
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
