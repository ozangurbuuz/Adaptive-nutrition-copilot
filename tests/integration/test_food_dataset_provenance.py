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
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.enums import FoodCategory, MealItemUnit, NutrientReferenceUnit
from app.models.food import Food, FoodNutrient


pytestmark = pytest.mark.integration

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_INI = PROJECT_ROOT / "backend" / "alembic.ini"
CURRENT_HEAD = "0013_food_portions"


# Eksik production siniflarini collection error yerine okunabilir RED failure'a cevirir.
def _models():
    module = importlib.import_module("app.models.food")
    dataset_release = getattr(module, "DatasetRelease", None)
    source_record = getattr(module, "FoodSourceRecord", None)
    assert dataset_release is not None, "DatasetRelease model is missing"
    assert source_record is not None, "FoodSourceRecord model is missing"
    return dataset_release, source_record


# Her test icin cakismayan fakat gercekci bir dataset release nesnesi uretir.
def _release(
    *,
    source: str = "USDA_FOUNDATION",
    release_version: str | None = None,
    checksum_sha256: str | None = None,
):
    DatasetRelease, _ = _models()
    unique_value = uuid.uuid4().hex
    return DatasetRelease(
        source=source,
        release_version=release_version or f"2026-04-{unique_value}",
        downloaded_at=datetime(2026, 8, 28, 10, 30, tzinfo=timezone.utc),
        imported_at=None,
        checksum_sha256=checksum_sha256 or (unique_value * 2),
        license_reference="USDA public-domain notice",
    )


# Mevcut Food kontratini kullanarak provenance kaydinin baglanacagi parent'i olusturur.
def _food(name: str = "provenance food") -> Food:
    return Food(
        name=f"{name} {uuid.uuid4()}",
        category=FoodCategory.OTHER,
        default_serving_quantity=Decimal("100"),
        default_serving_unit=MealItemUnit.GRAM,
    )


# Parent nesneleri flush edip bir source record'u tutarli foreign key'lerle ekler.
def _source_record(
    session: Session,
    *,
    release=None,
    food: Food | None = None,
    source_food_id: str | None = None,
    canonical_name: str = "Milk, whole, 3.25% milkfat",
    preparation_state: str | None = "As Purchased",
):
    _, FoodSourceRecord = _models()
    release = release or _release()
    food = food or _food()
    session.add_all([release, food])
    session.flush()
    record = FoodSourceRecord(
        food_id=food.id,
        dataset_release_id=release.id,
        source_food_id=source_food_id or f"FDC-{uuid.uuid4().hex}",
        canonical_name=canonical_name,
        preparation_state=preparation_state,
    )
    session.add(record)
    session.flush()
    return release, food, record


# Iki yeni tablonun iliskileriyle birlikte PostgreSQL round-trip yapabildigini sinar.
def test_provenance_round_trip_preserves_source_identity(db_session: Session) -> None:
    DatasetRelease, FoodSourceRecord = _models()
    release, food, record = _source_record(db_session, source_food_id="FDC_001AbC")
    release_id = release.id
    record_id = record.id
    db_session.expire_all()

    loaded_release = db_session.get(DatasetRelease, release_id)
    loaded_record = db_session.get(FoodSourceRecord, record_id)

    assert loaded_release is not None
    assert loaded_release.imported_at is None
    assert loaded_release.created_at is not None
    assert loaded_release.updated_at is not None
    assert [item.id for item in loaded_release.food_source_records] == [record_id]
    assert loaded_record is not None
    assert loaded_record.source_food_id == "FDC_001AbC"
    assert loaded_record.canonical_name == "Milk, whole, 3.25% milkfat"
    assert loaded_record.preparation_state == "As Purchased"
    assert loaded_record.dataset_release.id == release_id
    assert loaded_record.food.id == food.id
    assert [item.id for item in loaded_record.food.source_records] == [record_id]


# Ayni source ve release_version ikilisinin iki kez kaydedilememesini dogrular.
def test_duplicate_source_release_version_is_rejected(db_session: Session) -> None:
    version = f"release-{uuid.uuid4().hex}"
    db_session.add_all(
        [
            _release(release_version=version),
            _release(release_version=version),
        ]
    )

    with pytest.raises(IntegrityError):
        db_session.flush()


# Ayni source icin ayni checksum'in farkli release adiyla tekrarini da engeller.
def test_duplicate_source_checksum_is_rejected(db_session: Session) -> None:
    checksum = uuid.uuid4().hex * 2
    db_session.add_all(
        [
            _release(release_version="first", checksum_sha256=checksum),
            _release(release_version="second", checksum_sha256=checksum),
        ]
    )

    with pytest.raises(IntegrityError):
        db_session.flush()


# Bir release icinde source_food_id tekil olmali; ayni kimlik baska release'te kullanilabilir.
def test_source_food_id_is_unique_per_release(db_session: Session) -> None:
    _, FoodSourceRecord = _models()
    release = _release()
    first_food = _food("first source")
    second_food = _food("second source")
    db_session.add_all([release, first_food, second_food])
    db_session.flush()
    db_session.add_all(
        [
            FoodSourceRecord(
                food_id=first_food.id,
                dataset_release_id=release.id,
                source_food_id="shared-id",
                canonical_name="First",
            ),
            FoodSourceRecord(
                food_id=second_food.id,
                dataset_release_id=release.id,
                source_food_id="shared-id",
                canonical_name="Second",
            ),
        ]
    )

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_same_source_food_id_is_allowed_in_different_releases(
    db_session: Session,
) -> None:
    _, FoodSourceRecord = _models()
    first_release = _release(release_version="first")
    second_release = _release(release_version="second")
    food = _food("shared source")
    db_session.add_all([first_release, second_release, food])
    db_session.flush()
    db_session.add_all(
        [
            FoodSourceRecord(
                food_id=food.id,
                dataset_release_id=first_release.id,
                source_food_id="shared-id",
                canonical_name="First release name",
            ),
            FoodSourceRecord(
                food_id=food.id,
                dataset_release_id=second_release.id,
                source_food_id="shared-id",
                canonical_name="Second release name",
            ),
        ]
    )

    db_session.flush()


# Dataset release string ve checksum check constraint'lerini gercek PostgreSQL'de zorlar.
@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("source", "   "),
        ("release_version", "   "),
        ("checksum_sha256", "a" * 63),
        ("license_reference", "   "),
    ],
)
def test_invalid_dataset_release_values_are_rejected(
    db_session: Session,
    field_name: str,
    invalid_value: str,
) -> None:
    release = _release()
    setattr(release, field_name, invalid_value)
    db_session.add(release)

    with pytest.raises(IntegrityError):
        db_session.flush()


# Source record metinlerinde bos string'i reddeder, nullable preparation_state'i korur.
@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("source_food_id", "   "),
        ("canonical_name", "   "),
        ("preparation_state", "   "),
    ],
)
def test_invalid_food_source_record_values_are_rejected(
    db_session: Session,
    field_name: str,
    invalid_value: str,
) -> None:
    _, FoodSourceRecord = _models()
    release = _release()
    food = _food("invalid record")
    db_session.add_all([release, food])
    db_session.flush()
    values = {
        "food_id": food.id,
        "dataset_release_id": release.id,
        "source_food_id": "valid-id",
        "canonical_name": "Valid canonical name",
        "preparation_state": None,
    }
    values[field_name] = invalid_value
    db_session.add(FoodSourceRecord(**values))

    with pytest.raises(IntegrityError):
        db_session.flush()


# preparation_state verilmemesinin check constraint tarafindan kabul edilmesini dogrular.
def test_nullable_preparation_state_is_accepted(db_session: Session) -> None:
    _, _, record = _source_record(db_session, preparation_state=None)
    assert record.preparation_state is None


# Release silme RESTRICT olmali; kaynak dataset'i varken provenance kaydi yetim kalamaz.
def test_dataset_release_delete_is_restricted(db_session: Session) -> None:
    DatasetRelease, _ = _models()
    release, _, _ = _source_record(db_session)

    with pytest.raises(IntegrityError):
        db_session.execute(
            sa.delete(DatasetRelease).where(DatasetRelease.id == release.id)
        )


# Food silme source record'u DB CASCADE ile kaldirir.
def test_food_delete_cascades_to_source_records(db_session: Session) -> None:
    _, FoodSourceRecord = _models()
    _, food, record = _source_record(db_session)
    record_id = record.id

    db_session.execute(sa.delete(Food).where(Food.id == food.id))
    db_session.commit()

    remaining_records = db_session.scalar(
        sa.select(sa.func.count())
        .select_from(FoodSourceRecord)
        .where(FoodSourceRecord.id == record_id)
    )
    assert remaining_records == 0
    db_session.expire_all()
    assert db_session.get(FoodSourceRecord, record_id) is None


# Provenance eklenmesi mevcut Food/FoodNutrient bire-bir kontratini bozmamali.
def test_existing_food_nutrient_round_trip_remains_compatible(
    db_session: Session,
) -> None:
    food = _food("nutrient compatibility")
    nutrient = FoodNutrient(
        food=food,
        reference_unit=NutrientReferenceUnit.GRAM,
        calories_kcal=Decimal("120"),
        protein_g=Decimal("4"),
        carbohydrate_g=Decimal("24"),
        fat_g=Decimal("2"),
    )
    db_session.add(nutrient)
    db_session.flush()

    assert food.nutrient_profile is nutrient
    assert nutrient.food is food


# Migration'in 0010'a geri donup iki tabloyu kaldirdigini ve tekrar head'e cikabildigini sinar.
def test_provenance_migration_downgrade_and_reupgrade(
    postgres_engine: Engine,
) -> None:
    config = Config(str(ALEMBIC_INI))
    try:
        with postgres_engine.begin() as connection:
            config.attributes["connection"] = connection
            command.downgrade(config, "0010_add_meal_item_sort_order")

        inspector = sa.inspect(postgres_engine)
        assert "dataset_releases" not in inspector.get_table_names()
        assert "food_source_records" not in inspector.get_table_names()
    finally:
        with postgres_engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")

    with postgres_engine.connect() as connection:
        head = connection.scalar(sa.text("SELECT version_num FROM alembic_version"))
    assert head == CURRENT_HEAD
