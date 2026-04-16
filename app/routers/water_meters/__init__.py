from fastapi import APIRouter

from .overview import router as overview_router
from .import_readings import router as import_router
from .sending import router as sending_router

router = APIRouter()
router.include_router(import_router)
router.include_router(sending_router)
router.include_router(overview_router)
