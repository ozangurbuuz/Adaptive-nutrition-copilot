import importlib
import sys

import pytest
from pydantic import SecretStr


def test_declarative_base_has_importable_empty_metadata() -> None:
    from sqlalchemy.orm import DeclarativeBase

    from app.models.base import Base

    assert issubclass(Base, DeclarativeBase)
    assert Base.metadata.tables == {}


def test_orm_module_import_does_not_create_engine(monkeypatch) -> None:
    import sqlalchemy

    engine_calls = []

    def fail_if_engine_is_created(*args, **kwargs):
        engine_calls.append((args, kwargs))
        raise AssertionError("ORM import must not create an engine")

    monkeypatch.setattr(sqlalchemy, "create_engine", fail_if_engine_is_created)
    sys.modules.pop("app.core.orm", None)

    try:
        importlib.import_module("app.core.orm")
    finally:
        sys.modules.pop("app.core.orm", None)

    assert engine_calls == []


def test_engine_factory_uses_resolved_database_url(monkeypatch) -> None:
    from app.core import orm
    from app.core.config import Settings

    database_url = "postgresql://orm_user:***@orm-host:5432/orm_db"
    settings = Settings(
        _env_file=None,
        app_env="test",
        postgres_db="orm_db",
        postgres_user="orm_user",
        postgres_password="x",
        database_url=database_url,
    )
    engine_sentinel = object()
    captured = {}

    def fake_create_engine(url: str, **kwargs):
        captured["url"] = url
        captured["kwargs"] = kwargs
        return engine_sentinel

    monkeypatch.setattr(orm, "create_engine", fake_create_engine)

    result = orm.create_database_engine(settings)

    assert isinstance(settings.database_url, SecretStr)
    assert result is engine_sentinel
    assert captured == {
        "url": database_url.replace(
            "postgresql://",
            "postgresql+psycopg://",
            1,
        ),
        "kwargs": {"pool_pre_ping": True},
    }


def test_engine_factory_selects_psycopg_without_opening_connection(
    monkeypatch,
) -> None:
    import psycopg

    from app.core.orm import create_database_engine
    from app.core.config import Settings

    def fail_if_database_connects(*args, **kwargs):
        raise AssertionError("Engine creation must not connect to PostgreSQL")

    monkeypatch.setattr(psycopg, "connect", fail_if_database_connects)
    settings = Settings(
        _env_file=None,
        app_env="test",
        postgres_db="orm_db",
        postgres_user="orm_user",
        postgres_password="x",
    )

    engine = create_database_engine(settings)
    try:
        assert engine.dialect.driver == "psycopg"
    finally:
        engine.dispose()


def test_database_engine_is_created_lazily_and_cached(monkeypatch) -> None:
    from app.core import orm

    engine_sentinel = object()
    factory_calls = []

    def fake_create_database_engine():
        factory_calls.append(True)
        return engine_sentinel

    monkeypatch.setattr(orm, "create_database_engine", fake_create_database_engine)
    orm.get_database_engine.cache_clear()

    try:
        assert factory_calls == []
        first_engine = orm.get_database_engine()
        second_engine = orm.get_database_engine()
    finally:
        orm.get_database_engine.cache_clear()

    assert first_engine is engine_sentinel
    assert second_engine is engine_sentinel
    assert factory_calls == [True]


def test_session_factory_uses_lazy_engine_and_is_cached(monkeypatch) -> None:
    from app.core import orm

    engine_sentinel = object()
    session_factory_sentinel = object()
    captured = {}

    def fake_sessionmaker(**kwargs):
        captured.update(kwargs)
        return session_factory_sentinel

    monkeypatch.setattr(orm, "get_database_engine", lambda: engine_sentinel)
    monkeypatch.setattr(orm, "sessionmaker", fake_sessionmaker, raising=False)
    orm.get_session_factory.cache_clear()

    try:
        first_factory = orm.get_session_factory()
        second_factory = orm.get_session_factory()
    finally:
        orm.get_session_factory.cache_clear()

    assert first_factory is session_factory_sentinel
    assert second_factory is session_factory_sentinel
    assert captured == {
        "bind": engine_sentinel,
        "autoflush": False,
        "expire_on_commit": False,
    }


def test_database_session_dependency_yields_and_closes_mocked_session(
    monkeypatch,
) -> None:
    from app.core import orm

    class FakeSession:
        def __init__(self) -> None:
            self.closed = False

        def close(self) -> None:
            self.closed = True

    session = FakeSession()
    factory_calls = []

    def fake_factory():
        factory_calls.append(True)
        return session

    monkeypatch.setattr(orm, "get_session_factory", lambda: fake_factory)

    dependency = orm.get_database_session()
    yielded_session = next(dependency)

    assert yielded_session is session
    assert session.closed is False
    assert factory_calls == [True]

    with pytest.raises(StopIteration):
        next(dependency)

    assert session.closed is True
