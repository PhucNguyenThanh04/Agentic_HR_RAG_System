"""
app/features/face_profiles/models.py

Bảng sở hữu:
  - face_profiles : hồ sơ khuôn mặt nhân viên

Quan hệ:
  - 1-1 với employees (mỗi nhân viên chỉ có 1 face profile active tại một thời điểm)

Không có feature nào import model này trực tiếp.
Attendance events chỉ lưu employee_id, không FK vào face_profiles.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.db.base import Base, TimestampMixin
from src.api.v1.shared.enums import FaceProfileStatus

if TYPE_CHECKING:
    from src.api.v1.features.users.models import User
    from src.api.v1.features.staff.models import Employee


# ── face_profiles ──────────────────────────────────────────────────────────

class FaceProfile(Base, TimestampMixin):
    """
    Hồ sơ khuôn mặt của một nhân viên.

    Vòng đời trạng thái:
        pending  → (AI xử lý ảnh thành công) → active
        pending  → (AI thất bại)              → failed
        active   → (HR thu hồi / re-enroll)   → revoked
        revoked  → (re-enroll)                → pending (record mới)

    qdrant_collection: tên collection trong Qdrant chứa vectors của profile này.

    embedding_model / embedding_version: metadata để biết vector được tạo
    bằng model nào — dùng khi migrate sang model mới (re-embed toàn bộ).
    """
    __tablename__ = "face_profiles"

    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
        default=uuid.uuid4,
    )

    # FK 1-1 đến employees
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("employees.employee_id", ondelete="CASCADE"),
        unique=True,        # unique đảm bảo 1 nhân viên chỉ có 1 profile
        nullable=False,
        index=True,
    )

    status: Mapped[FaceProfileStatus] = mapped_column(
        Enum(FaceProfileStatus, name="face_profile_status"),
        nullable=False,
        default=FaceProfileStatus.pending,
        index=True,
    )

    # Qdrant metadata
    qdrant_collection: Mapped[str] = mapped_column(
        String, nullable=False, index=True,
        comment="Tên collection trong Qdrant",
    )

    # Embedding metadata
    embedding_model: Mapped[Optional[str]] = mapped_column(
        String, nullable=True,
        comment="e.g. buffalo_l / arcface",
    )
    embedding_version: Mapped[Optional[str]] = mapped_column(
        String, nullable=True,
        comment="Dùng khi switch sang model mới",
    )

    # Ai đăng ký (HR)
    registered_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )

    # Thông tin thu hồi
    revocation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Relationships ──────────────────────────────────────────────────────
    employee: Mapped["Employee"] = relationship(
        back_populates="face_profile",
        lazy="select",
    )
    registrar: Mapped[Optional["User"]] = relationship(
        foreign_keys=[registered_by],
        lazy="select",
    )

    def __repr__(self) -> str:
        return (
            f"<FaceProfile id={self.profile_id} "
            f"emp={self.employee_id} status={self.status}>"
        )

    @property
    def is_enrollable(self) -> bool:
        """Có thể enroll không (chưa active hoặc đã revoked/failed)."""
        return self.status in (
            FaceProfileStatus.pending,
            FaceProfileStatus.revoked,
            FaceProfileStatus.failed,
        )
