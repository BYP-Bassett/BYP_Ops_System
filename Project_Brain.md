# PROJECT_BRAIN.md — SAVE POINT (2025-12-24) — BYP Ops Backend (FastAPI)

## What this is
This is the **known-good save point** for the BYP Ops backend project so a new chat can pick up **immediately** without guesswork.

## Non‑negotiable rules (Steve rules)
- **No assumptions.** If we don’t know, we verify on Steve’s machine.
- **One step at a time.** No multi-step “do all this” dumps unless explicitly requested.
- **Windows/PowerShell-first.**
- When Steve asks for code edits: **provide full file contents**, not piecemeal fragments.

---

## Current known-good status
- Backend runs clean under **Uvicorn** at: `http://127.0.0.1:8000`
- Root endpoint returns:
  - `{"status":"BYP Ops backend online"}`
- Orders endpoints work:
  - `GET /orders/` returns a **list/array** of orders (not wrapped in `{value: ...}`).
  - `POST /orders/new` creates orders and persists them.
  - `GET /orders/{id}` returns order or **404**.
  - `PATCH /orders/{id}` updates fields (notes, etc.) but **cannot change asset_type** (400).
  - `DELETE /orders/{id}` deletes order or **404**.
- SP generation is correct:
  - **radio + video** → generate SP via `generate_next_sp`
  - **art** → no SP
- API response includes nested SP details:
  - `sp_id` and `sp` object with `id`, `sp_number`, `order_type`, `revision_of`

---

## The “server window has no prompt” thing (important)
When you run Uvicorn in a PowerShell window, it **takes over** that window.  
You need a **second PowerShell window** to run `irm` test commands.

---

## PowerShell gotchas we hit (and the fixes)
### 1) `irm /orders/` returns an array, not `{ value: [...] }`
So these are correct:
```powershell
(irm http://127.0.0.1:8000/orders/).Count
(irm http://127.0.0.1:8000/orders/)[-1]
```
And this is wrong:
```powershell
$r = irm http://127.0.0.1:8000/orders/
$r.value   # <- this yields nulls because there is no .value
```

### 2) `.Count` can be blank if the pipeline returns a single object
Force array semantics:
```powershell
@($orders | Where-Object id -eq 11).Count
```

### 3) SQLAlchemy columns don’t have `.lower()` in queries
Use `func.lower()`:
```powershell
python -c "from sqlalchemy import func; ..."
```

---

## Working directory + venv
- Project path: `C:\BYP_Ops_System\backend`
- Activate venv:
```powershell
cd C:\BYP_Ops_Systemackend
.env\Scripts\Activate.ps1
```

---

## Start server (known-good)
In **PowerShell window #1**:
```powershell
cd C:\BYP_Ops_Systemackend
.env\Scripts\Activate.ps1
uvicorn main:app --reload
```

In **PowerShell window #2**, test:
```powershell
cd C:\BYP_Ops_Systemackend
.env\Scripts\Activate.ps1
irm http://127.0.0.1:8000/ | ConvertTo-Json -Depth 5
irm http://127.0.0.1:8000/orders/ | ConvertTo-Json -Depth 8
```

---

## What we changed/implemented in this save point

### 1) Asset type normalization + allowlist
- Implemented in `app/schemas/order.py` using Pydantic v2 `@field_validator`
- Allowed: `radio`, `video`, `art`
- Normalizes whitespace + case (`" RADIO "` → `"radio"`)
- Rejects invalid types (`banana` → 422)

### 2) Delete endpoint
- Added `DELETE /orders/{order_id}` with 404 if missing
- Used to delete the bad row (banana order id 11 from earlier)

### 3) Consistent order creation uses service layer (SP generation)
- `POST /orders/new` route now calls:
  - `app.services.order_service.create_order(db, payload)`
- This ensures SP generation happens for radio/video.

### 4) PATCH endpoint
- Added `PATCH /orders/{order_id}` that:
  - Applies only provided fields (`exclude_unset=True`)
  - Rejects changing `asset_type` (400) to avoid SP/history problems

### 5) API response shows SP data
- `OrderResponse` includes:
  - `sp_id`
  - nested `sp` object: `id`, `sp_number`, `order_type`, `revision_of`

### 6) One-time DB cleanup
- Normalized existing bad casing:
  - `RADIO` → `radio` (id 3)
- Verified no non-lowercase left.

---

## Current file contents (canonical at this save point)

### `app/models/orders.py`
- Order has fields:
  - `artist`, `asset_type`, `notes`
  - `sp_id` FK to `sp_master.id`
  - workflow fields: `order_type`, `description`, `length`, `instructions`
  - revision tracking: `is_revision`, `parent_order_id`, `revision_of`
  - relationship: `sp = relationship(SPNumber, backref="orders")`

### `app/models/sp_master.py`
- `SPNumber` has:
  - `sp_number`, `order_type`, `created_at`, `notes`, `revision_of`

### `app/services/order_service.py`
- Generates SP only for `["radio","video"]`
- Creates Order and sets `sp_id` when applicable

### `app/routes/orders.py` (full file)
```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.order import OrderCreate, OrderUpdate, OrderResponse
from app.models.orders import Order
from app.services.order_service import create_order as create_order_service

router = APIRouter(prefix="/orders", tags=["Orders"])


@router.post("/new", response_model=OrderResponse)
def create_order(payload: OrderCreate, db: Session = Depends(get_db)):
    return create_order_service(db, payload)


@router.get("/{order_id}", response_model=OrderResponse)
def get_order(order_id: int, db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.patch("/{order_id}", response_model=OrderResponse)
def patch_order(order_id: int, payload: OrderUpdate, db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    updates = payload.model_dump(exclude_unset=True)

    # Prevent changing asset_type (SP logic + history headaches)
    if "asset_type" in updates and updates["asset_type"] != order.asset_type:
        raise HTTPException(status_code=400, detail="asset_type cannot be changed")

    for k, v in updates.items():
        setattr(order, k, v)

    db.commit()
    db.refresh(order)
    return order


@router.delete("/{order_id}")
def delete_order(order_id: int, db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    db.delete(order)
    db.commit()
    return {"deleted_id": order_id}


@router.get("/", response_model=list[OrderResponse])
def list_orders(db: Session = Depends(get_db)):
    return db.query(Order).all()
```

### `app/schemas/order.py` (full file)
```python
from pydantic import BaseModel, field_validator, ConfigDict
from typing import Optional

ALLOWED_ASSET_TYPES = {"radio", "video", "art"}


class OrderCreate(BaseModel):
    artist: str
    asset_type: str
    notes: Optional[str] = None

    # workflow fields
    order_type: Optional[str] = None
    description: Optional[str] = None
    length: Optional[str] = None
    instructions: Optional[str] = None

    # revision fields
    is_revision: Optional[bool] = False
    parent_order_id: Optional[int] = None
    revision_of: Optional[str] = None

    @field_validator("asset_type", mode="before")
    @classmethod
    def normalize_and_validate_asset_type(cls, v):
        if v is None:
            raise ValueError("asset_type is required")
        s = str(v).strip().lower()
        if not s:
            raise ValueError("asset_type cannot be blank")
        if s not in ALLOWED_ASSET_TYPES:
            raise ValueError(
                f"asset_type must be one of: {', '.join(sorted(ALLOWED_ASSET_TYPES))}"
            )
        return s


class OrderUpdate(BaseModel):
    # all optional for PATCH
    artist: Optional[str] = None
    asset_type: Optional[str] = None
    notes: Optional[str] = None

    # workflow fields
    order_type: Optional[str] = None
    description: Optional[str] = None
    length: Optional[str] = None
    instructions: Optional[str] = None

    # revision fields
    is_revision: Optional[bool] = None
    parent_order_id: Optional[int] = None
    revision_of: Optional[str] = None

    @field_validator("asset_type", mode="before")
    @classmethod
    def normalize_and_validate_asset_type_if_present(cls, v):
        if v is None:
            return None
        s = str(v).strip().lower()
        if not s:
            raise ValueError("asset_type cannot be blank")
        if s not in ALLOWED_ASSET_TYPES:
            raise ValueError(
                f"asset_type must be one of: {', '.join(sorted(ALLOWED_ASSET_TYPES))}"
            )
        return s


class SPLink(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sp_number: str
    order_type: str
    revision_of: Optional[str] = None


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    artist: str
    asset_type: str
    notes: Optional[str]
    sp_id: Optional[int] = None
    sp: Optional[SPLink] = None
```

---

## Where we were about to go next
Next planned feature (not started yet):
- **Revision endpoint** proposal:
  - `POST /orders/{id}/revise`
  - Creates a new order as a revision of an existing order
  - Copies fields, sets revision tracking fields
  - Generates new SP for radio/video and sets `SPNumber.revision_of`
But we **stopped here** to create a stable save point with nothing broken.

---
