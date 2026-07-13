from __future__ import annotations

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
        "Tra cứu hồ sơ của nhân viên hiện tại từ api-service. "
        "Dùng khi cần biết mã nhân viên, họ tên, trạng thái, phòng ban, chức vụ, quản lý, "
        "số điện thoại, ngày vào làm hoặc ngày nghỉ việc. "
        "Không nhận employee_id từ LLM và không truy vấn nhân viên khác."
    )
    usage_hint = "Tra cứu hồ sơ nhân viên hiện tại."
    input_example = "{}"
    args_schema = EmployeeQueryInput

    def __init__(
        self,
        api_service_client: APIServiceClient,
        employee_id: str,
        user_role: str,
    ) -> None:
        self.api_service_client = api_service_client
        self.employee_id = employee_id
        self.user_role = user_role

    async def run(self) -> ToolResult:
        try:
            employee = await self.api_service_client.get_employee(self.employee_id)
        except (ValidationError, httpx.HTTPError) as exc:
            return build_api_error_result(
                exc,
                not_found_observation="Không tìm thấy hồ sơ nhân viên hiện tại.",
            )

        return ToolResult(
            observation=format_employee(employee),
            metadata={"result_count": 1, "query_complete": True},
        )
