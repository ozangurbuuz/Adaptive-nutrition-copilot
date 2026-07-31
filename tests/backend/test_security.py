import asyncio
from typing import Annotated

import httpx
import pytest
from fastapi import Depends, FastAPI
from pydantic import ValidationError

from app.core.exception_handlers import register_exception_handlers


async def request(
    app: FastAPI,
    method: str,
    path: str,
    **kwargs,
) -> httpx.Response:
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        return await client.request(method, path, **kwargs)


def test_user_roles_and_authenticated_principal_are_typed_and_immutable() -> None:
    from app.core.security import AuthenticatedPrincipal, UserRole

    assert {role.value for role in UserRole} == {
        "DIETITIAN",
        "CLIENT",
        "ADMIN",
    }

    principal = AuthenticatedPrincipal(
        user_id="user-123",
        role=UserRole.DIETITIAN,
        tenant_id="tenant-456",
        organization_id="organization-789",
    )

    assert principal.user_id == "user-123"
    assert principal.role is UserRole.DIETITIAN
    assert principal.tenant_id == "tenant-456"
    assert principal.organization_id == "organization-789"

    with pytest.raises(ValidationError):
        principal.role = UserRole.ADMIN


def test_user_role_rejects_unknown_value() -> None:
    from app.core.security import UserRole

    with pytest.raises(ValueError):
        UserRole("OWNER")


def test_missing_principal_returns_safe_authentication_error() -> None:
    from app.core.security import AuthenticatedPrincipal, get_current_principal

    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/protected")
    def protected_endpoint(
        principal: Annotated[
            AuthenticatedPrincipal,
            Depends(get_current_principal),
        ],
    ) -> dict[str, str]:
        return {"user_id": principal.user_id}

    token_sentinel = "AUTH_TOKEN_SENTINEL_61"
    response = asyncio.run(
        request(
            app,
            "GET",
            "/protected",
            headers={"Authorization": f"Bearer {token_sentinel}"},
        )
    )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json() == {
        "error": {
            "code": "AUTHENTICATION_REQUIRED",
            "message": "Authentication is required",
            "details": None,
        }
    }
    assert token_sentinel not in response.text


def test_require_roles_returns_401_when_override_supplies_no_principal() -> None:
    from app.core.security import (
        AuthenticatedPrincipal,
        UserRole,
        get_current_principal,
        require_roles,
    )

    app = FastAPI()
    register_exception_handlers(app)
    app.dependency_overrides[get_current_principal] = lambda: None

    @app.get("/admin")
    def admin_endpoint(
        principal: Annotated[
            AuthenticatedPrincipal,
            Depends(require_roles(UserRole.ADMIN)),
        ],
    ) -> dict[str, str]:
        return {"user_id": principal.user_id}

    response = asyncio.run(request(app, "GET", "/admin"))

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


def test_require_roles_returns_403_for_disallowed_enum_role() -> None:
    from app.core.security import (
        AuthenticatedPrincipal,
        UserRole,
        get_current_principal,
        require_roles,
    )

    app = FastAPI()
    register_exception_handlers(app)
    client_principal = AuthenticatedPrincipal(
        user_id="client-123",
        role=UserRole.CLIENT,
    )
    app.dependency_overrides[get_current_principal] = lambda: client_principal

    @app.get("/admin")
    def admin_endpoint(
        principal: Annotated[
            AuthenticatedPrincipal,
            Depends(require_roles(UserRole.ADMIN)),
        ],
    ) -> dict[str, str]:
        return {"user_id": principal.user_id}

    response = asyncio.run(request(app, "GET", "/admin"))

    assert response.status_code == 403
    assert response.json() == {
        "error": {
            "code": "PERMISSION_DENIED",
            "message": "Permission denied",
            "details": None,
        }
    }


def test_dependency_override_allows_principal_with_required_role() -> None:
    from app.core.security import (
        AuthenticatedPrincipal,
        UserRole,
        get_current_principal,
        require_roles,
    )

    app = FastAPI()
    register_exception_handlers(app)
    dietitian_principal = AuthenticatedPrincipal(
        user_id="dietitian-123",
        role=UserRole.DIETITIAN,
        organization_id="clinic-456",
    )
    app.dependency_overrides[get_current_principal] = lambda: dietitian_principal

    @app.get("/dietitian")
    def dietitian_endpoint(
        principal: Annotated[
            AuthenticatedPrincipal,
            Depends(require_roles(UserRole.DIETITIAN)),
        ],
    ) -> dict[str, str]:
        return {
            "user_id": principal.user_id,
            "role": principal.role.value,
        }

    response = asyncio.run(request(app, "GET", "/dietitian"))

    assert response.status_code == 200
    assert response.json() == {
        "user_id": "dietitian-123",
        "role": "DIETITIAN",
    }


def test_require_roles_supports_multiple_allowed_enum_roles() -> None:
    from app.core.security import (
        AuthenticatedPrincipal,
        UserRole,
        get_current_principal,
        require_roles,
    )

    app = FastAPI()
    register_exception_handlers(app)
    admin_principal = AuthenticatedPrincipal(
        user_id="admin-123",
        role=UserRole.ADMIN,
    )
    app.dependency_overrides[get_current_principal] = lambda: admin_principal

    @app.get("/staff")
    def staff_endpoint(
        principal: Annotated[
            AuthenticatedPrincipal,
            Depends(require_roles(UserRole.DIETITIAN, UserRole.ADMIN)),
        ],
    ) -> dict[str, str]:
        return {"role": principal.role.value}

    response = asyncio.run(request(app, "GET", "/staff"))

    assert response.status_code == 200
    assert response.json() == {"role": "ADMIN"}


def test_require_roles_rejects_string_role_configuration() -> None:
    from app.core.security import require_roles

    with pytest.raises(TypeError):
        require_roles("ADMIN")
