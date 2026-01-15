# Project Brain — SP Order System (as of 2026-01-15)

## Goal
Replace legacy FileMaker workflows with a Windows-first order system:
- FastAPI backend + SQLite (dev)
- Desktop Tkinter GUI (office use)
- Simple Web UI (remote use)
- Trello integration on finalize for radio/video
- Real user auth + admin user management

## Architecture (current)
- **API:** FastAPI (`app/main.py`)
- **DB:** SQLite `backend/byp_ops.db` via SQLAlchemy
- **Migrations:** Alembic (`backend/alembic/*`)
- **Desktop:** `OrderSearchGUI.pyw` (Tkinter)
- **Web:** static-ish UI served from FastAPI (`/`, `/order/<built-in function id>`)

## Entrypoints
### Start API
```powershell
cd C:\BYP_Ops_System\backend
.\venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

### Start Desktop GUI
```powershell
cd C:\BYP_Ops_System\backend
python OrderSearchGUI.pyw
```

## Current Working State (truth)
- Web UI works and is **login-gated**.
- Desktop GUI works and is **login-gated**; it can remember login via cookies.
- Web Admin Users page exists at `/admin/users`.
- Trello finalize auto-create works when missing linkages.
- Orders have new user-id audit columns and routes stamp them on writes.
- Alembic heads were merged (confirm single head).

## Current Known Gaps (still pending)
- Desktop does **not** have an admin users page (web-only right now).
- Delete/override flows still prompt for “initials” in places; legacy `deleted_by` remains.
- Need to harden “disable user” behavior to ensure existing sessions can’t keep operating (verify/adjust).
- Web “My Drafts” filter (like desktop) not finished.

## Non‑negotiable rules
- One step at a time.
- No manual edits: Steve uploads file → return downloadable replacement with same filename.
- Never rename files.
- Windows paths only.
- GUI layout changes pinned unless explicitly unpinned.
- Avoid `${ }` inside Python f-strings embedding HTML/JS.
- For troubleshooting, always collect:
  1) exact command run
  2) full traceback
  3) the crashing file content (last `File "..."` in traceback)

## Key files (index)
- `app/main.py` — app setup, session auth, login, `/me`, web admin users UI
- `app/routes/orders.py` — orders API routes + user-id audit stamping
- `app/models/orders.py` — Order model + new audit user_id columns
- `app/models/users.py` — User model (role/is_active/password_hash)
- `app/database/session.py` / `engine.py` / `base.py` — SQLAlchemy engine/session/Base
- `alembic/env.py` — Alembic config/metadata
- `alembic/versions/*` — migrations (including merge migration + audit columns)

## Immediate Next Single Target
Add a Desktop Admin Users window to `OrderSearchGUI.pyw` (parity with web admin):
- list/create/enable-disable/set password/set role
- restrict to admin users only
