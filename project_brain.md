# PROJECT_BRAIN — SP Order System
_As of 2026-01-08 (America/Chicago)_

## What this is
Windows-first **FastAPI + SQLite + Alembic** backend with:
- **Tkinter GUI** (`OrderSearchGUI.pyw`) for internal reps to create/edit/search orders
- **Web UI v1 (vanilla HTML/JS)** for browser-based search (no React, no drama)

## Paths / environment
- Backend root: `C:\BYP_Ops_System\backend`
- Venv python: `C:\BYP_Ops_System\backend\venv\Scripts\python.exe`
- DB: `backend\byp_ops.db` (SQLite)
- SQLAlchemy engine URL: `sqlite:///./byp_ops.db`
- ABS DB path resolves to: `C:\BYP_Ops_System\backend\byp_ops.db`
- Alembic: head is up to date

## Start commands
From `C:\BYP_Ops_System\backend`:
- Start API: `python -m uvicorn app.main:app --reload`
- Start Tkinter GUI: `.\venv\Scripts\python.exe .\OrderSearchGUI.pyw`
- Web UI: open `http://127.0.0.1:8000/`

## Key API endpoints
- `GET /orders/search` — returns list only (server-side filtering + pagination)
- `GET /orders/search2` — returns `{ total, items }` (same filters + pagination)
- `GET /orders/{id}` — returns JSON for a single order
- `GET /health` — JSON health endpoint (because `/` is now the web UI)

### Search filters (current)
Contains (case-insensitive):
- `artist`, `notes`, `client_name`, `client_company` (and legacy alias `client_company_name`), `sp_number` (contains on SP)
Exact (normalized via trim/case):
- `asset_type`, `status`, `rep_code`

Pagination:
- `limit` default 200 (server)
- `offset` default 0
- newest-first (id desc)
- `include_deleted=false` by default (active only)

## Web UI v1 (vanilla)
Files:
- `backend\app\web\index.html`
- `backend\app\web\app.js`

Behavior:
- Click **Search** to load results (no auto-search on page load)
- Uses `/orders/search2` and shows “Showing X–Y of TOTAL”
- Page size is currently **50** in `app.js` (you’ll decide final default later once real web UI sizing is known)

## Rep fields (confirmed, end-to-end)
- `rep_name` (display): e.g. `SB - Steve Bassett`
- `rep_code` (initials): e.g. `SB`
- Clone ops (revise/add’l vers) carry both forward
- Exact rep filtering is done by `rep_code` (not parsing `rep_name`)

## Git state / safe tags
Branch: `fix-delete-override`

Known-good tags (newest first):
- `savepoint-webui-v1-search-2026-01-08` — web UI v1 + paging/search2
- `savepoint-search2-total-pagination-2026-01-08` — `/search2` returns `{total, items}`; GUI uses `/search2`
- `savepoint-search-and-rep-guard-2026-01-08` — server-side filters; rep_code/rep_name sync guard

## Known sharp edges / landmines
- **Blank GUI** often means API is throwing 500s (schema/model mismatch), not Tkinter “breaking”.
- **Port stuck**: old Uvicorn still running → Ctrl+C that window.
- **PowerShell quoting**: avoid nested escaping; prefer simple commands or parameters.
- If you see `SyntaxError` with `f\"` or `description=\"` in Python: you’ve got escaped quotes in Python code again. Fix immediately.
- `/favicon.ico 404` in server logs is harmless browser noise.
