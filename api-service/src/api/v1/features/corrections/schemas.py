from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.api.v1.shared.datetime_utils import AppTimezoneModel
from src.api.v1.shared.enums import ApprovalAction, CorrectionRequestStatus


class AttendanceCorrectionRequestBase(AppTimezoneModel):
    employee_id: uuid.UUID
    attendance_record_id: uuid.UUID | None = None
    requested_check_in: datetime | None = None
    requested_check_out: datetime | None = None
    reason: str = Field(..., min_length=3, max_length=1000)
    status: CorrectionRequestStatus = CorrectionRequestStatus.pending
    reviewed_by: uuid.UUID | None = None
    reviewed_at: datetime | None = None
    rejection_reason: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_request_values(self) -> "AttendanceCorrectionRequestBase":
        if not self.requested_check_in and not self.requested_check_out:
            raise ValueError("At least one of requested_check_in or requested_check_out is required")
        if self.requested_check_in and self.requested_check_out and self.requested_check_out < self.requested_check_in:
            raise ValueError("requested_check_out must be on/after requested_check_in")
        if self.status == CorrectionRequestStatus.rejected and not self.rejection_reason:
            raise ValueError("rejection_reason is required when status=rejected")
        return self


class AttendanceCorrectionRequestCreate(BaseModel):
    attendance_record_id: uuid.UUID | None = None
    requested_check_in: datetime | None = None
    requested_check_out: datetime | None = None
    reason: str = Field(..., min_length=3, max_length=1000)

    @model_validator(mode="after")
    def validate_request_values(self) -> "AttendanceCorrectionRequestCreate":
        if not self.requested_check_in and not self.requested_check_out:
            raise ValueError("At least one of requested_check_in or requested_check_out is required")
        if self.requested_check_in and self.requested_check_out and self.requested_check_out < self.requested_check_in:
            raise ValueError("requested_check_out must be on/after requested_check_in")
        return self


class AttendanceCorrectionRequestUpdate(BaseModel):
    requested_check_in: datetime | None = None
    requested_check_out: datetime | None = None
    reason: str | None = Field(default=None, min_length=3, max_length=1000)
    status: CorrectionRequestStatus | None = None
    reviewed_by: uuid.UUID | None = None
    reviewed_at: datetime | None = None
    rejection_reason: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_request_values(self) -> "AttendanceCorrectionRequestUpdate":
        if self.requested_check_in and self.requested_check_out and self.requested_check_out < self.requested_check_in:
            raise ValueError("requested_check_out must be on/after requested_check_in")
        if self.status == CorrectionRequestStatus.rejected and not self.rejection_reason:
            raise ValueError("rejection_reason is required when status=rejected")
        return self


class AttendanceCorrectionRequestRead(AttendanceCorrectionRequestBase):
    model_config = ConfigDict(from_attributes=True)

    request_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class AttendanceCorrectionLogBase(AppTimezoneModel):
    correction_request_id: uuid.UUID
    reviewer_id: uuid.UUID
    action: ApprovalAction
    comment: str | None = Field(default=None, max_length=1000)
    old_check_in: datetime | None = None
    old_check_out: datetime | None = None
    new_check_in: datetime | None = None
    new_check_out: datetime | None = None

    @model_validator(mode="after")
    def validate_time_snapshot(self) -> "AttendanceCorrectionLogBase":
        if self.old_check_in and self.old_check_out and self.old_check_out < self.old_check_in:
            raise ValueError("old_check_out must be on/after old_check_in")
        if self.new_check_in and self.new_check_out and self.new_check_out < self.new_check_in:
            raise ValueError("new_check_out must be on/after new_check_in")
        return self


class AttendanceCorrectionLogCreate(AttendanceCorrectionLogBase):
    pass


class AttendanceCorrectionLogRead(AttendanceCorrectionLogBase):
    model_config = ConfigDict(from_attributes=True)

    log_id: int
    created_at: datetime


class ReviewCorrectionRequest(BaseModel):
    action: ApprovalAction
    comment: str | None = Field(default=None, max_length=1000)
    approved_check_in: datetime | None = None
    approved_check_out: datetime | None = None
    rejection_reason: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_review_payload(self) -> "ReviewCorrectionRequest":
        if self.action == ApprovalAction.rejected and not self.rejection_reason:
            raise ValueError("rejection_reason is required when action=rejected")

        if self.approved_check_in and self.approved_check_out and self.approved_check_out < self.approved_check_in:
            raise ValueError("approved_check_out must be on/after approved_check_in")

        if self.action == ApprovalAction.approved and not self.approved_check_in and not self.approved_check_out:
            raise ValueError("At least one approved check time is required when action=approved")

        return self


class CorrectionListQuery(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=200)
    employee_id: uuid.UUID | None = None
    status: CorrectionRequestStatus | None = None
    requested_from: datetime | None = None
    requested_to: datetime | None = None

    @model_validator(mode="after")
    def validate_time_window(self) -> "CorrectionListQuery":
        if self.requested_from and self.requested_to and self.requested_to < self.requested_from:
            raise ValueError("requested_to must be on/after requested_from")
        return self
