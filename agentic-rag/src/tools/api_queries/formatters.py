from __future__ import annotations

from src.integrations.api_service.schemas import (
    AttendanceRecordListQuery,
    AttendanceRecordRead,
    CurrentShiftRead,
    EmployeeRead,
)
from src.utils.enums import AttendanceRecordStatus


def _format_time(value) -> str:
    if value is None:
        return "-"
    return value.strftime("%H:%M:%S")


def format_employee(employee: EmployeeRead) -> str:
    return "\n".join(
        [
            "Hồ sơ nhân viên:",
            f"- employee_id: {employee.employee_id}",
            f"- employee_code: {employee.employee_code}",
            f"- full_name: {employee.full_name}",
            f"- status: {employee.status.value}",
            f"- department_id: {employee.department_id}",
            f"- position_id: {employee.position_id}",
            f"- manager_id: {employee.manager_id}",
            f"- phone: {employee.phone}",
            f"- hire_date: {employee.hire_date}",
            f"- resignation_date: {employee.resignation_date}",
        ]
    )


def format_current_shift(current_shift: CurrentShiftRead) -> str:
    shift = current_shift.shift
    code = f" ({shift.code})" if shift.code else ""
    overnight = "qua đêm" if shift.is_overnight else "trong ngày"
    return "\n".join(
        [
            "Ca làm của nhân viên:",
            f"- employee_id: {current_shift.employee_id}",
            f"- assignment_id: {current_shift.assignment_id}",
            f"- effective_date: {current_shift.effective_date}",
            f"- end_date: {current_shift.end_date}",
            f"- shift: {shift.name}{code}",
            f"- time: {shift.start_time} - {shift.end_time} ({overnight})",
            f"- late_threshold_minutes: {shift.late_threshold_minutes}",
            f"- early_leave_threshold_minutes: {shift.early_leave_threshold_minutes}",
            f"- required_work_minutes: {shift.required_work_minutes}",
        ]
    )


def format_attendance_records(
    records: list[AttendanceRecordRead],
    query: AttendanceRecordListQuery,
) -> str:
    if not records:
        return "Không tìm thấy attendance record phù hợp với bộ lọc."

    lines = [
        "attendance_records chính thức từ sổ công. Chỉ dùng số liệu bên dưới, không suy diễn.",
        f"page={query.page}; page_size={query.page_size}; returned={len(records)}",
    ]

    max_records_to_show = 30
    visible_records = records[:max_records_to_show]
    status_value = query.status.value if query.status is not None else None

    if status_value in {
        AttendanceRecordStatus.late.value,
        AttendanceRecordStatus.late_and_early_leave.value,
    }:
        lines.append("fields: index|work_date|late_minutes|check_in_time")
        for index, record in enumerate(visible_records, start=1):
            lines.append(
                f"{index}|{record.work_date}|late={record.late_minutes}|"
                f"in={_format_time(record.check_in_time)}"
            )
    elif status_value == AttendanceRecordStatus.early_leave.value:
        lines.append("fields: index|work_date|early_leave_minutes|check_out_time")
        for index, record in enumerate(visible_records, start=1):
            lines.append(
                f"{index}|{record.work_date}|early={record.early_leave_minutes}|"
                f"out={_format_time(record.check_out_time)}"
            )
    else:
        lines.append(
            "fields: index|work_date|status|check_in|check_out|late|early|worked"
        )
        for index, record in enumerate(visible_records, start=1):
            lines.append(
                f"{index}|{record.work_date}|{record.status.value}|"
                f"in={_format_time(record.check_in_time)}|"
                f"out={_format_time(record.check_out_time)}|"
                f"late={record.late_minutes}|early={record.early_leave_minutes}|"
                f"worked={record.worked_minutes}"
            )

    if len(records) > max_records_to_show:
        lines.append(
            f"Còn {len(records) - max_records_to_show} record chưa hiển thị. "
            f"Dùng page={query.page + 1} để xem thêm."
        )

    return "\n".join(lines)
