"""Create food dataset provenance tables.

Revision ID: 0011_food_dataset_provenance
Revises: 0010_add_meal_item_sort_order
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0011_food_dataset_provenance"
down_revision: str | None = "0010_add_meal_item_sort_order"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "dataset_releases",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("release_version", sa.String(length=100), nullable=False),
        sa.Column("downloaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("license_reference", sa.String(length=500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "length(btrim(source)) > 0",
            name="ck_dataset_releases_source_nonblank",
        ),
        sa.CheckConstraint(
            "length(btrim(release_version)) > 0",
            name="ck_dataset_releases_release_version_nonblank",
        ),
        sa.CheckConstraint(
            "length(checksum_sha256) = 64",
            name="ck_dataset_releases_checksum_sha256_length",
        ),
        sa.CheckConstraint(
            "length(btrim(license_reference)) > 0",
            name="ck_dataset_releases_license_reference_nonblank",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_dataset_releases"),
        sa.UniqueConstraint(
            "source",
            "release_version",
            name="uq_dataset_releases_source_release_version",
        ),
        sa.UniqueConstraint(
            "source",
            "checksum_sha256",
            name="uq_dataset_releases_source_checksum_sha256",
        ),
    )
    op.create_table(
        "food_source_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("food_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "dataset_release_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("source_food_id", sa.String(length=100), nullable=False),
        sa.Column("canonical_name", sa.String(length=255), nullable=False),
        sa.Column("preparation_state", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "length(btrim(source_food_id)) > 0",
            name="ck_food_source_records_source_food_id_nonblank",
        ),
        sa.CheckConstraint(
            "length(btrim(canonical_name)) > 0",
            name="ck_food_source_records_canonical_name_nonblank",
        ),
        sa.CheckConstraint(
            "preparation_state IS NULL OR length(btrim(preparation_state)) > 0",
            name="ck_food_source_records_preparation_state_nonblank",
        ),
        sa.ForeignKeyConstraint(
            ["food_id"],
            ["foods.id"],
            name="fk_food_source_records_food_id_foods",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["dataset_release_id"],
            ["dataset_releases.id"],
            name="fk_food_source_records_dataset_release_id_dataset_releases",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_food_source_records"),
        sa.UniqueConstraint(
            "dataset_release_id",
            "source_food_id",
            name="uq_food_source_records_dataset_release_id_source_food_id",
        ),
    )
    op.create_index(
        "ix_food_source_records_food_id",
        "food_source_records",
        ["food_id"],
        unique=False,
    )
    op.create_index(
        "ix_food_source_records_source_food_id",
        "food_source_records",
        ["source_food_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_food_source_records_source_food_id",
        table_name="food_source_records",
    )
    op.drop_index(
        "ix_food_source_records_food_id",
        table_name="food_source_records",
    )
    op.drop_table("food_source_records")
    op.drop_table("dataset_releases")
