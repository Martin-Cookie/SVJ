"""Sdílené helper funkce pro modul plateb."""

import logging

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.utils import templates
from app.models import (
    PrescriptionYear, Prescription, VariableSymbolMapping,
    BankStatement, Payment, PaymentAllocation, PaymentMatchStatus, PaymentDirection,
    Settlement, SettlementStatus,
    Unit, UnitBalance,
)

logger = logging.getLogger(__name__)

# České názvy měsíců — centralizované pro routery i šablony
MONTH_NAMES_SHORT = {
    1: "Led", 2: "Úno", 3: "Bře", 4: "Dub", 5: "Kvě", 6: "Čvn",
    7: "Čvc", 8: "Srp", 9: "Zář", 10: "Říj", 11: "Lis", 12: "Pro",
}
MONTH_NAMES_LONG = {
    1: "Leden", 2: "Únor", 3: "Březen", 4: "Duben", 5: "Květen", 6: "Červen",
    7: "Červenec", 8: "Srpen", 9: "Září", 10: "Říjen", 11: "Listopad", 12: "Prosinec",
}

def compute_nav_stats(db: Session) -> dict:
    """Statistiky pro navigační karty platebního modulu.

    Vrací dict se všemi proměnnými potřebnými pro _platby_nav.html.
    Optimalizováno: jeden kombinovaný dotaz na Payment statistiky,
    dlužníci počítáni lehkou SQL cestou (bez plné matice).
    """
    years = db.query(PrescriptionYear).order_by(PrescriptionYear.year.desc()).all()
    vs_count = db.query(VariableSymbolMapping).filter(VariableSymbolMapping.is_active.is_(True)).count()
    total_prescriptions = db.query(Prescription).count()

    statement_count = db.query(BankStatement).count()

    # Jeden kombinovaný dotaz na Payment statistiky
    payment_stats = db.query(
        func.count(Payment.id).label("total"),
        func.count(Payment.id).filter(Payment.match_status == PaymentMatchStatus.UNMATCHED).label("unmatched"),
        func.count(Payment.id).filter(
            Payment.direction == PaymentDirection.INCOME,
            Payment.match_status.in_([PaymentMatchStatus.AUTO_MATCHED, PaymentMatchStatus.MANUAL]),
        ).label("matched_income"),
        func.coalesce(func.sum(Payment.amount).filter(
            Payment.direction == PaymentDirection.INCOME,
            Payment.match_status.in_([PaymentMatchStatus.AUTO_MATCHED, PaymentMatchStatus.MANUAL]),
        ), 0).label("total_income"),
    ).first()

    # Dlužníci — lehký SQL výpočet (bez plné matice)
    debtor_count = 0
    if years:
        debtor_count = _count_debtors_fast(db, years[0].year)

    settlement_count = db.query(Settlement).count()
    settlement_generated = db.query(Settlement).filter_by(status=SettlementStatus.GENERATED).count()

    balance_count = db.query(UnitBalance).count()

    return {
        "nav_years": years,
        "nav_total_prescriptions": total_prescriptions,
        "nav_vs_count": vs_count,
        "nav_statement_count": statement_count,
        "nav_total_payments": payment_stats.total,
        "nav_unmatched_payments": payment_stats.unmatched,
        "nav_matched_income": payment_stats.matched_income,
        "nav_total_income": payment_stats.total_income,
        "nav_debtor_count": debtor_count,
        "nav_settlement_count": settlement_count,
        "nav_settlement_generated": settlement_generated,
        "nav_balance_count": balance_count,
    }


def _count_debtors_fast(db: Session, year: int) -> int:
    """Rychlý výpočet počtu dlužníků bez plné matice plateb.

    Porovnává předpis × počet měsíců s daty vs. zaplaceno per jednotka.
    """
    py = db.query(PrescriptionYear).filter_by(year=year).first()
    if not py:
        return 0

    # Předpisy indexované dle unit_id
    prescriptions = db.query(Prescription).filter_by(prescription_year_id=py.id).all()
    presc_by_unit = {}
    for p in prescriptions:
        if p.unit_id:
            presc_by_unit[p.unit_id] = p.monthly_total or 0

    if not presc_by_unit:
        return 0

    # Kolik měsíců má data (alespoň 1 platba)
    months_rows = (
        db.query(func.distinct(func.extract("month", Payment.date)))
        .filter(
            Payment.direction == PaymentDirection.INCOME,
            Payment.match_status.in_([PaymentMatchStatus.AUTO_MATCHED, PaymentMatchStatus.MANUAL]),
            Payment.unit_id.isnot(None),
            func.extract("year", Payment.date) == year,
        )
        .all()
    )
    months_count = len(months_rows)
    if months_count == 0:
        # Žádné platby → nelze určit dlužníky
        return 0

    # Zaplaceno per unit_id (přes alokace)
    paid_rows = (
        db.query(
            PaymentAllocation.unit_id,
            func.sum(PaymentAllocation.amount).label("total"),
        )
        .join(Payment)
        .filter(
            Payment.direction == PaymentDirection.INCOME,
            Payment.match_status.in_([PaymentMatchStatus.AUTO_MATCHED, PaymentMatchStatus.MANUAL]),
            func.extract("year", Payment.date) == year,
        )
        .group_by(PaymentAllocation.unit_id)
        .all()
    )
    paid_map = {row.unit_id: row.total or 0 for row in paid_rows}

    # Zůstatky
    balances = db.query(UnitBalance).filter_by(year=year).all()
    balance_map = {b.unit_id: b.opening_amount for b in balances}

    # Počítání dlužníků
    count = 0
    for unit_id, monthly in presc_by_unit.items():
        opening = balance_map.get(unit_id, 0)
        expected = round(monthly * months_count + opening, 2)
        paid = paid_map.get(unit_id, 0)
        if paid < expected:
            count += 1

    return count


def compute_debt_map(db: Session, year: int) -> dict[int, float]:
    """Vrátí mapu {unit_id: dluh_kč} pro všechny jednotky s dluhem.

    Dluh = (předpis × měsíce + opening_balance) - zaplaceno.
    Vrací jen jednotky kde dluh > 0.
    """
    py = db.query(PrescriptionYear).filter_by(year=year).first()
    if not py:
        return {}

    prescriptions = db.query(Prescription).filter_by(prescription_year_id=py.id).all()
    presc_by_unit = {}
    for p in prescriptions:
        if p.unit_id:
            presc_by_unit[p.unit_id] = p.monthly_total or 0

    if not presc_by_unit:
        return {}

    months_rows = (
        db.query(func.distinct(func.extract("month", Payment.date)))
        .filter(
            Payment.direction == PaymentDirection.INCOME,
            Payment.match_status.in_([PaymentMatchStatus.AUTO_MATCHED, PaymentMatchStatus.MANUAL]),
            Payment.unit_id.isnot(None),
            func.extract("year", Payment.date) == year,
        )
        .all()
    )
    months_count = len(months_rows)
    if months_count == 0:
        return {}

    paid_rows = (
        db.query(
            PaymentAllocation.unit_id,
            func.sum(PaymentAllocation.amount).label("total"),
        )
        .join(Payment)
        .filter(
            Payment.direction == PaymentDirection.INCOME,
            Payment.match_status.in_([PaymentMatchStatus.AUTO_MATCHED, PaymentMatchStatus.MANUAL]),
            func.extract("year", Payment.date) == year,
        )
        .group_by(PaymentAllocation.unit_id)
        .all()
    )
    paid_map = {row.unit_id: row.total or 0 for row in paid_rows}

    balances = db.query(UnitBalance).filter_by(year=year).all()
    balance_map = {b.unit_id: b.opening_amount for b in balances}

    result = {}
    for unit_id, monthly in presc_by_unit.items():
        opening = balance_map.get(unit_id, 0)
        expected = round(monthly * months_count + opening, 2)
        paid = paid_map.get(unit_id, 0)
        debt = round(expected - paid, 2)
        if debt > 0:
            result[unit_id] = debt

    return result
