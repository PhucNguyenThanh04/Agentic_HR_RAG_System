import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.db.base import Base, TimestampMixin
from src.api.v1.shared.enums import AuditAction

if TYPE_CHECKING:
    from src.api.v1.features.users.models import User


class AuditLog(Base):
    """
    Nhật ký kiểm tra toàn hệ thống — immutable, chỉ ghi không sửa xóa.

    performed_by: null nếu là hành động của hệ thống (cron job, system event).

    object_type / object_id: polymorphic — dùng string thay vì FK cứng
    để audit log không bị vướng bởi cascade delete của entity.
    Ví dụ: xóa nhân viên → record audit vẫn còn nguyên.

    old_value / new_value: JSONB snapshot trạng thái trước/sau.
    Không cần serialize toàn bộ object — chỉ lưu các field thay đổi.

    ip_address + user_agent: để detect bất thường (đăng nhập từ IP lạ, v.v.)
    """
    __tablename__ = "audit_logs"

    log_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
        default=uuid.uuid4,
    )

    performed_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    action: Mapped[AuditAction] = mapped_column(
        Enum(AuditAction, name="audit_action"),
        nullable=False,
        index=True,
    )

    object_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    object_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)

    old_value: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    new_value: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    ip_address: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    # ── Relationships ──────────────────────────────────────────────────────
    performed_by_user: Mapped[Optional["User"]] = relationship(
        back_populates="audit_logs",
        foreign_keys=[performed_by],
        lazy="select",
    )

    def __repr__(self) -> str:
        return (
            f"<AuditLog id={self.log_id} "
            f"action={self.action} "
            f"object={self.object_type}:{self.object_id}>"
        )
