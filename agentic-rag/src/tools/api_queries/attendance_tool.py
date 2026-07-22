from __future__ import annotations

import uuid
from datetime import date

import httpx
from pydantic import ValidationError

from src.integrations.api_service.clients import APIServiceClient
from src.integrations.api_service.schemas import AttendanceRecordListQuery
from src.tools.api_queries.errors import build_api_error_result
from src.tools.api_queries.formatters import format_attendance_records
from src.tools.api_queries.schemas import AttendanceQueryInput
from src.tools.base_tool import BaseTool, ToolResult
from src.utils.enums import AttendanceRecordStatus, AttendanceSource


class AttendanceQueryTool(BaseTool):
    name = "attendance_query"
    description = (
        "Tra cứu attendance record chính thức theo scope của actor. "
        "Dùng khi user hỏi ngày công, check-in/check-out, đi trễ, về sớm, số phút làm việc, "
        "trạng thái chấm công hoặc dữ liệu công trong một khoảng ngày. "
        "Bỏ trống employee_id cho chính actor; API kiểm tra mọi target khác."
    )
    usage_hint = "Tra cứu chấm công của actor hoặc nhân viên đích được policy cho phép."
    input_example = (
        '{"employee_id":"UUID","work_date_from":"YYYY-MM-DD",'
        '"work_date_to":"YYYY-MM-DD",'
        '"status":"present|late|early_leave|late_and_early_leave|absent|on_leave|'
        'holiday|missing_check_in|missing_check_out|manually_edited"} hoặc {}'
    )
    args_schema = AttendanceQueryInput

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
        page: int = 1,
        page_size: int = 20,
        shift_id: int | None = None,
        work_date_from: date | None = None,
        work_date_to: date | None = None,
        status: AttendanceRecordStatus | None = None,
        source: AttendanceSource | None = None,
    ) -> ToolResult:
        target_employee_id = str(employee_id or self.employee_id)
        try:
            query = AttendanceRecordListQuery(
                page=page,
                page_size=page_size,
                employee_id=target_employee_id,
                shift_id=shift_id,
                work_date_from=work_date_from,
                work_date_to=work_date_to,
                status=status,
                source=source,
            )
            records = await self.api_service_client.list_attendance_records(
                query,
                access_token=self.access_token,
            )
        except (ValidationError, httpx.HTTPError) as exc:
            return build_api_error_result(exc)

        output = format_attendance_records(records, query)
        if not records:
            return ToolResult(
                observation=output,
                outcome="empty",
                metadata={
                    "result_count": 0,
                    "query_complete": True,
                },
            )

        return ToolResult(
            observation=output,
            metadata={
                "result_count": len(records),
                "query_complete": len(records) < query.page_size,
            },
        )
