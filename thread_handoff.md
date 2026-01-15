# SP Order System — Thread Handoff (Thread #22 start)

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

### Web UI — WORKING (now requires login)
- Landing/search/list: `http://127.0.0.1:8000/`
- Order detail: `http://127.0.0.1:8000/order/{id}`
- Detail pulls JSON from: `/orders/{id}`
- Draft-only `asset_type` dropdown on web detail; Save persists

### Auth + Sessions — WORKING
- Login page: `/login`
- Current session info: `/me` returns `authenticated`, `user_id`, `username`, `rep_code`, `rep_name`, `role`, `is_active`
- Web sessions are cookie-based (SessionMiddleware)
- Desktop GUI login is required and **remembers credentials** via local cookie persistence (cookie jar)

### Admin Users page (web) — WORKING
- Admin UI: `/admin/users`
- Supports: list users, create user, set password, enable/disable, set role/admin (as implemented in `app/main.py`)
- NOTE: “disable user should kill existing sessions” is a known next-hardening item (verify behavior after disabling).

### Finalize behavior (backend) — WORKING
Finalizing radio/video with missing Trello linkage auto-creates:
- Trello card in rep’s board “To Do”
- Checklist named SP# (e.g., `SP000105`)
- Stores `trello_card_id` + `trello_checklist_id` back on the order
- Sets `status=finalized` and `finalized_at`

### Desktop GUI — WORKING
- Desktop finalize uses backend finalize plumbing (no Trello prompts, no useless confirm)
- Draft `asset_type` changes: Save does not freeze; UI updates immediately
- Backend keeps `SP.order_type` synced with `order.asset_type` for drafts

### Trello credentials bug — FIXED
Root cause: `.env` had UTF-8 BOM (invisible leading char), so `TRELLO_KEY` parsing flaked out.  
Fix: Trello env load strips BOM + `.env` re-saved UTF-8 (no BOM). Finalize on order **117** confirmed.

### New audit stamping — WORKING
- DB now has: `orders.created_by_user_id`, `orders.updated_by_user_id`, `orders.deleted_by_user_id` (FK → `users.id`)
- `app/routes/orders.py` stamps these values on create/update/delete/finalize/unfinalize/revise/duplicate/addl-vers.
- Legacy `deleted_by` (string initials) still exists and is still used by current delete endpoint.

---

## 2) Branch + latest savepoints

**Branch:** `fix-delete-override`  
**Remote:** `https://github.com/BYP-Bassett/BYP_Ops_System.git`

**Key tags (known good):**
- `savepoint-trello-finalize-autocreate-2026-01-12` (commit 426cd5da…)
- `savepoint-trello-config-and-revise-2026-01-12` ✅ (commit 17aef48…)
- `savepoint-desktop-finalize-backend-2026-01-13` ✅
- `savepoint-web-asset-type-edit-2026-01-13` ✅
- `savepoint-pre-auth-admin-2026-01-14` ✅
- `savepoint-auth-desktop-cookie-2026-01-14` ✅ (NEW)

**Alembic note:** multiple heads were merged (heads were `b3f5c0d1a9e2` and `b7d4c21f8a90`); a merge migration was created.  
Sanity: `python -m alembic heads` should now show **one head**.

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
- If a file change is needed: Steve uploads the current file → return a downloadable replacement file with the **exact same filename**.
- No renaming files. Ever.
- Windows paths only.
- GUI layout tweaks pinned unless explicitly unpinned.
- No `${ }` inside Python f-strings that embed HTML/JS (it will explode).
- Don’t “assume” auth/cookies in PowerShell: `irm` needs its own session.
  - Passwords containing `$` must use single quotes in PowerShell (`'Doc$$2112'`) or they get mangled.

---

## 5) Next Single Target

### Target: Desktop Admin Users page (parity with web admin)
Add a desktop Admin window inside `OrderSearchGUI.pyw` that can:
- List users
- Create user
- Enable/disable user
- Set/reset password
- Set role/admin

**Done when:**
- Admin window works end-to-end from desktop
- Non-admin users cannot open it
- Disabling a user blocks future requests (and ideally clears/invalidates existing sessions on next request)

**One-file-at-a-time kickoff file:** `C:\BYP_Ops_System\backend\OrderSearchGUI.pyw`

---

## 6) Smoke Tests + Landmines

### Smoke tests
API reachable:
```powershell
irm "http://127.0.0.1:8000/orders/search2?limit=5&offset=0"
```

Session:
- Browser: log in at `/login`
- PowerShell (cookie session):
```powershell
$base = "http://127.0.0.1:8000"
$session = New-Object Microsoft.PowerShell.Commands.WebRequestSession
irm "$base/login" -WebSession $session | Out-Null
$u = 'sb'
$p = 'Doc$$2112'
irm "$base/login" -Method Post -WebSession $session -Body @{ username = $u; password = $p } | Out-Null
irm "$base/me" -WebSession $session
```

Order timestamps present:
```powershell
irm "http://127.0.0.1:8000/orders/72" | select created_at, updated_at
```

Finalize Trello auto-create:
```powershell
irm -Method Post "http://127.0.0.1:8000/orders/117/finalize"
irm "http://127.0.0.1:8000/orders/117" | select id,status,trello_card_id,trello_checklist_id,finalized_at
```

Draft asset_type change allowed + SP synced:
```powershell
irm -Method Patch "http://127.0.0.1:8000/orders/131" -ContentType "application/json" -Body '{"asset_type":"radio"}'
```

Audit stamp sanity:
```powershell
.\venv\Scripts\python.exe -c "import sqlite3; c=sqlite3.connect(r'C:\BYP_Ops_System\backend\byp_ops.db'); cur=c.cursor(); cur.execute('select updated_by_user_id from orders where id=?',(131,)); print(cur.fetchone())"
```

### Landmines
- Web UI blank/weird → Ctrl+F5 + console
- `/favicon.ico` 404 harmless
- Trello creds “missing” again → `.env` BOM/encoding
- Session crash `SessionMiddleware must be installed` → middleware order / guard touching `request.session` too early
- Missing package `itsdangerous` breaks SessionMiddleware import → install it in venv if it ever reappears
- Alembic “multiple heads” → needs merge migration
- DELETE endpoint expects initials as **query param** (not JSON):
  - Works: `/orders/142?initials=SB`
