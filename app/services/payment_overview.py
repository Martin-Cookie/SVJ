"""Výpočty pro přehled plateb — matice, dlužníci, detail jednotky."""

from collections import defaultdict

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    Payment, PaymentDirection, PaymentMatchStatus,
    Prescription, PrescriptionYear,
    Unit, UnitBalance,
)
from app.models.owner import OwnerUnit


def compute_payment_matrix(db: Session, year: int, section: str = "", space_type: str = "") -> dict:
    """Matice plateb: jednotky x měsíce.

    Returns dict:
        units: list[dict] — řádky matice
        total_prescribed: float — celkový měsíční předpis
        total_paid: float — celkem zaplaceno (příjmy)
        months_with_data: set — měsíce s alespoň jednou platbou
        space_types: list[str] — unikátní typy prostorů
    """
    # Najdi PrescriptionYear
    py = db.query(PrescriptionYear).filter_by(year=year).first()
    if not py:
        return {"units": [], "total_prescribed": 0, "total_paid": 0,
                "months_with_data": set(), "space_types": []}

    # Předpisy indexované dle unit_id
    prescriptions = db.query(Prescription).filter_by(prescription_year_id=py.id).all()
    presc_by_unit = {}
    for p in prescriptions:
        if p.unit_id:
            presc_by_unit[p.unit_id] = p

    # Platby příjmové, napárované, seskupené per unit_id + měsíc
    matched_statuses = [PaymentMatchStatus.AUTO_MATCHED, PaymentMatchStatus.MANUAL]
    payments = (
        db.query(
            Payment.unit_id,
            func.extract("month", Payment.date).label("month"),
            func.sum(Payment.amount).label("total"),
        )
        .filter(
            Payment.direction == PaymentDirection.INCOME,
            Payment.match_status.in_(matched_statuses),
            Payment.unit_id.isnot(None),
            func.extract("year", Payment.date) == year,
        )
        .group_by(Payment.unit_id, func.extract("month", Payment.date))
        .all()
    )

    paid_map = defaultdict(lambda: defaultdict(float))  # unit_id -> month -> amount
    months_with_data = set()
    for unit_id, month, total in payments:
        m = int(month)
        paid_map[unit_id][m] += total or 0
        months_with_data.add(m)

    # Zůstatky
    balances = db.query(UnitBalance).filter_by(year=year).all()
    balance_map = {b.unit_id: b.opening_amount for b in balances}

    # Jednotky s aktivními vlastníky
    units = db.query(Unit).order_by(Unit.unit_number).all()

    # Aktuální vlastník per unit
    owner_units = (
        db.query(OwnerUnit)
        .filter(OwnerUnit.valid_to.is_(None))
        .all()
    )
    owner_by_unit = {}
    for ou in owner_units:
        if ou.unit_id not in owner_by_unit:
            owner_by_unit[ou.unit_id] = ou.owner

    # Unikátní typy prostorů z předpisů
    space_types_set = set()
    for p in prescriptions:
        if p.space_type:
            space_types_set.add(p.space_type)
    space_types = sorted(space_types_set)

    rows = []
    total_prescribed = 0.0
    total_paid_all = 0.0

    for unit in units:
        presc = presc_by_unit.get(unit.id)
        if not presc:
            continue  # Jednotka bez předpisu — nezobrazovat

        # Filtr
        if section and (presc.section or "") != section:
            continue
        if space_type and (presc.space_type or "") != space_type:
            continue

        monthly = presc.monthly_total or 0
        total_prescribed += monthly
        opening = balance_map.get(unit.id, 0)
        owner = owner_by_unit.get(unit.id)

        months = {}
        row_paid = 0.0
        for m in range(1, 13):
            paid = paid_map[unit.id].get(m, 0)
            row_paid += paid
            if m in months_with_data:
                if paid >= monthly and monthly > 0:
                    status = "paid"
                elif paid > 0:
                    status = "partial"
                else:
                    status = "unpaid"
            else:
                status = "no_data"
            months[m] = {"paid": paid, "status": status}

        total_paid_all += row_paid
        expected = monthly * len(months_with_data) + opening
        debt = max(0, expected - row_paid)

        rows.append({
            "unit": unit,
            "prescription": presc,
            "owner": owner,
            "monthly": monthly,
            "opening": opening,
            "months": months,
            "total_paid": row_paid,
            "expected": expected,
            "debt": debt,
        })

    return {
        "units": rows,
        "total_prescribed": total_prescribed,
        "total_paid": total_paid_all,
        "months_with_data": months_with_data,
        "space_types": space_types,
    }


def compute_debtor_list(db: Session, year: int) -> list:
    """Jednotky kde total_paid < expected (dlužníci)."""
    matrix = compute_payment_matrix(db, year)
    debtors = [r for r in matrix["units"] if r["debt"] > 0]
    debtors.sort(key=lambda x: x["debt"], reverse=True)
    return debtors, matrix["months_with_data"]


def compute_unit_payment_detail(db: Session, unit_id: int, year: int) -> dict:
    """Platební historie jedné jednotky."""
    unit = db.query(Unit).get(unit_id)
    if not unit:
        return None

    py = db.query(PrescriptionYear).filter_by(year=year).first()
    presc = None
    if py:
        presc = db.query(Prescription).filter_by(
            prescription_year_id=py.id, unit_id=unit_id
        ).first()

    monthly = presc.monthly_total if presc else 0

    # Všechny platby pro tuto jednotku v daném roce
    matched_statuses = [PaymentMatchStatus.AUTO_MATCHED, PaymentMatchStatus.MANUAL]
    payments = (
        db.query(Payment)
        .filter(
            Payment.unit_id == unit_id,
            Payment.direction == PaymentDirection.INCOME,
            Payment.match_status.in_(matched_statuses),
            func.extract("year", Payment.date) == year,
        )
        .order_by(Payment.date)
        .all()
    )

    # Měsíční souhrn
    months = {}
    for m in range(1, 13):
        m_payments = [p for p in payments if p.date.month == m]
        paid = sum(p.amount for p in m_payments)
        if m_payments:
            if paid >= monthly and monthly > 0:
                status = "paid"
            elif paid > 0:
                status = "partial"
            else:
                status = "unpaid"
        else:
            status = "no_data"
        months[m] = {"paid": paid, "status": status, "payments": m_payments}

    total_paid = sum(p.amount for p in payments)
    balance = db.query(UnitBalance).filter_by(unit_id=unit_id, year=year).first()
    opening = balance.opening_amount if balance else 0

    # Aktuální vlastník
    owner_unit = (
        db.query(OwnerUnit)
        .filter(OwnerUnit.unit_id == unit_id, OwnerUnit.valid_to.is_(None))
        .first()
    )

    return {
        "unit": unit,
        "prescription": presc,
        "monthly": monthly,
        "opening": opening,
        "months": months,
        "payments": payments,
        "total_paid": total_paid,
        "owner": owner_unit.owner if owner_unit else None,
    }
