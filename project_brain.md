# BYP Ops System — Project Brain (SP Order System)

Last updated: 2026-01-13 (America/Chicago)

## What this is
Single source of truth for the SP Order System build: backend (FastAPI + SQLite), web UI, and desktop GUI (Tkinter).

## Repo + local layout
- Repo: BYP-Bassett/BYP_Ops_System (origin)
- Backend root (working dir): `C:\BYP_Ops_System\backend`
- venv python: `.\venv\Scripts\python.exe`
- SQLite DB: `backend\byp_ops.db`
- Engine URL resolves to: `sqlite:///C:/BYP_Ops_System/backend/byp_ops.db`

## How to run
### Start API
```powershell
cd C:\BYP_Ops_System\backend
.\venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

### Web UI
- Home/Search UI: `http://127.0.0.1:8000/`
- Order detail page (read-only HTML): `http://127.0.0.1:8000/order/{id}`
  - Fetches `/orders/{id}` JSON
  - Includes “Parent copy” widget (Revision/Add’l text click-to-select-all + auto-copy)

### Desktop GUI
```powershell
cd C:\BYP_Ops_System\backend
python .\OrderSearchGUI.pyw
```

## Trello integration (backend)
### Current behavior (working on web path)
- Finalizing **radio/video** orders will auto-handle Trello if linkage is missing:
  - Create Trello card in rep’s board “To Do” list (card title = full artist)
  - Create checklist on that card named by SP# (e.g., `SP000105`)
  - Persist `trello_card_id` + `trello_checklist_id` back to the order
  - Set `status=finalized` and `finalized_at`

- Revisions / Add’l versions:
  - Revisions should reuse the existing Trello card (`trello_card_id`)
  - Finalizing revised/add’l should create a new checklist for the new SP# on the existing card

## Durable Trello config (loaded from .env)
- `.env` path: `C:\BYP_Ops_System\backend\.env`
- Required keys:
  - `TRELLO_KEY`
  - `TRELLO_TOKEN`
  - `TRELLO_BOARD_ID_SB=8ePAKW8L`  (board shortLink)
  - `TRELLO_DEFAULT_BOARD_ID=8ePAKW8L` (optional but useful)
  - `TRELLO_TODO_LIST_NAME=To Do`

⚠️ Landmine: `.env` must be clean `KEY=VALUE` lines only. No commands, no junk.

## Desktop vs Web parity rule (standing requirement)
Any workflow change must be implemented for:
1) Web (backend endpoints + web UI)
2) Desktop GUI (OrderSearchGUI.pyw)

## Current known issue
- Web finalize/revise/add’l is working again after fixing `.env`.
- Desktop GUI still has legacy finalize UX: prompts for Trello Card ID + Checklist ID.

## Canonical Rules (must not violate)
- One step at a time (you run it, report success/error, then next).
- No manual file editing.
  - If a file change is needed: you upload the current file; I return a downloadable replacement with the **same exact filename**.
- No renaming files. Ever.
- Windows paths only.
- GUI layout tweaks pinned unless explicitly unpinned.
- When Python f-strings contain HTML/JS: **no JS template literals `${}`** inside Python f-strings.
