from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.nutrition_plan import NutritionPlan
from app.models.plan_structure import Meal, PlanDay
from app.models.profiles import ClientProfile, DietitianProfile
from app.schemas.nutrition_plan import NutritionPlanCreate


def get_client_profile_by_id(
    session: Session,
    client_profile_id: UUID,
) -> ClientProfile | None:
    statement = select(ClientProfile).where(ClientProfile.id == client_profile_id)
    return session.execute(statement).scalar_one_or_none()


def get_dietitian_profile_by_id(
    session: Session,
    dietitian_profile_id: UUID,
) -> DietitianProfile | None:
    statement = select(DietitianProfile).where(
        DietitianProfile.id == dietitian_profile_id
    )
    return session.execute(statement).scalar_one_or_none()


def create_nutrition_plan(
    session: Session,
    plan_create: NutritionPlanCreate,
) -> NutritionPlan:
    plan = NutritionPlan(
        client_profile_id=plan_create.client_profile_id,
        dietitian_profile_id=plan_create.dietitian_profile_id,
        title=plan_create.title,
        starts_on=plan_create.starts_on,
        ends_on=plan_create.ends_on,
        notes=plan_create.notes,
    )
    session.add(plan)
    session.flush()
    return plan


def get_nutrition_plan_by_id(
    session: Session,
    plan_id: UUID,
) -> NutritionPlan | None:
    statement = (
        select(NutritionPlan)
        .where(NutritionPlan.id == plan_id)
        .options(
            selectinload(NutritionPlan.plan_days)
            .selectinload(PlanDay.meals)
            .selectinload(Meal.items)
        )
    )
    return session.scalar(statement)
