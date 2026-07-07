from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.api.v1.shared.datetime_utils import AppTimezoneModel


class DepartmentBase(AppTimezoneModel):
    name: str = Field(..., min_length=1, max_length=100)
    code: str | None = Field(default=None, min_length=1, max_length=30)
    description: str | None = Field(default=None, max_length=500)
    is_active: bool = True

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("name must not be blank")
        return normalized

    @field_validator("code")
    @classmethod
    def validate_code(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = value.strip()
        if not normalized:
            raise ValueError("code must not be blank")
        return normalized


class DepartmentCreate(DepartmentBase):
    pass


class DepartmentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    code: str | None = Field(default=None, min_length=1, max_length=30)
    description: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = value.strip()
        if not normalized:
            raise ValueError("name must not be blank")
        return normalized

    @field_validator("code")
    @classmethod
    def validate_code(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = value.strip()
        if not normalized:
            raise ValueError("code must not be blank")
        return normalized


class DepartmentRead(DepartmentBase):
    model_config = ConfigDict(from_attributes=True)

    department_id: int
    created_at: datetime
    updated_at: datetime


class AssignDepartmentManagerRequest(BaseModel):
    manager_id: uuid.UUID
    department_id: int = Field(..., ge=1)


class UnassignDepartmentManagerRequest(BaseModel):
    manager_id: uuid.UUID
    department_id: int = Field(..., ge=1)
