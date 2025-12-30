# Project_Brain.md — SPOrder System (CURRENT)

**Date updated:** 2025-12-29  
**Project:** BYP Ops / SPOrder (FastAPI backend + Tkinter GUI)  
**Primary goal:** Replace/modernize BYP’s order workflow with a real API + tooling:
- Orders (radio/video/art)
- SP number generation (radio/video only)
- Revisions + revision tracking
- Field-based search (FileMaker-style)
- Draft vs Finalized lifecycle + controlled edits
- Trello sync for finalized edits (delete + rebuild checklist/items)

---

## Non‑negotiable working rules (Steve’s workflow)
- **Project_Brain is the single source of truth.**
- **No assumptions.** If anything is unknown/uncertain, ask.
- **One step at a time.** Do one thing, stop, wait.
- When you request code: **full-file only**, in **one code block**, no partial edits.
- **Do not rename files** unless Steve explicitly asks.
- **Overwriting files is allowed** when it’s clear the old version is not needed anymore.
- **Windows + PowerShell** only (assume PC).
- **First step every time:** confirm server is up:
  - `irm http://127.0.0.1:8000/`

---

## Current environment + paths
- Project root (Windows): `C:\BYP_Ops_System\backend`
- Venv: `(venv)`
- Local dev DB (SQLite): `byp_ops.db` (relative to backend folder)
- API base: `http://127.0.0.1:8000`

### Start server
From `C:\BYP_Ops_System\backend`:
- `uvicorn main:app --reload`

### Quick health check
- `irm http://127.0.0.1:8000/`

Expected:
```json
{ "status": "BYP Ops backend online" }
```

---

## What’s implemented and working (as of 2025-12-29)

### Order lifecycle: Draft vs Finalized
- Every new order starts as **draft**.
- Once a Trello card + checklist exist, we **finalize** the order by storing:
  - `trello_card_id`
  - `trello_checklist_id`
  - `finalized_at`
  - `status = finalized`

### Controlled edits after finalization
- Finalized orders are read-only by default.
- An **override edit** is allowed with confirmation and `override=true`.
- When override-editing a finalized order, backend **rebuilds the Trello checklist**:
  - Deletes the existing checklist
  - Creates a fresh checklist named:
    - SP Number for radio/video
    - `NEW` for art (kept as NEW for now)
  - Re-adds checklist items from the order notes (one item per non-empty line)
  - Updates stored `trello_checklist_id` to the new checklist id

---

## Database + ORM

### DB engine
- File: `app/database/engine.py`
- SQLite URL: `sqlite:///./byp_ops.db`

### Session dependency
- File: `app/database/session.py`
- `get_db()` yields `SessionLocal()`.

### Lightweight migrations (SQLite only)
- File: `app/database/migrate.py`
- Called at startup from `main.py`.
- Adds missing columns to the `orders` table without Alembic (dev-only convenience).

---

## Data model

### Order table: `app/models/orders.py`
Fields (current):
- `id` (int, pk)
- `artist` (string, indexed)
- `asset_type` (string) **immutable** once created (`radio` / `video` / `art`)
- `notes` (string, nullable)

Client fields:
- `client_name` (string, nullable)
- `client_company_name` (string, nullable)

SP link:
- `sp_id` (FK to `sp_master.id`, nullable for art)
- `sp` relationship to `SPNumber`

Workflow fields (placeholder / future):
- `order_type`, `description`, `length`, `instructions` (nullable strings)

Revision tracking:
- `is_revision` (bool)
- `parent_order_id` (int nullable)
- `revision_of` (string nullable)

Draft/finalized workflow:
- `status` (string default `draft`)
- `finalized_at` (string nullable)

Trello tracking (meaningful once finalized):
- `trello_card_id` (string nullable)
- `trello_checklist_id` (string nullable)

- `created_at` (string)

### SP master
- Stored in `sp_master` table (model lives in `app/models/sp_master.py`)
- SP generation occurs for **radio/video** orders only.

---

## API endpoints (CURRENT)

### Root
- `GET /`
  - Returns `{"status":"BYP Ops backend online"}`

### Orders
Router file: `app/routes/orders.py` (prefix: `/orders`)

- `GET /orders/`
  - List all orders (desc by id), includes joined `sp`.

- `GET /orders/{id}`
  - Get single order, includes joined `sp`.

- `POST /orders/new`
  - Create new order.
  - For `radio` or `video`: generates new SP.
  - For `art`: no SP.
  - Returns full order with `sp` when applicable.

- `PATCH /orders/{id}`
  - Updates allowed fields (artist, notes, client fields, workflow fields, revision tracking fields).
  - **asset_type cannot be changed** (400 error if attempted).
  - If order is finalized:
    - default: blocked (400) unless `override=true`
    - with `override=true`: allows update + triggers Trello rebuild (requires Trello IDs present)

- `POST /orders/{id}/finalize?trello_card_id=...&trello_checklist_id=...`
  - Marks order finalized and stores Trello IDs.

- `POST /orders/{id}/revise`
  - Creates a new revision order based on the parent order.
  - New order gets a newly generated SP (radio/video), and revision tracking fields are set.
  - NOTE: `revision_of` uses parent SP number when available.

### Search
- `GET /orders/search`
Field-based AND search (FileMaker-style field inputs):
- `artist` (contains, case-insensitive)
- `notes` (contains, case-insensitive)
- `asset_type` (exact match)
- `sp_number` (contains, case-insensitive; joins SP table)
- `client_name` (contains)
- `client_company_name` (contains)
- `status` (exact: `draft` / `finalized`)

Important: **All provided fields combine as AND logic.**

---

## Trello integration (CURRENT)

### What it does now
- Backend can **rebuild a checklist** on a known card, for finalized-order override edits.

### What it does NOT do yet
- Backend does not create Trello cards/lists automatically (yet).
- Finalization currently assumes a Trello card + checklist already exist.

### Config
- Service file: `app/services/trello_service.py`
- Requires environment variables:
  - `TRELLO_KEY`
  - `TRELLO_TOKEN`

If these are missing, override edits that sync Trello will fail with a 500.

---

## GUI (CURRENT)

File: `OrderSearchGUI.pyw` (Tkinter)

### Search screen
- FileMaker-style field inputs (AND search)
- Fields:
  - Artist
  - Asset Type (dropdown)
  - SP Number
  - Notes
  - Advanced toggle: Client Name, Client Company
- Enter/Return triggers **Search**
- Results columns (in this order):
  1. Artist
  2. Asset Type
  3. Notes
  4. SP Number
  5. Revision Of (shows `NEW` if none)
  6. Status

### Detail window
- Title at top shows **Artist name** (not Order ID).
- Draft:
  - Editable: Artist, Client Name, Client Company, Notes
  - Buttons: Save, Finalize
- Finalized:
  - Read-only by default
  - Override Edit… requires confirmation
  - Save uses `override=true` and triggers Trello checklist rebuild
- JSON is **not shown** (notes area uses full space).

### Not implemented yet (GUI)
- “Add’l Vers Of” button behavior (currently stubbed)
- “Revision Of” button behavior (currently stubbed — backend endpoint exists)

---

## Confirmed behavior / tests that were run
- Server returns `BYP Ops backend online` at `/`.
- `asset_type` is immutable (PATCHing it returns: `asset_type cannot be changed`).
- Search works and returns correct filtered lists (including AND behavior).
- Client fields exist, can be created, returned, and searched.
- GUI:
  - Enter triggers search.
  - Results open correct order detail window.
  - Notes area supports long notes.

---

## Known gotchas
- If `irm http://127.0.0.1:8000/` fails, server isn’t running or wrong folder.
- If you run uvicorn from the wrong directory, you can get `Could not import module ...`.
- Trello override sync will fail if `TRELLO_KEY`/`TRELLO_TOKEN` aren’t set.

---

## Immediate open decisions (need Steve’s answer later)
- Define the exact semantics of **Add’l Vers Of**:
  - Does it create a new Order record?
  - Does it reuse the same SP number or generate a new one?
  - Does it affect Trello behavior (new checklist vs same checklist)?
  (No guessing here — we implement exactly what you decide.)

---

## Next steps (planned)
1. Implement GUI wiring for:
   - **Revision Of** → call `POST /orders/{id}/revise`, open the new order detail window.
   - **Add’l Vers Of** → implement once semantics are defined.
2. Add “Finalize” workflow improvements:
   - Optional: allow finalization from GUI after Trello card creation step is integrated.
3. Expand Orders to include additional workflow fields (when ready):
   - Due dates, promoter type, deliverables, etc.
4. Later: add Tours/Clients models + endpoints after Orders is rock solid.
