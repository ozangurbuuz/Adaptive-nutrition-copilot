from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings


def resolve_sqlalchemy_database_url(settings: Settings | None = None) -> str:
    resolved_settings = settings or get_settings()
    database_url = resolved_settings.database_url
    if database_url is None:
        raise RuntimeError("DATABASE_URL was not resolved")

    url = database_url.get_secret_value()
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def create_database_engine(settings: Settings | None = None) -> Engine:
    return create_engine(
        resolve_sqlalchemy_database_url(settings),
        pool_pre_ping=True,
    )


@lru_cache
def get_database_engine() -> Engine:
    return create_database_engine()


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(
        bind=get_database_engine(),
        autoflush=False,
        expire_on_commit=False,
    )


def get_database_session() -> Iterator[Session]:
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()
