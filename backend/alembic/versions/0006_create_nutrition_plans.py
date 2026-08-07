"""create nutrition plans

Revision ID: 0006_create_nutrition_plans
Revises: 0005_create_clinical_records
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_create_nutrition_plans"
down_revision: str | None = "0005_create_clinical_records"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "nutrition_plans",
        sa.Column("client_profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "dietitian_profile_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "DRAFT",
                "ACTIVE",
                "ARCHIVED",
                name="nutrition_plan_status",
                native_enum=False,
                create_constraint=True,
            ),
            server_default=sa.text("'DRAFT'"),
            nullable=False,
        ),
        sa.Column("starts_on", sa.Date(), nullable=True),
        sa.Column("ends_on", sa.Date(), nullable=True),
        sa.Column("notes", sa.String(length=1000), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "starts_on IS NULL OR ends_on IS NULL OR ends_on >= starts_on",
            name="ck_nutrition_plans_date_range",
        ),
        sa.ForeignKeyConstraint(
            ["client_profile_id"],
            ["client_profiles.id"],
            name="fk_nutrition_plans_client_profile_id_client_profiles",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["dietitian_profile_id"],
            ["dietitian_profiles.id"],
            name="fk_nutrition_plans_dietitian_profile_id_dietitian_profiles",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_nutrition_plans"),
    )

    # The one-ACTIVE-plan rule remains a future partial unique index decision.


def downgrade() -> None:
    op.drop_table("nutrition_plans")
