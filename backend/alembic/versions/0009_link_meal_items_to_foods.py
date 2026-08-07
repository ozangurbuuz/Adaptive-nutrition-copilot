"""Öğün satırlarını besin kataloğuna bağla.

Revision ID: 0009_link_meal_items_to_foods
Revises: 0008_create_food_catalog
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009_link_meal_items_to_foods"
down_revision: str | None = "0008_create_food_catalog"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Nullable kolon mevcut ve elle girilmiş plan satırlarını geçerli tutar.
    op.add_column(
        "meal_items",
        sa.Column("food_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_meal_items_food_id_foods",
        "meal_items",
        "foods",
        ["food_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    # Bağımlılık önce kaldırılır, ardından kolon güvenle silinir.
    op.drop_constraint(
        "fk_meal_items_food_id_foods",
        "meal_items",
        type_="foreignkey",
    )
    op.drop_column("meal_items", "food_id")
