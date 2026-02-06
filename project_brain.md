# Project_Brain.md — SP Order System (Web) — Canonical State

## Current Date
- 2026-02-06 (America/Chicago)

## Project Summary
Web-based SP Order System (FastAPI + SQLite) replacing legacy FileMaker workflows. Includes user login/session handling, orders CRUD, search UI, clients admin, Trello integration fields, and print-ready order output (to be re-added).

---

## Current Truth (Known-Good)
### Latest Stable Savepoint
- Tag: **savepoint-order-created-updated-mdy-2026-02-06**
- (Prior) Tag: **savepoint-clear-refresh-fixed-2026-02-05**

### Confirmed Working
- Cookie sessions work
- Inactive users get kicked server-side
- Search page loads and is stable
- Search toolbar layout (DO NOT rearrange in JS):
  - Left: My Drafts, All, Search, Clear
  - Middle: New order, Clients
  - Right: Admin, Logout
- “Logged in as…” display behaves correctly
- Clients page works for admin + non-admin:
  - Active-only default
  - Show inactive works (no 422)
  - Active checkbox persists
  - Edit fields persist
  - No delete UI

### Search Page Safe Enhancements (Working)
- Artist column: single line + ellipsis + hover tooltip (full text)
- Notes column: first line only + ellipsis + hover tooltip (full text)
- Clear button: clears fields and refreshes results to All orders (forced re-run)

### Order Page Timestamp Fixes (Working)
- Order page shows Created + Updated timestamps
- Order page date display format: MM/DD/YYYY
- Removed stray dev helper line: “Editable here: Asset Type (draft only), Notes”
- Removed Client Email and Client Phone rows from Order page

---

## Root Cause Learnings (Don’t Repeat)
### Clear button issue
- Clear was clearing UI but not triggering fetch/refresh reliably.
- Fix: force `runSearch(true)` after Clear click on next tick (+ small delayed backup) without moving toolbar layout.

### Created/Updated blank on order page (while DB had values)
- DB had created_at / updated_at values.
- Order page fetches `/orders/{id}` (API), not `/order/{id}` (HTML view).
- `/orders/{id}` used `response_model=OrderResponse`, which dropped timestamps because schema didn’t include them.
- Fix: `GET /orders/{order_id}` now returns an explicit payload including `created_at` / `updated_at` (and pass-through for string timestamps).
- Also fixed a bad patch that caused `SyntaxError: return outside function` (indentation).

---

## Canonical Rules (Standing Instructions)
- One change at a time
- No manual file editing
- User uploads file → assistant returns downloadable replacement with **exact same filename**
- No renaming files. Ever.
- Windows only
- Desktop work forbidden until web is finished
- Do not reorder/move toolbar elements in JS (fragile)

---

## Current Branch / Repo Practices
- Branch (as previously): fix-delete-override
- Frequent savepoint tagging after each working chunk

---

## How to Run
```powershell
cd C:\BYP_Ops_System\backend
.\venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

---

## Files Recently Touched (Last Two Savepoints)
- `app/web/app.js`
  - Clear forces refresh of results after clearing
  - Artist/Notes single-line + ellipsis + hover tooltips
- `app/main.py`
  - Order page displays Created/Updated as MM/DD/YYYY
  - Removed Client Email/Phone display
  - Removed “Editable here…” hint line
- `app/routes/orders.py`
  - `GET /orders/{order_id}` returns timestamps (no response_model dropping)

---

## To-Do (Next Priorities)
### Priority A — Re-add Print Feature (Minimal + Stable)
1. Add route: `GET /order/{order_id}/print`
2. Add Search-row Print link/button (opens new tab)
3. Print page requirements:
   - Show Created date only
   - One-page sane print layout (don’t redesign beyond needed)

### Priority B — Optional Search Polish
- Admin → Deleted Orders: Artist one line + hover tooltip (nice-to-have)
