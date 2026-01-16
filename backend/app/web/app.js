(() => {
  const API_URL = "/orders/search2";
  const PAGE_SIZE = 50; // change later when you decide defaults

  let offset = 0;
  let total = 0;

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

  const els = {
    artist: $("artist"),
    notes: $("notes"),
    client_name: $("client_name"),
    client_company: $("client_company"),
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


  const STATE_KEY = "byp_ops_search_state_v1";

  function saveState() {
    try {
      const state = {
        offset,
        artist: els.artist.value,
        notes: els.notes.value,
        client_name: els.client_name.value,
        client_company: els.client_company.value,
        asset_type: els.asset_type.value,
        status: els.status.value,
        rep_code: els.rep_code.value,
        sp_number: els.sp_number.value,
        include_deleted: !!els.include_deleted.checked,
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

      els.artist.value = state.artist ?? "";
      els.notes.value = state.notes ?? "";
      els.client_name.value = state.client_name ?? "";
      els.client_company.value = state.client_company ?? "";
      els.asset_type.value = state.asset_type ?? "";
      els.status.value = state.status ?? "";
      els.rep_code.value = state.rep_code ?? "";
      els.sp_number.value = state.sp_number ?? "";
      els.include_deleted.checked = !!state.include_deleted;

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

    add("artist", els.artist.value);
    add("notes", els.notes.value);
    add("client_name", els.client_name.value);
    add("client_company", els.client_company.value);
    add("asset_type", els.asset_type.value);
    add("status", els.status.value);
    add("rep_code", els.rep_code.value);
    add("sp_number", els.sp_number.value);

    p.set("limit", String(PAGE_SIZE));
    p.set("offset", String(offset));
    p.set("include_deleted", els.include_deleted.checked ? "true" : "false");

    return p.toString();
  }

  function setPagerButtons() {
    els.prevBtn.disabled = offset <= 0;
    els.nextBtn.disabled = (offset + PAGE_SIZE) >= total;
  }

  function clearTable() {
    els.rows.innerHTML = "";
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
        "<th>Notes</th>";
    } catch (_) {
      // ignore
    }
  }


  function openDetail(id) {
    saveState();
    window.location.href = `/order/${encodeURIComponent(id)}`;
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

      tr.addEventListener("click", () => openDetail(o.id));
      tr.addEventListener("keydown", (e) => {
        if (e.key === "Enter") openDetail(o.id);
      });

      els.rows.appendChild(tr);
    }
  }

  async function runSearch(resetOffset) {
    if (resetOffset) offset = 0;

    // Persist current filters + paging so Back works without re-searching.
    saveState();
    els.error.textContent = "";
    els.summary.textContent = "Searching…";

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

      els.summary.textContent = total === 0
        ? "0 results."
        : ("Showing " + start + "–" + end + " of " + total + ".");

      render(items);
      setPagerButtons();
    } catch (e) {
      console.error(e);
      total = 0;
      setPagerButtons();
      clearTable();
      els.summary.textContent = "Error.";
      els.error.textContent = e && e.message ? e.message : String(e);
    }
  }

  function clearFilters() {
els.artist.value = "";
    els.notes.value = "";
    els.client_name.value = "";
    els.client_company.value = "";
    els.asset_type.value = "";
    els.status.value = "";
    els.rep_code.value = "";
    els.sp_number.value = "";
    els.include_deleted.checked = false;

    offset = 0;
    total = 0;
    els.summary.textContent = "Ready.";
    els.error.textContent = "";
    clearTable();
    // After clearing, show the default list again.
    runSearch(true);
  }

  // Wire up events
  els.searchBtn.addEventListener("click", () => runSearch(true));
  els.clearBtn.addEventListener("click", () => clearFilters());

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
        <input id="no_client_name" type="text" placeholder="Client name" />
      </div>

      <div class="byp-row">
        <label for="no_client_company">Company Name *</label>
        <input id="no_client_company" type="text" placeholder="Company name" />
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
          rep_name: rep_full,
          rep_code,
          client_name,
          client_company_name,
        };

        const url = "/orders/new?initials=" + encodeURIComponent(rep_code);

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
