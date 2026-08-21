"""Add ordering to meal item rows.

Revision ID: 0010_add_meal_item_sort_order
Revises: 0009_link_meal_items_to_foods
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_add_meal_item_sort_order"
down_revision: str | None = "0009_link_meal_items_to_foods"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "meal_items",
        sa.Column(
            "sort_order",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_meal_items_sort_order_non_negative",
        "meal_items",
        "sort_order >= 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_meal_items_sort_order_non_negative",
        "meal_items",
        type_="check",
    )
    op.drop_column("meal_items", "sort_order")
