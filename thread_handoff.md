# Thread Handoff — SP Order System (Thread #18 → next)

## 1) Current Truth

### Backend root
`C:\BYP_Ops_System\backend`

### venv
`.\venv\Scripts\python.exe`

### DB
- `backend\byp_ops.db` (SQLite)
- Engine URL: `sqlite:///C:/BYP_Ops_System/backend/byp_ops.db`

### Start API
```powershell
cd C:\BYP_Ops_System\backend
.\venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

### Web UI
- `http://127.0.0.1:8000/`
- `/order/{id}` read-only page (fetches `/orders/{id}` JSON)
- Parent copy widget (Revision/Add’l click-to-copy)

### Trello finalize behavior (backend) — WORKING
- Finalizing **radio/video** with missing Trello linkage auto-creates:
  - Trello card in rep’s board “To Do” list (title = full artist)
  - Checklist named SP# on that card
  - Stores `trello_card_id` + `trello_checklist_id` on the order
  - Sets `status=finalized` and `finalized_at`

### Durable Trello config — WORKING (after fixing .env)
Config file:
`C:\BYP_Ops_System\backend\.env`

Required keys:
- `TRELLO_KEY=...`
- `TRELLO_TOKEN=...`
- `TRELLO_BOARD_ID_SB=8ePAKW8L`
- `TRELLO_DEFAULT_BOARD_ID=8ePAKW8L`
- `TRELLO_TODO_LIST_NAME=To Do`

### Desktop GUI
Run:
```powershell
cd C:\BYP_Ops_System\backend
python .\OrderSearchGUI.pyw
```

Status:
- Desktop search/open works (after rollback).
- Desktop finalize is still legacy (asks for Trello Card ID + Checklist ID).

---

## 2) Branch + latest savepoints

Branch: `fix-delete-override`

Key tags:
- `savepoint-trello-finalize-autocreate-2026-01-12` (commit `426cd5da1af0e9fd8ab12fd8864c9f9732421ad9`)
- `savepoint-trello-config-and-revise-2026-01-12` ✅ (commit `17aef48`) **CURRENT WORKING BACKEND**

Remote:
- origin = `https://github.com/BYP-Bassett/BYP_Ops_System.git`

---

## 3) Canonical Rules

- One step at a time.
- No manual file editing. If a change is needed:
  - You upload the file
  - I return a downloadable replacement with the **same exact filename**
- No renaming files. Ever.
- Windows paths only.
- GUI layout tweaks pinned unless explicitly unpinned.
- No `${}` inside Python f-strings that embed HTML/JS.

---

## 4) Next Single Target

### Goal
Make desktop finalize use the backend Trello plumbing so it never prompts for Trello IDs on radio/video.

### Do next
Update `OrderSearchGUI.pyw` finalize flow so:
- For **radio/video**: it calls `POST /orders/{id}/finalize` and relies on backend to handle Trello.
- Avoid new UX; don’t break existing buttons/layout.

### Done when
Desktop GUI:
- Open order `41` (video, SB) and click Finalize
- No Trello ID prompt
- Order finalizes
- After Refresh, Trello IDs + finalized_at show up
- No UI regressions (no blank search grid, no extra stray Tk window, all previous buttons still present)

---

## 5) Smoke Tests + Landmines

### API reachable
```powershell
irm "http://127.0.0.1:8000/orders/search2?limit=5&offset=0"
```

### Detail page works
Open:
- `http://127.0.0.1:8000/order/85`

### Timestamps present
```powershell
irm "http://127.0.0.1:8000/orders/72" | select created_at, updated_at
```

### Trello finalize smoke test (backend)
```powershell
irm -Method Post "http://127.0.0.1:8000/orders/103/finalize"
irm "http://127.0.0.1:8000/orders/103" | select id,status,trello_card_id,trello_checklist_id,finalized_at
```

### Desktop target check (order 41)
```powershell
irm "http://127.0.0.1:8000/orders/41" | select id,asset_type,rep_code,status
```

### Landmines
- Web UI empty table → browser console; hard refresh `Ctrl+F5`
- `/favicon.ico` 404 harmless
- HTML/JS SyntaxError → look for `${}` inside Python f-strings
- `.env` must be plain `KEY=VALUE` lines only
