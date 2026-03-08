from fastapi import APIRouter

from .session import router as session_router
from .processing import router as processing_router
from .matching import router as matching_router
from .sending import router as sending_router
from ._helpers import recover_stuck_sending_sessions  # noqa: F401 — used by main.py

router = APIRouter()
router.include_router(session_router)
router.include_router(processing_router)
router.include_router(matching_router)
router.include_router(sending_router)
