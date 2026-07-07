from __future__ import annotations

import httpx
from pydantic import ValidationError


def format_api_error(exc: ValidationError | httpx.HTTPError) -> str:
    if isinstance(exc, ValidationError):
        return f"Tham số truy vấn không hợp lệ: {exc}"

    if isinstance(exc, httpx.HTTPStatusError):
        return (
            "api-service trả lỗi khi truy vấn dữ liệu: "
            f"status={exc.response.status_code}"
        )

    return f"Không gọi được api-service: {exc}"
