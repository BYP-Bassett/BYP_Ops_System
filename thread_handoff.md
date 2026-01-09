# SP Order System — THREAD HANDOFF
_As of 2026-01-08 (America/Chicago)_

## 1) Current Truth (what is working right now)
**Repo / environment**
- Backend root: `C:\BYP_Ops_System\backend`
- Venv python: `C:\BYP_Ops_System\backend\venv\Scripts\python.exe`
- DB: `backend\byp_ops.db` (SQLite)
- Engine URL: `sqlite:///./byp_ops.db` (ABS resolves to `C:\BYP_Ops_System\backend\byp_ops.db`)
- Alembic: head up to date

**Start commands**
From `C:\BYP_Ops_System\backend`:
- Start API: `python -m uvicorn app.main:app --reload`
- Start Tkinter GUI: `.\venv\Scripts\python.exe .\OrderSearchGUI.pyw`
- Web UI: `http://127.0.0.1:8000/`

**Working endpoints**
- `/orders/search` — list-only search (server-side filtering)
- `/orders/search2` — `{ total, items }` search (pagination metadata)
- `/orders/{id}` — JSON detail
- `/health` — JSON (because `/` is now HTML)

**Rep fields**
- `rep_code` + `rep_name` exist end-to-end (DB/model/schemas/routes)
- Clone ops carry both forward
- Exact rep filtering uses `rep_code`

## 2) Branch + latest savepoint tags
- Branch: `fix-delete-override`
- Savepoints (newest first):
  - `savepoint-webui-v1-search-2026-01-08` — web search UI served at `/` + paging via `/orders/search2`
  - `savepoint-search2-total-pagination-2026-01-08` — `/search2` returns `{total, items}`; GUI uses `/search2`
  - `savepoint-search-and-rep-guard-2026-01-08` — server-side filters + rep_code/rep_name sync guard
  - (older) `savepoint-gui-window-geometry-2026-01-07`, `savepoint-gui-enter-and-blankrev-2026-01-07`, etc.

## 3) Canonical Rules (don’t violate these)
- **One step at a time.** One action, then wait for confirmation/error.
- **No manual file editing.** If a file change is needed:
  - user uploads the current file
  - assistant returns a downloadable replacement with the **same exact filename**
- **No renaming files, ever.**
- **Windows paths only.**
- **GUI layout tweaks are pinned** unless explicitly unpinned.

## 4) Next Single Target (one task, not a wishlist)
**Target:** Web UI “order detail” page (read-only HTML view)

**Goal:** Clicking a row in the web table opens a human page (not JSON) showing full order details.

**Done when**
- Web table rows are clickable
- Clicking a row navigates to `/order/<id>` (HTML page)
- Page shows core fields + SP block (read-only)
- Still keeps `/orders/<id>` as JSON API

## Smoke Tests + Landmines
**Smoke tests**
- API reachable:
  - `irm "http://127.0.0.1:8000/orders/search2?limit=5&offset=0"`
- Pagination sanity:
  - `irm "http://127.0.0.1:8000/orders/search2?rep_code=SB&limit=5&offset=0"`
  - `irm "http://127.0.0.1:8000/orders/search2?rep_code=SB&limit=5&offset=5"`
- Web UI loads:
  - open `http://127.0.0.1:8000/` and click **Search**
- DB sanity:
  - `.\venv\Scripts\python.exe -c "import sqlite3; c=sqlite3.connect('byp_ops.db'); print(c.execute('select count(1) from orders').fetchone()[0]); c.close()"`

**Landmines**
- Empty web table + no server log for `/orders/search2` usually means **JS didn’t load / JS syntax error** → check F12 console + hard refresh `Ctrl+F5`.
- `/favicon.ico` 404 is harmless.
- If Uvicorn throws `SyntaxError` pointing at `f\"` / `description=\"`: escaped quotes leaked into Python code again.
- If port seems “stuck”: kill old Uvicorn (Ctrl+C) or `taskkill /F /IM python.exe`.
