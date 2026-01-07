"""add rep_name to orders

Revision ID: 3e5c884cb226
Revises: 71fbe0b19a1c
Create Date: 2026-01-07 11:05:27.680535

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3e5c884cb226'
down_revision: Union[str, Sequence[str], None] = '71fbe0b19a1c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "orders",
        sa.Column(
            "rep_name",
            sa.String(length=100),
            nullable=False,
            server_default="SB - Steve Bassett",
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("orders", "rep_name")

