import importlib
import subprocess
import sys
import uuid
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID


# Eksik production sınıflarını collection error yerine anlaşılır RED failure yapar.
def _models():
    module = importlib.import_module("app.models.food")
    dataset_release = getattr(module, "DatasetRelease", None)
    source_record = getattr(module, "FoodSourceRecord", None)
    assert dataset_release is not None, "DatasetRelease model is missing"
    assert source_record is not None, "FoodSourceRecord model is missing"
    return dataset_release, source_record


# İki provenance tablosunun mevcut UUID ve timestamp convention'larını kullanmasını sınar.
def test_provenance_table_names_columns_types_and_mixins() -> None:
    from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

    DatasetRelease, FoodSourceRecord = _models()

    assert DatasetRelease.__tablename__ == "dataset_releases"
    assert FoodSourceRecord.__tablename__ == "food_source_records"
    for model in (DatasetRelease, FoodSourceRecord):
        assert issubclass(model, UUIDPrimaryKeyMixin)
        assert issubclass(model, TimestampMixin)
        assert isinstance(model.__table__.c.id.type, UUID)
        assert model.__table__.c.id.primary_key is True
        assert model.__table__.c.id.default is not None
        assert model.__table__.c.id.server_default is None
        assert isinstance(model.__table__.c.created_at.type, DateTime)
        assert model.__table__.c.created_at.type.timezone is True
        assert model.__table__.c.created_at.nullable is False
        assert model.__table__.c.created_at.default is not None
        assert model.__table__.c.created_at.server_default is None
        assert isinstance(model.__table__.c.updated_at.type, DateTime)
        assert model.__table__.c.updated_at.type.timezone is True
        assert model.__table__.c.updated_at.nullable is False
        assert model.__table__.c.updated_at.default is not None
        assert model.__table__.c.updated_at.onupdate is not None
        assert model.__table__.c.updated_at.server_default is None

    release = DatasetRelease.__table__
    assert set(release.columns.keys()) == {
        "id",
        "source",
        "release_version",
        "downloaded_at",
        "imported_at",
        "checksum_sha256",
        "license_reference",
        "created_at",
        "updated_at",
    }
    for name, length, nullable in (
        ("source", 50, False),
        ("release_version", 100, False),
        ("checksum_sha256", 64, False),
        ("license_reference", 500, False),
    ):
        column = release.c[name]
        assert isinstance(column.type, String)
        assert column.type.length == length
        assert column.nullable is nullable
    assert isinstance(release.c.downloaded_at.type, DateTime)
    assert release.c.downloaded_at.type.timezone is True
    assert release.c.downloaded_at.nullable is False
    assert isinstance(release.c.imported_at.type, DateTime)
    assert release.c.imported_at.type.timezone is True
    assert release.c.imported_at.nullable is True
    for field_name in (
        "source",
        "release_version",
        "downloaded_at",
        "imported_at",
        "checksum_sha256",
        "license_reference",
    ):
        assert release.c[field_name].default is None
        assert release.c[field_name].server_default is None

    source_record = FoodSourceRecord.__table__
    assert set(source_record.columns.keys()) == {
        "id",
        "food_id",
        "dataset_release_id",
        "source_food_id",
        "canonical_name",
        "preparation_state",
        "created_at",
        "updated_at",
    }
    for name, length, nullable in (
        ("source_food_id", 100, False),
        ("canonical_name", 255, False),
        ("preparation_state", 100, True),
    ):
        column = source_record.c[name]
        assert isinstance(column.type, String)
        assert column.type.length == length
        assert column.nullable is nullable
        assert column.default is None
        assert column.server_default is None


# Composite unique ve nonblank/checksum check constraint adlarını kesinleştirir.
def test_provenance_unique_and_check_constraints() -> None:
    DatasetRelease, FoodSourceRecord = _models()

    release_constraints = {
        constraint.name: constraint
        for constraint in DatasetRelease.__table__.constraints
    }
    assert isinstance(
        release_constraints["uq_dataset_releases_source_release_version"],
        UniqueConstraint,
    )
    assert [
        column.name
        for column in release_constraints[
            "uq_dataset_releases_source_release_version"
        ].columns
    ] == ["source", "release_version"]
    assert isinstance(
        release_constraints["uq_dataset_releases_source_checksum_sha256"],
        UniqueConstraint,
    )
    assert [
        column.name
        for column in release_constraints[
            "uq_dataset_releases_source_checksum_sha256"
        ].columns
    ] == ["source", "checksum_sha256"]
    assert {
        "ck_dataset_releases_source_nonblank",
        "ck_dataset_releases_release_version_nonblank",
        "ck_dataset_releases_checksum_sha256_length",
        "ck_dataset_releases_license_reference_nonblank",
    }.issubset(
        name
        for name, constraint in release_constraints.items()
        if isinstance(constraint, CheckConstraint)
    )

    source_constraints = {
        constraint.name: constraint
        for constraint in FoodSourceRecord.__table__.constraints
    }
    unique = source_constraints[
        "uq_food_source_records_dataset_release_id_source_food_id"
    ]
    assert isinstance(unique, UniqueConstraint)
    assert [column.name for column in unique.columns] == [
        "dataset_release_id",
        "source_food_id",
    ]
    assert {
        "ck_food_source_records_source_food_id_nonblank",
        "ck_food_source_records_canonical_name_nonblank",
        "ck_food_source_records_preparation_state_nonblank",
    }.issubset(
        name
        for name, constraint in source_constraints.items()
        if isinstance(constraint, CheckConstraint)
    )

    # FK sorgulari ile source kimligi aramalarinin model metadata'sinda da indeksli olmasini bekler.
    assert {index.name for index in FoodSourceRecord.__table__.indexes} == {
        "ix_food_source_records_food_id",
        "ix_food_source_records_source_food_id",
    }


# FK hedeflerini ve Food CASCADE / DatasetRelease RESTRICT davranışını doğrular.
def test_food_source_record_foreign_keys_are_named_and_directional() -> None:
    _, FoodSourceRecord = _models()

    for column_name, target, constraint_name, ondelete in (
        (
            "food_id",
            "foods.id",
            "fk_food_source_records_food_id_foods",
            "CASCADE",
        ),
        (
            "dataset_release_id",
            "dataset_releases.id",
            "fk_food_source_records_dataset_release_id_dataset_releases",
            "RESTRICT",
        ),
    ):
        column = FoodSourceRecord.__table__.c[column_name]
        foreign_keys = list(column.foreign_keys)
        assert isinstance(column.type, UUID)
        assert column.nullable is False
        assert len(foreign_keys) == 1
        assert foreign_keys[0].target_fullname == target
        assert foreign_keys[0].constraint.name == constraint_name
        assert foreign_keys[0].ondelete == ondelete


# Dört yönlü back_populates sözleşmesini ve parent delete convention'larını sabitler.
def test_provenance_relationships_match_food_and_release_ownership() -> None:
    from app.models.food import Food

    DatasetRelease, FoodSourceRecord = _models()

    release_records = DatasetRelease.__mapper__.relationships[
        "food_source_records"
    ]
    record_release = FoodSourceRecord.__mapper__.relationships["dataset_release"]
    assert release_records.mapper.class_ is FoodSourceRecord
    assert release_records.uselist is True
    assert release_records.back_populates == "dataset_release"
    assert "delete" not in release_records.cascade
    assert release_records.passive_deletes == "all"
    assert record_release.mapper.class_ is DatasetRelease
    assert record_release.back_populates == "food_source_records"

    food_records = Food.__mapper__.relationships["source_records"]
    record_food = FoodSourceRecord.__mapper__.relationships["food"]
    assert food_records.mapper.class_ is FoodSourceRecord
    assert food_records.uselist is True
    assert food_records.back_populates == "food"
    assert "delete" in food_records.cascade
    assert "delete-orphan" in food_records.cascade
    assert food_records.passive_deletes is True
    assert food_records.single_parent is True
    assert record_food.mapper.class_ is Food
    assert record_food.back_populates == "source_records"


# Source kimlikleri ile canonical kaynak metninin normalize edilmeden korunmasını bekler.
def test_provenance_constructors_preserve_source_identity_and_nullable_import() -> None:
    DatasetRelease, FoodSourceRecord = _models()
    downloaded_at = datetime(2026, 8, 28, 10, 30, tzinfo=timezone.utc)
    release = DatasetRelease(
        source="USDA_FOUNDATION",
        release_version="Foundation_2026-04",
        downloaded_at=downloaded_at,
        imported_at=None,
        checksum_sha256="A" * 64,
        license_reference="USDA public-domain notice",
    )
    source_record = FoodSourceRecord(
        food_id=uuid.uuid4(),
        dataset_release_id=uuid.uuid4(),
        source_food_id="FDC_001AbC",
        canonical_name="Milk, whole, 3.25% milkfat",
        preparation_state="As Purchased",
    )

    assert release.source == "USDA_FOUNDATION"
    assert release.release_version == "Foundation_2026-04"
    assert release.imported_at is None
    assert source_record.source_food_id == "FDC_001AbC"
    assert source_record.canonical_name == "Milk, whole, 3.25% milkfat"
    assert source_record.preparation_state == "As Purchased"


# Yeni tablolar eklenirken mevcut Food ve FoodNutrient kolon sözleşmesini korur.
def test_existing_food_and_food_nutrient_columns_remain_unchanged() -> None:
    from app.models.food import Food, FoodNutrient

    _models()
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


# Model importu ve constructor kullanımı sırasında bağlantı/flush/commit yapılmasını engeller.
def test_provenance_model_import_and_construction_do_not_use_database() -> None:
    script = """
import psycopg
import sqlalchemy
from datetime import datetime, timezone

def fail_if_database_is_used(*args, **kwargs):
    raise AssertionError("Provenance model construction must not use the database")

sqlalchemy.create_engine = fail_if_database_is_used
psycopg.connect = fail_if_database_is_used

from app.models.food import DatasetRelease, FoodSourceRecord

release = DatasetRelease(
    source="USDA_FOUNDATION",
    release_version="2026-04",
    downloaded_at=datetime.now(timezone.utc),
    checksum_sha256="a" * 64,
    license_reference="USDA public-domain notice",
)
record = FoodSourceRecord(
    source_food_id="123",
    canonical_name="Source Name",
)
assert release.source == "USDA_FOUNDATION"
assert record.source_food_id == "123"
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
