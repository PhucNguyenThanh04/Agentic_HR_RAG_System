"""drop qdrant_point_ids from face_profiles

Revision ID: 8c6f5f3aa4b2
Revises: fc719c00346f
Create Date: 2026-05-31 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "8c6f5f3aa4b2"
down_revision: Union[str, Sequence[str], None] = "fc719c00346f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_column("face_profiles", "qdrant_point_ids")


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        "face_profiles",
        sa.Column(
            "qdrant_point_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment='List vector IDs, e.g. ["uuid-1", "uuid-2", ...]',
        ),
    )
