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
    # Read-only HTML page that fetches /orders/{id} JSON and renders it (human-friendly).
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
    .muted {{ color: #666; font-size: 13px; }}
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
  </style>
</head>
<body>
  <h1>Order <span class="pill">{order_id}</span></h1>

  <div class="bar">
    <button id="backBtn">← Back to Search</button>
    <a class="muted" href="/orders/{order_id}" target="_blank" rel="noopener">Open JSON</a>
    <span id="status" class="muted">Loading…</span>
    <span id="error" class="err"></span>
  </div>

  <div class="grid">
    <div class="card">
      <h2>Order</h2>
      <table><tbody id="orderRows"></tbody></table>
    </div>

    <div class="card">
      <h2>SP</h2>
      <table><tbody id="spRows"></tbody></table>
    </div>

    <div class="card">
      <h2>Client</h2>
      <table><tbody id="clientRows"></tbody></table>
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
      const errEl = document.getElementById("error");

      const orderRows = document.getElementById("orderRows");
      const spRows = document.getElementById("spRows");
      const clientRows = document.getElementById("clientRows");
      const repRows = document.getElementById("repRows");
      const rawJsonEl = document.getElementById("rawJson");

      document.getElementById("backBtn").addEventListener("click", () => {{
        // Go back to whatever search/page you came from. If there is no history, fallback to home.
        if (window.history.length > 1) {{
          window.history.back();
        }} else {{
          window.location.href = "/";
        }}
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

      function renderSection(tbody, data, fields) {{
        tbody.innerHTML = "";
        for (const f of fields) {{
          const val = getVal(data, f.key);
          addRow(tbody, f.label, val);
        }}
      }}

      async function load() {{
        try {{
          errEl.textContent = "";
          statusEl.textContent = "Fetching…";

          const res = await fetch(`/orders/${{ORDER_ID}}`);
          const text = await res.text();

          if (!res.ok) {{
            statusEl.textContent = "";
            errEl.textContent = `HTTP ${{res.status}}\n${{text}}`;
            return;
          }}

          const data = JSON.parse(text);
          rawJsonEl.textContent = JSON.stringify(data, null, 2);

          // Order fields
          renderSection(orderRows, data, [
            {{ label: "ID", key: "id" }},
            {{ label: "Artist", key: "artist" }},
            {{ label: "Asset Type", key: "asset_type" }},
            {{ label: "Status", key: "status" }},
            {{ label: "Notes", key: "notes" }},
            {{ label: "Deleted?", key: "is_deleted" }},
            {{ label: "Created", key: "created_at" }},
            {{ label: "Updated", key: "updated_at" }},
          ]);

          // SP fields (supports either nested sp.* or flat sp_* fields)
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

          // Client fields (best-effort keys)
          renderSection(clientRows, data, [
            {{ label: "Client Name", key: "client_name" }},
            {{ label: "Client Company", key: "client_company_name" }},
            {{ label: "Client Email", key: "client_email" }},
            {{ label: "Client Phone", key: "client_phone" }},
          ]);

          // Rep fields
          renderSection(repRows, data, [
            {{ label: "Rep Code", key: "rep_code" }},
            {{ label: "Rep Name", key: "rep_name" }},
          ]);

          statusEl.textContent = "Loaded.";
        }} catch (e) {{
          statusEl.textContent = "";
          errEl.textContent = String(e);
        }}
      }}

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
