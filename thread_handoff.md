# THREAD_HANDOFF.md — SP Order System (Thread #16)

Last updated: 2026-01-09 (America/Chicago)

## 1) Current Truth

**Repo / backend root (Windows):** `C:\BYP_Ops_System\backend`  
**Branch:** `fix-delete-override`  
**Python venv:** `C:\BYP_Ops_System\backend\venv\Scripts\python.exe`  
**DB (SQLite):** `C:\BYP_Ops_System\backend\byp_ops.db`  
**SQLAlchemy engine URL:** `sqlite:///./byp_ops.db` (resolves to the absolute path above)

### Start API
```powershell
cd C:\BYP_Ops_System\backend
.\venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

### Web UI
- Home/Search: `http://127.0.0.1:8000/`
- Detail (read-only HTML rendering JSON): `http://127.0.0.1:8000/order/{id}`
  - Includes a **Parent copy widget** that shows the full FM-style string:
    - `Revision of SPxxxxxx` **or**
    - `Add'l vers of SPxxxxxx`
  - Clicking the parent field **selects all + auto-copies**, and there is also a **Copy** button.
  - Important: `app/main.py` uses a Python `f"""..."""` HTML block — **do not** use JS template literals with `${}` inside it.

### API endpoints (confirmed in use)
- `GET /orders/{id}` returns JSON (includes `created_at`, `updated_at`, and `parent_display`)
- Search:
  - `GET /orders/search` → list only
  - `GET /orders/search2` → `{ total, items }` with pagination

### Desktop GUI
- Desktop app file: `C:\BYP_Ops_System\backend\OrderSearchGUI.pyw`
- The field label is now **“Revision/Add'l of”**
- That field shows a single “parent” display string (revision OR add'l version) and is copy-friendly.

### GitHub remote (exists now)
- Remote: `origin = https://github.com/BYP-Bassett/BYP_Ops_System.git`
- Work is still “dev local, deploy later” — nobody else uses it yet.

---

## 2) Branch + latest savepoints

**Branch:** `fix-delete-override`

**Key savepoint tags (older → newer):**
- `savepoint-search-and-rep-guard-2026-01-08`
- `savepoint-search2-total-pagination-2026-01-08`
- `savepoint-webui-v1-search-2026-01-08`
- `savepoint-webui-search-state-2026-01-09`
- `savepoint-order-timestamps-2026-01-09`
- **`savepoint-webui-parent-copy-2026-01-09`** (latest)

**Latest commit:** `658f478` (tagged by `savepoint-webui-parent-copy-2026-01-09`, pushed)

---

## 3) Canonical Rules (do-not-violate)

- **One step at a time**: user runs commands; we wait for success/error before proceeding.
- **No manual file edits**: user uploads/pastes → we return a **downloadable replacement**.
- **No renaming files, ever.** Replacements must keep the same exact filename.
- **Windows paths only.**
- **GUI layout tweaks are pinned** unless explicitly unpinned.
- If Python f-strings contain HTML/JS: avoid `${}` template literals; use string concatenation instead.

---

## 4) Next Single Target (ONE task)

### Target
**Web UI must eventually support full workflow** (remote users will use browser).  
Desktop is “office convenience,” not the primary app.

**Best next step:** add **inline edit + Save** on `/order/{id}` using existing `PATCH /orders/{id}`.

### Done when
On `http://127.0.0.1:8000/order/{id}`:
- User can edit at least:
  - `notes`
  - `client_name`
  - `client_company_name`
- Click **Save** → calls API PATCH → refreshes the displayed values from server response.
- No changes to immutable fields (ex: `asset_type`) unless API explicitly supports it.

---

## Smoke Tests + Landmines

### Smoke tests
**API reachable**
```powershell
irm "http://127.0.0.1:8000/orders/search2?limit=5&offset=0"
```

**Detail page loads**
- `http://127.0.0.1:8000/order/85`

**Timestamps present**
```powershell
irm "http://127.0.0.1:8000/orders/72" | select created_at, updated_at
```

### Landmines
- If web UI looks empty: check browser console for JS errors; hard refresh `Ctrl+F5`
- `/favicon.ico 404` is harmless
- If server throws `SyntaxError` / `NameError` around f-strings: you accidentally put JS `${}` or bad escaping inside Python again; fix immediately.
- If an order “exists” in POST response but GET 404s: wrong uvicorn process / wrong working dir / wrong DB.
