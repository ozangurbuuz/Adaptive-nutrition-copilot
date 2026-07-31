"""Establish the ORM migration baseline without domain tables.

Revision ID: 0001_orm_baseline
Revises:
"""
from collections.abc import Sequence


revision: str = "0001_orm_baseline"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
