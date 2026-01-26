"""Add clients table + orders.client_id

Revision ID: c7a9f0e2b1d4
Revises: d2813d3a1aea
Create Date: 2026-01-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c7a9f0e2b1d4"
down_revision: Union[str, Sequence[str], None] = "d2813d3a1aea"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) clients table
    op.create_table(
        "clients",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("client_name", sa.String(), nullable=False),
        sa.Column("company_name", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.String(), nullable=True),
        sa.Column("updated_at", sa.String(), nullable=True),
    )
    op.create_index("ix_clients_client_name", "clients", ["client_name"])
    op.create_index("ix_clients_company_name", "clients", ["company_name"])

    # 2) orders.client_id (+ FK) — use batch mode for SQLite compatibility
    with op.batch_alter_table("orders") as batch:
        batch.add_column(sa.Column("client_id", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_orders_client_id_clients", "clients", ["client_id"], ["id"])

    op.create_index("ix_orders_client_id", "orders", ["client_id"])


def downgrade() -> None:
    # Reverse in safe order
    op.drop_index("ix_orders_client_id", table_name="orders")

    with op.batch_alter_table("orders") as batch:
        batch.drop_constraint("fk_orders_client_id_clients", type_="foreignkey")
        batch.drop_column("client_id")

    op.drop_index("ix_clients_company_name", table_name="clients")
    op.drop_index("ix_clients_client_name", table_name="clients")
    op.drop_table("clients")
