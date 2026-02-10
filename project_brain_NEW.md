# SP Order System — Project Brain (Handoff for New AI)

**Purpose:** Give a replacement AI everything needed to continue the SP Order System web app *without breaking the Search page or toolbar*.

---

## 1) Baseline / Current Truth

### Known-good baseline tag (use this as starting point)
- **Tag:** `savepoint-search-columns-fit-2026-02-06`
- **Branch:** `fix-from-savepoint`

### Start server (Windows)
```powershell
cd C:\BYP_Ops_System\backend
.\venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

### Files used recently (avoid touching unless explicitly required)
- `app/main.py`
- `app/web/app.js`
- `app/web/index.html`

---

## 2) What Works (confirmed at baseline)

- Cookie sessions work (browser auth)
- Inactive users get kicked server-side
- Search page loads
- Search toolbar layout is correct and must NOT be rearranged:
  - Left: **My Drafts**, **All**, **Search**, **Clear**
  - Middle: **New order**, **Clients**
  - Right: **Admin**, **Logout**
- “Logged in as…” display behaves
- Clients page works (admin + non-admin):
  - active-only default
  - show inactive works
  - active checkbox persists
  - edits persist
  - no delete UI
- Search enhancements:
  - Artist + Notes single-line ellipsis + tooltip
  - Clear refresh works
- Order page:
  - Created/Updated timestamps show **MM/DD/YYYY**
  - Client Email/Phone removed
  - Print button works
- Print page layout finalized:
  - includes two-column notes w/ divider
  - fields editable
- Search results columns fit window (responsive widths)

---

## 3) What’s Missing / Next Work

### Goal A — DB-driven Reps + Auto-fill (New Order modal only)
- Rep dropdown must come from **Users** table (no hardcoded rep list)
- Rep must auto-select to **logged-in user** (via `/me`)
- Must not break Search page
- Must not touch toolbar layout
- Must be triggered **only when opening the New Order modal** (NOT Search boot)

### Goal B — Logout button not working
- Backend logout exists and is correct
- Fix should be frontend wiring/JS interference only
- Must not rebuild/move toolbar DOM

---

## 4) What We Tried / What Broke (avoid repeating)

DB-driven rep attempts failed due to frontend fragility:
- JS syntax errors during patching (try/catch mismatches) broke Search page
- Toolbar buttons moved/disappeared when JS injected/reordered DOM
- New Order button vanished due to toolbar rebuild logic
- Logout broke when Logout button detached from its `<form>`

Important testing note:
- PowerShell `irm /me` can show unauthenticated because it doesn’t send browser cookies; that’s not proof of a browser-session failure.

---

## 5) Canonical Rules (non-negotiable)

- **One change at a time**
- **Make ONLY the explicitly requested change** (no cleanup/refactors/UI tweaks)
- **If anything blocks the requested change: stop and report**
  - the blocker
  - fix options
  - which files would change
- **Do NOT reorder toolbar elements in JS**
- **Do NOT run modal-related logic at Search boot**
- **Windows only**
- Desktop work forbidden until web is finished
- If something isn’t crystal clear, verify first instead of guessing

---

## 6) Exact Code Locations (Baseline)

### 6.1 Rep dropdown hardcode (app/web/app.js)
**Hardcoded rep list (must be replaced):**
- Lines **655–661**
```js
const REP_FULL = [
  "SB - Steve Bassett",
  "RM - Ron Mewis",
  "AML - Allison Lineberry",
  "JS - Jon Shults",
  "CD - Celine DeLeon",
];
```

**Rep parsing helper:**
- Lines **663–667**
```js
function repCodeFromFull(repFull) {
  const s = String(repFull || "").trim();
  if (!s) return "";
  return (s.split(/\s+/)[0] || "").trim();
}
```

**Dropdown population today (replace with DB-driven fetch):**
- Lines **669–680**
```js
function populateRepSelect(sel) {
  if (!sel) return;
  sel.innerHTML = "";
  for (const r of REP_FULL) {
    const opt = document.createElement("option");
    opt.value = r;
    opt.textContent = r;
    sel.appendChild(opt);
  }
  sel.value = REP_FULL[0] || "";
}
```

**New Order modal (best injection point: modal-open only):**
- `showNewOrderModal()` starts at **line 786**
- Rep `<select>` in modal HTML: **799–802**
```html
<label for="no_rep">Rep *</label>
<select id="no_rep"></select>
```
- `repEl` retrieved: **line 841**
```js
const repEl = $m("no_rep");
```
- Current call (replace): **1056–1058**
```js
populateRepSelect(repEl);
populateAssetSelect(assetEl);
```

### 6.2 Auth middleware + /me + /logout (app/main.py)

**Session/auth middleware:**
- Starts at **line 220**
- API 401 behavior block: **247–252**
```py
# API endpoints (desktop + web JS fetches) should get a hard 401.
if path.startswith("/orders") or path == "/me":
    return JSONResponse(status_code=401, content={"detail": "Not authenticated"})

# Browser pages redirect to login.
return RedirectResponse(url="/login?error=Session+expired", status_code=303)
```
When adding `/api/reps`, it must follow the API-401 behavior (return JSON 401, not HTML redirect).

**/me endpoint (used for auto-select rep):**
- **270–287**
```py
@app.get("/me")
def me(request: Request):
    u = request.session.get("username")
    if not u:
        return {"authenticated": False}
    return {
        "authenticated": True,
        "user_id": request.session.get("user_id"),
        "username": request.session.get("username"),
        "rep_code": request.session.get("rep_code"),
        "rep_name": request.session.get("rep_name"),
        "role": request.session.get("role"),
        "is_active": request.session.get("is_active"),
    }
```

**/logout endpoint (backend already correct):**
- **398–401**
```py
@app.post("/logout", include_in_schema=False)
def logout(request: Request):
    _clear_session(request)
    return RedirectResponse(url="/login", status_code=303)
```

### 6.3 Logout HTML (app/web/index.html)
- **69–71**
```html
<form method="post" action="/logout" style="margin:0;">
  <button type="submit">Logout</button>
</form>
```
This is correct; if logout “does nothing,” it’s likely JS interference or DOM manipulation, not backend.

---

## 7) Implementation Spec (next AI should follow)

### 7.1 Backend — add endpoint
Add: **GET `/api/reps`** (auth required)
- Returns reps from Users table (at minimum: `id`, `rep_code`, `rep_name`, `username`, `role`, `is_active`)
- Ensure unauthenticated request returns JSON 401 (align with middleware)

Suggested payload:
```json
[
  {"id": 1, "rep_code": "SB", "rep_name": "Steve Bassett", "username": "steve", "role": "admin", "is_active": true}
]
```

### 7.2 Frontend — modal-only fetch + auto-select
- Trigger only when opening **New Order** modal
- Fetch `/me` and `/api/reps`
- Populate rep `<select>` with DB results
- Auto-select logged-in user:
  - Match by `user_id` first
  - Fallback to match by `rep_code`
- Must fail safely (show a message in modal, do not crash Search)

Suggested safe pattern:
- Make `populateRepSelect` async and invoked only inside `showNewOrderModal()` after modal DOM exists.

### 7.3 Logout fix
- Do not rebuild toolbar DOM
- Do not detach Logout button from its `<form>`
- If there is JS preventing default submit or overlaying the click, remove that interference without touching layout.

---

## 8) Success Criteria (no weasel words)

- Search page loads
- Toolbar layout unchanged
- New Order modal opens
- Rep dropdown loads all reps from DB
- Rep auto-selects to logged-in user
- Logout submits POST `/logout` and redirects to `/login`
- Refresh after logout shows unauthenticated session

---

## 9) Notes

- Users table now contains **3 users**: **1 admin + 2 test users** (for dropdown testing)
- Do not invent or implement “New Tour” UI yet — it does not exist at baseline.
