from __future__ import annotations

from datetime import date
from typing import Any

import httpx

from src.integrations.api_service.schemas import (
    APIServerPaths,
    AttendanceRecordListQuery,
    AttendanceRecordRead,
    CurrentShiftRead,
    EmployeeRead,
)

from src.core.settings import get_settings
from src.core.setup_logging import setup_logger

logger = setup_logger(__name__)
settings = get_settings()


class APIServiceClient:
    def __init__(self, http_client: httpx.AsyncClient) -> None:
        self._http = http_client
        self._api_key = settings.rag_api_key
        self._default_headers = {"Rag-API-Key": self._api_key} if self._api_key else {}

    async def get_employee(self, employee_id: str) -> EmployeeRead:
        data = await self._request_json(
            method="GET",
            path=APIServerPaths.EMPLOYEE_BY_ID.format(employee_id=employee_id),
        )
        return EmployeeRead.model_validate(data)

    async def get_employee_current_shift(
        self,
        employee_id: str,
        as_of: date | None = None,
    ) -> CurrentShiftRead:
        params = {"as_of": as_of.isoformat()} if as_of is not None else None
        data = await self._request_json(
            method="GET",
            path=APIServerPaths.EMPLOYEE_CURRENT_SHIFT.format(employee_id=employee_id),
            params=params,
        )
        return CurrentShiftRead.model_validate(data)

    async def list_attendance_records(
        self,
        query: AttendanceRecordListQuery | None = None,
    ) -> list[AttendanceRecordRead]:
        query = query or AttendanceRecordListQuery()
        data = await self._request_json(
            method="GET",
            path=APIServerPaths.ATTENDANCE_RECORDS,
            params=query.model_dump(mode="json", exclude_none=True),
        )
        return [AttendanceRecordRead.model_validate(item) for item in data]

    async def _request_json(
        self,
        *,
        method: str,
        path: str,
        require_api_key: bool = True,
        **kwargs: Any,
    ) -> Any:
        headers = dict(kwargs.pop("headers", {}))
        if require_api_key:
            headers.update(self._default_headers)

        try:
            response = await self._http.request(method, path, headers=headers, **kwargs)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "api-service returned error: method=%s path=%s status=%s body=%s",
                method,
                path,
                exc.response.status_code,
                exc.response.text,
            )
            raise
        except httpx.HTTPError:
            logger.exception("api-service request failed: method=%s path=%s", method, path)
            raise

        logger.debug(
            "api-service response: method=%s path=%s status=%s body=%s",
            method,
            path,
            response.status_code,
            response.text,
        )
        return response.json()
