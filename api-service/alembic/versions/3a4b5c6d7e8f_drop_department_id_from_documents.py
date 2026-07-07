"""drop department id from documents

Revision ID: 3a4b5c6d7e8f
Revises: 2f3a4b5c6d7e
Create Date: 2026-06-29 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "3a4b5c6d7e8f"
down_revision: Union[str, Sequence[str], None] = "2f3a4b5c6d7e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_index(op.f("ix_documents_department_id"), table_name="documents")
    op.drop_constraint(
        "fk_documents_department_id_departments",
        "documents",
        type_="foreignkey",
    )
    op.drop_column("documents", "department_id")


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        "documents",
        sa.Column(
            "department_id",
            sa.Integer(),
            nullable=True,
            comment="NULL means company-wide document",
        ),
    )
    op.create_foreign_key(
        "fk_documents_department_id_departments",
        "documents",
        "departments",
        ["department_id"],
        ["department_id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_documents_department_id"),
        "documents",
        ["department_id"],
    )
