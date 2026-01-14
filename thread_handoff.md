# SP Order System — Thread Handoff (Thread #21 start)

## 1) Current Truth (what is working right now)

**Backend root:** `C:\BYP_Ops_System\backend`  
**venv:** `.\venv\Scripts\python.exe`  
**DB:** `backend\byp_ops.db` (SQLite)  
**Engine URL:** `sqlite:///C:/BYP_Ops_System/backend/byp_ops.db`

### Start API
```powershell
cd C:\BYP_Ops_System\backend
.\venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

### Web UI
- Search/list page: `http://127.0.0.1:8000/`
- Order detail page: `http://127.0.0.1:8000/order/{id}`
- Detail page pulls JSON from `/orders/{id}`
- Web detail supports editing draft orders (asset_type dropdown draft-only) and Save works

### Finalize behavior (backend) — WORKING
Finalizing **radio/video** with missing Trello linkage auto-creates:
- Trello card (title = full artist) in rep’s board “To Do” list
- Checklist named SP# (e.g., `SP000105`)
- Stores `trello_card_id` + `trello_checklist_id` back on the order
- Sets `status=finalized` and `finalized_at`

### Desktop GUI — WORKING
- Desktop finalize uses backend finalize plumbing:
  - No prompts for Trello card/checklist IDs
  - Removed useless Yes/No confirmation popup on finalize
- Desktop can change `asset_type`, and Save no longer freezes
- Backend allows draft `asset_type` changes and keeps `SP.order_type` in sync

### Trello credentials bug — FIXED
Root cause: `.env` had UTF-8 BOM (invisible leading char), so `TRELLO_KEY` didn’t parse reliably.  
Fix: `app/services/trello_service.py` now loads `.env` robustly and strips BOM; `.env` re-saved as UTF-8 (no BOM).  
Finalize on order **117** confirmed working after fix.

### Web Delete button situation (status)
- We successfully restored web stability after multiple f-string/JS brace landmines.
- Web now runs again; a Delete button experiment exists, but behavior still “meh” and is deprioritized.
- We moved on rather than perfecting web delete UX.

---

## 2) Branch + latest savepoints

**Branch:** `fix-delete-override`

**Key tags:**
- `savepoint-trello-finalize-autocreate-2026-01-12` (commit `426cd5da1af0e9fd8ab12fd8864c9f9732421ad9`)
- `savepoint-trello-config-and-revise-2026-01-12` ✅ (commit `17aef48`)
- `savepoint-desktop-finalize-backend-2026-01-13` ✅
- `savepoint-web-asset-type-edit-2026-01-13` ✅
- `savepoint-pre-auth-admin-2026-01-14` ✅ (NEW — before auth/admin work)

**Remote:** `origin = https://github.com/BYP-Bassett/BYP_Ops_System.git`

---

## 3) How to start server + how to start GUI

### API
```powershell
cd C:\BYP_Ops_System\backend
.\venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

### Desktop GUI
```powershell
cd C:\BYP_Ops_System\backend
python OrderSearchGUI.pyw
```

(Optional compile check)
```powershell
python -m py_compile .\OrderSearchGUI.pyw
```

---

## 4) Canonical Rules (must not violate)

- One step at a time.
- No manual file editing.
- If a file change is needed: **Steve uploads current file → I return a replacement download with the same exact filename.**
- No renaming files. Ever.
- Windows paths only.
- GUI layout tweaks pinned unless explicitly unpinned.
- No ${} inside Python f-strings that embed HTML/JS.

---

## Next Single Target

### Target: Start “finished system” work with Auth + Admin Users page
Steve wants:
- Admin page to add/disable users and assign rights
- “My Drafts” button on the **web** (like desktop)

**Scope for next thread (one-file-at-a-time):**
1) Confirm DB plumbing location (session/base) so we can add a `users` table cleanly via Alembic.
2) Then implement minimal auth + admin users page + web “My Drafts” (tied to logged-in rep).

**Next file to upload (first step):**
- `backend/app/database/session.py`

Done when (phase 1):
- We can clearly identify `Base`, engine/session creation, and Alembic target metadata wiring.

---

## Smoke Tests + Landmines

### API reachable
```powershell
irm "http://127.0.0.1:8000/orders/search2?limit=5&offset=0"
```

### Order timestamps present
```powershell
irm "http://127.0.0.1:8000/orders/72" | select created_at, updated_at
```

### Finalize Trello auto-create
```powershell
irm -Method Post "http://127.0.0.1:8000/orders/117/finalize"
irm "http://127.0.0.1:8000/orders/117" | select id,status,trello_card_id,trello_checklist_id,finalized_at
```

### Draft asset_type change allowed + SP synced
```powershell
irm -Method Patch "http://127.0.0.1:8000/orders/131" -ContentType "application/json" -Body '{"asset_type":"radio"}'
```

### Web asset_type edit works
- Open: `http://127.0.0.1:8000/order/131`
- Change draft-only dropdown, Save, refresh, confirm persisted

### Landmines
- Web UI blank / weird layout → **Ctrl+F5** + console
- `/favicon.ico` 404 harmless
- Trello creds “missing” again → `.env` encoding/BOM (guarded + file re-saved)
- `.env` must be clean `KEY=VALUE` lines only
- **Big one:** JS braces inside Python f-strings can crash Uvicorn. Avoid embedding complex JS in f-strings.
