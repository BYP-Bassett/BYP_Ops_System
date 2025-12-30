# Project_Brain.md — SPOrder System (Save Point)

**Date:** 2025-12-24  
**Project:** BYP Ops / SPOrder System (FastAPI backend)  
**Goal:** Replace/modernize BYP order workflow with a real API: Orders + SP generation + revisions + search.

---

## Non‑negotiable working rules (Steve’s workflow)
- **No assumptions.** If anything is unknown/uncertain, ask.
- **One direction at a time.** One step, then wait.
- **Full-file outputs only** when you request code. No “add these lines” micro-edits.
- **Do not rename or overwrite existing files.** If a new file is needed, create a new one and leave existing ones intact.
- **Windows paths** (this project lives on Windows).
- **PowerShell** is the console. Use `irm` / `Invoke-RestMethod` (not `GET`).

---

## Current status (this save point is stable)
✅ Backend is running and stable.  
✅ SP generation works for radio/video orders.  
✅ `asset_type` is **immutable** (PATCH must not change it).  
✅ Revisions are implemented and verified as an SP chain.  
✅ Standalone SP endpoints exist (`/sp/...`).  
✅ Orders search endpoint exists (`/orders/search`) with filters and correct sorting.

---

## Local paths / runtime
- Project root: `C:\BYP_Ops_System\backend`
- Virtual env: `C:\BYP_Ops_System\backend\venv`

### Start the API (PowerShell)
```powershell
cd C:\BYP_Ops_System\backend
uvicorn main:app --reload
```

### Confirm server is up
```powershell
irm http://127.0.0.1:8000/
```
Expected:
```json
{"status":"BYP Ops backend online"}
```

---

## API Routes (current OpenAPI)
- `GET /` — health check
- `GET /orders/` — list orders (raw list; no sorting logic applied here)
- `GET /orders/{order_id}` — get one order
- `POST /orders/new` — create a new order (generates SP for radio/video)
- `PATCH /orders/{order_id}` — update allowed fields (**cannot change asset_type**)
- `POST /orders/{order_id}/revise` — create a revision order (new SP, chains `revision_of`)
- `GET /orders/search` — searchable orders with filters (sorted by highest SP first)
- `GET /sp/` — list SP records (**newest first**)
- `GET /sp/{sp_id}` — fetch one SP record

---

## Key business rules (must not break)
### 1) `asset_type` cannot be changed
Attempting to PATCH `asset_type` returns:
```json
{"detail":"asset_type cannot be changed"}
```

### 2) Revisions are new orders, not edits
- Revisions are created via:
  - `POST /orders/{order_id}/revise`
- A revision:
  - Creates a **new Order**
  - Generates a **new SP** (for radio/video)
  - Sets the new SP’s `revision_of` to the parent SP number

Verified chain example:
- `SP000014 → SP000015 → SP000016`

### 3) SP endpoints
- SP records return `created_at` as an ISO timestamp string (Pydantic uses `datetime` type).
- `/sp/` lists newest first via `ORDER BY id DESC`.

---

## Search behavior (Orders)
Endpoint: `GET /orders/search`

### Current search logic
- `q=` is the “main search box” and searches **artist** (contains + case-insensitive).
- Additional filters can be combined (AND):
  - `artist=...`
  - `notes=...`
  - `asset_type=radio|video|...` (contains + case-insensitive)
  - `sp_number=SP000016` (contains + case-insensitive)

### Sorting (per Steve’s requirement)
- Search results sort by **highest SP# first**:
  - Orders with NULL `sp_id` fall to the bottom
  - Then `sp_id DESC`, then `order id DESC`

### Example calls
```powershell
# Artist search
irm "http://127.0.0.1:8000/orders/search?q=SP%20Test" | ConvertTo-Json -Depth 8

# Artist + asset type filter
irm "http://127.0.0.1:8000/orders/search?q=SP%20Test&asset_type=radio" | ConvertTo-Json -Depth 8

# Find by SP number
irm "http://127.0.0.1:8000/orders/search?sp_number=SP000016" | ConvertTo-Json -Depth 8
```

---

## Smoke tests (known-good)
### Create new order
```powershell
$body = @{ artist="SP Test"; asset_type="radio"; notes="base order" } | ConvertTo-Json
irm "http://127.0.0.1:8000/orders/new" -Method Post -ContentType "application/json" -Body $body | ConvertTo-Json -Depth 8
```

### Create revision
```powershell
irm "http://127.0.0.1:8000/orders/12/revise" -Method Post | ConvertTo-Json -Depth 8
```

### Confirm SP endpoint
```powershell
irm "http://127.0.0.1:8000/sp/16" | ConvertTo-Json -Depth 5
```

### Confirm immutability
```powershell
$body = @{ asset_type = "video" } | ConvertTo-Json
irm "http://127.0.0.1:8000/orders/14" -Method Patch -ContentType "application/json" -Body $body
```

---

## Files modified/created in this phase
### Modified
- `main.py` — includes `orders_router` and `sp_router`
- `app/schemas/sp.py` — `created_at` is `datetime` (not `str`), includes `revision_of`
- `app/routes/orders.py` — adds `/orders/search` and supports `/orders/{id}/revise`

### Created
- `app/routes/sp.py` — `/sp/` and `/sp/{id}` endpoints

---

## Known gotchas
- PowerShell does **not** have `GET` as a command. Use `irm` or `Invoke-RestMethod`.
- If `/sp/{id}` returns 500 with `ResponseValidationError` on `created_at`, your schema type is wrong (must be `datetime`).

---

## Next logical steps (not implemented yet)
- Upgrade `q=` to search **multiple fields** (artist + notes + sp_number) while keeping field filters.
- Add search for date ranges once Orders have reliable timestamp columns.
- Expand Orders schema to include future fields (client/company, status, due dates, etc.).
- Build Tours/Clients models + endpoints after Orders is fully solid.

---
