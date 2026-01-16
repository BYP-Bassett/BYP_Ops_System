# Thread Handoff — SP Order System (Thread #22 → next) — 2026-01-16

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

### Web UI — WORKING (login-gated)
- Search/list: `http://127.0.0.1:8000/`
- Order detail (HTML): `http://127.0.0.1:8000/order/{id}`
- Order detail pulls JSON from: `/orders/{id}`
- Detail supports editing drafts (draft-only asset_type dropdown) + Save works
- **Open Trello Card button on /order/{id}: WORKING** (enabled when `trello_card_id` exists)
- **Pinned:** “Save on Back” / autosave-on-back is NOT implemented (Back just navigates)

### Auth — WORKING
- Login page: `/login`
- Session status: `/me` returns: authenticated, user_id, username, rep_code, rep_name, role, is_active
- Web uses cookie sessions (SessionMiddleware)
- Desktop requires login and can remember credentials via cookie persistence
- **Hardening:** inactive user now gets kicked (existing sessions stop working once `is_active=false`)

### Admin (web) — WORKING
- Admin users page: `/admin/users` (create users, set password, enable/disable, set role)

### Admin (desktop) — WORKING
- Desktop has **Admin Users** window (admins only)
- Supports core parity: list/add/disable/role/password

### Finalize behavior (backend) — WORKING
- Finalizing radio/video with missing Trello linkage auto-creates:
  - Trello card in rep’s board “To Do”
  - Checklist created and stored back on the order
  - Sets `status=finalized` and `finalized_at`

### Override + re-finalize Trello rebuild — WORKING
- Overriding a finalized order to draft and then finalizing again:
  - **Rebuilds** the Trello checklist (old checklist removed, new checklist created)
  - Updates `trello_checklist_id` so second-finalize actually writes the updated checklist

### Art orders Trello checklist — WORKING
- Art finalize creates the correct Trello checklist naming logic for ART (no SP-based naming)

### Desktop GUI — WORKING
- Finalize uses backend finalize plumbing (no Trello prompts)
- Draft asset_type changes: Save doesn’t freeze; UI updates immediately
- Backend keeps SP.order_type synced with order.asset_type for drafts
- Desktop now includes **Open Trello Card** on order detail (when Trello linked)
- **Pinned:** desktop autosave-on-close is NOT implemented (users must click Save)

### Trello creds BOM bug — FIXED
- Root cause: `.env` had UTF-8 BOM → parsing flaked
- Fixed by stripping BOM + saving `.env` as UTF-8 no BOM

### NEW: user-id audit columns + stamping — WORKING
DB has:
- `orders.created_by_user_id`
- `orders.updated_by_user_id`
- `orders.deleted_by_user_id`
(all FK → users.id)

Routes stamp these on:
- create, update, finalize, unfinalize, revise, duplicate, additional-version, delete

DELETE still expects initials as query param (legacy):
- Works: `/orders/142?initials=SB`
- Not JSON body


## 2) Branch + latest savepoints

**Branch:** `fix-delete-override`

**Remote:** `https://github.com/BYP-Bassett/BYP_Ops_System.git`

**Key tags (chronological-ish):**
- `savepoint-auth-desktop-cookie-2026-01-14`
- `savepoint-desktop-admin-users-2026-01-15`
- `savepoint-auth-inactive-kills-session-2026-01-15`
- `savepoint-art-finalize-trello-checklist-2026-01-15`

Alembic:
- Had two heads → merged via `alembic merge` and now upgraded
- Audit columns exist in DB and confirmed


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


## 4) Canonical Rules (must not violate)

- One step at a time.
- No manual file editing.
- If a file change is needed: you upload current file → I return a downloadable replacement with **exact same filename**.
- No renaming files. Ever.
- Windows paths only.
- GUI layout tweaks pinned unless explicitly unpinned.
- No raw `"\n"` inside Python strings that generate HTML/JS. Use `\\n`.
- PowerShell: passwords with `$` must use single quotes or they get mangled.


## Next Single Target

**Admin Orders: deleted-order search + undelete (web).**

Done when:
- Admin can list deleted orders (server-side filter) and click an order
- Admin can undelete (sets `is_deleted=0`, clears deleted stamps) and it reappears in normal search

(We pinned autosave/back behavior; not doing that next.)


## Smoke Tests + Landmines

### Smoke Tests

API reachable:
```powershell
irm "http://127.0.0.1:8000/orders/search2?limit=5&offset=0"
```

/me works:
```powershell
$base = "http://127.0.0.1:8000"
$session = New-Object Microsoft.PowerShell.Commands.WebRequestSession
irm "$base/login" -WebSession $session | Out-Null
irm "$base/login" -Method Post -WebSession $session -Body @{ username='sb'; password='Doc$$2112' } | Out-Null
irm "$base/me" -WebSession $session
```

Web detail loads + Open Trello button exists (HTML contains it):
```powershell
$i = iwr "$base/order/140" -WebSession $session
($i.Content | Select-String "openTrelloBtn|Open Trello Card" -List).Line
```

Resolve Trello URL:
```powershell
# Replace with an actual trello_card_id from an order
irm "$base/trello/card-url/69694d407259f20ff34d106e" -WebSession $session
```

Override → finalize again actually rebuilds checklist:
- After override edit, **second finalize** should update `trello_checklist_id` and reflect the new checklist in Trello.

### Landmines

- Web UI blank/weird → Ctrl+F5 + console
- `/favicon.ico` 404 harmless
- Trello creds “missing” again → `.env` BOM/encoding
- SessionMiddleware must be installed → don’t touch `request.session` without it
- DELETE expects initials as query param: `/orders/{id}?initials=SB`
- Alembic “multiple heads” → needs merge migration
- If the web order page hangs again, check for accidental raw newlines inside JS strings in `main.py` (must be `\\n` not `\n` in the Python template)
