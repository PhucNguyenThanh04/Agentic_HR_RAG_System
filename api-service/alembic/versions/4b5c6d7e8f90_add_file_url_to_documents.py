"""add file url to documents

Revision ID: 4b5c6d7e8f90
Revises: 3a4b5c6d7e8f
Create Date: 2026-06-29 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "4b5c6d7e8f90"
down_revision: Union[str, Sequence[str], None] = "3a4b5c6d7e8f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "documents",
        sa.Column(
            "file_url",
            sa.Text(),
            nullable=False,
            server_default="",
        ),
    )
    op.execute(
        "UPDATE documents "
        "SET file_url = '/uploads/documents/' || file_name "
        "WHERE file_url = ''"
    )
    op.alter_column("documents", "file_url", server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("documents", "file_url")
