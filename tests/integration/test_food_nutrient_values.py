import importlib
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.orm import Session

from app.models.enums import FoodCategory, MealItemUnit, NutrientReferenceUnit
from app.models.food import DatasetRelease, Food, FoodNutrient, FoodSourceRecord


pytestmark = pytest.mark.integration

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_INI = PROJECT_ROOT / "backend" / "alembic.ini"
MIGRATION_PATH = (
    PROJECT_ROOT
    / "backend"
    / "alembic"
    / "versions"
    / "0012_create_food_nutrient_values.py"
)
NUTRIENT_REVISION = "0012_food_nutrient_values"
CURRENT_HEAD = "0013_food_portions"


def _contract():
    enums_module = importlib.import_module("app.models.enums")
    food_module = importlib.import_module("app.models.food")
    nutrient_unit = getattr(enums_module, "NutrientUnit", None)
    definition = getattr(food_module, "NutrientDefinition", None)
    value = getattr(food_module, "FoodNutrientValue", None)
    assert nutrient_unit is not None, "NutrientUnit enum is missing"
    assert definition is not None, "NutrientDefinition model is missing"
    assert value is not None, "FoodNutrientValue model is missing"
    return nutrient_unit, definition, value


def _release() -> DatasetRelease:
    unique_value = uuid.uuid4().hex
    return DatasetRelease(
        source="USDA_FOUNDATION",
        release_version=f"nutrient-{unique_value}",
        downloaded_at=datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc),
        checksum_sha256=unique_value * 2,
        license_reference="USDA public-domain notice",
    )


def _food(name: str = "generic nutrient food") -> Food:
    return Food(
        name=f"{name} {uuid.uuid4().hex}",
        category=FoodCategory.OTHER,
        default_serving_quantity=Decimal("100"),
        default_serving_unit=MealItemUnit.GRAM,
    )


def _source_record(session: Session, *, release=None, food=None):
    release = release or _release()
    food = food or _food()
    session.add_all([release, food])
    session.flush()
    record = FoodSourceRecord(
        food_id=food.id,
        dataset_release_id=release.id,
        source_food_id=f"FDC-{uuid.uuid4().hex}",
        canonical_name="Canonical source food",
    )
    session.add(record)
    session.flush()
    return release, food, record


def _definition(
    *,
    code: str | None = None,
    name_en: str = "Protein",
    unit=None,
):
    NutrientUnit, NutrientDefinition, _ = _contract()
    return NutrientDefinition(
        code=code or f"NUTRIENT_{uuid.uuid4().hex.upper()}",
        name_en=name_en,
        unit=unit or NutrientUnit.GRAM,
    )


def _value(
    session: Session,
    *,
    record=None,
    definition=None,
    amount=Decimal("12.345678"),
):
    _, _, FoodNutrientValue = _contract()
    if record is None:
        _, _, record = _source_record(session)
    definition = definition or _definition()
    session.add(definition)
    session.flush()
    value = FoodNutrientValue(
        food_source_record_id=record.id,
        nutrient_definition_id=definition.id,
        amount_per_100g=amount,
    )
    session.add(value)
    session.flush()
    return record, definition, value


def test_nutrient_definition_round_trip(db_session: Session) -> None:
    NutrientUnit, NutrientDefinition, _ = _contract()
    definition = NutrientDefinition(
        code="ENERGY_KCAL",
        name_en="Energy",
        unit=NutrientUnit.KCAL,
    )
    db_session.add(definition)
    db_session.flush()
    definition_id = definition.id
    db_session.expire_all()

    loaded = db_session.get(NutrientDefinition, definition_id)
    assert loaded is not None
    assert loaded.code == "ENERGY_KCAL"
    assert loaded.name_en == "Energy"
    assert loaded.unit is NutrientUnit.KCAL


def test_food_source_record_nutrient_value_round_trip(db_session: Session) -> None:
    _, _, FoodNutrientValue = _contract()
    record, definition, value = _value(db_session)
    value_id = value.id
    record_id = record.id
    definition_id = definition.id
    db_session.expire_all()

    loaded = db_session.get(FoodNutrientValue, value_id)
    assert loaded is not None
    assert loaded.food_source_record.id == record_id
    assert loaded.nutrient_definition.id == definition_id
    assert [item.id for item in loaded.food_source_record.nutrient_values] == [
        value_id
    ]
    assert [item.id for item in loaded.nutrient_definition.values] == [value_id]


def test_decimal_14_6_round_trip_is_exact(db_session: Session) -> None:
    _, _, FoodNutrientValue = _contract()
    _, _, value = _value(db_session, amount=Decimal("12345678.123456"))
    value_id = value.id
    db_session.expire_all()

    loaded = db_session.get(FoodNutrientValue, value_id)
    assert loaded is not None
    assert loaded.amount_per_100g == Decimal("12345678.123456")
    assert isinstance(loaded.amount_per_100g, Decimal)


@pytest.mark.parametrize("amount", [None, Decimal("0")])
def test_null_and_zero_amounts_are_distinct_and_accepted(
    db_session: Session,
    amount,
) -> None:
    _, _, FoodNutrientValue = _contract()
    _, _, value = _value(db_session, amount=amount)
    value_id = value.id
    db_session.expire_all()

    loaded = db_session.get(FoodNutrientValue, value_id)
    assert loaded is not None
    assert loaded.amount_per_100g == amount


def test_negative_amount_is_rejected(db_session: Session) -> None:
    with pytest.raises(IntegrityError):
        _value(db_session, amount=Decimal("-0.000001"))


def test_duplicate_nutrient_code_is_rejected(db_session: Session) -> None:
    NutrientUnit, _, _ = _contract()
    db_session.add_all(
        [
            _definition(code="PROTEIN", unit=NutrientUnit.GRAM),
            _definition(code="PROTEIN", unit=NutrientUnit.GRAM),
        ]
    )
    with pytest.raises(IntegrityError):
        db_session.flush()


@pytest.mark.parametrize("invalid_code", ["protein", " PROTEIN", "PROTEIN "])
def test_noncanonical_nutrient_code_is_rejected(
    db_session: Session,
    invalid_code: str,
) -> None:
    db_session.add(_definition(code=invalid_code))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_blank_nutrient_name_is_rejected(db_session: Session) -> None:
    db_session.add(_definition(name_en="   "))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_invalid_nutrient_unit_is_rejected(db_session: Session) -> None:
    db_session.add(_definition(unit="IU"))
    with pytest.raises((IntegrityError, StatementError)):
        db_session.flush()


def test_duplicate_nutrient_per_source_record_is_rejected(
    db_session: Session,
) -> None:
    _, _, FoodNutrientValue = _contract()
    _, _, record = _source_record(db_session)
    definition = _definition(code="SODIUM")
    db_session.add(definition)
    db_session.flush()
    db_session.add_all(
        [
            FoodNutrientValue(
                food_source_record_id=record.id,
                nutrient_definition_id=definition.id,
                amount_per_100g=Decimal("1"),
            ),
            FoodNutrientValue(
                food_source_record_id=record.id,
                nutrient_definition_id=definition.id,
                amount_per_100g=Decimal("2"),
            ),
        ]
    )
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_same_nutrient_is_allowed_for_different_source_records(
    db_session: Session,
) -> None:
    _, _, FoodNutrientValue = _contract()
    release = _release()
    _, _, first_record = _source_record(db_session, release=release)
    _, _, second_record = _source_record(db_session, release=release)
    definition = _definition(code="POTASSIUM")
    db_session.add(definition)
    db_session.flush()
    db_session.add_all(
        [
            FoodNutrientValue(
                food_source_record_id=first_record.id,
                nutrient_definition_id=definition.id,
                amount_per_100g=Decimal("100"),
            ),
            FoodNutrientValue(
                food_source_record_id=second_record.id,
                nutrient_definition_id=definition.id,
                amount_per_100g=Decimal("200"),
            ),
        ]
    )
    db_session.flush()


def test_source_record_delete_cascades_nutrient_values(
    db_session: Session,
) -> None:
    _, _, FoodNutrientValue = _contract()
    record, _, value = _value(db_session)
    value_id = value.id

    db_session.execute(
        sa.delete(FoodSourceRecord).where(FoodSourceRecord.id == record.id)
    )
    db_session.commit()
    remaining = db_session.scalar(
        sa.select(sa.func.count())
        .select_from(FoodNutrientValue)
        .where(FoodNutrientValue.id == value_id)
    )
    assert remaining == 0
    db_session.expire_all()
    assert db_session.get(FoodNutrientValue, value_id) is None


def test_definition_delete_is_restricted_when_values_exist(
    db_session: Session,
) -> None:
    _, NutrientDefinition, _ = _contract()
    _, definition, _ = _value(db_session)
    with pytest.raises(IntegrityError):
        db_session.execute(
            sa.delete(NutrientDefinition).where(
                NutrientDefinition.id == definition.id
            )
        )


def test_dataset_release_restrict_behavior_remains_compatible(
    db_session: Session,
) -> None:
    release, _, record = _source_record(db_session)
    _value(db_session, record=record)
    with pytest.raises(IntegrityError):
        db_session.execute(
            sa.delete(DatasetRelease).where(DatasetRelease.id == release.id)
        )


def test_legacy_food_nutrient_round_trip_remains_compatible(
    db_session: Session,
) -> None:
    food = _food("legacy nutrient")
    nutrient = FoodNutrient(
        food=food,
        reference_unit=NutrientReferenceUnit.GRAM,
        calories_kcal=Decimal("100"),
        protein_g=Decimal("5"),
        carbohydrate_g=Decimal("10"),
        fat_g=Decimal("4"),
        fiber_g=None,
    )
    db_session.add(nutrient)
    db_session.flush()
    assert food.nutrient_profile is nutrient
    assert nutrient.food is food
    assert nutrient.fiber_g is None


def test_nutrient_value_migration_downgrade_and_reupgrade(
    request: pytest.FixtureRequest,
) -> None:
    assert MIGRATION_PATH.is_file(), "0012 nutrient value migration is missing"
    postgres_engine: Engine = request.getfixturevalue("postgres_engine")
    config = Config(str(ALEMBIC_INI))
    try:
        with postgres_engine.begin() as connection:
            config.attributes["connection"] = connection
            command.downgrade(config, "0011_food_dataset_provenance")

        tables = set(sa.inspect(postgres_engine).get_table_names())
        assert "nutrient_definitions" not in tables
        assert "food_nutrient_values" not in tables
        assert "dataset_releases" in tables
        assert "food_source_records" in tables
    finally:
        with postgres_engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")

    with postgres_engine.connect() as connection:
        head = connection.scalar(sa.text("SELECT version_num FROM alembic_version"))
    assert head == CURRENT_HEAD
