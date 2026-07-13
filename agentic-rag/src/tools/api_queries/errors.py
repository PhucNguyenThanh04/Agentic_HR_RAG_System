from __future__ import annotations

import httpx
from pydantic import ValidationError

from src.tools.base_tool import ToolResult


RETRYABLE_HTTP_STATUS_CODES = {408, 429}


def format_api_error(exc: ValidationError | httpx.HTTPError) -> str:
    if isinstance(exc, ValidationError):
        return f"Tham số truy vấn không hợp lệ: {exc}"

    if isinstance(exc, httpx.HTTPStatusError):
        return (
            "api-service trả lỗi khi truy vấn dữ liệu: "
            f"status={exc.response.status_code}"
        )

    return f"Không gọi được api-service: {exc}"


def build_api_error_result(
    exc: ValidationError | httpx.HTTPError,
    *,
    not_found_observation: str | None = None,
) -> ToolResult:
    """Phân loại lỗi API thành empty/error và quyết định có thể retry."""
    if isinstance(exc, ValidationError):
        return ToolResult(
            observation=format_api_error(exc),
            outcome="error",
            retryable=False,
            metadata={"error_type": "validation"},
        )

    if isinstance(exc, httpx.HTTPStatusError):
        status_code = exc.response.status_code
        if status_code == 404 and not_found_observation:
            return ToolResult(
                observation=not_found_observation,
                outcome="empty",
                retryable=False,
                metadata={
                    "http_status": status_code,
                    "result_count": 0,
                    "query_complete": True,
                },
            )

        retryable = (
            status_code in RETRYABLE_HTTP_STATUS_CODES
            or status_code >= 500
        )
        return ToolResult(
            observation=format_api_error(exc),
            outcome="error",
            retryable=retryable,
            metadata={"http_status": status_code},
        )

    return ToolResult(
        observation=format_api_error(exc),
        outcome="error",
        retryable=True,
        metadata={"error_type": type(exc).__name__},
    )
