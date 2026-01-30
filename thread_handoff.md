# Thread Handoff — SP Order System (Next Thread)

## Where we are now
Baseline: **working** on `fix-delete-override`.

### Fixed today (locked by savepoints)
1) **Order Save stopped working** due to JS calling `ensureClientExists` that was not defined in the order page scope.
   - Fixed by removing that dependency inside the order page save flow.
   - Tag: `savepoint-fix-save-ensureclient-2026-01-29`

2) **Open Trello Card button 500**
   - Fixed by adding missing session user helper / env loading / Trello key+token fallback so the endpoint no longer crashes.
   - Tag: `savepoint-fix-open-trello-card-2026-01-29`

3) **UI polish**
   - Admin button moved far right on search page
   - Search toolbar buttons reordered: My drafts, All, Search, Clear, New order
   - Tag: `savepoint-ui-search-toolbar-2026-01-29`

4) **Admin pages nav consistency**
   - Admin pages now share consistent top nav buttons (Back to Search | Users | Deleted Orders | Clients/Company)

## Current open work (next thread focus)
### Pivot decision
Move **Clients/Company management** from Admin page → **Search page** so normal users can maintain client info themselves.

Rationale:
- Finalized orders are protected because orders store snapshot text fields (`client_name`, `client_company_name`).
- Clients already support `is_active` to hide old companies from autofill without deleting history.

### Next step
Implement “Clients/Company” manager from the Search page:
- Add a button on Search page
- Modal/panel to:
  - Search clients
  - Add new
  - Edit name/company
  - Deactivate/reactivate
  - Optional: show inactive toggle
- Ensure suggestion/autofill uses active clients by default.

## Files touched recently (high risk)
- `app/main.py` (order page save flow + trello route + admin nav)
- `app/web/app.js` (search toolbar layout/order)
- **Warning:** any changes here can break Save or Trello button—savepoint before touching.

## Restore points
- `savepoint-fix-open-trello-card-2026-01-29`
- `savepoint-ui-search-toolbar-2026-01-29`
