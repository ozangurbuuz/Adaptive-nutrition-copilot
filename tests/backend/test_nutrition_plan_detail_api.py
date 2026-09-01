import asyncio
import importlib
import uuid
from datetime import date
from decimal import Decimal

import httpx
import pytest
from fastapi.routing import APIRoute

from app.core.orm import get_database_session
from app.models.enums import MealItemUnit, MealType, NutritionPlanStatus
from app.models.nutrition_plan import NutritionPlan
from app.models.plan_structure import Meal, MealItem, PlanDay


PLAN_ID = uuid.UUID("10000000-0000-0000-0000-000000000001")
CLIENT_ID = uuid.UUID("20000000-0000-0000-0000-000000000001")
DIETITIAN_ID = uuid.UUID("30000000-0000-0000-0000-000000000001")


class _ReadResult:
    def __init__(self, value) -> None:
        self.value = value

    def unique(self):
        return self

    def scalars(self):
        return self

    def scalar_one_or_none(self):
        return self.value

    def one_or_none(self):
        return self.value

    def first(self):
        return self.value


class _ReadOnlySession:
    def __init__(self, value) -> None:
        self.value = value
        self.read_calls = []
        self.write_calls = []

    def execute(self, statement):
        self.read_calls.append(("execute", statement))
        return _ReadResult(self.value)

    def scalar(self, statement):
        self.read_calls.append(("scalar", statement))
        return self.value

    def scalars(self, statement):
        self.read_calls.append(("scalars", statement))
        return _ReadResult(self.value)

    def get(self, *args, **kwargs):
        self.read_calls.append(("get", args, kwargs))
        return self.value

    def add(self, *args, **kwargs) -> None:
        self.write_calls.append("add")

    def add_all(self, *args, **kwargs) -> None:
        self.write_calls.append("add_all")

    def commit(self) -> None:
        self.write_calls.append("commit")

    def flush(self) -> None:
        self.write_calls.append("flush")

    def delete(self, *args, **kwargs) -> None:
        self.write_calls.append("delete")


def _build_plan() -> NutritionPlan:
    day_one = PlanDay(
        id=uuid.UUID("40000000-0000-0000-0000-000000000001"),
        day_number=1,
        label="Day 1",
    )
    day_two = PlanDay(
        id=uuid.UUID("40000000-0000-0000-0000-000000000002"),
        day_number=2,
        label="Day 2",
    )
    breakfast = Meal(
        id=uuid.UUID("50000000-0000-0000-0000-000000000001"),
        meal_type=MealType.BREAKFAST,
        name="Breakfast",
        sort_order=0,
    )
    dinner = Meal(
        id=uuid.UUID("50000000-0000-0000-0000-000000000002"),
        meal_type=MealType.DINNER,
        name="Dinner",
        sort_order=5,
    )
    oatmeal = MealItem(
        id=uuid.UUID("60000000-0000-0000-0000-000000000001"),
        food_id=None,
        item_name="oatmeal snapshot",
        quantity=Decimal("50.000"),
        unit=MealItemUnit.GRAM,
        sort_order=0,
    )
    berries = MealItem(
        id=uuid.UUID("60000000-0000-0000-0000-000000000002"),
        food_id=uuid.UUID("70000000-0000-0000-0000-000000000001"),
        item_name="berry snapshot",
        quantity=Decimal("25.000"),
        unit=MealItemUnit.GRAM,
        sort_order=3,
    )
    breakfast.items = [berries, oatmeal]
    day_one.meals = [dinner, breakfast]

    plan = NutritionPlan(
        id=PLAN_ID,
        client_profile_id=CLIENT_ID,
        dietitian_profile_id=DIETITIAN_ID,
        title="Week 1 Plan",
        status=NutritionPlanStatus.DRAFT,
        starts_on=date(2026, 8, 24),
        ends_on=date(2026, 8, 30),
        notes="Initial plan",
    )
    plan.plan_days = [day_two, day_one]
    return plan


async def _get(path: str, session: _ReadOnlySession) -> httpx.Response:
    main_module = importlib.import_module("app.main")
    app = main_module.app
    previous_overrides = dict(app.dependency_overrides)
    app.dependency_overrides[get_database_session] = lambda: session
    try:
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.get(path)
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)


def test_detail_route_uses_explicit_non_orm_response_model() -> None:
    main_module = importlib.import_module("app.main")
    route = next(
        (
            candidate
            for candidate in main_module.app.routes
            if isinstance(candidate, APIRoute)
            and candidate.path == "/api/v1/nutrition-plans/{plan_id}"
            and "GET" in candidate.methods
        ),
        None,
    )

    assert route is not None, "NutritionPlan detail GET route is not registered"
    assert route.response_model is not None
    assert route.response_model is not NutritionPlan


def test_detail_route_delegates_to_service_without_querying_session(
    monkeypatch,
) -> None:
    try:
        route_module = importlib.import_module("app.api.v1.nutrition_plans")
    except ModuleNotFoundError:
        pytest.fail(
            "app.api.v1.nutrition_plans is required for the detail route",
            pytrace=False,
        )

    service = getattr(route_module, "get_nutrition_plan_detail", None)
    assert callable(service), "router must import get_nutrition_plan_detail"
    session = _ReadOnlySession(None)
    service_calls = []
    response_payload = {
        "id": str(PLAN_ID),
        "client_profile_id": str(CLIENT_ID),
        "dietitian_profile_id": str(DIETITIAN_ID),
        "title": "Delegated plan",
        "status": "DRAFT",
        "starts_on": None,
        "ends_on": None,
        "notes": None,
        "days": [],
    }

    def fake_service(received_session, received_plan_id):
        service_calls.append((received_session, received_plan_id))
        return response_payload

    monkeypatch.setattr(
        route_module,
        "get_nutrition_plan_detail",
        fake_service,
    )

    response = asyncio.run(
        _get(f"/api/v1/nutrition-plans/{PLAN_ID}", session)
    )

    assert response.status_code == 200
    assert response.json() == response_payload
    assert service_calls == [(session, PLAN_ID)]
    assert session.read_calls == []
    assert session.write_calls == []


def test_get_nutrition_plan_detail_returns_sorted_nested_contract() -> None:
    session = _ReadOnlySession(_build_plan())

    response = asyncio.run(
        _get(f"/api/v1/nutrition-plans/{PLAN_ID}", session)
    )

    assert response.status_code == 200
    assert response.json() == {
        "id": str(PLAN_ID),
        "client_profile_id": str(CLIENT_ID),
        "dietitian_profile_id": str(DIETITIAN_ID),
        "title": "Week 1 Plan",
        "status": "DRAFT",
        "starts_on": "2026-08-24",
        "ends_on": "2026-08-30",
        "notes": "Initial plan",
        "days": [
            {
                "id": "40000000-0000-0000-0000-000000000001",
                "day_number": 1,
                "label": "Day 1",
                "meals": [
                    {
                        "id": "50000000-0000-0000-0000-000000000001",
                        "meal_type": "BREAKFAST",
                        "name": "Breakfast",
                        "sort_order": 0,
                        "items": [
                            {
                                "id": "60000000-0000-0000-0000-000000000001",
                                "food_id": None,
                                "item_name": "oatmeal snapshot",
                                "quantity": "50.000",
                                "unit": "GRAM",
                                "sort_order": 0,
                            },
                            {
                                "id": "60000000-0000-0000-0000-000000000002",
                                "food_id": "70000000-0000-0000-0000-000000000001",
                                "item_name": "berry snapshot",
                                "quantity": "25.000",
                                "unit": "GRAM",
                                "sort_order": 3,
                            },
                        ],
                    },
                    {
                        "id": "50000000-0000-0000-0000-000000000002",
                        "meal_type": "DINNER",
                        "name": "Dinner",
                        "sort_order": 5,
                        "items": [],
                    },
                ],
            },
            {
                "id": "40000000-0000-0000-0000-000000000002",
                "day_number": 2,
                "label": "Day 2",
                "meals": [],
            },
        ],
    }
    assert session.read_calls
    assert session.write_calls == []


def test_get_nutrition_plan_detail_returns_standard_404_for_unknown_uuid() -> None:
    session = _ReadOnlySession(None)

    response = asyncio.run(
        _get(f"/api/v1/nutrition-plans/{uuid.uuid4()}", session)
    )

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "RESOURCE_NOT_FOUND",
            "message": "Requested resource was not found",
            "details": None,
        }
    }
    assert session.write_calls == []


def test_get_nutrition_plan_detail_rejects_invalid_uuid() -> None:
    session = _ReadOnlySession(None)

    response = asyncio.run(
        _get("/api/v1/nutrition-plans/not-a-uuid", session)
    )

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "Request validation failed",
            "details": [
                {
                    "location": ["path", "plan_id"],
                    "type": "uuid_parsing",
                }
            ],
        }
    }
    assert session.read_calls == []
    assert session.write_calls == []
