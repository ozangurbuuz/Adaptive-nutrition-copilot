"""Plan içeriği tablolarını oluştur.

Revision ID: 0007_create_plan_structure
Revises: 0006_create_nutrition_plans
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_create_plan_structure"
down_revision: str | None = "0006_create_nutrition_plans"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Tablolar plan bütünü bağımlılık sırasına göre oluşturulur.
    op.create_table(
        "plan_days",
        sa.Column("nutrition_plan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("day_number", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "day_number > 0",
            name="ck_plan_days_day_number_positive",
        ),
        sa.ForeignKeyConstraint(
            ["nutrition_plan_id"],
            ["nutrition_plans.id"],
            name="fk_plan_days_nutrition_plan_id_nutrition_plans",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_plan_days"),
        sa.UniqueConstraint(
            "nutrition_plan_id",
            "day_number",
            name="uq_plan_days_nutrition_plan_id_day_number",
        ),
    )
    op.create_table(
        "meals",
        sa.Column("plan_day_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "meal_type",
            sa.Enum(
                "BREAKFAST",
                "MORNING_SNACK",
                "LUNCH",
                "AFTERNOON_SNACK",
                "DINNER",
                "EVENING_SNACK",
                "OTHER",
                name="meal_type",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "sort_order >= 0",
            name="ck_meals_sort_order_non_negative",
        ),
        sa.ForeignKeyConstraint(
            ["plan_day_id"],
            ["plan_days.id"],
            name="fk_meals_plan_day_id_plan_days",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_meals"),
        sa.UniqueConstraint(
            "plan_day_id",
            "sort_order",
            name="uq_meals_plan_day_id_sort_order",
        ),
    )
    op.create_table(
        "meal_items",
        sa.Column("meal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("item_name", sa.String(length=255), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=10, scale=3), nullable=False),
        sa.Column(
            "unit",
            sa.Enum(
                "GRAM",
                "MILLILITER",
                "PIECE",
                "PORTION",
                name="meal_item_unit",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "quantity > 0",
            name="ck_meal_items_quantity_positive",
        ),
        sa.ForeignKeyConstraint(
            ["meal_id"],
            ["meals.id"],
            name="fk_meal_items_meal_id_meals",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_meal_items"),
    )


def downgrade() -> None:
    # Tablolar bağımlılık sırasının tersine göre kaldırılır.
    op.drop_table("meal_items")
    op.drop_table("meals")
    op.drop_table("plan_days")
