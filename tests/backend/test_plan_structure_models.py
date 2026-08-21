import subprocess
import sys

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID


def test_plan_structure_tables_columns_foreign_keys_and_mixins() -> None:
    from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin
    from app.models.plan_structure import Meal, MealItem, PlanDay

    expectations = (
        (
            PlanDay,
            "plan_days",
            "nutrition_plan_id",
            "nutrition_plans.id",
            "fk_plan_days_nutrition_plan_id_nutrition_plans",
        ),
        (
            Meal,
            "meals",
            "plan_day_id",
            "plan_days.id",
            "fk_meals_plan_day_id_plan_days",
        ),
        (
            MealItem,
            "meal_items",
            "meal_id",
            "meals.id",
            "fk_meal_items_meal_id_meals",
        ),
    )

    for model, table_name, fk_column_name, target, constraint_name in expectations:
        assert model.__tablename__ == table_name
        assert issubclass(model, UUIDPrimaryKeyMixin)
        assert issubclass(model, TimestampMixin)
        assert isinstance(model.__table__.c.id.type, UUID)
        assert isinstance(model.__table__.c.created_at.type, DateTime)
        assert isinstance(model.__table__.c.updated_at.type, DateTime)

        fk_column = model.__table__.c[fk_column_name]
        foreign_keys = list(fk_column.foreign_keys)
        assert isinstance(fk_column.type, UUID)
        assert fk_column.nullable is False
        assert len(foreign_keys) == 1
        assert foreign_keys[0].target_fullname == target
        assert foreign_keys[0].constraint.name == constraint_name
        assert foreign_keys[0].ondelete == "CASCADE"


def test_plan_structure_relationships_are_composed_one_to_many() -> None:
    from app.models.nutrition_plan import NutritionPlan
    from app.models.plan_structure import Meal, MealItem, PlanDay

    relationships = (
        (NutritionPlan, "plan_days", PlanDay, "nutrition_plan"),
        (PlanDay, "meals", Meal, "plan_day"),
        (Meal, "items", MealItem, "meal"),
    )

    for parent, collection_name, child, parent_name in relationships:
        collection = parent.__mapper__.relationships[collection_name]
        scalar = child.__mapper__.relationships[parent_name]

        assert collection.mapper.class_ is child
        assert collection.uselist is True
        assert collection.back_populates == parent_name
        assert "delete" in collection.cascade
        assert "delete-orphan" in collection.cascade
        assert collection.passive_deletes is True
        assert collection.single_parent is True
        assert scalar.mapper.class_ is parent
        assert scalar.uselist is False
        assert scalar.back_populates == collection_name


def test_plan_day_constraints_are_positive_and_unique_per_plan() -> None:
    from app.models.plan_structure import PlanDay

    table = PlanDay.__table__
    assert isinstance(table.c.day_number.type, Integer)
    assert table.c.day_number.nullable is False
    assert isinstance(table.c.label.type, String)
    assert table.c.label.nullable is True

    constraints = {constraint.name: constraint for constraint in table.constraints}
    assert "ck_plan_days_day_number_positive" in constraints
    assert isinstance(
        constraints["ck_plan_days_day_number_positive"], CheckConstraint
    )
    assert "uq_plan_days_nutrition_plan_id_day_number" in constraints


def test_meal_type_and_sort_order_are_controlled_and_unique_per_day() -> None:
    from app.models.enums import MealType
    from app.models.plan_structure import Meal

    table = Meal.__table__
    assert isinstance(table.c.meal_type.type, Enum)
    assert table.c.meal_type.type.enum_class is MealType
    assert table.c.meal_type.type.enums == [
        "BREAKFAST",
        "MORNING_SNACK",
        "LUNCH",
        "AFTERNOON_SNACK",
        "DINNER",
        "EVENING_SNACK",
        "OTHER",
    ]
    assert table.c.meal_type.type.native_enum is False
    assert table.c.meal_type.type.create_constraint is True
    assert table.c.meal_type.nullable is False
    assert isinstance(table.c.sort_order.type, Integer)
    assert table.c.sort_order.nullable is False

    constraints = {constraint.name: constraint for constraint in table.constraints}
    assert "ck_meals_sort_order_non_negative" in constraints
    assert isinstance(constraints["ck_meals_sort_order_non_negative"], CheckConstraint)
    assert "uq_meals_plan_day_id_sort_order" in constraints


def test_meal_item_quantity_unit_and_snapshot_columns() -> None:
    from app.models.enums import MealItemUnit
    from app.models.plan_structure import MealItem

    table = MealItem.__table__
    assert set(table.columns.keys()) == {
        "id",
        "meal_id",
        "food_id",
        "item_name",
        "sort_order",
        "quantity",
        "unit",
        "created_at",
        "updated_at",
    }
    assert isinstance(table.c.item_name.type, String)
    assert table.c.item_name.nullable is False
    assert isinstance(table.c.quantity.type, Numeric)
    assert (table.c.quantity.type.precision, table.c.quantity.type.scale) == (10, 3)
    assert table.c.quantity.type.asdecimal is True
    assert table.c.quantity.nullable is False
    assert isinstance(table.c.unit.type, Enum)
    assert table.c.unit.type.enum_class is MealItemUnit
    assert table.c.unit.type.enums == ["GRAM", "MILLILITER", "PIECE", "PORTION"]
    assert table.c.unit.type.native_enum is False
    assert table.c.unit.type.create_constraint is True
    assert table.c.unit.nullable is False
    assert any(
        isinstance(constraint, CheckConstraint)
        and constraint.name == "ck_meal_items_quantity_positive"
        for constraint in table.constraints
    )
    assert not {
        "calories",
        "protein",
        "carbohydrate",
        "fat",
        "allergen_json",
        "substitution_data",
    }.intersection(table.columns.keys())


def test_meal_item_sort_order_is_integer_non_nullable_and_defaults_to_zero() -> None:
    from app.models.plan_structure import MealItem

    sort_order = MealItem.__table__.c.sort_order

    assert isinstance(sort_order.type, Integer)
    assert sort_order.nullable is False
    assert sort_order.default is not None
    assert sort_order.default.is_scalar is True
    assert sort_order.default.arg == 0
    assert sort_order.server_default is not None
    assert str(sort_order.server_default.arg) == "0"


def test_meal_item_sort_order_is_non_negative_without_unique_constraint() -> None:
    from app.models.plan_structure import Meal, MealItem

    table = MealItem.__table__
    constraints = {constraint.name: constraint for constraint in table.constraints}

    check = constraints["ck_meal_items_sort_order_non_negative"]
    assert isinstance(check, CheckConstraint)
    assert str(check.sqltext) == "sort_order >= 0"
    assert not any(
        isinstance(constraint, UniqueConstraint)
        and "sort_order" in constraint.columns
        for constraint in table.constraints
    )
    relationship = Meal.__mapper__.relationships["items"]
    assert relationship.mapper.class_ is MealItem
    assert relationship.back_populates == "meal"
    assert relationship.order_by is False


def test_metadata_contains_only_expected_plan_structure_tables() -> None:
    from app.models.base import Base
    from app.models.food import Food, FoodNutrient
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
    }
    assert PlanDay.__table__ is Base.metadata.tables["plan_days"]
    assert Meal.__table__ is Base.metadata.tables["meals"]
    assert MealItem.__table__ is Base.metadata.tables["meal_items"]
    assert Food.__table__ is Base.metadata.tables["foods"]
    assert FoodNutrient.__table__ is Base.metadata.tables["food_nutrients"]


def test_plan_structure_import_does_not_open_database_connection() -> None:
    script = """
import psycopg
import sqlalchemy

def fail_if_database_is_used(*args, **kwargs):
    raise AssertionError("Plan structure import must not use the database")

sqlalchemy.create_engine = fail_if_database_is_used
psycopg.connect = fail_if_database_is_used

from app.models.base import Base
from app.models.plan_structure import Meal, MealItem, PlanDay

assert isinstance(MealItem.__table__.c.sort_order.type, sqlalchemy.Integer)
assert MealItem.__mapper__.relationships["meal"].back_populates == "items"
assert Meal.__mapper__.relationships["items"].order_by is False
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
}
"""

    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
