"""
app/features/users/models.py

Bảng sở hữu:
  - users          : tài khoản đăng nhập
  - roles          : danh sách vai trò

Được import bởi: hầu hết mọi feature (FK đến users.user_id)
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.db.base import Base, TimestampMixin
from src.api.v1.shared.enums import RoleName, UserStatus

if TYPE_CHECKING:
    # Import vòng chỉ cho type hint, tránh circular import lúc runtime
    from src.api.v1.features.staff.models import Employee
    from src.api.v1.features.notifications.models import Notification
    from src.api.v1.features.audit.models import AuditLog
    from src.api.v1.features.system.models import SystemSetting


# ── users ──────────────────────────────────────────────────────────────────

class User(Base, TimestampMixin):
    __tablename__ = "users"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
        default=uuid.uuid4,
    )
    email: Mapped[str] = mapped_column(
        String,
        unique=True,
        nullable=False,
        index=True,
    )
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    role_id: Mapped[int] = mapped_column(
        ForeignKey("roles.role_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus, name="user_status"),
        nullable=False,
        default=UserStatus.active,
        index=True,
    )
    token_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    refresh_token_hash: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    refresh_token_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    refresh_token_created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # ── Relationships ──────────────────────────────────────────────────────
    # 1 user = 1 role
    role: Mapped["Role"] = relationship(
        back_populates="users",
        lazy="selectin",
    )

    # Quan hệ 1-1 sang Employee (một user có thể là một nhân viên)
    employee: Mapped[Optional["Employee"]] = relationship(
        back_populates="user",
        foreign_keys="Employee.user_id",
        uselist=False,
        lazy="select",
    )
    registered_employees: Mapped[List["Employee"]] = relationship(
        back_populates="registered_by_user",
        foreign_keys="Employee.registered_by",
        lazy="select",
    )

    notifications: Mapped[List["Notification"]] = relationship(
        back_populates="user",
        lazy="select",
    )

    audit_logs: Mapped[List["AuditLog"]] = relationship(
        back_populates="performed_by_user",
        foreign_keys="AuditLog.performed_by",
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<User id={self.user_id} email={self.email}>"

    def has_role(self, role: RoleName) -> bool:
        return self.role.name == role

    @property
    def role_name(self) -> RoleName:
        return self.role.name


# ── roles ──────────────────────────────────────────────────────────────────

class Role(Base, TimestampMixin):
    __tablename__ = "roles"

    role_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[RoleName] = mapped_column(
        Enum(RoleName, name="role_name"),
        unique=True,
        nullable=False,
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ── Relationships ──────────────────────────────────────────────────────
    users: Mapped[List["User"]] = relationship(
        back_populates="role",
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<Role {self.name}>"
