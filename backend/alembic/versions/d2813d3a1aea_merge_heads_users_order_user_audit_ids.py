"""Merge heads (users + order user-audit ids)

Revision ID: d2813d3a1aea
Revises: b3f5c0d1a9e2, b7d4c21f8a90
Create Date: 2026-01-15 10:04:22.282505

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd2813d3a1aea'
down_revision: Union[str, Sequence[str], None] = ('b3f5c0d1a9e2', 'b7d4c21f8a90')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
