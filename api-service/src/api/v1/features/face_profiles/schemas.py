from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.api.v1.shared.datetime_utils import AppTimezoneModel
from src.api.v1.shared.enums import FaceProfileStatus


class FaceProfileBase(BaseModel):
    employee_id: uuid.UUID
    status: FaceProfileStatus = FaceProfileStatus.pending
    qdrant_collection: str = Field(..., min_length=1, max_length=120)
    embedding_model: str | None = Field(default=None, max_length=120)
    embedding_version: str | None = Field(default=None, max_length=120)
    registered_by: uuid.UUID | None = None
    revocation_reason: str | None = Field(default=None, max_length=1000)
    revoked_at: datetime | None = None

    @model_validator(mode="after")
    def validate_revocation_fields(self) -> "FaceProfileBase":
        if self.status == FaceProfileStatus.revoked:
            if not self.revoked_at:
                raise ValueError("revoked_at is required when status=revoked")
            if not self.revocation_reason:
                raise ValueError("revocation_reason is required when status=revoked")
        return self


class FaceProfileCreate(BaseModel):
    employee_id: uuid.UUID
    qdrant_collection: str = Field(..., min_length=1, max_length=120)
    registered_by: uuid.UUID | None = None


class FaceProfileUpdate(BaseModel):
    status: FaceProfileStatus | None = None
    qdrant_collection: str | None = Field(default=None, min_length=1, max_length=120)
    embedding_model: str | None = Field(default=None, max_length=120)
    embedding_version: str | None = Field(default=None, max_length=120)
    registered_by: uuid.UUID | None = None
    revocation_reason: str | None = Field(default=None, max_length=1000)
    revoked_at: datetime | None = None

    @model_validator(mode="after")
    def validate_revocation_fields(self) -> "FaceProfileUpdate":
        if self.status == FaceProfileStatus.revoked:
            if not self.revoked_at:
                raise ValueError("revoked_at is required when status=revoked")
            if not self.revocation_reason:
                raise ValueError("revocation_reason is required when status=revoked")
        return self


class FaceProfileRead(AppTimezoneModel):
    model_config = ConfigDict(from_attributes=True)

    profile_id: uuid.UUID
    employee_id: uuid.UUID
    status: FaceProfileStatus
    qdrant_collection: str
    embedding_model: str | None = None
    embedding_version: str | None = None
    registered_by: uuid.UUID | None = None
    revocation_reason: str | None = None
    revoked_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class RevokeFaceProfileRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=1000)


class FaceProfileListQuery(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=200)
    employee_id: uuid.UUID | None = None
    status: FaceProfileStatus | None = None
