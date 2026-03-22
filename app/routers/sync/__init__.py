from fastapi import APIRouter

from .session import router as session_router
from .contacts import router as contacts_router
from .exchange import router as exchange_router

router = APIRouter()
router.include_router(session_router)
router.include_router(contacts_router)
router.include_router(exchange_router)
