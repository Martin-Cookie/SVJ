from fastapi import APIRouter

from .crud import router as crud_router
from .import_owners import router as import_owners_router
from .import_contacts import router as import_contacts_router

router = APIRouter()
# Import routers MUST be registered before crud_router,
# because crud has /{owner_id} catch-all that would intercept /import paths.
router.include_router(import_owners_router)
router.include_router(import_contacts_router)
router.include_router(crud_router)
