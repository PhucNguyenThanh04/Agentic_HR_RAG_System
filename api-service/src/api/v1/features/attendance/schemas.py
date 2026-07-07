from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.api.v1.shared.datetime_utils import AppTimezoneModel
from src.api.v1.shared.enums import (
    AttendanceEventType,
    AttendanceRecordStatus,
    AttendanceSource,
)


class AttendanceEventBase(AppTimezoneModel):
    employee_id: uuid.UUID | None = None
    event_type: AttendanceEventType
    event_time: datetime
    confidence_score: float | None = Field(default=None, ge=0, le=1)
    anti_spoof_score: float | None = Field(default=None, ge=0, le=1)
    image_url: str | None = Field(default=None, max_length=500)
    raw_result: dict | None = None
    is_accepted: bool = True
    rejection_reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_rejection_reason(self) -> "AttendanceEventBase":
        if not self.is_accepted and not self.rejection_reason:
            raise ValueError("rejection_reason is required when is_accepted=False")
        return self


class AttendanceEventCreate(AttendanceEventBase):
    pass


class AttendanceAIEventCreate(BaseModel):
    employee_id: uuid.UUID
    event_time: datetime | None = None
    confidence_score: float | None = Field(default=None, ge=0, le=1)
    anti_spoof_score: float | None = Field(default=None, ge=0, le=1)
    image_url: str | None = Field(default=None, max_length=500)
    raw_result: dict | None = None


class AttendanceEventRead(AttendanceEventBase):
    model_config = ConfigDict(from_attributes=True)

    event_id: uuid.UUID
    created_at: datetime


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


class AttendanceRecordCreate(AttendanceRecordBase):
    pass


class AttendanceRecordUpdate(BaseModel):
    shift_id: int | None = Field(default=None, ge=1)
    work_date: date | None = None
    check_in_time: datetime | None = None
    check_out_time: datetime | None = None
    status: AttendanceRecordStatus | None = None
    late_minutes: int | None = Field(default=None, ge=0)
    early_leave_minutes: int | None = Field(default=None, ge=0)
    worked_minutes: int | None = Field(default=None, ge=0)
    source: AttendanceSource | None = None
    notes: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_check_times(self) -> "AttendanceRecordUpdate":
        if self.check_in_time and self.check_out_time and self.check_out_time < self.check_in_time:
            raise ValueError("check_out_time must be on/after check_in_time")
        return self


class AttendanceRecordRead(AttendanceRecordBase):
    model_config = ConfigDict(from_attributes=True)

    record_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class AttendanceEventAcceptedResponse(AppTimezoneModel):
    accepted: bool
    reason: str | None = None
    employee_id: uuid.UUID
    event_id: uuid.UUID | None = None
    record_id: uuid.UUID | None = None
    shift_id: int | None = None
    event_type: AttendanceEventType | None = None
    event_time: datetime
    work_date: date | None = None
    check_in_time: datetime | None = None
    check_out_time: datetime | None = None
    late_minutes: int | None = None
    early_leave_minutes: int | None = None
    worked_minutes: int | None = None
    status: AttendanceRecordStatus | None = None
    cooldown_ttl_seconds: int | None = None


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


class AttendanceRecordSummaryQuery(BaseModel):
    employee_id: uuid.UUID | None = None
    shift_id: int | None = Field(default=None, ge=1)
    work_date_from: date | None = None
    work_date_to: date | None = None

    @model_validator(mode="after")
    def validate_date_window(self) -> "AttendanceRecordSummaryQuery":
        if self.work_date_from and self.work_date_to and self.work_date_to < self.work_date_from:
            raise ValueError("work_date_to must be on/after work_date_from")
        return self


class AttendanceRecordSummaryRead(BaseModel):
    total_records: int
    present_days: int
    late_days: int
    absent_days: int


class AttendanceEventListQuery(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=200)
    employee_id: uuid.UUID | None = None
    event_type: AttendanceEventType | None = None
    accepted: bool | None = None
    event_time_from: datetime | None = None
    event_time_to: datetime | None = None

    @model_validator(mode="after")
    def validate_time_window(self) -> "AttendanceEventListQuery":
        if self.event_time_from and self.event_time_to and self.event_time_to < self.event_time_from:
            raise ValueError("event_time_to must be on/after event_time_from")
        return self
