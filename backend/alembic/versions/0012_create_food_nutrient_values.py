"""Create canonical nutrient definitions and versioned food nutrient values.

Revision ID: 0012_food_nutrient_values
Revises: 0011_food_dataset_provenance
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0012_food_nutrient_values"
down_revision: str | None = "0011_food_dataset_provenance"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "nutrient_definitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name_en", sa.String(length=100), nullable=False),
        sa.Column(
            "unit",
            sa.Enum(
                "KCAL",
                "GRAM",
                "MILLIGRAM",
                "MICROGRAM",
                name="nutrient_unit",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "length(btrim(code)) > 0",
            name="ck_nutrient_definitions_code_nonblank",
        ),
        sa.CheckConstraint(
            "code = upper(btrim(code))",
            name="ck_nutrient_definitions_code_canonical",
        ),
        sa.CheckConstraint(
            "length(btrim(name_en)) > 0",
            name="ck_nutrient_definitions_name_en_nonblank",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_nutrient_definitions"),
        sa.UniqueConstraint("code", name="uq_nutrient_definitions_code"),
    )
    op.create_table(
        "food_nutrient_values",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "food_source_record_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "nutrient_definition_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "amount_per_100g",
            sa.Numeric(precision=14, scale=6),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "amount_per_100g IS NULL OR amount_per_100g >= 0",
            name="ck_food_nutrient_values_amount_non_negative",
        ),
        sa.ForeignKeyConstraint(
            ["food_source_record_id"],
            ["food_source_records.id"],
            name="fk_food_nutrient_values_source_record",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["nutrient_definition_id"],
            ["nutrient_definitions.id"],
            name="fk_food_nutrient_values_nutrient_definition",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_food_nutrient_values"),
        sa.UniqueConstraint(
            "food_source_record_id",
            "nutrient_definition_id",
            name="uq_food_nutrient_values_source_record_nutrient",
        ),
    )
    op.create_index(
        "ix_food_nutrient_values_food_source_record_id",
        "food_nutrient_values",
        ["food_source_record_id"],
        unique=False,
    )
    op.create_index(
        "ix_food_nutrient_values_nutrient_definition_id",
        "food_nutrient_values",
        ["nutrient_definition_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_food_nutrient_values_nutrient_definition_id",
        table_name="food_nutrient_values",
    )
    op.drop_index(
        "ix_food_nutrient_values_food_source_record_id",
        table_name="food_nutrient_values",
    )
    op.drop_table("food_nutrient_values")
    op.drop_table("nutrient_definitions")
