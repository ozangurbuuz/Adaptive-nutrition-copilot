"""Besin kataloğu tablolarını oluştur.

Revision ID: 0008_create_food_catalog
Revises: 0007_create_plan_structure
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008_create_food_catalog"
down_revision: str | None = "0007_create_plan_structure"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Katalog üst kaydı bağımlı besin değerlerinden önce oluşturulur.
    op.create_table(
        "foods",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "category",
            sa.Enum(
                "DAIRY",
                "MEAT",
                "EGG",
                "LEGUME",
                "GRAIN",
                "VEGETABLE",
                "FRUIT",
                "NUT_SEED",
                "FAT_OIL",
                "BEVERAGE",
                "OTHER",
                name="food_category",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "default_serving_quantity",
            sa.Numeric(precision=10, scale=3),
            nullable=True,
        ),
        sa.Column(
            "default_serving_unit",
            sa.Enum(
                "GRAM",
                "MILLILITER",
                "PIECE",
                "PORTION",
                name="food_default_serving_unit",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=True,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "default_serving_quantity IS NULL OR default_serving_quantity > 0",
            name="ck_foods_default_serving_quantity_positive",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_foods"),
    )
    op.create_table(
        "food_nutrients",
        sa.Column("food_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "reference_quantity",
            sa.Numeric(precision=10, scale=3),
            server_default=sa.text("100"),
            nullable=False,
        ),
        sa.Column(
            "reference_unit",
            sa.Enum(
                "GRAM",
                "MILLILITER",
                name="nutrient_reference_unit",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "calories_kcal",
            sa.Numeric(precision=10, scale=3),
            nullable=False,
        ),
        sa.Column("protein_g", sa.Numeric(precision=10, scale=3), nullable=False),
        sa.Column(
            "carbohydrate_g",
            sa.Numeric(precision=10, scale=3),
            nullable=False,
        ),
        sa.Column("fat_g", sa.Numeric(precision=10, scale=3), nullable=False),
        sa.Column("fiber_g", sa.Numeric(precision=10, scale=3), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "reference_quantity > 0",
            name="ck_food_nutrients_reference_quantity_positive",
        ),
        sa.CheckConstraint(
            "calories_kcal >= 0",
            name="ck_food_nutrients_calories_kcal_non_negative",
        ),
        sa.CheckConstraint(
            "protein_g >= 0",
            name="ck_food_nutrients_protein_g_non_negative",
        ),
        sa.CheckConstraint(
            "carbohydrate_g >= 0",
            name="ck_food_nutrients_carbohydrate_g_non_negative",
        ),
        sa.CheckConstraint(
            "fat_g >= 0",
            name="ck_food_nutrients_fat_g_non_negative",
        ),
        sa.CheckConstraint(
            "fiber_g IS NULL OR fiber_g >= 0",
            name="ck_food_nutrients_fiber_g_non_negative",
        ),
        sa.ForeignKeyConstraint(
            ["food_id"],
            ["foods.id"],
            name="fk_food_nutrients_food_id_foods",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_food_nutrients"),
        sa.UniqueConstraint("food_id", name="uq_food_nutrients_food_id"),
    )


def downgrade() -> None:
    # Bağımlı besin değerleri katalog üst kaydından önce kaldırılır.
    op.drop_table("food_nutrients")
    op.drop_table("foods")
