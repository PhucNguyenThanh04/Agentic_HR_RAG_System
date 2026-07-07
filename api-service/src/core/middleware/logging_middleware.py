from __future__ import annotations

import logging
import time
from uuid import uuid4

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("uvicorn.error")

REQUEST_ID_HEADER = "X-Request-ID"


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid4())
        request.state.request_id = request_id

        method = request.method
        path = request.url.path
        client_host = request.client.host if request.client else "unknown"
        start_time = time.perf_counter()

        logger.info(
            "request_started request_id=%s method=%s path=%s client=%s",
            request_id,
            method,
            path,
            client_host,
        )

        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.exception(
                "request_failed request_id=%s method=%s path=%s duration_ms=%.2f",
                request_id,
                method,
                path,
                duration_ms,
            )
            raise

        duration_ms = (time.perf_counter() - start_time) * 1000
        response.headers[REQUEST_ID_HEADER] = request_id

        logger.info(
            "request_finished request_id=%s method=%s path=%s status_code=%s duration_ms=%.2f",
            request_id,
            method,
            path,
            response.status_code,
            duration_ms,
        )
        return response
