# THREAD_HANDOFF.md — SP Order System (BYP Ops)
**Updated:** 2026-01-06 (America/Chicago)

## Snapshot (NO GUESSING)
- Repo root: `C:\BYP_Ops_System`
- Backend working dir: `C:\BYP_Ops_System\backend`
- Branch: `fix-delete-override`
- HEAD commit: **6bba23f** (Chore: remove accidentally committed audit routes copy)
- Last known-good commit: **212a89a** (Audit: log create/update/finalize/unfinalize with order_id + sp_number) — tested via DB query output

## Recent commits (context)
- 6bba23f — Chore: remove accidentally committed audit routes copy (cleanup; should not affect runtime)
- 212a89a — Audit: log create/update/finalize/unfinalize with order_id + sp_number
- 6088520 — GUI: multi-select delete with count confirmation (right-click + Delete key)
- bfda0a1 — GUI: right-click context menu delete/open in search grid
- fd4f8bb — Save point: soft delete + audit_log foundation
- a30bccb — Save point: default notes templates for new radio/video orders
- 0e80613 — Save point: override/unfinalize + duplicate + addl-vers asset dropdown + notes single-line + rev/addl prefixes
- 7d06c4c (tag: savepoint-before-override-draft)
- 48d1935 (tag: rebuild-start)

## Exact run commands (copy/paste)
### Backend server
From `C:\BYP_Ops_System\backend` (venv active):
```powershell
uvicorn main:app --reload
```

### GUI
From `C:\BYP_Ops_System\backend`:
```powershell
py .\OrderSearchGUI.pyw
```

### Migrations
From `C:\BYP_Ops_System\backend`:
```powershell
python -m alembic upgrade head
```

---

## DB Reality Check (PROVEN LINES)
### FastAPI runtime DB (this is what the app actually uses)
File: `backend\app\database\engine.py`
```py
DATABASE_URL = "sqlite:///./byp_ops.db"  # Temporary local database
engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)
```
✅ Runtime DB is **SQLite** at `backend\byp_ops.db` (relative path).

### Alembic migration DB (what upgrades target)
File: `backend\alembic.ini`
- Uses `sqlalchemy.url = sqlite:///byp_ops.db` (SQLite, same DB file in backend folder).

⚠️ Note: runtime uses `sqlite:///./byp_ops.db` and Alembic uses `sqlite:///byp_ops.db`. Functionally the same location from `backend\`.

## Python Reality Check (PROVEN)
From `C:\BYP_Ops_System\backend` (venv active), `python` resolves to:
- Executable: `C:\BYP_Ops_System\backend\venv\Scripts\python.exe`
- Version: `3.13.9 (64-bit, MSC v.1944)`

Proof command:
```powershell
python -c "import sys; print(sys.executable); print(sys.version)"
```


## Python Launcher Check (PROVEN)
From `C:\BYP_Ops_System\backend` (venv active), `py` resolves to the same venv Python:
- Executable: `C:\BYP_Ops_System\backend\venv\Scripts\python.exe`
- Version: `3.13.9 (64-bit, MSC v.1944)`

Proof command:
```powershell
py -c "import sys; print(sys.executable); print(sys.version)"
```


---

---

## Current behavior snapshot (facts)
- Orders table includes soft-delete columns: `is_deleted`, `deleted_at`, `deleted_by`.
- Deleted orders:
  - Hidden from normal `GET /orders/{id}` (404 unless `include_deleted=true`).
  - Hidden from GUI search list.
- Audit log exists: table `audit_log` logs create/update/finalize/unfinalize/delete; details include `order_id` + `sp_number`.


## Rep field decision (LOCKED)
- Decision: **Store `rep_name` on the Order record (orders.rep_name)**.
- Default (temporary): **`SB`**
- Rationale: matches workflow (search/filter by Rep; audit/admin visibility) and avoids losing creator info when auth changes later.



## Rep UI behavior (LOCKED)
- Auto-fill `rep_name` on new orders with default `SB`.
- In the order detail window: **Rep is a dropdown** (not free text).
- Dropdown values are the **approved reps list** (admin-managed later).
- User may change Rep **only** by selecting from the approved list.



## Approved reps list (LOCKED)
Dropdown values (initials → name):
- `SB` → Steve Bassett
- `RM` → Ron Mewis
- `AML` → Allison Lineberry
- `JS` → Jon Shults
- `CD` → Celine DeLeon

Note (future): Admin panel must allow adding/removing reps from this list.


---

## Current target (ONE ITEM ONLY)
- Target: **Add `rep_name` field end-to-end (DB + API + GUI/search column placement)**

### Definition of Done
- Create new RADIO/VIDEO order: `rep_name` auto-fills to default (e.g., `SB`) and persists in DB.
- GET order returns `rep_name`.
- Search grid shows a **Rep** column placed **after Status and before Artist**.
- Search/filter by Rep works (API + GUI).
- Alembic migration runs clean (`alembic upgrade head`) and existing rows get a safe default (empty or `SB`).

### Files involved (explicit paths)
- `backend/app/models/orders.py` (add column)
- `backend/app/schemas/order.py` (include field)
- `backend/app/routes/orders.py` (create/update/search include Rep)
- `backend/OrderSearchGUI.pyw` (grid column + display order)
- `backend/alembic/versions/<new>_add_rep_name.py` (migration)

---

## Known-good tests (what “working” means)
1) Backend responds:
```powershell
irm http://127.0.0.1:8000/
```
2) GUI launches:
```powershell
cd C:\BYP_Ops_System\backend
py .\OrderSearchGUI.pyw
```
3) Soft delete works:
- Delete from GUI (right-click) or API delete
- Order disappears from GUI
- DB shows `is_deleted=1` and audit_log entry created

---

## End-of-session checklist (so tomorrow doesn’t suck)
From `C:\BYP_Ops_System\backend`:
```powershell
git status
git log -1 --oneline
```
Copy those into this file under “Snapshot”.
