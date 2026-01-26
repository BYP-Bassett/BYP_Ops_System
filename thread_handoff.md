# Thread Handoff — SP Order System — Thread #26 → Thread #27

Date: 2026-01-26 (America/Chicago)

## 1) Where we left off (high-level)
We completed a bunch of client/company work:
- Desktop and web client typeahead works + keyboard nav + visible highlight.
- Backend now “heals” poisoned client records (same client name with NULL company gets updated when a company is later provided), including a fix for snapshot overwrite ordering.
- A savepoint tag exists: `savepoint-client-company-heal-2026-01-23`.

Then we started upgrading the **Web Admin**:
- Wanted admin top bar buttons: **Deleted Orders** + **Client/Company list**.
- Wanted Client/Company list fully editable with deletion.
- Multiple iterations on `app/main.py` caused regressions.

## 2) Current broken state (must fix first)
User reports:
- Web: **order list** not loading.
- Web: **client list** not loading.
This is after the latest admin UI changes in `app/main.py`.

## 3) What “done” looks like for the next task
Minimum restore:
- Web order list loads again (existing behavior restored).
- `/admin/clients` shows client records reliably (not blank).
- `/admin/clients.json` returns valid JSON and matches what the page expects.
- Deleted Orders “View” works (no 404) and “Restore” still works.

## 4) Known-good checkpoints
- `savepoint-client-company-heal-2026-01-23` is the last known-good tag for client/company healing and typeahead correctness.

## 5) Files likely involved for the fix
Primary:
- `C:\BYP_Ops_System\backend\app\main.py`

Possibly:
- `C:\BYP_Ops_System\backend\app\routes\orders.py` (if deleted-order view uses include_deleted and it regressed)
- `C:\BYP_Ops_System\backend\app\web\app.js` (only if order/new-order client JS got broken, but current symptom is admin/order list not loading)

## 6) Smoke tests
API reachable:
- `irm "http://127.0.0.1:8000/orders/search2?limit=5&offset=0"`

Login + /me:
- `$base="http://127.0.0.1:8000"`
- `$session = New-Object Microsoft.PowerShell.Commands.WebRequestSession`
- `irm "$base/login" -WebSession $session | Out-Null`
- `irm "$base/login" -Method Post -WebSession $session -Body @{ username='sb'; password='Doc$$2112' } | Out-Null`
- `irm "$base/me" -WebSession $session`

Admin clients JSON sanity (in browser while logged in):
- `http://127.0.0.1:8000/admin/clients.json` should return `{ "value": [...], "Count": N }` with N>0.

## 7) Landmines
- If JS is embedded inside Python f-strings, unescaped `{}` can crash Python at import time. Use safe templating.
- A JSON endpoint returning HTML (login redirect) will make UI look blank if JS expects JSON.
- Wrong model import path: there is **no** `app.db.models` module (caused a ModuleNotFoundError during a check).

## 8) Next action in Thread #27
User should upload:
- `C:\BYP_Ops_System\backend\app\main.py` (current running version) — already done at end of Thread #26, but re-upload in new thread if needed per rules.
Then fix:
- Restore order list and client list rendering, and stabilize `/admin/clients` + `/admin/clients.json`.
