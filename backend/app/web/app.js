(() => {
  const API_URL = "/orders/search2";
  const PAGE_SIZE = 50; // change later when you decide defaults

  let offset = 0;
  let total = 0;

  const $ = (id) => document.getElementById(id);

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

  function render(items) {
    clearTable();

    for (const o of items) {
      const tr = document.createElement("tr");
      tr.innerHTML =
        "<td class=\"nowrap\">" + esc(o.id) + "</td>" +
        "<td>" + esc(o.artist) + "</td>" +
        "<td class=\"nowrap\">" + esc(o.asset_type) + "</td>" +
        "<td class=\"nowrap\">" + esc(o.status) + "</td>" +
        "<td class=\"nowrap\">" + esc(o.rep_code) + "</td>" +
        "<td>" + esc(o.client_company_name) + "</td>" +
        "<td>" + esc(o.notes) + "</td>";
      els.rows.appendChild(tr);
    }
  }

  async function runSearch(resetOffset) {
    if (resetOffset) offset = 0;

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
    setPagerButtons();
  }

  // Wire up events
  els.searchBtn.addEventListener("click", () => runSearch(true));
  els.clearBtn.addEventListener("click", () => clearFilters());

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
  setPagerButtons();
})();