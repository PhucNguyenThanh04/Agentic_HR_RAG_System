"""add registered_by to employees

Revision ID: b7e2d9f4c1aa
Revises: 8c6f5f3aa4b2
Create Date: 2026-05-31 10:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "b7e2d9f4c1aa"
down_revision: Union[str, Sequence[str], None] = "8c6f5f3aa4b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "employees",
        sa.Column(
            "registered_by",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="User who created this employee profile",
        ),
    )
    op.create_index(
        op.f("ix_employees_registered_by"),
        "employees",
        ["registered_by"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_employees_registered_by_users",
        "employees",
        "users",
        ["registered_by"],
        ["user_id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("fk_employees_registered_by_users", "employees", type_="foreignkey")
    op.drop_index(op.f("ix_employees_registered_by"), table_name="employees")
    op.drop_column("employees", "registered_by")
