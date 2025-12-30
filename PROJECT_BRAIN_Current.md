# PROJECT_BRAIN — SPorder Backend (CURRENT / LOCKED WORKING STATE)

**Locked on:** 2025-12-23 (America/Chicago)  
**What this is:** The *current* known-good state + exact resume steps, so we don’t re-live the “start-from-scratch” clown show.

---

## 0) Hard Rules (non‑negotiable)
- **No assumptions.** If we don’t *know*, we verify from your machine output.
- **One step at a time.** You run a step, paste output, then we decide the next step.
- **Recovery first.** If it’s not running clean, we restore the locked state before building anything.
- **Windows-first.**
- **Do not rename existing files.** If a different name is needed, create a new file and leave the old one untouched.

---

## 1) Current Status (Verified Working)
✅ `uvicorn main:app --reload` runs  
✅ `http://127.0.0.1:8000/` returns:
```json
{"status":"BYP Ops backend online"}
```
✅ Swagger loads: `http://127.0.0.1:8000/docs`  
✅ **Orders** section exists  
✅ **GET** `/orders/` returns **200**  
✅ **POST** `/orders/new` returns **200** and creates an order

### Confirmed test create
Request body used:
```json
{
  "artist": "Test Artist",
  "asset_type": "radio",
  "notes": "hello"
}
```

Example response seen:
```json
{
  "id": 7,
  "artist": "Test Artist",
  "asset_type": "radio",
  "notes": "hello"
}
```

---

## 2) Where Everything Lives (Verified)
Project root:
- `C:\BYP_Ops_System\backend`

Key folders (exist):
- `app\routes\`
- `app\models\`
- `app\schemas\`
- `app\database\`

Key files (exist):
- `main.py`
- `app\routes\orders.py`
- `app\models\orders.py`
- `app\models\sp_master.py`
- `app\schemas\order.py`
- `app\database\session.py`

---

## 3) Fixes Applied to Reach This Working State (DO NOT UNDO)
### A) `backend\main.py` import fixed
**Was wrong:** `from app.routes.order ...` (file didn’t exist)  
**Now:**
```py
from fastapi import FastAPI
from app.routes.orders import router as orders_router

app = FastAPI()
app.include_router(orders_router)

@app.get("/")
def read_root():
    return {"status": "BYP Ops backend online"}
```

### B) `app\routes\orders.py` model import fixed
**Was wrong:** `from app.models.order import Order`  
**Now:**
```py
from app.models.orders import Order
```

### C) SQLAlchemy relationship resolution fixed (`SPNumber`)
**Problem encountered:** GET `/orders/` caused SQLAlchemy mapper error because `SPNumber` couldn’t be resolved at runtime.

**Fix applied in `app\models\orders.py`:**
- Import the class directly:
```py
from app.models.sp_master import SPNumber
```
- Use class reference instead of string name:
```py
sp = relationship(SPNumber, backref="orders")
```

---

## 4) Resume Procedure (when everything is closed)
### Step 1 — Open PowerShell and go to backend
```powershell
cd C:\BYP_Ops_System\backend
```

### Step 2 — Activate venv
```powershell
.\venv\Scripts\Activate.ps1
```
Prompt should show `(venv)`.

### Step 3 — Start server
```powershell
uvicorn main:app --reload
```

### Step 4 — Verify
- `http://127.0.0.1:8000/` → status JSON
- `http://127.0.0.1:8000/docs` → Orders section

---

## 5) Fast “Show Me The Evidence” Commands (use these instead of clicking around)
```powershell
dir .\app
dir .\app\routes
dir .\app\models
dir .\app\schemas

type .\main.py
type .\app\routes\orders.py
type .\app\models\orders.py
type .\app\models\sp_master.py
```

---

## 6) Definition of “Back To Working”
We are “back” only if ALL of these are true:
- Uvicorn starts without import errors
- `/` returns the status JSON
- Swagger loads + Orders section appears
- GET `/orders/` returns **200**
- POST `/orders/new` returns **200** and creates a record

If any fails: stop and restore this state first.
