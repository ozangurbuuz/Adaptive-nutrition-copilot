import subprocess
import sys

from sqlalchemy import CheckConstraint, Date, DateTime, Enum, String
from sqlalchemy.dialects.postgresql import UUID


def test_nutrition_plan_table_columns_and_mixins() -> None:
    from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin
    from app.models.nutrition_plan import NutritionPlan

    assert NutritionPlan.__tablename__ == "nutrition_plans"
    assert issubclass(NutritionPlan, UUIDPrimaryKeyMixin)
    assert issubclass(NutritionPlan, TimestampMixin)
    assert set(NutritionPlan.__table__.columns.keys()) == {
        "id",
        "client_profile_id",
        "dietitian_profile_id",
        "title",
        "status",
        "starts_on",
        "ends_on",
        "notes",
        "created_at",
        "updated_at",
    }
    assert isinstance(NutritionPlan.__table__.c.id.type, UUID)
    assert isinstance(NutritionPlan.__table__.c.created_at.type, DateTime)
    assert isinstance(NutritionPlan.__table__.c.updated_at.type, DateTime)


def test_nutrition_plan_foreign_keys_are_required_named_and_restrict_deletes() -> None:
    from app.models.nutrition_plan import NutritionPlan

    for column_name, target, constraint_name in (
        (
            "client_profile_id",
            "client_profiles.id",
            "fk_nutrition_plans_client_profile_id_client_profiles",
        ),
        (
            "dietitian_profile_id",
            "dietitian_profiles.id",
            "fk_nutrition_plans_dietitian_profile_id_dietitian_profiles",
        ),
    ):
        column = NutritionPlan.__table__.c[column_name]
        foreign_keys = list(column.foreign_keys)

        assert isinstance(column.type, UUID)
        assert column.nullable is False
        assert len(foreign_keys) == 1
        assert foreign_keys[0].target_fullname == target
        assert foreign_keys[0].constraint.name == constraint_name
        assert foreign_keys[0].ondelete == "RESTRICT"


def test_profile_plan_relationships_are_bidirectional_one_to_many() -> None:
    from app.models.nutrition_plan import NutritionPlan
    from app.models.profiles import ClientProfile, DietitianProfile

    for profile_model, plan_attribute in (
        (ClientProfile, "client_profile"),
        (DietitianProfile, "dietitian_profile"),
    ):
        profile_relationship = profile_model.__mapper__.relationships[
            "nutrition_plans"
        ]
        plan_relationship = NutritionPlan.__mapper__.relationships[plan_attribute]

        assert profile_relationship.mapper.class_ is NutritionPlan
        assert profile_relationship.uselist is True
        assert profile_relationship.back_populates == plan_attribute
        assert "delete" not in profile_relationship.cascade
        assert profile_relationship.passive_deletes == "all"
        assert plan_relationship.mapper.class_ is profile_model
        assert plan_relationship.back_populates == "nutrition_plans"
        assert plan_relationship.uselist is False


def test_nutrition_plan_status_title_defaults_and_date_constraint() -> None:
    from app.models.enums import NutritionPlanStatus
    from app.models.nutrition_plan import NutritionPlan

    table = NutritionPlan.__table__
    assert isinstance(table.c.title.type, String)
    assert table.c.title.type.length == 255
    assert table.c.title.nullable is False
    assert isinstance(table.c.notes.type, String)
    assert table.c.notes.type.length == 1000
    assert table.c.notes.nullable is True

    status = table.c.status
    assert isinstance(status.type, Enum)
    assert status.type.enum_class is NutritionPlanStatus
    assert status.type.enums == ["DRAFT", "ACTIVE", "ARCHIVED"]
    assert status.type.native_enum is False
    assert status.type.create_constraint is True
    assert status.nullable is False
    assert status.default is not None
    assert status.default.arg is NutritionPlanStatus.DRAFT
    assert status.server_default is not None
    assert str(status.server_default.arg) == "'DRAFT'"

    assert isinstance(table.c.starts_on.type, Date)
    assert table.c.starts_on.nullable is True
    assert isinstance(table.c.ends_on.type, Date)
    assert table.c.ends_on.nullable is True
    assert any(
        isinstance(constraint, CheckConstraint)
        and constraint.name == "ck_nutrition_plans_date_range"
        for constraint in table.constraints
    )


def test_metadata_contains_only_expected_tables_and_no_plan_children() -> None:
    from app.models.base import Base
    from app.models.food import Food, FoodNutrient
    from app.models.nutrition_plan import NutritionPlan
    from app.models.plan_structure import Meal, MealItem, PlanDay

    assert set(Base.metadata.tables) == {
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
    }
    assert NutritionPlan.__table__ is Base.metadata.tables["nutrition_plans"]
    assert PlanDay.__table__ is Base.metadata.tables["plan_days"]
    assert Meal.__table__ is Base.metadata.tables["meals"]
    assert MealItem.__table__ is Base.metadata.tables["meal_items"]
    assert Food.__table__ is Base.metadata.tables["foods"]
    assert FoodNutrient.__table__ is Base.metadata.tables["food_nutrients"]


def test_nutrition_plan_import_does_not_open_database_connection() -> None:
    script = """
import psycopg
import sqlalchemy

def fail_if_database_is_used(*args, **kwargs):
    raise AssertionError("Nutrition plan import must not use the database")

sqlalchemy.create_engine = fail_if_database_is_used
psycopg.connect = fail_if_database_is_used

from app.models.base import Base
from app.models.nutrition_plan import NutritionPlan
from app.models.plan_structure import Meal, MealItem, PlanDay

assert set(Base.metadata.tables) == {
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
}
"""

    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
