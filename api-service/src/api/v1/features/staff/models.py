"""
app/features/staff/models.py

Bảng sở hữu:
  - departments         : phòng ban
  - positions           : chức vụ
  - employees           : hồ sơ nhân viên (bảng trung tâm hệ thống)
  - department_managers : junction — manager nào phụ trách phòng ban nào

Được import bởi: hầu hết mọi feature vì đều FK đến employees.employee_id
"""

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    Boolean, Date, DateTime, Enum, ForeignKey,
    String, Text, func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.db.base import Base, TimestampMixin
from src.api.v1.shared.enums import EmployeeStatus

if TYPE_CHECKING:
    from src.api.v1.features.users.models import User
    from src.api.v1.features.shifts.models import EmployeeShiftAssignment
    from src.api.v1.features.face_profiles.models import FaceProfile
    from src.api.v1.features.attendance.models import AttendanceEvent, AttendanceRecord
    from src.api.v1.features.corrections.models import AttendanceCorrectionRequest
    from src.api.v1.features.leaves.models import LeaveRequest, LeaveApprovalLog


# ── departments ────────────────────────────────────────────────────────────

class Department(Base, TimestampMixin):
    __tablename__ = "departments"

    department_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    code: Mapped[Optional[str]] = mapped_column(String, unique=True, nullable=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, index=True
    )

    # ── Relationships ──────────────────────────────────────────────────────
    employees: Mapped[List["Employee"]] = relationship(
        back_populates="department",
        lazy="select",
    )
    department_managers: Mapped[List["DepartmentManager"]] = relationship(
        back_populates="department",
        cascade="all, delete-orphan",
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<Department id={self.department_id} name={self.name}>"


# ── positions ──────────────────────────────────────────────────────────────

class Position(Base, TimestampMixin):
    __tablename__ = "positions"

    position_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False, index=True, unique=True)
    code: Mapped[Optional[str]] = mapped_column(String, unique=True, nullable=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, index=True
    )

    # ── Relationships ──────────────────────────────────────────────────────
    employees: Mapped[List["Employee"]] = relationship(
        back_populates="position",
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<Position id={self.position_id} name={self.name}>"


# ── employees ──────────────────────────────────────────────────────────────

class Employee(Base, TimestampMixin):
    """
    Bảng trung tâm của hệ thống.
    Hầu hết mọi feature đều có FK trỏ vào đây.

    Self-referential FK: manager_id → employee_id
    (một nhân viên có thể là manager của nhiều nhân viên khác)
    """
    __tablename__ = "employees"

    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
        default=uuid.uuid4,
    )

    # FK 1-1 đến users
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="SET NULL"),
        unique=True,
        nullable=True,
        index=True,
    )
    registered_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="User who created this employee profile",
    )

    employee_code: Mapped[str] = mapped_column(
        String, unique=True, nullable=False, index=True
    )
    full_name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    phone: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # FKs tổ chức
    department_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("departments.department_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    position_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("positions.position_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Self-referential: manager trực tiếp
    manager_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("employees.employee_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Thông tin cá nhân
    date_of_birth: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    gender: Mapped[Optional[str]] = mapped_column(
        String, nullable=True,
        comment="male | female | other",
    )
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    hire_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    resignation_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    status: Mapped[EmployeeStatus] = mapped_column(
        Enum(EmployeeStatus, name="employee_status"),
        nullable=False,
        default=EmployeeStatus.active,
        index=True,
    )

    # ── Relationships ──────────────────────────────────────────────────────

    # Quan hệ ngược lên User
    user: Mapped[Optional["User"]] = relationship(
        back_populates="employee",
        foreign_keys=[user_id],
        lazy="select",
    )
    registered_by_user: Mapped[Optional["User"]] = relationship(
        back_populates="registered_employees",
        foreign_keys=[registered_by],
        lazy="select",
    )

    # Lookup phòng ban / chức vụ
    department: Mapped[Optional["Department"]] = relationship(
        back_populates="employees",
        lazy="selectin",    # thường cần hiển thị cùng nhân viên
    )
    position: Mapped[Optional["Position"]] = relationship(
        back_populates="employees",
        lazy="selectin",
    )

    # Self-referential: manager của nhân viên này
    manager: Mapped[Optional["Employee"]] = relationship(
        back_populates="subordinates",
        foreign_keys=[manager_id],
        remote_side="Employee.employee_id",  # phía "một" là employee_id
        lazy="select",
    )
    # Danh sách nhân viên báo cáo trực tiếp cho employee này
    subordinates: Mapped[List["Employee"]] = relationship(
        back_populates="manager",
        foreign_keys=[manager_id],
        lazy="select",
    )

    # Phòng ban mà nhân viên này được gán làm manager
    managed_departments: Mapped[List["DepartmentManager"]] = relationship(
        back_populates="manager",
        cascade="all, delete-orphan",
        foreign_keys="DepartmentManager.manager_id",
        lazy="select",
    )

    # Feature: shifts
    shift_assignments: Mapped[List["EmployeeShiftAssignment"]] = relationship(
        back_populates="employee",
        cascade="all, delete-orphan",
        lazy="select",
    )

    # Feature: face_profiles (1-1)
    face_profile: Mapped[Optional["FaceProfile"]] = relationship(
        back_populates="employee",
        uselist=False,
        lazy="select",
    )

    # Feature: attendance
    attendance_events: Mapped[List["AttendanceEvent"]] = relationship(
        back_populates="employee",
        lazy="select",
    )
    attendance_records: Mapped[List["AttendanceRecord"]] = relationship(
        back_populates="employee",
        lazy="select",
    )

    # Feature: corrections
    correction_requests: Mapped[List["AttendanceCorrectionRequest"]] = relationship(
        back_populates="employee",
        foreign_keys="AttendanceCorrectionRequest.employee_id",
        lazy="select",
    )

    # Feature: leaves
    leave_requests: Mapped[List["LeaveRequest"]] = relationship(
        back_populates="employee",
        foreign_keys="LeaveRequest.employee_id",
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<Employee id={self.employee_id} code={self.employee_code} name={self.full_name}>"


# ── department_managers (junction) ─────────────────────────────────────────

class DepartmentManager(Base):

    __tablename__ = "department_managers"

    manager_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("employees.employee_id", ondelete="CASCADE"),
        primary_key=True,
    )
    department_id: Mapped[int] = mapped_column(
        ForeignKey("departments.department_id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # ── Relationships ──────────────────────────────────────────────────────
    manager: Mapped["Employee"] = relationship(
        back_populates="managed_departments",
        foreign_keys=[manager_id],
    )
    department: Mapped["Department"] = relationship(
        back_populates="department_managers",
    )

    def __repr__(self) -> str:
        return f"<DepartmentManager manager={self.manager_id} dept={self.department_id}>"
