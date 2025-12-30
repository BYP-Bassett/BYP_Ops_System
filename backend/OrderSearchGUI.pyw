# OrderSearchGUI.pyw
# FileMaker-style Orders search GUI for your FastAPI backend.
#
# Current features:
# - Field-specific search params (AND across fields)
# - Advanced toggle for client fields
# - Results columns: Artist, Asset Type, Notes, SP Number, Revision Of (NEW if none), Status
# - Enter/Return triggers Search
# - Double-click fetches /orders/{id} fresh from API and shows detail window
#
# Detail window workflow:
# - Draft: editable fields + Save + Finalize (links Trello IDs)
# - Finalized: read-only + Override Edit… (confirmation) + Save (override=true → rebuild Trello checklist)

import json
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from urllib.parse import urlencode
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

API_BASE = "http://127.0.0.1:8000"


def _read_json_response(resp):
    data = resp.read().decode("utf-8", errors="replace")
    return json.loads(data) if data else {}


def http_get_json(url: str, timeout: int = 10):
    req = Request(url, headers={"Accept": "application/json"})
    with urlopen(req, timeout=timeout) as resp:
        return _read_json_response(resp)


def http_send_json(method: str, url: str, payload: dict | None, timeout: int = 15):
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = Request(url, data=body, headers=headers, method=method)
    with urlopen(req, timeout=timeout) as resp:
        return _read_json_response(resp)


def http_post_json(url: str, payload: dict | None = None, timeout: int = 15):
    return http_send_json("POST", url, payload, timeout=timeout)


def http_patch_json(url: str, payload: dict, timeout: int = 15):
    return http_send_json("PATCH", url, payload, timeout=timeout)


class NewOrderDialog(tk.Toplevel):
    """Brand new order (POST /orders/new)."""

    def __init__(self, parent, prefill_from: dict | None = None):
        super().__init__(parent)
        self.parent = parent
        self.prefill_from = prefill_from or {}

        self.title("Create New Order")
        self.geometry("780x520")
        self.resizable(True, True)

        self._build_ui()
        self._prefill()

    def _build_ui(self):
        pad = {"padx": 10, "pady": 8}

        top = ttk.Frame(self)
        top.pack(fill="x", **pad)

        self.status_var = tk.StringVar(value="Ready.")
        ttk.Label(top, textvariable=self.status_var).pack(side="left")

        form = ttk.Frame(self)
        form.pack(fill="x", padx=10)

        ttk.Label(form, text="Artist").grid(row=0, column=0, sticky="w")
        self.artist_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.artist_var, width=40).grid(row=0, column=1, sticky="w", padx=(0, 18))

        ttk.Label(form, text="Asset Type").grid(row=0, column=2, sticky="w")
        self.asset_var = tk.StringVar()
        self.asset_cb = ttk.Combobox(
            form, textvariable=self.asset_var, values=["radio", "video", "art"], width=12, state="readonly"
        )
        self.asset_cb.grid(row=0, column=3, sticky="w")

        ttk.Label(form, text="Client Name").grid(row=1, column=0, sticky="w", pady=(10, 0))
        self.client_name_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.client_name_var, width=28).grid(row=1, column=1, sticky="w", padx=(0, 18), pady=(10, 0))

        ttk.Label(form, text="Client Company").grid(row=1, column=2, sticky="w", pady=(10, 0))
        self.client_company_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.client_company_var, width=32).grid(row=1, column=3, sticky="w", pady=(10, 0))

        notes_frame = ttk.Frame(self)
        notes_frame.pack(fill="both", expand=True, padx=10, pady=(10, 10))
        ttk.Label(notes_frame, text="Notes").pack(anchor="w")

        self.notes_text = tk.Text(notes_frame, height=10, wrap="word")
        self.notes_text.pack(fill="both", expand=True)

        footer = ttk.Frame(self)
        footer.pack(fill="x", padx=10, pady=(0, 10))

        self.create_btn = ttk.Button(footer, text="Create", command=self.on_create)
        self.create_btn.pack(side="left")

        ttk.Button(footer, text="Cancel", command=self.destroy).pack(side="left", padx=(10, 0))

    def _prefill(self):
        self.artist_var.set((self.prefill_from.get("artist") or "").strip())
        asset = (self.prefill_from.get("asset_type") or "radio").strip().lower()
        if asset not in ("radio", "video", "art"):
            asset = "radio"
        self.asset_var.set(asset)

        self.client_name_var.set((self.prefill_from.get("client_name") or "").strip())
        self.client_company_var.set((self.prefill_from.get("client_company_name") or "").strip())

        self.notes_text.delete("1.0", "end")
        self.notes_text.insert("1.0", "")

    def on_create(self):
        artist = (self.artist_var.get() or "").strip()
        asset = (self.asset_var.get() or "").strip().lower()
        client_name = (self.client_name_var.get() or "").strip()
        client_company = (self.client_company_var.get() or "").strip()
        notes = (self.notes_text.get("1.0", "end") or "").strip()

        if not artist:
            messagebox.showerror("Missing data", "Artist is required.")
            return
        if asset not in ("radio", "video", "art"):
            messagebox.showerror("Missing data", "Asset Type must be radio, video, or art.")
            return

        payload = {"artist": artist, "asset_type": asset, "notes": notes}
        if client_name:
            payload["client_name"] = client_name
        if client_company:
            payload["client_company_name"] = client_company

        self.status_var.set("Creating…")
        self.create_btn.configure(state="disabled")

        def worker():
            try:
                created = http_post_json(f"{API_BASE}/orders/new", payload=payload, timeout=20)
                self.after(0, lambda: self._done_success(created))
            except HTTPError as e:
                try:
                    body = e.read().decode("utf-8", errors="replace")
                except Exception:
                    body = str(e)
                self.after(0, lambda: self._done_fail(f"HTTP {e.code}: {body}"))
            except URLError as e:
                self.after(0, lambda: self._done_fail(f"Connection error: {e}"))
            except Exception as e:
                self.after(0, lambda: self._done_fail(str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def _done_success(self, created: dict):
        self.status_var.set("Done.")
        self.create_btn.configure(state="normal")

        new_id = created.get("id")
        if not new_id:
            messagebox.showerror("Created, but…", "Order created, but response did not include an id.")
            return

        OrderDetailsWindow(self.parent, int(new_id))
        self.destroy()

    def _done_fail(self, msg: str):
        self.create_btn.configure(state="normal")
        self.status_var.set("Failed.")
        messagebox.showerror("Create failed", msg)


class FinalizeDialog(tk.Toplevel):
    """Finalize a draft order by linking existing Trello card/checklist IDs."""

    def __init__(self, parent, order_id: int):
        super().__init__(parent)
        self.parent = parent
        self.order_id = order_id

        self.title("Finalize Order (link Trello)")
        self.geometry("520x200")
        self.resizable(False, False)

        self._build_ui()

    def _build_ui(self):
        pad = {"padx": 10, "pady": 10}

        frm = ttk.Frame(self)
        frm.pack(fill="both", expand=True, **pad)

        ttk.Label(frm, text="Trello Card ID").grid(row=0, column=0, sticky="w")
        self.card_var = tk.StringVar()
        ttk.Entry(frm, textvariable=self.card_var, width=45).grid(row=0, column=1, sticky="w")

        ttk.Label(frm, text="Checklist ID").grid(row=1, column=0, sticky="w", pady=(10, 0))
        self.chk_var = tk.StringVar()
        ttk.Entry(frm, textvariable=self.chk_var, width=45).grid(row=1, column=1, sticky="w", pady=(10, 0))

        self.status_var = tk.StringVar(value="Provide the IDs from the Trello card that was created for this order.")
        ttk.Label(frm, textvariable=self.status_var, wraplength=480).grid(row=2, column=0, columnspan=2, sticky="w", pady=(10, 0))

        btns = ttk.Frame(self)
        btns.pack(fill="x", padx=10, pady=(0, 10))

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
                url = f"{API_BASE}/orders/{self.order_id}/finalize?{urlencode({'trello_card_id': card, 'trello_checklist_id': chk})}"
                http_post_json(url, payload=None, timeout=25)
                self.after(0, self._done)
            except HTTPError as e:
                try:
                    body = e.read().decode("utf-8", errors="replace")
                except Exception:
                    body = str(e)
                self.after(0, lambda: self._fail(f"HTTP {e.code}: {body}"))
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


class OrderDetailsWindow(tk.Toplevel):
    def __init__(self, parent, order_id: int):
        super().__init__(parent)
        self.parent = parent
        self.order_id = order_id
        self.order_data = None

        self._override_mode = False

        self.geometry("980x740")
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        pad = {"padx": 10, "pady": 8}

        header = ttk.Frame(self)
        header.pack(fill="x", **pad)

        self.title_var = tk.StringVar(value="(loading…)")
        ttk.Label(header, textvariable=self.title_var, font=("Segoe UI", 12, "bold")).pack(side="left")

        self.status_var = tk.StringVar(value="Loading…")
        ttk.Label(header, textvariable=self.status_var).pack(side="right")

        actions = ttk.Frame(self)
        actions.pack(fill="x", padx=10, pady=(0, 8))

        ttk.Button(actions, text="Refresh", command=self.refresh).pack(side="left")

        ttk.Separator(actions, orient="vertical").pack(side="left", fill="y", padx=10)

        ttk.Button(actions, text="New", command=self.on_new).pack(side="left")
        ttk.Button(actions, text="Add'l Vers Of", command=self.on_addl_vers).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Revision Of", command=self.on_revision_of).pack(side="left", padx=(8, 0))

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

        self.vars = {}

        def add_row(r, c, label, width=38):
            ttk.Label(body, text=label).grid(row=r, column=c, sticky="w", pady=(0, 4))
            var = tk.StringVar(value="")
            ent = ttk.Entry(body, textvariable=var, width=width)
            ent.grid(row=r + 1, column=c, sticky="w", padx=(0, 16), pady=(0, 10))
            self.vars[label] = (var, ent)

        add_row(0, 0, "Artist", 46)
        add_row(0, 1, "Asset Type", 18)
        add_row(0, 2, "SP Number", 18)

        add_row(2, 0, "Client Name", 30)
        add_row(2, 1, "Client Company", 34)
        add_row(2, 2, "Revision Of", 22)

        add_row(4, 0, "Status", 18)
        add_row(4, 1, "Trello Card ID", 34)
        add_row(4, 2, "Checklist ID", 34)

        notes_frame = ttk.Frame(self)
        notes_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        ttk.Label(notes_frame, text="Notes").pack(anchor="w")

        self.notes_text = tk.Text(notes_frame, height=24, wrap="word")
        self.notes_text.pack(fill="both", expand=True)

    def _set_entry_state(self, editable: bool):
        for label, (_var, ent) in self.vars.items():
            if label in ("Asset Type", "SP Number", "Revision Of", "Trello Card ID", "Checklist ID", "Status"):
                ent.configure(state="readonly")
            else:
                ent.configure(state="normal" if editable else "readonly")
        self.notes_text.configure(state="normal" if editable else "disabled")

    def refresh(self):
        self.status_var.set("Loading…")

        def worker():
            try:
                data = http_get_json(f"{API_BASE}/orders/{self.order_id}", timeout=15)
                self.after(0, lambda: self._apply_order(data))
            except HTTPError as e:
                try:
                    body = e.read().decode("utf-8", errors="replace")
                except Exception:
                    body = str(e)
                self.after(0, lambda: self._fail(f"HTTP {e.code}: {body}"))
            except URLError as e:
                self.after(0, lambda: self._fail(f"Connection error: {e}"))
            except Exception as e:
                self.after(0, lambda: self._fail(str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def _fail(self, msg: str):
        self.status_var.set("Load failed.")
        messagebox.showerror("Order load failed", msg)

    def _apply_order(self, data: dict):
        self.order_data = data
        self.status_var.set("Loaded.")

        artist = (data.get("artist") or "").strip() or "(no artist)"
        self.title_var.set(artist)
        self.title(f"Order Details — {artist} — #{data.get('id', self.order_id)}")

        sp = data.get("sp") if isinstance(data, dict) else None
        sp_number = ""
        sp_revision_of = ""
        if isinstance(sp, dict):
            sp_number = sp.get("sp_number", "") or ""
            sp_revision_of = sp.get("revision_of", "") or ""

        revision_of = data.get("revision_of") or sp_revision_of or "NEW"
        status = (data.get("status") or "draft").strip().lower()

        self.vars["Artist"][0].set(artist)
        self.vars["Asset Type"][0].set(data.get("asset_type", "") or "")
        self.vars["SP Number"][0].set(sp_number)
        self.vars["Client Name"][0].set(data.get("client_name", "") or "")
        self.vars["Client Company"][0].set(data.get("client_company_name", "") or "")
        self.vars["Revision Of"][0].set(revision_of)

        self.vars["Status"][0].set(status.upper())
        self.vars["Trello Card ID"][0].set(data.get("trello_card_id", "") or "")
        self.vars["Checklist ID"][0].set(data.get("trello_checklist_id", "") or "")

        self.notes_text.configure(state="normal")
        self.notes_text.delete("1.0", "end")
        self.notes_text.insert("1.0", (data.get("notes") or "").strip())
        self.notes_text.configure(state="disabled")

        self._override_mode = False
        if status == "draft":
            self._set_entry_state(True)
            self.edit_btn.configure(state="disabled")
            self.save_btn.configure(state="normal")
            self.finalize_btn.configure(state="normal")
        else:
            self._set_entry_state(False)
            self.edit_btn.configure(state="normal")
            self.save_btn.configure(state="disabled")
            self.finalize_btn.configure(state="disabled")

    def on_new(self):
        if not self.order_data:
            messagebox.showinfo("Hold up", "This order hasn't finished loading yet.")
            return
        NewOrderDialog(self, prefill_from=self.order_data)

    def on_addl_vers(self):
        messagebox.showinfo("Not yet", "Add'l Vers Of: we’ll define + implement this next.")

    def on_revision_of(self):
        if not self.order_data:
            return

        ok = messagebox.askyesno(
            "Revision Of",
            "Create a new revision order from this one?\n\nThis will create a new DRAFT revision and open it.",
        )
        if not ok:
            return

        self.status_var.set("Creating revision…")

        def fail(msg: str):
            self.status_var.set("Revision failed.")
            messagebox.showerror("Revision Of failed", msg)

        def worker():
            try:
                data = http_post_json(f"{API_BASE}/orders/{self.order_id}/revise", payload=None, timeout=25)
                new_id = data.get("id") if isinstance(data, dict) else None
                if not new_id:
                    raise Exception(f"Unexpected response: {data!r}")

                def open_new():
                    self.status_var.set("Revision created.")
                    OrderDetailsWindow(self.parent, int(new_id))

                self.after(0, open_new)
            except HTTPError as e:
                try:
                    body = e.read().decode("utf-8", errors="replace")
                except Exception:
                    body = str(e)
                self.after(0, lambda: fail(f"HTTP {e.code}: {body}"))
            except URLError as e:
                self.after(0, lambda: fail(f"Connection error: {e}"))
            except Exception as e:
                self.after(0, lambda: fail(str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def on_finalize(self):
        if not self.order_data:
            return
        FinalizeDialog(self, self.order_id)

    def on_override_edit(self):
        if not self.order_data:
            return

        ok = messagebox.askyesno(
            "Override edit",
            "This order is FINALIZED (Trello already exists).\n\nEdit anyway?\n\nSaving will rebuild the Trello checklist.",
        )
        if not ok:
            return

        self._override_mode = True
        self._set_entry_state(True)
        self.edit_btn.configure(state="disabled")
        self.save_btn.configure(state="normal")

    def on_save(self):
        if not self.order_data:
            return

        artist = (self.vars["Artist"][0].get() or "").strip()
        client_name = (self.vars["Client Name"][0].get() or "").strip()
        client_company = (self.vars["Client Company"][0].get() or "").strip()
        notes = (self.notes_text.get("1.0", "end") or "").strip()

        if not artist:
            messagebox.showerror("Missing data", "Artist is required.")
            return

        payload = {
            "artist": artist,
            "notes": notes,
            "client_name": client_name,
            "client_company_name": client_company,
        }

        qs = "?override=true" if self._override_mode else ""

        self.status_var.set("Saving…")
        self.save_btn.configure(state="disabled")

        def worker():
            try:
                http_patch_json(f"{API_BASE}/orders/{self.order_id}{qs}", payload, timeout=30)
                self.after(0, self._after_save)
            except HTTPError as e:
                try:
                    body = e.read().decode("utf-8", errors="replace")
                except Exception:
                    body = str(e)
                self.after(0, lambda: self._after_save_fail(f"HTTP {e.code}: {body}"))
            except Exception as e:
                self.after(0, lambda: self._after_save_fail(str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def _after_save(self):
        self.status_var.set("Saved.")
        self.refresh()

    def _after_save_fail(self, msg: str):
        self.save_btn.configure(state="normal")
        self.status_var.set("Save failed.")
        messagebox.showerror("Save failed", msg)


class OrderSearchGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Orders Search")
        self.geometry("1200x640")

        self.advanced_visible = tk.BooleanVar(value=False)
        self._build_ui()

        self.bind_all("<Return>", self._on_enter_key)

    def _on_enter_key(self, _event=None):
        if str(self.search_btn["state"]) != "disabled":
            self.on_search()

    def _build_ui(self):
        pad = {"padx": 8, "pady": 6}

        top = ttk.Frame(self)
        top.pack(fill="x", **pad)

        ttk.Label(top, text="Artist").grid(row=0, column=0, sticky="w")
        self.artist_var = tk.StringVar()
        ttk.Entry(top, textvariable=self.artist_var, width=35).grid(row=0, column=1, sticky="we", padx=(0, 12))

        ttk.Label(top, text="Asset Type").grid(row=0, column=2, sticky="w")
        self.asset_var = tk.StringVar()
        self.asset_cb = ttk.Combobox(
            top, textvariable=self.asset_var, values=["", "radio", "video", "art"], width=12, state="readonly"
        )
        self.asset_cb.grid(row=0, column=3, sticky="w", padx=(0, 12))
        self.asset_cb.current(0)

        ttk.Label(top, text="SP Number").grid(row=0, column=4, sticky="w")
        self.spnum_var = tk.StringVar()
        ttk.Entry(top, textvariable=self.spnum_var, width=18).grid(row=0, column=5, sticky="w")

        ttk.Label(top, text="Notes").grid(row=1, column=0, sticky="w")
        self.notes_var = tk.StringVar()
        ttk.Entry(top, textvariable=self.notes_var, width=35).grid(row=1, column=1, sticky="we", padx=(0, 12))

        self.adv_btn = ttk.Button(top, text="Show Advanced ▾", command=self.toggle_advanced)
        self.adv_btn.grid(row=1, column=2, sticky="w", padx=(0, 12))

        self.adv_frame = ttk.Frame(top)

        ttk.Label(self.adv_frame, text="Client Name").grid(row=0, column=0, sticky="w")
        self.client_name_var = tk.StringVar()
        ttk.Entry(self.adv_frame, textvariable=self.client_name_var, width=25).grid(row=0, column=1, sticky="w", padx=(0, 12))

        ttk.Label(self.adv_frame, text="Client Company").grid(row=0, column=2, sticky="w")
        self.client_company_var = tk.StringVar()
        ttk.Entry(self.adv_frame, textvariable=self.client_company_var, width=30).grid(row=0, column=3, sticky="w")

        btns = ttk.Frame(self)
        btns.pack(fill="x", **pad)

        self.search_btn = ttk.Button(btns, text="Search", command=self.on_search)
        self.search_btn.pack(side="left")

        ttk.Button(btns, text="Open Selected", command=self.open_selected_from_api).pack(side="left", padx=(8, 0))
        ttk.Button(btns, text="Clear", command=self.on_clear).pack(side="left", padx=(8, 0))
        ttk.Button(btns, text="Ping API", command=self.on_ping).pack(side="left", padx=(8, 0))

        self.status_var = tk.StringVar(value="Ready.")
        ttk.Label(btns, textvariable=self.status_var).pack(side="right")

        table_frame = ttk.Frame(self)
        table_frame.pack(fill="both", expand=True, **pad)

        cols = ("artist", "asset_type", "notes", "sp_number", "revision_of", "status")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings", height=18)
        self.tree.pack(side="left", fill="both", expand=True)

        yscroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        yscroll.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=yscroll.set)

        headings = {
            "artist": "Artist",
            "asset_type": "Asset Type",
            "notes": "Notes",
            "sp_number": "SP Number",
            "revision_of": "Revision Of",
            "status": "Status",
        }
        widths = {
            "artist": 240,
            "asset_type": 110,
            "notes": 520,
            "sp_number": 120,
            "revision_of": 140,
            "status": 90,
        }

        for c in cols:
            self.tree.heading(c, text=headings[c])
            self.tree.column(c, width=widths[c], anchor="w")

        self.tree.bind("<Double-1>", lambda _e: self.open_selected_from_api())

        self._last_rows = []
        top.columnconfigure(1, weight=1)

    def toggle_advanced(self):
        if self.advanced_visible.get():
            self.adv_frame.grid_forget()
            self.advanced_visible.set(False)
            self.adv_btn.configure(text="Show Advanced ▾")
        else:
            self.adv_frame.grid(row=2, column=0, columnspan=6, sticky="w", pady=(6, 0))
            self.advanced_visible.set(True)
            self.adv_btn.configure(text="Hide Advanced ▴")

    def on_ping(self):
        try:
            data = http_get_json(f"{API_BASE}/")
            self.status_var.set(data.get("status", "OK"))
        except Exception as e:
            messagebox.showerror("Ping failed", str(e))

    def on_clear(self):
        self.artist_var.set("")
        self.asset_var.set("")
        self.spnum_var.set("")
        self.notes_var.set("")
        self.client_name_var.set("")
        self.client_company_var.set("")
        self.status_var.set("Cleared.")
        self._set_rows([])

    def _build_params(self):
        params = {}
        if self.artist_var.get().strip():
            params["artist"] = self.artist_var.get().strip()
        if self.asset_var.get().strip():
            params["asset_type"] = self.asset_var.get().strip()
        if self.notes_var.get().strip():
            params["notes"] = self.notes_var.get().strip()
        if self.spnum_var.get().strip():
            params["sp_number"] = self.spnum_var.get().strip()

        if self.advanced_visible.get():
            if self.client_name_var.get().strip():
                params["client_name"] = self.client_name_var.get().strip()
            if self.client_company_var.get().strip():
                params["client_company_name"] = self.client_company_var.get().strip()

        return params

    def on_search(self):
        params = self._build_params()
        qs = urlencode(params, doseq=False)
        url = f"{API_BASE}/orders/search"
        if qs:
            url += "?" + qs

        self.status_var.set("Searching…")
        self.search_btn.configure(state="disabled")

        def worker():
            try:
                rows = http_get_json(url, timeout=15)
                if not isinstance(rows, list):
                    raise ValueError("Unexpected response; expected list.")
                self.after(0, lambda: self._finish_search(rows))
            except HTTPError as e:
                try:
                    body = e.read().decode("utf-8", errors="replace")
                except Exception:
                    body = str(e)
                self.after(0, lambda: self._fail_search(f"HTTP {e.code}: {body}"))
            except Exception as e:
                self.after(0, lambda: self._fail_search(str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_search(self, rows):
        self._set_rows(rows)
        self.status_var.set(f"Found {len(rows)} result(s).")
        self.search_btn.configure(state="normal")

    def _fail_search(self, msg):
        self.search_btn.configure(state="normal")
        self.status_var.set("Search failed.")
        messagebox.showerror("Search failed", msg)

    def _extract_sp_fields(self, r: dict):
        sp_number = ""
        sp_revision_of = ""
        sp = r.get("sp") if isinstance(r, dict) else None
        if isinstance(sp, dict):
            sp_number = sp.get("sp_number", "") or ""
            sp_revision_of = sp.get("revision_of", "") or ""
        return sp_number, sp_revision_of

    def _extract_revision_of(self, r: dict):
        order_rev = r.get("revision_of") if isinstance(r, dict) else None
        if order_rev:
            return order_rev

        _, sp_rev = self._extract_sp_fields(r)
        if sp_rev:
            return sp_rev

        return "NEW"

    def _set_rows(self, rows):
        self._last_rows = rows or []
        for item in self.tree.get_children():
            self.tree.delete(item)

        for idx, r in enumerate(self._last_rows):
            sp_number, _ = self._extract_sp_fields(r)
            revision_of = self._extract_revision_of(r)
            status = (r.get("status") or "draft").strip().upper()

            self.tree.insert(
                "",
                "end",
                iid=str(idx),
                values=(
                    r.get("artist", "") or "",
                    r.get("asset_type", "") or "",
                    (r.get("notes", "") or "").replace("\\n", " "),
                    sp_number,
                    revision_of,
                    status,
                ),
            )

    def _get_selected_row(self):
        sel = self.tree.selection()
        if not sel:
            return None
        try:
            idx = int(sel[0])
            return self._last_rows[idx]
        except Exception:
            return None

    def open_selected_from_api(self):
        row = self._get_selected_row()
        if not row:
            messagebox.showinfo("Open", "Select a row first.")
            return

        order_id = row.get("id")
        if not order_id:
            messagebox.showerror("Open", "Selected row is missing an id.")
            return

        OrderDetailsWindow(self, int(order_id))


if __name__ == "__main__":
    app = OrderSearchGUI()
    app.mainloop()
