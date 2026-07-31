from collections.abc import Callable
from enum import Enum
from typing import Annotated

from fastapi import Depends
from pydantic import BaseModel, ConfigDict, Field

from app.core.exceptions import (
    AuthenticationRequiredException,
    PermissionDeniedException,
)


class UserRole(str, Enum):
    DIETITIAN = "DIETITIAN"
    CLIENT = "CLIENT"
    ADMIN = "ADMIN"


class AuthenticatedPrincipal(BaseModel):
    user_id: str = Field(min_length=1)
    role: UserRole
    tenant_id: str | None = None
    organization_id: str | None = None

    model_config = ConfigDict(frozen=True)


def get_current_principal() -> AuthenticatedPrincipal:
    raise AuthenticationRequiredException()


def require_roles(
    *allowed_roles: UserRole,
) -> Callable[..., AuthenticatedPrincipal]:
    if not allowed_roles:
        raise ValueError("At least one role must be allowed")
    if not all(isinstance(role, UserRole) for role in allowed_roles):
        raise TypeError("Allowed roles must be UserRole values")

    allowed_role_set = frozenset(allowed_roles)

    def verify_principal_role(
        principal: Annotated[
            AuthenticatedPrincipal | None,
            Depends(get_current_principal),
        ],
    ) -> AuthenticatedPrincipal:
        if principal is None:
            raise AuthenticationRequiredException()
        if principal.role not in allowed_role_set:
            raise PermissionDeniedException()
        return principal

    return verify_principal_role
