from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.v1.features.users.models import User
from src.core.db.database import get_db
from src.core.security.authentication import hash_refresh_token
from src.utils.exeptions import DatabaseException
from src.utils.setup_logger import setup_logger

logger = setup_logger(__name__)


class AuthRepo:
    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _user_with_role_stmt():
        return select(User).options(selectinload(User.role))

    async def get_user_by_email(self, email: str) -> User | None:
        normalized = email.strip().lower()
        stmt = self._user_with_role_stmt().where(User.email.ilike(normalized))
        return await self.db.scalar(stmt)

    async def get_user_by_id(self, user_id: UUID) -> User | None:
        stmt = self._user_with_role_stmt().where(User.user_id == user_id)
        return await self.db.scalar(stmt)

    async def get_user_by_refresh_token(self, refresh_token: str) -> User | None:
        token_hash = hash_refresh_token(refresh_token)
        stmt = self._user_with_role_stmt().where(User.refresh_token_hash == token_hash)
        return await self.db.scalar(stmt)

    async def save_login_session(
        self,
        *,
        user: User,
        refresh_token: str,
        refresh_token_expires_at: datetime,
    ) -> User:
        user.refresh_token_hash = hash_refresh_token(refresh_token)
        user.refresh_token_expires_at = refresh_token_expires_at
        user.refresh_token_created_at = datetime.now(timezone.utc)
        user.last_login_at = datetime.now(timezone.utc)

        try:
            await self.db.commit()
            await self.db.refresh(user)
            return user
        except Exception as exc:
            await self.db.rollback()
            logger.exception("Failed to persist login session in repo: user_id=%s", user.user_id)
            raise DatabaseException("Failed to persist login session") from exc

    async def rotate_refresh_token(
        self,
        *,
        user: User,
        refresh_token: str,
        refresh_token_expires_at: datetime,
    ) -> User:
        user.refresh_token_hash = hash_refresh_token(refresh_token)
        user.refresh_token_expires_at = refresh_token_expires_at
        user.refresh_token_created_at = datetime.now(timezone.utc)

        try:
            await self.db.commit()
            await self.db.refresh(user)
            return user
        except Exception as exc:
            await self.db.rollback()
            logger.exception("Failed to rotate refresh token in repo: user_id=%s", user.user_id)
            raise DatabaseException("Failed to rotate refresh token") from exc

    async def clear_refresh_token(
        self,
        *,
        user: User,
        bump_token_version: bool = False,
    ) -> User:
        user.refresh_token_hash = None
        user.refresh_token_expires_at = None
        user.refresh_token_created_at = None
        if bump_token_version:
            user.token_version = user.token_version + 1

        try:
            await self.db.commit()
            await self.db.refresh(user)
            return user
        except Exception as exc:
            await self.db.rollback()
            logger.exception("Failed to clear refresh token in repo: user_id=%s", user.user_id)
            raise DatabaseException("Failed to clear refresh token") from exc

    async def change_password(
        self,
        *,
        user: User,
        new_password_hash: str,
        revoke_refresh_token: bool = True,
        bump_token_version: bool = True,
    ) -> User:
        user.password_hash = new_password_hash
        if bump_token_version:
            user.token_version = user.token_version + 1
        if revoke_refresh_token:
            user.refresh_token_hash = None
            user.refresh_token_expires_at = None
            user.refresh_token_created_at = None

        try:
            await self.db.commit()
            await self.db.refresh(user)
            return user
        except Exception as exc:
            await self.db.rollback()
            logger.exception("Failed to change password in repo: user_id=%s", user.user_id)
            raise DatabaseException("Failed to change password") from exc


def get_auth_repo(db: AsyncSession = Depends(get_db)) -> AuthRepo:
    return AuthRepo(db)
