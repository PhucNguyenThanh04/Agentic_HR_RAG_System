from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.api.v1.shared.datetime_utils import AppTimezoneModel
from src.api.v1.shared.enums import NotificationType


class NotificationBase(AppTimezoneModel):
    user_id: uuid.UUID
    title: str = Field(..., min_length=1, max_length=200)
    content: str | None = Field(default=None, max_length=2000)
    type: NotificationType
    object_type: str | None = Field(default=None, min_length=1, max_length=100)
    object_id: str | None = Field(default=None, min_length=1, max_length=120)
    is_read: bool = False
    read_at: datetime | None = None

    @model_validator(mode="after")
    def validate_read_status(self) -> "NotificationBase":
        if self.is_read and not self.read_at:
            raise ValueError("read_at is required when is_read=True")
        return self


class NotificationCreate(BaseModel):
    user_id: uuid.UUID
    title: str = Field(..., min_length=1, max_length=200)
    content: str | None = Field(default=None, max_length=2000)
    type: NotificationType
    object_type: str | None = Field(default=None, min_length=1, max_length=100)
    object_id: str | None = Field(default=None, min_length=1, max_length=120)


class NotificationUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    content: str | None = Field(default=None, max_length=2000)
    type: NotificationType | None = None
    object_type: str | None = Field(default=None, min_length=1, max_length=100)
    object_id: str | None = Field(default=None, min_length=1, max_length=120)
    is_read: bool | None = None
    read_at: datetime | None = None

    @model_validator(mode="after")
    def validate_read_status(self) -> "NotificationUpdate":
        if self.is_read is True and not self.read_at:
            raise ValueError("read_at is required when is_read=True")
        return self


class NotificationRead(NotificationBase):
    model_config = ConfigDict(from_attributes=True)

    notification_id: uuid.UUID
    created_at: datetime


class MarkNotificationReadRequest(BaseModel):
    read_at: datetime | None = None


class NotificationListQuery(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=200)
    user_id: uuid.UUID | None = None
    type: NotificationType | None = None
    is_read: bool | None = None
    created_from: datetime | None = None
    created_to: datetime | None = None

    @model_validator(mode="after")
    def validate_time_window(self) -> "NotificationListQuery":
        if self.created_from and self.created_to and self.created_to < self.created_from:
            raise ValueError("created_to must be on/after created_from")
        return self
