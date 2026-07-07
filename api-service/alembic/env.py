"""
alembic/env.py

Cấu hình Alembic cho project FastAPI async.
Alembic chạy sync (dùng psycopg2), app chạy async (dùng asyncpg) —
hai driver khác nhau nhưng cùng kết nối đến 1 DB PostgreSQL.
"""
from dotenv import load_dotenv
load_dotenv()

import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# ── 1. Load tất cả models để Alembic biết schema ──────────────────────────
# Import Base TRƯỚC, sau đó import models để chúng đăng ký vào Base.metadata
from src.core.db.base import Base  # noqa: F401

# Import tất cả models — không thiếu cái nào,
# thiếu 1 model = Alembic không tạo bảng đó
from src.api.v1.features.users.models import User, Role  # noqa: F401
from src.api.v1.features.staff.models import (  # noqa: F401
    Department, Position, Employee, DepartmentManager
)
from src.api.v1.features.shifts.models import (  # noqa: F401
    WorkShift, EmployeeShiftAssignment, Holiday
)
from src.api.v1.features.face_profiles.models import FaceProfile  # noqa: F401
from src.api.v1.features.attendance.models import (  # noqa: F401
    AttendanceEvent, AttendanceRecord
)
from src.api.v1.features.corrections.models import (  # noqa: F401
    AttendanceCorrectionRequest, AttendanceCorrectionLog
)
from src.api.v1.features.leaves.models import (  # noqa: F401
    LeaveType, LeaveRequest, LeaveApprovalLog
)
from src.api.v1.features.notifications.models import Notification  # noqa: F401
from src.api.v1.features.audit.models import AuditLog  # noqa: F401
from src.api.v1.features.system.models import SystemSetting  # noqa: F401
from src.api.v1.features.chat.models import (  # noqa: F401
    ChatMessage, Conversation
)
from src.api.v1.features.documents.models import Document  # noqa: F401

# ── 2. Đọc DATABASE_URL từ biến môi trường ────────────────────────────────
# Alembic dùng psycopg2 (sync), không phải asyncpg
# asyncpg URL:  postgresql+asyncpg://user:pass@host/db
# psycopg2 URL: postgresql+psycopg2://user:pass@host/db  (hoặc postgresql://)
DATABASE_URL = os.environ.get("DATABASE_URL", "").replace(
    "postgresql+asyncpg://", "postgresql+psycopg2://"
)

# ── 3. Alembic Config object ───────────────────────────────────────────────
config = context.config
config.set_main_option("sqlalchemy.url", DATABASE_URL)

# Logging từ alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# target_metadata: Alembic so sánh schema hiện tại của DB với metadata này
# để tự động sinh migration
target_metadata = Base.metadata


# ── 4. Offline mode (không cần kết nối DB) ────────────────────────────────
def run_migrations_offline() -> None:
    """
    Chạy migration chỉ dựa trên URL, không mở connection thật.
    Dùng để generate SQL script — xem trước migration sẽ làm gì.

    Lệnh: alembic upgrade head --sql
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # Quan trọng: so sánh kiểu dữ liệu, không chỉ tên bảng
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


# ── 5. Online mode (kết nối DB thật) ─────────────────────────────────────
def run_migrations_online() -> None:
    """
    Kết nối DB thật và chạy migration trực tiếp.
    Đây là mode dùng trong hầu hết các lệnh thông thường.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,  # NullPool: đóng connection ngay sau migration
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,  # detect thay đổi kiểu cột
            compare_server_default=True,  # detect thay đổi default value
        )
        with context.begin_transaction():
            context.run_migrations()


# ── 6. Entry point ─────────────────────────────────────────────────────────
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
