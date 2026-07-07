from uuid import UUID

from fastapi import Depends

from src.api.v1.features.users import schemas as user_schemas
from src.api.v1.features.users.user_repo import UserRepo, get_user_repo
from src.core.security.authentication import hash_password, verify_password
from src.utils.exeptions import BadRequestException, ConflictException, NotFoundException
from src.api.v1.shared.enums import RoleName, UserStatus

from src.utils.setup_logger import setup_logger

logger = setup_logger(__name__)


class UserService:
    def __init__(self, user_repo: UserRepo):
        self.user_repo = user_repo

    @staticmethod
    def _to_read(user) -> user_schemas.UserRead:
        return user_schemas.UserRead.model_validate(user)

    async def email_exists(self, email: str) -> bool:
        return await self.user_repo.email_exists(email)

    async def create_user(self, email: str, password_hash: str, role_name: RoleName, status: UserStatus) -> user_schemas.UserRead :
        if await self.email_exists(email=email):
            raise ConflictException("Email already exists")

        user = await self.user_repo.create_user(
            email=email,
            password_hash=password_hash,
            role_name=role_name,
            status=status,
        )
        return self._to_read(user)

    async def get_user(self, user_id: UUID) -> user_schemas.UserRead:
        user = await self.user_repo.get_user_by_id(user_id)
        if user is None:
            logger.warning("Get user not found: user_id=%s", user_id)
            raise NotFoundException("User")
        return self._to_read(user)

    async def list_users(
        self,
        query: user_schemas.UserListQuery,
    ) -> dict:
        users, total = await self.user_repo.list_users(
            page=query.page,
            page_size=query.page_size,
            search=query.search,
            status=query.status,
            role=query.role,
        )
        logger.info(
            "List users: page=%s page_size=%s total=%s search=%s status=%s role=%s",
            query.page,
            query.page_size,
            total,
            query.search,
            query.status,
            query.role,
        )
        return {
            "items": [self._to_read(user) for user in users],
            "total": total,
            "page": query.page,
            "page_size": query.page_size,
        }

    async def update_user(
        self,
        user_id: UUID,
        payload: user_schemas.UserUpdate,
    ) -> user_schemas.UserRead:
        password_hash = hash_password(payload.password) if payload.password else None
        user = await self.user_repo.update_user(
            user_id=user_id,
            email=payload.email,
            status=payload.status,
            role_name=payload.role_name,
            password_hash=password_hash,
        )
        logger.info("User updated: user_id=%s", user_id)
        return self._to_read(user)

    async def change_password(
        self,
        user_id: UUID,
        payload: user_schemas.ChangePasswordRequest,
    ) -> user_schemas.UserRead:
        existing_user = await self.user_repo.get_user_by_id(user_id)
        if existing_user is None:
            logger.warning("Change password user not found: user_id=%s", user_id)
            raise NotFoundException("User")

        if not verify_password(payload.old_password, existing_user.password_hash):
            logger.warning("Change password rejected: wrong current password user_id=%s", user_id)
            raise BadRequestException("Current password is incorrect")

        new_hash = hash_password(payload.new_password)
        updated_user = await self.user_repo.update_password(user_id=user_id, password_hash=new_hash)
        logger.info("Password changed: user_id=%s", user_id)
        return self._to_read(updated_user)

    async def assign_role(
        self,
        user_id: UUID,
        payload: user_schemas.UserRoleAssignRequest,
    ) -> user_schemas.UserRead:
        user = await self.user_repo.set_role(user_id=user_id, role_name=payload.role_name)
        logger.info("Role assigned: user_id=%s role=%s", user_id, payload.role_name)
        return self._to_read(user)

    async def deactivate_user(self, user_id: UUID) -> user_schemas.UserRead:
        user = await self.user_repo.soft_delete_user(user_id)
        logger.info("User deactivated: user_id=%s", user_id)
        return self._to_read(user)

    async def delete_user(self, user_id: UUID) -> None:
        deleted = await self.user_repo.delete_user(user_id)
        if not deleted:
            logger.warning("Delete user not found: user_id=%s", user_id)
            raise NotFoundException("User")
        logger.info("User deleted: user_id=%s", user_id)


def get_user_service(
    user_repo: UserRepo = Depends(get_user_repo),
) -> UserService:
    return UserService(user_repo=user_repo)
