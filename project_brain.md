# BYP Ops System — Project Brain (SP Order System)

**Baseline date:** 2026-01-29  
**OS:** Windows (PowerShell)  
**Repo root:** `C:\BYP_Ops_System\backend`

## Current working state (truth)
### Auth
- Cookie sessions working
- Inactive users kicked server-side

### Web UI
- Search page loads
- Delete on search works
- Admin button moved to far right
- Search toolbar button order: **My drafts, All, Search, Clear, New order**

### Web Admin
- Admin pages load (Users / Deleted Orders / Clients)
- Admin pages have consistent top nav buttons:
  - Back to Search | Users | Deleted Orders | Clients/Company

### Orders / Save
- Save works on order page (fixed the `ensureClientExists is not defined` crash)
- Unfinalize → edit → Save works
- Asset type change persists again (fixed as a side-effect of Save actually running)

### Trello
- Finalize creates Trello card + checklist correctly
- Open Trello Card button works (fixed 500)

## Branch + Savepoints
- **Branch:** `fix-delete-override`
- **Key tags (2026-01-29):**
  - `savepoint-fix-save-ensureclient-2026-01-29`
  - `savepoint-fix-open-trello-card-2026-01-29`
  - `savepoint-ui-search-toolbar-2026-01-29`

## How to run server
```powershell
cd C:\BYP_Ops_System\backend
.\venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

## Canonical rules (still law)
- One step at a time.
- No manual file editing.
- Upload → I return downloadable replacement with the **exact same filename**.
- No renaming files. Ever.
- Windows-only commands/paths.
- Avoid `${}` in Python f-strings when embedding HTML/JS.
- PowerShell: passwords with `$` must use single quotes.
- Route ordering matters.
- `rg` not installed. Use:
  ```powershell
  gci .\app -Recurse -File | Select-String -Pattern "whatever"
  ```

## Data model notes (Clients/Company)
- Orders already store snapshot text fields:
  - `Order.client_name`
  - `Order.client_company_name`
- Clients already have:
  - `Client.is_active` (supports deactivation/archiving)
- Current UX direction: move client/company management from Admin page → Search page so normal users can maintain it; finalized orders remain stable because they display snapshot fields.

## Next feature direction (queued)
Move Client/Company management UI to the Search page:
- Add/edit/deactivate from Search page
- Autofill/suggest: active clients by default
- Finalized order history remains stable via snapshot fields
