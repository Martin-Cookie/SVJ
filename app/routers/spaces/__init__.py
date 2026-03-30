from fastapi import APIRouter

from .crud import router as crud_router
from .import_spaces import router as import_router

router = APIRouter()
router.include_router(import_router)
router.include_router(crud_router)
