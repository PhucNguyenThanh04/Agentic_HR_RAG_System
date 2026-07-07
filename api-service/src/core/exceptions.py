from __future__ import annotations

from typing import Any


class AppException(Exception):
    """Base exception for predictable business/application errors."""

    def __init__(
        self,
        message: str,
        status_code: int = 400,
        error_code: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code or "APP_ERROR"
        self.detail = detail or {}


class BadRequestException(AppException):
    def __init__(self, message: str = "Bad request", detail: dict[str, Any] | None = None) -> None:
        super().__init__(message, status_code=400, error_code="BAD_REQUEST", detail=detail)


class UnauthorizedException(AppException):
    def __init__(self, message: str = "Unauthorized", detail: dict[str, Any] | None = None) -> None:
        super().__init__(message, status_code=401, error_code="UNAUTHORIZED", detail=detail)


class ForbiddenException(AppException):
    def __init__(self, message: str = "Forbidden", detail: dict[str, Any] | None = None) -> None:
        super().__init__(message, status_code=403, error_code="FORBIDDEN", detail=detail)


class NotFoundException(AppException):
    def __init__(self, resource: str = "Resource", detail: dict[str, Any] | None = None) -> None:
        super().__init__(
            f"{resource} not found",
            status_code=404,
            error_code="NOT_FOUND",
            detail=detail,
        )


class ConflictException(AppException):
    def __init__(self, message: str = "Conflict", detail: dict[str, Any] | None = None) -> None:
        super().__init__(message, status_code=409, error_code="CONFLICT", detail=detail)


class UnprocessableEntityException(AppException):
    def __init__(self, message: str = "Unprocessable entity", detail: dict[str, Any] | None = None) -> None:
        super().__init__(message, status_code=422, error_code="UNPROCESSABLE_ENTITY", detail=detail)


# Backwards-compatible aliases/classes used by the current codebase.
class ValidationException(UnprocessableEntityException):
    def __init__(self, message: str = "Validation error", detail: dict[str, Any] | None = None) -> None:
        super().__init__(message=message, detail=detail)
        self.error_code = "VALIDATION_ERROR"


class InternalServerException(AppException):
    def __init__(self, message: str = "Internal server error", detail: dict[str, Any] | None = None) -> None:
        super().__init__(message, status_code=500, error_code="INTERNAL_SERVER_ERROR", detail=detail)


class DatabaseException(AppException):
    def __init__(self, message: str = "Database operation failed", detail: dict[str, Any] | None = None) -> None:
        super().__init__(message, status_code=500, error_code="DATABASE_ERROR", detail=detail)


class MLProcessingException(AppException):
    def __init__(
        self,
        step: str,
        reason: str,
        task_id: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        message = f"ML step '{step}' failed: {reason}"
        if task_id:
            message = f"[task={task_id}] {message}"
        super().__init__(message, status_code=500, error_code="ML_PROCESSING_ERROR", detail=detail)
        self.task_id = task_id
