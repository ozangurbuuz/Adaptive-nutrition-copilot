import asyncio
import importlib
import os

import httpx
import psycopg
from fastapi import APIRouter


def test_api_v1_router_is_attached_to_main_api_router(monkeypatch) -> None:
    included_routers = []
    original_include_router = APIRouter.include_router

    def record_include(parent, child, *args, **kwargs):
        included_routers.append((parent, child))
        return original_include_router(parent, child, *args, **kwargs)

    monkeypatch.setattr(APIRouter, "include_router", record_include)

    v1_module = importlib.import_module("app.api.v1.router")
    router_module = importlib.import_module("app.api.router")
    router_module = importlib.reload(router_module)

    assert v1_module.router.prefix == "/api/v1"
    assert any(
        parent is router_module.router and child is v1_module.router
        for parent, child in included_routers
    )


def test_main_includes_only_main_api_router(monkeypatch) -> None:
    router_module = importlib.import_module("app.api.router")
    main_module = importlib.import_module("app.main")
    included_routers = []
    original_include_router = main_module.FastAPI.include_router

    def record_include(parent, child, *args, **kwargs):
        included_routers.append((parent, child))
        return original_include_router(parent, child, *args, **kwargs)

    monkeypatch.setattr(main_module.FastAPI, "include_router", record_include)
    main_module = importlib.reload(main_module)

    assert included_routers == [(main_module.app, router_module.router)]


def test_unknown_api_v1_endpoint_returns_404_without_database_connection(
    monkeypatch,
) -> None:
    def fail_if_database_connects(*args, **kwargs):
        raise AssertionError("router lookup must not open a database connection")

    monkeypatch.setattr(psycopg, "connect", fail_if_database_connects)
    main_module = importlib.import_module("app.main")

    async def request_unknown_endpoint() -> httpx.Response:
        transport = httpx.ASGITransport(
            app=main_module.app,
            raise_app_exceptions=False,
        )
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.get("/api/v1/does-not-exist")

    response = asyncio.run(request_unknown_endpoint())

    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}


def test_router_imports_are_side_effect_free(monkeypatch) -> None:
    def fail_if_database_connects(*args, **kwargs):
        raise AssertionError("router imports must not open a database connection")

    monkeypatch.setattr(psycopg, "connect", fail_if_database_connects)
    for key in ("POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD", "DATABASE_URL"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("APP_ENV", "test")

    for module_name in (
        "app.api.v1.router",
        "app.api.router",
        "app.main",
    ):
        module = importlib.import_module(module_name)
        importlib.reload(module)

    assert os.environ["APP_ENV"] == "test"
