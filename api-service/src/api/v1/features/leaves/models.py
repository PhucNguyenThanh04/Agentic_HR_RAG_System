"""
app/features/leaves/models.py

Bảng sở hữu:
  - leave_types         : master data loại nghỉ phép (HR quản lý)
  - leave_requests      : đơn xin nghỉ phép của nhân viên
  - leave_approval_logs : lịch sử từng bước duyệt đơn

Import:
  - Holiday từ shifts/  : tính số ngày nghỉ thực tế (trừ ngày lễ + cuối tuần)
  - Employee từ staff/  : employee_id, approved_by
"""

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    Boolean, Date, DateTime, Enum, Float,
    ForeignKey, Integer, String, Text, func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.db.base import Base, TimestampMixin
from src.api.v1.shared.enums import ApprovalAction, LeaveRequestStatus, LeaveTimeType

if TYPE_CHECKING:
    from src.api.v1.features.staff.models import Employee


# ── leave_types ────────────────────────────────────────────────────────────

class LeaveType(Base, TimestampMixin):
    """
    Master data loại nghỉ phép.

    is_paid: nghỉ có lương hay không (ảnh hưởng tính lương sau này).
    max_days_per_year: giới hạn số ngày / năm — null = không giới hạn.
    code: mã ngắn dùng cho báo cáo (ví dụ: "AL" = Annual Leave, "SL" = Sick Leave).
    """
    __tablename__ = "leave_types"

    leave_type_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    code: Mapped[Optional[str]] = mapped_column(
        String, unique=True, nullable=True, index=True
    )
    is_paid: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, index=True
    )
    max_days_per_year: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, index=True
    )

    # ── Relationships ──────────────────────────────────────────────────────
    leave_requests: Mapped[List["LeaveRequest"]] = relationship(
        back_populates="leave_type",
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<LeaveType id={self.leave_type_id} code={self.code} name={self.name}>"


# ── leave_requests ─────────────────────────────────────────────────────────

class LeaveRequest(Base, TimestampMixin):
    """
    Đơn xin nghỉ phép của nhân viên.

    total_days: được tính tự động bởi LeaveService.calculate_working_days()
    (trừ cuối tuần và ngày lễ trong khoảng start_date → end_date).

    time_type:
      full_day  = nghỉ cả ngày
      morning   = nghỉ buổi sáng (tính 0.5 ngày)
      afternoon = nghỉ buổi chiều (tính 0.5 ngày)
      custom    = tùy chỉnh (dùng total_days nhân viên tự nhập)

    Luồng duyệt:
      pending → (Manager approve) → pending [log: approved]
              → (HR approve)      → approved
              → (reject bất kỳ)   → rejected
              → (employee hủy)    → cancelled

    approved_by: người duyệt cuối cùng (HR hoặc Manager tùy flow).
    """
    __tablename__ = "leave_requests"

    request_id: Mapped[uuid.UUID] = mapped_column(
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
    leave_type_id: Mapped[int] = mapped_column(
        ForeignKey("leave_types.leave_type_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    start_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    end_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    time_type: Mapped[LeaveTimeType] = mapped_column(
        Enum(LeaveTimeType, name="leave_time_type"),
        nullable=False,
        default=LeaveTimeType.full_day,
    )
    # Tính sau khi trừ weekend + holiday
    total_days: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[LeaveRequestStatus] = mapped_column(
        Enum(LeaveRequestStatus, name="leave_request_status"),
        nullable=False,
        default=LeaveRequestStatus.pending,
        index=True,
    )

    # Người duyệt cuối
    approved_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("employees.employee_id", ondelete="SET NULL"),
        nullable=True,
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ── Relationships ──────────────────────────────────────────────────────
    employee: Mapped["Employee"] = relationship(
        back_populates="leave_requests",
        foreign_keys=[employee_id],
        lazy="selectin",
    )
    leave_type: Mapped["LeaveType"] = relationship(
        back_populates="leave_requests",
        lazy="selectin",    # thường cần tên loại nghỉ khi hiển thị
    )
    approver: Mapped[Optional["Employee"]] = relationship(
        foreign_keys=[approved_by],
        lazy="select",
    )
    approval_logs: Mapped[List["LeaveApprovalLog"]] = relationship(
        back_populates="leave_request",
        cascade="all, delete-orphan",
        order_by="LeaveApprovalLog.created_at",
        lazy="select",
    )

    def __repr__(self) -> str:
        return (
            f"<LeaveRequest id={self.request_id} "
            f"emp={self.employee_id} "
            f"{self.start_date}→{self.end_date} status={self.status}>"
        )

    @property
    def duration_days(self) -> int:
        """Số ngày calendar (chưa trừ weekend/holiday)."""
        return (self.end_date - self.start_date).days + 1


# ── leave_approval_logs ────────────────────────────────────────────────────

class LeaveApprovalLog(Base):
    """
    Lịch sử từng bước duyệt đơn nghỉ phép.

    Mỗi action (Manager approve, HR override, reject...) tạo 1 record.
    Immutable — không có updated_at.

    Dùng để:
      - Hiển thị timeline duyệt đơn cho nhân viên
      - Audit trail cho HR
    """
    __tablename__ = "leave_approval_logs"

    log_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    leave_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("leave_requests.request_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    approver_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
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

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    # ── Relationships ──────────────────────────────────────────────────────
    leave_request: Mapped["LeaveRequest"] = relationship(
        back_populates="approval_logs",
    )
    approver: Mapped["Employee"] = relationship(
        foreign_keys=[approver_id],
        lazy="select",
    )

    def __repr__(self) -> str:
        return (
            f"<LeaveApprovalLog id={self.log_id} "
            f"req={self.leave_request_id} action={self.action}>"
        )