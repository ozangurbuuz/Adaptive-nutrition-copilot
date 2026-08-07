import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import MealItemUnit, MealType
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.nutrition_plan import NutritionPlan

if TYPE_CHECKING:
    from app.models.food import Food


class PlanDay(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "plan_days"
    __table_args__ = (
        UniqueConstraint(
            "nutrition_plan_id",
            "day_number",
            name="uq_plan_days_nutrition_plan_id_day_number",
        ),
        CheckConstraint(
            "day_number > 0",
            name="ck_plan_days_day_number_positive",
        ),
    )

    nutrition_plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "nutrition_plans.id",
            name="fk_plan_days_nutrition_plan_id_nutrition_plans",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    day_number: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)

    nutrition_plan: Mapped[NutritionPlan] = relationship(
        back_populates="plan_days",
    )
    # Öğünler gün kaydının bileşim parçalarıdır.
    meals: Mapped[list["Meal"]] = relationship(
        back_populates="plan_day",
        cascade="all, delete-orphan",
        passive_deletes=True,
        single_parent=True,
    )


class Meal(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "meals"
    __table_args__ = (
        UniqueConstraint(
            "plan_day_id",
            "sort_order",
            name="uq_meals_plan_day_id_sort_order",
        ),
        CheckConstraint(
            "sort_order >= 0",
            name="ck_meals_sort_order_non_negative",
        ),
    )

    plan_day_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "plan_days.id",
            name="fk_meals_plan_day_id_plan_days",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    meal_type: Mapped[MealType] = mapped_column(
        Enum(
            MealType,
            name="meal_type",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
    )
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)

    plan_day: Mapped[PlanDay] = relationship(back_populates="meals")
    # Satırlar öğünden ayrı bir yaşam döngüsüne sahip değildir.
    items: Mapped[list["MealItem"]] = relationship(
        back_populates="meal",
        cascade="all, delete-orphan",
        passive_deletes=True,
        single_parent=True,
    )


class MealItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "meal_items"
    __table_args__ = (
        CheckConstraint(
            "quantity > 0",
            name="ck_meal_items_quantity_positive",
        ),
    )

    meal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "meals.id",
            name="fk_meal_items_meal_id_meals",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    food_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "foods.id",
            name="fk_meal_items_food_id_foods",
            ondelete="RESTRICT",
        ),
        nullable=True,
    )
    # Yemek kataloğu eklenene kadar isim, plan içeriğinin gösterim anlık görüntüsüdür.
    item_name: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(10, 3),
        nullable=False,
    )
    unit: Mapped[MealItemUnit] = mapped_column(
        Enum(
            MealItemUnit,
            name="meal_item_unit",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
    )

    meal: Mapped[Meal] = relationship(back_populates="items")
    food: Mapped["Food | None"] = relationship(back_populates="meal_items")


from app.models import food as _food  # noqa: E402, F401
