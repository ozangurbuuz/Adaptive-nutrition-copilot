"""Create client health profile and preferences tables.

Revision ID: 0004_create_client_details
Revises: 0003_create_profiles
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0004_create_client_details"
down_revision: str | Sequence[str] | None = "0003_create_profiles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Health measurements remain isolated from identity and preference data.
    op.create_table(
        "client_health_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "client_profile_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column(
            "biological_sex",
            sa.Enum(
                "FEMALE",
                "MALE",
                "INTERSEX",
                name="client_biological_sex",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=True,
        ),
        sa.Column("height_cm", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("weight_kg", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "height_cm IS NULL OR height_cm > 0",
            name="ck_client_health_profiles_height_cm_positive",
        ),
        sa.CheckConstraint(
            "weight_kg IS NULL OR weight_kg > 0",
            name="ck_client_health_profiles_weight_kg_positive",
        ),
        sa.ForeignKeyConstraint(
            ["client_profile_id"],
            ["client_profiles.id"],
            name="fk_client_health_profiles_client_profile_id_client_profiles",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "client_profile_id",
            name="uq_client_health_profiles_client_profile_id",
        ),
    )

    # Preference scope stays narrow until normalized food relations are designed.
    op.create_table(
        "client_preferences",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "client_profile_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "dietary_pattern",
            sa.Enum(
                "OMNIVORE",
                "VEGETARIAN",
                "VEGAN",
                name="client_dietary_pattern",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["client_profile_id"],
            ["client_profiles.id"],
            name="fk_client_preferences_client_profile_id_client_profiles",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "client_profile_id",
            name="uq_client_preferences_client_profile_id",
        ),
    )


def downgrade() -> None:
    # Drop in reverse creation order even though the new tables are siblings.
    op.drop_table("client_preferences")
    op.drop_table("client_health_profiles")
