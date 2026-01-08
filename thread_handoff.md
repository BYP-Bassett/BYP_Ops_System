# SP Order System — THREAD HANDOFF
_As of 2026-01-08 (America/Chicago)_

## 1) Current Truth (what is working right now)
**Repo / environment**
- Project root (backend): `C:\BYP_Ops_System\backend`
- Venv python: `C:\BYP_Ops_System\backend\venv\Scripts\python.exe`
- Python: 3.13.x
- DB: SQLite file `backend\byp_ops.db`
- Start API: `python -m uvicorn app.main:app --reload`

**Git**
- Branch: `fix-delete-override`
- Savepoint tags you can safely return to:
  - `savepoint-repcode-2026-01-07` — rep_code end-to-end (DB/API) + circular import fix
  - `savepoint-rep-carryforward-2026-01-07` — revise/duplicate/add’l vers carry `rep_code/rep_name`
  - `savepoint-gui-repcode-filter-2026-01-07` — GUI rep filtering uses `rep_code`
  - `savepoint-gui-enter-and-blankrev-2026-01-07` — Enter-to-search + blank “none/None” in rev columns
  - `savepoint-gui-window-geometry-2026-01-07` — GUI remembers window size/position + current client-fields row behavior
  - `savepoint-ignore-handoff-md-2026-01-07` — ignores handoff markdowns in repo root

**Rep fields (confirmed working)**
- `rep_name` (display string): `SB - Steve Bassett`
- `rep_code` (initials): `SB`
- Both exist in: DB `orders` table, SQLAlchemy model, Pydantic schemas, routes.
- GUI:
  - Search Rep filter is a dropdown (codes).
  - “My Drafts” uses `rep_code`.
  - Rep dropdown in order detail uses full names (display-only).

**GUI (current behavior that matters)**
- Search window has:
  - Rep dropdown (codes), Clear Search button, Enter-to-search, column width persistence,
  - “Revision Of” / “Add’l Vers Of” show blank (not “none”) when not applicable,
  - Client fields toggle adds a second row under the top row without shifting the top row layout,
  - Window geometry persists between launches.

## 2) Canonical Rules (don’t violate these)
- **One step at a time.** Give exactly one action; wait for confirmation/error.
- **No manual file editing.** If a file needs changes:
  - user uploads current file
  - assistant returns a downloadable replacement **with the same exact filename**
  - **do not rename** files “for convenience.”
- Windows paths only.
- **GUI layout tweaks are pinned for later** unless explicitly unpinned.

## 3) Next Single Target (one thing only)
### Target: Move search filtering server-side (API), stop client-side filtering in GUI.
**Why:** Browser app later will depend on API search; GUI should too. Client-side filtering is slow and fragile.

**Definition of done (DoD)**
- `/orders/search` supports query params for:
  - `artist`, `asset_type`, `notes`, `status`, `rep_code`, `client_name`, `client_company`
- Text fields are **case-insensitive “contains”** matches.
- Enum-ish fields are exact matches (asset_type/status/rep_code).
- GUI uses these query params instead of downloading everything and filtering locally.
- Smoke tests below pass.

**Assumptions if user doesn’t override**
- `artist/notes/client_*` use case-insensitive contains.
- Empty query params mean “ignore this filter.”
- Results order stays current behavior.

## 4) Smoke Tests + Landmines
**Smoke tests**
- API up:
  - `irm http://127.0.0.1:8000/orders/search`
- DB columns exist:
  - `python -c "import sqlite3; c=sqlite3.connect('byp_ops.db'); print([r[1] for r in c.execute('PRAGMA table_info(orders)').fetchall()]); c.close()"`
- Patch rep on draft order:
  - `irm http://127.0.0.1:8000/orders/<draft_id> -Method Patch -ContentType "application/json" -Body '{"rep_code":"RM","rep_name":"RM - Ron Mewis"}'`
- Rep carry-forward on clone:
  - create add’l version / revise from an RM order → new order should stay RM.

**Landmines**
- If Uvicorn throws 500s after model/schema changes: usually a mismatch (migration missing) or import loop.
- PowerShell quoting: outer double quotes, inner single quotes for `python -c`.
- Git warns about LF/CRLF — ignore unless you enjoy noisy diffs.
