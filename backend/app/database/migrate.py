# app/database/migrate.py
# Lightweight SQLite schema migration helper (no Alembic yet).

from __future__ import annotations

from app.database.engine import engine


def _column_names(cur, table_name: str) -> set[str]:
    cur.execute(f"PRAGMA table_info({table_name})")
    rows = cur.fetchall() or []
    return {r[1] for r in rows}  # (cid, name, type, notnull, dflt_value, pk)


def migrate_sqlite_schema() -> None:
    """
    Adds new columns to existing tables in local SQLite dev DB.

    This is intentionally tiny + pragmatic.
    When you switch to Postgres + Alembic, this file goes in the trash.
    """
    conn = engine.raw_connection()
    try:
        cur = conn.cursor()

        # ORDERS table new columns
        try:
            cols = _column_names(cur, "orders")
        except Exception:
            # table doesn't exist yet; create_all will handle it
            return

        alters: list[str] = []

        if "status" not in cols:
            alters.append("ALTER TABLE orders ADD COLUMN status VARCHAR DEFAULT 'draft'")

        if "finalized_at" not in cols:
            alters.append("ALTER TABLE orders ADD COLUMN finalized_at VARCHAR")

        if "trello_card_id" not in cols:
            alters.append("ALTER TABLE orders ADD COLUMN trello_card_id VARCHAR")

        if "trello_checklist_id" not in cols:
            alters.append("ALTER TABLE orders ADD COLUMN trello_checklist_id VARCHAR")

        if alters:
            for sql in alters:
                cur.execute(sql)
            conn.commit()
    finally:
        conn.close()
