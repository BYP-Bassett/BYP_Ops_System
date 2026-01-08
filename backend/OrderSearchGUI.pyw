# OrderSearchGUI.pyw
# Orders Search + Details GUI for BYP Ops FastAPI backend
# - Search orders
# - Open details
# - Create Revision / Add'l Version
# - Finalize / Override Edit / Save
# - Delete with initials (double speed bump for finalized)

from __future__ import annotations

import json
import os
import threading
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API_BASE = "http://127.0.0.1:8000"
ASSET_TYPES = ["radio", "video", "art"]

# Rep display rules:
# - API/DB stores FULL strings (e.g., "SB - Steve Bassett")
# - Search grid shows INITIALS only (e.g., "SB")
# - Order dropdown shows FULL strings
REP_FULL = [
    "SB - Steve Bassett",
    "RM - Ron Mewis",
    "AML - Allison Lineberry",
    "JS - Jon Shults",
    "CD - Celine DeLeon",
]

# Rep codes for dropdown filtering in the search window
REP_CODES = [((r or '').strip().split() or [''])[0] for r in REP_FULL]

def rep_initials(rep_full: str) -> str:
    s = (rep_full or "").strip()
    if not s:
        return ""
    # Typical: "SB - Steve Bassett" or "SB = Steve Bassett"
    # Grab the token before the first space/delimiter.
    for delim in ("-", "=", "—"):
        if delim in s:
            return s.split(delim, 1)[0].strip()
    return s.split()[0].strip()

def _prefs_path() -> str:
    """Path to persisted UI prefs (column widths/order) stored next to this script."""
    try:
        base = os.path.dirname(os.path.abspath(__file__))
    except Exception:
        base = os.getcwd()
    return os.path.join(base, "OrderSearchGUI_prefs.json")



# -----------------------------
# HTTP helpers
# -----------------------------
def _read_json_response(resp):
    raw = resp.read().decode("utf-8", errors="replace")
    return json.loads(raw) if raw else {}


def http_get_json(url: str, timeout: int = 10) -> dict:
    req = Request(url, headers={"Accept": "application/json"})
    with urlopen(req, timeout=timeout) as resp:
        return _read_json_response(resp)


def http_send_json(method: str, url: str, payload: dict | None, timeout: int = 15) -> dict:
    headers = {"Accept": "application/json"}
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = Request(url, data=data, headers=headers, method=method)
    with urlopen(req, timeout=timeout) as resp:
        return _read_json_response(resp)


def http_post_json(url: str, payload: dict | None = None, timeout: int = 15) -> dict:
    return http_send_json("POST", url, payload, timeout=timeout)


def http_patch_json(url: str, payload: dict, timeout: int = 15) -> dict:
    return http_send_json("PATCH", url, payload, timeout=timeout)


def http_delete_json(url: str, timeout: int = 15) -> dict:
    return http_send_json("DELETE", url, payload=None, timeout=timeout)


# -----------------------------
# Dialogs
# -----------------------------
class FinalizeDialog(tk.Toplevel):
    def __init__(self, parent, order_id: int):
        super().__init__(parent)
        self.parent = parent
        self.order_id = order_id

        self.title("Finalize Order (link Trello)")
        self.geometry("540x220")
        self.resizable(False, False)

        self._build_ui()

    def _build_ui(self):
        frm = ttk.Frame(self)
        frm.pack(fill="both", expand=True, padx=12, pady=12)

        ttk.Label(frm, text="Trello Card ID").grid(row=0, column=0, sticky="w")
        self.card_var = tk.StringVar()
        ttk.Entry(frm, textvariable=self.card_var, width=46).grid(row=0, column=1, sticky="w")

        ttk.Label(frm, text="Checklist ID").grid(row=1, column=0, sticky="w", pady=(10, 0))
        self.chk_var = tk.StringVar()
        ttk.Entry(frm, textvariable=self.chk_var, width=46).grid(row=1, column=1, sticky="w", pady=(10, 0))

        self.status_var = tk.StringVar(value="Paste the IDs from the Trello card/checklist for this order.")
        ttk.Label(frm, textvariable=self.status_var, wraplength=500).grid(row=2, column=0, columnspan=2, sticky="w", pady=(10, 0))

        btns = ttk.Frame(self)
        btns.pack(fill="x", padx=12, pady=(0, 12))

        self.ok_btn = ttk.Button(btns, text="Finalize", command=self.on_finalize)
        self.ok_btn.pack(side="left")

        ttk.Button(btns, text="Cancel", command=self.destroy).pack(side="left", padx=(10, 0))

    def on_finalize(self):
        card = (self.card_var.get() or "").strip()
        chk = (self.chk_var.get() or "").strip()
        if not card or not chk:
            messagebox.showerror("Missing data", "Both Trello Card ID and Checklist ID are required.")
            return

        self.ok_btn.configure(state="disabled")
        self.status_var.set("Finalizing…")

        def worker():
            try:
                qs = urlencode({"trello_card_id": card, "trello_checklist_id": chk})
                http_post_json(f"{API_BASE}/orders/{self.order_id}/finalize?{qs}", payload=None, timeout=25)
                self.after(0, self._done)
            except HTTPError as e:
                self.after(0, lambda: self._fail(_http_error_to_message(e)))
            except Exception as e:
                self.after(0, lambda: self._fail(str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def _done(self):
        self.destroy()
        if hasattr(self.parent, "refresh"):
            self.parent.refresh()

    def _fail(self, msg: str):
        self.ok_btn.configure(state="normal")
        self.status_var.set("Failed.")
        messagebox.showerror("Finalize failed", msg)


class NewOrderDialog(tk.Toplevel):
    def __init__(self, parent, prefill: dict | None = None):
        super().__init__(parent)
        self.parent = parent
        self.prefill = prefill or {}

        self.title("Create New Order")
        self.geometry("780x520")
        self.resizable(True, True)

        self._build_ui()
        self._apply_prefill()

    def _build_ui(self):
        top = ttk.Frame(self)
        top.pack(fill="x", padx=10, pady=8)

        self.status_var = tk.StringVar(value="Ready.")
        ttk.Label(top, textvariable=self.status_var).pack(side="left")

        form = ttk.Frame(self)
        form.pack(fill="x", padx=10)

        ttk.Label(form, text="Artist").grid(row=0, column=0, sticky="w")
        self.artist_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.artist_var, width=44).grid(row=0, column=1, sticky="w", padx=(0, 18))

        ttk.Label(form, text="Asset Type").grid(row=0, column=2, sticky="w")
        self.asset_var = tk.StringVar()
        ttk.Combobox(form, textvariable=self.asset_var, values=ASSET_TYPES, width=12, state="readonly").grid(row=0, column=3, sticky="w")

        ttk.Label(form, text="Client Name").grid(row=1, column=0, sticky="w", pady=(10, 0))
        self.client_name_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.client_name_var, width=28).grid(row=1, column=1, sticky="w", padx=(0, 18), pady=(10, 0))

        ttk.Label(form, text="Client Company").grid(row=1, column=2, sticky="w", pady=(10, 0))
        self.client_company_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.client_company_var, width=34).grid(row=1, column=3, sticky="w", pady=(10, 0))

        ttk.Label(form, text="Rep").grid(row=2, column=0, sticky="w", pady=(10, 0))
        self.rep_var = tk.StringVar(value=REP_FULL[0])
        ttk.Combobox(
            form,
            textvariable=self.rep_var,
            values=REP_FULL,
            width=44,
            state="readonly",
        ).grid(row=2, column=1, columnspan=3, sticky="w", pady=(10, 0))
        notes_frame = ttk.Frame(self)
        notes_frame.pack(fill="both", expand=True, padx=10, pady=(10, 10))
        ttk.Label(notes_frame, text="Notes").pack(anchor="w")
        self.notes_text = tk.Text(notes_frame, height=12, wrap="word")
        self.notes_text.pack(fill="both", expand=True)

        btns = ttk.Frame(self)
        btns.pack(fill="x", padx=10, pady=(0, 10))
        self.create_btn = ttk.Button(btns, text="Create", command=self.on_create)
        self.create_btn.pack(side="left")
        ttk.Button(btns, text="Cancel", command=self.destroy).pack(side="left", padx=(10, 0))

    def _apply_prefill(self):
        self.artist_var.set((self.prefill.get("artist") or "").strip())
        asset = (self.prefill.get("asset_type") or "radio").strip().lower()
        if asset not in ("radio", "video", "art"):
            asset = "radio"
        self.asset_var.set(asset)
        self.client_name_var.set((self.prefill.get("client_name") or "").strip())
        self.client_company_var.set((self.prefill.get("client_company_name") or "").strip())
        rep = (self.prefill.get("rep_name") or "").strip()
        self.rep_var.set(rep if rep in REP_FULL else REP_FULL[0])
        self.notes_text.delete("1.0", "end")
        self.notes_text.insert("1.0", "")

    def on_create(self):
        artist = (self.artist_var.get() or "").strip()
        asset = (self.asset_var.get() or "").strip().lower()
        if not artist:
            messagebox.showerror("Missing data", "Artist is required.")
            return
        if asset not in ("radio", "video", "art"):
            messagebox.showerror("Missing data", "Asset Type must be radio, video, or art.")
            return

        payload = {
            "artist": artist,
            "asset_type": asset,
            "notes": (self.notes_text.get("1.0", "end") or "").strip(),
            "rep_name": (self.rep_var.get() or REP_FULL[0]).strip(),
        }
        cn = (self.client_name_var.get() or "").strip()
        cco = (self.client_company_var.get() or "").strip()
        if cn:
            payload["client_name"] = cn
        if cco:
            payload["client_company_name"] = cco

        self.create_btn.configure(state="disabled")
        self.status_var.set("Creating…")

        def worker():
            try:
                created = http_post_json(f"{API_BASE}/orders/new", payload=payload, timeout=20)
                self.after(0, lambda: self._done(created))
            except HTTPError as e:
                self.after(0, lambda: self._fail(_http_error_to_message(e)))
            except URLError as e:
                self.after(0, lambda: self._fail(f"Connection error: {e}"))
            except Exception as e:
                self.after(0, lambda: self._fail(str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def _done(self, created: dict):
        self.create_btn.configure(state="normal")
        oid = created.get("id")
        if not oid:
            messagebox.showerror("Created, but…", "Order created but no id returned.")
            return
        OrderDetailsWindow(self.parent, int(oid))
        self.destroy()

    def _fail(self, msg: str):
        self.create_btn.configure(state="normal")
        self.status_var.set("Failed.")
        messagebox.showerror("Create failed", msg)


# -----------------------------
# Helpers
# -----------------------------
def _http_error_to_message(e: HTTPError) -> str:
    try:
        body = e.read().decode("utf-8", errors="replace")
    except Exception:
        body = str(e)
    return f"HTTP {e.code}: {body}"


def _safe_get(d: dict, *keys, default=None):
    cur = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


# -----------------------------
# Details window
# -----------------------------
class OrderDetailsWindow(tk.Toplevel):
    def __init__(self, parent, order_id: int):
        super().__init__(parent)
        self.parent = parent
        self.order_id = order_id
        self.order_data: dict | None = None
        self._override_mode = False
        self._asset_type_editable = False

        self.title(f"Order {order_id}")
        self.geometry("980x760")

        self._build_ui()
        self.refresh()

    def _build_ui(self):
        header = ttk.Frame(self)
        header.pack(fill="x", padx=10, pady=8)

        self.title_var = tk.StringVar(value="(loading…)")
        ttk.Label(header, textvariable=self.title_var, font=("Segoe UI", 12, "bold")).pack(side="left")

        self.status_var = tk.StringVar(value="")
        ttk.Label(header, textvariable=self.status_var).pack(side="right")

        actions = ttk.Frame(self)
        actions.pack(fill="x", padx=10, pady=(0, 8))

        ttk.Button(actions, text="Refresh", command=self.refresh).pack(side="left")

        ttk.Separator(actions, orient="vertical").pack(side="left", fill="y", padx=10)

        ttk.Button(actions, text="New", command=self.on_new).pack(side="left")
        ttk.Button(actions, text="Add'l Vers Of", command=self.on_addl_vers).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Duplicate", command=self.on_duplicate).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Revision Of", command=self.on_revision_of).pack(side="left", padx=(8, 0))

        ttk.Separator(actions, orient="vertical").pack(side="left", fill="y", padx=10)

        self.delete_btn = ttk.Button(actions, text="Delete…", command=self.on_delete)
        self.delete_btn.pack(side="left")

        ttk.Separator(actions, orient="vertical").pack(side="left", fill="y", padx=10)

        self.edit_btn = ttk.Button(actions, text="Override Edit…", command=self.on_override_edit)
        self.edit_btn.pack(side="left")

        self.save_btn = ttk.Button(actions, text="Save", command=self.on_save)
        self.save_btn.pack(side="left", padx=(8, 0))

        self.finalize_btn = ttk.Button(actions, text="Finalize", command=self.on_finalize)
        self.finalize_btn.pack(side="left", padx=(8, 0))

        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=10, pady=(0, 8))

        body = ttk.Frame(self)
        body.pack(fill="x", padx=10)

        self.vars: dict[str, tuple[tk.StringVar, ttk.Widget]] = {}

        def add_row(row, col, label, width=38):
            ttk.Label(body, text=label).grid(row=row, column=col, sticky="w", pady=(0, 4))
            v = tk.StringVar(value="")
            if label == "Asset Type":
                e = ttk.Combobox(body, textvariable=v, values=ASSET_TYPES, width=width, state="disabled")
            else:
                e = ttk.Entry(body, textvariable=v, width=width)
            e.grid(row=row + 1, column=col, sticky="w", padx=(0, 16), pady=(0, 10))
            self.vars[label] = (v, e)

        add_row(0, 0, "Artist", 46)
        add_row(0, 1, "Asset Type", 18)
        add_row(0, 2, "SP Number", 18)

        add_row(2, 0, "Client Name", 30)
        add_row(2, 1, "Client Company", 34)
        add_row(2, 2, "Revision Of", 22)

        add_row(4, 0, "Add'l Vers Of", 22)
        add_row(4, 1, "Status", 18)
        add_row(4, 2, "Trello Card ID", 34)

        add_row(6, 2, "Checklist ID", 34)

        # Rep (full names shown here; search grid shows initials)
        ttk.Label(body, text="Rep").grid(row=6, column=0, sticky="w", pady=(10, 0))
        self.rep_var = tk.StringVar()
        self.rep_cb = ttk.Combobox(body, textvariable=self.rep_var, values=REP_FULL, width=30, state="disabled")
        self.rep_cb.grid(row=7, column=0, sticky="w", pady=(0, 10), padx=(0, 16))
        self.vars["Rep"] = (self.rep_var, self.rep_cb)

        notes_frame = ttk.Frame(self)
        notes_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        ttk.Label(notes_frame, text="Notes").pack(anchor="w")

        self.notes_text = tk.Text(notes_frame, height=24, wrap="word")
        self.notes_text.pack(fill="both", expand=True)

    def _set_entry_state(self, editable: bool):
        for label, (_v, ent) in self.vars.items():
            # Fields that are ALWAYS read-only
            if label in ("SP Number", "Revision Of", "Add'l Vers Of", "Status", "Trello Card ID", "Checklist ID"):
                ent.configure(state="readonly")
                continue

            # Asset Type is normally read-only, EXCEPT for draft additional-version orders
            if label == "Asset Type":
                ent.configure(state=("readonly" if (editable and self._asset_type_editable) else "disabled"))
                continue

            if label == "Rep":
                # Rep is a dropdown: allow selecting when editable, otherwise lock it.
                ent.configure(state=("readonly" if editable else "disabled"))
                continue

            ent.configure(state=("normal" if editable else "readonly"))

        self.notes_text.configure(state=("normal" if editable else "disabled"))

    def refresh(self):
        self.status_var.set("Loading…")

        def worker():
            try:
                data = http_get_json(f"{API_BASE}/orders/{self.order_id}", timeout=20)
                self.after(0, lambda: self._apply_order(data))
            except HTTPError as e:
                self.after(0, lambda: self._fail(_http_error_to_message(e)))
            except URLError as e:
                self.after(0, lambda: self._fail(f"Connection error: {e}"))
            except Exception as e:
                self.after(0, lambda: self._fail(str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def _fail(self, msg: str):
        self.status_var.set("Failed.")
        messagebox.showerror("Load failed", msg)

    def _apply_order(self, data: dict):
        self.order_data = data
        status = (data.get("status") or "").strip().lower()
        sp = data.get("sp") or {}

        self.title_var.set(f"Order {data.get('id')} — {data.get('artist') or ''}")
        self.status_var.set(status or "draft")

        def set_field(label, value):
            v, _e = self.vars[label]
            v.set("" if value is None else str(value))

        set_field("Artist", data.get("artist", ""))
        set_field("Asset Type", data.get("asset_type", ""))
        set_field("SP Number", sp.get("sp_number", "") if isinstance(sp, dict) else "")
        set_field("Client Name", data.get("client_name", ""))
        set_field("Client Company", data.get("client_company_name", ""))
        set_field("Revision Of", sp.get("revision_of", "") if isinstance(sp, dict) else "")
        set_field("Add'l Vers Of", sp.get("additional_version_of", "") if isinstance(sp, dict) else "")
        set_field("Status", status)
        set_field("Trello Card ID", data.get("trello_card_id", ""))
        set_field("Checklist ID", data.get("trello_checklist_id", ""))
        # Rep
        rep = (data.get("rep_name") or "").strip()
        if "Rep" in self.vars:
            self.rep_var.set(rep if rep in REP_FULL else (REP_FULL[0] if not rep else rep))
        self.notes_text.configure(state="normal")
        self.notes_text.delete("1.0", "end")
        self.notes_text.insert("1.0", data.get("notes") or "")
        self.notes_text.configure(state="disabled")

        is_addl = False
        try:
            is_addl = bool((sp.get("additional_version_of") or "").strip()) if isinstance(sp, dict) else False
        except Exception:
            is_addl = False

        editable = (status != "finalized") or self._override_mode
        # Asset Type can only be edited on *additional versions* (draft), per workflow.
        self._asset_type_editable = bool(editable and is_addl and status != "finalized")
        self._set_entry_state(editable)

        # Buttons states
        self.finalize_btn.configure(state=("normal" if status != "finalized" else "disabled"))
        self.edit_btn.configure(state=("normal" if status == "finalized" else "disabled"))
        self.save_btn.configure(state=("normal" if editable else "disabled"))
        self.delete_btn.configure(state="normal")  # delete allowed for both (with double bump for finalized)

    def on_new(self):
        NewOrderDialog(self.parent, prefill={"artist": self.vars["Artist"][0].get(), "asset_type": self.vars["Asset Type"][0].get()})

    def on_addl_vers(self):
        if not self.order_data:
            return

        def worker():
            try:
                created = http_post_json(f"{API_BASE}/orders/{self.order_id}/addl_vers", payload=None, timeout=25)
                self.after(0, lambda: self._open_new(created))
            except HTTPError as e:
                self.after(0, lambda: messagebox.showerror("Add'l version failed", _http_error_to_message(e)))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Add'l version failed", str(e)))

        threading.Thread(target=worker, daemon=True).start()

    

    def on_duplicate(self):
        if not self.order_data:
            return

        def worker():
            try:
                created = http_post_json(f"{API_BASE}/orders/{self.order_id}/duplicate", payload=None, timeout=25)
                self.after(0, lambda: self._open_new(created))
            except HTTPError as e:
                self.after(0, lambda: messagebox.showerror("Duplicate failed", _http_error_to_message(e)))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Duplicate failed", str(e)))

        threading.Thread(target=worker, daemon=True).start()
    def on_revision_of(self):
        if not self.order_data:
            return

        def worker():
            try:
                created = http_post_json(f"{API_BASE}/orders/{self.order_id}/revise", payload=None, timeout=25)
                self.after(0, lambda: self._open_new(created))
            except HTTPError as e:
                self.after(0, lambda: messagebox.showerror("Revision failed", _http_error_to_message(e)))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Revision failed", str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def _open_new(self, created: dict):
        new_id = created.get("id")
        if not new_id:
            messagebox.showerror("Created, but…", "No new order id returned.")
            return
        OrderDetailsWindow(self.parent, int(new_id))

    def on_finalize(self):
        if not self.order_data:
            return
        status = (self.order_data.get("status") or "").strip().lower()
        if status == "finalized":
            return
        FinalizeDialog(self, self.order_id)

    def on_override_edit(self):
        if not self.order_data:
            return
        status = (self.order_data.get("status") or "").strip().lower()
        if status != "finalized":
            return

        ok = messagebox.askyesno(
            "Override edit",
            "This order is FINALIZED (already processed).\n\nReopen it to DRAFT so you can edit + finalize again?",
        )
        if not ok:
            return

        # Reopen in backend (no Trello sync) and refresh UI
        self.edit_btn.configure(state="disabled")
        self.save_btn.configure(state="disabled")
        self.status_var.set("Reopening…")

        def worker():
            try:
                reopened = http_post_json(f"{API_BASE}/orders/{self.order_id}/unfinalize", payload=None, timeout=25)
                self.after(0, lambda: self._after_unfinalize(reopened))
            except HTTPError as e:
                self.after(0, lambda: self._after_unfinalize_fail(_http_error_to_message(e)))
            except Exception as e:
                self.after(0, lambda: self._after_unfinalize_fail(str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def _after_unfinalize(self, reopened: dict):
        self._override_mode = False
        self._asset_type_editable = False
        self._apply_order(reopened)
        self.status_var.set("Reopened to draft.")
        if hasattr(self.parent, "run_search"):
            self.parent.run_search(silent=True)

    def _after_unfinalize_fail(self, msg: str):
        # Put the button back so you can try again.
        self.edit_btn.configure(state="normal")
        self.status_var.set("Failed.")
        messagebox.showerror("Override failed", msg)

    def on_save(self):
        if not self.order_data:
            return

        status = (self.order_data.get("status") or "").strip().lower()
        if status == "finalized":
            messagebox.showerror("Read-only", "This order is finalized. Use Override Edit… first.")
            return

        payload = {
            "artist": self.vars["Artist"][0].get().strip(),
            "notes": (self.notes_text.get("1.0", "end") or "").strip(),
            "client_name": self.vars["Client Name"][0].get().strip() or None,
            "client_company_name": self.vars["Client Company"][0].get().strip() or None,
            "rep_name": (self.vars.get("Rep", (tk.StringVar(value=REP_FULL[0]), None))[0].get() or REP_FULL[0]).strip(),
        }
        # Asset Type is normally immutable. We only allow editing it for *additional versions*.
        if getattr(self, "_asset_type_editable", False):
            at = (self.vars["Asset Type"][0].get() or "").strip().lower()
            if at:
                if at not in ("radio", "video", "art"):
                    messagebox.showerror("Bad asset type", "Asset Type must be: radio, video, or art.")
                    return
                payload["asset_type"] = at


        self.save_btn.configure(state="disabled")
        self.status_var.set("Saving…")

        def worker():
            try:
                updated = http_patch_json(f"{API_BASE}/orders/{self.order_id}", payload=payload, timeout=30)
                self.after(0, lambda: self._after_save(updated))
            except HTTPError as e:
                self.after(0, lambda: self._after_save_fail(_http_error_to_message(e)))
            except Exception as e:
                self.after(0, lambda: self._after_save_fail(str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def _after_save(self, updated: dict):
        self.save_btn.configure(state="normal")
        self._override_mode = False
        self._asset_type_editable = False

        # Refresh from API so the UI never looks "stuck" on Saving…
        try:
            fresh = http_get_json(f"{API_BASE}/orders/{self.order_id}", timeout=15)
        except Exception:
            fresh = updated

        self._apply_order(fresh)
        self.status_var.set("Saved.")
        if hasattr(self.parent, "run_search"):
            self.parent.run_search(silent=True)

    def _after_save_fail(self, msg: str):
        self.save_btn.configure(state="normal")
        self.status_var.set("Failed.")
        messagebox.showerror("Save failed", msg)

    def on_delete(self):
        if not self.order_data:
            return

        status = (self.order_data.get("status") or "").strip().lower()
        is_finalized = status == "finalized"

        if is_finalized:
            ok = messagebox.askokcancel(
                "Delete FINALIZED order",
                "You are about to delete an order that has ALREADY BEEN PROCESSED.\n\nThis is dangerous.\n\nContinue?",
                icon="warning",
            )
            if not ok:
                return

        initials = simpledialog.askstring("Confirm delete", "Type your initials to confirm deletion:", parent=self)
        initials = (initials or "").strip()
        if not initials:
            messagebox.showerror("Cancelled", "Initials are required to delete.")
            return

        if is_finalized:
            ok2 = messagebox.askokcancel(
                "Are you sure?",
                f"FINAL check.\n\nDelete order {self.order_id}?\n\nInitials: {initials}",
                icon="warning",
            )
            if not ok2:
                return

        qs = {"initials": initials}
        if is_finalized:
            qs["force"] = "true"

        self.delete_btn.configure(state="disabled")
        self.status_var.set("Deleting…")

        def worker():
            try:
                http_delete_json(f"{API_BASE}/orders/{self.order_id}?{urlencode(qs)}", timeout=25)
                self.after(0, self._after_delete_ok)
            except HTTPError as e:
                self.after(0, lambda: self._after_delete_fail(_http_error_to_message(e)))
            except Exception as e:
                self.after(0, lambda: self._after_delete_fail(str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def _after_delete_ok(self):
        if hasattr(self.parent, "run_search"):
            self.parent.run_search(silent=True)
        self.destroy()

    def _after_delete_fail(self, msg: str):
        self.delete_btn.configure(state="normal")
        self.status_var.set("Failed.")
        messagebox.showerror("Delete failed", msg)


# -----------------------------
# Search GUI
# -----------------------------
class OrderSearchGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("BYP Ops — Orders")

        # Default size (overridden if we have a saved window geometry)
        default_geometry = "1080x720"
        saved_geo = None
        try:
            _p = self._load_prefs()
            saved_geo = (_p or {}).get("window_geometry")
        except Exception:
            saved_geo = None

        if isinstance(saved_geo, str) and "x" in saved_geo:
            try:
                self.geometry(saved_geo)
            except Exception:
                self.geometry(default_geometry)
        else:
            self.geometry(default_geometry)

        # Restore maximized state if it was last used
        try:
            saved_state = None
            try:
                _p = getattr(self, "_prefs", None)
                if not isinstance(_p, dict):
                    _p = self._load_prefs()
                saved_state = (_p or {}).get("window_state")
            except Exception:
                saved_state = None
            if saved_state == "zoomed":
                self.after(0, lambda: self.state("zoomed"))
        except Exception:
            pass

        self.show_order_id = False

        self._last_items = []

        # Load UI preferences (column widths now; column order later)
        self._prefs = self._load_prefs()
        self._col_widths = dict(self._prefs.get("column_widths") or {})
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_ui()

        # On launch, show all orders immediately.
        # (Search endpoint with no filters returns everything.)
        self.after(150, self.run_search)


    # -----------------------------
    # UI preferences
    # -----------------------------
    def _load_prefs(self) -> dict:
        path = _prefs_path()
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except FileNotFoundError:
            return {}
        except Exception:
            # Don't crash the app over a bad prefs file.
            return {}

    def _save_prefs(self, data: dict) -> None:
        path = _prefs_path()
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            # Preferences are nice-to-have. If save fails, shrug and move on.
            pass

    def _gather_column_widths(self) -> dict:
        widths = {}
        try:
            for col in self.tree["columns"]:
                w = self.tree.column(col, "width")
                try:
                    widths[col] = int(w)
                except Exception:
                    pass
        except Exception:
            pass
        return widths

    def _apply_saved_column_widths(self, cols: list[str]) -> None:
        for col in cols:
            w = self._col_widths.get(col)
            if isinstance(w, int) and 30 <= w <= 1400:
                try:
                    self.tree.column(col, width=w)
                except Exception:
                    pass

    def _on_close(self):
        prefs = dict(getattr(self, "_prefs", {}) or {})
        prefs["column_widths"] = self._gather_column_widths()

        # Persist window size/position so it opens the way you left it.
        try:
            prefs["window_geometry"] = self.winfo_geometry()
        except Exception:
            pass
        try:
            prefs["window_state"] = self.state()
        except Exception:
            pass

        # Column order will be stored here later as prefs["displaycolumns"]
        self._save_prefs(prefs)
        self.destroy()

    def _build_ui(self):
        top = ttk.Frame(self)
        top.pack(fill="x", padx=10, pady=10)

        ttk.Label(top, text="Artist").grid(row=0, column=0, sticky="w")
        self.artist_var = tk.StringVar()
        ent_artist = ttk.Entry(top, textvariable=self.artist_var, width=34)
        ent_artist.grid(row=0, column=1, sticky="w", padx=(0, 12))

        ttk.Label(top, text="Asset").grid(row=0, column=2, sticky="w")
        self.asset_var = tk.StringVar()
        cb_asset = ttk.Combobox(top, textvariable=self.asset_var, values=["", "radio", "video", "art"], width=10, state="readonly")
        cb_asset.grid(row=0, column=3, sticky="w", padx=(0, 12))

        ttk.Label(top, text="Notes").grid(row=0, column=4, sticky="w")
        self.notes_var = tk.StringVar()
        ent_notes = ttk.Entry(top, textvariable=self.notes_var, width=28)
        ent_notes.grid(row=0, column=5, sticky="w", padx=(0, 12))

        ttk.Label(top, text="Status").grid(row=0, column=6, sticky="w")
        self.status_var = tk.StringVar()
        cb_status = ttk.Combobox(top, textvariable=self.status_var, values=["", "draft", "finalized"], width=10, state="readonly")
        cb_status.grid(row=0, column=7, sticky="w", padx=(0, 12))

        ttk.Label(top, text="Rep").grid(row=0, column=8, sticky="w")
        self.rep_search_var = tk.StringVar()
        cb_rep = ttk.Combobox(
            top,
            textvariable=self.rep_search_var,
            values=[""] + REP_CODES,
            width=8,
            state="readonly",
        )
        cb_rep.grid(row=0, column=9, sticky="w", padx=(0, 12))

        self.adv_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(top, text="Client fields", variable=self.adv_var, command=self._toggle_adv).grid(row=0, column=10, sticky="w")

        self.client_name_var = tk.StringVar()
        self.client_company_var = tk.StringVar()
        # Advanced (client) fields live in their own sub-frame so they DON'T resize/shift the top row.
        self.adv_frame = ttk.Frame(top)

        self.client_name_lbl = ttk.Label(self.adv_frame, text="Client Name")
        self.client_name_ent = ttk.Entry(self.adv_frame, textvariable=self.client_name_var, width=34)

        self.client_company_lbl = ttk.Label(self.adv_frame, text="Client Company")
        self.client_company_ent = ttk.Entry(self.adv_frame, textvariable=self.client_company_var, width=34)

        # Layout inside the adv_frame (single row)
        self.client_name_lbl.grid(row=0, column=0, sticky="w")
        self.client_name_ent.grid(row=0, column=1, sticky="w", padx=(0, 12))

        self.client_company_lbl.grid(row=0, column=2, sticky="w")
        self.client_company_ent.grid(row=0, column=3, sticky="w", padx=(0, 12))

        btns = ttk.Frame(self)
        btns.pack(fill="x", padx=10)        # Buttons (grouped to reduce misclicks)
        btns_left = ttk.Frame(btns)
        btns_left.pack(side="left")

        ttk.Button(btns_left, text="My Drafts", command=self.show_my_drafts).pack(side="left")
        ttk.Button(btns_left, text="Search", command=self.run_search).pack(side="left", padx=(10, 0))
        ttk.Button(btns_left, text="Clear Search", command=self.clear_search).pack(side="left", padx=(6, 0))

        btns_mid = ttk.Frame(btns)
        btns_mid.pack(side="left", fill="x", expand=True)

        ttk.Button(btns_mid, text="New Order", command=lambda: NewOrderDialog(self)).pack()

        btns_right = ttk.Frame(btns)
        btns_right.pack(side="right")

        self.msg_var = tk.StringVar(value="")
        ttk.Label(btns_right, textvariable=self.msg_var).pack(side="right")

        self.show_id_btn = ttk.Button(btns_right, text="Show Order ID", command=self.enable_order_id_column)
        self.show_id_btn.pack(side="right", padx=(0, 10))

        # Tree
        cols = self._tree_columns()
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=22, selectmode="extended")
        self._configure_tree_columns()

        self.tree.pack(fill="both", expand=True, padx=10, pady=10)
        self.tree.bind("<Double-1>", lambda _e: self.open_selected_from_api())
        # Right-click context menu
        self._init_context_menu()
        self.tree.bind("<Button-3>", self._on_right_click)
        self.tree.bind("<Delete>", lambda _e: self._ctx_delete())
                # Enter-to-search (because it's not 1994)
        for w in (ent_artist, ent_notes, cb_asset, cb_status, cb_rep, self.client_name_ent, self.client_company_ent):
            try:
                w.bind("<Return>", lambda _e: self.run_search())
            except Exception:
                pass

        self._toggle_adv()

    def _tree_columns(self):
        base = ["Status", "Rep", "Artist", "Asset", "Notes", "SP", "Revision Of", "Add'l Vers Of"]
        if self.show_order_id:
            base.append("Order ID")
        return base

    def _configure_tree_columns(self):
        cols = self._tree_columns()
        self.tree.configure(columns=cols)

        for c in cols:
            self.tree.heading(c, text=c)
            if c == "Notes":
                self.tree.column(c, width=380, anchor="w")
            elif c == "Artist":
                self.tree.column(c, width=200, anchor="w")
            elif c == "Status":
                self.tree.column(c, width=90, anchor="w")
            elif c == "Rep":
                self.tree.column(c, width=60, anchor="w")
            elif c == "Order ID":
                self.tree.column(c, width=80, anchor="e")
            else:
                self.tree.column(c, width=140, anchor="w")


        self._apply_saved_column_widths(cols)

    def _toggle_adv(self):
        # Show/hide the advanced client fields row without shifting the top row layout.
        if self.adv_var.get():
            self.adv_frame.grid(row=1, column=0, columnspan=20, sticky="w", pady=(10, 0))
        else:
            try:
                self.adv_frame.grid_remove()
            except Exception:
                pass


    def enable_order_id_column(self):
        if self.show_order_id:
            return
        self.show_order_id = True
        self.show_id_btn.configure(state="disabled")

        # Reset tree with new columns
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        self._configure_tree_columns()
        # Re-render the current results so the list doesn't go blank
        self._apply_results(getattr(self, "_last_items", []), silent=True)

    def show_my_drafts(self):
        # Convenience: show draft orders for the rep in the Rep box (initials).
        # If Rep box is empty, default to the first rep in REP_FULL.
        try:
            self.status_var.set("draft")
        except Exception:
            pass

        rep = (self.rep_search_var.get() or "").strip()
        if not rep:
            try:
                self.rep_search_var.set(rep_initials(REP_FULL[0]))
            except Exception:
                pass

        self.run_search()


    def _build_search_params(self) -> dict:
        params = {}
        artist = (self.artist_var.get() or "").strip()
        notes = (self.notes_var.get() or "").strip()
        asset = (self.asset_var.get() or "").strip().lower()
        status = (self.status_var.get() or "").strip().lower()
        if artist:
            params["artist"] = artist
        if notes:
            params["notes"] = notes
        if asset:
            params["asset_type"] = asset
        if status:
            params["status"] = status

        if self.adv_var.get():
            cn = (self.client_name_var.get() or "").strip()
            cc = (self.client_company_var.get() or "").strip()
            if cn:
                params["client_name"] = cn
            if cc:
                params["client_company"] = cc

        rep_code = (getattr(self, "rep_search_var", tk.StringVar()).get() or "").strip().upper()
        if rep_code:
            params["rep_code"] = rep_code

        return params


    def clear_search(self):
        # Reset all search filters to defaults and show all results.
        if hasattr(self, "artist_var"):
            self.artist_var.set("")
        if hasattr(self, "asset_var"):
            self.asset_var.set("")
        if hasattr(self, "notes_var"):
            self.notes_var.set("")
        if hasattr(self, "status_var"):
            self.status_var.set("")
        if hasattr(self, "rep_search_var"):
            self.rep_search_var.set("")
        if hasattr(self, "client_name_var"):
            self.client_name_var.set("")
        if hasattr(self, "client_company_var"):
            self.client_company_var.set("")
        if hasattr(self, "msg_var"):
            self.msg_var.set("")
        self.run_search()


    def run_search(self, silent: bool = False):
        params = self._build_search_params()
        url = f"{API_BASE}/orders/search"
        if params:
            url = f"{url}?{urlencode(params)}"

        if not silent:
            self.msg_var.set("Searching…")

        def worker():
            try:
                data = http_get_json(url, timeout=25)
                items = data.get("value") if isinstance(data, dict) else None
                if items is None and isinstance(data, list):
                    items = data
                if items is None:
                    items = []
                self.after(0, lambda: self._apply_results(items, silent=silent))
            except HTTPError as e:
                self.after(0, lambda: self._search_fail(_http_error_to_message(e), silent=silent))
            except URLError as e:
                self.after(0, lambda: self._search_fail(f"Connection error: {e}", silent=silent))
            except Exception as e:
                self.after(0, lambda: self._search_fail(str(e), silent=silent))

        threading.Thread(target=worker, daemon=True).start()

    def _search_fail(self, msg: str, silent: bool):
        if not silent:
            self.msg_var.set("Failed.")
            messagebox.showerror("Search failed", msg)

    def _apply_results(self, items: list, silent: bool):
        self._last_items = items or []
        for iid in self.tree.get_children():
            self.tree.delete(iid)

        cols = self._tree_columns()
        for row in items:
            oid = row.get("id")
            status = (row.get("status") or "").strip()
            artist = row.get("artist") or ""
            asset = row.get("asset_type") or ""
            notes = (row.get("notes") or "")
            # Treeview cells don't handle multi-line text well; flatten notes for display.
            _n = notes.replace("\r\n", "\n").replace("\r", "\n")
            notes = " | ".join([ln.strip() for ln in _n.split("\n") if ln.strip()])
            sp = row.get("sp") or {}
            sp_num = sp.get("sp_number", "") if isinstance(sp, dict) else ""
            rev = sp.get("revision_of", "") if isinstance(sp, dict) else ""
            addl = sp.get("additional_version_of", "") if isinstance(sp, dict) else ""

            # Hide None/"none" placeholders in the grid (show blank when not applicable)
            def _blank(v):
                if v is None:
                    return ""
                s = str(v).strip()
                return "" if s.lower() == "none" else s

            rev = _blank(rev)
            addl = _blank(addl)

            rep = rep_initials(row.get("rep_name", "") or "")

            values = [status, rep, artist, asset, notes, sp_num, rev, addl]
            if self.show_order_id:
                values.append(str(oid) if oid is not None else "")

            self.tree.insert("", "end", iid=str(oid), values=values)

        if not silent:
            self.msg_var.set(f"{len(items)} result(s)")

    def open_selected_from_api(self):
        sel = self.tree.selection()
        if not sel:
            return
        order_id = sel[0]
        try:
            OrderDetailsWindow(self, int(order_id))
        except Exception as e:
            messagebox.showerror("Open failed", str(e))

    def _init_context_menu(self):
        # Context menu for the search grid
        self._rc_menu = tk.Menu(self, tearoff=0)
        self._rc_menu.add_command(label="Open", command=self._ctx_open)
        self._rc_menu.add_separator()
        self._rc_menu.add_command(label="Delete…", command=self._ctx_delete)
    def _on_right_click(self, event):
        # Select the row under the cursor and show menu.
        iid = self.tree.identify_row(event.y)
        if not iid:
            return

        try:
            current = set(self.tree.selection() or ())
            # If you right-click a non-selected row, switch selection to that row.
            # If you right-click an already-selected row, keep the multi-selection.
            if iid not in current:
                self.tree.selection_set(iid)
            self.tree.focus(iid)
        except Exception:
            pass

        try:
            self._rc_menu.tk_popup(event.x_root, event.y_root)
        finally:
            try:
                self._rc_menu.grab_release()
            except Exception:
                pass

    def _ctx_open(self):
        self.open_selected_from_api()
    def _ctx_delete(self):
        sel = list(self.tree.selection() or [])
        if not sel:
            return

        # Convert iids to order ids and detect finalized rows via Status column (first visible column).
        order_ids: list[int] = []
        finalized_ids: list[int] = []

        for iid in sel:
            try:
                oid = int(iid)
            except Exception:
                continue
            order_ids.append(oid)
            try:
                values = self.tree.item(iid, "values") or []
                status = (values[0] or "").strip().lower() if values else ""
                if status == "finalized":
                    finalized_ids.append(oid)
            except Exception:
                pass

        if not order_ids:
            messagebox.showerror("Delete failed", "Couldn't determine the selected order id(s).")
            return

        count = len(order_ids)

        # Confirm count (and extra scary warning if any are finalized)
        if finalized_ids:
            ok = messagebox.askokcancel(
                "Delete FINALIZED order(s)",
                f"You selected {count} order(s) to delete.\n\n"
                f"{len(finalized_ids)} of them are FINALIZED (already processed).\n\n"
                "This is dangerous.\n\nContinue?",
                icon="warning",
            )
            if not ok:
                return
        else:
            ok = messagebox.askokcancel(
                "Confirm delete",
                f"Delete {count} selected order(s)?",
                icon="warning",
            )
            if not ok:
                return

        initials = simpledialog.askstring(
            "Confirm delete",
            "Type your initials to confirm deletion:",
            parent=self,
        )
        initials = (initials or "").strip()
        if not initials:
            messagebox.showerror("Cancelled", "Initials are required to delete.")
            return

        # FINAL double-check if any are finalized
        if finalized_ids:
            ok2 = messagebox.askokcancel(
                "Are you sure?",
                "FINAL check.\n\n"
                f"Delete {count} order(s)?\n"
                f"Finalized included: {', '.join(map(str, finalized_ids))}\n\n"
                f"Initials: {initials}",
                icon="warning",
            )
            if not ok2:
                return

        self.msg_var.set("Deleting…")

        def worker():
            failures: list[tuple[int, str]] = []

            for oid in order_ids:
                qs = {"initials": initials}
                # Force only for finalized ones
                if oid in finalized_ids:
                    qs["force"] = "true"
                try:
                    http_delete_json(f"{API_BASE}/orders/{oid}?{urlencode(qs)}", timeout=25)
                except HTTPError as e:
                    failures.append((oid, _http_error_to_message(e)))
                except Exception as e:
                    failures.append((oid, str(e)))

            def done():
                try:
                    self.run_search(silent=True)
                except Exception:
                    pass

                if failures:
                    self.msg_var.set("Delete completed with errors.")
                    details = "\n".join([f"{oid}: {msg}" for oid, msg in failures])
                    messagebox.showerror(
                        "Some deletes failed",
                        f"Deleted {count - len(failures)} of {count} order(s).\n\nFailures:\n{details}",
                    )
                else:
                    self.msg_var.set(f"Deleted {count} order(s).")

            self.after(0, done)

        threading.Thread(target=worker, daemon=True).start()

    def _after_ctx_delete_ok(self, order_id: int):
        try:
            self.run_search(silent=True)
        except Exception:
            pass
        self.msg_var.set(f"Deleted {order_id}")

    def _after_ctx_delete_fail(self, msg: str):
        self.msg_var.set("Delete failed.")
        messagebox.showerror("Delete failed", msg)


def main():
    root = OrderSearchGUI()
    root.mainloop()


if __name__ == "__main__":
    main()

