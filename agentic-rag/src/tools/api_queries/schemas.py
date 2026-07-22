from __future__ import annotations

import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.utils.enums import AttendanceRecordStatus, AttendanceSource


class EmployeeQueryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    employee_id: uuid.UUID | None = Field(
        default=None,
        description=(
            "Nhân viên đích. Bỏ trống khi người dùng hỏi về chính mình; "
            "API sẽ kiểm tra scope nếu tra cứu nhân viên khác."
        ),
    )


class ShiftQueryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    employee_id: uuid.UUID | None = Field(
        default=None,
        description=(
            "Nhân viên đích. Bỏ trống khi người dùng hỏi về chính mình; "
            "API sẽ kiểm tra scope nếu tra cứu nhân viên khác."
        ),
    )

    as_of: date | None = Field(
        default=None,
        description="Ngày cần tra cứu ca làm, định dạng YYYY-MM-DD. Bỏ trống để lấy ca hiện tại.",
    )


class AttendanceQueryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    employee_id: uuid.UUID | None = Field(
        default=None,
        description=(
            "Nhân viên đích. Bỏ trống khi người dùng hỏi về chính mình; "
            "API sẽ kiểm tra scope nếu tra cứu nhân viên khác."
        ),
    )
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
    @model_validator(mode="after")
    def validate_date_window(self) -> "AttendanceQueryInput":
        if self.work_date_from and self.work_date_to and self.work_date_to < self.work_date_from:
            raise ValueError("work_date_to must be on/after work_date_from")
        return self
