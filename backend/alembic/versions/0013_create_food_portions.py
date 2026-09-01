"""Create source-specific food portion gram conversions.

Revision ID: 0013_food_portions
Revises: 0012_food_nutrient_values
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0013_food_portions"
down_revision: str | None = "0012_food_nutrient_values"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "food_portions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "food_source_record_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("source_portion_id", sa.String(length=100), nullable=True),
        sa.Column(
            "amount",
            sa.Numeric(precision=14, scale=6),
            nullable=False,
        ),
        sa.Column("measure_code", sa.String(length=50), nullable=True),
        sa.Column("measure_name", sa.String(length=100), nullable=True),
        sa.Column("modifier", sa.String(length=100), nullable=True),
        sa.Column(
            "portion_description",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "gram_weight",
            sa.Numeric(precision=14, scale=6),
            nullable=True,
        ),
        sa.Column("sequence_number", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "source_portion_id IS NULL OR btrim(source_portion_id) <> ''",
            name="ck_food_portions_source_portion_id_nonblank",
        ),
        sa.CheckConstraint(
            "amount > 0",
            name="ck_food_portions_amount_positive",
        ),
        sa.CheckConstraint(
            "measure_code IS NULL OR "
            "(btrim(measure_code) <> '' "
            "AND measure_code = upper(btrim(measure_code)))",
            name="ck_food_portions_measure_code_canonical",
        ),
        sa.CheckConstraint(
            "measure_name IS NULL OR btrim(measure_name) <> ''",
            name="ck_food_portions_measure_name_nonblank",
        ),
        sa.CheckConstraint(
            "modifier IS NULL OR btrim(modifier) <> ''",
            name="ck_food_portions_modifier_nonblank",
        ),
        sa.CheckConstraint(
            "btrim(portion_description) <> ''",
            name="ck_food_portions_description_nonblank",
        ),
        sa.CheckConstraint(
            "gram_weight IS NULL OR gram_weight > 0",
            name="ck_food_portions_gram_weight_positive",
        ),
        sa.CheckConstraint(
            "sequence_number IS NULL OR sequence_number > 0",
            name="ck_food_portions_sequence_number_positive",
        ),
        sa.ForeignKeyConstraint(
            ["food_source_record_id"],
            ["food_source_records.id"],
            name=(
                "fk_food_portions_food_source_record_id_food_source_records"
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_food_portions"),
        sa.UniqueConstraint(
            "food_source_record_id",
            "source_portion_id",
            name="uq_food_portions_source_record_source_portion_id",
        ),
        sa.UniqueConstraint(
            "food_source_record_id",
            "sequence_number",
            name="uq_food_portions_source_record_sequence_number",
        ),
    )
    op.create_index(
        "ix_food_portions_food_source_record_id",
        "food_portions",
        ["food_source_record_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_food_portions_food_source_record_id",
        table_name="food_portions",
    )
    op.drop_table("food_portions")
