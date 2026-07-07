from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone
from uuid import UUID

from fastapi import Depends
from redis.asyncio import Redis

from src.api.v1.features.auth import schemas as auth_schemas
from src.api.v1.features.auth.auth_repo import AuthRepo, get_auth_repo
from src.api.v1.features.users.models import User
from src.api.v1.shared.enums import UserStatus
from src.core.configs.settings import settings
from src.core.dependencies.dep import get_redis_client
from src.core.email.email import send_email
from src.core.security.authentication import (
    TokenError,
    build_access_token_blacklist_key,
    create_access_token,
    create_password_reset_token,
    create_refresh_token,
    decode_access_token,
    get_refresh_token_expires_at,
    get_remaining_seconds,
    hash_password,
    hash_password_reset_token,
    verify_password,
)
from src.utils.exeptions import BadRequestException, InternalServerException, UnauthorizedException
from src.utils.setup_logger import setup_logger

logger = setup_logger(__name__)


class AuthService:
    def __init__(self, auth_repo: AuthRepo, redis_client: Redis):
        self.auth_repo = auth_repo
        self.redis = redis_client

    @staticmethod
    def _normalize_email(email: str) -> str:
        return email.strip().lower()

    @staticmethod
    def _session_id_from_hash(token_hash: str) -> str:
        return token_hash[:24]

    def _otp_key(self, email: str) -> str:
        return f"auth:pwdreset:otp:{email}"

    def _otp_lock_key(self, email: str) -> str:
        return f"auth:pwdreset:lock:{email}"

    def _reset_token_key(self, reset_token_hash: str) -> str:
        return f"auth:pwdreset:token:{reset_token_hash}"

    @staticmethod
    def _generate_otp() -> str:
        return f"{secrets.randbelow(1_000_000):06d}"

    @staticmethod
    def _require_user_active(user: User) -> None:
        if user.status != UserStatus.active:
            raise UnauthorizedException("Account is inactive or locked")

    @staticmethod
    def _session_id_from_hash(token_hash: str) -> str:
        return token_hash[:24]

    async def _blacklist_access_token(self, access_token: str) -> None:
        try:
            payload = decode_access_token(access_token)
        except TokenError:
            return

        jti = str(payload.get("jti") or "")
        exp = int(payload.get("exp") or 0)
        if not jti or exp <= 0:
            return

        ttl_seconds = get_remaining_seconds(exp)
        if ttl_seconds <= 0:
            return

        await self.redis.set(
            build_access_token_blacklist_key(jti),
            "1",
            ex=ttl_seconds,
        )

    async def login(self, payload: auth_schemas.LoginRequest) -> auth_schemas.TokenPairResponse:
        normalized_email = self._normalize_email(payload.email)
        user = await self.auth_repo.get_user_by_email(normalized_email)
        if user is None or not verify_password(payload.password, user.password_hash):
            logger.warning("Login failed: invalid credentials email=%s", normalized_email)
            raise UnauthorizedException("Invalid email or password")

        self._require_user_active(user)

        access_token, _, access_expire_at = create_access_token(
            user_id=str(user.user_id),
            role=user.role.name.value,
            token_version=user.token_version,
        )

        refresh_token = create_refresh_token()
        refresh_expire_at = get_refresh_token_expires_at()

        await self.auth_repo.save_login_session(
            user=user,
            refresh_token=refresh_token,
            refresh_token_expires_at=refresh_expire_at,
        )
        logger.info("Login success: user_id=%s", user.user_id)

        return auth_schemas.TokenPairResponse(
            access_token=access_token,
            access_token_expires_at=access_expire_at,
            refresh_token=refresh_token,
            refresh_token_expires_at=refresh_expire_at,
        )

    async def refresh(self, payload: auth_schemas.RefreshTokenRequest) -> auth_schemas.TokenPairResponse:
        user = await self.auth_repo.get_user_by_refresh_token(payload.refresh_token)
        if user is None:
            logger.warning("Refresh failed: invalid refresh token")
            raise UnauthorizedException("Invalid refresh token")

        self._require_user_active(user)

        if user.refresh_token_expires_at is None:
            logger.warning("Refresh failed: session missing user_id=%s", user.user_id)
            raise UnauthorizedException("Refresh session is not found")
        if user.refresh_token_expires_at <= datetime.now(timezone.utc):
            await self.auth_repo.clear_refresh_token(user=user, bump_token_version=False)
            logger.warning("Refresh failed: token expired user_id=%s", user.user_id)
            raise UnauthorizedException("Refresh token is expired")

        access_token, _, access_expire_at = create_access_token(
            user_id=str(user.user_id),
            role=user.role.name.value,
            token_version=user.token_version,
        )
        new_refresh_token = create_refresh_token()
        new_refresh_expires_at = get_refresh_token_expires_at()

        await self.auth_repo.rotate_refresh_token(
            user=user,
            refresh_token=new_refresh_token,
            refresh_token_expires_at=new_refresh_expires_at,
        )
        logger.info("Refresh success: user_id=%s", user.user_id)

        return auth_schemas.TokenPairResponse(
            access_token=access_token,
            access_token_expires_at=access_expire_at,
            refresh_token=new_refresh_token,
            refresh_token_expires_at=new_refresh_expires_at,
        )

    async def logout(self, current_user: User, access_token: str) -> auth_schemas.MessageResponse:
        await self._blacklist_access_token(access_token)
        await self.auth_repo.clear_refresh_token(user=current_user, bump_token_version=False)
        logger.info("Logout success: user_id=%s", current_user.user_id)
        return auth_schemas.MessageResponse(message="Logged out successfully")

    async def get_me(self, current_user: User) -> auth_schemas.AuthUserProfileResponse:
        return auth_schemas.AuthUserProfileResponse(
            user_id=current_user.user_id,
            email=current_user.email,
            role_name=current_user.role.name,
            status=current_user.status,
            token_version=current_user.token_version,
            last_login_at=current_user.last_login_at,
            created_at=current_user.created_at,
            updated_at=current_user.updated_at,
        )


    async def change_password(
        self,
        current_user: User,
        payload: auth_schemas.ChangePasswordRequest,
    ) -> auth_schemas.MessageResponse:
        if not verify_password(payload.old_password, current_user.password_hash):
            logger.warning("Change password failed: wrong current password user_id=%s", current_user.user_id)
            raise BadRequestException("Current password is incorrect")

        new_password_hash = hash_password(payload.new_password)
        await self.auth_repo.change_password(
            user=current_user,
            new_password_hash=new_password_hash,
            revoke_refresh_token=True,
            bump_token_version=True,
        )
        logger.info("Change password success: user_id=%s", current_user.user_id)
        return auth_schemas.MessageResponse(message="Password changed successfully")

    async def request_password_reset_otp(
        self,
        payload: auth_schemas.PasswordResetRequestOTP,
    ) -> auth_schemas.PasswordResetRequestOTPResponse:
        email = self._normalize_email(payload.email)
        otp_ttl = settings.otp_expire_minutes * 60

        lock_key = self._otp_lock_key(email)
        lock_ttl = await self.redis.ttl(lock_key)
        if lock_ttl > 0:
            logger.warning("Request OTP blocked: email=%s ttl=%s", email, lock_ttl)
            raise BadRequestException(
                message=f"OTP is temporarily locked. Try again in {lock_ttl} seconds"
            )

        user = await self.auth_repo.get_user_by_email(email)
        if user is None:
            logger.info("Request OTP for non-existing email: email=%s", email)
            return auth_schemas.PasswordResetRequestOTPResponse(
                message="If the email exists, OTP has been sent",
                otp_ttl_seconds=otp_ttl,
            )

        otp = self._generate_otp()
        otp_hash = hash_password_reset_token(otp)
        record = {
            "user_id": str(user.user_id),
            "otp_hash": otp_hash,
            "attempts": 0,
        }

        await self.redis.set(self._otp_key(email), json.dumps(record), ex=otp_ttl)

        try:
            await send_email(
                to=email,
                subject="Your password reset OTP",
                body=(
                    f"Your OTP is: {otp}\n"
                    f"This OTP expires in {settings.otp_expire_minutes} minutes."
                ),
            )
        except Exception as exc:
            await self.redis.delete(self._otp_key(email))
            logger.exception("Failed to send password reset OTP email")
            raise InternalServerException("Failed to send OTP email") from exc
        logger.info("Password reset OTP issued: user_id=%s", user.user_id)

        return auth_schemas.PasswordResetRequestOTPResponse(
            message="If the email exists, OTP has been sent",
            otp_ttl_seconds=otp_ttl,
        )

    async def verify_password_reset_otp(
        self,
        payload: auth_schemas.PasswordResetVerifyOTPRequest,
    ) -> auth_schemas.PasswordResetVerifyOTPResponse:
        email = self._normalize_email(payload.email)
        lock_key = self._otp_lock_key(email)

        lock_ttl = await self.redis.ttl(lock_key)
        if lock_ttl > 0:
            raise BadRequestException(
                message=f"Too many wrong OTP attempts. Try again in {lock_ttl} seconds"
            )

        otp_key = self._otp_key(email)
        raw = await self.redis.get(otp_key)
        if not raw:
            raise BadRequestException("OTP is invalid or expired")

        record = json.loads(raw)
        expected_hash = str(record.get("otp_hash") or "")
        attempts = int(record.get("attempts") or 0)

        input_hash = hash_password_reset_token(payload.otp)
        if input_hash != expected_hash:
            attempts += 1
            max_attempts = settings.otp_max_attempts

            if attempts >= max_attempts:
                await self.redis.delete(otp_key)
                await self.redis.set(
                    lock_key,
                    "1",
                    ex=settings.otp_lock_minutes * 60,
                )
                raise BadRequestException(
                    message=(
                        f"Too many wrong OTP attempts. "
                        f"Locked for {settings.otp_lock_minutes} minutes"
                    )
                )

            ttl = await self.redis.ttl(otp_key)
            if ttl <= 0:
                raise BadRequestException("OTP is invalid or expired")
            record["attempts"] = attempts
            await self.redis.set(otp_key, json.dumps(record), ex=ttl)
            remaining = max_attempts - attempts
            raise BadRequestException(
                message=f"Invalid OTP. Remaining attempts: {remaining}"
            )

        user_id_raw = record.get("user_id")
        if not user_id_raw:
            raise BadRequestException("OTP payload is invalid")

        reset_token = create_password_reset_token()
        reset_token_hash = hash_password_reset_token(reset_token)
        reset_ttl = settings.password_reset_token_expire_minutes * 60

        token_payload = {"user_id": user_id_raw, "email": email}
        await self.redis.set(
            self._reset_token_key(reset_token_hash),
            json.dumps(token_payload),
            ex=reset_ttl,
        )

        await self.redis.delete(otp_key)
        await self.redis.delete(lock_key)

        return auth_schemas.PasswordResetVerifyOTPResponse(
            reset_token=reset_token,
            reset_token_ttl_seconds=reset_ttl,
        )

    async def verify_reset_token(
        self,
        payload: auth_schemas.VerifyResetTokenRequest,
    ) -> auth_schemas.VerifyResetTokenResponse:
        reset_token_hash = hash_password_reset_token(payload.reset_token)
        token_key = self._reset_token_key(reset_token_hash)
        raw = await self.redis.get(token_key)
        if not raw:
            logger.warning("Reset password failed: invalid/expired reset token")
            raise BadRequestException("Reset token is invalid or expired")

        ttl = await self.redis.ttl(token_key)
        return auth_schemas.VerifyResetTokenResponse(valid=True, expires_in_seconds=max(ttl, 0))

    async def reset_password_with_token(
        self,
        payload: auth_schemas.PasswordResetConfirmRequest,
    ) -> auth_schemas.PasswordResetConfirmResponse:
        reset_token_hash = hash_password_reset_token(payload.reset_token)
        token_key = self._reset_token_key(reset_token_hash)
        raw = await self.redis.get(token_key)
        if not raw:
            raise BadRequestException("Reset token is invalid or expired")

        token_payload = json.loads(raw)
        user_id_raw = token_payload.get("user_id")
        if not user_id_raw:
            await self.redis.delete(token_key)
            raise BadRequestException("Reset token payload is invalid")

        user = await self.auth_repo.get_user_by_id(UUID(user_id_raw))
        if user is None:
            await self.redis.delete(token_key)
            logger.warning("Reset password failed: user not found user_id=%s", user_id_raw)
            raise BadRequestException("User is not found")

        password_hash = hash_password(payload.new_password)
        await self.auth_repo.change_password(
            user=user,
            new_password_hash=password_hash,
            revoke_refresh_token=True,
            bump_token_version=True,
        )

        await self.redis.delete(token_key)

        logger.info(
            "Password reset completed for user_id=%s, token_version=%s",
            str(user.user_id),
            user.token_version,
        )
        return auth_schemas.PasswordResetConfirmResponse(
            message="Password has been reset successfully"
        )


def get_auth_service(
    auth_repo: AuthRepo = Depends(get_auth_repo),
    redis_client: Redis = Depends(get_redis_client),
) -> AuthService:
    return AuthService(auth_repo=auth_repo, redis_client=redis_client)
