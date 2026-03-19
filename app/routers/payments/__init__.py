from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import PrescriptionYear, Prescription, VariableSymbolMapping
from ._helpers import templates

from .prescriptions import router as prescriptions_router
from .symbols import router as symbols_router
from .balances import router as balances_router

router = APIRouter()


@router.get("")
async def platby_index(request: Request, db: Session = Depends(get_db)):
    """Rozcestník modulu plateb."""
    years = db.query(PrescriptionYear).order_by(PrescriptionYear.year.desc()).all()
    vs_count = db.query(VariableSymbolMapping).filter(VariableSymbolMapping.is_active.is_(True)).count()
    total_prescriptions = db.query(Prescription).count()

    back_url = request.query_params.get("back", "")

    return templates.TemplateResponse("payments/index.html", {
        "request": request,
        "active_nav": "platby",
        "years": years,
        "vs_count": vs_count,
        "total_prescriptions": total_prescriptions,
        "back_url": back_url,
    })


router.include_router(prescriptions_router)
router.include_router(symbols_router)
router.include_router(balances_router)
