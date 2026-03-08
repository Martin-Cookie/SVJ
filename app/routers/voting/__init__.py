from fastapi import APIRouter

from .session import router as session_router
from .ballots import router as ballots_router
from .import_votes import router as import_router

router = APIRouter()
router.include_router(session_router)
router.include_router(ballots_router)
router.include_router(import_router)
