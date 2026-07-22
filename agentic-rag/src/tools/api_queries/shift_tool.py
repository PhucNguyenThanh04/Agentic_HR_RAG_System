from __future__ import annotations

import uuid
from datetime import date

import httpx
from pydantic import ValidationError

from src.integrations.api_service.clients import APIServiceClient
from src.tools.api_queries.errors import build_api_error_result
from src.tools.api_queries.formatters import format_current_shift
from src.tools.api_queries.schemas import ShiftQueryInput
from src.tools.base_tool import BaseTool, ToolResult


class ShiftQueryTool(BaseTool):
    name = "shift_query"
    description = (
        "Tra cứu ca làm từ api-service theo scope của actor. "
        "Dùng khi user hỏi hôm nay/ở một ngày cụ thể làm ca nào, giờ bắt đầu/kết thúc, "
        "ngưỡng đi trễ/về sớm hoặc số phút làm việc yêu cầu. "
        "Bỏ trống employee_id cho chính actor; API kiểm tra mọi target khác."
    )
    usage_hint = "Tra cứu ca làm của actor hoặc nhân viên đích được policy cho phép."
    input_example = '{"as_of":"YYYY-MM-DD"} hoặc {"employee_id":"UUID"}'
    args_schema = ShiftQueryInput

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

    async def run(
        self,
        employee_id: uuid.UUID | str | None = None,
        as_of: date | None = None,
    ) -> ToolResult:
        target_employee_id = str(employee_id or self.employee_id)
        try:
            current_shift = await self.api_service_client.get_employee_current_shift(
                employee_id=target_employee_id,
                as_of=as_of,
                access_token=self.access_token,
            )
        except (ValidationError, httpx.HTTPError) as exc:
            return build_api_error_result(
                exc,
                not_found_observation=(
                    "Không tìm thấy ca làm của nhân viên được yêu cầu trong ngày này."
                ),
            )

        return ToolResult(
            observation=format_current_shift(current_shift),
            metadata={"result_count": 1, "query_complete": True},
        )
