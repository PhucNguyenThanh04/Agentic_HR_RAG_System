import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.db.base import Base
from src.api.v1.shared.enums import NotificationType

if TYPE_CHECKING:
    from src.api.v1.features.users.models import User


class Notification(Base):
    """
    Thông báo in-app cho người dùng.

    FK đến users (không phải employees) vì thông báo gắn với tài khoản đăng nhập,
    bao gồm cả admin/HR không có hồ sơ nhân viên.

    object_type / object_id: polymorphic reference — cho phép link đến
    bất kỳ entity nào mà không cần FK cứng.
    Ví dụ: object_type="leave_request", object_id="uuid-..."

    Không có updated_at — notification chỉ thay đổi is_read.
    """
    __tablename__ = "notifications"

    notification_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
        default=uuid.uuid4,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    type: Mapped[NotificationType] = mapped_column(
        Enum(NotificationType, name="notification_type"),
        nullable=False,
        index=True,
    )

    # Polymorphic reference — không FK cứng để tránh coupling
    object_type: Mapped[Optional[str]] = mapped_column(
        String, nullable=True,
        comment="leave_request | correction_request | attendance_record | face_profile",
    )
    object_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    is_read: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, index=True
    )
    read_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    # ── Relationships ──────────────────────────────────────────────────────
    user: Mapped["User"] = relationship(
        back_populates="notifications",
        lazy="select",
    )

    def __repr__(self) -> str:
        return (
            f"<Notification id={self.notification_id} "
            f"user={self.user_id} type={self.type} read={self.is_read}>"
        )
