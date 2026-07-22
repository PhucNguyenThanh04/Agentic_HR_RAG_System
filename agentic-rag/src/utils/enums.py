import enum


# ── Users ──────────────────────────────────────────────────────────────────

class UserStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"
    locked = "locked"


class RoleName(str, enum.Enum):
    admin = "admin"
    hr = "hr"
    manager = "manager"
    employee = "employee"


# ── Employees ──────────────────────────────────────────────────────────────

class EmployeeStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"
    resigned = "resigned"


# ── Face Profiles ──────────────────────────────────────────────────────────

class FaceProfileStatus(str, enum.Enum):
    pending = "pending"
    active = "active"
    revoked = "revoked"
    failed = "failed"


class FaceImageStatus(str, enum.Enum):
    accepted = "accepted"
    rejected = "rejected"


# ── Attendance ─────────────────────────────────────────────────────────────

class AttendanceRecordStatus(str, enum.Enum):
    present = "present"
    late = "late"
    early_leave = "early_leave"
    late_and_early_leave = "late_and_early_leave"
    absent = "absent"
    on_leave = "on_leave"
    holiday = "holiday"
    missing_check_in = "missing_check_in"
    missing_check_out = "missing_check_out"
    manually_edited = "manually_edited"


class AttendanceSource(str, enum.Enum):
    face_recognition = "face_recognition"
    manual = "manual"
    edited = "edited"
    system = "system"


# ── Leaves ─────────────────────────────────────────────────────────────────

class LeaveRequestStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    cancelled = "cancelled"


class LeaveTimeType(str, enum.Enum):
    full_day = "full_day"
    morning = "morning"
    afternoon = "afternoon"
    custom = "custom"


# ── Approvals / Actions ────────────────────────────────────────────────────

class ApprovalAction(str, enum.Enum):
    approved = "approved"
    rejected = "rejected"
    forwarded = "forwarded"
    cancelled = "cancelled"


# ── Corrections ────────────────────────────────────────────────────────────

class CorrectionRequestStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    cancelled = "cancelled"


# ── Notifications ──────────────────────────────────────────────────────────

class NotificationType(str, enum.Enum):
    attendance = "attendance"
    leave = "leave"
    correction = "correction"
    system = "system"
    face_registration = "face_registration"


# ── Audit ──────────────────────────────────────────────────────────────────

class AuditAction(str, enum.Enum):
    create = "create"
    update = "update"
    delete = "delete"
    approve = "approve"
    reject = "reject"
    login = "login"
    logout = "logout"
    revoke = "revoke"
    manual_edit = "manual_edit"
