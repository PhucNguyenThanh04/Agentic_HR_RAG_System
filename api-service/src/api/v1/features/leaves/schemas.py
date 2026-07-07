from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.api.v1.shared.datetime_utils import AppTimezoneModel
from src.api.v1.shared.enums import ApprovalAction, LeaveRequestStatus, LeaveTimeType


class LeaveTypeBase(AppTimezoneModel):
    name: str = Field(..., min_length=1, max_length=100)
    code: str | None = Field(default=None, min_length=1, max_length=30)
    is_paid: bool = True
    max_days_per_year: int | None = Field(default=None, ge=0, le=365)
    description: str | None = Field(default=None, max_length=500)
    is_active: bool = True


class LeaveTypeCreate(LeaveTypeBase):
    pass


class LeaveTypeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    code: str | None = Field(default=None, min_length=1, max_length=30)
    is_paid: bool | None = None
    max_days_per_year: int | None = Field(default=None, ge=0, le=365)
    description: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None


class LeaveTypeRead(LeaveTypeBase):
    model_config = ConfigDict(from_attributes=True)

    leave_type_id: int
    created_at: datetime
    updated_at: datetime


class LeaveBalanceItem(BaseModel):
    leave_type_id: int
    name: str
    code: str | None = None
    is_paid: bool
    max_days_per_year: int | None = None
    used_days: float
    remaining_days: float | None = None


class LeaveBalanceRead(BaseModel):
    employee_id: uuid.UUID
    year: int
    total_allowed_days: float
    total_used_days: float
    total_remaining_days: float
    items: list[LeaveBalanceItem]


class LeaveRequestBase(AppTimezoneModel):
    employee_id: uuid.UUID
    leave_type_id: int = Field(..., ge=1)
    start_date: date
    end_date: date
    time_type: LeaveTimeType = LeaveTimeType.full_day
    total_days: float | None = Field(default=None, gt=0)
    reason: str | None = Field(default=None, max_length=1000)
    status: LeaveRequestStatus = LeaveRequestStatus.pending
    approved_by: uuid.UUID | None = None
    approved_at: datetime | None = None
    rejection_reason: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_leave_dates(self) -> "LeaveRequestBase":
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on/after start_date")

        if self.time_type in {LeaveTimeType.morning, LeaveTimeType.afternoon} and self.start_date != self.end_date:
            raise ValueError("Half-day leave (morning/afternoon) must be within one day")

        if self.time_type == LeaveTimeType.custom and self.total_days is None:
            raise ValueError("total_days is required when time_type=custom")

        if self.status == LeaveRequestStatus.rejected and not self.rejection_reason:
            raise ValueError("rejection_reason is required when status=rejected")

        return self


class LeaveRequestCreate(BaseModel):
    leave_type_id: int = Field(..., ge=1)
    start_date: date
    end_date: date
    time_type: LeaveTimeType = LeaveTimeType.full_day
    total_days: float | None = Field(default=None, gt=0)
    reason: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_leave_dates(self) -> "LeaveRequestCreate":
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on/after start_date")
        if self.time_type in {LeaveTimeType.morning, LeaveTimeType.afternoon} and self.start_date != self.end_date:
            raise ValueError("Half-day leave (morning/afternoon) must be within one day")
        if self.time_type == LeaveTimeType.custom and self.total_days is None:
            raise ValueError("total_days is required when time_type=custom")
        return self


class LeaveRequestUpdate(BaseModel):
    leave_type_id: int | None = Field(default=None, ge=1)
    start_date: date | None = None
    end_date: date | None = None
    time_type: LeaveTimeType | None = None
    total_days: float | None = Field(default=None, gt=0)
    reason: str | None = Field(default=None, max_length=1000)
    status: LeaveRequestStatus | None = None
    approved_by: uuid.UUID | None = None
    approved_at: datetime | None = None
    rejection_reason: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_leave_dates(self) -> "LeaveRequestUpdate":
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must be on/after start_date")

        if self.time_type in {LeaveTimeType.morning, LeaveTimeType.afternoon}:
            if self.start_date and self.end_date and self.start_date != self.end_date:
                raise ValueError("Half-day leave (morning/afternoon) must be within one day")

        if self.time_type == LeaveTimeType.custom and self.total_days is None:
            raise ValueError("total_days is required when time_type=custom")

        if self.status == LeaveRequestStatus.rejected and not self.rejection_reason:
            raise ValueError("rejection_reason is required when status=rejected")

        return self


class LeaveRequestRead(LeaveRequestBase):
    model_config = ConfigDict(from_attributes=True)

    request_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class LeaveApprovalLogBase(AppTimezoneModel):
    leave_request_id: uuid.UUID
    approver_id: uuid.UUID
    action: ApprovalAction
    comment: str | None = Field(default=None, max_length=1000)


class LeaveApprovalLogCreate(LeaveApprovalLogBase):
    pass


class LeaveApprovalLogRead(LeaveApprovalLogBase):
    model_config = ConfigDict(from_attributes=True)

    log_id: int
    created_at: datetime


class ReviewLeaveRequest(BaseModel):
    action: ApprovalAction
    comment: str | None = Field(default=None, max_length=1000)
    rejection_reason: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_review_payload(self) -> "ReviewLeaveRequest":
        if self.action == ApprovalAction.rejected and not self.rejection_reason:
            raise ValueError("rejection_reason is required when action=rejected")
        return self


class LeaveRequestListQuery(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=200)
    employee_id: uuid.UUID | None = None
    leave_type_id: int | None = Field(default=None, ge=1)
    status: LeaveRequestStatus | None = None
    start_from: date | None = None
    start_to: date | None = None

    @model_validator(mode="after")
    def validate_date_window(self) -> "LeaveRequestListQuery":
        if self.start_from and self.start_to and self.start_to < self.start_from:
            raise ValueError("start_to must be on/after start_from")
        return self


class LeaveRequestListResponse(BaseModel):
    items: list[LeaveRequestRead]
    total: int
    page: int
    page_size: int
