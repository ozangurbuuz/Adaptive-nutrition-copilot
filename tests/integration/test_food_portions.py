import importlib
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.enums import (
    FoodCategory,
    MealItemUnit,
    NutrientReferenceUnit,
    NutrientUnit,
)
from app.models.food import (
    DatasetRelease,
    Food,
    FoodNutrient,
    FoodNutrientValue,
    FoodSourceRecord,
    NutrientDefinition,
)


pytestmark = pytest.mark.integration
EXPECTED_HEAD = "0013_food_portions"


def _model():
    module = importlib.import_module("app.models.food")
    food_portion = getattr(module, "FoodPortion", None)
    assert food_portion is not None, "FoodPortion model is missing"
    return food_portion


def _release() -> DatasetRelease:
    unique_value = uuid.uuid4().hex
    return DatasetRelease(
        source="USDA_FOUNDATION",
        release_version=f"portion-{unique_value}",
        downloaded_at=datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc),
        checksum_sha256=unique_value * 2,
        license_reference="USDA public-domain notice",
    )


def _food(name: str = "portion food") -> Food:
    return Food(
        name=f"{name} {uuid.uuid4().hex}",
        category=FoodCategory.OTHER,
        default_serving_quantity=Decimal("100"),
        default_serving_unit=MealItemUnit.GRAM,
    )


def _source_record(
    session: Session,
    *,
    release: DatasetRelease | None = None,
    food: Food | None = None,
) -> tuple[DatasetRelease, Food, FoodSourceRecord]:
    release = release or _release()
    food = food or _food()
    session.add_all([release, food])
    session.flush()
    record = FoodSourceRecord(
        food_id=food.id,
        dataset_release_id=release.id,
        source_food_id=f"FDC-{uuid.uuid4().hex}",
        canonical_name="Canonical portion source food",
        preparation_state="As Purchased",
    )
    session.add(record)
    session.flush()
    return release, food, record


def _portion(
    session: Session,
    *,
    record: FoodSourceRecord | None = None,
    source_portion_id: str | None = None,
    amount: Decimal = Decimal("1"),
    measure_code: str | None = "TABLESPOON",
    measure_name: str | None = "tablespoon",
    modifier: str | None = None,
    portion_description: str = "1 tablespoon",
    gram_weight: Decimal | None = Decimal("13.5"),
    sequence_number: int | None = 1,
):
    FoodPortion = _model()
    if record is None:
        _, _, record = _source_record(session)
    portion = FoodPortion(
        food_source_record_id=record.id,
        source_portion_id=source_portion_id or f"PORTION-{uuid.uuid4().hex}",
        amount=amount,
        measure_code=measure_code,
        measure_name=measure_name,
        modifier=modifier,
        portion_description=portion_description,
        gram_weight=gram_weight,
        sequence_number=sequence_number,
    )
    session.add(portion)
    session.flush()
    return record, portion


def test_food_portion_table_exists_at_expected_head(postgres_engine) -> None:
    tables = set(sa.inspect(postgres_engine).get_table_names())
    assert "food_portions" in tables
    with postgres_engine.connect() as connection:
        head = connection.scalar(sa.text("SELECT version_num FROM alembic_version"))
    assert head == EXPECTED_HEAD


@pytest.mark.parametrize(
    (
        "measure_code",
        "measure_name",
        "modifier",
        "description",
        "gram_weight",
    ),
    [
        (
            "TABLESPOON",
            "tablespoon",
            None,
            "1 tablespoon",
            Decimal("13.500000"),
        ),
        ("CUP", "cup", None, "1 cup", Decimal("240.000000")),
        ("PIECE", "piece", "medium", "1 medium banana", Decimal("118.000000")),
    ],
)
def test_example_food_portions_round_trip(
    db_session: Session,
    measure_code: str,
    measure_name: str,
    modifier: str | None,
    description: str,
    gram_weight: Decimal,
) -> None:
    FoodPortion = _model()
    _, portion = _portion(
        db_session,
        measure_code=measure_code,
        measure_name=measure_name,
        modifier=modifier,
        portion_description=description,
        gram_weight=gram_weight,
    )
    portion_id = portion.id
    db_session.expire_all()

    loaded = db_session.get(FoodPortion, portion_id)
    assert loaded is not None
    assert loaded.amount == Decimal("1.000000")
    assert loaded.measure_code == measure_code
    assert loaded.measure_name == measure_name
    assert loaded.modifier == modifier
    assert loaded.portion_description == description
    assert loaded.gram_weight == gram_weight
    assert loaded.food_source_record.preparation_state == "As Purchased"


def test_decimal_amount_and_gram_weight_round_trip_exactly(
    db_session: Session,
) -> None:
    FoodPortion = _model()
    _, portion = _portion(
        db_session,
        amount=Decimal("0.500000"),
        portion_description="0.5 cup",
        gram_weight=Decimal("13.500000"),
    )
    portion_id = portion.id
    db_session.expire_all()

    loaded = db_session.get(FoodPortion, portion_id)
    assert loaded is not None
    assert loaded.amount == Decimal("0.500000")
    assert isinstance(loaded.amount, Decimal)
    assert loaded.gram_weight == Decimal("13.500000")
    assert isinstance(loaded.gram_weight, Decimal)


@pytest.mark.parametrize("amount", [Decimal("0"), Decimal("-0.000001")])
def test_non_positive_amount_is_rejected(
    db_session: Session,
    amount: Decimal,
) -> None:
    with pytest.raises(IntegrityError):
        _portion(db_session, amount=amount)


def test_null_gram_weight_is_accepted(db_session: Session) -> None:
    FoodPortion = _model()
    _, portion = _portion(db_session, gram_weight=None)
    portion_id = portion.id
    db_session.expire_all()
    loaded = db_session.get(FoodPortion, portion_id)
    assert loaded is not None
    assert loaded.gram_weight is None


@pytest.mark.parametrize("gram_weight", [Decimal("0"), Decimal("-0.000001")])
def test_non_positive_gram_weight_is_rejected(
    db_session: Session,
    gram_weight: Decimal,
) -> None:
    with pytest.raises(IntegrityError):
        _portion(db_session, gram_weight=gram_weight)


@pytest.mark.parametrize("description", ["", "   "])
def test_blank_portion_description_is_rejected(
    db_session: Session,
    description: str,
) -> None:
    with pytest.raises(IntegrityError):
        _portion(db_session, portion_description=description)


@pytest.mark.parametrize("source_portion_id", ["", "   "])
def test_non_null_blank_source_portion_id_is_rejected(
    db_session: Session,
    source_portion_id: str,
) -> None:
    FoodPortion = _model()
    _, _, record = _source_record(db_session)
    db_session.add(
        FoodPortion(
            food_source_record_id=record.id,
            source_portion_id=source_portion_id,
            amount=Decimal("1"),
            portion_description="1 portion",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.flush()


@pytest.mark.parametrize(
    "measure_code",
    ["", "   ", "tablespoon", " TABLESPOON", "TABLESPOON "],
)
def test_invalid_measure_code_is_rejected(
    db_session: Session,
    measure_code: str,
) -> None:
    with pytest.raises(IntegrityError):
        _portion(db_session, measure_code=measure_code)


@pytest.mark.parametrize("measure_name", ["", "   "])
def test_non_null_blank_measure_name_is_rejected(
    db_session: Session,
    measure_name: str,
) -> None:
    with pytest.raises(IntegrityError):
        _portion(db_session, measure_name=measure_name)


@pytest.mark.parametrize("modifier", ["", "   "])
def test_non_null_blank_modifier_is_rejected(
    db_session: Session,
    modifier: str,
) -> None:
    with pytest.raises(IntegrityError):
        _portion(db_session, modifier=modifier)


@pytest.mark.parametrize("sequence_number", [0, -1])
def test_non_positive_sequence_number_is_rejected(
    db_session: Session,
    sequence_number: int,
) -> None:
    with pytest.raises(IntegrityError):
        _portion(db_session, sequence_number=sequence_number)


def test_duplicate_source_portion_id_in_source_record_is_rejected(
    db_session: Session,
) -> None:
    FoodPortion = _model()
    _, _, record = _source_record(db_session)
    db_session.add_all(
        [
            FoodPortion(
                food_source_record_id=record.id,
                source_portion_id="SHARED-PORTION",
                amount=Decimal("1"),
                portion_description="First portion",
                sequence_number=1,
            ),
            FoodPortion(
                food_source_record_id=record.id,
                source_portion_id="SHARED-PORTION",
                amount=Decimal("2"),
                portion_description="Second portion",
                sequence_number=2,
            ),
        ]
    )
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_duplicate_sequence_number_in_source_record_is_rejected(
    db_session: Session,
) -> None:
    FoodPortion = _model()
    _, _, record = _source_record(db_session)
    db_session.add_all(
        [
            FoodPortion(
                food_source_record_id=record.id,
                source_portion_id="FIRST",
                amount=Decimal("1"),
                portion_description="First portion",
                sequence_number=1,
            ),
            FoodPortion(
                food_source_record_id=record.id,
                source_portion_id="SECOND",
                amount=Decimal("2"),
                portion_description="Second portion",
                sequence_number=1,
            ),
        ]
    )
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_multiple_null_source_ids_and_sequences_are_accepted(
    db_session: Session,
) -> None:
    FoodPortion = _model()
    _, _, record = _source_record(db_session)
    db_session.add_all(
        [
            FoodPortion(
                food_source_record_id=record.id,
                source_portion_id=None,
                amount=Decimal("1"),
                portion_description="First unnumbered portion",
                sequence_number=None,
            ),
            FoodPortion(
                food_source_record_id=record.id,
                source_portion_id=None,
                amount=Decimal("2"),
                portion_description="Second unnumbered portion",
                sequence_number=None,
            ),
        ]
    )
    db_session.flush()


def test_same_source_portion_id_is_allowed_for_different_source_records(
    db_session: Session,
) -> None:
    FoodPortion = _model()
    release = _release()
    _, _, first_record = _source_record(db_session, release=release)
    _, _, second_record = _source_record(db_session, release=release)
    db_session.add_all(
        [
            FoodPortion(
                food_source_record_id=first_record.id,
                source_portion_id="SHARED",
                amount=Decimal("1"),
                portion_description="First source",
            ),
            FoodPortion(
                food_source_record_id=second_record.id,
                source_portion_id="SHARED",
                amount=Decimal("1"),
                portion_description="Second source",
            ),
        ]
    )
    db_session.flush()


def test_same_measure_code_can_have_different_food_specific_gram_weights(
    db_session: Session,
) -> None:
    FoodPortion = _model()
    _, _, oil_record = _source_record(db_session, food=_food("olive oil"))
    _, _, flour_record = _source_record(db_session, food=_food("flour"))
    oil = FoodPortion(
        food_source_record_id=oil_record.id,
        amount=Decimal("1"),
        measure_code="TABLESPOON",
        portion_description="1 tablespoon olive oil",
        gram_weight=Decimal("13.5"),
    )
    flour = FoodPortion(
        food_source_record_id=flour_record.id,
        amount=Decimal("1"),
        measure_code="TABLESPOON",
        portion_description="1 tablespoon flour",
        gram_weight=Decimal("7.8"),
    )
    db_session.add_all([oil, flour])
    db_session.flush()
    assert oil.gram_weight != flour.gram_weight


def test_source_record_delete_cascades_food_portions(
    db_session: Session,
) -> None:
    FoodPortion = _model()
    record, portion = _portion(db_session)
    portion_id = portion.id
    db_session.execute(
        sa.delete(FoodSourceRecord).where(FoodSourceRecord.id == record.id)
    )
    db_session.commit()

    remaining = db_session.scalar(
        sa.select(sa.func.count())
        .select_from(FoodPortion)
        .where(FoodPortion.id == portion_id)
    )
    assert remaining == 0
    db_session.expire_all()
    assert db_session.get(FoodPortion, portion_id) is None


def test_food_delete_cascades_through_source_record_to_portions(
    db_session: Session,
) -> None:
    FoodPortion = _model()
    _, food, record = _source_record(db_session)
    _, portion = _portion(db_session, record=record)
    portion_id = portion.id
    db_session.execute(sa.delete(Food).where(Food.id == food.id))
    db_session.commit()

    remaining = db_session.scalar(
        sa.select(sa.func.count())
        .select_from(FoodPortion)
        .where(FoodPortion.id == portion_id)
    )
    assert remaining == 0
    db_session.expire_all()
    assert db_session.get(FoodPortion, portion_id) is None


def test_dataset_release_delete_remains_restricted(
    db_session: Session,
) -> None:
    release, _, record = _source_record(db_session)
    _portion(db_session, record=record)
    with pytest.raises(IntegrityError):
        db_session.execute(
            sa.delete(DatasetRelease).where(DatasetRelease.id == release.id)
        )


def test_food_nutrient_values_are_unaffected_by_portions(
    db_session: Session,
) -> None:
    _, _, record = _source_record(db_session)
    _portion(db_session, record=record)
    definition = NutrientDefinition(
        code=f"PORTION_PROTEIN_{uuid.uuid4().hex.upper()}",
        name_en="Protein",
        unit=NutrientUnit.GRAM,
    )
    db_session.add(definition)
    db_session.flush()
    nutrient_value = FoodNutrientValue(
        food_source_record_id=record.id,
        nutrient_definition_id=definition.id,
        amount_per_100g=Decimal("3.250000"),
    )
    db_session.add(nutrient_value)
    db_session.flush()
    assert nutrient_value.amount_per_100g == Decimal("3.250000")


def test_legacy_food_nutrient_behavior_remains_compatible(
    db_session: Session,
) -> None:
    food = _food("legacy portion compatibility")
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
    assert nutrient.reference_quantity == Decimal("100")
    assert nutrient.fiber_g is None
