# Thread Handoff — SP Order System Thread #29 → Thread #30

**Date:** 2026-01-30 (America/Chicago)

## 1) Where we are (truth)
### Working
- Auth cookie sessions good; inactive users rejected
- Web search page loads; delete works
- Admin pages load (Users / Deleted Orders / Clients)
- Save works (previously blocked by JS crash)
- Finalize creates Trello card + checklist
- Open Trello Card works
- ART checklist naming bug “original had R1” is fixed at savepoint

### Not solved / needs redesign
- ART “display code” (MMDDYY / MMDDYY-R#) should **NOT** live in `sp_number`
- Using `sp_number` for ART got wiped by correct “Art clears SP” rule
- Conclusion: add a dedicated ART field

## 2) Why the last thread got messy
- Save failures were caused by front-end JS crash (`ensureClientExists is not defined`)
- Finalize errors were caused by datetime import misuse inside `order_service.py`
- Trying to overload `sp_number` for ART caused “stored then gone” behavior

## 3) Branch + savepoint
- Branch: `fix-delete-override`
- Latest tag: `savepoint-art-checklist-r1-fixed-2026-01-30`

## 4) Next goal (Thread #30)
### Implement `art_number` end-to-end
**Definition:** A visible ART code stored on the order, independent of SP numbers.
- Original ART: `MMDDYY`
- ART revision: `MMDDYY-R#`

### Files likely to touch
- `app\models\orders.py` (add column)
- `app\schemas\order.py` (expose field)
- `app\database\migrate.py` (add column)
- `app\services\order_service.py` (set `art_number` on finalize for ART)
- `app\routes\orders.py` (ensure API returns it where needed)
- `app\web\app.js` (display on order page; search display choice)

## 5) Acceptance tests (don’t guess, verify)
1) Create **new ART** order → finalize
   - Checklist name: `MMDDYY`
   - Order shows ART#: `MMDDYY`
   - Stored in DB: `art_number` filled, `sp_number` unchanged/blank
2) Create **ART revision** → finalize
   - Checklist name: `MMDDYY-R1`
   - Order ART# matches
3) Create **ART additional version** → finalize
   - Creates a **new Trello card**
   - Stores its own Trello IDs
   - ART# is `MMDDYY` (no R1)
4) Radio/Video still behave the same:
   - SP numbers still stored in `sp_number`
   - Flipping to Art still clears SP (but does not touch `art_number`)

## 6) Canonical operating rules (carry forward)
- One step at a time
- No manual editing
- Provide downloadable replacements with the same filename
- No renaming files
- Windows/PowerShell only
- Route ordering matters

## 7) Immediate next step
Decide where ART# appears on the search page:
- Option A: show ART# in the existing SP column for art rows
- Option B: add a dedicated ART# column

(Default recommendation: Option A unless you want maximum clarity.)
