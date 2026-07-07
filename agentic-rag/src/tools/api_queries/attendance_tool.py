from __future__ import annotations

from datetime import date, datetime

import httpx
from pydantic import ValidationError

from src.integrations.api_service.clients import APIServiceClient
from src.integrations.api_service.schemas import AttendanceRecordListQuery
from src.tools.api_queries.errors import format_api_error
from src.tools.api_queries.formatters import format_attendance_records
from src.tools.api_queries.schemas import AttendanceQueryInput
from src.tools.base_tool import BaseTool
from src.utils.enums import AttendanceEventType, AttendanceRecordStatus, AttendanceSource


class AttendanceQueryTool(BaseTool):
    name = "attendance_query"
    description = (
        "Tra cứu attendance record chính thức của nhân viên hiện tại từ api-service. "
        "Dùng khi user hỏi ngày công, check-in/check-out, đi trễ, về sớm, số phút làm việc, "
        "trạng thái chấm công hoặc dữ liệu công trong một khoảng ngày. "
        "Không nhận employee_id từ LLM và không truy vấn nhân viên khác."
    )
    usage_hint = "Tra cứu chấm công, check-in/out, đi trễ/về sớm."
    input_example = (
        '{"work_date_from":"YYYY-MM-DD",'
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
    ) -> None:
        self.api_service_client = api_service_client
        self.employee_id = employee_id
        self.user_role = user_role

    async def run(
        self,
        page: int = 1,
        page_size: int = 20,
        shift_id: int | None = None,
        work_date_from: date | None = None,
        work_date_to: date | None = None,
        status: AttendanceRecordStatus | None = None,
        source: AttendanceSource | None = None,
        event_type: AttendanceEventType | None = None,
        accepted: bool | None = None,
        event_time_from: datetime | None = None,
        event_time_to: datetime | None = None,
    ) -> str:
        try:
            query = AttendanceRecordListQuery(
                page=page,
                page_size=page_size,
                employee_id=self.employee_id,
                shift_id=shift_id,
                work_date_from=work_date_from or (
                    event_time_from.date() if event_time_from else None
                ),
                work_date_to=work_date_to or (
                    event_time_to.date() if event_time_to else None
                ),
                status=status,
                source=source,
            )
            records = await self.api_service_client.list_attendance_records(query)
        except (ValidationError, httpx.HTTPError) as exc:
            return format_api_error(exc)

        output = format_attendance_records(records, query)
        ignored_filters: list[str] = []
        if event_type is not None:
            ignored_filters.append("event_type")
        if accepted is not None:
            ignored_filters.append("accepted")
        if ignored_filters:
            output += (
                "\n\nLưu ý: attendance_query hiện dùng attendance_records chính thức; "
                f"đã bỏ qua filter raw event: {', '.join(ignored_filters)}."
            )
        return output
