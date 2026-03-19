from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import PrescriptionYear, Prescription, VariableSymbolMapping, BankStatement, Payment, PaymentMatchStatus
from ._helpers import templates

from .prescriptions import router as prescriptions_router
from .symbols import router as symbols_router
from .balances import router as balances_router
from .statements import router as statements_router

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
        "back_url": back_url,
    })


router.include_router(prescriptions_router)
router.include_router(symbols_router)
router.include_router(balances_router)
router.include_router(statements_router)
