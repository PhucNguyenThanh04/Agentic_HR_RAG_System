from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.core.exceptions import AppException

logger = logging.getLogger(__name__)


def _error_body(
    *,
    message: str,
    error_code: str | None = None,
    detail: dict[str, Any] | None = None,
    errors: list[Any] | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "success": False,
        "message": message,
    }
    if error_code is not None:
        body["error_code"] = error_code
    if detail:
        body["detail"] = jsonable_encoder(detail)
    if errors is not None:
        body["errors"] = jsonable_encoder(errors)
    return body


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    if exc.status_code >= 500:
        logger.exception("App exception: %s", exc.message)
    else:
        logger.warning("App exception: %s", exc.message)

    return JSONResponse(
        status_code=exc.status_code,
        content=_error_body(
            message=exc.message,
            error_code=exc.error_code,
            detail=exc.detail,
        ),
    )


async def request_validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    logger.warning("Request validation error on %s: %s", request.url.path, exc.errors())
    return JSONResponse(
        status_code=422,
        content=_error_body(
            message="Validation error",
            error_code="VALIDATION_ERROR",
            errors=exc.errors(),
        ),
    )


async def value_error_exception_handler(request: Request, exc: ValueError) -> JSONResponse:
    logger.warning("ValueError mapped to 400 on %s: %s", request.url.path, exc)
    return JSONResponse(
        status_code=400,
        content=_error_body(
            message=str(exc) or "Bad request",
            error_code="BAD_REQUEST",
        ),
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    message = exc.detail if isinstance(exc.detail, str) else "HTTP error"
    status_code = int(exc.status_code)
    error_code = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        422: "VALIDATION_ERROR",
    }.get(status_code, "HTTP_ERROR")

    if status_code >= 500:
        logger.error("HTTP exception on %s: %s", request.url.path, message)
    else:
        logger.warning("HTTP exception on %s: %s", request.url.path, message)

    return JSONResponse(
        status_code=status_code,
        content=_error_body(message=message, error_code=error_code),
        headers=getattr(exc, "headers", None),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception on %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content=_error_body(
            message="Internal server error",
            error_code="INTERNAL_SERVER_ERROR",
        ),
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(RequestValidationError, request_validation_exception_handler)
    app.add_exception_handler(ValueError, value_error_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
