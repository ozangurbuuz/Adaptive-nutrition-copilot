"""Create normalized client clinical record tables.

Revision ID: 0005_create_clinical_records
Revises: 0004_create_client_details
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0005_create_clinical_records"
down_revision: str | Sequence[str] | None = "0004_create_client_details"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # These records are normalized safety inputs, not medical decision outputs.
    op.create_table(
        "client_allergies",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "client_profile_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("allergen_name", sa.String(length=255), nullable=False),
        sa.Column(
            "severity",
            sa.Enum(
                "MILD",
                "MODERATE",
                "SEVERE",
                name="allergy_severity",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("notes", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "allergen_name = lower(btrim(allergen_name))",
            name="ck_client_allergies_allergen_name_normalized",
        ),
        sa.ForeignKeyConstraint(
            ["client_profile_id"],
            ["client_profiles.id"],
            name="fk_client_allergies_client_profile_id_client_profiles",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "client_profile_id",
            "allergen_name",
            name="uq_client_allergies_client_profile_id_allergen_name",
        ),
    )
    op.create_table(
        "client_medical_conditions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "client_profile_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("condition_name", sa.String(length=255), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "ACTIVE",
                "RESOLVED",
                "UNKNOWN",
                name="medical_condition_status",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("notes", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["client_profile_id"],
            ["client_profiles.id"],
            name="fk_client_medical_conditions_client_profile_id_client_profiles",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "client_medications",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "client_profile_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("medication_name", sa.String(length=255), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "ACTIVE",
                "INACTIVE",
                name="medication_status",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("notes", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["client_profile_id"],
            ["client_profiles.id"],
            name="fk_client_medications_client_profile_id_client_profiles",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("client_medications")
    op.drop_table("client_medical_conditions")
    op.drop_table("client_allergies")
