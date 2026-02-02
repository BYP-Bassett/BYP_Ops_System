# Project Brain — SP Order System (BYP Ops)

**Updated:** 2026-01-30 (America/Chicago)

## 0) What this is
A Windows-first BYP Ops system to create/manage SP Orders (Radio/Video/Art), with:
- FastAPI backend
- Web UI (static HTML/JS)
- Desktop GUI (Tkinter .pyw) — parity matters long-term
- Trello integration (create card + checklist on finalize)
- Cookie-session auth + role-based admin pages

## 1) Repo / paths (canonical)
- Project root: `C:\BYP_Ops_System\backend`
- Backend package: `app\`
- Web UI: `app\web\` (served content)
- Key files (common touchpoints):
  - `app\main.py` (FastAPI app, HTML routes, auth guard)
  - `app\routes\orders.py` (API endpoints for orders)
  - `app\services\order_service.py` (business logic: finalize, Trello)
  - `app\services\trello_service.py` (Trello API wrapper)
  - `app\schemas\order.py` (Pydantic response models)
  - `app\models\orders.py` (SQLAlchemy model)
  - `app\database\migrate.py` (SQLite migration helper)
  - `app\web\app.js` (web UI JS)

## 2) How to run (canonical)
```powershell
cd C:\BYP_Ops_System\backend
.\venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

## 3) Canonical rules (still law)
- **One step at a time.**
- **No manual file editing.**
- Upload → assistant returns **downloadable replacement with the exact same filename**.
- **No renaming files. Ever.**
- **Windows only** (PowerShell).
- No `${ }` in Python f-strings when embedding HTML/JS.
- PowerShell: passwords/tokens with `$` must use **single quotes**.
- Route ordering matters (e.g., `/orders/search` must come before `/orders/<built-in function id>`).
- `rg` not installed.
- PowerShell recursive search:
  - `gci .\app -Recurse -File | Select-String -Pattern "whatever"`

## 4) Current working state (as of savepoint)
### Auth
- Cookie sessions work
- Inactive users are rejected server-side

### Web UI
- Search loads and works
- Delete works
- Search toolbar order: **My drafts, All, Search, Clear, New order**
- Admin page nav is consistent across admin sections

### Orders / Save / Finalize
- Save works again (previous “nothing saves” chaos was caused by a JS crash)
- Notes persist
- Unfinalize → edit → Save persists
- Asset type changes persist
- Finalize creates Trello card + checklist correctly
- Trello card description is **client name only**
- Open Trello Card works

### Asset type flip rules (confirmed)
- Art → Radio/Video assigns SP immediately
- Radio/Video → Art clears SP immediately

### ART checklist naming
- Original checklist should be **MMDDYY**
- Revisions should be **MMDDYY-R1, R2, ...**
- The “R1 on first checklist” bug is fixed at the current savepoint

## 5) The big decision: stop overloading `sp_number` for ART
### Problem
`sp_number` is used for Radio/Video SP numbers and is correctly cleared when asset type becomes Art.
Trying to store ART codes (MMDDYY / MMDDYY-R#) in `sp_number` causes “it stored, then it vanished” behavior.

### Decision
Add a **separate field** for ART display codes:
- New DB field: `art_number` (or `art_code`)
- UI shows it directly under SP number (order page)
- Search page can show it in the SP column for Art OR add a dedicated ART column (TBD)

## 6) Open work (next steps)
1) **Add `art_number` field end-to-end**
   - SQLAlchemy model + Pydantic schema + migration + finalize logic writes it
2) **UI updates**
   - Order page: show ART# under SP#
   - Search page: show ART# for art rows (exact placement TBD)
3) **Client lifecycle cleanup**
   - Reintroduce “Show deactivated” toggle
   - Deactivation should set `Client.is_active = False` (not hard delete)
4) **ART checklist tracking**
   - Store checklist IDs for art like SP tracking already does for radio/video (Trello IDs stay in `trello_*` fields)

## 7) Latest savepoint
- `savepoint-art-checklist-r1-fixed-2026-01-30`
