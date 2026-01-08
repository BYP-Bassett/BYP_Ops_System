# PROJECT_BRAIN — SP Order System
_As of 2026-01-08 (America/Chicago)_

## What this is
Local, Windows-friendly FastAPI + SQLite backend with a Tkinter GUI for reps to:
- Create/edit/search orders
- Track revisions / additional versions
- Finalize orders (with override path)
- Track rep info cleanly
Future: browser UI, per-user login/admin, server-side reporting/filtering.

## Paths / environment
- Backend root: `C:\BYP_Ops_System\backend`
- Venv python: `C:\BYP_Ops_System\backend\venv\Scripts\python.exe`
- DB: `backend\byp_ops.db`
- Run API: `python -m uvicorn app.main:app --reload`

## Git status / savepoints (known good)
Branch: `fix-delete-override`

Key tags:
- `savepoint-repcode-2026-01-07` — rep_code end-to-end + circular import fix
- `savepoint-rep-carryforward-2026-01-07` — clone ops carry rep fields forward
- `savepoint-gui-repcode-filter-2026-01-07` — GUI filtering uses rep_code
- `savepoint-gui-enter-and-blankrev-2026-01-07` — Enter triggers search + blank “none”
- `savepoint-gui-window-geometry-2026-01-07` — GUI geometry persists + client fields row doesn’t shift top row
- `savepoint-ignore-handoff-md-2026-01-07` — ignores handoff markdowns in repo

## Rep fields (canonical)
- Display format: `SB - Steve Bassett` (stored as `rep_name`)
- Code: `SB` (stored as `rep_code`)
Both are present/working end-to-end in DB/model/schemas/routes; clone ops carry forward.

## GUI (OrderSearchGUI.pyw) — current UX decisions
- Rep filter dropdown of codes; “My Drafts” filters by rep_code.
- Enter-to-search across search widgets.
- “Revision Of” / “Add’l Vers Of” show blank when not applicable.
- Client fields toggle adds a clean second row using a sub-frame so top row never shifts.
- Clear Search resets all fields and reloads all.
- Column widths persist via `OrderSearchGUI_prefs.json`.
- Window geometry/state persists via `OrderSearchGUI_prefs.json`.

Pinned for later:
- Further layout/pixel tweaking unless explicitly unpinned.

## Files that matter
- `OrderSearchGUI.pyw`
- `OrderSearchGUI_prefs.json`
- `app\routes\orders.py`
- `byp_ops.db` + Alembic migrations (head up to date)

## Known sharp edges / previous failures
- “Blank GUI” can be an API 500 (schema/model mismatch) not a UI bug.
- Circular import previously broke Uvicorn; avoid models importing themselves.
- PowerShell quoting traps with `python -c`.

## Do NOT ask the user (already answered)
- Using SQLite? Yes (`byp_ops.db`).
- How to restart Uvicorn? Command above.
- Do rep_name/rep_code exist? Yes, end-to-end.

## Next logical work
- Server-side `/orders/search` filtering with query params; update GUI to use it.
