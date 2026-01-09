# project_brain.md — SP Order System

Last updated: 2026-01-09 (America/Chicago)

## What this project is
A BYP Ops Order system built on **FastAPI + SQLAlchemy + Alembic + SQLite** with:
- API-first backend (eventually cloud-hosted)
- Two UIs:
  - **Web UI** for remote users (must become fully functional)
  - **Desktop Tkinter GUI** for in-office convenience

Goal: replace/augment FileMaker workflows while preserving key behavior (SP numbers, revision/add'l version relationships, etc.).

---

## Repo + Environment

**Backend root:** `C:\BYP_Ops_System\backend`  
**Branch:** `fix-delete-override`  
**venv python:** `.\venv\Scripts\python.exe`  
**DB:** `C:\BYP_Ops_System\backend\byp_ops.db`  
**Engine URL:** `sqlite:///./byp_ops.db`

### Start server
```powershell
cd C:\BYP_Ops_System\backend
.\venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

---

## Web UI (current state)

### Home/Search
- `http://127.0.0.1:8000/`
- Uses `/orders/search2` for paginated results.
- Search state persists (auto-load + returns to results instead of blank after navigating back).

### Detail page
- `http://127.0.0.1:8000/order/{id}`
- Renders JSON from `GET /orders/{id}`.
- Includes **Parent copy widget** showing the full string:
  - `Revision of SPxxxxxx` OR `Add'l vers of SPxxxxxx`
- Click-to-select-all + auto-copy, plus Copy button.
- Implementation is embedded HTML/JS inside `app/main.py` using a Python `f"""..."""`.

**Landmine:** no JS template literals with `${}` inside that `f"""` block. Use string concatenation.

---

## Desktop GUI (current state)

**File:** `C:\BYP_Ops_System\backend\OrderSearchGUI.pyw`

- The field label is **Revision/Add'l of**
- It displays one FM-style parent display string (revision OR add'l).
- It is copy-friendly.

---

## API + Data model notes

### Orders
- `GET /orders/{id}` returns JSON including:
  - `created_at` and `updated_at`
  - `parent_display`
- Search endpoints:
  - `/orders/search` list-only
  - `/orders/search2` returns `{ total, items }`

### Revision/Add'l Version behavior (FM parity)
- In FileMaker, the “parent display” is a **non-editable** field; users copy/paste it into notes if needed.
- We match that:
  - store/compute a single parent display string
  - do **not** spam Notes with repeated lineage strings

---

## Git / Savepoints / Remote

Remote:
- `origin = https://github.com/BYP-Bassett/BYP_Ops_System.git`

Latest known good tag:
- **savepoint-webui-parent-copy-2026-01-09** (commit `658f478`, pushed)

Other recent tags:
- savepoint-webui-search-state-2026-01-09
- savepoint-order-timestamps-2026-01-09

---

## Canonical Rules (non-negotiable)

- One step at a time; wait for confirmation/error.
- No manual file edits — replacements only, same filenames.
- No renaming files.
- Windows paths only.
- GUI layout changes are pinned unless explicitly unpinned.

---

## Next Single Target

**Web UI must become the full app** for remote work.

**Next step:** implement **inline edit + Save** on `/order/{id}`:
- Editable first: `notes`, `client_name`, `client_company_name`
- Save uses `PATCH /orders/{id}`
- After save: show updated values (and updated timestamp)

---

## Smoke tests + common failures

**API reachable**
```powershell
irm "http://127.0.0.1:8000/orders/search2?limit=5&offset=0"
```

**Detail loads**
- `http://127.0.0.1:8000/order/85`

**Timestamps**
```powershell
irm "http://127.0.0.1:8000/orders/72" | select created_at, updated_at
```

If web UI empty: console errors; hard refresh Ctrl+F5  
/favicon.ico 404: harmless  
f-string crash: `${}` or escaping inside Python HTML — fix immediately.
