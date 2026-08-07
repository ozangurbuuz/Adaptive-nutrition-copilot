import subprocess
import sys
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, DateTime, Enum, JSON, Numeric, String
from sqlalchemy.dialects.postgresql import UUID


def test_food_table_columns_mixins_name_and_category() -> None:
    from app.models.enums import FoodCategory
    from app.models.food import Food
    from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

    assert Food.__tablename__ == "foods"
    assert issubclass(Food, UUIDPrimaryKeyMixin)
    assert issubclass(Food, TimestampMixin)
    assert set(Food.__table__.columns.keys()) == {
        "id",
        "name",
        "category",
        "default_serving_quantity",
        "default_serving_unit",
        "is_active",
        "created_at",
        "updated_at",
    }
    assert isinstance(Food.__table__.c.id.type, UUID)
    assert isinstance(Food.__table__.c.created_at.type, DateTime)
    assert isinstance(Food.__table__.c.updated_at.type, DateTime)
    assert isinstance(Food.__table__.c.name.type, String)
    assert Food.__table__.c.name.type.length == 255
    assert Food.__table__.c.name.nullable is False

    food = Food(name="  Whole MILK  ", category=FoodCategory.DAIRY)
    assert food.name == "whole milk"

    category = Food.__table__.c.category
    assert isinstance(category.type, Enum)
    assert category.type.enum_class is FoodCategory
    assert category.type.enums == [
        "DAIRY",
        "MEAT",
        "EGG",
        "LEGUME",
        "GRAIN",
        "VEGETABLE",
        "FRUIT",
        "NUT_SEED",
        "FAT_OIL",
        "BEVERAGE",
        "OTHER",
    ]
    assert category.type.native_enum is False
    assert category.type.create_constraint is True
    assert category.nullable is False


def test_food_serving_fields_reuse_meal_item_unit_without_global_name_unique() -> None:
    from app.models.enums import MealItemUnit
    from app.models.food import Food

    table = Food.__table__
    quantity = table.c.default_serving_quantity
    unit = table.c.default_serving_unit

    assert isinstance(quantity.type, Numeric)
    assert (quantity.type.precision, quantity.type.scale) == (10, 3)
    assert quantity.type.asdecimal is True
    assert quantity.nullable is True
    assert isinstance(unit.type, Enum)
    assert unit.type.enum_class is MealItemUnit
    assert unit.type.enums == ["GRAM", "MILLILITER", "PIECE", "PORTION"]
    assert unit.nullable is True
    assert any(
        isinstance(constraint, CheckConstraint)
        and constraint.name == "ck_foods_default_serving_quantity_positive"
        for constraint in table.constraints
    )
    assert not any(
        constraint.__class__.__name__ == "UniqueConstraint"
        and [column.name for column in constraint.columns] == ["name"]
        for constraint in table.constraints
    )

    is_active = table.c.is_active
    assert isinstance(is_active.type, Boolean)
    assert is_active.nullable is False
    assert is_active.default is not None
    assert is_active.default.arg is True
    assert is_active.server_default is not None
    assert str(is_active.server_default.arg).lower() == "true"


def test_food_nutrient_table_numeric_fields_and_defaults() -> None:
    from app.models.enums import NutrientReferenceUnit
    from app.models.food import FoodNutrient
    from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

    assert FoodNutrient.__tablename__ == "food_nutrients"
    assert issubclass(FoodNutrient, UUIDPrimaryKeyMixin)
    assert issubclass(FoodNutrient, TimestampMixin)
    assert set(FoodNutrient.__table__.columns.keys()) == {
        "id",
        "food_id",
        "reference_quantity",
        "reference_unit",
        "calories_kcal",
        "protein_g",
        "carbohydrate_g",
        "fat_g",
        "fiber_g",
        "created_at",
        "updated_at",
    }

    table = FoodNutrient.__table__
    for column_name in (
        "reference_quantity",
        "calories_kcal",
        "protein_g",
        "carbohydrate_g",
        "fat_g",
        "fiber_g",
    ):
        column = table.c[column_name]
        assert isinstance(column.type, Numeric)
        assert column.type.asdecimal is True
        assert (column.type.precision, column.type.scale) == (10, 3)

    assert table.c.reference_quantity.nullable is False
    assert table.c.reference_quantity.default is not None
    assert table.c.reference_quantity.default.arg == Decimal("100")
    assert table.c.reference_quantity.server_default is not None
    assert str(table.c.reference_quantity.server_default.arg) == "100"
    assert table.c.calories_kcal.nullable is False
    assert table.c.protein_g.nullable is False
    assert table.c.carbohydrate_g.nullable is False
    assert table.c.fat_g.nullable is False
    assert table.c.fiber_g.nullable is True

    reference_unit = table.c.reference_unit
    assert isinstance(reference_unit.type, Enum)
    assert reference_unit.type.enum_class is NutrientReferenceUnit
    assert reference_unit.type.enums == ["GRAM", "MILLILITER"]
    assert reference_unit.type.native_enum is False
    assert reference_unit.type.create_constraint is True
    assert reference_unit.nullable is False


def test_food_nutrient_constraints_cover_reference_and_all_values() -> None:
    from app.models.food import FoodNutrient

    constraint_names = {
        constraint.name
        for constraint in FoodNutrient.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }
    assert {
        "ck_food_nutrients_reference_quantity_positive",
        "ck_food_nutrients_calories_kcal_non_negative",
        "ck_food_nutrients_protein_g_non_negative",
        "ck_food_nutrients_carbohydrate_g_non_negative",
        "ck_food_nutrients_fat_g_non_negative",
        "ck_food_nutrients_fiber_g_non_negative",
    }.issubset(constraint_names)


def test_food_nutrient_relationship_is_one_to_one_composition() -> None:
    from app.models.food import Food, FoodNutrient

    food_id = FoodNutrient.__table__.c.food_id
    foreign_keys = list(food_id.foreign_keys)
    assert isinstance(food_id.type, UUID)
    assert food_id.nullable is False
    assert len(foreign_keys) == 1
    assert foreign_keys[0].target_fullname == "foods.id"
    assert foreign_keys[0].constraint.name == "fk_food_nutrients_food_id_foods"
    assert foreign_keys[0].ondelete == "CASCADE"
    assert any(
        constraint.__class__.__name__ == "UniqueConstraint"
        and constraint.name == "uq_food_nutrients_food_id"
        and [column.name for column in constraint.columns] == ["food_id"]
        for constraint in FoodNutrient.__table__.constraints
    )

    nutrient_profile = Food.__mapper__.relationships["nutrient_profile"]
    food = FoodNutrient.__mapper__.relationships["food"]
    assert nutrient_profile.mapper.class_ is FoodNutrient
    assert nutrient_profile.uselist is False
    assert nutrient_profile.back_populates == "food"
    assert "delete" in nutrient_profile.cascade
    assert "delete-orphan" in nutrient_profile.cascade
    assert nutrient_profile.passive_deletes is True
    assert nutrient_profile.single_parent is True
    assert food.mapper.class_ is Food
    assert food.uselist is False
    assert food.back_populates == "nutrient_profile"


def test_food_models_keep_catalog_scope_without_meal_item_nutrients() -> None:
    from app.models.base import Base
    from app.models.food import Food, FoodNutrient
    from app.models.plan_structure import MealItem

    assert not {
        "calories_kcal",
        "protein_g",
        "carbohydrate_g",
        "fat_g",
        "fiber_g",
    }.intersection(Food.__table__.columns.keys())
    assert not any(
        isinstance(column.type, JSON) for column in FoodNutrient.__table__.columns
    )
    assert not {
        "vitamins",
        "minerals",
        "micronutrients",
        "allergens",
        "glycemic_index",
        "embedding",
        "substitution_score",
    }.intersection(FoodNutrient.__table__.columns.keys())
    assert "food_id" in MealItem.__table__.columns
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


def test_food_import_does_not_open_database_connection() -> None:
    script = """
import psycopg
import sqlalchemy

def fail_if_database_is_used(*args, **kwargs):
    raise AssertionError("Food import must not use the database")

sqlalchemy.create_engine = fail_if_database_is_used
psycopg.connect = fail_if_database_is_used

from app.models.base import Base
from app.models.food import Food, FoodNutrient

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
