from typing import Any


class AppException(Exception):
    status_code = 500
    code = "APP_ERROR"
    default_message = "Application error"
    default_headers: dict[str, str] | None = None

    def __init__(
        self,
        message: str | None = None,
        details: dict[str, Any] | list[Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.message = message or self.default_message
        self.details = details
        default_headers = self.default_headers
        self.headers = dict(headers or default_headers) if headers or default_headers else None
        super().__init__(self.message)


class ResourceNotFoundException(AppException):
    status_code = 404
    code = "RESOURCE_NOT_FOUND"
    default_message = "Requested resource was not found"


class ConflictException(AppException):
    status_code = 409
    code = "CONFLICT"
    default_message = "Resource conflict"


class BusinessRuleViolationException(AppException):
    status_code = 422
    code = "BUSINESS_RULE_VIOLATION"
    default_message = "Business rule was violated"


class AuthenticationRequiredException(AppException):
    status_code = 401
    code = "AUTHENTICATION_REQUIRED"
    default_message = "Authentication is required"
    default_headers = {"WWW-Authenticate": "Bearer"}


class PermissionDeniedException(AppException):
    status_code = 403
    code = "PERMISSION_DENIED"
    default_message = "Permission denied"
