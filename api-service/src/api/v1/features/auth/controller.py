from fastapi import APIRouter, Depends, Security, status
from fastapi.security import HTTPAuthorizationCredentials

from src.api.v1.features.auth import schemas as auth_schemas
from src.api.v1.features.auth.service import AuthService, get_auth_service
from src.api.v1.features.users.models import User
from src.core.dependencies.auth import (
    bearer_scheme,
    get_current_user, 
)

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", response_model=auth_schemas.TokenPairResponse, status_code=status.HTTP_200_OK)
async def login(
    payload: auth_schemas.LoginRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> auth_schemas.TokenPairResponse:
    return await auth_service.login(payload)


@router.post("/refresh", response_model=auth_schemas.TokenPairResponse, status_code=status.HTTP_200_OK)
async def refresh(
    payload: auth_schemas.RefreshTokenRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> auth_schemas.TokenPairResponse:
    return await auth_service.refresh(payload)


@router.post("/logout", response_model=auth_schemas.MessageResponse, status_code=status.HTTP_200_OK)
async def logout(
    credentials: HTTPAuthorizationCredentials = Security(bearer_scheme),
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> auth_schemas.MessageResponse:
    return await auth_service.logout(current_user, access_token=credentials.credentials)

@router.get("/me", response_model=auth_schemas.AuthUserProfileResponse, status_code=status.HTTP_200_OK)
async def me(
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> auth_schemas.AuthUserProfileResponse:
    return await auth_service.get_me(current_user)


@router.post(
    "/change-password",
    response_model=auth_schemas.MessageResponse,
    status_code=status.HTTP_200_OK,
)
async def change_password(
    payload: auth_schemas.ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> auth_schemas.MessageResponse:
    return await auth_service.change_password(current_user=current_user, payload=payload)


@router.post(
    "/password-reset/request-otp",
    response_model=auth_schemas.PasswordResetRequestOTPResponse,
    status_code=status.HTTP_200_OK,
)
async def request_password_reset_otp(
    payload: auth_schemas.PasswordResetRequestOTP,
    auth_service: AuthService = Depends(get_auth_service),
) -> auth_schemas.PasswordResetRequestOTPResponse:
    return await auth_service.request_password_reset_otp(payload)


@router.post(
    "/password-reset/verify-otp",
    response_model=auth_schemas.PasswordResetVerifyOTPResponse,
    status_code=status.HTTP_200_OK,
)
async def verify_password_reset_otp(
    payload: auth_schemas.PasswordResetVerifyOTPRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> auth_schemas.PasswordResetVerifyOTPResponse:
    return await auth_service.verify_password_reset_otp(payload)


@router.post(
    "/password-reset/verify-token",
    response_model=auth_schemas.VerifyResetTokenResponse,
    status_code=status.HTTP_200_OK,
)
async def verify_reset_token(
    payload: auth_schemas.VerifyResetTokenRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> auth_schemas.VerifyResetTokenResponse:
    return await auth_service.verify_reset_token(payload)


@router.post(
    "/password-reset/confirm",
    response_model=auth_schemas.PasswordResetConfirmResponse,
    status_code=status.HTTP_200_OK,
)
async def reset_password_with_token(
    payload: auth_schemas.PasswordResetConfirmRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> auth_schemas.PasswordResetConfirmResponse:
    return await auth_service.reset_password_with_token(payload)
