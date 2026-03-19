from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from sqlalchemy import func

from app.models import PrescriptionYear, Prescription, VariableSymbolMapping, BankStatement, Payment, PaymentMatchStatus, PaymentDirection, Settlement, SettlementStatus
from ._helpers import templates

from .prescriptions import router as prescriptions_router
from .symbols import router as symbols_router
from .balances import router as balances_router
from .statements import router as statements_router
from .overview import router as overview_router
from .settlement import router as settlement_router

router = APIRouter()


@router.get("")
async def platby_index(request: Request, db: Session = Depends(get_db)):
    """Rozcestník modulu plateb."""
    years = db.query(PrescriptionYear).order_by(PrescriptionYear.year.desc()).all()
    vs_count = db.query(VariableSymbolMapping).filter(VariableSymbolMapping.is_active.is_(True)).count()
    total_prescriptions = db.query(Prescription).count()

    # Statistiky výpisů
    statement_count = db.query(BankStatement).count()
    total_payments = db.query(Payment).count()
    unmatched_payments = db.query(Payment).filter_by(match_status=PaymentMatchStatus.UNMATCHED).count()

    # Statistiky pro matici plateb — napárované příjmy
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

    # Dlužníci — quick count z nejnovějšího roku
    debtor_count = 0
    if years:
        from app.services.payment_overview import compute_debtor_list
        debtors, _ = compute_debtor_list(db, years[0].year)
        debtor_count = len(debtors)

    # Vyúčtování — statistiky
    settlement_count = db.query(Settlement).count()
    settlement_generated = db.query(Settlement).filter_by(status=SettlementStatus.GENERATED).count()
    settlement_year = years[0].year if years else 0

    back_url = request.query_params.get("back", "")

    return templates.TemplateResponse("payments/index.html", {
        "request": request,
        "active_nav": "platby",
        "years": years,
        "vs_count": vs_count,
        "total_prescriptions": total_prescriptions,
        "statement_count": statement_count,
        "total_payments": total_payments,
        "unmatched_payments": unmatched_payments,
        "matched_income": matched_income,
        "total_income": total_income,
        "debtor_count": debtor_count,
        "settlement_count": settlement_count,
        "settlement_generated": settlement_generated,
        "settlement_year": settlement_year,
        "back_url": back_url,
    })


router.include_router(prescriptions_router)
router.include_router(symbols_router)
router.include_router(balances_router)
router.include_router(statements_router)
router.include_router(overview_router)
router.include_router(settlement_router)
