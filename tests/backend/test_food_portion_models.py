import importlib
import subprocess
import sys
import uuid
from decimal import Decimal

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


def _model():
    module = importlib.import_module("app.models.food")
    food_portion = getattr(module, "FoodPortion", None)
    assert food_portion is not None, "FoodPortion model is missing"
    return food_portion


def test_food_portion_table_columns_types_and_mixins() -> None:
    from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

    FoodPortion = _model()
    assert FoodPortion.__tablename__ == "food_portions"
    assert issubclass(FoodPortion, UUIDPrimaryKeyMixin)
    assert issubclass(FoodPortion, TimestampMixin)

    table = FoodPortion.__table__
    assert set(table.columns.keys()) == {
        "id",
        "food_source_record_id",
        "source_portion_id",
        "amount",
        "measure_code",
        "measure_name",
        "modifier",
        "portion_description",
        "gram_weight",
        "sequence_number",
        "created_at",
        "updated_at",
    }
    assert isinstance(table.c.id.type, UUID)
    assert table.c.id.primary_key is True
    assert table.c.id.default is not None
    assert table.c.id.server_default is None

    assert isinstance(table.c.food_source_record_id.type, UUID)
    assert table.c.food_source_record_id.nullable is False
    assert table.c.food_source_record_id.default is None
    assert table.c.food_source_record_id.server_default is None

    for name, length, nullable in (
        ("source_portion_id", 100, True),
        ("measure_code", 50, True),
        ("measure_name", 100, True),
        ("modifier", 100, True),
        ("portion_description", 255, False),
    ):
        column = table.c[name]
        assert isinstance(column.type, String)
        assert not isinstance(column.type, Enum)
        assert column.type.length == length
        assert column.nullable is nullable
        assert column.default is None
        assert column.server_default is None

    for name, nullable in (("amount", False), ("gram_weight", True)):
        column = table.c[name]
        assert isinstance(column.type, Numeric)
        assert column.type.asdecimal is True
        assert (column.type.precision, column.type.scale) == (14, 6)
        assert column.nullable is nullable
        assert column.default is None
        assert column.server_default is None

    assert isinstance(table.c.sequence_number.type, Integer)
    assert table.c.sequence_number.nullable is True
    assert table.c.sequence_number.default is None
    assert table.c.sequence_number.server_default is None

    for name in ("created_at", "updated_at"):
        column = table.c[name]
        assert isinstance(column.type, DateTime)
        assert column.type.timezone is True
        assert column.nullable is False
        assert column.default is not None
        assert column.server_default is None
    assert table.c.updated_at.onupdate is not None


def test_food_portion_check_constraints_match_contract() -> None:
    FoodPortion = _model()
    constraints = {
        constraint.name: constraint
        for constraint in FoodPortion.__table__.constraints
    }
    expected = {
        "ck_food_portions_source_portion_id_nonblank",
        "ck_food_portions_amount_positive",
        "ck_food_portions_measure_code_canonical",
        "ck_food_portions_measure_name_nonblank",
        "ck_food_portions_modifier_nonblank",
        "ck_food_portions_description_nonblank",
        "ck_food_portions_gram_weight_positive",
        "ck_food_portions_sequence_number_positive",
    }
    assert expected.issubset(
        name
        for name, constraint in constraints.items()
        if isinstance(constraint, CheckConstraint)
    )


def test_food_portion_unique_constraints_use_source_identity_and_order() -> None:
    FoodPortion = _model()
    constraints = {
        constraint.name: constraint
        for constraint in FoodPortion.__table__.constraints
    }
    expected = {
        "uq_food_portions_source_record_source_portion_id": [
            "food_source_record_id",
            "source_portion_id",
        ],
        "uq_food_portions_source_record_sequence_number": [
            "food_source_record_id",
            "sequence_number",
        ],
    }
    for name, columns in expected.items():
        constraint = constraints[name]
        assert isinstance(constraint, UniqueConstraint)
        assert [column.name for column in constraint.columns] == columns

    assert not any(
        isinstance(constraint, UniqueConstraint)
        and [column.name for column in constraint.columns]
        == ["food_source_record_id", "amount", "measure_code", "modifier"]
        for constraint in FoodPortion.__table__.constraints
    )


def test_food_portion_foreign_key_and_index_are_explicit() -> None:
    FoodPortion = _model()
    column = FoodPortion.__table__.c.food_source_record_id
    foreign_keys = list(column.foreign_keys)

    assert len(foreign_keys) == 1
    assert foreign_keys[0].target_fullname == "food_source_records.id"
    assert foreign_keys[0].constraint.name == (
        "fk_food_portions_food_source_record_id_food_source_records"
    )
    assert foreign_keys[0].ondelete == "CASCADE"
    assert {index.name for index in FoodPortion.__table__.indexes} == {
        "ix_food_portions_food_source_record_id"
    }


def test_food_portion_relationship_is_source_record_composition() -> None:
    from app.models.food import FoodSourceRecord

    FoodPortion = _model()
    portions = FoodSourceRecord.__mapper__.relationships["portions"]
    source_record = FoodPortion.__mapper__.relationships["food_source_record"]

    assert portions.mapper.class_ is FoodPortion
    assert portions.uselist is True
    assert portions.back_populates == "food_source_record"
    assert "delete" in portions.cascade
    assert "delete-orphan" in portions.cascade
    assert portions.passive_deletes is True
    assert portions.single_parent is True
    assert source_record.mapper.class_ is FoodSourceRecord
    assert source_record.uselist is False
    assert source_record.back_populates == "portions"


def test_food_portion_has_no_redundant_parent_or_nutrient_fields() -> None:
    FoodPortion = _model()
    assert {
        "food_id",
        "dataset_release_id",
        "calories",
        "calories_kcal",
        "protein",
        "protein_g",
        "carbohydrate",
        "carbohydrate_g",
        "fat",
        "fat_g",
        "fiber",
        "fiber_g",
        "amount_per_100g",
    }.isdisjoint(FoodPortion.__table__.columns.keys())
    assert not isinstance(FoodPortion.__table__.c.measure_code.type, Enum)


def test_existing_source_record_columns_remain_unchanged() -> None:
    from app.models.food import FoodSourceRecord

    _model()
    assert set(FoodSourceRecord.__table__.columns.keys()) == {
        "id",
        "food_id",
        "dataset_release_id",
        "source_food_id",
        "canonical_name",
        "preparation_state",
        "created_at",
        "updated_at",
    }


def test_food_portion_constructor_preserves_decimal_and_source_values() -> None:
    FoodPortion = _model()
    source_record_id = uuid.uuid4()
    portion = FoodPortion(
        food_source_record_id=source_record_id,
        source_portion_id="FDC-PORTION-1",
        amount=Decimal("0.500000"),
        measure_code="CUP",
        measure_name="cup",
        modifier="chopped",
        portion_description="0.5 cup chopped",
        gram_weight=Decimal("13.500000"),
        sequence_number=1,
    )

    assert portion.food_source_record_id == source_record_id
    assert portion.source_portion_id == "FDC-PORTION-1"
    assert portion.amount == Decimal("0.500000")
    assert isinstance(portion.amount, Decimal)
    assert portion.measure_code == "CUP"
    assert portion.measure_name == "cup"
    assert portion.modifier == "chopped"
    assert portion.portion_description == "0.5 cup chopped"
    assert portion.gram_weight == Decimal("13.500000")
    assert isinstance(portion.gram_weight, Decimal)
    assert portion.sequence_number == 1


def test_food_portion_model_import_and_construction_do_not_use_database() -> None:
    script = """
import importlib
import psycopg
import sqlalchemy
from decimal import Decimal

def fail_if_database_is_used(*args, **kwargs):
    raise AssertionError("FoodPortion construction must not use the database")

sqlalchemy.create_engine = fail_if_database_is_used
psycopg.connect = fail_if_database_is_used

module = importlib.import_module("app.models.food")
FoodPortion = getattr(module, "FoodPortion", None)
assert FoodPortion is not None, "FoodPortion model is missing"
portion = FoodPortion(
    amount=Decimal("1"),
    portion_description="1 tablespoon",
    gram_weight=Decimal("13.5"),
)
assert portion.amount == Decimal("1")
assert portion.gram_weight == Decimal("13.5")
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
