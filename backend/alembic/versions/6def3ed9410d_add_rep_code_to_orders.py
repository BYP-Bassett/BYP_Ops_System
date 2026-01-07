"""add rep_code to orders

Revision ID: 6def3ed9410d
Revises: 3e5c884cb226
Create Date: 2026-01-07 14:25:11.460763

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6def3ed9410d'
down_revision: Union[str, Sequence[str], None] = '3e5c884cb226'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add rep_code with a default so existing rows are valid immediately (SQLite-friendly).
    op.add_column(
        "orders",
        sa.Column(
            "rep_code",
            sa.String(length=8),
            nullable=False,
            server_default="SB",
        ),
    )

    # Backfill rep_code from rep_name when possible.
    # Expected rep_name format: "SB - Steve Bassett"
    # If the delimiter isn't present, leave the default or copy the whole rep_name (first token).
    op.execute(
        """
        UPDATE orders
        SET rep_code =
            CASE
                WHEN rep_name IS NULL OR TRIM(rep_name) = '' THEN rep_code
                WHEN instr(rep_name, ' - ') > 0 THEN substr(rep_name, 1, instr(rep_name, ' - ') - 1)
                WHEN instr(rep_name, ' ') > 0 THEN substr(rep_name, 1, instr(rep_name, ' ') - 1)
                ELSE rep_name
            END
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("orders", "rep_code")
