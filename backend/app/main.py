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
    # Supports inline edit + Save for a small set of fields + Revise/Add'l Vers + Finalize/Unfinalize actions.
    # NOTE: Keep JS syntax conservative (avoid optional-chaining) to support older mobile browsers.
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

    <button id="finalizeBtn" type="button" disabled>Finalize</button>
    <button id="unfinalizeBtn" type="button" disabled>Unfinalize</button>

    <button id="reviseBtn" type="button" disabled>Revise</button>
    <button id="addlBtn" type="button" disabled>Add'l Vers</button>

    <span id="status" class="muted">Loading…</span>
    <span id="ok" class="ok"></span>
    <span id="error" class="err"></span>
  </div>

  <div class="grid">
    <div class="card">
      <h2>Order</h2>
      <table><tbody id="orderRows"></tbody></table>
      <div class="hint">Editable here: <b>Asset Type</b> (draft only), <b>Notes</b></div>
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
    (function() {{
      var ORDER_ID = {order_id};

      var statusEl = document.getElementById("status");
      var okEl = document.getElementById("ok");
      var errEl = document.getElementById("error");

      var saveBtn = document.getElementById("saveBtn");
      var resetBtn = document.getElementById("resetBtn");
      var finalizeBtn = document.getElementById("finalizeBtn");
      var unfinalizeBtn = document.getElementById("unfinalizeBtn");
      var reviseBtn = document.getElementById("reviseBtn");
      var addlBtn = document.getElementById("addlBtn");

      var orderRows = document.getElementById("orderRows");
      var spRows = document.getElementById("spRows");
      var clientRows = document.getElementById("clientRows");
      var repRows = document.getElementById("repRows");
      var rawJsonEl = document.getElementById("rawJson");

      var parentInput = document.getElementById("parentDisplay");
      var copyBtn = document.getElementById("copyParentBtn");

      // Editable inputs
      var assetTypeSelect = null;
      var notesInput = null;
      var clientNameInput = null;
      var clientCompanyInput = null;

      // Track last-loaded values so we can enable Save only when dirty
      var baseline = {{
        asset_type: "",
        notes: "",
        client_name: "",
        client_company_name: ""
      }};

      document.getElementById("backBtn").addEventListener("click", function() {{
        // Always go back to main search.
        window.location.href = "/";
      }});

      function esc(s) {{
        var v = (s === null || s === undefined) ? "" : String(s);
        return v
          .replace(/&/g, "&amp;")
          .replace(/</g, "&lt;")
          .replace(/>/g, "&gt;")
          .replace(/"/g, "&quot;")
          .replace(/'/g, "&#039;");
      }}

      function getVal(obj, path) {{
        if (!obj) return undefined;
        var parts = path.split(".");
        var cur = obj;
        for (var i = 0; i < parts.length; i++) {{
          if (cur === null || cur === undefined) return undefined;
          cur = cur[parts[i]];
        }}
        return cur;
      }}

      function addRow(tbody, label, value) {{
        var tr = document.createElement("tr");
        var th = document.createElement("th");
        th.textContent = label;

        var td = document.createElement("td");
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
        var tr = document.createElement("tr");

        var th = document.createElement("th");
        th.textContent = label;

        var td = document.createElement("td");
        var input;
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

      function addSelectRow(tbody, label, id, options) {{
        var tr = document.createElement("tr");

        var th = document.createElement("th");
        th.textContent = label;

        var td = document.createElement("td");

        var sel = document.createElement("select");
        sel.id = id;
        sel.className = "editbox";

        // Populate options
        for (var i = 0; i < options.length; i++) {{
          var opt = document.createElement("option");
          opt.value = options[i];
          opt.textContent = options[i];
          sel.appendChild(opt);
        }}

        td.appendChild(sel);
        tr.appendChild(th);
        tr.appendChild(td);
        tbody.appendChild(tr);

        return sel;
      }}

      function renderSection(tbody, data, fields) {{
        tbody.innerHTML = "";
        for (var i = 0; i < fields.length; i++) {{
          var f = fields[i];
          var val = getVal(data, f.key);
          addRow(tbody, f.label, val);
        }}
      }}

      function computeParentDisplay(data) {{
        // Prefer server-provided parent_display (FM-style). Fallback to derive from sp.*.
        if (data && data.parent_display) return data.parent_display;

        var sp = (data && data.sp) ? data.sp : null;
        var rev = sp ? sp.revision_of : null;
        if (rev) return "Revision of " + rev;

        var addl = sp ? sp.additional_version_of : null;
        if (addl) return "Add'l vers of " + addl;

        return "";
      }}

      function copyText(text, done) {{
        if (!text) return done(false);

        // Prefer modern clipboard API when available.
        try {{
          if (navigator.clipboard && navigator.clipboard.writeText) {{
            navigator.clipboard.writeText(text).then(function() {{
              done(true);
            }}).catch(function() {{
              legacyCopy(text, done);
            }});
            return;
          }}
        }} catch (e) {{
          // fall through
        }}
        legacyCopy(text, done);
      }}

      function legacyCopy(text, done) {{
        try {{
          var tmp = document.createElement("textarea");
          tmp.value = text;
          tmp.style.position = "fixed";
          tmp.style.left = "-9999px";
          document.body.appendChild(tmp);
          tmp.focus();
          tmp.select();
          document.execCommand("copy");
          document.body.removeChild(tmp);
          done(true);
        }} catch (e) {{
          done(false);
        }}
      }}

      function wireCopyWidget() {{
        function selectAll() {{
          parentInput.focus();
          parentInput.select();
          parentInput.setSelectionRange(0, parentInput.value.length);
        }}

        parentInput.addEventListener("focus", function() {{
          if (parentInput.value) {{
            selectAll();
          }}
        }});

        parentInput.addEventListener("click", function() {{
          if (!parentInput.value) return;
          selectAll();
          copyText(parentInput.value, function(){{}});
        }});

        copyBtn.addEventListener("click", function() {{
          if (!parentInput.value) return;
          selectAll();
          copyText(parentInput.value, function(){{}});
        }});
      }}

      function normalize(s) {{
        return (s === null || s === undefined) ? "" : String(s);
      }}

      function getDraft() {{
        return {{
          asset_type: normalize(assetTypeSelect ? assetTypeSelect.value : ""),
          notes: normalize(notesInput ? notesInput.value : ""),
          client_name: normalize(clientNameInput ? clientNameInput.value : ""),
          client_company_name: normalize(clientCompanyInput ? clientCompanyInput.value : "")
        }};
      }}

      function setDraftFromBaseline() {{
        if (assetTypeSelect) assetTypeSelect.value = baseline.asset_type;
        if (notesInput) notesInput.value = baseline.notes;
        if (clientNameInput) clientNameInput.value = baseline.client_name;
        if (clientCompanyInput) clientCompanyInput.value = baseline.client_company_name;
      }}

      function isDirty() {{
        var d = getDraft();
        return (
          d.asset_type !== baseline.asset_type ||
          d.notes !== baseline.notes ||
          d.client_name !== baseline.client_name ||
          d.client_company_name !== baseline.client_company_name
        );
      }}

      function refreshDirtyUI() {{
        var dirty = isDirty();
        saveBtn.disabled = !dirty;
        resetBtn.disabled = !dirty;
      }}

      function setBusy(msg) {{
        statusEl.textContent = msg || "";
      }}

      function clearMsgs() {{
        okEl.textContent = "";
        errEl.textContent = "";
      }}

      function setActionsDisabled(disabled) {{
        reviseBtn.disabled = disabled || reviseBtn.disabled;
        addlBtn.disabled = disabled || addlBtn.disabled;
        finalizeBtn.disabled = disabled || finalizeBtn.disabled;
        unfinalizeBtn.disabled = disabled || unfinalizeBtn.disabled;
      }}

      function save() {{
        clearMsgs();
        setBusy("Saving…");
        saveBtn.disabled = true;

        var d = getDraft();
        var payload = {{
          notes: d.notes,
          client_name: d.client_name,
          client_company_name: d.client_company_name
        }};

        // Only send asset_type when it actually changed (avoids 400s on finalized orders).
        if (d.asset_type !== baseline.asset_type) {{
          payload.asset_type = d.asset_type;
        }}

        fetch("/orders/" + ORDER_ID, {{
          method: "PATCH",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify(payload)
        }})
        .then(function(res) {{
          return res.text().then(function(text) {{
            if (!res.ok) {{
              setBusy("");
              errEl.textContent = "HTTP " + res.status + "\\n" + text;
              refreshDirtyUI();
              return null;
            }}
            okEl.textContent = "Saved.";
            return true;
          }});
        }})
        .then(function(ok) {{
          if (ok) load(); // reload to show updated_at + any server-side normalization
        }})
        .catch(function(e) {{
          setBusy("");
          errEl.textContent = String(e);
          refreshDirtyUI();
        }});
      }}

      saveBtn.addEventListener("click", save);

      resetBtn.addEventListener("click", function() {{
        clearMsgs();
        setDraftFromBaseline();
        refreshDirtyUI();
      }});

      function postAndGo(path) {{
        clearMsgs();
        setBusy("Working…");
        reviseBtn.disabled = true;
        addlBtn.disabled = true;
        finalizeBtn.disabled = true;
        unfinalizeBtn.disabled = true;

        fetch(path, {{ method: "POST" }})
          .then(function(res) {{
            return res.text().then(function(text) {{
              if (!res.ok) {{
                setBusy("");
                errEl.textContent = "HTTP " + res.status + "\\n" + text;
                return null;
              }}
              try {{
                return JSON.parse(text);
              }} catch (e) {{
                setBusy("");
                errEl.textContent = "Bad JSON response\\n" + text;
                return null;
              }}
            }});
          }})
          .then(function(data) {{
            if (!data || !data.id) return;
            // Replace so browser Back goes to search, not back to this order.
            window.location.replace("/order/" + data.id);
          }})
          .catch(function(e) {{
            setBusy("");
            errEl.textContent = String(e);
          }});
      }}

      function postAndReload(path, okMsg) {{
        clearMsgs();
        setBusy("Working…");
        reviseBtn.disabled = true;
        addlBtn.disabled = true;
        finalizeBtn.disabled = true;
        unfinalizeBtn.disabled = true;

        fetch(path, {{ method: "POST" }})
          .then(function(res) {{
            return res.text().then(function(text) {{
              if (!res.ok) {{
                setBusy("");
                errEl.textContent = "HTTP " + res.status + "\\n" + text;
                return null;
              }}
              okEl.textContent = okMsg || "Done.";
              return true;
            }});
          }})
          .then(function(ok) {{
            if (ok) load();
          }})
          .catch(function(e) {{
            setBusy("");
            errEl.textContent = String(e);
          }});
      }}

      reviseBtn.addEventListener("click", function() {{
        postAndGo("/orders/" + ORDER_ID + "/revise");
      }});

      addlBtn.addEventListener("click", function() {{
        postAndGo("/orders/" + ORDER_ID + "/addl_vers");
      }});

      finalizeBtn.addEventListener("click", function() {{
        postAndReload("/orders/" + ORDER_ID + "/finalize", "Finalized.");
      }});

      unfinalizeBtn.addEventListener("click", function() {{
        postAndReload("/orders/" + ORDER_ID + "/unfinalize", "Unfinalized.");
      }});

      function load() {{
        clearMsgs();
        setBusy("Fetching…");

        fetch("/orders/" + ORDER_ID)
          .then(function(res) {{
            return res.text().then(function(text) {{
              if (!res.ok) {{
                setBusy("");
                errEl.textContent = "HTTP " + res.status + "\\n" + text;
                return null;
              }}
              try {{
                return JSON.parse(text);
              }} catch (e) {{
                setBusy("");
                errEl.textContent = "Bad JSON\\n" + text;
                return null;
              }}
            }});
          }})
          .then(function(data) {{
            if (!data) return;

            rawJsonEl.textContent = JSON.stringify(data, null, 2);

            // Parent display (copy/paste weapon)
            var parentDisplay = computeParentDisplay(data);
            parentInput.value = parentDisplay || "";
            parentInput.placeholder = parentDisplay ? "" : "(none)";
            copyBtn.disabled = !parentDisplay;

            // ----- Order section (Notes editable) -----
            orderRows.innerHTML = "";
            addRow(orderRows, "ID", data.id);
            addRow(orderRows, "Artist", data.artist);
            // Asset Type (editable only when draft)
            var at = normalize(data.asset_type).toLowerCase();
            var assetOptions = ["radio", "video", "art", "longform", "other"];
            // Ensure current value is present even if it's not in our known list.
            if (at && assetOptions.indexOf(at) === -1) {{
              assetOptions.unshift(at);
            }}
            assetTypeSelect = addSelectRow(orderRows, "Asset Type", "editAssetType", assetOptions);
            assetTypeSelect.value = at || "";

            addRow(orderRows, "Status", data.status);

            notesInput = addInputRow(orderRows, "Notes", "editNotes", "textarea");

            addRow(orderRows, "Deleted?", data.is_deleted);
            addRow(orderRows, "Created", data.created_at);
            addRow(orderRows, "Updated", data.updated_at);

            // ----- SP section -----
            var spObj;
            if (data && typeof data.sp === "object" && data.sp) {{
              spObj = data;
            }} else {{
              spObj = {{
                sp: {{
                  sp_number: data.sp_number,
                  order_type: data.sp_order_type || data.order_type,
                  revision_of: data.sp_revision_of || data.revision_of,
                  additional_version_of: data.additional_version_of
                }}
              }};
            }}

            renderSection(spRows, spObj, [
              {{ label: "SP Number", key: "sp.sp_number" }},
              {{ label: "Order Type", key: "sp.order_type" }},
              {{ label: "Revision Of", key: "sp.revision_of" }},
              {{ label: "Add'l Vers Of", key: "sp.additional_version_of" }}
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
              {{ label: "Rep Name", key: "rep_name" }}
            ]);

            // Baseline values
            baseline = {{
              asset_type: normalize(data.asset_type).toLowerCase(),
              notes: normalize(data.notes),
              client_name: normalize(data.client_name),
              client_company_name: normalize(data.client_company_name)
            }};
            setDraftFromBaseline();

            // Wire dirty tracking
            function onChange() {{
              okEl.textContent = "";
              refreshDirtyUI();
            }}
            if (assetTypeSelect) assetTypeSelect.addEventListener("change", onChange);
            notesInput.addEventListener("input", onChange);
            clientNameInput.addEventListener("input", onChange);
            clientCompanyInput.addEventListener("input", onChange);

            // Enable action buttons once we know the order exists
            reviseBtn.disabled = false;
            addlBtn.disabled = false;

            // Asset Type editable only when draft
            var isDraft = false;
            if (data && data.status) {{
              var ds = String(data.status).toLowerCase();
              if (ds.indexOf("draft") >= 0) isDraft = true;
            }}
            if (assetTypeSelect) {{
              assetTypeSelect.disabled = !isDraft;
            }}

            // Finalize/Unfinalize: best-effort based on finalized_at or status text
            var isFinal = false;
            if (data && data.finalized_at) {{
              isFinal = true;
            }} else if (data && data.status) {{
              var s = String(data.status).toLowerCase();
              if (s.indexOf("final") >= 0) isFinal = true;
            }}

            finalizeBtn.disabled = isFinal;
            unfinalizeBtn.disabled = !isFinal;

            refreshDirtyUI();
            setBusy("Loaded.");
          }})
          .catch(function(e) {{
            setBusy("");
            errEl.textContent = String(e);
          }});
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
