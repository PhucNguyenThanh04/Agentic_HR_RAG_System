from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.api.v1.shared.datetime_utils import AppTimezoneModel
from src.api.v1.shared.enums import AuditAction


class AuditLogBase(AppTimezoneModel):
    performed_by: uuid.UUID | None = None
    action: AuditAction
    object_type: str = Field(..., min_length=1, max_length=100)
    object_id: str | None = Field(default=None, max_length=120)
    old_value: dict[str, Any] | None = None
    new_value: dict[str, Any] | None = None
    reason: str | None = Field(default=None, max_length=1000)
    ip_address: str | None = Field(default=None, max_length=64)
    user_agent: str | None = Field(default=None, max_length=1000)


class AuditLogCreate(AuditLogBase):
    pass


class AuditLogRead(AuditLogBase):
    model_config = ConfigDict(from_attributes=True)

    log_id: uuid.UUID
    created_at: datetime


class AuditLogListQuery(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=200)
    performed_by: uuid.UUID | None = None
    action: AuditAction | None = None
    object_type: str | None = Field(default=None, min_length=1, max_length=100)
    object_id: str | None = Field(default=None, max_length=120)
    created_from: datetime | None = None
    created_to: datetime | None = None

    @model_validator(mode="after")
    def validate_time_window(self) -> "AuditLogListQuery":
        if self.created_from and self.created_to and self.created_to < self.created_from:
            raise ValueError("created_to must be on/after created_from")
        return self
