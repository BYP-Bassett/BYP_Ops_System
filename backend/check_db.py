import sqlite3

DB_PATH = "byp_ops.db"

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cols = [r[1] for r in cur.execute("PRAGMA table_info('orders')").fetchall()]
print("orders columns:", cols)

audit = cur.execute(
    "SELECT name FROM sqlite_master WHERE type='table' AND name='audit_log'"
).fetchall()
print("audit_log table:", audit)

conn.close()
