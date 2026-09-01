from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import ResourceNotFoundException
from app.models.nutrition_plan import NutritionPlan
from app.models.plan_structure import Meal, MealItem, PlanDay
from app.repositories import nutrition_plan as nutrition_plan_repository
from app.schemas.nutrition_plan import (
    MealItemRead,
    MealRead,
    NutritionPlanCreate,
    NutritionPlanRead,
    PlanDayRead,
)


def _map_meal_item(item: MealItem) -> MealItemRead:
    return MealItemRead(
        id=item.id,
        food_id=item.food_id,
        item_name=item.item_name,
        quantity=item.quantity,
        unit=item.unit,
        sort_order=item.sort_order,
    )


def _map_meal(meal: Meal) -> MealRead:
    items = sorted(meal.items, key=lambda item: (item.sort_order, str(item.id)))
    return MealRead(
        id=meal.id,
        meal_type=meal.meal_type,
        name=meal.name,
        sort_order=meal.sort_order,
        items=[_map_meal_item(item) for item in items],
    )


def _map_plan_day(day: PlanDay) -> PlanDayRead:
    meals = sorted(day.meals, key=lambda meal: (meal.sort_order, str(meal.id)))
    return PlanDayRead(
        id=day.id,
        day_number=day.day_number,
        label=day.label,
        meals=[_map_meal(meal) for meal in meals],
    )


def _map_nutrition_plan(plan: NutritionPlan) -> NutritionPlanRead:
    days = sorted(
        plan.plan_days,
        key=lambda day: (day.day_number, str(day.id)),
    )
    return NutritionPlanRead(
        id=plan.id,
        client_profile_id=plan.client_profile_id,
        dietitian_profile_id=plan.dietitian_profile_id,
        title=plan.title,
        status=plan.status,
        starts_on=plan.starts_on,
        ends_on=plan.ends_on,
        notes=plan.notes,
        days=[_map_plan_day(day) for day in days],
    )


def get_nutrition_plan_detail(
    session: Session,
    plan_id: UUID,
) -> NutritionPlanRead:
    plan = nutrition_plan_repository.get_nutrition_plan_by_id(session, plan_id)
    if plan is None:
        raise ResourceNotFoundException()
    return _map_nutrition_plan(plan)


def create_nutrition_plan(
    session: Session,
    plan_create: NutritionPlanCreate,
) -> NutritionPlanRead:
    client_profile = nutrition_plan_repository.get_client_profile_by_id(
        session,
        plan_create.client_profile_id,
    )
    if client_profile is None:
        raise ResourceNotFoundException()

    dietitian_profile = nutrition_plan_repository.get_dietitian_profile_by_id(
        session,
        plan_create.dietitian_profile_id,
    )
    if dietitian_profile is None:
        raise ResourceNotFoundException()

    try:
        plan = nutrition_plan_repository.create_nutrition_plan(
            session,
            plan_create,
        )
        result = NutritionPlanRead(
            id=plan.id,
            client_profile_id=plan.client_profile_id,
            dietitian_profile_id=plan.dietitian_profile_id,
            title=plan.title,
            status=plan.status,
            starts_on=plan.starts_on,
            ends_on=plan.ends_on,
            notes=plan.notes,
            days=[],
        )
        session.commit()
    except Exception:
        session.rollback()
        raise

    return result
