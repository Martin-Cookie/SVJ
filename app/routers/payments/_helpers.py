"""Sdílené helper funkce pro modul plateb."""

import logging

from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.utils import setup_jinja_filters
from app.models import (
    PrescriptionYear, Prescription, VariableSymbolMapping,
    BankStatement, Payment, PaymentMatchStatus, PaymentDirection,
    Settlement, SettlementStatus,
)

logger = logging.getLogger(__name__)

templates = Jinja2Templates(directory="app/templates")
setup_jinja_filters(templates)


def compute_nav_stats(db: Session) -> dict:
    """Statistiky pro navigační karty platebního modulu.

    Vrací dict se všemi proměnnými potřebnými pro _platby_nav.html,
    identický s daty na /platby indexu.
    """
    years = db.query(PrescriptionYear).order_by(PrescriptionYear.year.desc()).all()
    vs_count = db.query(VariableSymbolMapping).filter(VariableSymbolMapping.is_active.is_(True)).count()
    total_prescriptions = db.query(Prescription).count()

    statement_count = db.query(BankStatement).count()
    total_payments = db.query(Payment).count()
    unmatched_payments = db.query(Payment).filter_by(match_status=PaymentMatchStatus.UNMATCHED).count()

    matched_statuses = [PaymentMatchStatus.AUTO_MATCHED, PaymentMatchStatus.MANUAL]
    matched_income = db.query(Payment).filter(
        Payment.direction == PaymentDirection.INCOME,
        Payment.match_status.in_(matched_statuses),
    ).count()
    total_income = db.query(
        func.coalesce(func.sum(Payment.amount), 0)
    ).filter(
        Payment.direction == PaymentDirection.INCOME,
        Payment.match_status.in_(matched_statuses),
    ).scalar() or 0

    debtor_count = 0
    if years:
        from app.services.payment_overview import compute_debtor_list
        debtors, _ = compute_debtor_list(db, years[0].year)
        debtor_count = len(debtors)

    settlement_count = db.query(Settlement).count()
    settlement_generated = db.query(Settlement).filter_by(status=SettlementStatus.GENERATED).count()

    return {
        "nav_years": years,
        "nav_total_prescriptions": total_prescriptions,
        "nav_vs_count": vs_count,
        "nav_statement_count": statement_count,
        "nav_total_payments": total_payments,
        "nav_unmatched_payments": unmatched_payments,
        "nav_matched_income": matched_income,
        "nav_total_income": total_income,
        "nav_debtor_count": debtor_count,
        "nav_settlement_count": settlement_count,
        "nav_settlement_generated": settlement_generated,
    }
