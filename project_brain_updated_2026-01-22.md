# SP Order System — Project Brain (Updated)

**Date:** 2026-01-22  
**Branch:** `fix-delete-override`  
**Remote:** BYP-Bassett/BYP_Ops_System

---

## 1) Current Truth (what’s working right now)

### Auth
- Cookie sessions working.
- Inactive users get kicked out server-side.

### Web UI
- `/search` works.
- `/order/{id}` detail works + Open Trello Card button shows when `trello_card_id` exists.
- **Save button enabled immediately on load** (not only after “dirty” changes). ✅ `savepoint-web-save-enabled-on-load-2026-01-21`
- Back still doesn’t auto-save (pinned).

### Web Admin
- `/admin/users` works (HTML).
- `/admin/users.json` works (returns data when authenticated). Verified in uvicorn logs: `GET /admin/users.json 200 OK`.

### Desktop GUI
- Desktop loads again (Login works; no silent “blank window” lockup).
- Deleted Orders exists on desktop + Restore works via `POST /orders/{id}/restore` (no GET spam/hang). ✅ `savepoint-desktop-restore-2026-01-20`
- Deleted Orders button removed from the main search page UI.

### Trello
- Finalize creates/ensures checklist correctly.
- Art finalize uses art checklist naming (date-based), not SP naming.
- Override finalized → edit → finalize again rebuilds checklist properly (old checklist removed, new checklist written, DB updated).

### Asset type flip correctness
- Art → Radio/Video: SP# gets assigned immediately on flip.
- Radio/Video → Art: SP# gets cleared immediately on flip; art naming used on finalize.

---

## 2) What’s broken / unresolved

### Rep assignment / rep change (CURRENT BLOCKER)
**Goal behavior:**
- Admin can create an order on behalf of another rep (selected rep persists).
- Rep can be changed on an existing order **only if not finalized**.
- Non-admin cannot spoof reps; forced to self.

**Current behavior:**
- `POST /orders/new` still stamps orders as the **logged-in user** (`rep_code=SB`, `rep_name=SB - Steve Bassett`) even when a different rep is provided.
- Web UI does not currently expose a clean way to change rep within an order (desktop can change after creation; web doesn’t).

**Root cause (likely):**
- Create/update routes are taking rep from the session user and ignoring inbound rep fields OR the request models don’t include rep fields so they are dropped.

---

## 3) Canonical Rules (must not violate)
- One step at a time.
- No manual file editing.
- If a file change is needed: user uploads current file → assistant returns a downloadable replacement with exact same filename.
- No renaming files. Ever.
- Windows paths only.
- GUI layout tweaks pinned unless explicitly unpinned.
- No `${}` inside Python f-strings embedding HTML/JS.
- PowerShell: passwords with `$` must use single quotes.
- If a querystring is needed in PS, build the URL string (don’t inline `?override=true` and let PS eat it).

---

## 4) How to run

### Start API
```powershell
cd C:\BYP_Ops_System\backend
.\venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

### Start Desktop GUI
```powershell
cd C:\BYP_Ops_System\backend
python OrderSearchGUI.pyw
```

### Compile checks
```powershell
python -m py_compile .\OrderSearchGUI.pyw
python -m py_compile .\app\routes\orders.py
python -m py_compile .\app\main.py
```

---

## 5) Confirmed Savepoints / Tags
- `savepoint-desktop-restore-2026-01-20` ✅
- `savepoint-web-save-enabled-on-load-2026-01-21` ✅

(Do not assume additional tags unless Steve pastes the tag push confirmation.)

---

## 6) Smoke Tests

### API reachable
```powershell
irm "http://127.0.0.1:8000/orders/search2?limit=5&offset=0"
```

### Login + /me
```powershell
$base="http://127.0.0.1:8000"
$session = New-Object Microsoft.PowerShell.Commands.WebRequestSession
irm "$base/login" -WebSession $session | Out-Null
irm "$base/login" -Method Post -WebSession $session -Body @{ username='sb'; password='Doc$$2112' } | Out-Null
irm "$base/me" -WebSession $session
```

### Admin Users JSON
```powershell
irm "$base/admin/users.json" -WebSession $session
```

### Rep override create (expected FAIL until fixed)
```powershell
$body = @{ artist="REP TEST"; asset_type="radio"; rep_code="RM"; rep_name="RM - Ron Mewis" } | ConvertTo-Json
irm "$base/orders/new" -Method Post -WebSession $session -ContentType "application/json" -Body $body
```
Expected when fixed: returns RM.  
Current: returns SB.

---

## 7) Landmines
- “Not authenticated” in PowerShell = forgot `-WebSession $session`.
- Create endpoint is **`POST /orders/new`** (not `/orders`).
- Route ordering matters (don’t put `/orders/{id}` above `/orders/search*`).
- If server won’t start: run `python -m py_compile app\routes\orders.py` first (catches syntax junk fast).
- `rg` is not installed; use `Select-String`.

---

## 8) Next Single Target
**Fix rep assignment and rep change end-to-end (API + Web UI + Desktop consistency).**

**Done when:**
- Admin `POST /orders/new` with `rep_code=RM` returns/saves RM.
- Web order detail allows rep change for non-finalized orders (admin only).
- Desktop and web enforce “no rep change on finalized orders” consistently.
