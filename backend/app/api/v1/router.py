from fastapi import APIRouter

from app.api.v1.nutrition_plans import router as nutrition_plans_router


router = APIRouter(prefix="/api/v1")
router.include_router(nutrition_plans_router)
