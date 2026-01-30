(() => {
  const API_URL = "/orders/search2";



// ----- UI: Move Admin button/link to the far right on the main Search toolbar.
// This is done defensively (server renders the button; JS repositions it).
function moveAdminButtonToRightEdge() {
  try {
    const adminEl =
      document.querySelector('a[href^="/admin"]') ||
      document.querySelector('a[href*="/admin"]') ||
      document.querySelector('[data-role="admin-link"]') ||
      document.querySelector('#adminBtn') ||
      document.querySelector('#adminLink');

    if (!adminEl) return;

    // Try to find the toolbar row that contains this control.
    const row =
      adminEl.closest('.toolbar,.topbar,.actions,.controls,.btnrow,header,nav') ||
      adminEl.parentElement;

    if (!row) return;

    // Ensure the row is flex so margin-left:auto works.
    const cs = window.getComputedStyle(row);
    if (cs.display !== 'flex') {
      row.style.display = 'flex';
      row.style.flexWrap = 'wrap';
      row.style.alignItems = 'center';
      row.style.gap = '8px';
    }

    // Push the admin control to the far right.
    adminEl.style.marginLeft = 'auto';
  } catch (_) {
    // no-op
  }
}

// Run immediately (script is loaded at end of body) and also on DOMContentLoaded as a fallback.
try { moveAdminButtonToRightEdge(); } catch (_) {}
try { document.addEventListener('DOMContentLoaded', moveAdminButtonToRightEdge); } catch (_) {}

// ----- UI: Reorder main Search page buttons into a single left-aligned group.
// Desired order: My drafts, All, Search, Clear, New order
function reorderSearchToolbarButtons() {
  try {
    // Only run on the main search page (defensive); if this doesn't match, we still no-op safely.
    const path = (location && location.pathname) ? location.pathname : "";
    if (path.startsWith("/admin") || path.startsWith("/order/")) return;

    const norm = (s) => (s || "").toString().trim().toLowerCase();

    const controls = Array.from(document.querySelectorAll(
      'button, a.btnlink, a.button, a, input[type="button"], input[type="submit"]'
    ));

    const findByLabel = (label) => {
      const target = norm(label);
      for (const el of controls) {
        let t = "";
        if (el.tagName === "INPUT") t = el.value || "";
        else t = el.textContent || "";
        if (norm(t) === target) return el;
      }
      return null;
    };

    const draftsEl = findByLabel("My drafts") || findByLabel("My Drafts");
    const allEl = findByLabel("All");
    const searchEl = findByLabel("Search");
    const clearEl = findByLabel("Clear");
    const newOrderEl = findByLabel("New order") || findByLabel("New Order") || findByLabel("New");

    if (!draftsEl || !allEl) return; // can't anchor reliably

    // Find a toolbar container that contains drafts + all.
    let toolbar = draftsEl.parentElement;
    while (toolbar && toolbar !== document.body && !toolbar.contains(allEl)) {
      toolbar = toolbar.parentElement;
    }
    if (!toolbar || toolbar === document.body) return;

    // Pull target controls into the same toolbar (moving them if necessary).
    const desired = [draftsEl, allEl, searchEl, clearEl, newOrderEl].filter(Boolean);

    // Insert a marker at the start, then insert desired controls before it in order.
    const marker = document.createComment("toolbar-marker");
    toolbar.insertBefore(marker, toolbar.firstChild);

    for (const el of desired) {
      // If a control is outside, moving it here keeps it functional.
      if (!toolbar.contains(el)) {
        toolbar.insertBefore(el, marker);
      } else {
        toolbar.insertBefore(el, marker);
      }
    }

    // Remove marker
    toolbar.removeChild(marker);
  } catch (_) {
    // no-op
  }
}

// ----- UI: Ensure a real Clients button exists on the Search page (not a naked link).
function ensureClientsButton() {
  try {
    const newBtn = document.getElementById("newOrderBtn");
    if (!newBtn || !newBtn.parentElement) return;

    let clientsBtn = document.getElementById("clientsBtn");

    // If a link exists, replace it with a proper button.
    if (clientsBtn && clientsBtn.tagName === "A") {
      const btn = document.createElement("button");
      btn.id = "clientsBtn";
      btn.className = "btn";
      btn.textContent = (clientsBtn.textContent || "Clients").trim() || "Clients";
      try { clientsBtn.parentElement.replaceChild(btn, clientsBtn); } catch (_) {}
      clientsBtn = btn;
    }

    if (!clientsBtn) {
      clientsBtn = document.createElement("button");
      clientsBtn.id = "clientsBtn";
      clientsBtn.className = "btn";
      clientsBtn.textContent = "Clients";
      // Insert right after "New order" in the same toolbar row.
      try {
        newBtn.parentElement.insertBefore(clientsBtn, newBtn.nextSibling);
      } catch (_) {
        newBtn.parentElement.appendChild(clientsBtn);
      }
    }

    // Always wire the click (idempotent).
    clientsBtn.onclick = function () {
      try { window.location.href = "/admin/clients"; } catch (_) {}
    };
  } catch (_) {}
}

try { ensureClientsButton(); } catch (_) {}
try { document.addEventListener('DOMContentLoaded', ensureClientsButton); } catch (_) {}
// Run now + on DOMContentLoaded.
try { reorderSearchToolbarButtons(); } catch (_) {}
try { document.addEventListener('DOMContentLoaded', reorderSearchToolbarButtons); } catch (_) {}


  // ----- Clients: best-effort create so new names appear in suggest (fast v1)
  async function ensureClientExists(clientName, companyName) {
    const name = (clientName || "").trim();
    const company = (companyName || "").trim();
    if (!name) return null;

    try {
      const res = await fetch("/orders/clients", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", "Accept": "application/json" },
        body: JSON.stringify({
          client_name: name,
          company_name: company || null,
          is_active: true
        })
      });
      if (!res.ok) return null;
      const data = await res.json();
      if (data && data.id != null) return data.id;
      return null;
    } catch (_e) {
      return null;
    }
  }

  const PAGE_SIZE = 50; // change later when you decide defaults

  let offset = 0;
  let total = 0;
  
  // Row selection (for highlight + safe delete)
  let selectedOrderId = null;
  let selectedRowEl = null;

  const $ = (id) => {
    if (!id) return null;
    let el = document.getElementById(id);
    if (el) return el;

    // Fallbacks if IDs ever change:
    // - name="<id>"
    // - data-id="<id>"
    const esc = (window.CSS && CSS.escape)
      ? CSS.escape(String(id))
      : String(id).replace(/"/g, '\"');

    el = document.querySelector(`[name="${esc}"]`);
    if (el) return el;

    el = document.querySelector(`[data-id="${esc}"]`);
    if (el) return el;

    return null;
  };

  const pick = (...ids) => {
    for (let i = 0; i < ids.length; i++) {
      const el = $(ids[i]);
      if (el) return el;
    }
    return null;
  };

  const els = {
    artist: $("artist"),
    notes: $("notes"),
    client_name: $("client_name"),
    client_company: pick("client_company","client_company_name","client_company_name_filter","client_company_filter"),
    asset_type: $("asset_type"),
    status: $("status"),
    rep_code: $("rep_code"),
    sp_number: $("sp_number"),
    include_deleted: $("include_deleted"),

    searchBtn: $("searchBtn"),
    clearBtn: $("clearBtn"),
    prevBtn: $("prevBtn"),
    nextBtn: $("nextBtn"),

    summary: $("summary"),
    error: $("error"),
    rows: $("rows"),
  };

  // Users should not see deleted items from Search.
  (function hideIncludeDeleted(){
    try{
      if (!els.include_deleted) return;
      els.include_deleted.checked = false;
      // Hide checkbox and any nearby label text
      const wrap = els.include_deleted.closest("label") || els.include_deleted.parentElement;
      if (wrap) wrap.style.display = "none";
      else els.include_deleted.style.display = "none";
    } catch (_) {}
  })();


  // Visual cues for selection + delete button
  (function injectSearchStyles(){
    try{
      if (document.getElementById("searchDeleteStyles")) return;
      const st = document.createElement("style");
      st.id = "searchDeleteStyles";
      st.textContent = `
        tr.clickrow{ cursor: default; }
        tr.clickrow.row-selected{ outline: 2px solid currentColor; outline-offset: -2px; }
        tr.clickrow.row-selected td{ font-weight: 600; }
        button.btn-delete{
          border: 1px solid currentColor;
          padding: 2px 8px;
          border-radius: 6px;
          background: transparent;
          cursor: pointer;
        }
        button.btn-delete:hover{ filter: brightness(0.9); }
        button.btn-delete:disabled{ opacity: .5; cursor: not-allowed; }
        /* red delete (without assuming any global CSS vars) */
        button.btn-delete{ color: #b00020; border-color: #b00020; }
      `;
      document.head.appendChild(st);
    }catch(_e){}
  })();

  const val = (el) => {
    try { return el ? String(el.value ?? "") : ""; } catch (_) { return ""; }
  };
  const setVal = (el, v) => {
    try { if (el) el.value = String(v ?? ""); } catch (_) {}
  };
  const isChecked = (el) => {
    try { return !!(el && el.checked); } catch (_) { return false; }
  };
  const setChecked = (el, v) => {
    try { if (el) el.checked = !!v; } catch (_) {}
  };


  const STATE_KEY = "byp_ops_search_state_v1";

  function saveState() {
    try {
      const state = {
        offset,
        artist: val(els.artist),
        notes: val(els.notes),
        client_name: val(els.client_name),
        client_company: val(els.client_company),
        asset_type: val(els.asset_type),
        status: val(els.status),
        rep_code: val(els.rep_code),
        sp_number: val(els.sp_number),
        include_deleted: false,
      };
      sessionStorage.setItem(STATE_KEY, JSON.stringify(state));
    } catch (_) {
      // ignore
    }
  }

  function loadState() {
    try {
      const raw = sessionStorage.getItem(STATE_KEY);
      if (!raw) return false;
      const state = JSON.parse(raw);
      if (!state || typeof state !== "object") return false;

      setVal(els.artist, state.artist ?? "");
      setVal(els.notes, state.notes ?? "");
      setVal(els.client_name, state.client_name ?? "");
      setVal(els.client_company, state.client_company ?? "");
      setVal(els.asset_type, state.asset_type ?? "");
      setVal(els.status, state.status ?? "");
      setVal(els.rep_code, state.rep_code ?? "");
      setVal(els.sp_number, state.sp_number ?? "");
      setChecked(els.include_deleted, false);

      offset = Number(state.offset ?? 0) || 0;
      if (offset < 0) offset = 0;

      return true;
    } catch (_) {
      return false;
    }
  }

  function esc(v) {
    const s = String(v ?? "");
    return s
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function buildQuery() {
    const p = new URLSearchParams();

    const add = (k, v) => {
      const s = String(v ?? "").trim();
      if (s) p.set(k, s);
    };

    add("artist", val(els.artist));
    add("notes", val(els.notes));
    add("client_name", val(els.client_name));
    add("client_company", val(els.client_company));
    add("client_company_name", val(els.client_company));
add("asset_type", val(els.asset_type));
    add("status", val(els.status));
    add("rep_code", val(els.rep_code));
    add("sp_number", val(els.sp_number));

    p.set("limit", String(PAGE_SIZE));
    p.set("offset", String(offset));
    p.set("include_deleted", "false");
return p.toString();
  }

  function setPagerButtons() {
    if (els.prevBtn) els.prevBtn.disabled = offset <= 0;
    if (els.nextBtn) els.nextBtn.disabled = (offset + PAGE_SIZE) >= total;
  }

  function clearTable() {
    if (els.rows) els.rows.innerHTML = "";
    selectedOrderId = null;
    selectedRowEl = null;
  }

  function setTableHeaders() {
    // Force the header order to match the desktop app.
    // We do this here so you don't have to touch index.html every time we tweak columns.
    try {
      const headRow = document.querySelector("table thead tr");
      if (!headRow) return;
      headRow.innerHTML =
        "<th class=\"nowrap\">Rep</th>" +
        "<th class=\"nowrap\">Status</th>" +
        "<th class=\"nowrap\">Asset</th>" +
        "<th class=\"nowrap\">SP</th>" +
        "<th class=\"nowrap\">Revision Of</th>" +
        "<th class=\"nowrap\">Add'l Vers Of</th>" +
        "<th>Artist</th>" +
        "<th>Notes</th>" +
        "<th class=\"nowrap\">Actions</th>";
    } catch (_) {
      // ignore
    }
  }


  function openDetail(id) {
    saveState();
    window.location.href = `/order/${encodeURIComponent(id)}`;
  }


  function selectRow(tr, id) {
    try {
      if (selectedRowEl && selectedRowEl !== tr) selectedRowEl.classList.remove("row-selected");
      selectedRowEl = tr;
      selectedOrderId = id;
      if (selectedRowEl) selectedRowEl.classList.add("row-selected");
    } catch (_e) {}
  }

  async function softDeleteOrder(orderId, initials, force) {
    const id = Number(orderId);
    if (!id) throw new Error("Bad order id");

    const params = new URLSearchParams();
    if (initials) params.set("initials", initials);
    if (force) params.set("force", "true");
    const qs = params.toString() ? ("?" + params.toString()) : "";

    // Try a few known patterns without needing another code change.

    const attempts = [
      { url: `/orders/${encodeURIComponent(id)}/delete${qs}`, method: "POST" },
      { url: `/orders/${encodeURIComponent(id)}/delete${qs}`, method: "DELETE" },
      { url: `/orders/${encodeURIComponent(id)}${qs}`, method: "DELETE" },
      { url: `/orders/${encodeURIComponent(id)}/soft-delete${qs}`, method: "POST" },
      { url: `/orders/${encodeURIComponent(id)}/soft_delete${qs}`, method: "POST" },
    ];

    let lastText = "";
    for (const a of attempts) {
      try {
        const res = await fetch(a.url, { method: a.method, credentials: "same-origin", headers: { "Accept": "application/json" } });
        if (res.ok) return true;
        // If auth kicked us, bounce to login.
        if (res.status === 401 || res.status === 403) {
          window.location.href = "/login";
          return false;
        }
        lastText = await res.text();
        // Only keep trying if it's a likely "wrong endpoint/method".
        if (res.status === 404 || res.status === 405) continue;
        throw new Error(`HTTP ${res.status}: ${lastText || "Delete failed"}`);
      } catch (e) {
        // Network error, stop early.
        if (String(e && e.message || "").startsWith("HTTP ")) throw e;
      }
    }
    throw new Error(lastText ? lastText : "Delete failed (no matching endpoint)");
  }

  async function onDeleteFromList(orderId, label) {
    const id = Number(orderId);
    if (!id) return;
    const pretty = label ? String(label).trim() : "";
    const msg = pretty ? `Delete order ${id} (${pretty})?` : `Delete order ${id}?`;
    if (!confirm(msg + "\n\nThis will move it to Deleted Orders.")) return;

    try {
      if (els.error) els.error.textContent = "";
      const initials = await getActionInitials();
      if (!initials) throw new Error('Missing initials');

      try {
        await softDeleteOrder(id, initials, false);
      } catch (err) {
        const emsg = String((err && err.message) ? err.message : err);
        const needsForce = emsg.includes("order is finalized") && emsg.includes("force=true");
        if (!needsForce) throw err;

        if (!confirm("This order is FINALIZED.\n\nDelete anyway? (This requires force=true)")) {
          return;
        }
        await softDeleteOrder(id, initials, true);
      }

      // Re-run current search to refresh list
      await runSearch(false);
    } catch (e) {
      console.error(e);
      if (els.error) els.error.textContent = "Delete failed: " + (e && e.message ? e.message : String(e));
    }
  }

  function render(items) {
    clearTable();

    for (const o of items) {
      const tr = document.createElement("tr");
      tr.classList.add("clickrow");
      tr.tabIndex = 0;
      tr.title = "Open order details";
      tr.innerHTML =
        "<td class=\"nowrap\">" + esc((o.rep_code || (o.rep_name ? String(o.rep_name).split(/[-=—]/)[0].trim() : ""))) + "</td>" +
        "<td class=\"nowrap\">" + esc(o.status) + "</td>" +
        "<td class=\"nowrap\">" + esc(o.asset_type) + "</td>" +
        "<td class=\"nowrap\">" + esc(((o.sp && typeof o.sp === "object" && o.sp) ? (o.sp.sp_number || "") : (o.sp_number || ""))) + "</td>" +
        "<td class=\"nowrap\">" + esc(((o.sp && typeof o.sp === "object" && o.sp) ? (o.sp.revision_of || "") : (o.sp_revision_of || o.revision_of || ""))) + "</td>" +
        "<td class=\"nowrap\">" + esc(((o.sp && typeof o.sp === "object" && o.sp) ? (o.sp.additional_version_of || "") : (o.additional_version_of || ""))) + "</td>" +
        "<td>" + esc(o.artist) + "</td>" +
        "<td>" + esc(o.notes) + "</td>";

      tr.addEventListener("click", () => selectRow(tr, o.id));
      tr.addEventListener("dblclick", () => openDetail(o.id));
      tr.addEventListener("keydown", (e) => {
        if (e.key === "Enter") openDetail(o.id);
        if (e.key === "Delete") { e.preventDefault(); onDeleteFromList(o.id, o.artist); }
      });


      // Actions: Delete (soft-delete to Deleted Orders)
      try {
        const tdA = document.createElement("td");
        tdA.className = "nowrap";
        const delBtn = document.createElement("button");
        delBtn.type = "button";
        delBtn.className = "btn-delete";
        const alreadyDeleted = !!(o && (o.is_deleted || o.deleted_at || o.deleted_by));
        delBtn.textContent = alreadyDeleted ? "Deleted" : "Delete";
        delBtn.disabled = alreadyDeleted;
        delBtn.title = alreadyDeleted ? "Already deleted" : "Move to Deleted Orders";
        delBtn.addEventListener("click", (e) => {
          e.stopPropagation();
          selectRow(tr, o.id);
          onDeleteFromList(o.id, o.artist);
        });
        tdA.appendChild(delBtn);
        tr.appendChild(tdA);
      } catch (_e) {
        // ignore
      }

      if (els.rows) els.rows.appendChild(tr);
    }
  }

  async function runSearch(resetOffset) {
    if (resetOffset) offset = 0;

    // Persist current filters + paging so Back works without re-searching.
    saveState();
    if (els.error) els.error.textContent = "";
    if (els.summary) els.summary.textContent = "Searching…";

    const url = API_URL + "?" + buildQuery();

    try {
      const resp = await fetch(url, { headers: { "Accept": "application/json" } });
      if (!resp.ok) {
        const msg = await resp.text();
        throw new Error("HTTP " + resp.status + ": " + msg);
      }

      const data = await resp.json();
      total = Number(data.total ?? 0) || 0;
      const items = Array.isArray(data.items) ? data.items : [];

      const start = total === 0 ? 0 : offset + 1;
      const end = Math.min(offset + items.length, total);

      if (els.summary) els.summary.textContent = total === 0
        ? "0 results."
        : ("Showing " + start + "–" + end + " of " + total + ".");

      render(items);
      setPagerButtons();
    } catch (e) {
      console.error(e);
      total = 0;
      setPagerButtons();
      clearTable();
      if (els.summary) els.summary.textContent = "Error.";
      if (els.error) els.error.textContent = e && e.message ? e.message : String(e);
    }
  }

  function clearFilters() {
setVal(els.artist, "");
    setVal(els.notes, "");
    setVal(els.client_name, "");
    setVal(els.client_company, "");
    setVal(els.asset_type, "");
    setVal(els.status, "");
    setVal(els.rep_code, "");
    setVal(els.sp_number, "");
    setChecked(els.include_deleted, false);

    offset = 0;
    total = 0;
    els.summary.textContent = "Ready.";
    els.error.textContent = "";
    clearTable();
    // After clearing, show the default list again.
    runSearch(true);
  }

  // Wire up events
  if (els.searchBtn) els.searchBtn.addEventListener("click", () => runSearch(true));
if (els.clearBtn) els.clearBtn.addEventListener("click", () => clearFilters());
// ----- New Order (web-only) -----
  // Minimal create flow: Artist + Asset Type required (per OpenAPI OrderCreate). Optional notes + client fields.
  // Keep in sync with desktop GUI REP_FULL (source of truth for now)
  const REP_FULL = [
    "SB - Steve Bassett",
    "RM - Ron Mewis",
    "AML - Allison Lineberry",
    "JS - Jon Shults",
    "CD - Celine DeLeon",
  ];

  function repCodeFromFull(repFull) {
    const s = String(repFull || "").trim();
    if (!s) return "";
    return (s.split(/\s+/)[0] || "").trim();
  }

  function populateRepSelect(sel) {
    if (!sel) return;
    sel.innerHTML = "";
    for (const r of REP_FULL) {
      const opt = document.createElement("option");
      opt.value = r;
      opt.textContent = r;
      sel.appendChild(opt);
    }
    // default
    sel.value = REP_FULL[0] || "";
  }

  function populateAssetSelect(sel) {
    if (!sel) return;
    sel.innerHTML = "";

    // Prefer copying whatever the search filter uses, so we don't fork lists.
    const src = els.asset_type;
    let values = [];

    try {
      if (src && src.tagName === "SELECT") {
        values = Array.from(src.options || []).map(o => String(o.value || "").trim()).filter(v => v);
      } else if (src && src.getAttribute) {
        const dlId = src.getAttribute("list");
        if (dlId) {
          const dl = document.getElementById(dlId);
          if (dl) {
            values = Array.from(dl.querySelectorAll("option")).map(o => String(o.value || "").trim()).filter(v => v);
          }
        }
      }
    } catch (_) {}

    if (!values.length) {
      values = ["radio", "video", "art", "longform"];
    }

    for (const v of values) {
      const opt = document.createElement("option");
      opt.value = v;
      opt.textContent = v;
      sel.appendChild(opt);
    }

    // default to radio if present
    sel.value = values.includes("radio") ? "radio" : (values[0] || "");
  }

  function injectNewOrderButton() {
    try {
      if (!els.searchBtn) return;
      const parent = els.searchBtn.parentElement;
      if (!parent) return;

      // Don't double-insert if app.js hot reloads or runs twice.
      if (document.getElementById("newOrderBtn")) return;

      const btn = document.createElement("button");
      btn.id = "newOrderBtn";
      btn.type = "button";
      btn.textContent = "New Order";
      btn.style.marginLeft = "6px";

      btn.addEventListener("click", () => showNewOrderModal());
            // Put it on its own (not wedged between Search and Clear)
      btn.style.marginLeft = "18px";
      btn.style.whiteSpace = "nowrap";

      // Prefer placing it AFTER Clear (same button bar), otherwise just append.
      if (els.clearBtn && els.clearBtn.parentElement === parent) {
        parent.insertBefore(btn, els.clearBtn.nextSibling);
      } else {
        parent.appendChild(btn);
      }
} catch (_) {
      // ignore
    }
  }

  function ensureNewOrderStyles() {
    if (document.getElementById("newOrderStyles")) return;
    const style = document.createElement("style");
    style.id = "newOrderStyles";
    style.textContent = `
      .byp-modal-overlay{
        position:fixed; inset:0; background:rgba(0,0,0,.35);
        display:flex; align-items:center; justify-content:center;
        z-index:9999; padding:16px;
      }
      .byp-modal{
        width:min(720px, 100%); background:#fff; border:1px solid #ddd;
        border-radius:14px; padding:14px;
        font-family:system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
      }
      .byp-modal h3{ margin:0 0 10px 0; font-size:16px; }
      .byp-row{ display:grid; grid-template-columns: 160px 1fr; gap:10px; margin:8px 0; align-items:center; }
      .byp-row label{ font-size:12px; color:#444; }
      .byp-row input, .byp-row textarea, .byp-row select{
        width:100%; padding:8px 10px; border:1px solid #ccc; border-radius:10px; font-size:14px;
      }
      .byp-row textarea{ min-height:90px; resize:vertical; }
      .byp-actions{ display:flex; gap:10px; justify-content:flex-end; margin-top:12px; flex-wrap:wrap; }
      .byp-hint{ font-size:12px; color:#666; }
      .byp-err{ color:#b00020; font-weight:700; white-space:pre-wrap; }
      .byp-suggest{ position:absolute; left:0; right:0; top:calc(100% + 2px);
        background:#fff; border:1px solid #ccc; border-radius:10px; box-shadow:0 8px 20px rgba(0,0,0,.12);
        max-height:220px; overflow:auto; z-index:10000; display:none; }
      .byp-suggest-item{ padding:8px 10px; cursor:pointer; font-size:13px; }
      .byp-suggest-item:hover{ background:#f3f3f3; }
      .byp-suggest-item.active{ background:#93c5fd; }
      .byp-suggest-muted{ color:#666; font-size:12px; }
    `;
    document.head.appendChild(style);
  }

  function showNewOrderModal() {
    ensureNewOrderStyles();

    const overlay = document.createElement("div");
    overlay.className = "byp-modal-overlay";
    overlay.tabIndex = -1;

    const modal = document.createElement("div");
    modal.className = "byp-modal";

    modal.innerHTML = `
      <h3>Create Order</h3>

      <div class="byp-row">
        <label for="no_rep">Rep *</label>
        <select id="no_rep"></select>
      </div>

      <div class="byp-row">
        <label for="no_client_name">Client Name *</label>
        <div style="position:relative;">
          <input id="no_client_name" type="text" placeholder="Client name" autocomplete="new-password" />
          <input id="no_client_id" type="hidden" />
          <div id="no_client_suggest" class="byp-suggest"></div>
        </div>
</div>

      <div class="byp-row">
        <label for="no_client_company">Company Name *</label>
        <input id="no_client_company" type="text" placeholder="Company name" autocomplete="new-password" />
      </div>

      <div class="byp-row">
        <label for="no_artist">Artist *</label>
        <input id="no_artist" type="text" placeholder="Artist name" />
      </div>

      <div class="byp-row">
        <label for="no_asset">Asset *</label>
        <select id="no_asset"></select>
      </div>

      <div class="byp-hint">* required</div>
      <div id="no_err" class="byp-err"></div>
      <div class="byp-actions">
        <button id="no_cancel" type="button">Cancel</button>
        <button id="no_create" type="button">Create</button>
      </div>
    `;

    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    const $m = (id) => modal.querySelector("#" + id);

    const repEl = $m("no_rep");
    const clientNameEl = $m("no_client_name");
    const clientCompanyEl = $m("no_client_company");
    const clientIdEl = $m("no_client_id");
    const clientSuggestBox = $m("no_client_suggest");

    // --- Client typeahead (New Order) ---
    let clientSuggestTimer = null;
    let clientSelectedCompany = null;
    let clientSuggestItems = [];
    let clientSuggestIndex = -1;

    function hideClientSuggest() {
      if (!clientSuggestBox) return;
      clientSuggestBox.style.display = "none";
      clientSuggestBox.innerHTML = "";
      clientSuggestItems = [];
      clientSuggestIndex = -1;
    }

    async function fetchClientSuggest(q) {
      try {
        const res = await fetch("/orders/clients/suggest?q=" + encodeURIComponent(q) + "&limit=10", { credentials: "same-origin" });
        if (!res.ok) return [];
        const data = await res.json();

        // API may return a raw array OR a wrapper object like { value: [...], Count: N } / { items: [...] }.
        if (Array.isArray(data)) return data;
        if (data && Array.isArray(data.value)) return data.value;
        if (data && Array.isArray(data.items)) return data.items;
        if (data && Array.isArray(data.results)) return data.results;

        return [];
      } catch (_) {
        return [];
      }
    }

    
function setClientSuggestActive(idx) {
  if (!clientSuggestBox) return;
  const kids = Array.from(clientSuggestBox.querySelectorAll(".byp-suggest-item"));
  if (!kids.length) { clientSuggestIndex = -1; return; }
  let n = idx;
  if (n < 0) n = 0;
  if (n >= kids.length) n = kids.length - 1;

  kids.forEach((el, i) => {
    el.style.background = (i === n) ? "#93c5fd" : "transparent";
    el.style.border = (i === n) ? "1px solid #1d4ed8" : "1px solid transparent";
    el.style.borderRadius = "8px";
    el.setAttribute("aria-selected", (i === n) ? "true" : "false");
  });

  clientSuggestIndex = n;
  try { kids[n].scrollIntoView({ block: "nearest" }); } catch (_) {}
}

function applyClientSuggestItem(it) {
  if (!it) return;
  const nm = String(it.client_name || "").trim();
  const co = String(it.company_name || it.client_company_name || it.client_company || it.company || "").trim();
  try { clientNameEl.value = nm; } catch (_) {}
  try { clientCompanyEl.value = co; } catch (_) {}
  try { clientIdEl.value = String(it.id ?? ""); } catch (_) {}
  clientSelectedCompany = co || null;
  hideClientSuggest();
  try { clientNameEl.focus(); clientNameEl.setSelectionRange(clientNameEl.value.length, clientNameEl.value.length); } catch (_) {}
}

function maybeAutofillCompanyFromExactMatch(typedName, items) {
  try {
    const want = String(typedName || "").trim().toLowerCase();
    if (!want) return;

    // Don't overwrite something the user already typed.
    const coNow = String(clientCompanyEl && clientCompanyEl.value || "").trim();
    if (coNow) return;

    let best = null;
    let bestCompany = "";

    const getCo = (x) => {
      try { return String(x.company_name || x.client_company_name || x.client_company || x.company || "").trim(); }
      catch (_e) { return ""; }
    };

    for (let i = 0; i < (items || []).length; i++) {
      const it = items[i];
      const nm = String(it && it.client_name || "").trim();
      if (!nm) continue;
      if (nm.toLowerCase() !== want) continue;

      const co = getCo(it);
      if (!best) best = it;
      if (co) { best = it; bestCompany = co; break; }
    }

    if (!best) return;

    bestCompany = bestCompany || getCo(best);
    if (bestCompany) {
      try { clientCompanyEl.value = bestCompany; } catch (_) {}
      try { clientIdEl.value = String(best.id ?? ""); } catch (_) {}
      clientSelectedCompany = bestCompany || null;
    }
  } catch (_e) {}
}

function selectActiveClientSuggest() {
  if (clientSuggestIndex < 0 || clientSuggestIndex >= clientSuggestItems.length) return false;
  applyClientSuggestItem(clientSuggestItems[clientSuggestIndex]);
  return true;
}

function renderClientSuggest(items) {
      if (!clientSuggestBox) return;
      if (!items || !items.length) { hideClientSuggest(); return; }
      clientSuggestBox.innerHTML = "";
      clientSuggestItems = Array.isArray(items) ? items.slice() : [];
      clientSuggestIndex = -1;
      for (let i = 0; i < items.length; i++) {
        const it = items[i];
        const nm = String(it.client_name || "").trim();
        const co = String(it.company_name || it.client_company_name || it.client_company || it.company || "").trim();
        const div = document.createElement("div");
        div.className = "byp-suggest-item";
        div.setAttribute("role", "option");
        div.style.padding = "8px 10px";
        div.style.cursor = "pointer";
        div.style.userSelect = "none";
        div.style.borderRadius = "8px";
        div.style.background = "transparent";
        div.textContent = co ? (nm + " — " + co) : nm;
        div.addEventListener("mouseenter", () => { setClientSuggestActive(i); });
        div.addEventListener("mousedown", (e) => {
          e.preventDefault();
          applyClientSuggestItem(it);
        });
        clientSuggestBox.appendChild(div);
      }
      clientSuggestBox.setAttribute("role", "listbox");
      clientSuggestBox.style.display = "block";
    }

    
function onClientNameKeyDown(e) {
  if (!clientSuggestBox || clientSuggestBox.style.display !== "block") return;
  const k = e.key || "";
  const code = e.keyCode || 0;

  if (k === "ArrowDown" || code === 40) {
    e.preventDefault();
    if (clientSuggestIndex < 0) setClientSuggestActive(0);
    else setClientSuggestActive(clientSuggestIndex + 1);
  } else if (k === "ArrowUp" || code === 38) {
    e.preventDefault();
    if (clientSuggestIndex < 0) setClientSuggestActive(0);
    else setClientSuggestActive(clientSuggestIndex - 1);
  } else if (k === "Enter" || code === 13) {
    if (clientSuggestIndex >= 0) {
      e.preventDefault();
      selectActiveClientSuggest();
    }
  } else if (k === "Escape" || code === 27) {
    e.preventDefault();
    hideClientSuggest();
  }
}

function onClientNameInput() {
      const q = String(clientNameEl.value || "").trim();

      // If user is typing after selecting a client, clear client_id and (if we auto-filled it) company
      if (clientIdEl && clientIdEl.value) {
        // If current value no longer equals the selected client name, treat as manual edit
        // (best-effort; we don't store selected name separately)
        // Clearing here is safer than silently keeping an old client_id.
        clientIdEl.value = "";
        if (clientSelectedCompany && String(clientCompanyEl.value || "") === String(clientSelectedCompany || "")) {
          clientCompanyEl.value = "";
        }
        clientSelectedCompany = null;
      }

      if (clientSuggestTimer) { clearTimeout(clientSuggestTimer); clientSuggestTimer = null; }
      if (q.length < 2) { hideClientSuggest(); return; }
      clientSuggestTimer = setTimeout(async () => {
        const items = await fetchClientSuggest(q);
        renderClientSuggest(items);
        // If typed name exactly matches a known client, auto-fill company without forcing a click.
        maybeAutofillCompanyFromExactMatch(q, items);
      }, 250);
    }

    if (clientNameEl) {
      clientNameEl.addEventListener("input", onClientNameInput);
      clientNameEl.addEventListener("keydown", onClientNameKeyDown);
      clientNameEl.addEventListener("focus", () => { /* re-run to show suggestions */ onClientNameInput(); });
      clientNameEl.addEventListener("blur", () => { setTimeout(hideClientSuggest, 150); });
    }

    document.addEventListener("mousedown", (e) => {
      try {
        if (!modal.contains(e.target)) return;
        if (clientSuggestBox && !clientSuggestBox.contains(e.target) && e.target !== clientNameEl) hideClientSuggest();
      } catch (_) {}
    });

    const artistEl = $m("no_artist");
    const assetEl = $m("no_asset");
    const errEl = $m("no_err");
    const cancelBtn = $m("no_cancel");
    const createBtn = $m("no_create");

    // Populate dropdowns (Rep + Asset) from known lists / existing filter controls
    populateRepSelect(repEl);
    populateAssetSelect(assetEl);

    // Default focus
    setTimeout(() => { try { clientNameEl.focus(); } catch (_) {} }, 0);

    function close() {
      try { document.body.removeChild(overlay); } catch (_) {}
    }

    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) close();
    });

    cancelBtn.addEventListener("click", close);

    overlay.addEventListener("keydown", (e) => {
      if (e.key === "Escape") close();
    });

    async function create() {
      errEl.textContent = "";

      const rep_full = String(repEl.value || "").trim();
      const rep_code = repCodeFromFull(rep_full);

      const client_name = String(clientNameEl.value || "").trim();
      const client_company_name = String(clientCompanyEl.value || "").trim();
      const artist = String(artistEl.value || "").trim();
      const asset_type = String(assetEl.value || "").trim();

      if (!rep_full || !rep_code) {
        errEl.textContent = "Rep is required.";
        repEl.focus();
        return;
      }
      if (!client_name) {
        errEl.textContent = "Client Name is required.";
        clientNameEl.focus();
        return;
      }
      if (!client_company_name) {
        errEl.textContent = "Company Name is required.";
        clientCompanyEl.focus();
        return;
      }
      if (!artist) {
        errEl.textContent = "Artist is required.";
        artistEl.focus();
        return;
      }
      if (!asset_type) {
        errEl.textContent = "Asset is required.";
        assetEl.focus();
        return;
      }

      createBtn.disabled = true;
      cancelBtn.disabled = true;
      createBtn.textContent = "Creating…";

      try {
        const payload = {
          artist,
          asset_type,
          status: "draft",
          rep_name: rep_full,
          rep_code,
          client_name,
          client_company_name,
          client_id: (clientIdEl && clientIdEl.value ? Number(clientIdEl.value) : null),
        };

        const url = "/orders/new?initials=" + encodeURIComponent(rep_code);

        // Best-effort: if user typed a new client and didn't pick a suggestion, create it so it appears in autofill next time.
        if (!payload.client_id && (payload.client_name || "").trim()) {
          const newId = await ensureClientExists(payload.client_name, payload.client_company_name);
          if (newId) {
            payload.client_id = newId;
            if (clientIdEl) clientIdEl.value = String(newId);
          }
        }

        const res = await fetch(url, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Accept": "application/json",
          },
          body: JSON.stringify(payload),
        });

        const text = await res.text();
        if (!res.ok) {
          throw new Error("HTTP " + res.status + ": " + text);
        }

        const data = JSON.parse(text);

        if (!data || !data.id) {
          throw new Error("Create succeeded but response is missing id.");
        }

        // Force a refresh when returning to search, so the new order shows up without "Clear".
        try {
          sessionStorage.setItem("byp_ops_force_refresh", "1");
          sessionStorage.setItem("byp_ops_last_created_id", String(data.id));
        } catch (_) {}

        saveState();
        window.location.href = "/order/" + encodeURIComponent(data.id) + "?from=home";
      } catch (e) {
        errEl.textContent = String(e);
      } finally {
        createBtn.disabled = false;
        cancelBtn.disabled = false;
        createBtn.textContent = "Create";
      }
    }

createBtn.addEventListener("click", create);
    modal.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        // Let Enter in textarea insert newline; everything else triggers create
        const t = e.target;
        if (t && t.tagName === "TEXTAREA") return;
        e.preventDefault();
        create();
      }
    });

    // Focus first input
    artistEl.focus();
  }

  els.prevBtn.addEventListener("click", () => {
    offset = Math.max(0, offset - PAGE_SIZE);
    runSearch(false);
  });

  els.nextBtn.addEventListener("click", () => {
    offset = offset + PAGE_SIZE;
    runSearch(false);
  });

  document.addEventListener("keydown", (e) => {
    if (e.key !== "Enter") return;
    const t = e.target;
    if (t && (t.tagName === "BUTTON")) return;
    runSearch(true);
  });

  // Initial state
  setTableHeaders();
  injectNewOrderButton();
  setPagerButtons();

  // Auto-load results on first open, and restore last search when returning.
  const hadState = loadState();

  // If we just created/edited something and came back, force a refresh (bfcache won’t rerun JS otherwise).
  let forceRefresh = false;
  try {
    const params = new URLSearchParams(window.location.search || "");
    if (params.get("refresh") === "1") forceRefresh = true;
    if (sessionStorage.getItem("byp_ops_force_refresh") === "1") forceRefresh = true;

    if (forceRefresh) {
      try { sessionStorage.removeItem("byp_ops_force_refresh"); } catch (_) {}
      // Clean the URL so refresh=1 doesn’t stick around forever.
      if (params.get("refresh") === "1") {
        params.delete("refresh");
        const qs = params.toString();
        const newUrl = window.location.pathname + (qs ? ("?" + qs) : "");
        window.history.replaceState(null, "", newUrl);
      }
    }
  } catch (_) {}

  runSearch(forceRefresh || !hadState);


  // ---- My Drafts (web) helpers ----
  // Expose a tiny API so index.html (or future pages) can call it without depending on element IDs.
  // Shortcut keys:
  //   Ctrl+Shift+K = My Drafts
  //   Ctrl+Shift+L = All
  window.BYPOps = window.BYPOps || {};

  let _meCache = null;

  async function fetchMe() {
    if (_meCache) return _meCache;
    try {
      const r = await fetch("/me", { method: "GET" });
      const j = await r.json();
      _meCache = j;
      return j;
    } catch (_) {
      return null;
    }
  }

  async function getActionInitials() {
    // Many endpoints require ?initials=XX (rep_code). Pull from /me, fall back to cached UI value, then prompt.
    let me = null;
    try { me = await fetchMe(); } catch (_) { me = null; }

    const candidates = [
      me && (me.initials || me.rep_code || me.repCode || me.code),
      (typeof BYPOps !== "undefined" && BYPOps && (BYPOps.rep_code || BYPOps.initials)) ? (BYPOps.rep_code || BYPOps.initials) : null,
    ];

    let initials = null;
    for (const c of candidates) {
      if (typeof c === "string" && c.trim()) { initials = c.trim(); break; }
    }

    if (!initials) {
      initials = (localStorage.getItem("bypops_initials") || "").trim();
    }

    if (!initials) {
      const typed = prompt("Enter your initials (rep code), e.g. SB", "SB");
      if (typed && String(typed).trim()) {
        initials = String(typed).trim();
        try { localStorage.setItem("bypops_initials", initials); } catch (_) {}
      }
    }

    return initials;
  }


  function clearFilters() {
    // Text inputs
    const txtIds = ["artist", "notes", "client_name", "client_company", "sp_number"];
    for (let i = 0; i < txtIds.length; i++) {
      const el = $(txtIds[i]);
      if (el) el.value = "";
    }

    // Selects (best-effort)
    const selIds = ["asset_type", "status", "rep_code"];
    for (let j = 0; j < selIds.length; j++) {
      const s = $(selIds[j]);
      if (s) s.value = "";
    }

    const chk = $("include_deleted");
    if (chk) chk.checked = false;
  }

  async function applyMyDrafts() {
    const me = await fetchMe();
    if (!me || !me.authenticated) {
      window.location.href = "/login";
      return;
    }

    clearFilters();

    const status = $("status");
    if (status) status.value = "draft";

    const rep = $("rep_code");
    if (rep && me.rep_code) rep.value = String(me.rep_code).trim();

    // Reuse existing search pipeline
    try {
      runSearch(true);
    } catch (_) {
      // Fallback: click search button if someone ever refactors runSearch away
      const b = $("searchBtn");
      if (b) b.click();
    }
  }

  function applyAll() {
    clearFilters();
    try {
      runSearch(true);
    } catch (_) {
      const b = $("searchBtn");
      if (b) b.click();
    }
  }

  window.BYPOps.applyMyDrafts = applyMyDrafts;
  window.BYPOps.applyAll = applyAll;
  window.BYPOps.fetchMe = fetchMe;

  // Wire buttons if present (id preferred, text fallback)
  function findButtonByText(text) {
    const buttons = document.querySelectorAll("button");
    const want = String(text || "").toLowerCase();
    for (let i = 0; i < buttons.length; i++) {
      const t = (buttons[i].textContent || "").trim().toLowerCase();
      if (t === want) return buttons[i];
    }
    return null;
  }

  const myBtn = $("myDraftsBtn") || findButtonByText("My Drafts");
  if (myBtn) myBtn.addEventListener("click", () => applyMyDrafts());

  const allBtn = $("allBtn") || findButtonByText("All");
  if (allBtn) allBtn.addEventListener("click", () => applyAll());

  // Shortcut keys (avoid common browser combos)
  window.addEventListener("keydown", (e) => {
    try {
      if (!e) return;
      const key = String(e.key || "").toLowerCase();

      if (e.ctrlKey && e.shiftKey && key === "k") {
        e.preventDefault();
        applyMyDrafts();
      } else if (e.ctrlKey && e.shiftKey && key === "l") {
        e.preventDefault();
        applyAll();
      }
    } catch (_) {}
  });

  // When navigating back from detail, browsers may restore this page from bfcache.
  // Ensure the table isn't stale.
  window.addEventListener("pageshow", (e) => {
    try {
      if (e && e.persisted) runSearch(false);
    } catch (_) {}
  });

  // ---- Order detail helpers: Auto-save on Back (web) ----
  // This file is also loaded on the order detail page. We don't assume IDs
  // never change, so this is defensive and only activates when an order form
  // is present.
  (function enableOrderAutoSaveOnBack() {
    try {
      // Detect an order detail form.
      const form =
        document.querySelector('form#orderForm') ||
        document.querySelector('form[data-order-form]') ||
        document.querySelector('form[action*="/orders/"]') ||
        null;

      if (!form) return; // not on order page

      // Track dirty state for any input/select/textarea inside the form.
      let isDirty = false;
      const markDirty = () => { isDirty = true; };

      const fields = form.querySelectorAll('input, select, textarea');
      for (let i = 0; i < fields.length; i++) {
        fields[i].addEventListener('input', markDirty, { passive: true });
        fields[i].addEventListener('change', markDirty, { passive: true });
      }

      // Expose tiny hooks so the order page can cooperate without tight coupling.
      window.BYPOps = window.BYPOps || {};
      window.BYPOps.orderIsDirty = () => !!isDirty;
      window.BYPOps._markOrderClean = () => { isDirty = false; };

      // Try to locate a Back button/link.
      const byId = (id) => document.getElementById(id);
      const backBtn =
        byId('backBtn') ||
        byId('backButton') ||
        byId('btnBack') ||
        document.querySelector('[data-action="back"]') ||
        (function findBackByText() {
          const btns = document.querySelectorAll('button, a');
          for (let j = 0; j < btns.length; j++) {
            const t = (btns[j].textContent || '').trim().toLowerCase();
            if (t === 'back' || t === '← back' || t === 'back to search') return btns[j];
          }
          return null;
        })();

      if (!backBtn) {
        // No explicit Back button found. Still warn on unload if dirty.
        window.addEventListener('beforeunload', (e) => {
          try {
            if (!isDirty) return;
            e.preventDefault();
            e.returnValue = '';
          } catch (_) {}
        });
        return;
      }

      // Identify the save function the order page already uses.
      function getSaveFn() {
        try {
          if (window.BYPOps && typeof window.BYPOps.saveOrder === 'function') return window.BYPOps.saveOrder;
          if (typeof window.saveOrder === 'function') return window.saveOrder;
          if (typeof window.onSave === 'function') return window.onSave;
        } catch (_) {}
        return null;
      }

      // Attempt to show errors somewhere sane.
      function showSaveError(msg) {
        try {
          const el = document.getElementById('saveError') || document.getElementById('error') || null;
          if (el) {
            el.textContent = msg;
            return;
          }
        } catch (_) {}
        try { alert(msg); } catch (_) {}
      }

      async function saveThenGoBack(ev) {
        try {
          if (!isDirty) return; // nothing to do

          const saveFn = getSaveFn();
          if (!saveFn) {
            // Can't autosave without a save function; at least warn.
            showSaveError('Unsaved changes. No save handler found for auto-save. Click Save first.');
            ev.preventDefault();
            ev.stopPropagation();
            return;
          }

          ev.preventDefault();
          ev.stopPropagation();

          // Lock UI while saving
          const prevDisabled = !!backBtn.disabled;
          backBtn.disabled = true;

          let ok = false;
          try {
            const res = await saveFn();
            // Accept: true/false, {ok:true}, or undefined (assume ok if no exception)
            ok = (res === undefined) ? true : (!!res && (res.ok === undefined ? true : !!res.ok));
          } catch (e) {
            ok = false;
            showSaveError((e && e.message) ? e.message : String(e));
          }

          backBtn.disabled = prevDisabled;

          if (!ok) {
            // stay put
            return;
          }

          // Mark clean and navigate.
          isDirty = false;

          // If it's a link, preserve its intent; otherwise just history.back().
          try {
            if (backBtn.tagName === 'A') {
              const href = backBtn.getAttribute('href');
              if (href) {
                window.location.href = href;
                return;
              }
            }
          } catch (_) {}

          try { window.history.back(); } catch (_) { window.location.href = '/'; }
        } catch (_) {
          // ignore
        }
      }

      // Capture-phase handler so we beat any existing click logic that navigates.
      backBtn.addEventListener('click', saveThenGoBack, true);

      // Native back/refresh/tab-close: we can't reliably async save here, so warn.
      window.addEventListener('beforeunload', (e) => {
        try {
          if (!isDirty) return;
          e.preventDefault();
          e.returnValue = '';
        } catch (_) {}
      });
    } catch (_) {
      // no-op
    }
  })();
})();
