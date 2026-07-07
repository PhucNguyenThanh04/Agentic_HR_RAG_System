"""
app/features/shifts/models.py

Bảng sở hữu:
  - work_shifts                 : định nghĩa ca làm việc
  - employee_shift_assignments  : phân công ca cho từng nhân viên
  - holidays                    : ngày lễ (ảnh hưởng ca + tính ngày nghỉ phép)

Được import bởi:
  - attendance/processor.py   : cần WorkShift + EmployeeShiftAssignment để xác định ca đang áp dụng
  - leaves/service.py         : cần Holiday để tính số ngày nghỉ thực tế
"""

import uuid
from datetime import date, datetime, time
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    Boolean, Date, DateTime, ForeignKey,
    Integer, String, Time, func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from src.api.v1.features.users.models import User
    from src.api.v1.features.staff.models import Employee
    from src.api.v1.features.attendance.models import AttendanceRecord


# ── work_shifts ────────────────────────────────────────────────────────────

class WorkShift(Base, TimestampMixin):
    """
    Định nghĩa một ca làm việc.

    is_overnight = True khi ca vắt qua nửa đêm
    (ví dụ: ca đêm 22:00 → 06:00 hôm sau).
    Processor cần biết điều này để tính thời gian đúng.
    """
    __tablename__ = "work_shifts"

    shift_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    code: Mapped[Optional[str]] = mapped_column(
        String, unique=True, nullable=True, index=True
    )

    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    is_overnight: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    # Ngưỡng tính đi trễ / về sớm (phút)
    # Ví dụ: late_threshold_minutes=5 → trễ 5 phút mới tính late
    late_threshold_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    early_leave_threshold_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )

    # Số phút làm việc yêu cầu để tính đủ công
    required_work_minutes: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True,
        comment="Required working minutes to count as full attendance",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, index=True
    )

    # ── Relationships ──────────────────────────────────────────────────────
    assignments: Mapped[List["EmployeeShiftAssignment"]] = relationship(
        back_populates="shift",
        lazy="select",
    )
    attendance_records: Mapped[List["AttendanceRecord"]] = relationship(
        back_populates="shift",
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<WorkShift id={self.shift_id} code={self.code} {self.start_time}→{self.end_time}>"



class EmployeeShiftAssignment(Base, TimestampMixin):
    """
    Phân công ca cho nhân viên theo khoảng ngày hiệu lực.

    Logic lấy ca active: lấy assignment có effective_date <= ngày cần xét
    VÀ (end_date IS NULL HOẶC end_date >= ngày cần xét).
    Nếu có nhiều record thỏa → lấy effective_date lớn nhất (mới nhất).

    created_by: HR nào tạo phân công này (audit trail nhẹ).
    """
    __tablename__ = "employee_shift_assignments"

    assignment_id: Mapped[int] = mapped_column(
        primary_key=True, autoincrement=True
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("employees.employee_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    shift_id: Mapped[int] = mapped_column(
        ForeignKey("work_shifts.shift_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    effective_date: Mapped[date] = mapped_column(
        Date, nullable=False, index=True
    )
    # null = áp dụng vô thời hạn
    end_date: Mapped[Optional[date]] = mapped_column(
        Date, nullable=True, index=True
    )
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )

    # ── Relationships ──────────────────────────────────────────────────────
    employee: Mapped["Employee"] = relationship(
        back_populates="shift_assignments",
    )
    shift: Mapped["WorkShift"] = relationship(
        back_populates="assignments",
        lazy="selectin",    # thường cần load shift info cùng assignment
    )
    creator: Mapped[Optional["User"]] = relationship(
        foreign_keys=[created_by],
        lazy="select",
    )

    def __repr__(self) -> str:
        return (
            f"<ShiftAssignment emp={self.employee_id} "
            f"shift={self.shift_id} "
            f"{self.effective_date}→{self.end_date or '∞'}>"
        )


# ── holidays ───────────────────────────────────────────────────────────────

class Holiday(Base, TimestampMixin):
    """
    Danh sách ngày lễ quốc gia / công ty.

    Đặt trong shifts/ vì ngày lễ là cấu hình lịch làm việc.
    Được import bởi leaves/service.py để tính số ngày nghỉ thực tế
    (trừ cuối tuần + ngày lễ).
    """
    __tablename__ = "holidays"

    holiday_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    holiday_date: Mapped[date] = mapped_column(
        Date, unique=True, nullable=False, index=True
    )
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    def __repr__(self) -> str:
        return f"<Holiday id={self.holiday_id} date={self.holiday_date} name={self.name}>"