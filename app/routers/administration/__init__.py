from fastapi import APIRouter

from .info import router as info_router
from .board import router as board_router
from .code_lists import router as code_lists_router
from .backups import router as backups_router
from .bulk import router as bulk_router

router = APIRouter()

router.include_router(info_router)
router.include_router(board_router)
router.include_router(code_lists_router)
router.include_router(backups_router)
router.include_router(bulk_router)
