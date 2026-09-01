import importlib
import subprocess
import sys

from sqlalchemy import CheckConstraint, DateTime, Enum as SqlEnum, String
from sqlalchemy.dialects.postgresql import UUID


def _contract():
    enums_module = importlib.import_module("app.models.enums")
    food_module = importlib.import_module("app.models.food")
    nutrient_unit = getattr(enums_module, "NutrientUnit", None)
    definition = getattr(food_module, "NutrientDefinition", None)
    assert nutrient_unit is not None, "NutrientUnit enum is missing"
    assert definition is not None, "NutrientDefinition model is missing"
    return nutrient_unit, definition


def test_nutrient_unit_members_and_non_native_storage() -> None:
    NutrientUnit, NutrientDefinition = _contract()

    assert [member.value for member in NutrientUnit] == [
        "KCAL",
        "GRAM",
        "MILLIGRAM",
        "MICROGRAM",
    ]
    unit_column = NutrientDefinition.__table__.c.unit
    assert isinstance(unit_column.type, SqlEnum)
    assert unit_column.type.native_enum is False
    assert unit_column.type.create_constraint is True
    assert unit_column.type.validate_strings is True
    assert unit_column.type.enums == [
        "KCAL",
        "GRAM",
        "MILLIGRAM",
        "MICROGRAM",
    ]


def test_nutrient_definition_columns_types_and_mixins() -> None:
    from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

    _, NutrientDefinition = _contract()
    assert NutrientDefinition.__tablename__ == "nutrient_definitions"
    assert issubclass(NutrientDefinition, UUIDPrimaryKeyMixin)
    assert issubclass(NutrientDefinition, TimestampMixin)

    table = NutrientDefinition.__table__
    assert set(table.columns.keys()) == {
        "id",
        "code",
        "name_en",
        "unit",
        "created_at",
        "updated_at",
    }
    assert isinstance(table.c.id.type, UUID)
    assert table.c.id.primary_key is True
    assert table.c.id.default is not None
    assert table.c.id.server_default is None
    for name, length in (("code", 50), ("name_en", 100)):
        column = table.c[name]
        assert isinstance(column.type, String)
        assert column.type.length == length
        assert column.nullable is False
        assert column.default is None
        assert column.server_default is None
    assert table.c.unit.nullable is False
    for name in ("created_at", "updated_at"):
        column = table.c[name]
        assert isinstance(column.type, DateTime)
        assert column.type.timezone is True
        assert column.nullable is False
        assert column.default is not None
        assert column.server_default is None
    assert table.c.updated_at.onupdate is not None


def test_nutrient_definition_unique_and_canonical_constraints() -> None:
    _, NutrientDefinition = _contract()
    constraints = {
        constraint.name: constraint
        for constraint in NutrientDefinition.__table__.constraints
    }

    unique = constraints["uq_nutrient_definitions_code"]
    assert [column.name for column in unique.columns] == ["code"]
    check_names = {
        name
        for name, constraint in constraints.items()
        if isinstance(constraint, CheckConstraint)
    }
    assert {
        "ck_nutrient_definitions_code_nonblank",
        "ck_nutrient_definitions_code_canonical",
        "ck_nutrient_definitions_name_en_nonblank",
    }.issubset(check_names)


def test_definition_constructor_preserves_canonical_text() -> None:
    NutrientUnit, NutrientDefinition = _contract()
    definition = NutrientDefinition(
        code="ENERGY_KCAL",
        name_en="Energy",
        unit=NutrientUnit.KCAL,
    )

    assert definition.code == "ENERGY_KCAL"
    assert definition.name_en == "Energy"
    assert definition.unit is NutrientUnit.KCAL


def test_definition_constructor_does_not_silently_normalize_text() -> None:
    NutrientUnit, NutrientDefinition = _contract()
    definition = NutrientDefinition(
        code=" protein ",
        name_en=" Protein ",
        unit=NutrientUnit.GRAM,
    )

    assert definition.code == " protein "
    assert definition.name_en == " Protein "


def test_definition_has_no_source_specific_fields() -> None:
    _, NutrientDefinition = _contract()
    assert {
        "source",
        "source_nutrient_id",
    }.isdisjoint(NutrientDefinition.__table__.columns.keys())


def test_nutrient_model_construction_does_not_use_database() -> None:
    script = """
import psycopg
import sqlalchemy

def fail_if_database_is_used(*args, **kwargs):
    raise AssertionError("Nutrient construction must not use the database")

sqlalchemy.create_engine = fail_if_database_is_used
psycopg.connect = fail_if_database_is_used

from app.models.enums import NutrientUnit
from app.models.food import NutrientDefinition, FoodNutrientValue

definition = NutrientDefinition(code="PROTEIN", name_en="Protein", unit=NutrientUnit.GRAM)
value = FoodNutrientValue(amount_per_100g=None)
assert definition.code == "PROTEIN"
assert value.amount_per_100g is None
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
