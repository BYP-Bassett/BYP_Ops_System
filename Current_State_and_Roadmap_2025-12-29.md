# SPOrder System — Current State + Roadmap

**Date:** 2025-12-29  
**This doc is separate from Project_Brain.**  
Purpose: capture exactly what’s done, what’s stable, and what we build next so a new thread can resume instantly.

---

## 1) Current stable state (what works right now)

### Backend
- FastAPI running at `http://127.0.0.1:8000`
- SQLite DB: `byp_ops.db`
- Orders CRUD + SP generation:
  - Radio/Video orders auto-generate SP numbers.
  - Art orders do not generate SP numbers.
- `asset_type` is **immutable** (confirmed by tests; PATCH attempts fail with 400).
- Revisions supported:
  - `POST /orders/{id}/revise` creates a new order tied to the parent.
- Search supported (FileMaker-style field inputs):
  - Endpoint: `GET /orders/search`
  - AND logic across fields.
- Draft vs Finalized lifecycle:
  - Draft orders are editable.
  - Finalized orders are read-only unless `override=true`.

### Trello sync behavior (for finalized edits)
- Finalized order can be override-edited (with confirmation in GUI).
- When override-editing a finalized order:
  - Backend deletes the existing Trello checklist,
  - recreates it with the same checklist title concept (SP number or NEW),
  - recreates checklist items from notes,
  - stores the new checklist id back on the order.

### GUI (OrderSearchGUI.pyw)
- Search form matches FileMaker’s mental model: field-specific inputs.
- Enter key triggers search.
- Results grid columns are correct:
  - Artist, Asset Type, Notes, SP Number, Revision Of, Status
- Double-click opens detail window.
- Detail window:
  - Artist displayed at the top (not Order ID).
  - Notes uses full space (JSON removed).
  - Draft: Save + Finalize
  - Finalized: Override Edit… (confirmation) + Save (override sync)

---

## 2) What was deliberately chosen (so we don’t “re-decide” later)

### Search logic
- Field-specific input boxes.
- AND logic across fields.
- Text fields use contains/ilike.
- `asset_type` is exact match.
- SP search uses `sp_number` (not sp_id).

### Post-finalization editing
- Simple confirmation instead of complex locking UI.
- If edited after Trello exists:
  - Do NOT create a second Trello card.
  - Instead: delete and rebuild checklist + items on the existing card.

### Checklist rules
- Checklist title = SP Number for radio/video.
- For art: checklist title remains `NEW` for now.

---

## 3) What’s incomplete / stubbed (known work remaining)

### GUI buttons not wired yet
- “Add’l Vers Of” currently shows “Not yet”.
- “Revision Of” currently shows “Not yet” (even though backend `/revise` exists).

### “Add’l Vers Of” semantics are NOT defined yet
We need Steve to define exactly what it should do before implementing:
- New record or same record?
- New SP or same SP?
- What should happen on Trello (new checklist, same checklist, or new card)?

---

## 4) Next implementation chunk (what we build immediately next)

### Step A — wire “Revision Of” in the GUI
Goal: zero-new-concepts for the users.
- User opens an order.
- Clicks “Revision Of”.
- GUI calls: `POST /orders/{current_id}/revise`
- GUI receives new order id and opens the new order detail window.

### Step B — implement “Add’l Vers Of” (after Steve defines behavior)
We will implement exactly as specified, no guessing.
Likely outcomes depend on semantics:
- Could become a new Order record tied to the same original,
- or a new “version” under the same SP,
- or something else.

---

## 5) How to resume in a new thread (exact procedure)

1. **Confirm server:**
   - `irm http://127.0.0.1:8000/`

2. If server is down:
   - cd to `C:\BYP_Ops_System\backend`
   - activate venv (your usual method)
   - `uvicorn main:app --reload`
   - re-run the health check

3. Run the GUI:
   - Launch `OrderSearchGUI.pyw`
   - Test search + open detail window

4. Next code work (once ready):
   - Implement GUI wiring for “Revision Of” (Step A above)

---

## 6) Files touched/added in the latest rollout (for reference)
Backend:
- `main.py`
- `app/database/migrate.py`
- `app/models/orders.py`
- `app/schemas/order.py`
- `app/routes/orders.py`
- `app/services/order_service.py`
- `app/services/trello_service.py`

GUI:
- `OrderSearchGUI.pyw`

---

## 7) Quick smoke tests
- Health:
  - `irm http://127.0.0.1:8000/`
- Search:
  - `irm "http://127.0.0.1:8000/orders/search?artist=Test&asset_type=video"`
- Open one order in GUI and verify:
  - Status shows DRAFT or FINALIZED correctly
  - Notes area is large and editable only in draft or override
