"""add users table

Revision ID: b3f5c0d1a9e2
Revises: a61729c3c58e
Create Date: 2026-01-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b3f5c0d1a9e2"
down_revision: Union[str, Sequence[str], None] = "a61729c3c58e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("username", sa.String(), nullable=False),
        sa.Column("rep_code", sa.String(), nullable=False),
        sa.Column("rep_name", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("password_hash", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("role", sa.String(), nullable=False, server_default="user"),
        sa.Column("created_at", sa.String(), nullable=True),
        sa.Column("updated_at", sa.String(), nullable=True),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_index("ix_users_rep_code", "users", ["rep_code"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_rep_code", table_name="users")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")
