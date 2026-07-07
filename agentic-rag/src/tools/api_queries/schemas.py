from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.utils.enums import AttendanceEventType, AttendanceRecordStatus, AttendanceSource


class EmployeeQueryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ShiftQueryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    as_of: date | None = Field(
        default=None,
        description="Ngày cần tra cứu ca làm, định dạng YYYY-MM-DD. Bỏ trống để lấy ca hiện tại.",
    )


class AttendanceQueryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=200)
    shift_id: int | None = Field(default=None, ge=1)
    work_date_from: date | None = Field(
        default=None,
        description="Ngày bắt đầu lọc sổ công, định dạng YYYY-MM-DD.",
    )
    work_date_to: date | None = Field(
        default=None,
        description="Ngày kết thúc lọc sổ công, định dạng YYYY-MM-DD.",
    )
    status: AttendanceRecordStatus | None = Field(
        default=None,
        description=(
            "Trạng thái record: present, late, early_leave, late_and_early_leave, "
            "absent, on_leave, holiday, missing_check_in, missing_check_out, manually_edited."
        ),
    )
    source: AttendanceSource | None = Field(
        default=None,
        description="Nguồn record: face_recognition, manual, edited hoặc system.",
    )
    event_type: AttendanceEventType | None = Field(
        default=None,
        description="Deprecated: attendance_query hiện dùng attendance_records, không lọc theo event_type.",
    )
    accepted: bool | None = Field(
        default=None,
        description="Deprecated: attendance_query hiện dùng attendance_records, không lọc event accepted.",
    )
    event_time_from: datetime | None = Field(
        default=None,
        description="Deprecated: nếu được truyền, tool sẽ map sang work_date_from.",
    )
    event_time_to: datetime | None = Field(
        default=None,
        description="Deprecated: nếu được truyền, tool sẽ map sang work_date_to.",
    )

    @model_validator(mode="after")
    def validate_date_window(self) -> "AttendanceQueryInput":
        if self.work_date_from and self.work_date_to and self.work_date_to < self.work_date_from:
            raise ValueError("work_date_to must be on/after work_date_from")
        if (
            self.event_time_from
            and self.event_time_to
            and self.event_time_to < self.event_time_from
        ):
            raise ValueError("event_time_to must be on/after event_time_from")
        return self
