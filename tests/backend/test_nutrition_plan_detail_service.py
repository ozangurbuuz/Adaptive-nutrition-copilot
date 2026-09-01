import importlib
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.core.exceptions import ResourceNotFoundException
from app.models.enums import MealItemUnit, MealType, NutritionPlanStatus
from app.models.nutrition_plan import NutritionPlan
from app.models.plan_structure import Meal, MealItem, PlanDay


PLAN_ID = uuid.UUID("10000000-0000-0000-0000-000000000001")
CLIENT_ID = uuid.UUID("20000000-0000-0000-0000-000000000001")
DIETITIAN_ID = uuid.UUID("30000000-0000-0000-0000-000000000001")


class _SessionSpy:
    def __init__(self) -> None:
        self.write_calls = []

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


def _service_contract():
    try:
        service_module = importlib.import_module("app.services.nutrition_plan")
        repository_module = importlib.import_module("app.repositories.nutrition_plan")
        schema_module = importlib.import_module("app.schemas.nutrition_plan")
    except ModuleNotFoundError:
        pytest.fail(
            "nutrition plan service, repository, and schema modules are required",
            pytrace=False,
        )

    service = getattr(service_module, "get_nutrition_plan_detail", None)
    repository = getattr(repository_module, "get_nutrition_plan_by_id", None)
    dto_type = getattr(schema_module, "NutritionPlanRead", None)
    assert callable(service), "get_nutrition_plan_detail service function is missing"
    assert callable(repository), "get_nutrition_plan_by_id repository function is missing"
    assert dto_type is not None, "NutritionPlanRead DTO is missing"
    return service_module, repository_module, service, dto_type


def _patch_repository(
    monkeypatch,
    service_module,
    repository_module,
    replacement,
) -> None:
    monkeypatch.setattr(
        repository_module,
        "get_nutrition_plan_by_id",
        replacement,
    )
    if hasattr(service_module, "get_nutrition_plan_by_id"):
        monkeypatch.setattr(
            service_module,
            "get_nutrition_plan_by_id",
            replacement,
        )


def _build_unsorted_plan() -> NutritionPlan:
    timestamp = datetime(2026, 8, 21, 9, 30, tzinfo=timezone.utc)
    low_item = MealItem(
        id=uuid.UUID("60000000-0000-0000-0000-000000000001"),
        food_id=None,
        item_name="oatmeal snapshot",
        quantity=Decimal("50.000"),
        unit=MealItemUnit.GRAM,
        sort_order=0,
        created_at=timestamp,
        updated_at=timestamp,
    )
    high_item = MealItem(
        id=uuid.UUID("60000000-0000-0000-0000-000000000002"),
        food_id=uuid.UUID("70000000-0000-0000-0000-000000000001"),
        item_name="catalog snapshot",
        quantity=Decimal("25.000"),
        unit=MealItemUnit.GRAM,
        sort_order=0,
        created_at=timestamp,
        updated_at=timestamp,
    )
    low_meal = Meal(
        id=uuid.UUID("50000000-0000-0000-0000-000000000001"),
        meal_type=MealType.BREAKFAST,
        name="Breakfast",
        sort_order=0,
        created_at=timestamp,
        updated_at=timestamp,
    )
    high_meal = Meal(
        id=uuid.UUID("50000000-0000-0000-0000-000000000002"),
        meal_type=MealType.LUNCH,
        name="Lunch",
        sort_order=0,
        created_at=timestamp,
        updated_at=timestamp,
    )
    low_meal.items = [high_item, low_item]
    low_day = PlanDay(
        id=uuid.UUID("40000000-0000-0000-0000-000000000001"),
        day_number=1,
        label="First by id",
        created_at=timestamp,
        updated_at=timestamp,
    )
    high_day = PlanDay(
        id=uuid.UUID("40000000-0000-0000-0000-000000000002"),
        day_number=1,
        label="Second by id",
        created_at=timestamp,
        updated_at=timestamp,
    )
    low_day.meals = [high_meal, low_meal]

    plan = NutritionPlan(
        id=PLAN_ID,
        client_profile_id=CLIENT_ID,
        dietitian_profile_id=DIETITIAN_ID,
        title="Week 1 Plan",
        status=NutritionPlanStatus.DRAFT,
        starts_on=date(2026, 8, 24),
        ends_on=date(2026, 8, 30),
        notes="Initial plan",
        created_at=timestamp,
        updated_at=timestamp,
    )
    plan.plan_days = [high_day, low_day]
    return plan


def test_service_maps_repository_orm_to_explicit_sorted_dto(monkeypatch) -> None:
    service_module, repository_module, service, dto_type = _service_contract()
    plan = _build_unsorted_plan()
    session = _SessionSpy()
    repository_calls = []

    def fake_repository(received_session, received_plan_id):
        repository_calls.append((received_session, received_plan_id))
        return plan

    _patch_repository(
        monkeypatch,
        service_module,
        repository_module,
        fake_repository,
    )

    result = service(session, PLAN_ID)

    assert isinstance(result, dto_type)
    assert repository_calls == [(session, PLAN_ID)]
    assert result.model_dump(mode="json") == {
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
                "label": "First by id",
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
                                "item_name": "catalog snapshot",
                                "quantity": "25.000",
                                "unit": "GRAM",
                                "sort_order": 0,
                            },
                        ],
                    },
                    {
                        "id": "50000000-0000-0000-0000-000000000002",
                        "meal_type": "LUNCH",
                        "name": "Lunch",
                        "sort_order": 0,
                        "items": [],
                    },
                ],
            },
            {
                "id": "40000000-0000-0000-0000-000000000002",
                "day_number": 1,
                "label": "Second by id",
                "meals": [],
            },
        ],
    }
    assert session.write_calls == []


def test_service_raises_existing_not_found_when_repository_returns_none(
    monkeypatch,
) -> None:
    service_module, repository_module, service, _ = _service_contract()
    session = _SessionSpy()
    repository_calls = []

    def fake_repository(received_session, received_plan_id):
        repository_calls.append((received_session, received_plan_id))
        return None

    _patch_repository(
        monkeypatch,
        service_module,
        repository_module,
        fake_repository,
    )

    with pytest.raises(ResourceNotFoundException):
        service(session, PLAN_ID)

    assert repository_calls == [(session, PLAN_ID)]
    assert session.write_calls == []


def test_service_does_not_commit_flush_add_or_delete(monkeypatch) -> None:
    service_module, repository_module, service, _ = _service_contract()
    session = _SessionSpy()
    plan = _build_unsorted_plan()

    _patch_repository(
        monkeypatch,
        service_module,
        repository_module,
        lambda received_session, received_plan_id: plan,
    )

    service(session, PLAN_ID)

    assert session.write_calls == []
