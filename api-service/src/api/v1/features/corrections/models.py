"""
app/features/corrections/models.py

Bảng sở hữu:
  - attendance_correction_requests : đơn yêu cầu sửa công của nhân viên
  - attendance_correction_logs     : lịch sử từng bước duyệt (ai làm gì, lúc nào)

Luồng trạng thái:
  pending → (manager confirm) → pending  [vẫn pending, nhưng log ghi forwarded]
          → (HR approve)      → approved [apply vào AttendanceRecord]
          → (reject bất kỳ bước) → rejected
          → (employee hủy)    → cancelled

Import:
  - AttendanceRecord từ attendance/  : để đọc giờ cũ và ghi giờ mới khi approve
  - Employee từ staff/               : employee_id, reviewed_by
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.db.base import Base, TimestampMixin
from src.api.v1.shared.enums import ApprovalAction, CorrectionRequestStatus

if TYPE_CHECKING:
    from src.api.v1.features.staff.models import Employee
    from src.api.v1.features.attendance.models import AttendanceRecord


# ── attendance_correction_requests ────────────────────────────────────────

class AttendanceCorrectionRequest(Base, TimestampMixin):
    """
    Đơn yêu cầu sửa công từ nhân viên.

    attendance_record_id: có thể null nếu nhân viên không có record cho ngày đó
    (ví dụ: quên check-in hoàn toàn — không có record nào được tạo).
    Trong trường hợp này, HR sẽ tạo mới AttendanceRecord khi approve.

    requested_check_in / requested_check_out:
      Nhân viên tự điền giờ họ cho là đúng.
      Không bắt buộc cả hai — có thể chỉ sửa một chiều.
    """
    __tablename__ = "attendance_correction_requests"

    request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True) if True else None,
        primary_key=True,
        server_default=func.gen_random_uuid(),
        default=uuid.uuid4,
    )

    employee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("employees.employee_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # null nếu không có record gốc
    attendance_record_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("attendance_records.record_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Giờ nhân viên đề xuất
    requested_check_in: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    requested_check_out: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)

    status: Mapped[CorrectionRequestStatus] = mapped_column(
        Enum(CorrectionRequestStatus, name="correction_request_status"),
        nullable=False,
        default=CorrectionRequestStatus.pending,
        index=True,
    )

    # Người xem xét cuối cùng (HR)
    reviewed_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("employees.employee_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ── Relationships ──────────────────────────────────────────────────────
    employee: Mapped["Employee"] = relationship(
        back_populates="correction_requests",
        foreign_keys=[employee_id],
        lazy="selectin",
    )
    reviewer: Mapped[Optional["Employee"]] = relationship(
        foreign_keys=[reviewed_by],
        lazy="select",
    )
    attendance_record: Mapped[Optional["AttendanceRecord"]] = relationship(
        back_populates="correction_requests",
        lazy="selectin",    # thường cần xem record gốc cùng lúc
    )
    logs: Mapped[List["AttendanceCorrectionLog"]] = relationship(
        back_populates="correction_request",
        cascade="all, delete-orphan",
        order_by="AttendanceCorrectionLog.created_at",
        lazy="select",
    )

    def __repr__(self) -> str:
        return (
            f"<CorrectionRequest id={self.request_id} "
            f"emp={self.employee_id} status={self.status}>"
        )


# ── attendance_correction_logs ─────────────────────────────────────────────

class AttendanceCorrectionLog(Base):
    """
    Lịch sử từng bước xử lý yêu cầu sửa công.

    Mỗi lần Manager confirm, HR approve/reject đều tạo 1 log record.
    old_check_in/out: snapshot trước khi thay đổi (để audit trail đầy đủ).
    new_check_in/out: giá trị mới được áp dụng (chỉ có khi approve).

    Không có updated_at — đây là immutable log.
    """
    __tablename__ = "attendance_correction_logs"

    log_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    correction_request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("attendance_correction_requests.request_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reviewer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("employees.employee_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    action: Mapped[ApprovalAction] = mapped_column(
        Enum(ApprovalAction, name="approval_action"),
        nullable=False,
        index=True,
    )
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Snapshot giá trị trước/sau
    old_check_in: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    old_check_out: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    new_check_in: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    new_check_out: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    # ── Relationships ──────────────────────────────────────────────────────
    correction_request: Mapped["AttendanceCorrectionRequest"] = relationship(
        back_populates="logs",
    )
    reviewer: Mapped["Employee"] = relationship(
        foreign_keys=[reviewer_id],
        lazy="select",
    )

    def __repr__(self) -> str:
        return (
            f"<CorrectionLog id={self.log_id} "
            f"req={self.correction_request_id} action={self.action}>"
        )