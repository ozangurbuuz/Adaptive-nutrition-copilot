from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.orm import get_database_session
from app.schemas.nutrition_plan import NutritionPlanCreate, NutritionPlanRead
from app.services.nutrition_plan import (
    create_nutrition_plan as create_nutrition_plan_service,
    get_nutrition_plan_detail,
)


router = APIRouter(prefix="/nutrition-plans")


@router.post(
    "",
    response_model=NutritionPlanRead,
    status_code=status.HTTP_201_CREATED,
)
def create_nutrition_plan_endpoint(
    plan_create: NutritionPlanCreate,
    session: Annotated[Session, Depends(get_database_session)],
) -> NutritionPlanRead:
    return create_nutrition_plan_service(session, plan_create)


@router.get("/{plan_id}", response_model=NutritionPlanRead)
def read_nutrition_plan_detail(
    plan_id: UUID,
    session: Annotated[Session, Depends(get_database_session)],
) -> NutritionPlanRead:
    return get_nutrition_plan_detail(session, plan_id)
