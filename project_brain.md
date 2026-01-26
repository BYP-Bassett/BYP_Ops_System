# BYP Ops — SP Order System — Project Brain (Thread #26 closeout)

Last updated: 2026-01-26 (America/Chicago)

## 0) Canonical Rules (do not violate)
- One step at a time.
- No manual file editing.
- If a file change is needed: user uploads current file → assistant returns a downloadable replacement with the **exact same filename**.
- **No renaming files. Ever.**
- Windows paths only.
- GUI layout tweaks pinned unless explicitly unpinned.
- No `${}` inside Python f-strings embedding HTML/JS (use templates/format safely).
- PowerShell: passwords with `$` must use single quotes.
- If a querystring is needed in PS, build the URL string (don’t inline `?override=true`).
- Route ordering matters (`/orders/search*` must be above `/orders/{id}`).
- `rg` isn’t installed. Use `Select-String`.

## 1) Repo + branch
- Repo: https://github.com/BYP-Bassett/BYP_Ops_System.git
- Branch: `fix-delete-override`

## 2) Confirmed savepoints / tags
- `savepoint-desktop-restore-2026-01-20`
- `savepoint-web-save-enabled-on-load-2026-01-21`
- `savepoint-rep-picker-rules-2026-01-22`
- `savepoint-client-company-heal-2026-01-23` ✅ (poisoned client company “heal” fix)

## 3) Current Truth (what was working before the latest admin UI changes)
Auth
- ✅ Cookie sessions working.
- ✅ Inactive users get kicked out server-side.

Web UI
- ✅ `/orders/search2` works.
- ✅ `/orders/{id}` detail works.
- ✅ Save button enabled immediately on load (savepoint-web-save-enabled-on-load-2026-01-21).
- 🧷 Back still doesn’t auto-save (pinned).

Web Admin (before recent breakage)
- ✅ `/admin/users` works (HTML).
- ✅ `/admin/users.json` works (authenticated).

Desktop GUI
- ✅ Desktop loads again (LoginDialog crash fixed earlier).
- ✅ Deleted Orders restore works (POST `/orders/{id}/restore`, no GET spam/hang). (savepoint-desktop-restore-2026-01-20)

Trello
- ✅ Finalize creates/ensures checklist correctly.
- ✅ Art finalize uses art checklist naming (date-based), not SP naming.
- ✅ Override finalized → edit → finalize again rebuilds checklist properly.

Asset type flip correctness
- ✅ Art → Radio/Video assigns SP immediately.
- ✅ Radio/Video → Art clears SP immediately.

## 4) Client/Company typeahead work (web + desktop)
- Web: client typeahead works on Order page + New Order modal.
- Web: keyboard navigation added (↑/↓/Enter/Esc), highlight fixed and visible.
- Desktop: suggestions & keyboard navigation working.
- Backend: client “poisoned company” healing fixed (existing client row with blank company gets updated when new company provided). Included special case where order snapshotting could overwrite user-entered company. Fixed and saved in savepoint-client-company-heal-2026-01-23.

## 5) Admin UI changes (in-progress) — CURRENTLY BROKEN
Goal requested:
- Admin top bar buttons: **Deleted Orders** and **Client/Company list**
- Client/Company list: fully editable + delete capability, ideally with order-search-style list behavior.

What happened:
- Multiple iterations modifying `app/main.py` caused drift/regressions.
- Latest state reported by user:
  - ❌ Web: **order list** not loading
  - ❌ Web: **client list** not loading
  - These failures happened after the latest admin UI changes to `/admin/clients` and related JSON/data loading.
- Verified at one point:
  - `RUNNING: C:\BYP_Ops_System\backend\app\main.py`
  - `HAS /admin/clients: True`
- A prior check attempt failed due to incorrect import path `app.db.models` (actual models module differs).

## 6) How to start server + GUI
API
- `cd C:\BYP_Ops_System\backend`
- `.[0m\venv\Scripts\python.exe -m uvicorn app.main:app --reload`

Desktop GUI
- `cd C:\BYP_Ops_System\backend`
- `python OrderSearchGUI.pyw`

Optional compile checks (Python only)
- `python -m py_compile .\app\routes\orders.py`
- `python -m py_compile .\app\main.py`
- `python -m py_compile .\OrderSearchGUI.pyw`

## 7) Next Single Target (Thread #27 starting point)
Restore web functionality after admin UI changes:
- Fix web **order list** loading regression.
- Fix web **client list** loading regression.
Likely scope:
- `C:\BYP_Ops_System\backend\app\main.py` (admin HTML + JS injection + JSON endpoints)
Possibly:
- `C:\BYP_Ops_System\backend\app\routes\orders.py` (if include_deleted or data endpoints need alignment)
