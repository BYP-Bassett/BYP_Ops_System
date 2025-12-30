# Project_Brain.md — SPOrder System (CURRENT)

**Date updated:** 2025-12-30  
**Project:** BYP Ops / SPOrder (FastAPI backend + Tkinter GUI)  
**Primary goal:** Replace/modernize BYP’s order workflow with a real API + tooling:
- Orders (radio/video/art)
- SP number generation (radio/video only)
- Revisions + revision tracking
- **Additional versions** (not a revision; “same order, different version”)
- Field-based search (FileMaker-style)
- Draft vs Finalized lifecycle + controlled edits
- Trello sync (later) so users don’t type IDs

---

## Non‑negotiable working rules (Steve’s workflow)
- **Project_Brain is the single source of truth.**
- **No assumptions.** If anything is unknown/uncertain, ask.
- **One step at a time.** Do one thing, stop, wait.
- When you request code: **full-file only**, in **one code block**, no partial edits.
- **Never tell Steve to copy/paste individual lines** into a file — always provide the full file to replace.
- **Do not rename existing files** unless Steve explicitly asks.
- **Windows + PowerShell** only (assume PC).
- **First step every time:** confirm server is up:
  - `irm http://127.0.0.1:8000/`

---

## Current environment + paths
- Project root (Windows): `C:\BYP_Ops_System`
- Backend folder: `C:\BYP_Ops_System\backend`
- Venv: `(venv)`
- API base: `http://127.0.0.1:8000`
- Local dev DB (SQLite): `backend\byp_ops.db`

### Start server
From `C:\BYP_Ops_System\backend`:
- `uvicorn main:app --reload`

### Quick health check (always)
- `irm http://127.0.0.1:8000/`

Expected:
```json
{ "status": "BYP Ops backend online" }
```

---

## Git (ADDED 2025-12-30)
Git is now the safety net. We don’t “hope” we can get back to working — we **checkout a tag**.

### Repo root
- Git repo initialized at: `C:\BYP_Ops_System`

### Branches / tags created today
- Feature branch used: `feature/alembic-addl-vers`
- Tags:
  - `savepoint-addl-vers`
  - `savepoint-delete`

### Restore last known-good state (when something breaks)
From `C:\BYP_Ops_System`:
- `git checkout savepoint-delete`
- If you only want to restore the GUI file:
  - `git checkout savepoint-delete -- backend\OrderSearchGUI.pyw`

---

## DB migrations (Alembic) (ADDED 2025-12-30)
We added Alembic and established a baseline.

### Key files
- `backend\alembic.ini`
- `backend\alembic\env.py`
- Migrations: `backend\alembic\versions\*.py`

### Running Alembic (important)
Run from **backend** folder with venv active:
- `python -m alembic revision --autogenerate -m "message"`
- `python -m alembic upgrade head`
- `python -m alembic current`
- `python -m alembic history`

### Baseline
- Baseline migration created: `a213a7221254_baseline.py`
- Stamped into DB.

### New migration added today
- Added column on `sp_master`:
  - `additional_version_of` (nullable string)
- Migration file: `8fae4f541360_add_additional_version_of.py`

---

## Data model (CURRENT)
### Orders table (app/models/orders.py)
Core fields include:
- `id`, `artist`, `asset_type`, `notes`
- `client_name`, `client_company_name`
- `status` = `draft` or `finalized`
- `finalized_at`
- `trello_card_id`, `trello_checklist_id`
- Revision tracking:
  - `is_revision` (bool)
  - `parent_order_id` (int) — **points to immediate parent** (both revision + add’l vers use this)
- (SP details are loaded via relationship `order.sp`)

### SP master (app/models/sp_master.py)
- `sp_number` like `SP000027`
- `order_type` (radio/video)
- **`revision_of`** (nullable string SP#)
- **`additional_version_of`** (nullable string SP#)  ✅ added today

---

## API endpoints (CURRENT)

### Root
- `GET /` → `{"status":"BYP Ops backend online"}`

### Orders
Router file: `backend\app\routes\orders.py` (prefix: `/orders`)

- `GET /orders/{id}`
- `GET /orders/search`
  - FileMaker-style AND search:
    - `artist` contains (case-insensitive)
    - `notes` contains (case-insensitive)
    - `asset_type` exact
    - `status` exact
    - `sp_number` contains
    - (order id intentionally NOT searchable)

- `POST /orders/new`
  - Creates new order. Radio/video generate SP.

- `PATCH /orders/{id}`
  - Finalized orders blocked unless `override=true`.
  - asset_type immutable.

- `POST /orders/{id}/finalize?trello_card_id=...&trello_checklist_id=...`
  - Finalizes order and stores Trello IDs.
  - **Current placeholder:** IDs are user-entered for now.

- `POST /orders/{id}/revise`
  - Creates a **revision** order:
    - `parent_order_id` set to parent order id
    - New SP generated (radio/video)
    - SP field `revision_of` set to parent SP# (when parent has SP)

- `POST /orders/{id}/addl_vers`
  - Creates an **additional version** order:
    - `parent_order_id` set to parent order id
    - New SP generated (radio/video)
    - SP field `additional_version_of` set to parent SP# (when parent has SP)

- `DELETE /orders/{id}?initials=XX[&force=true]`
  - Requires initials.
  - If deleting a finalized order, GUI uses double confirmation and passes `force=true`.

---

## GUI (CURRENT)
File: `backend\OrderSearchGUI.pyw`

### Search grid
- Status column is first.
- Optional “Show Order ID” button adds order id column at far right.

### Details window buttons (intended behavior)
- **Finalize**: currently prompts for Trello IDs (placeholder).
- **Override Edit…**: unlocks finalized orders for editing (current behavior works but has workflow issues listed below).
- **Revision Of**: should call `POST /orders/{id}/revise` and open new order.
- **Add’l Vers Of**: should call `POST /orders/{id}/addl_vers` and open new order.
- **Delete…**: initials + double speed bump for finalized.

---

## Known issues / decisions (as of 2025-12-30)
### Override edit workflow
Observed:
- Override allows editing finalized orders.
- Save can appear to “hang” in UI even though backend saved.
- Finalize button stays disabled after override-save (because order is still finalized).
Desired behavior (Steve confirmed):
- When Override is confirmed, order should **immediately return to draft** until finalized again.
- Finalized deletes should be allowed with **double speed bump** (implemented).

### Current warning
If the GUI file gets “messed up” after experimentation:
- Restore from Git tag: `savepoint-delete`.

---

## Next build target (short)
1) **Unfinalize/Reopen flow**:
   - Add backend endpoint to reopen a finalized order back to `draft` (clear `finalized_at`).
   - GUI Override should call that endpoint, then allow edits, then allow Finalize again.

2) **Keep GUI layout identical** (do not redesign; only surgical behavior fixes).

3) Trello automation later:
   - Finalize should create Trello card/checklist automatically so users never type IDs.

