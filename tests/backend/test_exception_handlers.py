import asyncio
import importlib

import httpx
from fastapi import FastAPI
from pydantic import BaseModel


class QuantityPayload(BaseModel):
    quantity: int


async def request(app: FastAPI, method: str, path: str, **kwargs) -> httpx.Response:
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        return await client.request(method, path, **kwargs)


def test_resource_not_found_exception_returns_standard_error() -> None:
    from app.core.exception_handlers import register_exception_handlers
    from app.core.exceptions import ResourceNotFoundException

    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/resource")
    def get_resource() -> None:
        raise ResourceNotFoundException()

    response = asyncio.run(request(app, "GET", "/resource"))

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "RESOURCE_NOT_FOUND",
            "message": "Requested resource was not found",
            "details": None,
        }
    }


def test_conflict_exception_returns_standard_error_with_safe_details() -> None:
    from app.core.exception_handlers import register_exception_handlers
    from app.core.exceptions import ConflictException

    app = FastAPI()
    register_exception_handlers(app)

    @app.post("/conflict")
    def create_conflict() -> None:
        raise ConflictException(
            message="Resource already exists",
            details={"field": "name"},
        )

    response = asyncio.run(request(app, "POST", "/conflict"))

    assert response.status_code == 409
    assert response.json() == {
        "error": {
            "code": "CONFLICT",
            "message": "Resource already exists",
            "details": {"field": "name"},
        }
    }


def test_business_rule_violation_exception_returns_standard_error() -> None:
    from app.core.exception_handlers import register_exception_handlers
    from app.core.exceptions import BusinessRuleViolationException

    app = FastAPI()
    register_exception_handlers(app)

    @app.post("/business-rule")
    def violate_business_rule() -> None:
        raise BusinessRuleViolationException()

    response = asyncio.run(request(app, "POST", "/business-rule"))

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "BUSINESS_RULE_VIOLATION",
            "message": "Business rule was violated",
            "details": None,
        }
    }


def test_request_validation_error_returns_safe_standard_error() -> None:
    from app.core.exception_handlers import register_exception_handlers

    app = FastAPI()
    register_exception_handlers(app)

    @app.post("/validate")
    def validate_payload(payload: QuantityPayload) -> None:
        return None

    sensitive_input = "VALIDATION_INPUT_SENTINEL_58"
    response = asyncio.run(
        request(
            app,
            "POST",
            "/validate",
            json={"quantity": sensitive_input},
        )
    )

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "Request validation failed",
            "details": [
                {
                    "location": ["body", "quantity"],
                    "type": "int_parsing",
                }
            ],
        }
    }
    assert sensitive_input not in response.text


def test_unexpected_exception_returns_generic_error_without_sensitive_data() -> None:
    from app.core.exception_handlers import register_exception_handlers

    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/unexpected")
    def raise_unexpected_exception() -> None:
        raise RuntimeError(
            "UNEXPECTED_SECRET_SENTINEL_73 "
            "postgresql://private-user:private-value@private-host/private-db"
        )

    response = asyncio.run(request(app, "GET", "/unexpected"))

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "INTERNAL_SERVER_ERROR",
            "message": "An unexpected error occurred",
            "details": None,
        }
    }
    assert "UNEXPECTED_SECRET_SENTINEL_73" not in response.text
    assert "postgresql://" not in response.text
    assert "traceback" not in response.text.lower()


def test_main_registers_central_exception_handlers(monkeypatch) -> None:
    handlers_module = importlib.import_module("app.core.exception_handlers")
    main_module = importlib.import_module("app.main")
    registered_apps = []

    def record_registration(app: FastAPI) -> None:
        registered_apps.append(app)

    monkeypatch.setattr(
        handlers_module,
        "register_exception_handlers",
        record_registration,
    )
    main_module = importlib.reload(main_module)

    assert registered_apps == [main_module.app]
