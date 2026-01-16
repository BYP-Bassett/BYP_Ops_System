# Project Brain — BYP Ops / SP Order System

Last updated: **2026-01-16** (America/Chicago)

## Repo + Local Setup
- Repo: `BYP-Bassett/BYP_Ops_System`
- Branch: `fix-delete-override`
- Local backend root: `C:\BYP_Ops_System\backend`
- DB (dev): `backend\byp_ops.db` (SQLite)
- Engine URL: `sqlite:///C:/BYP_Ops_System/backend/byp_ops.db`

### Run
- API:
  - `cd C:\BYP_Ops_System\backend`
  - `.\venv\Scripts\python.exe -m uvicorn app.main:app --reload`
- Desktop GUI:
  - `cd C:\BYP_Ops_System\backend`
  - `python OrderSearchGUI.pyw`

## What Works Now

### Web UI (login-gated)
- Search/list page: `http://127.0.0.1:8000/`
- Order detail HTML: `http://127.0.0.1:8000/order/{id}`
- Order detail JSON: `http://127.0.0.1:8000/orders/{id}`
- Order detail supports editing **draft-only asset_type** + **notes** + **client name/company** and saving via **Save**.
- Order detail has **Open Trello Card** button:
  - Enabled when `trello_card_id` is present.
  - Uses backend helper endpoint `/trello/card-url/{trello_card_id}` (Trello API resolve).
- Known: **Back does NOT autosave** (pinned).

### Auth
- `/login` + cookie sessions (SessionMiddleware)
- `/me` returns: authenticated, user_id, username, rep_code, rep_name, role, is_active
- **Inactive users are blocked** and existing sessions are invalidated (hardening implemented).

### Admin
- Web admin users screen: `/admin/users` (HTML) and `/admin/users?json=1` (JSON)
- Desktop admin users window exists with parity for core actions (list/add/disable/role/password) and is **admins-only**.

### Finalize + Trello
- Finalize radio/video with missing Trello linkage auto-creates:
  - Trello card in rep’s board “To Do”
  - Checklist on the card
  - Stores `trello_card_id` + `trello_checklist_id` back on the order
  - Sets `status=finalized` and `finalized_at`
- **ART orders do not use SP numbers**.
  - Trello checklist naming/creation for ART was fixed and verified working.

### Override edit on finalized orders
- Override-edit workflow now correctly supports “finalize again”:
  - Old checklist is removed/rebuilt (no duplicate stale checklist)
  - New checklist id is stored back on the order
  - Card remains linked

### Audit stamping
- DB columns exist and are stamped on key routes:
  - `orders.created_by_user_id`
  - `orders.updated_by_user_id`
  - `orders.deleted_by_user_id`
- Applied on: create, update, finalize, unfinalize, revise, duplicate, additional-version, delete.

### Delete (legacy behavior)
- DELETE requires initials query param:
  - `/orders/{id}?initials=SB`
  - Not JSON body.

## Savepoints / Tags
- `savepoint-auth-desktop-cookie-2026-01-14`
- `savepoint-desktop-admin-users-2026-01-15`
- `savepoint-auth-inactive-kills-session-2026-01-15`
- `savepoint-art-finalize-trello-checklist-2026-01-15`

## Known Issues / Pinned
- Web detail page **Back** does not autosave; we agreed to pin (either adults hit Save, or later add “unsaved changes” warning / confirm).

## Guardrails / Non‑Negotiables
- One step at a time.
- No manual file editing.
- If a file change is needed: user uploads current file → assistant returns **downloadable replacement** with the **exact same filename**.
- No renaming files. Ever.
- Windows paths only.
- GUI layout tweaks pinned unless explicitly unpinned.
- No `${}` inside Python f-strings that embed HTML/JS.
- PowerShell passwords containing `$` must be in **single quotes**.

## Next Logical Target (recommended)
- Add **Admin Orders tools**:
  - Search/view deleted orders
  - Undelete (restore) orders
  - Optional: audit viewer / basic health checks
  - Optional: “Open Trello card” from admin order view too
