import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
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
from app.models.enums import FoodCategory, MealItemUnit, NutrientReferenceUnit
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
