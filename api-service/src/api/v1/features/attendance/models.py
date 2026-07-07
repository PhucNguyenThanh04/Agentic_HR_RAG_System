"""
app/features/attendance/models.py

Bảng sở hữu:
  - attendance_events   : raw event từ AI service (không bao giờ bị sửa)
  - attendance_records  : bản ghi đã xử lý theo business rules

Được import bởi:
  - corrections/service.py  : đọc record cũ và apply giờ mới khi HR approve
  - reports/service.py      : aggregate query để xuất báo cáo

Hai bảng này có vai trò khác nhau:
  attendance_events   = "log gốc" — lưu tất cả lần camera nhận diện
  attendance_records  = "sổ công" — 1 record / (nhân viên, ngày), HR xem và sửa được
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    Boolean, DateTime, Enum, Float, ForeignKey,
    Integer, String, Text, func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.db.base import Base, TimestampMixin
from src.api.v1.shared.enums import (
    AttendanceEventType,
    AttendanceRecordStatus,
    AttendanceSource,
)

if TYPE_CHECKING:
    from src.api.v1.features.staff.models import Employee
    from src.api.v1.features.shifts.models import WorkShift
    from src.api.v1.features.corrections.models import AttendanceCorrectionRequest


# ── attendance_events ──────────────────────────────────────────────────────

class AttendanceEvent(Base):
    """
    Raw event từ AI service — mỗi lần camera nhận diện = 1 record.

    Không có updated_at vì đây là immutable log.
    employee_id = null nếu AI không nhận ra ai (confidence quá thấp).

    is_accepted = False khi:
      - anti_spoof_score < threshold (phát hiện ảnh/video giả)
      - confidence_score < threshold
      - Đang trong cooldown period

    raw_result: toàn bộ JSON response từ AI service — lưu để debug sau này.
    """
    __tablename__ = "attendance_events"

    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
        default=uuid.uuid4,
    )

    # null nếu không nhận ra
    employee_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("employees.employee_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    event_type: Mapped[AttendanceEventType] = mapped_column(
        Enum(AttendanceEventType, name="attendance_event_type"),
        nullable=False,
        index=True,
    )
    event_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    # Scores từ AI
    confidence_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    anti_spoof_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Media và raw data
    image_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_result: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True,
        comment="Full JSON response từ AI service",
    )

    # Acceptance
    is_accepted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Chỉ có created_at (immutable log)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # ── Relationships ──────────────────────────────────────────────────────
    employee: Mapped[Optional["Employee"]] = relationship(
        back_populates="attendance_events",
        lazy="select",
    )

    def __repr__(self) -> str:
        return (
            f"<AttendanceEvent id={self.event_id} "
            f"type={self.event_type} time={self.event_time} "
            f"emp={self.employee_id} accepted={self.is_accepted}>"
        )


# ── attendance_records ─────────────────────────────────────────────────────

class AttendanceRecord(Base, TimestampMixin):
    """
    Bản ghi chấm công đã xử lý — "sổ công" chính thức.

    Unique constraint: (employee_id, work_date) — mỗi nhân viên
    chỉ có 1 bản ghi mỗi ngày.

    Processor tạo/cập nhật record này khi nhận event từ AI:
      - Lần đầu nhận diện trong ngày → tạo record, set check_in_time
      - Lần tiếp theo → cập nhật check_out_time
      - Cuối ngày (cron job) → xử lý các record thiếu check_out, tính absent

    source tracking:
      face_recognition  = AI tự động
      manual            = HR nhập thủ công (mất điện/camera lỗi)
      edited            = HR đã từng sửa bản ghi này
      system            = cron job tự động tạo (absent, holiday, on_leave)
    """
    __tablename__ = "attendance_records"

    record_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
        default=uuid.uuid4,
    )

    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("employees.employee_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    shift_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("work_shifts.shift_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Ngày làm việc — date, không phải timestamp
    # (event_time có thể là timestamp bất kỳ, work_date là ngày quy ước)
    work_date: Mapped[datetime] = mapped_column(
        # dùng Date type từ sqlalchemy
        nullable=False,
        index=True,
    )

    # Giờ vào / ra
    check_in_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    check_out_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Trạng thái và số liệu
    status: Mapped[AttendanceRecordStatus] = mapped_column(
        Enum(AttendanceRecordStatus, name="attendance_record_status"),
        nullable=False,
        index=True,
    )
    late_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    early_leave_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    worked_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    source: Mapped[AttendanceSource] = mapped_column(
        Enum(AttendanceSource, name="attendance_source"),
        nullable=False,
        default=AttendanceSource.face_recognition,
        index=True,
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ── Relationships ──────────────────────────────────────────────────────
    employee: Mapped["Employee"] = relationship(
        back_populates="attendance_records",
        lazy="selectin",
    )
    shift: Mapped[Optional["WorkShift"]] = relationship(
        back_populates="attendance_records",
        lazy="selectin",    # thường cần biết ca khi xem bảng công
    )
    correction_requests: Mapped[List["AttendanceCorrectionRequest"]] = relationship(
        back_populates="attendance_record",
        lazy="select",
    )

    def __repr__(self) -> str:
        return (
            f"<AttendanceRecord emp={self.employee_id} "
            f"date={self.work_date} status={self.status}>"
        )

    @property
    def has_check_in(self) -> bool:
        return self.check_in_time is not None

    @property
    def has_check_out(self) -> bool:
        return self.check_out_time is not None

    @property
    def is_complete(self) -> bool:
        """Có cả check-in lẫn check-out."""
        return self.has_check_in and self.has_check_out