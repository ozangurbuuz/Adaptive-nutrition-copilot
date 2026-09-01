import asyncio
import importlib
import uuid

import httpx
import pytest
from fastapi.routing import APIRoute

from app.core.exceptions import ResourceNotFoundException
from app.core.orm import get_database_session


# Sabit UUID'ler request delegasyonu ile response gövdesini deterministik tutar.
PLAN_ID = uuid.UUID("10000000-0000-0000-0000-000000000001")
CLIENT_ID = uuid.UUID("20000000-0000-0000-0000-000000000001")
DIETITIAN_ID = uuid.UUID("30000000-0000-0000-0000-000000000001")


# Router doğrudan session kullanırsa gerekli metotları bulamayarak testi kıran sentinel'dir.
class _NoDirectDatabaseSession:
    pass


# Global FastAPI uygulamasını test anında alarak route kayıtlarını güncel haliyle inceler.
def _app():
    return importlib.import_module("app.main").app


# NutritionPlan koleksiyon endpoint'i için istenen HTTP metoduna ait route'u bulur.
def _route(method: str) -> APIRoute | None:
    return next(
        (
            candidate
            for candidate in _app().routes
            if isinstance(candidate, APIRoute)
            and candidate.path == "/api/v1/nutrition-plans"
            and method in candidate.methods
        ),
        None,
    )


# Delegasyon ve validation senaryolarının ortak, en küçük geçerli body’sini üretir.
def _minimum_payload() -> dict[str, object]:
    return {
        "client_profile_id": str(CLIENT_ID),
        "dietitian_profile_id": str(DIETITIAN_ID),
        "title": "September Plan",
    }


# Session dependency override'ını her durumda geri yükleyerek global test durumunu korur.
async def _post(payload: dict[str, object], session) -> httpx.Response:
    app = _app()
    previous_overrides = dict(app.dependency_overrides)
    app.dependency_overrides[get_database_session] = lambda: session
    try:
        # Exception'ların merkezi handler tarafından HTTP cevabına çevrilmesini sağlar.
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.post("/api/v1/nutrition-plans", json=payload)
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)


# Service çağrısını modül importu veya açık alias fark etmeksizin güvenle monkeypatch eder.
def _patch_route_service(monkeypatch, replacement) -> None:
    route_module = importlib.import_module("app.api.v1.nutrition_plans")
    service_module = importlib.import_module("app.services.nutrition_plan")
    original = getattr(service_module, "create_nutrition_plan", None)
    assert callable(original), "create_nutrition_plan service function is missing"
    bound_aliases = [
        name
        for name, value in vars(route_module).items()
        if value is original
    ]
    monkeypatch.setattr(service_module, "create_nutrition_plan", replacement)
    for alias in bound_aliases:
        monkeypatch.setattr(route_module, alias, replacement)


# POST route metadata'sının 201, create request DTO ve explicit read DTO kullandığını sınar.
def test_create_route_is_registered_with_201_and_explicit_models() -> None:
    schema_module = importlib.import_module("app.schemas.nutrition_plan")
    request_model = getattr(schema_module, "NutritionPlanCreate", None)
    response_model = getattr(schema_module, "NutritionPlanRead", None)
    route = _route("POST")

    assert request_model is not None, "NutritionPlanCreate request DTO is missing"
    assert response_model is not None, "NutritionPlanRead response DTO is missing"
    assert route is not None, "NutritionPlan create POST route is not registered"
    assert route.status_code == 201
    assert route.response_model is response_model
    assert route.body_field is not None
    assert route.body_field.type_ is request_model


# Router'ın DB işi yapmadan gerçek session ve parse edilmiş DTO ile service'e delegasyonunu sınar.
def test_create_route_delegates_session_and_dto_to_service(monkeypatch) -> None:
    session = _NoDirectDatabaseSession()
    service_calls = []
    response_payload = {
        "id": str(PLAN_ID),
        "client_profile_id": str(CLIENT_ID),
        "dietitian_profile_id": str(DIETITIAN_ID),
        "title": "September Plan",
        "status": "DRAFT",
        "starts_on": None,
        "ends_on": None,
        "notes": None,
        "days": [],
    }

    # Service dublörü aldığı bağımlılıkları kaydeder ve beklenen response sözleşmesini döndürür.
    def fake_service(received_session, received_create):
        service_calls.append((received_session, received_create))
        return response_payload

    _patch_route_service(monkeypatch, fake_service)

    response = asyncio.run(_post(_minimum_payload(), session))

    assert response.status_code == 201
    assert response.json() == response_payload
    assert len(service_calls) == 1
    assert service_calls[0][0] is session
    request_dto = service_calls[0][1]
    assert request_dto.client_profile_id == CLIENT_ID
    assert request_dto.dietitian_profile_id == DIETITIAN_ID
    assert request_dto.title == "September Plan"
    assert request_dto.starts_on is None
    assert request_dto.ends_on is None
    assert request_dto.notes is None


# Ters tarih ile client'ın göndermemesi gereken alanların standart 422 üretmesini bekler.
@pytest.mark.parametrize(
    "invalid_fields",
    [
        {"starts_on": "2026-09-07", "ends_on": "2026-09-01"},
        {"status": "ACTIVE"},
        {"days": []},
    ],
)
def test_create_route_returns_standard_422_for_invalid_contract(
    invalid_fields: dict[str, object],
) -> None:
    response = asyncio.run(
        _post(
            {**_minimum_payload(), **invalid_fields},
            _NoDirectDatabaseSession(),
        )
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["message"] == "Request validation failed"
    assert isinstance(body["error"]["details"], list)
    assert body["error"]["details"]


# Service'ten gelen domain not-found exception'ının merkezi 404 gövdesine çevrilmesini sınar.
def test_create_route_maps_service_not_found_to_standard_404(monkeypatch) -> None:
    # Profil bulunamaması durumunu router'a doğrudan exception yükselterek taşır.
    def missing_profile(received_session, received_create):
        raise ResourceNotFoundException()

    _patch_route_service(monkeypatch, missing_profile)

    response = asyncio.run(
        _post(_minimum_payload(), _NoDirectDatabaseSession())
    )

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "RESOURCE_NOT_FOUND",
            "message": "Requested resource was not found",
            "details": None,
        }
    }


# Yeni POST eklenirken mevcut NutritionPlan detail GET endpoint'inin korunmasını güvenceye alır.
def test_existing_detail_get_route_remains_registered() -> None:
    route = next(
        (
            candidate
            for candidate in _app().routes
            if isinstance(candidate, APIRoute)
            and candidate.path == "/api/v1/nutrition-plans/{plan_id}"
            and "GET" in candidate.methods
        ),
        None,
    )

    assert route is not None, "existing NutritionPlan detail GET route was removed"
