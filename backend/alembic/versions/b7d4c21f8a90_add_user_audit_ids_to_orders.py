"""Add user-id audit columns to orders

Revision ID: b7d4c21f8a90
Revises: a61729c3c58e
Create Date: 2026-01-15 15:56:37

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b7d4c21f8a90"
down_revision: Union[str, Sequence[str], None] = "a61729c3c58e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SQLite-safe: batch mode will rebuild table as needed.
    with op.batch_alter_table("orders") as batch:
        batch.add_column(sa.Column("created_by_user_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("updated_by_user_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("deleted_by_user_id", sa.Integer(), nullable=True))

        batch.create_foreign_key(
            "fk_orders_created_by_user_id_users",
            "users",
            ["created_by_user_id"],
            ["id"],
        )
        batch.create_foreign_key(
            "fk_orders_updated_by_user_id_users",
            "users",
            ["updated_by_user_id"],
            ["id"],
        )
        batch.create_foreign_key(
            "fk_orders_deleted_by_user_id_users",
            "users",
            ["deleted_by_user_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("orders") as batch:
        batch.drop_constraint("fk_orders_deleted_by_user_id_users", type_="foreignkey")
        batch.drop_constraint("fk_orders_updated_by_user_id_users", type_="foreignkey")
        batch.drop_constraint("fk_orders_created_by_user_id_users", type_="foreignkey")

        batch.drop_column("deleted_by_user_id")
        batch.drop_column("updated_by_user_id")
        batch.drop_column("created_by_user_id")
