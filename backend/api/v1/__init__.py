from fastapi import APIRouter

from .admin import router as admin_router
from .conversation import router as conversation_router
from .schemes import router as schemes_router

router = APIRouter()
router.include_router(conversation_router)
router.include_router(schemes_router)
router.include_router(admin_router)
