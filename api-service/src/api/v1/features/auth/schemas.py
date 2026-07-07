from datetime import datetime
import uuid

from pydantic import BaseModel, Field, field_validator, model_validator, EmailStr

from src.api.v1.shared.datetime_utils import AppTimezoneModel
from src.api.v1.shared.enums import RoleName, UserStatus

EMAIL_PATTERN = r"^[^\s@]+@[^\s@]+\.[^\s@]+$"
OTP_PATTERN = r"^\d{6}$"
PASSWORD_MIN_LENGTH = 8


class LoginRequest(BaseModel):
    email: EmailStr = Field(..., min_length=5, max_length=255, pattern=EMAIL_PATTERN)
    password: str = Field(..., min_length=1, max_length=128)


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(..., min_length=20, max_length=512)


class TokenPairResponse(AppTimezoneModel):
    access_token: str
    access_token_expires_at: datetime
    refresh_token: str
    refresh_token_expires_at: datetime
    token_type: str = "bearer"


class AuthUserProfileResponse(AppTimezoneModel):
    user_id: uuid.UUID
    email: str
    role_name: RoleName
    status: UserStatus
    token_version: int
    last_login_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=PASSWORD_MIN_LENGTH, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_password_strength(cls, value: str) -> str:
        if not any(ch.isalpha() for ch in value):
            raise ValueError("Password must include at least one letter")
        if not any(ch.isdigit() for ch in value):
            raise ValueError("Password must include at least one digit")
        return value

    @model_validator(mode="after")
    def validate_password_not_same(self) -> "ChangePasswordRequest":
        if self.old_password == self.new_password:
            raise ValueError("New password must be different from old password")
        return self


class MessageResponse(BaseModel):
    message: str


class PasswordResetRequestOTP(BaseModel):
    email: str = Field(..., min_length=5, max_length=255, pattern=EMAIL_PATTERN)


class PasswordResetRequestOTPResponse(BaseModel):
    message: str
    otp_ttl_seconds: int


class PasswordResetVerifyOTPRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=255, pattern=EMAIL_PATTERN)
    otp: str = Field(..., pattern=OTP_PATTERN)


class PasswordResetVerifyOTPResponse(BaseModel):
    reset_token: str
    reset_token_ttl_seconds: int


class PasswordResetConfirmRequest(BaseModel):
    reset_token: str = Field(..., min_length=20, max_length=512)
    new_password: str = Field(..., min_length=PASSWORD_MIN_LENGTH, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_password_strength(cls, value: str) -> str:
        if not any(ch.isalpha() for ch in value):
            raise ValueError("Password must include at least one letter")
        if not any(ch.isdigit() for ch in value):
            raise ValueError("Password must include at least one digit")
        return value


class PasswordResetConfirmResponse(BaseModel):
    message: str


class VerifyResetTokenRequest(BaseModel):
    reset_token: str = Field(..., min_length=20, max_length=512)


class VerifyResetTokenResponse(BaseModel):
    valid: bool
    expires_in_seconds: int
