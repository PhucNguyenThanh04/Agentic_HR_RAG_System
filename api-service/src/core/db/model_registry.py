"""
Import all ORM models so SQLAlchemy class registry is complete at runtime.

Without this, querying one model (e.g. User) can trigger mapper configuration
before related models (e.g. Notification) are imported, causing
"failed to locate a name" errors on relationship(...) strings.
"""

# users / auth
from src.api.v1.features.users.models import Role, User  # noqa: F401

# org / staff
from src.api.v1.features.staff.models import (  # noqa: F401
    Department,
    DepartmentManager,
    Employee,
    Position,
)

# scheduling
from src.api.v1.features.shifts.models import (  # noqa: F401
    EmployeeShiftAssignment,
    Holiday,
    WorkShift,
)

# face / attendance
from src.api.v1.features.face_profiles.models import FaceProfile  # noqa: F401
from src.api.v1.features.attendance.models import (  # noqa: F401
    AttendanceEvent,
    AttendanceRecord,
)

# workflows
from src.api.v1.features.corrections.models import (  # noqa: F401
    AttendanceCorrectionLog,
    AttendanceCorrectionRequest,
)
from src.api.v1.features.leaves.models import (  # noqa: F401
    LeaveApprovalLog,
    LeaveRequest,
    LeaveType,
)

# cross-cutting
from src.api.v1.features.notifications.models import Notification  # noqa: F401
from src.api.v1.features.audit.models import AuditLog  # noqa: F401
from src.api.v1.features.system.models import SystemSetting  # noqa: F401
from src.api.v1.features.chat.models import (  # noqa: F401
    ChatMessage,
    Conversation,
)
from src.api.v1.features.documents.models import Document  # noqa: F401
