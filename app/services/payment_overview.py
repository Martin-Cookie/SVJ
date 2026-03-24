"""Výpočty pro přehled plateb — matice, dlužníci, detail jednotky."""

from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    OwnerUnit, Payment, PaymentAllocation, PaymentDirection, PaymentMatchStatus,
    Prescription, PrescriptionYear,
    Space, SpaceTenant, Tenant,
    Unit, UnitBalance,
)


@dataclass
class PaymentWithAlloc:
    """Wrapper kolem Payment s alokovanou částkou (místo dynamického atributu na ORM objektu)."""
    _payment: object
    alloc_amount: float

    def __getattr__(self, name):
        return getattr(self._payment, name)


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

    # Platby příjmové, napárované, seskupené per unit_id + měsíc (přes alokace)
    payments = (
        db.query(
            PaymentAllocation.unit_id,
            func.extract("month", Payment.date).label("month"),
            func.sum(PaymentAllocation.amount).label("total"),
        )
        .join(Payment)
        .filter(
            Payment.direction == PaymentDirection.INCOME,
            Payment.match_status.in_([PaymentMatchStatus.AUTO_MATCHED, PaymentMatchStatus.MANUAL]),
            func.extract("year", Payment.date) == year,
        )
        .group_by(PaymentAllocation.unit_id, func.extract("month", Payment.date))
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

    # Aktuální vlastníci per unit (všichni spoluvlastníci)
    owner_units = (
        db.query(OwnerUnit)
        .filter(OwnerUnit.valid_to.is_(None))
        .all()
    )
    owners_by_unit = {}
    for ou in owner_units:
        owners_by_unit.setdefault(ou.unit_id, []).append(ou.owner)

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
        owners = owners_by_unit.get(unit.id, [])

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
        expected = round(monthly * len(months_with_data) + opening, 2)
        debt = round(max(0, expected - row_paid), 2)

        rows.append({
            "unit": unit,
            "prescription": presc,
            "owner": owners[0] if owners else None,
            "owners": owners,
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

    # Všechny platby pro tuto jednotku v daném roce (přes alokace)
    alloc_rows = (
        db.query(PaymentAllocation, Payment)
        .join(Payment)
        .filter(
            PaymentAllocation.unit_id == unit_id,
            Payment.direction == PaymentDirection.INCOME,
            Payment.match_status.in_([PaymentMatchStatus.AUTO_MATCHED, PaymentMatchStatus.MANUAL]),
            func.extract("year", Payment.date) == year,
        )
        .order_by(Payment.date)
        .all()
    )
    payments = []
    for alloc, payment in alloc_rows:
        payments.append(PaymentWithAlloc(payment, alloc.amount))

    # Měsíční souhrn
    months = {}
    for m in range(1, 13):
        m_payments = [p for p in payments if p.date.month == m]
        paid = sum(p.alloc_amount for p in m_payments)
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

    total_paid = sum(p.alloc_amount for p in payments)
    balance = db.query(UnitBalance).filter_by(unit_id=unit_id, year=year).first()
    opening = balance.opening_amount if balance else 0

    # Aktuální vlastníci (všichni spoluvlastníci)
    unit_owners = (
        db.query(OwnerUnit)
        .filter(OwnerUnit.unit_id == unit_id, OwnerUnit.valid_to.is_(None))
        .all()
    )
    owners = [ou.owner for ou in unit_owners]

    return {
        "unit": unit,
        "prescription": presc,
        "monthly": monthly,
        "opening": opening,
        "months": months,
        "payments": payments,
        "total_paid": total_paid,
        "owner": owners[0] if owners else None,
        "owners": owners,
    }


def compute_space_debtor_list(db: Session, year: int) -> tuple:
    """Prostory kde total_paid < expected (dlužníci)."""
    matrix = compute_space_payment_matrix(db, year)
    debtors = [r for r in matrix["rows"] if r["debt"] > 0]
    debtors.sort(key=lambda x: x["debt"], reverse=True)
    return debtors, matrix["months_with_data"]


def compute_space_payment_matrix(db: Session, year: int) -> dict:
    """Matice plateb prostorů: prostory x měsíce.

    Stejná struktura jako compute_payment_matrix, ale pro prostory.
    """
    py = db.query(PrescriptionYear).filter_by(year=year).first()
    if not py:
        return {"rows": [], "total_prescribed": 0, "total_paid": 0,
                "months_with_data": set()}

    # Předpisy indexované dle space_id
    prescriptions = db.query(Prescription).filter(
        Prescription.prescription_year_id == py.id,
        Prescription.space_id.isnot(None),
    ).all()
    presc_by_space = {}
    for p in prescriptions:
        presc_by_space[p.space_id] = p

    if not presc_by_space:
        return {"rows": [], "total_prescribed": 0, "total_paid": 0,
                "months_with_data": set()}

    # Platby přes alokace (space_id)
    from sqlalchemy.orm import joinedload as jl
    payments = (
        db.query(
            PaymentAllocation.space_id,
            func.extract("month", Payment.date).label("month"),
            func.sum(PaymentAllocation.amount).label("total"),
        )
        .join(Payment)
        .filter(
            Payment.direction == PaymentDirection.INCOME,
            Payment.match_status.in_([PaymentMatchStatus.AUTO_MATCHED, PaymentMatchStatus.MANUAL]),
            func.extract("year", Payment.date) == year,
            PaymentAllocation.space_id.isnot(None),
        )
        .group_by(PaymentAllocation.space_id, func.extract("month", Payment.date))
        .all()
    )

    paid_map = defaultdict(lambda: defaultdict(float))
    months_with_data = set()
    for space_id, month, total in payments:
        m = int(month)
        paid_map[space_id][m] += total or 0
        months_with_data.add(m)

    # Use unit months_with_data if space has none (share global month coverage)
    if not months_with_data:
        unit_payments = (
            db.query(func.distinct(func.extract("month", Payment.date)))
            .filter(
                Payment.direction == PaymentDirection.INCOME,
                Payment.match_status.in_([PaymentMatchStatus.AUTO_MATCHED, PaymentMatchStatus.MANUAL]),
                func.extract("year", Payment.date) == year,
            ).all()
        )
        months_with_data = {int(r[0]) for r in unit_payments}

    # Zůstatky prostorů
    balances = db.query(UnitBalance).filter(
        UnitBalance.year == year, UnitBalance.space_id.isnot(None)
    ).all()
    balance_map = {b.space_id: b.opening_amount for b in balances}

    # Prostory
    spaces = db.query(Space).order_by(Space.space_number).all()

    # Nájemci per space (eager load tenant + owner pro display_name)
    from sqlalchemy.orm import joinedload
    active_tenants = (
        db.query(SpaceTenant)
        .options(joinedload(SpaceTenant.tenant).joinedload(Tenant.owner))
        .filter(SpaceTenant.is_active == True)  # noqa: E712
        .all()
    )
    tenant_by_space = {st.space_id: st for st in active_tenants}

    rows = []
    total_prescribed = 0.0
    total_paid_all = 0.0

    for space in spaces:
        presc = presc_by_space.get(space.id)
        if not presc:
            continue

        monthly = presc.monthly_total or 0
        total_prescribed += monthly
        opening = balance_map.get(space.id, 0)
        st_rel = tenant_by_space.get(space.id)

        months = {}
        row_paid = 0.0
        for m in range(1, 13):
            paid = paid_map[space.id].get(m, 0)
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
        expected = round(monthly * len(months_with_data) + opening, 2)
        debt = round(max(0, expected - row_paid), 2)

        rows.append({
            "space": space,
            "prescription": presc,
            "tenant_rel": st_rel,
            "monthly": monthly,
            "opening": opening,
            "months": months,
            "total_paid": row_paid,
            "expected": expected,
            "debt": debt,
            "entity_type": "space",
        })

    return {
        "rows": rows,
        "total_prescribed": total_prescribed,
        "total_paid": total_paid_all,
        "months_with_data": months_with_data,
    }


def compute_space_payment_detail(db: Session, space_id: int, year: int):
    """Platební historie jednoho prostoru."""
    from sqlalchemy.orm import joinedload as jl
    space = db.query(Space).get(space_id)
    if not space:
        return None

    py = db.query(PrescriptionYear).filter_by(year=year).first()
    presc = None
    if py:
        presc = db.query(Prescription).filter_by(
            prescription_year_id=py.id, space_id=space_id
        ).first()

    monthly = presc.monthly_total if presc else 0

    # Platby přes alokace
    alloc_rows = (
        db.query(PaymentAllocation, Payment)
        .join(Payment)
        .filter(
            PaymentAllocation.space_id == space_id,
            Payment.direction == PaymentDirection.INCOME,
            Payment.match_status.in_([PaymentMatchStatus.AUTO_MATCHED, PaymentMatchStatus.MANUAL]),
            func.extract("year", Payment.date) == year,
        )
        .order_by(Payment.date)
        .all()
    )
    payments = [PaymentWithAlloc(payment, alloc.amount) for alloc, payment in alloc_rows]

    months = {}
    for m in range(1, 13):
        m_payments = [p for p in payments if p.date.month == m]
        paid = sum(p.alloc_amount for p in m_payments)
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

    total_paid = sum(p.alloc_amount for p in payments)
    balance = db.query(UnitBalance).filter_by(space_id=space_id, year=year).first()
    opening = balance.opening_amount if balance else 0

    # Active tenant
    st_rel = db.query(SpaceTenant).filter_by(
        space_id=space_id, is_active=True
    ).first()

    return {
        "space": space,
        "prescription": presc,
        "monthly": monthly,
        "opening": opening,
        "months": months,
        "payments": payments,
        "total_paid": total_paid,
        "tenant_rel": st_rel,
    }
