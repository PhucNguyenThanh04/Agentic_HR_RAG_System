
import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.configs.settings import settings
from src.core.db.database import get_db
from src.core.security.authentication import build_access_token_blacklist_key
from src.api.v1.features.users.models import User
from src.api.v1.features.staff.models import Employee
from src.api.v1.shared.enums import RoleName, UserStatus
from src.core.exceptions import ForbiddenException, NotFoundException, UnauthorizedException


bearer_scheme = HTTPBearer(scheme_name="BearerAuth")
optional_bearer_scheme = HTTPBearer(
    scheme_name="BearerAuth",
    auto_error=False,
)

_attendance_api_key_header = APIKeyHeader(
    name="Attendance-API-Key",
    scheme_name="AttendanceAPIKey",
    auto_error=False,
)

_rag_api_key_header = APIKeyHeader(
    name="Rag-API-Key",
    scheme_name="RagAPIKey",
    auto_error=False,
)


async def verify_api_key_attendance(api_key: str | None = Security(_attendance_api_key_header)) -> None:
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key",
        )

    if not secrets.compare_digest(api_key, settings.face_service_api_key):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key",
        )


async def get_current_user_or_rag_api_key(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    credentials: HTTPAuthorizationCredentials | None = Security(optional_bearer_scheme),
    rag_api_key: str | None = Security(_rag_api_key_header),
) -> User | None:
    # Nhánh internal — agentic-rag gọi
    if rag_api_key:
        if not secrets.compare_digest(rag_api_key, settings.rag_api_key):
            raise UnauthorizedException("Rag API key không hợp lệ")
        return None

    # Nhánh JWT — frontend gọi
    if credentials is None:
        raise UnauthorizedException("Token không hợp lệ hoặc đã hết hạn")

    credentials_exception = UnauthorizedException("Token không hợp lệ hoặc đã hết hạn")
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        user_id: str = payload.get("sub")
        token_version_claim = payload.get("token_version")
        jti_claim = payload.get("jti")
        if user_id is None:
            raise credentials_exception
        if token_version_claim is None:
            raise credentials_exception
        if jti_claim is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    redis_client = getattr(request.app.state, "redis", None)
    if redis_client is not None:
        is_blacklisted = await redis_client.get(build_access_token_blacklist_key(str(jti_claim)))
        if is_blacklisted:
            raise credentials_exception

    result = await db.execute(select(User).where(User.user_id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception
    if int(token_version_claim) != int(user.token_version):
        raise credentials_exception
    if user.status != UserStatus.active:
        raise ForbiddenException("Tài khoản đã bị khóa hoặc vô hiệu hóa")
    return user


async def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials, Security(bearer_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Decode JWT → load User từ DB. Dùng cho mọi endpoint cần auth."""
    credentials_exception = UnauthorizedException("Token không hợp lệ hoặc đã hết hạn")
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        user_id: str = payload.get("sub")
        token_version_claim = payload.get("token_version")
        jti_claim = payload.get("jti")
        if user_id is None:
            raise credentials_exception
        if token_version_claim is None:
            raise credentials_exception
        if jti_claim is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    redis_client = getattr(request.app.state, "redis", None)
    if redis_client is not None:
        is_blacklisted = await redis_client.get(build_access_token_blacklist_key(str(jti_claim)))
        if is_blacklisted:
            raise credentials_exception

    result = await db.execute(select(User).where(User.user_id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception
    if int(token_version_claim) != int(user.token_version):
        raise credentials_exception
    if user.status != UserStatus.active:
        raise ForbiddenException("Tài khoản đã bị khóa hoặc vô hiệu hóa")
    return user


async def get_current_employee(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Employee:
    """Load Employee tương ứng với user đang đăng nhập."""
    result = await db.execute(
        select(Employee).where(Employee.user_id == current_user.user_id)
    )
    employee = result.scalar_one_or_none()
    if employee is None:
        raise NotFoundException("Employee profile")
    return employee


def require_roles(*roles: RoleName):
    """
    Factory tạo dependency kiểm tra role.

    Dùng:
        @router.get("/...", dependencies=[Depends(require_roles(RoleName.hr))])
    Hoặc:
        current_user: User = Depends(require_roles(RoleName.hr, RoleName.admin))
    """
    async def _check(
        current_user: Annotated[User, Depends(get_current_user)]
    ) -> User:
        user_role = current_user.role.name
        if user_role not in roles:
            raise ForbiddenException(f"Yêu cầu quyền: {', '.join(r.value for r in roles)}")
        return current_user
    return _check


# Shortcut dependencies hay dùng
RequireHR = Depends(require_roles(RoleName.hr, RoleName.admin))
RequireManager = Depends(require_roles(RoleName.manager, RoleName.hr, RoleName.admin))
RequireEmployee = Depends(get_current_user)  # mọi user đã login đều được
