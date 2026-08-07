import importlib
import subprocess
import sys
import uuid
from datetime import timedelta

from sqlalchemy import DateTime
from sqlalchemy.dialects.postgresql import UUID


def _column(mixin: type, name: str):
    return mixin.__dict__[name].column


def _invoke_default(default):
    assert default is not None
    return default.arg(None)


def test_uuid_primary_key_uses_postgresql_uuid_and_uuid4_default() -> None:
    from app.models.mixins import UUIDPrimaryKeyMixin

    id_column = _column(UUIDPrimaryKeyMixin, "id")

    assert id_column.primary_key is True
    assert isinstance(id_column.type, UUID)
    assert id_column.type.as_uuid is True

    first_id = _invoke_default(id_column.default)
    second_id = _invoke_default(id_column.default)

    assert isinstance(first_id, uuid.UUID)
    assert first_id.version == 4
    assert isinstance(second_id, uuid.UUID)
    assert second_id.version == 4
    assert first_id != second_id


def test_timestamp_columns_use_timezone_aware_utc_defaults() -> None:
    from app.models.mixins import TimestampMixin

    created_column = _column(TimestampMixin, "created_at")
    updated_column = _column(TimestampMixin, "updated_at")

    assert isinstance(created_column.type, DateTime)
    assert created_column.type.timezone is True
    assert isinstance(updated_column.type, DateTime)
    assert updated_column.type.timezone is True

    created_at = _invoke_default(created_column.default)
    updated_at = _invoke_default(updated_column.default)

    assert created_at.utcoffset() == timedelta(0)
    assert updated_at.utcoffset() == timedelta(0)


def test_updated_at_has_timezone_aware_utc_onupdate() -> None:
    from app.models.mixins import TimestampMixin

    updated_column = _column(TimestampMixin, "updated_at")
    updated_at = _invoke_default(updated_column.onupdate)

    assert updated_at.utcoffset() == timedelta(0)


def test_mixin_import_does_not_add_tables_to_base_metadata() -> None:
    from app.models.base import Base

    tables_before_import = dict(Base.metadata.tables)
    importlib.import_module("app.models.mixins")

    assert dict(Base.metadata.tables) == tables_before_import


def test_mixin_import_does_not_create_engine_or_connect() -> None:
    script = """
import psycopg
import sqlalchemy

def fail_if_database_is_used(*args, **kwargs):
    raise AssertionError("Mixin import must not use the database")

sqlalchemy.create_engine = fail_if_database_is_used
psycopg.connect = fail_if_database_is_used

from app.models.base import Base
import app.models.mixins

assert Base.metadata.tables == {}
"""

    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
