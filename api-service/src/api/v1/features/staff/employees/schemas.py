from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.api.v1.shared.datetime_utils import AppTimezoneModel
from src.api.v1.shared.enums import EmployeeStatus

PHONE_PATTERN = r"^\+?[0-9]{8,15}$"
GENDER_ALLOWED = {"male", "female", "other"}


class EmployeeBase(AppTimezoneModel):
    employee_code: str = Field(..., min_length=1, max_length=50)
    full_name: str = Field(..., min_length=1, max_length=120)
    phone: str | None = Field(default=None, pattern=PHONE_PATTERN)
    avatar_url: str | None = Field(default=None, max_length=500)
    department_id: int | None = Field(default=None, ge=1)
    position_id: int | None = Field(default=None, ge=1)
    manager_id: uuid.UUID | None = None
    date_of_birth: date | None = None
    gender: str | None = Field(default=None, max_length=20)
    address: str | None = Field(default=None, max_length=500)
    hire_date: date | None = None
    resignation_date: date | None = None
    status: EmployeeStatus = EmployeeStatus.active

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, value: str | None) -> str | None:
        if value is None:
            return value
        lowered = value.strip().lower()
        if lowered not in GENDER_ALLOWED:
            raise ValueError("gender must be one of: male, female, other")
        return lowered

    @model_validator(mode="after")
    def validate_dates(self) -> "EmployeeBase":
        if self.hire_date and self.date_of_birth and self.hire_date < self.date_of_birth:
            raise ValueError("hire_date must be after date_of_birth")
        if self.resignation_date and self.hire_date and self.resignation_date < self.hire_date:
            raise ValueError("resignation_date must be on/after hire_date")
        return self


class EmployeeCreate(EmployeeBase):
    employee_code: str | None = Field(default=None, min_length=1, max_length=50)
    user_id: uuid.UUID | None = None


class EmployeeUpdate(BaseModel):
    user_id: uuid.UUID | None = None
    employee_code: str | None = Field(default=None, min_length=1, max_length=50)
    full_name: str | None = Field(default=None, min_length=1, max_length=120)
    phone: str | None = Field(default=None, pattern=PHONE_PATTERN)
    avatar_url: str | None = Field(default=None, max_length=500)
    department_id: int | None = Field(default=None, ge=1)
    position_id: int | None = Field(default=None, ge=1)
    manager_id: uuid.UUID | None = None
    date_of_birth: date | None = None
    gender: str | None = Field(default=None, max_length=20)
    address: str | None = Field(default=None, max_length=500)
    hire_date: date | None = None
    resignation_date: date | None = None
    status: EmployeeStatus | None = None

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, value: str | None) -> str | None:
        if value is None:
            return value
        lowered = value.strip().lower()
        if lowered not in GENDER_ALLOWED:
            raise ValueError("gender must be one of: male, female, other")
        return lowered

    @model_validator(mode="after")
    def validate_dates(self) -> "EmployeeUpdate":
        if self.hire_date and self.date_of_birth and self.hire_date < self.date_of_birth:
            raise ValueError("hire_date must be after date_of_birth")
        if self.resignation_date and self.hire_date and self.resignation_date < self.hire_date:
            raise ValueError("resignation_date must be on/after hire_date")
        return self


class EmployeeRead(AppTimezoneModel):
    model_config = ConfigDict(from_attributes=True)

    employee_id: uuid.UUID
    user_id: uuid.UUID | None = None
    registered_by: uuid.UUID | None = None
    employee_code: str
    full_name: str
    phone: str | None = None
    avatar_url: str | None = None
    department_id: int | None = None
    position_id: int | None = None
    manager_id: uuid.UUID | None = None
    date_of_birth: date | None = None
    gender: str | None = None
    address: str | None = None
    hire_date: date | None = None
    resignation_date: date | None = None
    status: EmployeeStatus
    created_at: datetime
    updated_at: datetime


class EmployeeSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    employee_id: uuid.UUID
    employee_code: str
    full_name: str
    registered_by: uuid.UUID | None = None
    department_id: int | None = None
    position_id: int | None = None
    manager_id: uuid.UUID | None = None
    status: EmployeeStatus


class EmployeeListQuery(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=200)
    search: str | None = Field(default=None, min_length=1, max_length=120)
    department_id: int | None = Field(default=None, ge=1)
    position_id: int | None = Field(default=None, ge=1)
    manager_id: uuid.UUID | None = None
    status: EmployeeStatus | None = None
