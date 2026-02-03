# Project Brain — SP Order System (BYP Ops)

**Updated:** 2026-02-03 (America/Chicago)

## Current baseline
- **Latest known-good tag:** `savepoint-art-number-added-2026-02-02`
- **HEAD (reported):** `77c49f7` — Add `art_number` field + sqlite migrate

### What works at baseline
- Auth: cookie sessions ✅, inactive users kicked ✅
- Web Search/Orders: loads ✅, toolbar order ✅, save ✅, notes ✅, unfinalize/edit/save ✅
- Trello: finalize creates card+checklist ✅, Open Trello Card ✅
- Asset flip rules: Art↔Radio/Video SP assignment/clearing ✅
- ART checklist first one has **no -R1** ✅
- Trello checklist one-line width reference: **78 chars total** ✅
- `art_number` field exists and is stable ✅

## Known problem area: Clients/Company page
`/admin/clients` is unstable because it lives inside `app/main.py` (embedded HTML/JS/CSS + endpoints).

### Symptoms we’ve seen
- Table loads empty (contract/filter mismatch)
- “Show inactive” breaks or disappears
- Per-row Active checkbox appears but does nothing
- Accidental restyling (black background / layout drift)
- Search page breaks if `main.py` gets overwritten incorrectly

### Key gotcha
Browser may send `include_inactive=` (empty string) which can trigger a **422 parsing error** if the backend expects int/bool without normalization.

### Required target behavior
- Page loads for logged-in users (not admin-only)
- Default active-only
- “Show inactive” works (no 422)
- Per-row Active toggle persists
- Editable client/company + save
- No delete UI

## Canonical rules
- One step at a time.
- No manual file editing.
- Upload → I return downloadable replacement with the **exact same filename**.
- No renaming files. Ever.
- Windows only.
- No `${}` inside Python f-strings with embedded HTML/JS.
- Route ordering matters.
