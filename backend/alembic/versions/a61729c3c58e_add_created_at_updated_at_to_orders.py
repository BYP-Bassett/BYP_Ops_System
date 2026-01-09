"""add created_at updated_at to orders

Revision ID: a61729c3c58e
Revises: 6def3ed9410d
Create Date: 2026-01-09 11:50:12.223919

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a61729c3c58e"
down_revision: Union[str, Sequence[str], None] = "6def3ed9410d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    NOTE:
    - This migration is intentionally limited to timestamps only.
    - It avoids unrelated autogenerate type changes (rep_code/client_name/client_company_name).
    """
    # 1) Add updated_at (created_at already exists in the table in your current schema).
    op.add_column("orders", sa.Column("updated_at", sa.String(), nullable=True))

    # 2) Backfill timestamps for existing rows so the UI isn't blank.
    # Store as UTC ISO-ish strings similar to app-side values: 2026-01-09T21:33:12+00:00
    now_expr = "strftime('%Y-%m-%dT%H:%M:%S', 'now') || '+00:00'"

    # Fill created_at where missing/blank
    op.execute(
        f"""
        UPDATE orders
        SET created_at = {now_expr}
        WHERE created_at IS NULL OR TRIM(created_at) = ''
        """
    )

    # Fill updated_at where missing/blank (use created_at as the initial updated_at)
    op.execute(
        """
        UPDATE orders
        SET updated_at = created_at
        WHERE updated_at IS NULL OR TRIM(updated_at) = ''
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("orders", "updated_at")
