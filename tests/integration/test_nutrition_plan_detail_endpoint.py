import asyncio
import uuid
from decimal import Decimal

import httpx
import pytest
from sqlalchemy.orm import Session

from app.core.orm import get_database_session
from app.core.security import UserRole
from app.main import app
from app.models.enums import (
    FoodCategory,
    MealItemUnit,
    MealType,
    NutrientReferenceUnit,
)
from app.models.food import Food, FoodNutrient
from app.models.nutrition_plan import NutritionPlan
from app.models.plan_structure import Meal, MealItem, PlanDay
from app.models.profiles import ClientProfile, DietitianProfile
from app.models.user import User


pytestmark = pytest.mark.integration


async def _get_detail(plan_id: uuid.UUID, session: Session) -> httpx.Response:
    previous_overrides = dict(app.dependency_overrides)
    app.dependency_overrides[get_database_session] = lambda: session
    try:
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.get(f"/api/v1/nutrition-plans/{plan_id}")
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)


def test_detail_endpoint_round_trips_sorted_snapshot_without_food_embedding(
    db_session: Session,
) -> None:
    client = ClientProfile(
        user=User(email=f"detail-client-{uuid.uuid4()}@example.test", role=UserRole.CLIENT),
        display_name="Detail Client",
    )
    dietitian = DietitianProfile(
        user=User(
            email=f"detail-dietitian-{uuid.uuid4()}@example.test",
            role=UserRole.DIETITIAN,
        ),
        display_name="Detail Dietitian",
    )
    plan = NutritionPlan(
        client_profile=client,
        dietitian_profile=dietitian,
        title="Week 1 Plan",
        notes="Initial plan",
    )
    day_two = PlanDay(nutrition_plan=plan, day_number=2, label="Day 2")
    day_one = PlanDay(nutrition_plan=plan, day_number=1, label="Day 1")
    dinner = Meal(
        plan_day=day_one,
        meal_type=MealType.DINNER,
        name="Dinner",
        sort_order=5,
    )
    breakfast = Meal(
        plan_day=day_one,
        meal_type=MealType.BREAKFAST,
        name="Breakfast",
        sort_order=0,
    )
    food = Food(
        name=f"detail food {uuid.uuid4()}",
        category=FoodCategory.GRAIN,
        default_serving_quantity=Decimal("100"),
        default_serving_unit=MealItemUnit.GRAM,
    )
    nutrient = FoodNutrient(
        food=food,
        reference_unit=NutrientReferenceUnit.GRAM,
        calories_kcal=Decimal("120"),
        protein_g=Decimal("4"),
        carbohydrate_g=Decimal("24"),
        fat_g=Decimal("2"),
    )
    linked_item = MealItem(
        meal=breakfast,
        food=food,
        item_name="catalog snapshot",
        quantity=Decimal("100"),
        unit=MealItemUnit.GRAM,
        sort_order=4,
    )
    snapshot_item = MealItem(
        meal=breakfast,
        food_id=None,
        item_name="oatmeal snapshot",
        quantity=Decimal("50"),
        unit=MealItemUnit.GRAM,
        sort_order=0,
    )
    db_session.add_all(
        [day_two, dinner, nutrient, linked_item, snapshot_item]
    )
    db_session.flush()
    plan_id = plan.id
    linked_food_id = food.id
    db_session.expunge_all()

    response = asyncio.run(_get_detail(plan_id, db_session))

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "id",
        "client_profile_id",
        "dietitian_profile_id",
        "title",
        "status",
        "starts_on",
        "ends_on",
        "notes",
        "days",
    }
    assert [day["day_number"] for day in body["days"]] == [1, 2]
    assert [meal["sort_order"] for meal in body["days"][0]["meals"]] == [0, 5]

    items = body["days"][0]["meals"][0]["items"]
    assert [item["sort_order"] for item in items] == [0, 4]
    assert items[0] == {
        "id": str(snapshot_item.id),
        "food_id": None,
        "item_name": "oatmeal snapshot",
        "quantity": "50.000",
        "unit": "GRAM",
        "sort_order": 0,
    }
    assert items[1]["food_id"] == str(linked_food_id)
    assert set(items[1]) == {
        "id",
        "food_id",
        "item_name",
        "quantity",
        "unit",
        "sort_order",
    }
