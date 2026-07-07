from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.api.v1.shared.datetime_utils import AppTimezoneModel

SETTING_KEY_PATTERN = r"^[a-z][a-z0-9_.-]{1,120}$"


class SystemSettingBase(AppTimezoneModel):
    key: str = Field(
        ...,
        min_length=2,
        max_length=120,
        pattern=SETTING_KEY_PATTERN,
        description="Example: attendance.cooldown_seconds",
    )
    value: dict[str, Any]
    description: str | None = Field(default=None, max_length=1000)
    updated_by: uuid.UUID | None = None

    @field_validator("value")
    @classmethod
    def validate_value_not_empty(cls, value: dict[str, Any]) -> dict[str, Any]:
        if not value:
            raise ValueError("value must not be empty")
        return value


class SystemSettingCreate(SystemSettingBase):
    pass


class SystemSettingUpdate(BaseModel):
    value: dict[str, Any] | None = None
    description: str | None = Field(default=None, max_length=1000)
    updated_by: uuid.UUID | None = None

    @field_validator("value")
    @classmethod
    def validate_value_not_empty(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        if value is None:
            return value
        if not value:
            raise ValueError("value must not be empty")
        return value


class SystemSettingRead(SystemSettingBase):
    model_config = ConfigDict(from_attributes=True)

    setting_id: int
    created_at: datetime
    updated_at: datetime


class SystemSettingItem(BaseModel):
    key: str = Field(..., min_length=2, max_length=120, pattern=SETTING_KEY_PATTERN)
    value: dict[str, Any]
    description: str | None = Field(default=None, max_length=1000)


class SystemSettingBulkUpsertRequest(BaseModel):
    items: list[SystemSettingItem] = Field(..., min_length=1, max_length=500)


class SystemSettingListQuery(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=500)
    key_prefix: str | None = Field(default=None, min_length=1, max_length=120)
    search: str | None = Field(default=None, min_length=1, max_length=120)
