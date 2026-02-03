# Thread Handoff — SP Order System Thread #31 Reset

**Date:** 2026-02-03 (America/Chicago)

## Why reset
Thread #31 turned into whack-a-mole because Clients page patches repeatedly:
- overwrote unrelated routes in `app/main.py`
- broke Search page ("Not Found")
- changed styling/layout unintentionally
- caused “Show inactive” to throw 422 parsing errors

We are freezing scope: preserve baseline, patch Clients surgically.

## Baseline to preserve
- Tag: `savepoint-art-number-added-2026-02-02`
- Search page + toolbar layout must remain unchanged.

## Current state
- User restored `app/main.py` to baseline and uploaded it for surgical patching.

## Single focus next
Fix `/admin/clients` to meet requirements:
- users can view clients (login required)
- show inactive works (no 422 on include_inactive)
- per-row active checkbox toggles and persists
- edit client/company + save
- remove delete UI
- do NOT break Search page/layout

## Files involved
- `app/main.py` (primary)
- `app/web/app.js` (only if absolutely necessary; avoid touching)

## Safe workflow
1) Apply one replacement file.
2) Restart server.
3) Test Clients page + Search page.
4) If fail: revert immediately.

## Quick verification commands
From `C:\BYP_Ops_System\backend`:
- `git status`
- `git rev-parse --short HEAD`
- `git describe --tags --exact-match`
- `.\venv\Scripts\python.exe -c "import app.main; print(app.main.__file__)"`
