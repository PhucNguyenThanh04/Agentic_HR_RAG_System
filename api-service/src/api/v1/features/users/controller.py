from uuid import UUID

from fastapi import APIRouter, Depends

from src.api.v1.features.users import schemas as user_schemas
from src.api.v1.features.users.models import User
from src.api.v1.features.users.service import UserService, get_user_service
from src.api.v1.shared.enums import RoleName
from src.core.dependencies.auth import get_current_user, require_roles
from src.utils.exeptions import ForbiddenException

router = APIRouter(prefix="/users", tags=["Users"])


def _ensure_self_or_admin(current_user: User, target_user_id: UUID) -> None:
    if current_user.user_id == target_user_id:
        return
    if current_user.role.name in {RoleName.admin, RoleName.hr}:
        return
    raise ForbiddenException("You do not have permission to modify this user")


# @router.post(
#     "/",
#     response_model=user_schemas.UserRead,
#     status_code=status.HTTP_201_CREATED,
# )
# async def create_user(
#     payload: user_schemas.UserCreate,
#     _: User = Depends(require_roles(RoleName.hr, RoleName.admin)),
#     user_service: UserService = Depends(get_user_service),
# ) -> user_schemas.UserRead:
#     return await user_service.create_user(payload)


@router.get("/", response_model=dict)
async def list_users(
    query: user_schemas.UserListQuery = Depends(),
    _: User = Depends(require_roles(RoleName.manager, RoleName.hr, RoleName.admin)),
    user_service: UserService = Depends(get_user_service),
) -> dict:
    return await user_service.list_users(query)


@router.get("/{user_id}", response_model=user_schemas.UserRead)
async def get_user(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> user_schemas.UserRead:
    _ensure_self_or_admin(current_user, user_id)
    return await user_service.get_user(user_id)


@router.patch("/{user_id}", response_model=user_schemas.UserRead)
async def update_user(
    user_id: UUID,
    payload: user_schemas.UserUpdate,
    _: User = Depends(require_roles(RoleName.hr, RoleName.admin)),
    user_service: UserService = Depends(get_user_service),
) -> user_schemas.UserRead:
    return await user_service.update_user(user_id, payload)


@router.patch("/{user_id}/password", response_model=user_schemas.UserRead)
async def change_password(
    user_id: UUID,
    payload: user_schemas.ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> user_schemas.UserRead:
    _ensure_self_or_admin(current_user, user_id)
    return await user_service.change_password(user_id, payload)


@router.patch("/{user_id}/role", response_model=user_schemas.UserRead)
async def assign_role(
    user_id: UUID,
    payload: user_schemas.UserRoleAssignRequest,
    _: User = Depends(require_roles(RoleName.hr, RoleName.admin)),
    user_service: UserService = Depends(get_user_service),
) -> user_schemas.UserRead:
    return await user_service.assign_role(user_id, payload)


@router.patch("/{user_id}/deactivate", response_model=user_schemas.UserRead)
async def deactivate_user(
    user_id: UUID,
    _: User = Depends(require_roles(RoleName.hr, RoleName.admin)),
    user_service: UserService = Depends(get_user_service),
) -> user_schemas.UserRead:
    return await user_service.deactivate_user(user_id)

