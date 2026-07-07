from __future__ import annotations

import re
import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator

from src.api.v1.shared.datetime_utils import AppTimezoneModel


EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
PHONE_PATTERN = r"^\+?[0-9]{8,15}$"


class OnboardingSessionStatus(str, Enum):
    pending = "pending"
    ready_to_commit = "ready_to_commit"
    committed = "committed"
    cancelled = "cancelled"
    failed = "failed"
    expired = "expired"


class EmployeeOnboardingStartSessionRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field(..., min_length=1, max_length=120)
    department_id: int = Field(..., ge=1)
    position_id: int = Field(..., ge=1)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not EMAIL_PATTERN.match(normalized):
            raise ValueError("email is not valid")
        return normalized

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("full_name must not be blank")
        return normalized
    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, value: str) -> str:
        if not any(ch.isalpha() for ch in value):
            raise ValueError("Password must include at least one letter")
        if not any(ch.isdigit() for ch in value):
            raise ValueError("Password must include at least one digit")
        return value



class EmployeeOnboardingStartSessionResponse(AppTimezoneModel):
    session_id: str
    status: OnboardingSessionStatus
    expires_at: datetime
    min_required_photos: int = 3
    current_valid_photos: int = 0


class EmployeeOnboardingPhotoUploadResponse(BaseModel):
    session_id: str
    accepted: bool
    reason: str | None = None
    quality_score: float | None = None
    valid_photo_count: int = 0
    min_required_photos: int = 3
    ready_to_commit: bool = False


class EmployeeOnboardingCommitRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=200)


class EmployeeOnboardingCommitResponse(BaseModel):
    session_id: str
    status: OnboardingSessionStatus
    user_id: uuid.UUID
    employee_id: uuid.UUID
    employee_code: str
    face_profile_id: uuid.UUID | None = None
    vectors_stored: int | None = None


class EmployeeOnboardingCancelResponse(BaseModel):
    session_id: str
    cancelled: bool
    status: OnboardingSessionStatus


class EmployeeOnboardingSessionDetailResponse(AppTimezoneModel):
    session_id: str
    status: OnboardingSessionStatus
    email: str
    full_name: str
    department_id: int
    position_id: int
    employee_code: str | None = None
    valid_photo_count: int = 0
    min_required_photos: int = 3
    ready_to_commit: bool = False
    last_error: str | None = None
    expires_at: datetime
    created_at: datetime
    updated_at: datetime


# Stored structure for Redis/session cache.
class EmployeeOnboardingSessionState(BaseModel):
    session_id: str
    status: OnboardingSessionStatus = OnboardingSessionStatus.pending
    email: str
    password_hash: str
    full_name: str
    department_id: int
    position_id: int
    employee_code: str | None = None
    valid_photo_count: int = 0
    min_required_photos: int = 3
    last_error: str | None = None
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime
    expires_at: datetime
