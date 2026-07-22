from __future__ import annotations

from datetime import date
from typing import Any

import httpx

from src.integrations.api_service.schemas import (
    APIServerPaths,
    AttendanceRecordListQuery,
    AttendanceRecordRead,
    AuthenticatedUserRead,
    CurrentShiftRead,
    EmployeeRead,
)

from src.core.setup_logging import setup_logger

logger = setup_logger(__name__)


class APIServiceClient:
    def __init__(self, http_client: httpx.AsyncClient) -> None:
        self._http = http_client

    async def validate_actor_context(
        self,
        *,
        access_token: str,
        expected_employee_id: str,
        expected_role: str,
    ) -> None:
        user_data = await self._request_json(
            method="GET",
            path=APIServerPaths.AUTH_ME,
            access_token=access_token,
        )
        employee_data = await self._request_json(
            method="GET",
            path=APIServerPaths.EMPLOYEE_ME,
            access_token=access_token,
        )
        user = AuthenticatedUserRead.model_validate(user_data)
        employee = EmployeeRead.model_validate(employee_data)

        if str(employee.employee_id) != expected_employee_id:
            raise ValueError("Authenticated employee context does not match request")
        if employee.user_id != user.user_id:
            raise ValueError("Authenticated user and employee context do not match")
        if user.role_name != expected_role:
            raise ValueError("Authenticated role context does not match request")

    async def get_employee(
        self,
        employee_id: str,
        *,
        access_token: str,
    ) -> EmployeeRead:
        data = await self._request_json(
            method="GET",
            path=APIServerPaths.EMPLOYEE_BY_ID.format(employee_id=employee_id),
            access_token=access_token,
        )
        return EmployeeRead.model_validate(data)

    async def get_employee_current_shift(
        self,
        employee_id: str,
        as_of: date | None = None,
        *,
        access_token: str,
    ) -> CurrentShiftRead:
        params = {"as_of": as_of.isoformat()} if as_of is not None else None
        data = await self._request_json(
            method="GET",
            path=APIServerPaths.EMPLOYEE_CURRENT_SHIFT.format(employee_id=employee_id),
            params=params,
            access_token=access_token,
        )
        return CurrentShiftRead.model_validate(data)

    async def list_attendance_records(
        self,
        query: AttendanceRecordListQuery | None = None,
        *,
        access_token: str,
    ) -> list[AttendanceRecordRead]:
        query = query or AttendanceRecordListQuery()
        data = await self._request_json(
            method="GET",
            path=APIServerPaths.ATTENDANCE_RECORDS,
            params=query.model_dump(mode="json", exclude_none=True),
            access_token=access_token,
        )
        return [AttendanceRecordRead.model_validate(item) for item in data]

    async def _request_json(
        self,
        *,
        method: str,
        path: str,
        access_token: str,
        **kwargs: Any,
    ) -> Any:
        headers = dict(kwargs.pop("headers", {}))
        headers.update(self._authorization_header(access_token))

        try:
            response = await self._http.request(method, path, headers=headers, **kwargs)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "api-service returned error: method=%s path=%s status=%s",
                method,
                path,
                exc.response.status_code,
            )
            raise
        except httpx.HTTPError:
            logger.exception("api-service request failed: method=%s path=%s", method, path)
            raise

        logger.debug(
            "api-service response: method=%s path=%s status=%s",
            method,
            path,
            response.status_code,
        )
        return response.json()

    @staticmethod
    def _authorization_header(access_token: str) -> dict[str, str]:
        token = access_token.strip()
        if not token:
            raise ValueError("access_token must not be empty")
        return {"Authorization": f"Bearer {token}"}
