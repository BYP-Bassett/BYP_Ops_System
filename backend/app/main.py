from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.routes.orders import router as orders_router


app = FastAPI()

# API routes
app.include_router(orders_router)

# --- Web UI (vanilla HTML/JS served by FastAPI) ---
APP_DIR = Path(__file__).resolve().parent
WEB_DIR = APP_DIR / "web"

# Serve static assets (JS/CSS) from /web/*
# Example: /web/app.js
app.mount("/web", StaticFiles(directory=WEB_DIR), name="web")


@app.get("/", include_in_schema=False)
def web_root():
    # Browser UI
    return FileResponse(WEB_DIR / "index.html")


@app.get("/order/{order_id}", include_in_schema=False)
def web_order_detail(order_id: int):
    # HTML page that fetches /orders/{id} JSON and renders it (human-friendly).
    # Now supports inline edit + Save for a small set of fields.
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>BYP Ops — Order {order_id}</title>
  <style>
    :root {{ color-scheme: light; }}
    body {{
      font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
      margin: 16px;
      max-width: 1100px;
    }}
    h1 {{ margin: 0 0 8px 0; font-size: 22px; }}
    h2 {{ margin: 0 0 10px 0; font-size: 16px; }}
    .bar {{
      display:flex; gap:10px; align-items:center; flex-wrap:wrap;
      margin: 10px 0 14px 0;
    }}
    a {{ color: inherit; }}
    button {{
      padding: 8px 12px; border: 1px solid #888; border-radius: 10px;
      background: #f4f4f4; cursor: pointer;
    }}
    button:active {{ transform: translateY(1px); }}
    button:disabled {{
      opacity: 0.5;
      cursor: not-allowed;
    }}
    .muted {{ color: #666; font-size: 13px; }}
    .ok {{ color: #0a7b27; font-weight: 700; }}
    .err {{ color: #b00020; font-weight: 700; white-space: pre-wrap; }}
    .grid {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
    }}
    @media (max-width: 900px) {{
      .grid {{ grid-template-columns: 1fr; }}
    }}
    .card {{
      border: 1px solid #ddd; border-radius: 12px; padding: 12px;
      background: #fff;
    }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{
      padding: 8px; border-bottom: 1px solid #eee;
      text-align: left; vertical-align: top;
    }}
    th {{
      width: 220px; font-size: 12px; color: #444; user-select: none;
    }}
    td {{ font-size: 14px; }}
    .pill {{
      display:inline-block; padding: 2px 8px; border-radius: 999px;
      border: 1px solid #ccc; font-size: 12px;
    }}
    pre {{
      margin: 0; white-space: pre-wrap; word-break: break-word;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
      font-size: 12px;
    }}
    details summary {{ cursor: pointer; }}

    /* Parent display copy widget */
    .copywrap {{
      display:flex; gap:8px; align-items:center; flex-wrap:wrap;
    }}
    .copywrap input {{
      width: min(520px, 100%);
      padding: 8px 10px;
      border: 1px solid #ccc;
      border-radius: 10px;
      font-size: 14px;
      background: #fff;
    }}

    /* Inline edit controls */
    .editbox {{
      width: min(520px, 100%);
      padding: 8px 10px;
      border: 1px solid #ccc;
      border-radius: 10px;
      font-size: 14px;
      background: #fff;
      font-family: inherit;
    }}
    textarea.editbox {{
      min-height: 90px;
      resize: vertical;
      font-family: inherit;
    }}
    .hint {{
      font-size: 12px;
      color: #666;
      margin-top: 6px;
    }}
  </style>
</head>
<body>
  <h1>Order <span class="pill">{order_id}</span></h1>

  <div class="bar">
    <button id="backBtn">← Back</button>
    <a class="muted" href="/orders/{order_id}" target="_blank" rel="noopener">Open JSON</a>

    <span class="muted">Parent:</span>
    <span class="copywrap">
      <input id="parentDisplay" type="text" readonly value="" placeholder="(none)" />
      <button id="copyParentBtn" type="button">Copy</button>
    </span>

    <button id="saveBtn" type="button" disabled>Save</button>
    <button id="resetBtn" type="button" disabled>Reset</button>

    <span id="status" class="muted">Loading…</span>
    <span id="ok" class="ok"></span>
    <span id="error" class="err"></span>
  </div>

  <div class="grid">
    <div class="card">
      <h2>Order</h2>
      <table><tbody id="orderRows"></tbody></table>
      <div class="hint">Editable here: <b>Notes</b></div>
    </div>

    <div class="card">
      <h2>SP</h2>
      <table><tbody id="spRows"></tbody></table>
    </div>

    <div class="card">
      <h2>Client</h2>
      <table><tbody id="clientRows"></tbody></table>
      <div class="hint">Editable here: <b>Client Name</b>, <b>Client Company</b></div>
    </div>

    <div class="card">
      <h2>Rep</h2>
      <table><tbody id="repRows"></tbody></table>
    </div>
  </div>

  <div class="card" style="margin-top:12px;">
    <details>
      <summary class="muted">Raw JSON (for when something looks wrong)</summary>
      <pre id="rawJson"></pre>
    </details>
  </div>

  <script>
    (() => {{
      const ORDER_ID = {order_id};

      const statusEl = document.getElementById("status");
      const okEl = document.getElementById("ok");
      const errEl = document.getElementById("error");

      const saveBtn = document.getElementById("saveBtn");
      const resetBtn = document.getElementById("resetBtn");

      const orderRows = document.getElementById("orderRows");
      const spRows = document.getElementById("spRows");
      const clientRows = document.getElementById("clientRows");
      const repRows = document.getElementById("repRows");
      const rawJsonEl = document.getElementById("rawJson");

      const parentInput = document.getElementById("parentDisplay");
      const copyBtn = document.getElementById("copyParentBtn");

      // Editable inputs
      let notesInput = null;
      let clientNameInput = null;
      let clientCompanyInput = null;

      // Track last-loaded values so we can enable Save only when dirty
      let baseline = {{
        notes: "",
        client_name: "",
        client_company_name: ""
      }};

      let isSaving = false;

      document.getElementById("backBtn").addEventListener("click", () => {{
        // Always go to main search (and force refresh so new/edited orders show immediately).
        window.location.href = "/?refresh=1";
      }});

      function esc(s) {{
        return String(s ?? "")
          .replace(/&/g, "&amp;")
          .replace(/</g, "&lt;")
          .replace(/>/g, "&gt;")
          .replace(/"/g, "&quot;")
          .replace(/'/g, "&#039;");
      }}

      function getVal(obj, path) {{
        if (!obj) return undefined;
        const parts = path.split(".");
        let cur = obj;
        for (const p of parts) {{
          if (cur == null) return undefined;
          cur = cur[p];
        }}
        return cur;
      }}

      function addRow(tbody, label, value) {{
        const tr = document.createElement("tr");
        const th = document.createElement("th");
        th.textContent = label;

        const td = document.createElement("td");
        if (value === null || value === undefined || value === "") {{
          td.innerHTML = "<span class='muted'>(blank)</span>";
        }} else if (typeof value === "object") {{
          td.innerHTML = "<pre>" + esc(JSON.stringify(value, null, 2)) + "</pre>";
        }} else {{
          td.innerHTML = "<span>" + esc(value) + "</span>";
        }}

        tr.appendChild(th);
        tr.appendChild(td);
        tbody.appendChild(tr);
      }}

      function addInputRow(tbody, label, id, kind) {{
        const tr = document.createElement("tr");

        const th = document.createElement("th");
        th.textContent = label;

        const td = document.createElement("td");
        let input;
        if (kind === "textarea") {{
          input = document.createElement("textarea");
        }} else {{
          input = document.createElement("input");
          input.type = "text";
        }}
        input.id = id;
        input.className = "editbox";
        td.appendChild(input);

        tr.appendChild(th);
        tr.appendChild(td);
        tbody.appendChild(tr);

        return input;
      }}

      function renderSection(tbody, data, fields) {{
        tbody.innerHTML = "";
        for (const f of fields) {{
          const val = getVal(data, f.key);
          addRow(tbody, f.label, val);
        }}
      }}

      function computeParentDisplay(data) {{
        // Prefer server-provided parent_display (FM-style). Fallback to derive from sp.*.
        const direct = data?.parent_display;
        if (direct) return direct;

        const sp = data?.sp;
        const rev = sp?.revision_of;
        if (rev) return "Revision of " + rev;

        const addl = sp?.additional_version_of;
        if (addl) return "Add'l vers of " + addl;

        return "";
      }}

      async function copyText(text) {{
        if (!text) return;
        try {{
          if (navigator.clipboard && navigator.clipboard.writeText) {{
            await navigator.clipboard.writeText(text);
            return true;
          }}
        }} catch (e) {{
          // fall through
        }}
        try {{
          const tmp = document.createElement("textarea");
          tmp.value = text;
          tmp.style.position = "fixed";
          tmp.style.left = "-9999px";
          document.body.appendChild(tmp);
          tmp.focus();
          tmp.select();
          document.execCommand("copy");
          document.body.removeChild(tmp);
          return true;
        }} catch (e) {{
          return false;
        }}
      }}

      function wireCopyWidget() {{
        const selectAll = () => {{
          parentInput.focus();
          parentInput.select();
          // iOS Safari needs this sometimes; harmless elsewhere.
          parentInput.setSelectionRange(0, parentInput.value.length);
        }};

        parentInput.addEventListener("focus", () => {{
          if (parentInput.value) {{
            selectAll();
          }}
        }});

        parentInput.addEventListener("click", async () => {{
          if (!parentInput.value) return;
          selectAll();
          await copyText(parentInput.value);
        }});

        copyBtn.addEventListener("click", async () => {{
          if (!parentInput.value) return;
          selectAll();
          await copyText(parentInput.value);
        }});
      }}

      function normalize(s) {{
        return String(s ?? "");
      }}

      function getDraft() {{
        return {{
          notes: normalize(notesInput?.value),
          client_name: normalize(clientNameInput?.value),
          client_company_name: normalize(clientCompanyInput?.value)
        }};
      }}

      function setDraftFromBaseline() {{
        if (notesInput) notesInput.value = baseline.notes;
        if (clientNameInput) clientNameInput.value = baseline.client_name;
        if (clientCompanyInput) clientCompanyInput.value = baseline.client_company_name;
      }}

      function isDirty() {{
        const d = getDraft();
        return (
          d.notes !== baseline.notes ||
          d.client_name !== baseline.client_name ||
          d.client_company_name !== baseline.client_company_name
        );
      }}

      function refreshDirtyUI() {{
        const dirty = isDirty();
        // Save should always be allowed (even if nothing changed) so users can "save as is".
        saveBtn.disabled = !!isSaving;
        resetBtn.disabled = !!isSaving ? true : !dirty;
      }}

      async function save() {{
        try {{
          okEl.textContent = "";
          errEl.textContent = "";
          statusEl.textContent = "Saving…";
          isSaving = true;
          refreshDirtyUI();

          const d = getDraft();
          const payload = {{
            notes: d.notes,
            client_name: d.client_name,
            client_company_name: d.client_company_name
          }};

          const res = await fetch("/orders/" + ORDER_ID, {{
            method: "PATCH",
            headers: {{
              "Content-Type": "application/json"
            }},
            body: JSON.stringify(payload)
          }});

          const text = await res.text();

          if (!res.ok) {{
            statusEl.textContent = "";
            errEl.textContent = "HTTP " + res.status + "\\n" + text;
            isSaving = false;
            refreshDirtyUI();
            return;
          }}

          okEl.textContent = "Saved.";
          // Reload to show updated_at + any server-side normalization
          await load();
          isSaving = false;
          refreshDirtyUI();
        }} catch (e) {{
          statusEl.textContent = "";
          errEl.textContent = String(e);
          isSaving = false;
          refreshDirtyUI();
        }}
      }}

      saveBtn.addEventListener("click", save);

      resetBtn.addEventListener("click", () => {{
        okEl.textContent = "";
        errEl.textContent = "";
        setDraftFromBaseline();
        refreshDirtyUI();
      }});

      async function load() {{
        try {{
          okEl.textContent = "";
          errEl.textContent = "";
          statusEl.textContent = "Fetching…";

          const res = await fetch("/orders/" + ORDER_ID);
          const text = await res.text();

          if (!res.ok) {{
            statusEl.textContent = "";
            errEl.textContent = "HTTP " + res.status + "\\n" + text;
            return;
          }}

          const data = JSON.parse(text);
          rawJsonEl.textContent = JSON.stringify(data, null, 2);

          // Parent display (copy/paste weapon)
          const parentDisplay = computeParentDisplay(data);
          parentInput.value = parentDisplay || "";
          parentInput.placeholder = parentDisplay ? "" : "(none)";
          copyBtn.disabled = !parentDisplay;

          // ----- Order section (Notes editable) -----
          orderRows.innerHTML = "";
          addRow(orderRows, "ID", data.id);
          addRow(orderRows, "Artist", data.artist);
          addRow(orderRows, "Asset Type", data.asset_type);
          addRow(orderRows, "Status", data.status);

          notesInput = addInputRow(orderRows, "Notes", "editNotes", "textarea");

          addRow(orderRows, "Deleted?", data.is_deleted);
          addRow(orderRows, "Created", data.created_at);
          addRow(orderRows, "Updated", data.updated_at);

          // ----- SP section -----
          // Supports either nested sp.* or flat sp_* fields
          const spObj = (data && typeof data.sp === "object") ? data : {{
            sp: {{
              sp_number: data.sp_number,
              order_type: data.sp_order_type || data.order_type,
              revision_of: data.sp_revision_of || data.revision_of,
              additional_version_of: data.additional_version_of,
            }}
          }};

          renderSection(spRows, spObj, [
            {{ label: "SP Number", key: "sp.sp_number" }},
            {{ label: "Order Type", key: "sp.order_type" }},
            {{ label: "Revision Of", key: "sp.revision_of" }},
            {{ label: "Add'l Vers Of", key: "sp.additional_version_of" }},
          ]);

          // ----- Client section (editable fields first) -----
          clientRows.innerHTML = "";
          clientNameInput = addInputRow(clientRows, "Client Name", "editClientName", "text");
          clientCompanyInput = addInputRow(clientRows, "Client Company", "editClientCompany", "text");
          addRow(clientRows, "Client Email", data.client_email);
          addRow(clientRows, "Client Phone", data.client_phone);

          // ----- Rep section -----
          renderSection(repRows, data, [
            {{ label: "Rep Code", key: "rep_code" }},
            {{ label: "Rep Name", key: "rep_name" }},
          ]);

          // Baseline values
          baseline = {{
            notes: normalize(data.notes),
            client_name: normalize(data.client_name),
            client_company_name: normalize(data.client_company_name)
          }};
          setDraftFromBaseline();

          // Wire dirty tracking
          const onChange = () => {{
            okEl.textContent = "";
            refreshDirtyUI();
          }};
          notesInput.addEventListener("input", onChange);
          clientNameInput.addEventListener("input", onChange);
          clientCompanyInput.addEventListener("input", onChange);

          refreshDirtyUI();
          statusEl.textContent = "Loaded.";
        }} catch (e) {{
          statusEl.textContent = "";
          errEl.textContent = String(e);
        }}
      }}

      wireCopyWidget();
      load();
    }})();
  </script>
</body>
</html>
"""
    return HTMLResponse(content=html)


@app.get("/health")
def health():
    return {"status": "BYP Ops backend online"}
