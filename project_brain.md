# Project Brain — SP Order System (as of 2026-01-14)

## What this system is
A Windows-first BYP Ops Order System with:
- FastAPI backend + SQLite dev DB
- Desktop Tkinter GUI (office use)
- Simple web UI (remote use)

Core objects:
- Orders (draft/finalized, asset types, notes, client info)
- SP numbers / SP order_type sync
- Trello integration on finalize (auto-create card + checklist when missing linkages)
- Audit trail for key actions (in progress / partial)

## Working right now (truth, not vibes)
- Backend runs from `C:\BYP_Ops_System\backend`
- API starts with uvicorn `app.main:app --reload`
- Web:
  - `/` search/list
  - `/order/{id}` detail/edit (draft-only asset_type dropdown)
- Desktop:
  - Uses backend finalize plumbing (no Trello prompts, no confirm popup)
  - Draft asset_type changes save and no longer freeze
  - Backend keeps SP.order_type in sync with order.asset_type for drafts
- Trello `.env` BOM issue fixed (loader strips BOM; `.env` re-saved no BOM)

## Current branch + savepoints
- Branch: `fix-delete-override`
- Savepoints:
  - `savepoint-trello-finalize-autocreate-2026-01-12`
  - `savepoint-trello-config-and-revise-2026-01-12`
  - `savepoint-desktop-finalize-backend-2026-01-13`
  - `savepoint-web-asset-type-edit-2026-01-13`
  - `savepoint-pre-auth-admin-2026-01-14` (before starting auth/admin)

## Known pain points / lessons learned
- Editing Python f-string embedded HTML/JS is a minefield:
  - Any `{` / `}` (JS braces) can break Python parsing unless escaped.
  - Any `\n` vs `\
` inside JS string literals can create “unescaped line break” JS syntax errors.
  - Prefer template strings without f-strings (or serve static JS files) to avoid server crashes.
- Web Delete was attempted; not worth polishing right now.

## Next logical “finish the system” work
### Users + Auth + Admin panel
Steve wants:
- Admin page to add users and assign rights
- Web “My Drafts” button (like desktop)

Planned minimal approach:
- Add `users` table (rep_code, rep_name, password_hash, is_admin, is_active)
- Session cookie login for web
- Require auth for mutating actions (eventually)
- Admin UI: create/disable users, set admin flag
- Web My Drafts: filter drafts by logged-in rep_code

### One-file-at-a-time kickoff
First file needed to correctly wire migrations/models:
- `backend/app/database/session.py`
