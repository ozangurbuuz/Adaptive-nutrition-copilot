import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
    text,
    true,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.models import plan_structure as _plan_structure  # noqa: F401
from app.models.base import Base
from app.models.enums import (
    FoodCategory,
    MealItemUnit,
    NutrientReferenceUnit,
    NutrientUnit,
)
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.plan_structure import MealItem


class Food(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "foods"
    __table_args__ = (
        CheckConstraint(
            "default_serving_quantity IS NULL OR default_serving_quantity > 0",
            name="ck_foods_default_serving_quantity_positive",
        ),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[FoodCategory] = mapped_column(
        Enum(
            FoodCategory,
            name="food_category",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
    )
    default_serving_quantity: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 3),
        nullable=True,
    )
    # Plan satırlarıyla aynı kontrollü birimler kullanılır.
    default_serving_unit: Mapped[MealItemUnit | None] = mapped_column(
        Enum(
            MealItemUnit,
            name="food_default_serving_unit",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default=true(),
        nullable=False,
    )

    # Besin değerleri katalog kaydının bağımsız yaşam döngüsü olmayan parçasıdır.
    nutrient_profile: Mapped["FoodNutrient | None"] = relationship(
        back_populates="food",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
        single_parent=True,
    )
    # Geçmiş plan satırları katalog kaydı silinerek veya ayrıştırılarak değiştirilmez.
    meal_items: Mapped[list["MealItem"]] = relationship(
        back_populates="food",
        passive_deletes="all",
    )
    source_records: Mapped[list["FoodSourceRecord"]] = relationship(
        back_populates="food",
        cascade="all, delete-orphan",
        passive_deletes=True,
        single_parent=True,
    )

    @validates("name")
    def normalize_name(self, key: str, value: str) -> str:
        return value.strip().casefold()


class FoodNutrient(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "food_nutrients"
    __table_args__ = (
        UniqueConstraint("food_id", name="uq_food_nutrients_food_id"),
        CheckConstraint(
            "reference_quantity > 0",
            name="ck_food_nutrients_reference_quantity_positive",
        ),
        CheckConstraint(
            "calories_kcal >= 0",
            name="ck_food_nutrients_calories_kcal_non_negative",
        ),
        CheckConstraint(
            "protein_g >= 0",
            name="ck_food_nutrients_protein_g_non_negative",
        ),
        CheckConstraint(
            "carbohydrate_g >= 0",
            name="ck_food_nutrients_carbohydrate_g_non_negative",
        ),
        CheckConstraint(
            "fat_g >= 0",
            name="ck_food_nutrients_fat_g_non_negative",
        ),
        CheckConstraint(
            "fiber_g IS NULL OR fiber_g >= 0",
            name="ck_food_nutrients_fiber_g_non_negative",
        ),
    )

    food_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "foods.id",
            name="fk_food_nutrients_food_id_foods",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    reference_quantity: Mapped[Decimal] = mapped_column(
        Numeric(10, 3),
        default=Decimal("100"),
        server_default=text("100"),
        nullable=False,
    )
    reference_unit: Mapped[NutrientReferenceUnit] = mapped_column(
        Enum(
            NutrientReferenceUnit,
            name="nutrient_reference_unit",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
    )
    calories_kcal: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    protein_g: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    carbohydrate_g: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    fat_g: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    # Bilinmeyen lif değeri sıfır kabul edilmez; NULL olarak korunur.
    fiber_g: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), nullable=True)

    food: Mapped[Food] = relationship(back_populates="nutrient_profile")


class DatasetRelease(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "dataset_releases"
    __table_args__ = (
        UniqueConstraint(
            "source",
            "release_version",
            name="uq_dataset_releases_source_release_version",
        ),
        UniqueConstraint(
            "source",
            "checksum_sha256",
            name="uq_dataset_releases_source_checksum_sha256",
        ),
        CheckConstraint(
            "length(btrim(source)) > 0",
            name="ck_dataset_releases_source_nonblank",
        ),
        CheckConstraint(
            "length(btrim(release_version)) > 0",
            name="ck_dataset_releases_release_version_nonblank",
        ),
        CheckConstraint(
            "length(checksum_sha256) = 64",
            name="ck_dataset_releases_checksum_sha256_length",
        ),
        CheckConstraint(
            "length(btrim(license_reference)) > 0",
            name="ck_dataset_releases_license_reference_nonblank",
        ),
    )

    source: Mapped[str] = mapped_column(String(50), nullable=False)
    release_version: Mapped[str] = mapped_column(String(100), nullable=False)
    downloaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    imported_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    license_reference: Mapped[str] = mapped_column(String(500), nullable=False)

    food_source_records: Mapped[list["FoodSourceRecord"]] = relationship(
        back_populates="dataset_release",
        passive_deletes="all",
    )


class FoodSourceRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "food_source_records"
    __table_args__ = (
        UniqueConstraint(
            "dataset_release_id",
            "source_food_id",
            name="uq_food_source_records_dataset_release_id_source_food_id",
        ),
        CheckConstraint(
            "length(btrim(source_food_id)) > 0",
            name="ck_food_source_records_source_food_id_nonblank",
        ),
        CheckConstraint(
            "length(btrim(canonical_name)) > 0",
            name="ck_food_source_records_canonical_name_nonblank",
        ),
        CheckConstraint(
            "preparation_state IS NULL OR length(btrim(preparation_state)) > 0",
            name="ck_food_source_records_preparation_state_nonblank",
        ),
    )

    food_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "foods.id",
            name="fk_food_source_records_food_id_foods",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    dataset_release_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "dataset_releases.id",
            name="fk_food_source_records_dataset_release_id_dataset_releases",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    source_food_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    canonical_name: Mapped[str] = mapped_column(String(255), nullable=False)
    preparation_state: Mapped[str | None] = mapped_column(String(100), nullable=True)

    food: Mapped[Food] = relationship(back_populates="source_records")
    dataset_release: Mapped[DatasetRelease] = relationship(
        back_populates="food_source_records"
    )
    nutrient_values: Mapped[list["FoodNutrientValue"]] = relationship(
        back_populates="food_source_record",
        cascade="all, delete-orphan",
        passive_deletes=True,
        single_parent=True,
    )


class NutrientDefinition(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "nutrient_definitions"
    __table_args__ = (
        UniqueConstraint("code", name="uq_nutrient_definitions_code"),
        CheckConstraint(
            "length(btrim(code)) > 0",
            name="ck_nutrient_definitions_code_nonblank",
        ),
        CheckConstraint(
            "code = upper(btrim(code))",
            name="ck_nutrient_definitions_code_canonical",
        ),
        CheckConstraint(
            "length(btrim(name_en)) > 0",
            name="ck_nutrient_definitions_name_en_nonblank",
        ),
    )

    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name_en: Mapped[str] = mapped_column(String(100), nullable=False)
    unit: Mapped[NutrientUnit] = mapped_column(
        Enum(
            NutrientUnit,
            name="nutrient_unit",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
    )

    values: Mapped[list["FoodNutrientValue"]] = relationship(
        back_populates="nutrient_definition",
        passive_deletes="all",
    )


class FoodNutrientValue(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "food_nutrient_values"
    __table_args__ = (
        UniqueConstraint(
            "food_source_record_id",
            "nutrient_definition_id",
            name="uq_food_nutrient_values_source_record_nutrient",
        ),
        CheckConstraint(
            "amount_per_100g IS NULL OR amount_per_100g >= 0",
            name="ck_food_nutrient_values_amount_non_negative",
        ),
    )

    food_source_record_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "food_source_records.id",
            name="fk_food_nutrient_values_source_record",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    nutrient_definition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "nutrient_definitions.id",
            name="fk_food_nutrient_values_nutrient_definition",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )
    amount_per_100g: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 6),
        nullable=True,
    )

    food_source_record: Mapped[FoodSourceRecord] = relationship(
        back_populates="nutrient_values"
    )
    nutrient_definition: Mapped[NutrientDefinition] = relationship(
        back_populates="values"
    )
