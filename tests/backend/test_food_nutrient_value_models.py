import importlib
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import CheckConstraint, DateTime, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID


def _models():
    module = importlib.import_module("app.models.food")
    definition = getattr(module, "NutrientDefinition", None)
    value = getattr(module, "FoodNutrientValue", None)
    assert definition is not None, "NutrientDefinition model is missing"
    assert value is not None, "FoodNutrientValue model is missing"
    return definition, value


def test_food_nutrient_value_columns_types_and_mixins() -> None:
    from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

    _, FoodNutrientValue = _models()
    assert FoodNutrientValue.__tablename__ == "food_nutrient_values"
    assert issubclass(FoodNutrientValue, UUIDPrimaryKeyMixin)
    assert issubclass(FoodNutrientValue, TimestampMixin)

    table = FoodNutrientValue.__table__
    assert set(table.columns.keys()) == {
        "id",
        "food_source_record_id",
        "nutrient_definition_id",
        "amount_per_100g",
        "created_at",
        "updated_at",
    }
    assert isinstance(table.c.id.type, UUID)
    assert table.c.id.primary_key is True
    assert table.c.id.default is not None
    for name in ("food_source_record_id", "nutrient_definition_id"):
        assert isinstance(table.c[name].type, UUID)
        assert table.c[name].nullable is False
    amount = table.c.amount_per_100g
    assert isinstance(amount.type, Numeric)
    assert amount.type.precision == 14
    assert amount.type.scale == 6
    assert amount.nullable is True
    assert amount.default is None
    assert amount.server_default is None
    for name in ("created_at", "updated_at"):
        assert isinstance(table.c[name].type, DateTime)
        assert table.c[name].type.timezone is True
        assert table.c[name].nullable is False


def test_food_nutrient_value_unique_and_non_negative_constraints() -> None:
    _, FoodNutrientValue = _models()
    constraints = {
        constraint.name: constraint
        for constraint in FoodNutrientValue.__table__.constraints
    }
    unique = constraints[
        "uq_food_nutrient_values_source_record_nutrient"
    ]
    assert isinstance(unique, UniqueConstraint)
    assert [column.name for column in unique.columns] == [
        "food_source_record_id",
        "nutrient_definition_id",
    ]
    assert isinstance(
        constraints["ck_food_nutrient_values_amount_non_negative"],
        CheckConstraint,
    )


def test_food_nutrient_value_foreign_keys_and_delete_actions() -> None:
    _, FoodNutrientValue = _models()
    expected = {
        "food_source_record_id": ("food_source_records.id", "CASCADE"),
        "nutrient_definition_id": ("nutrient_definitions.id", "RESTRICT"),
    }
    for column_name, (target, ondelete) in expected.items():
        foreign_keys = list(FoodNutrientValue.__table__.c[column_name].foreign_keys)
        assert len(foreign_keys) == 1
        assert foreign_keys[0].target_fullname == target
        assert foreign_keys[0].ondelete == ondelete


def test_generic_nutrient_relationship_contract() -> None:
    from app.models.food import FoodSourceRecord

    NutrientDefinition, FoodNutrientValue = _models()
    source_values = FoodSourceRecord.__mapper__.relationships["nutrient_values"]
    value_source = FoodNutrientValue.__mapper__.relationships[
        "food_source_record"
    ]
    definition_values = NutrientDefinition.__mapper__.relationships["values"]
    value_definition = FoodNutrientValue.__mapper__.relationships[
        "nutrient_definition"
    ]

    assert source_values.mapper.class_ is FoodNutrientValue
    assert source_values.back_populates == "food_source_record"
    assert "delete" in source_values.cascade
    assert "delete-orphan" in source_values.cascade
    assert source_values.passive_deletes is True
    assert source_values.single_parent is True
    assert value_source.back_populates == "nutrient_values"

    assert definition_values.mapper.class_ is FoodNutrientValue
    assert definition_values.back_populates == "nutrient_definition"
    assert "delete" not in definition_values.cascade
    assert definition_values.passive_deletes == "all"
    assert value_definition.back_populates == "values"


@pytest.mark.parametrize(
    "amount",
    [Decimal("12.345678"), None, Decimal("0")],
)
def test_food_nutrient_value_constructor_preserves_amount(amount) -> None:
    _, FoodNutrientValue = _models()
    value = FoodNutrientValue(
        food_source_record_id=uuid.uuid4(),
        nutrient_definition_id=uuid.uuid4(),
        amount_per_100g=amount,
    )

    assert value.amount_per_100g == amount
    if amount is not None:
        assert isinstance(value.amount_per_100g, Decimal)


def test_food_nutrient_value_has_no_redundant_fields() -> None:
    _, FoodNutrientValue = _models()
    assert {
        "source",
        "source_nutrient_id",
        "unit",
        "basis_grams",
        "reference_quantity",
        "reference_unit",
    }.isdisjoint(FoodNutrientValue.__table__.columns.keys())


def test_legacy_food_nutrient_contract_remains_unchanged() -> None:
    from app.models.food import FoodNutrient

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
