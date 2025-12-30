# SPOrder System — New Thread Runbook + Finish Plan

**Date:** 2025-12-30  
Purpose: when a new chat/thread starts, this document gets us back to *exactly* where we are, fast — and tells us what to build next without guesswork.

---

## 0) Golden rules (do not violate)
- **First command every time:** `irm http://127.0.0.1:8000/`
- **No assumptions. Ask if unknown.**
- **One step at a time.**
- **Code requests = full-file replacement only.**
- **Do not rename files.**
- If anything breaks: **restore from Git tag** and continue.

---

## 1) Current state (what exists right now)

### Git
Repo root: `C:\BYP_Ops_System`

Savepoints:
- `savepoint-addl-vers`
- `savepoint-delete`  ✅ latest working savepoint

If the GUI is broken/weird:
- `git checkout savepoint-delete -- backend\OrderSearchGUI.pyw`

### Alembic
- Alembic initialized under `backend\alembic`
- Baseline stamped + migration added for `sp_master.additional_version_of`

### Backend features working
- Orders CRUD + search
- Revisions: `POST /orders/{id}/revise` (creates child, sets `revision_of`)
- Additional versions: `POST /orders/{id}/addl_vers` (creates child, sets `additional_version_of`)
- Delete: initials required; finalized delete supported w/ force + GUI double speed bump

### GUI features working (at `savepoint-delete`)
- Search grid: Status first column, optional Order ID column
- Details: Delete works + finalized speed bump
- Details: Finalize prompts for Trello IDs (placeholder)
- Details: Override Edit unlocks fields, but workflow still needs fixing (see below)

---

## 2) How to start a new thread (exact steps)

### Step A — server health check (always)
```powershell
irm http://127.0.0.1:8000/
```

Expected:
- `status : BYP Ops backend online`

### Step B — confirm Git is clean + on the right savepoint
From `C:\BYP_Ops_System`:
```powershell
git status
git tag
git rev-parse --abbrev-ref HEAD
git log --oneline -1
```

If anything is broken:
```powershell
git checkout savepoint-delete
```

### Step C — run the GUI from PowerShell (so tracebacks show)
From `C:\BYP_Ops_System\backend`:
```powershell
python .\OrderSearchGUI.pyw
```

---

## 3) Testing checklist (fast smoke tests)

### Create a new order
- Use GUI “New” or:
```powershell
irm http://127.0.0.1:8000/orders/new -Method Post -ContentType "application/json" -Body '{"artist":"Smoke Test","asset_type":"video","notes":"smoke"}'
```

### Create a revision
```powershell
irm http://127.0.0.1:8000/orders/<ID>/revise -Method Post
```

### Create an additional version
```powershell
irm http://127.0.0.1:8000/orders/<ID>/addl_vers -Method Post
```

### Finalize (placeholder Trello)
```powershell
irm "http://127.0.0.1:8000/orders/<ID>/finalize?trello_card_id=TESTCARD&trello_checklist_id=TESTCHECK" -Method Post
```

### Delete (initials required)
```powershell
irm "http://127.0.0.1:8000/orders/<ID>?initials=SB" -Method Delete
```

---

## 4) What needs to be built next (no wandering)

### A) Override should “reopen” to draft automatically
Current pain:
- Override edit allows editing, but:
  - Save can look like it hangs (UI state not refreshed)
  - Finalize stays disabled because status stays `finalized`

Required behavior (Steve decision):
- When override confirmed:
  - order immediately becomes `draft`
  - `finalized_at` cleared
  - user can edit + save normally
  - user can finalize again

Implementation plan:
1) Backend: add endpoint
   - `POST /orders/{id}/unfinalize` (or `reopen`)
   - sets `status="draft"`, `finalized_at=None` (and **does not** require Trello info)
2) GUI: Override Edit… calls that endpoint and refreshes the detail window.
3) GUI: Save always re-fetches the order after PATCH so it never “hangs”.

### B) Preserve GUI layout
- Absolutely no redesign.
- Fix behavior only.

### C) (Later) Trello automation so Finalize doesn’t ask for IDs
Target:
- Finalize button triggers backend to:
  - create Trello card if needed
  - create checklist titled with SP #
  - store trello ids
  - mark order finalized
Then GUI Finalize = one click.

---

## 5) Deployment finish line (high level)
Constraints:
- <10 users
- Houston office + LA office + remote/mobile
- Steve is primary dev

Likely “sane” path:
- Single hosted backend (VM) + Postgres
- Reverse proxy (Caddy/Nginx) + HTTPS
- Auth (simple login) + role-based permissions (admin/user)
- Frontend served over HTTPS (or bundled) so remote users access it via URL
- Backups + logs

This is **not** today’s task — this is the finish line.

