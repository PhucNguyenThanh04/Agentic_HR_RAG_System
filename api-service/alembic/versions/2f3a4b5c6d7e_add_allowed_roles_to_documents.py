"""add allowed roles to documents

Revision ID: 2f3a4b5c6d7e
Revises: 4d9c2a7b8e11
Create Date: 2026-06-29 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "2f3a4b5c6d7e"
down_revision: Union[str, Sequence[str], None] = "4d9c2a7b8e11"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "documents",
        sa.Column(
            "allowed_roles",
            postgresql.ARRAY(sa.String()),
            server_default=sa.text("'{}'::varchar[]"),
            nullable=False,
            comment="Roles allowed to retrieve this document from RAG",
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("documents", "allowed_roles")
