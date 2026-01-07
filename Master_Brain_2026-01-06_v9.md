# Master_Brain.md — SP Order System (CURRENT)
**Updated:** 2026-01-06  
**Branch:** `fix-delete-override`  
**HEAD:** `6bba23f` (Chore: remove accidentally committed audit routes copy)  

**Known-good:** `212a89a` (audit logging confirmed)  
**Current HEAD:** `6bba23f` (cleanup only)  
**Repo:** `C:\BYP_Ops_System`  
**Backend dir:** `C:\BYP_Ops_System\backend`  
**API base:** `http://127.0.0.1:8000`  
**Dev DB:** SQLite file `backend\byp_ops.db` (proven below)

---

## 0) Non-negotiables
- One change at a time.
- No assumptions. If we don’t know, we look.
- Code changes are full-file replacements (no fragments).
- Don’t rename files unless Steve explicitly says so.

---

## 1) Where the DB is defined (DB Reality Check)
### FastAPI runtime DB (PROVEN)
File: `backend\app\database\engine.py`
```py
DATABASE_URL = "sqlite:///./byp_ops.db"  # Temporary local database
engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)
```
✅ Runtime DB = SQLite at `backend\byp_ops.db`.

### Alembic migration DB (PROVEN)
File: `backend\alembic.ini`
- `sqlalchemy.url = sqlite:///byp_ops.db`

✅ Alembic targets the same SQLite DB file from `backend\`.

---

## Python Reality Check (PROVEN)
- `python` is the venv Python: `C:\BYP_Ops_System\backend\venv\Scripts\python.exe`
- Version: `3.13.9 (64-bit)`

Proof:
```powershell
python -c "import sys; print(sys.executable); print(sys.version)"
```


## 2) How to run (copy/paste)
### Start backend
From `C:\BYP_Ops_System\backend` (venv active):
```powershell
uvicorn main:app --reload
```

### Health check
```powershell
irm http://127.0.0.1:8000/
```

### Launch GUI
From `C:\BYP_Ops_System\backend`:
```powershell
py .\OrderSearchGUI.pyw
```

### Run migrations
```powershell
python -m alembic upgrade head
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

## 3) Current features in place (high level)
- Orders CRUD + search.
- Status lifecycle: draft/finalized + override edit support.
- Default notes templates for new RADIO/VIDEO orders.
- Soft delete for orders (is_deleted/deleted_at/deleted_by).
- Audit log table `audit_log` capturing create/update/finalize/unfinalize/delete.
- GUI: right-click delete + multi-select delete with count confirmation.

---

## 4) What to do first in a new thread (so we don’t “where are we?” again)
Paste these outputs at the top of the new thread:
```powershell
cd C:\BYP_Ops_System\backend
git status
git log -1 --oneline
```
Then we pick exactly one target and list the exact files we’re touching in THREAD_HANDOFF.md.

---

## 5) Next info we still need to lock down (one-at-a-time)
- Which Python executable is being used when running GUI and backend commands (so we stop hitting “multiple Python installs” weirdness).


## Rep Name (next foundational feature)
- Decision: **Store `rep_name` on orders** (DB column) and auto-fill from login later.
- For now: default value is **`SB`** until auth/admin panel exists.
- UI: Rep is a **dropdown** limited to approved reps (no free-text).
- GUI requirement: Rep column appears **after Status and before Artist**.

### Approved reps list (initials → name)
- `SB` → Steve Bassett
- `RM` → Ron Mewis
- `AML` → Allison Lineberry
- `JS` → Jon Shults
- `CD` → Celine DeLeon

Future: Admin panel must make add/remove reps easy.
