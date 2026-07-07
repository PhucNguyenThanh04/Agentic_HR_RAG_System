import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from src.api.v1.features.users.models import User



class SystemSetting(Base, TimestampMixin):
    """
    Cấu hình hệ thống dạng key-value.

    value là JSONB — cho phép lưu bất kỳ kiểu dữ liệu nào:
      - string: {"value": "Asia/Ho_Chi_Minh"}
      - number: {"value": 60}  (cooldown seconds)
      - object: {"threshold": 0.85, "min_images": 5}

    Các feature khác đọc config qua SystemService.get(key)
    — không import model này trực tiếp để tránh coupling.

    Ví dụ các keys thường dùng:
      "attendance.cooldown_seconds"     : 60
      "face.min_confidence"             : 0.85
      "face.min_anti_spoof_score"       : 0.7
      "face.min_images_required"        : 5
      "attendance.late_notify_enabled"  : true
    """
    __tablename__ = "system_settings"

    setting_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(
        String, unique=True, nullable=False, index=True
    )
    value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    updated_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )

    # ── Relationships ──────────────────────────────────────────────────────
    updater: Mapped[Optional["User"]] = relationship(
        foreign_keys=[updated_by],
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<SystemSetting key={self.key} value={self.value}>"

    def get_value(self):
        """
        Trả về giá trị thực từ JSONB.
        Convention: nếu value là {"value": x} thì trả x, ngược lại trả cả dict.
        """
        if isinstance(self.value, dict) and "value" in self.value and len(self.value) == 1:
            return self.value["value"]
        return self.value
