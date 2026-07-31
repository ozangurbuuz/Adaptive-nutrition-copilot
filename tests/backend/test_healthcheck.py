import asyncio
import os

import httpx
import psycopg
import pytest

os.environ.setdefault("POSTGRES_DB", "test_db")
os.environ.setdefault("POSTGRES_USER", "test_user")
os.environ.setdefault("POSTGRES_PASSWORD", "test_password")

from app.core import database
from app.core.database import verify_database_connection
from app.main import app


async def get_healthcheck() -> httpx.Response:
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        return await client.get("/healthcheck")


def test_healthcheck_returns_healthy_when_database_is_reachable() -> None:
    app.dependency_overrides[verify_database_connection] = lambda: True

    try:
        response = asyncio.run(get_healthcheck())
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "database": "reachable",
    }


def test_healthcheck_returns_unhealthy_when_database_is_unreachable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_connection_error() -> None:
        raise psycopg.OperationalError(
            "database exception sentinel: DB_EXCEPTION_SENTINEL_7F31"
        )

    monkeypatch.setattr(database, "create_database_connection", raise_connection_error)
    response = asyncio.run(get_healthcheck())

    assert response.status_code == 503
    assert response.json() == {
        "status": "unhealthy",
        "database": "unreachable",
    }
    assert "DB_EXCEPTION_SENTINEL_7F31" not in response.text
    assert "postgresql://" not in response.text
