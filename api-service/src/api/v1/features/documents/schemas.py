from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.api.v1.shared.datetime_utils import AppTimezoneModel
from src.api.v1.shared.enums import DocumentStatus


class DocumentBase(AppTimezoneModel):
    title: str = Field(..., min_length=1, max_length=300)
    file_name: str = Field(..., min_length=1, max_length=255)
    file_url: str = Field(..., min_length=1, max_length=500)
    file_type: str = Field(..., min_length=1, max_length=50)
    uploaded_by: uuid.UUID | None = None
    allowed_roles: list[str] = Field(default_factory=list)
    status: DocumentStatus = DocumentStatus.processing
    chunk_count: int = Field(default=0, ge=0)
    qdrant_collection: str = Field(..., min_length=1, max_length=200)

    @field_validator("title", "file_name", "file_url", "file_type", "qdrant_collection")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be blank")
        return normalized

    @field_validator("allowed_roles")
    @classmethod
    def validate_allowed_roles(cls, value: list[str]) -> list[str]:
        normalized = [role.strip() for role in value if role.strip()]
        if len(normalized) != len(set(normalized)):
            raise ValueError("allowed_roles must not contain duplicates")
        return normalized


class DocumentCreate(DocumentBase):
    pass


class DocumentUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    file_name: str | None = Field(default=None, min_length=1, max_length=255)
    file_url: str | None = Field(default=None, min_length=1, max_length=500)
    file_type: str | None = Field(default=None, min_length=1, max_length=50)
    uploaded_by: uuid.UUID | None = None
    allowed_roles: list[str] | None = None
    status: DocumentStatus | None = None
    chunk_count: int | None = Field(default=None, ge=0)
    qdrant_collection: str | None = Field(default=None, min_length=1, max_length=200)

    @field_validator("title", "file_name", "file_url", "file_type", "qdrant_collection")
    @classmethod
    def validate_required_text(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be blank")
        return normalized

    @field_validator("allowed_roles")
    @classmethod
    def validate_allowed_roles(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return value
        normalized = [role.strip() for role in value if role.strip()]
        if len(normalized) != len(set(normalized)):
            raise ValueError("allowed_roles must not contain duplicates")
        return normalized


class DocumentRead(DocumentBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class DocumentListQuery(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=200)
    search: str | None = Field(default=None, min_length=1, max_length=120)
    uploaded_by: uuid.UUID | None = None
    allowed_role: str | None = Field(default=None, min_length=1, max_length=50)
    status: DocumentStatus | None = None
    file_type: str | None = Field(default=None, min_length=1, max_length=50)
    created_from: datetime | None = None
    created_to: datetime | None = None

    @model_validator(mode="after")
    def validate_time_window(self) -> "DocumentListQuery":
        if self.created_from and self.created_to and self.created_to < self.created_from:
            raise ValueError("created_to must be on/after created_from")
        return self
