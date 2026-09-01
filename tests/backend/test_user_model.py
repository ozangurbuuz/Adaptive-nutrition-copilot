import subprocess
import sys

from sqlalchemy import Boolean, DateTime, Enum, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID


def test_user_table_name_and_mixin_columns() -> None:
    from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin
    from app.models.user import User

    assert User.__tablename__ == "users"
    assert issubclass(User, UUIDPrimaryKeyMixin)
    assert issubclass(User, TimestampMixin)
    assert set(User.__table__.columns.keys()) == {
        "id",
        "email",
        "role",
        "is_active",
        "is_verified",
        "created_at",
        "updated_at",
    }
    assert isinstance(User.__table__.c.id.type, UUID)
    assert isinstance(User.__table__.c.created_at.type, DateTime)
    assert isinstance(User.__table__.c.updated_at.type, DateTime)


def test_user_email_schema_and_normalization() -> None:
    from app.core.security import UserRole
    from app.models.user import User

    email_column = User.__table__.c.email
    unique_constraints = [
        constraint
        for constraint in User.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    ]
    email_indexes = [
        index
        for index in User.__table__.indexes
        if [column.name for column in index.columns] == ["email"]
    ]

    assert isinstance(email_column.type, String)
    assert email_column.type.length == 320
    assert email_column.nullable is False
    assert len(unique_constraints) == 1
    assert unique_constraints[0].name == "uq_users_email"
    assert [column.name for column in unique_constraints[0].columns] == ["email"]
    assert len(email_indexes) == 1
    assert email_indexes[0].name == "ix_users_email"

    user = User(email="  Dietitian@Example.COM ", role=UserRole.DIETITIAN)
    assert user.email == "dietitian@example.com"


def test_user_role_reuses_security_enum_and_is_required() -> None:
    from app.core.security import UserRole
    from app.models.user import User

    role_column = User.__table__.c.role

    assert isinstance(role_column.type, Enum)
    assert role_column.type.enum_class is UserRole
    assert role_column.type.enums == ["DIETITIAN", "CLIENT", "ADMIN"]
    assert role_column.type.native_enum is False
    assert role_column.type.create_constraint is True
    assert role_column.nullable is False


def test_user_boolean_defaults_exist_in_python_and_database() -> None:
    from app.models.user import User

    is_active = User.__table__.c.is_active
    is_verified = User.__table__.c.is_verified

    assert isinstance(is_active.type, Boolean)
    assert is_active.nullable is False
    assert is_active.default is not None
    assert is_active.default.arg is True
    assert is_active.server_default is not None
    assert str(is_active.server_default.arg).lower() == "true"

    assert isinstance(is_verified.type, Boolean)
    assert is_verified.nullable is False
    assert is_verified.default is not None
    assert is_verified.default.arg is False
    assert is_verified.server_default is not None
    assert str(is_verified.server_default.arg).lower() == "false"


def test_base_metadata_contains_only_expected_domain_tables() -> None:
    from app.models.base import Base
    from app.models.client_details import ClientHealthProfile, ClientPreferences
    from app.models.clinical_records import (
        ClientAllergy,
        ClientMedicalCondition,
        ClientMedication,
    )
    from app.models.profiles import ClientProfile, DietitianProfile
    from app.models.nutrition_plan import NutritionPlan
    from app.models.plan_structure import Meal, MealItem, PlanDay
    from app.models.food import (
        DatasetRelease,
        Food,
        FoodNutrient,
        FoodNutrientValue,
        FoodPortion,
        FoodSourceRecord,
        NutrientDefinition,
    )
    from app.models.user import User

    assert dict(Base.metadata.tables) == {
        "users": User.__table__,
        "dietitian_profiles": DietitianProfile.__table__,
        "client_profiles": ClientProfile.__table__,
        "client_health_profiles": ClientHealthProfile.__table__,
        "client_preferences": ClientPreferences.__table__,
        "client_allergies": ClientAllergy.__table__,
        "client_medical_conditions": ClientMedicalCondition.__table__,
        "client_medications": ClientMedication.__table__,
        "nutrition_plans": NutritionPlan.__table__,
        "plan_days": PlanDay.__table__,
        "meals": Meal.__table__,
        "meal_items": MealItem.__table__,
        "foods": Food.__table__,
        "food_nutrients": FoodNutrient.__table__,
        "dataset_releases": DatasetRelease.__table__,
        "food_source_records": FoodSourceRecord.__table__,
        "nutrient_definitions": NutrientDefinition.__table__,
        "food_nutrient_values": FoodNutrientValue.__table__,
        "food_portions": FoodPortion.__table__,
    }


def test_user_model_import_does_not_open_database_connection() -> None:
    script = """
import psycopg
import sqlalchemy

def fail_if_database_is_used(*args, **kwargs):
    raise AssertionError("User model import must not use the database")

sqlalchemy.create_engine = fail_if_database_is_used
psycopg.connect = fail_if_database_is_used

from app.models.base import Base
from app.models.client_details import ClientHealthProfile, ClientPreferences
from app.models.clinical_records import (
    ClientAllergy,
    ClientMedicalCondition,
    ClientMedication,
)
from app.models.profiles import ClientProfile, DietitianProfile
from app.models.nutrition_plan import NutritionPlan
from app.models.plan_structure import Meal, MealItem, PlanDay
from app.models.food import (
    DatasetRelease,
    Food,
    FoodNutrient,
    FoodNutrientValue,
    FoodPortion,
    FoodSourceRecord,
    NutrientDefinition,
)
from app.models.user import User

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
    "nutrient_definitions",
    "food_nutrient_values",
    "food_portions",
}
assert User.__table__ is Base.metadata.tables["users"]
assert DietitianProfile.__table__ is Base.metadata.tables["dietitian_profiles"]
assert ClientProfile.__table__ is Base.metadata.tables["client_profiles"]
assert ClientHealthProfile.__table__ is Base.metadata.tables["client_health_profiles"]
assert ClientPreferences.__table__ is Base.metadata.tables["client_preferences"]
assert ClientAllergy.__table__ is Base.metadata.tables["client_allergies"]
assert ClientMedicalCondition.__table__ is Base.metadata.tables["client_medical_conditions"]
assert ClientMedication.__table__ is Base.metadata.tables["client_medications"]
assert NutritionPlan.__table__ is Base.metadata.tables["nutrition_plans"]
assert PlanDay.__table__ is Base.metadata.tables["plan_days"]
assert Meal.__table__ is Base.metadata.tables["meals"]
assert MealItem.__table__ is Base.metadata.tables["meal_items"]
assert Food.__table__ is Base.metadata.tables["foods"]
assert FoodNutrient.__table__ is Base.metadata.tables["food_nutrients"]
assert DatasetRelease.__table__ is Base.metadata.tables["dataset_releases"]
assert FoodSourceRecord.__table__ is Base.metadata.tables["food_source_records"]
assert NutrientDefinition.__table__ is Base.metadata.tables["nutrient_definitions"]
assert FoodNutrientValue.__table__ is Base.metadata.tables["food_nutrient_values"]
assert FoodPortion.__table__ is Base.metadata.tables["food_portions"]
"""

    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
