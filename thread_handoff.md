# thread_handoff.md — SP Order System — Next Thread Kickoff

## Starting Point
- Latest stable tag: **savepoint-order-created-updated-mdy-2026-02-06**
- Prior stable tag: **savepoint-clear-refresh-fixed-2026-02-05**

## What’s Verified Working
- Sessions/cookies OK; inactive users kicked server-side
- Search page stable; toolbar layout correct and must not be moved in JS
- Clients page stable for admin + non-admin (active-only default, show inactive OK, active checkbox persists, edits persist)
- Search improvements working:
  - Artist: one-line ellipsis + tooltip
  - Notes: first-line ellipsis + tooltip
  - Clear: forces re-run search and reloads All orders
- Order page shows timestamps:
  - Created + Updated visible
  - Format: MM/DD/YYYY
  - Removed “Editable here…” hint line
  - Removed Client Email/Phone display rows

## Key Technical Notes
- Order page fetches order data from **`/orders/{id}`** (API).
- `/orders/{id}` previously used `response_model=OrderResponse` which dropped timestamps; now endpoint returns explicit payload including `created_at` and `updated_at`.
- Avoid JS toolbar rearrangement — breaks buttons and causes silent failures.

## Canonical Rules
- One change at a time
- No manual file editing
- User uploads file(s) → assistant returns downloadable replacement with same filename
- No renaming files
- Windows only
- Desktop work forbidden until web is finished

## Next Task (Do First)
### Re-add Print Feature (Minimal + Stable)
1) Add route: `GET /order/{order_id}/print`
2) Add a Print link/button per order row (opens new tab)
3) Print page: include **Created date only**, keep layout one-page and stable

## Expected Files to Work On Next
- `app/web/app.js` (add Print link/button in order list render; no toolbar changes)
- `app/main.py` (add print route/template)
