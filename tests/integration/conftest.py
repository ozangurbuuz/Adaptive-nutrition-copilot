import os
import re
from collections.abc import Iterator
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.engine import Connection, Engine, URL, make_url
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.base import Base
from app.models.food import Food, FoodNutrient  # noqa: F401


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_INI = PROJECT_ROOT / "backend" / "alembic.ini"
DOMAIN_TABLES = {
    "users",
    "dietitian_profiles",
    "client_profiles",
    "client_health_profiles",
    "client_preferences",
    "client_allergies",
    "client_medical_conditions",
    "client_medications",
    "nutrition_plans",
    "plan_days",
    "meals",
    "meal_items",
    "foods",
    "food_nutrients",
    "dataset_releases",
    "food_source_records",
    "nutrient_definitions",
    "food_nutrient_values",
    "food_portions",
}
MANAGED_TABLES = DOMAIN_TABLES | {"alembic_version"}


def _psycopg_url(raw_url: str) -> URL:
    url = make_url(raw_url.strip())
    if url.drivername not in {"postgresql", "postgresql+psycopg"}:
        raise pytest.UsageError("TEST_DATABASE_URL PostgreSQL kullanmalıdır")
    if not url.database or not _is_test_database_name(url.database):
        raise pytest.UsageError(
            "Test database adı ayrı bir test/tests/testing bölümü içermelidir"
        )
    if url.drivername == "postgresql":
        url = url.set(drivername="postgresql+psycopg")
    return url


def _is_test_database_name(database_name: str) -> bool:
    tokens = {
        token
        for token in re.split(r"[^a-z0-9]+", database_name.casefold())
        if token
    }
    return bool(tokens & {"test", "tests", "testing"})


def _database_identity(url: URL) -> tuple[str, int, str]:
    return (
        (url.host or "").casefold(),
        url.port or 5432,
        (url.database or "").casefold(),
    )


def _application_database_url() -> URL | None:
    explicit_url = os.getenv("DATABASE_URL")
    if explicit_url:
        return make_url(explicit_url.strip())

    try:
        settings = get_settings()
    except Exception:
        return None

    if settings.database_url is None:
        return None
    return make_url(settings.database_url.get_secret_value())


def _validated_test_database_url() -> URL:
    raw_url = os.getenv("TEST_DATABASE_URL")
    if not raw_url:
        pytest.skip("TEST_DATABASE_URL tanımlı değil; PostgreSQL integration atlandı")

    test_url = _psycopg_url(raw_url)
    application_url = _application_database_url()
    same_database_name = (
        application_url is not None
        and application_url.database is not None
        and test_url.database is not None
        and application_url.database.casefold() == test_url.database.casefold()
    )
    if application_url is not None and (
        same_database_name
        or _database_identity(test_url) == _database_identity(application_url)
    ):
        raise pytest.UsageError(
            "TEST_DATABASE_URL uygulama DATABASE_URL hedefiyle aynı olamaz"
        )
    return test_url


def _assert_test_database_connection(engine: Engine, expected_database: str) -> None:
    with engine.connect() as connection:
        actual_database = connection.scalar(sa.text("SELECT current_database()"))

    if not isinstance(actual_database, str):
        raise pytest.UsageError("PostgreSQL mevcut database adını döndürmedi")
    if actual_database.casefold() != expected_database.casefold():
        raise pytest.UsageError("Bağlanılan database TEST_DATABASE_URL ile eşleşmiyor")
    if not _is_test_database_name(actual_database):
        raise pytest.UsageError("Bağlanılan database test database olarak doğrulanamadı")


def _assert_only_managed_objects(engine: Engine) -> None:
    inspector = sa.inspect(engine)
    tables = set(inspector.get_table_names())
    views = set(inspector.get_view_names())
    unknown_tables = tables - MANAGED_TABLES

    if unknown_tables or views:
        raise pytest.UsageError(
            "Test database bilinmeyen tablo veya view içeriyor; temizlik yapılmadı"
        )


def _drop_managed_tables(engine: Engine) -> None:
    _assert_only_managed_objects(engine)
    Base.metadata.drop_all(engine, checkfirst=True)

    with engine.begin() as connection:
        if "alembic_version" in sa.inspect(connection).get_table_names():
            metadata = sa.MetaData()
            version_table = sa.Table(
                "alembic_version",
                metadata,
                autoload_with=connection,
            )
            version_table.drop(connection)

    remaining_tables = set(sa.inspect(engine).get_table_names())
    if remaining_tables:
        raise pytest.UsageError("Test database bilinen tablolardan temizlenemedi")


def _upgrade_to_head(engine: Engine) -> None:
    config = Config(str(ALEMBIC_INI))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")


@pytest.fixture(scope="session")
def postgres_engine() -> Iterator[Engine]:
    test_url = _validated_test_database_url()
    engine = sa.create_engine(test_url, pool_pre_ping=True)

    try:
        _assert_test_database_connection(engine, test_url.database or "")
        _drop_managed_tables(engine)
        _upgrade_to_head(engine)
        yield engine
    finally:
        try:
            _assert_test_database_connection(engine, test_url.database or "")
            _drop_managed_tables(engine)
        finally:
            engine.dispose()


@pytest.fixture
def postgres_connection(postgres_engine: Engine) -> Iterator[Connection]:
    connection = postgres_engine.connect()
    transaction = connection.begin()
    try:
        yield connection
    finally:
        if transaction.is_active:
            transaction.rollback()
        connection.close()


@pytest.fixture
def db_session(postgres_connection: Connection) -> Iterator[Session]:
    session = Session(
        bind=postgres_connection,
        join_transaction_mode="create_savepoint",
        expire_on_commit=False,
    )
    try:
        yield session
    finally:
        session.close()
