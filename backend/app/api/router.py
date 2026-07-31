from fastapi import APIRouter

from app.api.healthcheck import router as healthcheck_router
from app.api.v1.router import router as api_v1_router


router = APIRouter()
router.include_router(healthcheck_router)
router.include_router(api_v1_router)
