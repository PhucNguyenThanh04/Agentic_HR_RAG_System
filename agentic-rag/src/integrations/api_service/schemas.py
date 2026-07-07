import uuid
from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.utils.datetime_utils import AppTimezoneModel
from src.utils.enums import (
    AttendanceRecordStatus,
    AttendanceSource,
    EmployeeStatus,
)


class APIServerPaths:
    EMPLOYEE_BY_ID = "/api/v1/employees/{employee_id}"
    EMPLOYEE_CURRENT_SHIFT = "/api/v1/employees/{employee_id}/current-shift"
    ATTENDANCE_RECORDS = "/api/v1/attendance/records"


class EmployeeRead(AppTimezoneModel):
    model_config = ConfigDict(from_attributes=True)

    employee_id: uuid.UUID
    user_id: uuid.UUID | None = None
    registered_by: uuid.UUID | None = None
    employee_code: str
    full_name: str
    phone: str | None = None
    avatar_url: str | None = None
    department_id: int | None = None
    position_id: int | None = None
    manager_id: uuid.UUID | None = None
    date_of_birth: date | None = None
    gender: str | None = None
    address: str | None = None
    hire_date: date | None = None
    resignation_date: date | None = None
    status: EmployeeStatus
    created_at: datetime
    updated_at: datetime


class WorkShiftRead(AppTimezoneModel):
    model_config = ConfigDict(from_attributes=True)

    shift_id: int
    name: str
    code: str | None = None
    start_time: time
    end_time: time
    is_overnight: bool = False
    late_threshold_minutes: int = 0
    early_leave_threshold_minutes: int = 0
    required_work_minutes: int | None = None
    is_active: bool = True
    created_at: datetime
    updated_at: datetime


class CurrentShiftRead(BaseModel):
    assignment_id: int
    employee_id: uuid.UUID
    effective_date: date
    end_date: date | None = None
    shift: WorkShiftRead


# attendance record
class AttendanceRecordListQuery(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=200)
    employee_id: uuid.UUID | None = None
    shift_id: int | None = Field(default=None, ge=1)
    work_date_from: date | None = None
    work_date_to: date | None = None
    status: AttendanceRecordStatus | None = None
    source: AttendanceSource | None = None

    @model_validator(mode="after")
    def validate_date_window(self) -> "AttendanceRecordListQuery":
        if self.work_date_from and self.work_date_to and self.work_date_to < self.work_date_from:
            raise ValueError("work_date_to must be on/after work_date_from")
        return self


class AttendanceRecordBase(AppTimezoneModel):
    employee_id: uuid.UUID
    shift_id: int | None = Field(default=None, ge=1)
    work_date: date
    check_in_time: datetime | None = None
    check_out_time: datetime | None = None
    status: AttendanceRecordStatus
    late_minutes: int = Field(default=0, ge=0)
    early_leave_minutes: int = Field(default=0, ge=0)
    worked_minutes: int = Field(default=0, ge=0)
    source: AttendanceSource = AttendanceSource.face_recognition
    notes: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_check_times(self) -> "AttendanceRecordBase":
        if self.check_in_time and self.check_out_time and self.check_out_time < self.check_in_time:
            raise ValueError("check_out_time must be on/after check_in_time")
        return self


class AttendanceRecordRead(AttendanceRecordBase):
    model_config = ConfigDict(from_attributes=True)

    record_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
