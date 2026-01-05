"""soft delete + audit log (SQLite-safe, idempotent)

Revision ID: 71fbe0b19a1c
Revises: 8fae4f541360
Create Date: 2026-01-05

This migration is written to be resilient on SQLite even if a previous attempt
partially applied (e.g., columns already exist).
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "71fbe0b19a1c"
down_revision = "8fae4f541360"
branch_labels = None
depends_on = None


def _sqlite_existing_columns(conn, table_name: str) -> set[str]:
    rows = conn.exec_driver_sql(f"PRAGMA table_info('{table_name}')").fetchall()
    # PRAGMA table_info: (cid, name, type, notnull, dflt_value, pk)
    return {r[1] for r in rows}


def upgrade() -> None:
    conn = op.get_bind()
    dialect = conn.dialect.name

    # --- orders: add soft-delete columns (idempotent) ---
    if dialect == "sqlite":
        cols = _sqlite_existing_columns(conn, "orders")

        if "is_deleted" not in cols:
            op.add_column(
                "orders",
                sa.Column(
                    "is_deleted",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.text("0"),
                ),
            )
        if "deleted_at" not in cols:
            op.add_column(
                "orders",
                sa.Column("deleted_at", sa.DateTime(), nullable=True),
            )
        if "deleted_by" not in cols:
            op.add_column(
                "orders",
                sa.Column("deleted_by", sa.String(), nullable=True),
            )

        # Ensure server_default doesn't linger in SQLAlchemy model expectations
        # (SQLite doesn't support ALTER COLUMN DROP DEFAULT cleanly; leave it.)
    else:
        # Non-SQLite: normal alter path
        op.add_column(
            "orders",
            sa.Column(
                "is_deleted",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("0"),
            ),
        )
        op.add_column("orders", sa.Column("deleted_at", sa.DateTime(), nullable=True))
        op.add_column("orders", sa.Column("deleted_by", sa.String(), nullable=True))

    # --- audit_log table (idempotent) ---
    inspector = sa.inspect(conn)
    if not inspector.has_table("audit_log"):
        op.create_table(
            "audit_log",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("ts", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("action", sa.String(), nullable=False),
            sa.Column("order_id", sa.Integer(), nullable=True),
            sa.Column("actor", sa.String(), nullable=True),
            sa.Column("details_json", sa.Text(), nullable=True),
        )
        op.create_index("ix_audit_log_order_id", "audit_log", ["order_id"], unique=False)
        op.create_index("ix_audit_log_ts", "audit_log", ["ts"], unique=False)


def downgrade() -> None:
    conn = op.get_bind()
    dialect = conn.dialect.name

    inspector = sa.inspect(conn)
    if inspector.has_table("audit_log"):
        op.drop_index("ix_audit_log_ts", table_name="audit_log")
        op.drop_index("ix_audit_log_order_id", table_name="audit_log")
        op.drop_table("audit_log")

    if dialect == "sqlite":
        # SQLite can't DROP COLUMN without table rebuild; keep downgrade as no-op to avoid data loss surprises.
        # If you ever need this, we'll write a proper batch table rebuild.
        return

    # Non-SQLite: safe column drops
    op.drop_column("orders", "deleted_by")
    op.drop_column("orders", "deleted_at")
    op.drop_column("orders", "is_deleted")
