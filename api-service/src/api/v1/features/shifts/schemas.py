from __future__ import annotations

import uuid
from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.api.v1.shared.datetime_utils import AppTimezoneModel


class WorkShiftBase(AppTimezoneModel):
    name: str = Field(..., min_length=1, max_length=100)
    code: str | None = Field(default=None, min_length=1, max_length=30)
    start_time: time
    end_time: time
    is_overnight: bool = False
    late_threshold_minutes: int = Field(default=0, ge=0, le=240)
    early_leave_threshold_minutes: int = Field(default=0, ge=0, le=240)
    required_work_minutes: int | None = Field(default=None, ge=1, le=24 * 60)
    is_active: bool = True

    @model_validator(mode="after")
    def validate_shift_times(self) -> "WorkShiftBase":
        if self.start_time == self.end_time:
            raise ValueError("start_time and end_time must not be equal")

        if self.is_overnight:
            if self.end_time > self.start_time:
                raise ValueError("Overnight shift must have end_time earlier than start_time")
        else:
            if self.end_time < self.start_time:
                raise ValueError("Non-overnight shift must have end_time later than start_time")

        return self


class WorkShiftCreate(WorkShiftBase):
    pass


class WorkShiftUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    code: str | None = Field(default=None, min_length=1, max_length=30)
    start_time: time | None = None
    end_time: time | None = None
    is_overnight: bool | None = None
    late_threshold_minutes: int | None = Field(default=None, ge=0, le=240)
    early_leave_threshold_minutes: int | None = Field(default=None, ge=0, le=240)
    required_work_minutes: int | None = Field(default=None, ge=1, le=24 * 60)
    is_active: bool | None = None


class WorkShiftRead(WorkShiftBase):
    model_config = ConfigDict(from_attributes=True)

    shift_id: int
    created_at: datetime
    updated_at: datetime


class EmployeeShiftAssignmentBase(AppTimezoneModel):
    employee_id: uuid.UUID
    shift_id: int = Field(..., ge=1)
    effective_date: date
    end_date: date | None = None

    @model_validator(mode="after")
    def validate_effective_window(self) -> "EmployeeShiftAssignmentBase":
        if self.end_date and self.end_date < self.effective_date:
            raise ValueError("end_date must be on/after effective_date")
        return self


class EmployeeShiftAssignmentCreate(EmployeeShiftAssignmentBase):
    created_by: uuid.UUID | None = None


class EmployeeShiftAssignmentCreateForEmployee(BaseModel):
    shift_id: int = Field(..., ge=1)
    effective_date: date
    end_date: date | None = None

    @model_validator(mode="after")
    def validate_effective_window(self) -> "EmployeeShiftAssignmentCreateForEmployee":
        if self.end_date and self.end_date < self.effective_date:
            raise ValueError("end_date must be on/after effective_date")
        return self


class EmployeeShiftAssignmentUpdate(BaseModel):
    shift_id: int | None = Field(default=None, ge=1)
    effective_date: date | None = None
    end_date: date | None = None

    @model_validator(mode="after")
    def validate_effective_window(self) -> "EmployeeShiftAssignmentUpdate":
        if self.effective_date and self.end_date and self.end_date < self.effective_date:
            raise ValueError("end_date must be on/after effective_date")
        return self


class ChangeShiftPayload(BaseModel):
    new_shift_id: int = Field(..., ge=1)
    effective_date: date
    reason: str | None = Field(default=None, max_length=500)


class EmployeeShiftAssignmentRead(EmployeeShiftAssignmentBase):
    model_config = ConfigDict(from_attributes=True)

    assignment_id: int
    created_by: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime


class CurrentShiftRead(BaseModel):
    assignment_id: int
    employee_id: uuid.UUID
    effective_date: date
    end_date: date | None = None
    shift: WorkShiftRead


class HolidayBase(AppTimezoneModel):
    name: str = Field(..., min_length=1, max_length=100)
    holiday_date: date
    description: str | None = Field(default=None, max_length=500)


class HolidayCreate(HolidayBase):
    pass


class HolidayUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    holiday_date: date | None = None
    description: str | None = Field(default=None, max_length=500)


class HolidayRead(HolidayBase):
    model_config = ConfigDict(from_attributes=True)

    holiday_id: int
    created_at: datetime
    updated_at: datetime


class ShiftListQuery(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=200)
    is_active: bool | None = None
    code: str | None = Field(default=None, min_length=1, max_length=30)
