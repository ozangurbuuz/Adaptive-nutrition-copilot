import subprocess
import sys

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import UUID


def test_meal_item_food_id_is_nullable_named_restrict_foreign_key() -> None:
    from app.models.food import Food
    from app.models.plan_structure import MealItem

    food_id = MealItem.__table__.c.food_id
    foreign_keys = list(food_id.foreign_keys)

    assert isinstance(food_id.type, UUID)
    assert food_id.nullable is True
    assert len(foreign_keys) == 1
    assert foreign_keys[0].target_fullname == "foods.id"
    assert foreign_keys[0].constraint.name == "fk_meal_items_food_id_foods"
    assert foreign_keys[0].ondelete == "RESTRICT"
    assert Food.__table__.c.id is foreign_keys[0].column


def test_meal_item_food_relationship_is_bidirectional_many_to_one() -> None:
    from app.models.food import Food
    from app.models.plan_structure import MealItem

    meal_item_food = MealItem.__mapper__.relationships["food"]
    food_meal_items = Food.__mapper__.relationships["meal_items"]

    assert meal_item_food.mapper.class_ is Food
    assert meal_item_food.uselist is False
    assert meal_item_food.back_populates == "meal_items"
    assert food_meal_items.mapper.class_ is MealItem
    assert food_meal_items.uselist is True
    assert food_meal_items.back_populates == "food"
    assert "delete" not in food_meal_items.cascade
    assert "delete-orphan" not in food_meal_items.cascade
    assert food_meal_items.passive_deletes == "all"


def test_meal_item_keeps_snapshot_name_without_nutrient_columns() -> None:
    from app.models.plan_structure import MealItem

    table = MealItem.__table__
    assert isinstance(table.c.item_name.type, String)
    assert table.c.item_name.type.length == 255
    assert table.c.item_name.nullable is False
    assert not {
        "calories",
        "calories_kcal",
        "protein",
        "protein_g",
        "carbs",
        "carbohydrate",
        "carbohydrate_g",
        "fat",
        "fat_g",
        "fiber_g",
    }.intersection(table.columns.keys())


def test_meal_item_food_import_does_not_open_database_connection() -> None:
    script = """
import psycopg
import sqlalchemy

def fail_if_database_is_used(*args, **kwargs):
    raise AssertionError("MealItem Food import must not use the database")

sqlalchemy.create_engine = fail_if_database_is_used
psycopg.connect = fail_if_database_is_used

from app.models.food import Food
from app.models.plan_structure import MealItem

assert MealItem.__table__.c.food_id.foreign_keys
assert MealItem.__mapper__.relationships["food"].mapper.class_ is Food
assert Food.__mapper__.relationships["meal_items"].mapper.class_ is MealItem
"""

    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
