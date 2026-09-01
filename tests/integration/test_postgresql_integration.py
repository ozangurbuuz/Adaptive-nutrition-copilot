import uuid
from decimal import Decimal

import pytest
import sqlalchemy as sa
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import UserRole
from app.models.client_details import ClientHealthProfile, ClientPreferences
from app.models.clinical_records import (
    ClientAllergy,
    ClientMedicalCondition,
    ClientMedication,
)
from app.models.enums import (
    AllergySeverity,
    DietaryPattern,
    FoodCategory,
    MealItemUnit,
    MealType,
    MedicalConditionStatus,
    MedicationStatus,
    NutrientReferenceUnit,
)
from app.models.food import Food, FoodNutrient
from app.models.nutrition_plan import NutritionPlan
from app.models.plan_structure import Meal, MealItem, PlanDay
from app.models.profiles import ClientProfile, DietitianProfile
from app.models.user import User


pytestmark = pytest.mark.integration

EXPECTED_TABLES = {
    "users",
    "dietitian_profiles",
    "client_profiles",
    "client_health_profiles",
    "client_preferences",
    "client_allergies",
    "client_medical_conditions",
    "client_medications",
    "nutrition_plans",
    "plan_days",
    "meals",
    "meal_items",
    "foods",
    "food_nutrients",
    "dataset_releases",
    "food_source_records",
    "nutrient_definitions",
    "food_nutrient_values",
    "food_portions",
    "alembic_version",
}


def _new_user(role: UserRole, label: str) -> User:
    return User(
        email=f"{label}-{uuid.uuid4()}@example.test",
        role=role,
    )


def _create_plan(session: Session) -> tuple[NutritionPlan, ClientProfile, DietitianProfile]:
    client_profile = ClientProfile(
        user=_new_user(UserRole.CLIENT, "client"),
        display_name="Integration Client",
    )
    dietitian_profile = DietitianProfile(
        user=_new_user(UserRole.DIETITIAN, "dietitian"),
        display_name="Integration Dietitian",
    )
    plan = NutritionPlan(
        client_profile=client_profile,
        dietitian_profile=dietitian_profile,
        title="Integration Plan",
    )
    session.add(plan)
    session.flush()
    return plan, client_profile, dietitian_profile


def _create_meal(session: Session) -> tuple[NutritionPlan, PlanDay, Meal]:
    plan, _, _ = _create_plan(session)
    day = PlanDay(nutrition_plan=plan, day_number=1, label="Day 1")
    meal = Meal(
        plan_day=day,
        meal_type=MealType.LUNCH,
        name="Lunch",
        sort_order=0,
    )
    session.add(meal)
    session.flush()
    return plan, day, meal


def _create_food(session: Session, name: str = "integration food") -> Food:
    food = Food(
        name=f"{name} {uuid.uuid4()}",
        category=FoodCategory.OTHER,
        default_serving_quantity=Decimal("100"),
        default_serving_unit=MealItemUnit.GRAM,
    )
    session.add(food)
    session.flush()
    return food


def test_migrations_upgrade_empty_database_to_expected_head(
    postgres_engine: Engine,
) -> None:
    inspector = sa.inspect(postgres_engine)
    assert set(inspector.get_table_names()) == EXPECTED_TABLES

    with postgres_engine.connect() as connection:
        head = connection.scalar(sa.text("SELECT version_num FROM alembic_version"))

    assert head == "0013_food_portions"


def test_duplicate_user_email_is_rejected(db_session: Session) -> None:
    db_session.add_all(
        [
            User(email="duplicate@example.test", role=UserRole.CLIENT),
            User(email="  DUPLICATE@example.test  ", role=UserRole.DIETITIAN),
        ]
    )

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_second_client_profile_for_same_user_is_rejected(db_session: Session) -> None:
    user = _new_user(UserRole.CLIENT, "single-profile")
    db_session.add(user)
    db_session.flush()
    db_session.add_all(
        [
            ClientProfile(user_id=user.id, display_name="First"),
            ClientProfile(user_id=user.id, display_name="Second"),
        ]
    )

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_duplicate_plan_day_number_is_rejected(db_session: Session) -> None:
    plan, _, _ = _create_plan(db_session)
    db_session.add_all(
        [
            PlanDay(nutrition_plan_id=plan.id, day_number=1),
            PlanDay(nutrition_plan_id=plan.id, day_number=1),
        ]
    )

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_non_positive_meal_item_quantity_is_rejected(db_session: Session) -> None:
    _, _, meal = _create_meal(db_session)
    db_session.add(
        MealItem(
            meal_id=meal.id,
            item_name="Invalid Quantity",
            quantity=Decimal("0"),
            unit=MealItemUnit.GRAM,
        )
    )

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_meal_item_sort_order_orm_default_preserves_nullable_food_and_snapshot(
    db_session: Session,
) -> None:
    _, _, meal = _create_meal(db_session)
    item = MealItem(
        meal_id=meal.id,
        item_name="Default Order Snapshot",
        quantity=Decimal("1"),
        unit=MealItemUnit.PORTION,
    )
    db_session.add(item)
    db_session.flush()

    assert item.sort_order == 0
    assert item.food_id is None
    assert item.item_name == "Default Order Snapshot"


def test_meal_item_sort_order_server_default_is_zero(db_session: Session) -> None:
    _, _, meal = _create_meal(db_session)
    item_id = uuid.uuid4()
    db_session.execute(
        sa.text(
            "INSERT INTO meal_items "
            "(id, meal_id, item_name, quantity, unit, created_at, updated_at) "
            "VALUES (:id, :meal_id, :item_name, :quantity, :unit, now(), now())"
        ),
        {
            "id": item_id,
            "meal_id": meal.id,
            "item_name": "Server Default Snapshot",
            "quantity": Decimal("1"),
            "unit": MealItemUnit.PORTION.value,
        },
    )

    row = db_session.execute(
        sa.text(
            "SELECT sort_order, food_id, item_name "
            "FROM meal_items WHERE id = :id"
        ),
        {"id": item_id},
    ).one()

    assert row.sort_order == 0
    assert row.food_id is None
    assert row.item_name == "Server Default Snapshot"


def test_negative_meal_item_sort_order_is_rejected(db_session: Session) -> None:
    _, _, meal = _create_meal(db_session)
    db_session.add(
        MealItem(
            meal_id=meal.id,
            item_name="Invalid Order",
            quantity=Decimal("1"),
            unit=MealItemUnit.PORTION,
            sort_order=-1,
        )
    )

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_negative_nutrient_value_is_rejected(db_session: Session) -> None:
    food = _create_food(db_session, "negative nutrient")
    db_session.add(
        FoodNutrient(
            food_id=food.id,
            reference_unit=NutrientReferenceUnit.GRAM,
            calories_kcal=Decimal("-1"),
            protein_g=Decimal("1"),
            carbohydrate_g=Decimal("1"),
            fat_g=Decimal("1"),
        )
    )

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_invalid_enum_string_is_rejected_by_database_check(
    db_session: Session,
) -> None:
    statement = sa.text(
        "INSERT INTO foods "
        "(id, name, category, is_active, created_at, updated_at) "
        "VALUES (:id, :name, :category, true, now(), now())"
    )

    with pytest.raises(IntegrityError):
        db_session.execute(
            statement,
            {
                "id": uuid.uuid4(),
                "name": "invalid category",
                "category": "INVALID",
            },
        )


def test_duplicate_normalized_allergen_is_rejected(db_session: Session) -> None:
    profile = ClientProfile(
        user=_new_user(UserRole.CLIENT, "allergy"),
        display_name="Allergy Client",
    )
    db_session.add(profile)
    db_session.flush()
    db_session.add_all(
        [
            ClientAllergy(
                client_profile_id=profile.id,
                allergen_name="  PEANUT  ",
                severity=AllergySeverity.SEVERE,
            ),
            ClientAllergy(
                client_profile_id=profile.id,
                allergen_name="peanut",
                severity=AllergySeverity.MILD,
            ),
        ]
    )

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_meal_item_links_to_food_and_food_delete_is_restricted(
    db_session: Session,
) -> None:
    _, _, meal = _create_meal(db_session)
    food = _create_food(db_session, "linked food")
    item = MealItem(
        meal_id=meal.id,
        food_id=food.id,
        item_name="Food Snapshot",
        quantity=Decimal("100"),
        unit=MealItemUnit.GRAM,
    )
    db_session.add(item)
    db_session.flush()

    assert item.food_id == food.id
    with pytest.raises(IntegrityError):
        db_session.execute(sa.delete(Food).where(Food.id == food.id))


def test_plan_delete_cascades_through_composition(db_session: Session) -> None:
    plan, day, meal = _create_meal(db_session)
    item = MealItem(
        meal_id=meal.id,
        item_name="Cascade Item",
        quantity=Decimal("1"),
        unit=MealItemUnit.PORTION,
    )
    db_session.add(item)
    db_session.flush()
    ids = (plan.id, day.id, meal.id, item.id)

    db_session.execute(sa.delete(NutritionPlan).where(NutritionPlan.id == plan.id))
    db_session.flush()

    for model, record_id in zip((NutritionPlan, PlanDay, Meal, MealItem), ids):
        count = db_session.scalar(
            sa.select(sa.func.count()).select_from(model).where(model.id == record_id)
        )
        assert count == 0


def test_client_profile_delete_cascades_to_client_details(
    db_session: Session,
) -> None:
    profile = ClientProfile(
        user=_new_user(UserRole.CLIENT, "client-cascade"),
        display_name="Cascade Client",
    )
    health = ClientHealthProfile(client_profile=profile, height_cm=Decimal("170"))
    preferences = ClientPreferences(
        client_profile=profile,
        dietary_pattern=DietaryPattern.OMNIVORE,
    )
    allergy = ClientAllergy(
        client_profile=profile,
        allergen_name="sesame",
        severity=AllergySeverity.MODERATE,
    )
    condition = ClientMedicalCondition(
        client_profile=profile,
        condition_name="condition",
        status=MedicalConditionStatus.ACTIVE,
    )
    medication = ClientMedication(
        client_profile=profile,
        medication_name="medication",
        status=MedicationStatus.ACTIVE,
    )
    db_session.add_all([health, preferences, allergy, condition, medication])
    db_session.flush()
    ids = {
        ClientHealthProfile: health.id,
        ClientPreferences: preferences.id,
        ClientAllergy: allergy.id,
        ClientMedicalCondition: condition.id,
        ClientMedication: medication.id,
    }

    db_session.execute(sa.delete(ClientProfile).where(ClientProfile.id == profile.id))
    db_session.flush()

    for model, record_id in ids.items():
        count = db_session.scalar(
            sa.select(sa.func.count()).select_from(model).where(model.id == record_id)
        )
        assert count == 0


def test_client_profile_with_plan_is_protected_by_restrict(
    db_session: Session,
) -> None:
    _, client_profile, _ = _create_plan(db_session)

    with pytest.raises(IntegrityError):
        db_session.execute(
            sa.delete(ClientProfile).where(ClientProfile.id == client_profile.id)
        )


def test_orm_round_trip_persists_relationships(
    postgres_connection: Connection,
) -> None:
    first_session = Session(
        bind=postgres_connection,
        join_transaction_mode="create_savepoint",
        expire_on_commit=False,
    )
    try:
        plan, _, _ = _create_plan(first_session)
        day = PlanDay(nutrition_plan=plan, day_number=1, label="Round Trip Day")
        meal = Meal(
            plan_day=day,
            meal_type=MealType.DINNER,
            name="Round Trip Meal",
            sort_order=0,
        )
        food = Food(
            name="Round Trip Food",
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
            fiber_g=Decimal("3"),
        )
        item = MealItem(
            meal=meal,
            food=food,
            item_name="Round Trip Snapshot",
            quantity=Decimal("100"),
            unit=MealItemUnit.GRAM,
        )
        first_session.add_all([nutrient, item])
        first_session.commit()
        plan_id = plan.id
    finally:
        first_session.close()

    second_session = Session(
        bind=postgres_connection,
        join_transaction_mode="create_savepoint",
        expire_on_commit=False,
    )
    try:
        loaded_plan = second_session.get(NutritionPlan, plan_id)
        assert loaded_plan is not None
        assert loaded_plan.client_profile.display_name == "Integration Client"
        assert loaded_plan.dietitian_profile.display_name == "Integration Dietitian"
        assert len(loaded_plan.plan_days) == 1
        loaded_item = loaded_plan.plan_days[0].meals[0].items[0]
        assert loaded_item.item_name == "Round Trip Snapshot"
        assert loaded_item.food is not None
        assert loaded_item.food.name == "round trip food"
        assert loaded_item.food.nutrient_profile is not None
        assert loaded_item.food.nutrient_profile.calories_kcal == Decimal("120.000")
    finally:
        second_session.close()
