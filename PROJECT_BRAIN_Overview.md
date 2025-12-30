# PROJECT_BRAIN Overview — SPorder Backend (LOCKED WORKING STATE)
**Date locked:** 2025-12-23  
**Status:** ✅ Server runs, ✅ Swagger loads, ✅ GET /orders works, ✅ POST /orders/new works

---

## 0) The Prime Directive
- **No assumptions.** If we don’t *know*, we verify.
- **One step at a time.** You run a step, paste output, we move on.
- **Restore working state first.** No new features until it’s running clean.
- **Windows-first.**
- **Do not rename existing files.** If a new name is needed, create a new file and leave the old one untouched.

---

## 1) Known Working Startup Procedure (Step-by-step)
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

### Step 4 — Verify in browser
- Health check: `http://127.0.0.1:8000/`  
  Expected:
```json
{"status":"BYP Ops backend online"}
```

- Swagger: `http://127.0.0.1:8000/docs`  
  Expected: **Orders** section is visible.

---

## 2) Working API Checks (Confirmed)
### GET /orders/
From Swagger: **GET** `/orders/`  
✅ Returns **200** (list of orders)

### POST /orders/new
Body used:
```json
{
  "artist": "Test Artist",
  "asset_type": "radio",
  "notes": "hello"
}
```

✅ Returns **200** with created object (example):
```json
{
  "id": 7,
  "artist": "Test Artist",
  "asset_type": "radio",
  "notes": "hello"
}
```

---

## 3) Files and Structure (Confirmed)
Project root:
- `C:\BYP_Ops_System\backend`

Key files:
- `app\routes\orders.py` ✅ exists
- `app\models\orders.py` ✅ exists
- `app\models\sp_master.py` ✅ exists (defines `SPNumber`)
- `app\schemas\order.py` ✅ exists
- `main.py` ✅ exists

---

## 4) Fixes Applied to Reach Working State (DO NOT UNDO)
### A) `backend\main.py`
**Problem:** imported non-existent `app.routes.order`  
**Fix:** changed import to `app.routes.orders`

Current:
```py
from fastapi import FastAPI
from app.routes.orders import router as orders_router

app = FastAPI()
app.include_router(orders_router)

@app.get("/")
def read_root():
    return {"status": "BYP Ops backend online"}
```

### B) `app\routes\orders.py`
**Problem:** imported non-existent `app.models.order`  
**Fix:** changed to `app.models.orders`

Critical imports:
```py
from app.schemas.order import OrderCreate, OrderResponse
from app.models.orders import Order
```

### C) `app\models\orders.py`
**Problem:** SQLAlchemy failed resolving relationship `"SPNumber"` because the class wasn’t imported/registered.  
**Fix:** import the class directly + use class reference in relationship.

Critical lines:
```py
from app.models.base import Base
from app.models.sp_master import SPNumber

sp = relationship(SPNumber, backref="orders")
```

---

## 5) What “Working” Means Right Now
- Uvicorn starts without import errors.
- `/` returns status JSON.
- Swagger loads and shows Orders routes.
- GET `/orders/` returns **200**.
- POST `/orders/new` returns **200** and creates a record.

If any of these fail, we stop and restore this state before doing anything else.
