from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from .prescriptions import router as prescriptions_router
from .symbols import router as symbols_router
from .balances import router as balances_router
from .statements import router as statements_router
from .discrepancies import router as discrepancies_router
from .overview import router as overview_router
from .settlement import router as settlement_router

router = APIRouter()


@router.get("")
async def platby_index(request: Request):
    """Redirect na výchozí tab (předpisy)."""
    back = request.query_params.get("back", "")
    url = "/platby/predpisy"
    if back:
        url += f"?back={back}"
    return RedirectResponse(url, status_code=302)


router.include_router(prescriptions_router)
router.include_router(symbols_router)
router.include_router(balances_router)
router.include_router(statements_router)
router.include_router(discrepancies_router)
router.include_router(overview_router)
router.include_router(settlement_router)
