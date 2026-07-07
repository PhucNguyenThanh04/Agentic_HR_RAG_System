from uuid import UUID

from fastapi import Depends
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.v1.features.users import models
from src.api.v1.features.staff.models import Employee
from src.api.v1.shared.enums import RoleName, UserStatus
from src.core.db.database import get_db
from src.utils.exeptions import (
    BadRequestException,
    ConflictException,
    DatabaseException,
    NotFoundException,
)
from src.utils.setup_logger import setup_logger

logger = setup_logger(__name__)


class UserRepo:
    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _normalize_email(email: str) -> str:
        return email.strip().lower()

    def _user_stmt(self) -> Select:
            return select(models.User).options(selectinload(models.User.role))

    async def email_exists(self, email: str, exclude_user_id: UUID | None = None) -> bool:
        normalized = self._normalize_email(email)
        stmt = select(models.User.user_id).where(models.User.email == normalized)
        if exclude_user_id is not None:
            stmt = stmt.where(models.User.user_id != exclude_user_id)

        result = await self.db.execute(stmt)
        return result.first() is not None

    async def get_role_by_name(self, role_name: RoleName) -> models.Role | None:
        result = await self.db.execute(select(models.Role).where(models.Role.name == role_name))
        return result.scalar_one_or_none()

    async def get_user_by_id(self, user_id: UUID) -> models.User | None:
        result = await self.db.execute(
            self._user_stmt().where(models.User.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_user_by_email(self, email: str) -> models.User | None:
        normalized = self._normalize_email(email)
        result = await self.db.execute(
            self._user_stmt().where(models.User.email == normalized)
        )
        return result.scalar_one_or_none()

    async def get_user_or_404(self, user_id: UUID) -> models.User:
        user = await self.get_user_by_id(user_id)
        if user is None:
            raise NotFoundException("User")
        return user

    async def list_users(
        self,
        page: int = 1,
        page_size: int = 20,
        search: str | None = None,
        status: UserStatus | None = None,
        role: RoleName | None = None,
    ) -> tuple[list[models.User], int]:
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 20

        offset = (page - 1) * page_size

        base_stmt = self._user_stmt().join(
            models.Role, models.Role.role_id == models.User.role_id
        )

        if search:
            keyword = f"%{search.strip()}%"
            base_stmt = base_stmt.where(models.User.email.ilike(keyword))
        if status is not None:
            base_stmt = base_stmt.where(models.User.status == status)
        if role is not None:
            base_stmt = base_stmt.where(models.Role.name == role)

        count_stmt = select(func.count()).select_from(base_stmt.order_by(None).subquery())
        total = int((await self.db.scalar(count_stmt)) or 0)

        result = await self.db.execute(
            base_stmt.order_by(models.User.created_at.desc()).offset(offset).limit(page_size)
        )
        users = result.scalars().all()
        return users, total

    async def create_user(
        self,
        email: str,
        password_hash: str,
        role_name: RoleName,
        status: UserStatus,
    ) -> models.User:
        normalized_email = self._normalize_email(email)

        if await self.email_exists(normalized_email):
            raise ConflictException("Email already exists")

        role = await self.get_role_by_name(role_name)
        if role is None:
            raise BadRequestException(message=f"Role not found: {role_name.value}")

        new_user = models.User(
            email=normalized_email,
            password_hash=password_hash,
            role_id=role.role_id,
            status=status,
        )

        try:
            self.db.add(new_user)
            await self.db.commit()
            created_user = await self.db.scalar(
                self._user_stmt().where(models.User.user_id == new_user.user_id)
            )
            if created_user is None:
                raise DatabaseException("Failed to reload created user")
            return created_user
        except (BadRequestException, ConflictException):
            await self.db.rollback()
            raise
        except Exception as exc:
            await self.db.rollback()
            logger.exception("Failed to create user in repo: email=%s", normalized_email)
            raise DatabaseException("Failed to create user") from exc

    async def update_user(
        self,
        user_id: UUID,
        *,
        email: str | None = None,
        status: UserStatus | None = None,
        role_name: RoleName | None = None,
        password_hash: str | None = None,
    ) -> models.User:
        user = await self.get_user_or_404(user_id)
        changed = False

        if email is not None:
            normalized = self._normalize_email(email)
            if normalized != user.email:
                if await self.email_exists(normalized, exclude_user_id=user.user_id):
                    raise ConflictException("Email already exists")
                user.email = normalized
                changed = True

        if status is not None and status != user.status:
            user.status = status
            changed = True

        if password_hash is not None and password_hash != user.password_hash:
            user.password_hash = password_hash
            changed = True

        if role_name is not None and user.role.name != role_name:
            role = await self.get_role_by_name(role_name)
            if role is None:
                raise BadRequestException(message=f"Role not found: {role_name.value}")
            user.role_id = role.role_id
            changed = True

        if changed:
            try:
                await self.db.commit()
            except Exception as exc:
                await self.db.rollback()
                logger.exception("Failed to update user in repo: user_id=%s", user_id)
                raise DatabaseException("Failed to update user") from exc

        updated = await self.get_user_by_id(user.user_id)
        if updated is None:
            raise DatabaseException("Failed to reload updated user")
        return updated

    async def update_password(self, user_id: UUID, password_hash: str) -> models.User:
        return await self.update_user(user_id, password_hash=password_hash)

    async def set_role(self, user_id: UUID, role_name: RoleName) -> models.User:
        return await self.update_user(user_id, role_name=role_name)

    async def soft_delete_user(self, user_id: UUID) -> models.User:
        return await self.update_user(user_id, status=UserStatus.inactive)

    async def delete_user(self, user_id: UUID) -> bool:
        user = await self.get_user_by_id(user_id)
        if user is None:
            return False
        linked_employee_id = await self.db.scalar(
            select(Employee.employee_id).where(Employee.user_id == user_id)
        )
        try:
            if linked_employee_id is not None:
                user.status = UserStatus.inactive
                user.token_version += 1
                user.refresh_token_hash = None
                user.refresh_token_expires_at = None
                user.refresh_token_created_at = None
                await self.db.commit()
                logger.info(
                    "User is linked to employee; deactivated instead of hard delete: user_id=%s employee_id=%s",
                    user_id,
                    linked_employee_id,
                )
                return True

            await self.db.delete(user)
            await self.db.commit()
            return True
        except Exception as exc:
            await self.db.rollback()
            logger.exception("Failed to delete user in repo: user_id=%s", user_id)
            raise DatabaseException("Failed to delete user") from exc


def get_user_repo(
    db: AsyncSession = Depends(get_db),
) -> UserRepo:
    return UserRepo(db)
