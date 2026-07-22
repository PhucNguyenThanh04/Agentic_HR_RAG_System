from __future__ import annotations

import uuid

import httpx
from pydantic import ValidationError

from src.integrations.api_service.clients import APIServiceClient
from src.tools.api_queries.errors import build_api_error_result
from src.tools.api_queries.formatters import format_employee
from src.tools.api_queries.schemas import EmployeeQueryInput
from src.tools.base_tool import BaseTool, ToolResult


class EmployeeQueryTool(BaseTool):
    name = "employee_query"
    description = (
        "Tra cứu hồ sơ nhân viên từ api-service theo scope của actor. "
        "Dùng khi cần biết mã nhân viên, họ tên, trạng thái, phòng ban, chức vụ, quản lý, "
        "số điện thoại, ngày vào làm hoặc ngày nghỉ việc. "
        "Bỏ trống employee_id cho chính actor; API kiểm tra mọi target khác."
    )
    usage_hint = "Tra cứu hồ sơ của actor hoặc nhân viên đích được policy cho phép."
    input_example = '{} hoặc {"employee_id":"UUID"}'
    args_schema = EmployeeQueryInput

    def __init__(
        self,
        api_service_client: APIServiceClient,
        employee_id: str,
        user_role: str,
        access_token: str,
    ) -> None:
        self.api_service_client = api_service_client
        self.employee_id = employee_id
        self.user_role = user_role
        self.access_token = access_token

    async def run(self, employee_id: uuid.UUID | str | None = None) -> ToolResult:
        target_employee_id = str(employee_id or self.employee_id)
        try:
            employee = await self.api_service_client.get_employee(
                target_employee_id,
                access_token=self.access_token,
            )
        except (ValidationError, httpx.HTTPError) as exc:
            return build_api_error_result(
                exc,
                not_found_observation="Không tìm thấy hồ sơ nhân viên được yêu cầu.",
            )

        return ToolResult(
            observation=format_employee(employee),
            metadata={"result_count": 1, "query_complete": True},
        )
