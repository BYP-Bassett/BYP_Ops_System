from __future__ import annotations

import os
import hmac
import hashlib
import base64
import json
import urllib.parse
import urllib.request
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.routes.orders import router as orders_router

# DB / models (for auth)
from app.database.engine import SessionLocal
from app.models.users import User
from app.models.orders import Order
from app.models.clients import Client


app = FastAPI()

# ---- Sessions (Auth skeleton) ----
# For dev: set SESSION_SECRET_KEY in your .env (or system env) to something non-stupid.
# This is used to sign the session cookie.
SESSION_SECRET_KEY = (os.getenv("SESSION_SECRET_KEY") or "dev-not-secret-change-me").strip()

# 12 hours default session lifetime (seconds)
SESSION_MAX_AGE = int(os.getenv("SESSION_MAX_AGE", "43200"))

app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET_KEY,
    max_age=SESSION_MAX_AGE,
    same_site="lax",
    https_only=False,  # local dev
)


def _pbkdf2_sha256(password: str, salt_b64: str, iterations: int) -> str:
    salt = base64.b64decode(salt_b64.encode("utf-8"))
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return base64.b64encode(dk).decode("utf-8")


def _verify_password(stored: str | None, provided: str) -> bool:
    """
    Supported formats:
      - plain:<password>                (temporary bootstrap; replace later)
      - pbkdf2_sha256$<iters>$<saltb64>$<hashb64>
    """
    if not stored:
        return False

    stored = str(stored).strip()

    if stored.startswith("plain:"):
        return hmac.compare_digest(stored[len("plain:"):], provided)

    if stored.startswith("pbkdf2_sha256$"):
        try:
            _, iters_s, salt_b64, hash_b64 = stored.split("$", 3)
            iters = int(iters_s)
            calc = _pbkdf2_sha256(provided, salt_b64, iters)
            return hmac.compare_digest(calc, hash_b64)
        except Exception:
            return False

    # Unknown format
    return False


def _set_session(request: Request, user: User) -> None:
    request.session["user_id"] = int(user.id)
    request.session["username"] = str(user.username)
    request.session["rep_code"] = str(user.rep_code)
    request.session["rep_name"] = str(user.rep_name)
    request.session["role"] = str(user.role)
    request.session["is_active"] = bool(user.is_active)


def _clear_session(request: Request) -> None:
    try:
        request.session.clear()
    except Exception:
        # SessionMiddleware should make this safe, but don't crash the app over it.
        pass

# ---- Session guard: enforce disabled users are logged out everywhere ----
# If a user is toggled inactive in Admin, their existing sessions are rejected on the very next request.
@app.middleware("http")
async def _auth_session_guard(request: Request, call_next):
    # IMPORTANT: SessionMiddleware must be installed to use request.session.
    # If it's not in the scope yet, just pass through (prevents 500s on startup/misorder).
    if "session" not in request.scope:
        return await call_next(request)

    path = (request.url.path or "")

    # Allow public / bootstrap routes
    if (
        path.startswith("/login")
        or path.startswith("/web")
        or path.startswith("/static")
        or path in ("/health", "/favicon.ico")
    ):
        return await call_next(request)

    uid = request.session.get("user_id")

    # If we have a session, validate it against the DB every request (simple + reliable for now).
    if uid is not None:
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == int(uid)).first()
            if (not user) or (not bool(getattr(user, "is_active", True))):
                _clear_session(request)

                # API endpoints (desktop + web JS fetches) should get a hard 401.
                if path.startswith("/orders") or path == "/me":
                    return JSONResponse(status_code=401, content={"detail": "Not authenticated"})

                # Browser pages redirect to login.
                return RedirectResponse(url="/login?error=Session+expired", status_code=303)

            # Keep session fields in sync if admin changed role/rep info.
            try:
                request.session["username"] = str(user.username)
                request.session["rep_code"] = str(user.rep_code or "")
                request.session["rep_name"] = str(user.rep_name or "")
                request.session["role"] = str(user.role or "user")
                request.session["is_active"] = bool(getattr(user, "is_active", True))
            except Exception:
                pass
        finally:
            db.close()

    return await call_next(request)



@app.get("/me")
def me(request: Request):
    """
    Simple "who am I" endpoint for the web UI.
    Later: use this to power My Drafts and lock actions to a logged-in rep.
    """
    u = request.session.get("username")
    if not u:
        return {"authenticated": False}
    return {
        "authenticated": True,
        "user_id": request.session.get("user_id"),
        "username": request.session.get("username"),
        "rep_code": request.session.get("rep_code"),
        "rep_name": request.session.get("rep_name"),
        "role": request.session.get("role"),
        "is_active": request.session.get("is_active"),
    }


@app.get("/trello/card-url/{card_id}")
def trello_card_url(card_id: str, request: Request):
    # Must be logged in (same as the web UI)
    user = get_current_user_from_session(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    key = os.environ.get("TRELLO_KEY")
    token = os.environ.get("TRELLO_TOKEN")
    if not key or not token:
        raise HTTPException(status_code=500, detail="Trello not configured (missing TRELLO_KEY/TRELLO_TOKEN)")

    # Use Trello API to get a real usable URL (shortUrl is best).
    params = {
        "fields": "shortUrl,url",
        "key": key,
        "token": token,
    }
    api_url = "https://api.trello.com/1/cards/" + urllib.parse.quote(card_id) + "?" + urllib.parse.urlencode(params)

    try:
        req = urllib.request.Request(api_url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=12) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        data = json.loads(raw)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Trello lookup failed: {e}")

    url = (data or {}).get("shortUrl") or (data or {}).get("url")
    if not url:
        raise HTTPException(status_code=502, detail="Trello lookup failed: missing url")

    return {"url": url}


@app.get("/login", include_in_schema=False)
def login_form(request: Request, error: str | None = None):
    html = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>BYP Ops - Login</title>
  <style>
    body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; margin: 18px; max-width: 520px; }
    h1 { margin: 0 0 12px 0; font-size: 22px; }
    .card { border: 1px solid #ddd; border-radius: 12px; padding: 14px; background: #fff; }
    label { display:block; font-size: 13px; color: #444; margin-top: 10px; }
    input { width: 100%; padding: 10px 12px; border: 1px solid #ccc; border-radius: 10px; font-size: 14px; }
    button { margin-top: 14px; padding: 10px 14px; border: 1px solid #888; border-radius: 10px; background: #f4f4f4; cursor: pointer; }
    .err { color: #b00020; font-weight: 700; white-space: pre-wrap; margin-top: 10px; }
    .muted { color: #666; font-size: 13px; margin-top: 10px; }
    code { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace; font-size: 12px; }
  </style>
</head>
<body>
  <h1>Login</h1>
  <div class="card">
    <form method="post" action="/login">
      <label for="username">Username</label>
      <input id="username" name="username" autocomplete="username" />

      <label for="password">Password</label>
      <input id="password" name="password" type="password" autocomplete="current-password" />

      <button type="submit">Sign in</button>
      <div class="err">__ERROR__</div>
      <div class="muted">
        If your user has no password yet, set <code>password_hash</code> in the DB to <code>plain:&lt;yourpassword&gt;</code> temporarily.
      </div>
    </form>
  </div>
</body>
</html>
"""
    msg = (error or "").strip()
    html = html.replace("__ERROR__", msg)
    return HTMLResponse(content=html)


@app.post("/login", include_in_schema=False)
def login_post(request: Request, username: str = Form(...), password: str = Form(...)):
    u = (username or "").strip().lower()
    p = (password or "").strip()

    if not u or not p:
        return RedirectResponse(url="/login?error=Missing+username+or+password", status_code=303)

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == u).first()
        if not user:
            return RedirectResponse(url="/login?error=Bad+credentials", status_code=303)
        if not user.is_active:
            return RedirectResponse(url="/login?error=User+disabled", status_code=303)
        if not _verify_password(user.password_hash, p):
            return RedirectResponse(url="/login?error=Bad+credentials", status_code=303)

        _set_session(request, user)
        return RedirectResponse(url="/", status_code=303)
    finally:
        db.close()


@app.post("/logout", include_in_schema=False)
def logout(request: Request):
    _clear_session(request)
    return RedirectResponse(url="/login", status_code=303)

# ---- Auth helpers ----
def _is_logged_in(request: Request) -> bool:
    return bool(request.session.get("username"))


def _is_admin(request: Request) -> bool:
    return (str(request.session.get("role") or "").strip().lower() == "admin") and bool(request.session.get("username"))


def _require_login_or_redirect(request: Request):
    if not _is_logged_in(request):
        return RedirectResponse(url="/login", status_code=303)
    return None


def _require_admin_or_redirect(request: Request):
    if not _is_logged_in(request):
        return RedirectResponse(url="/login", status_code=303)
    if not _is_admin(request):
        return RedirectResponse(url="/?err=not_admin", status_code=303)
    return None


def _user_field(u: User, name: str, default: str = "") -> str:
    try:
        return str(getattr(u, name))
    except Exception:
        return default


def _client_field(c: Client, name: str, default: str = "") -> str:
    try:
        val = getattr(c, name)
        if val is None:
            return default
        return str(val)
    except Exception:
        return default


def _html_escape(s: str) -> str:
    return (
        (s or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#039;")
    )


# ---- Admin: Users page ----
@app.get("/admin/users", include_in_schema=False)
def admin_users_page(request: Request, msg: str | None = None, err: str | None = None):
    gate = _require_admin_or_redirect(request)
    if gate is not None:
        return gate

    db = SessionLocal()
    try:
        users = db.query(User).order_by(User.id.asc()).all()
    finally:
        db.close()

    rows = []
    for u in users:
        uid = _user_field(u, "id")
        username = _html_escape(_user_field(u, "username"))
        rep_code = _html_escape(_user_field(u, "rep_code"))
        rep_name = _html_escape(_user_field(u, "rep_name"))
        role = _html_escape(_user_field(u, "role"))
        active = bool(getattr(u, "is_active", True))

        email = ""
        if hasattr(u, "email"):
            email = _html_escape(_user_field(u, "email"))

        rows.append(
            f"""
            <tr>
              <td>{uid}</td>
              <td>{username}</td>
              <td>{rep_code}</td>
              <td>{rep_name}</td>
              <td>{email}</td>
              <td>
                <form method="post" action="/admin/users/{uid}/set_role" style="display:flex; gap:8px; align-items:center; margin:0;">
                  <select name="role" style="padding:6px 8px; border:1px solid #ccc; border-radius:10px;">
                    <option value="{role}" selected>{role}</option>
                    <option value="user">user</option>
                    <option value="admin">admin</option>
                  </select>
                  <button type="submit">Set</button>
                </form>
              </td>
              <td>{'YES' if active else 'NO'}</td>
              <td style="white-space:nowrap;">
                <form method="post" action="/admin/users/{uid}/toggle_active" style="display:inline; margin:0;">
                  <button type="submit">{'Disable' if active else 'Enable'}</button>
                </form>
                <form method="post" action="/admin/users/{uid}/set_password" style="display:inline; margin:0; margin-left:6px;">
                  <input name="password" placeholder="new password" style="padding:6px 8px; border:1px solid #ccc; border-radius:10px; width:160px;" />
                  <button type="submit">Set Pw</button>
                </form>
              </td>
            </tr>
            """
        )

    msg_txt = _html_escape((msg or "").strip())
    err_txt = _html_escape((err or "").strip())

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>BYP Ops — Admin Users</title>
  <style>
    body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; margin: 16px; max-width: 1200px; }}
    h1 {{ margin: 0 0 10px 0; font-size: 22px; }}
    .bar {{ display:flex; gap:10px; align-items:center; flex-wrap:wrap; margin: 10px 0 14px 0; }}
    a {{ color: inherit; }}
    button {{ padding: 8px 12px; border: 1px solid #888; border-radius: 10px; background: #f4f4f4; cursor: pointer; }}
    button:active {{ transform: translateY(1px); }}
    .btnlink {{ padding: 8px 12px; border: 1px solid #888; border-radius: 10px; background: #f4f4f4; cursor: pointer; text-decoration: none; display: inline-block; }}
    .btnlink:active {{ transform: translateY(1px); }}
    .card {{ border: 1px solid #ddd; border-radius: 12px; padding: 12px; background: #fff; }}
    .muted {{ color: #666; font-size: 13px; }}
    .ok {{ color: #0a7b27; font-weight: 700; white-space: pre-wrap; }}
    .err {{ color: #b00020; font-weight: 700; white-space: pre-wrap; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ padding: 8px; border-bottom: 1px solid #eee; text-align: left; vertical-align: top; font-size: 14px; }}
    th {{ font-size: 12px; color: #444; user-select: none; }}
    input {{ font-size: 14px; }}
    .grid {{ display:grid; grid-template-columns: 1fr; gap: 12px; }}
    @media (max-width: 900px) {{ .grid {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
  <h1>Admin — Users</h1>

  <div class="bar">
    <a href="/">← Back to Search</a>
    <a class="btnlink" href="/admin/deleted-orders">Deleted Orders</a>
    <a class="btnlink" href="/admin/clients">Client/Company List</a>

    <form method="post" action="/logout" style="margin:0;">
      <button type="submit">Logout</button>
    </form>
    <span class="muted">Logged in as: <b>{_html_escape(str(request.session.get("username") or ""))}</b></span>
  </div>

  <div class="ok">{msg_txt}</div>
  <div class="err">{err_txt}</div>

  <div class="card" style="margin-bottom:12px;">
    <h2 style="margin:0 0 10px 0; font-size:16px;">Add User</h2>
    <form method="post" action="/admin/users/add" style="display:flex; gap:10px; flex-wrap:wrap; align-items:flex-end;">
      <div>
        <div class="muted">Username</div>
        <input name="username" style="padding:8px 10px; border:1px solid #ccc; border-radius:10px; width:170px;" />
      </div>
      <div>
        <div class="muted">Rep Code</div>
        <input name="rep_code" style="padding:8px 10px; border:1px solid #ccc; border-radius:10px; width:90px;" />
      </div>
      <div>
        <div class="muted">Rep Name</div>
        <input name="rep_name" style="padding:8px 10px; border:1px solid #ccc; border-radius:10px; width:220px;" />
      </div>
      <div>
        <div class="muted">Email (optional)</div>
        <input name="email" style="padding:8px 10px; border:1px solid #ccc; border-radius:10px; width:240px;" />
      </div>
      <div>
        <div class="muted">Role</div>
        <select name="role" style="padding:8px 10px; border:1px solid #ccc; border-radius:10px; width:120px;">
          <option value="user" selected>user</option>
          <option value="admin">admin</option>
        </select>
      </div>
      <div>
        <div class="muted">Password</div>
        <input name="password" placeholder="(sets plain:password)" style="padding:8px 10px; border:1px solid #ccc; border-radius:10px; width:220px;" />
      </div>
      <button type="submit">Add</button>
    </form>
    <div class="muted" style="margin-top:10px;">
      Passwords are bootstrapped as <code>plain:&lt;password&gt;</code> for now. We'll harden later.
    </div>
  </div>

  <div class="card">
    <h2 style="margin:0 0 10px 0; font-size:16px;">Users</h2>
    <table>
      <thead>
        <tr>
          <th>ID</th>
          <th>Username</th>
          <th>Rep Code</th>
          <th>Rep Name</th>
          <th>Email</th>
          <th>Role</th>
          <th>Active</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        {''.join(rows)}
      </tbody>
    </table>
  </div>
</body>
</html>
"""
    return HTMLResponse(content=html)


@app.post("/admin/users/add", include_in_schema=False)
def admin_users_add(
    request: Request,
    username: str = Form(...),
    rep_code: str = Form(""),
    rep_name: str = Form(""),
    email: str = Form(""),
    role: str = Form("user"),
    password: str = Form(""),
):
    gate = _require_admin_or_redirect(request)
    if gate is not None:
        return gate

    u = (username or "").strip().lower()
    if not u:
        return RedirectResponse(url="/admin/users?err=Username+required", status_code=303)

    rc = (rep_code or "").strip()
    rn = (rep_name or "").strip()
    em = (email or "").strip()
    r = (role or "user").strip().lower()
    if r not in ("user", "admin"):
        r = "user"

    ph = None
    pw = (password or "").strip()
    if pw:
        ph = "plain:" + pw

    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.username == u).first()
        if existing:
            return RedirectResponse(url="/admin/users?err=Username+already+exists", status_code=303)

        new_user = User(
            username=u,
            rep_code=rc,
            rep_name=rn,
            role=r,
            is_active=True,
            password_hash=ph,
        )

        # Optional email field if model supports it
        if hasattr(new_user, "email"):
            setattr(new_user, "email", em)

        db.add(new_user)
        db.commit()

        return RedirectResponse(url="/admin/users?msg=User+added", status_code=303)
    except Exception as e:
        db.rollback()
        return RedirectResponse(url="/admin/users?err=" + _url_q(str(e)), status_code=303)
    finally:
        db.close()


def _url_q(s: str) -> str:
    # minimal safe query encoding (spaces only) to avoid importing urllib for one line
    return _html_escape(str(s)).replace(" ", "+")


@app.post("/admin/users/{user_id}/toggle_active", include_in_schema=False)
def admin_users_toggle_active(request: Request, user_id: int):
    gate = _require_admin_or_redirect(request)
    if gate is not None:
        return gate

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return RedirectResponse(url="/admin/users?err=User+not+found", status_code=303)

        # Prevent locking yourself out mid-flight (you can still do it manually if you really want)
        me_id = request.session.get("user_id")
        if me_id is not None and int(me_id) == int(user_id) and bool(getattr(user, "is_active", True)):
            return RedirectResponse(url="/admin/users?err=Nice+try.+Don%27t+disable+yourself", status_code=303)

        cur = bool(getattr(user, "is_active", True))
        setattr(user, "is_active", (not cur))
        db.commit()
        return RedirectResponse(url="/admin/users?msg=User+updated", status_code=303)
    except Exception as e:
        db.rollback()
        return RedirectResponse(url="/admin/users?err=" + _url_q(str(e)), status_code=303)
    finally:
        db.close()


@app.post("/admin/users/{user_id}/set_role", include_in_schema=False)
def admin_users_set_role(request: Request, user_id: int, role: str = Form(...)):
    gate = _require_admin_or_redirect(request)
    if gate is not None:
        return gate

    r = (role or "user").strip().lower()
    if r not in ("user", "admin"):
        r = "user"

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return RedirectResponse(url="/admin/users?err=User+not+found", status_code=303)
        setattr(user, "role", r)
        db.commit()
        return RedirectResponse(url="/admin/users?msg=Role+updated", status_code=303)
    except Exception as e:
        db.rollback()
        return RedirectResponse(url="/admin/users?err=" + _url_q(str(e)), status_code=303)
    finally:
        db.close()


@app.post("/admin/users/{user_id}/set_password", include_in_schema=False)
def admin_users_set_password(request: Request, user_id: int, password: str = Form(...)):
    gate = _require_admin_or_redirect(request)
    if gate is not None:
        return gate

    pw = (password or "").strip()
    if not pw:
        return RedirectResponse(url="/admin/users?err=Password+required", status_code=303)

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return RedirectResponse(url="/admin/users?err=User+not+found", status_code=303)
        setattr(user, "password_hash", "plain:" + pw)
        db.commit()
        return RedirectResponse(url="/admin/users?msg=Password+updated", status_code=303)
    except Exception as e:
        db.rollback()
        return RedirectResponse(url="/admin/users?err=" + _url_q(str(e)), status_code=303)
    finally:
        db.close()






# ---- Admin: Client / Company List ----

@app.get("/admin/clients.json", include_in_schema=False)
def admin_clients_json(request: Request, q: str | None = None, limit: int = 500):
    gate = _require_admin_or_redirect(request)
    if gate is not None:
        # fetch() callers need JSON, not HTML redirects.
        try:
            from starlette.responses import RedirectResponse as _RR
            if isinstance(gate, _RR):
                return JSONResponse(content={"detail": "Not authenticated"}, status_code=401)
        except Exception:
            pass
        return gate

    from sqlalchemy import or_

    q_txt = (q or "").strip()
    db = SessionLocal()
    try:
        query = db.query(Client)
        if q_txt:
            like = f"%{q_txt}%"
            try:
                query = query.filter(or_(Client.client_name.ilike(like), Client.company_name.ilike(like)))
            except Exception:
                query = query.filter(Client.client_name.ilike(like))

        query = query.order_by(Client.client_name.asc())
        clients = query.limit(int(limit)).all()

        items = []
        for c in clients:
            items.append({
                "id": int(getattr(c, "id")),
                "client_name": str(getattr(c, "client_name") or ""),
                "company_name": (getattr(c, "company_name", None) if getattr(c, "company_name", None) is not None else ""),
            })

        try:
            count_q = db.query(Client)
            if q_txt:
                like = f"%{q_txt}%"
                try:
                    count_q = count_q.filter(or_(Client.client_name.ilike(like), Client.company_name.ilike(like)))
                except Exception:
                    count_q = count_q.filter(Client.client_name.ilike(like))
            count = int(count_q.count())
        except Exception:
            count = int(len(items))

        return JSONResponse(content={"value": items, "Count": count})
    finally:
        db.close()


@app.get("/admin/clients", include_in_schema=False)
def admin_clients_page(request: Request, msg: str | None = None, err: str | None = None):
    gate = _require_admin_or_redirect(request)
    if gate is not None:
        return gate

    username = (request.session.get("username") or "admin")

    # Bootstrap initial data server-side so the page never appears blank.
    db = SessionLocal()
    try:
        try:
            clients = db.query(Client).order_by(Client.client_name.asc()).limit(500).all()
            boot_items = [{
                "id": int(getattr(c, "id")),
                "client_name": str(getattr(c, "client_name") or ""),
                "company_name": (getattr(c, "company_name", None) if getattr(c, "company_name", None) is not None else ""),
            } for c in clients]
            boot_count = int(db.query(Client).count())
        except Exception:
            boot_items = []
            boot_count = 0
    finally:
        db.close()

    clients_bootstrap_json = json.dumps({"value": boot_items, "Count": boot_count}).replace("</", "<\\/")

    msg_html = ""
    err_html = ""
    if msg:
        msg_html = f"<div class='ok'>{_html_escape(msg)}</div>"
    if err:
        err_html = f"<div class='err'>{_html_escape(err)}</div>"

    html_tmpl = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>BYP Ops — Admin Clients</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 16px; font-size: 14px; font-weight: normal; }
    .topbar { display:flex; gap:10px; align-items:center; margin-bottom:12px; flex-wrap:wrap; }
    .btnlink { display:inline-block; padding:6px 10px; border:1px solid #999; border-radius:6px; text-decoration:none; color:#000; background:#f3f3f3; }
    .btnlink:hover { background:#e9e9e9; }
    .ok { background:#eaffea; border:1px solid #7ad67a; padding:8px 10px; border-radius:8px; margin:10px 0; }
    .err { background:#ffecec; border:1px solid #d67a7a; padding:8px 10px; border-radius:8px; margin:10px 0; }
    .muted { color:#666; font-size:12px; }
    .grid { display:grid; grid-template-columns: 1fr 360px; gap:14px; align-items:start; }
    .list { border:1px solid #ddd; border-radius:12px; overflow:hidden; }
    .listHeader { display:flex; gap:10px; align-items:center; padding:10px; border-bottom:1px solid #eee; background:#fafafa; }
    .listHeader input { flex: 1; padding:8px; border:1px solid #ccc; border-radius:8px; }
    .listHeader button { padding:8px 10px; border:1px solid #999; border-radius:8px; background:#f3f3f3; cursor:pointer; }
    .rows { max-height: 70vh; overflow:auto; }
    .row { display:grid; grid-template-columns: 70px 1fr 1fr; gap:10px; padding:6px 10px; border-bottom:1px solid #f0f0f0; cursor:pointer; font-size: 13px; line-height: 1.2; align-items: center; }
    .row:hover { background:#f7f7f7; }
    .row.sel { background:#dbeafe; }
    .cid { color:#666; font-size:12px; }
    .cname { font-weight: normal; }
    .comp { color:#333; }
    .panel { border:1px solid #ddd; border-radius:12px; padding:12px; }
    .panel h2 { margin:0 0 10px 0; font-size:16px; }
    .field { margin-bottom:10px; }
    .field label { display:block; font-size:12px; color:#666; margin-bottom:4px; }
    .field input { width:100%; padding:8px; border:1px solid #ccc; border-radius:8px; }
    .pill { display:inline-block; padding:2px 8px; border:1px solid #ccc; border-radius:999px; background:#f6f6f6; font-size:12px; }
    .danger { background:#fee2e2 !important; border-color:#ef4444 !important; }
    .ctx { position:fixed; display:none; z-index:9999; background:#fff; border:1px solid #ccc; border-radius:10px; overflow:hidden; box-shadow:0 10px 28px rgba(0,0,0,0.15); }
    .ctx button { width:100%; border:0; background:#fff; padding:10px 12px; text-align:left; cursor:pointer; }
    .ctx button:hover { background:#f5f5f5; }
  
/* Tighten client list row height */
#clientsTable th, #clientsTable td {
  padding-top: 2px !important;
  padding-bottom: 2px !important;
  line-height: 1.05 !important;
}
#clientsTable input[type="text"] {
  padding-top: 2px !important;
  padding-bottom: 2px !important;
  line-height: 1.05 !important;
}
</style>
</head>
<body>
  <div class="topbar">
    <a class="btnlink" href="/admin/users">Users</a>
    <a class="btnlink" href="/admin/deleted-orders">Deleted Orders</a>
    <a class="btnlink" href="/admin/clients">Client/Company List</a>
    <span class="muted">Signed in as <b>__USERNAME__</b></span>
  </div>

  __MSG_BLOCK__
  __ERR_BLOCK__

  <div class="grid">
    <div class="list">
      <div class="listHeader">
        <input id="q" type="text" placeholder="Filter (name or company)..." />
        <button id="refreshBtn" type="button">Refresh</button>
        <span class="muted" id="countLbl"></span>
      </div>
      <div class="rows" id="rows"></div>
    </div>

    <div class="panel">
      <h2>Edit</h2>
      <div class="field">
        <label>ID</label>
        <div><span class="pill" id="editId">—</span></div>
      </div>
      <div class="field">
        <label>Client Name</label>
        <input id="editClient" type="text" />
      </div>
      <div class="field">
        <label>Company Name</label>
        <input id="editCompany" type="text" />
      </div>
      <div style="display:flex; gap:10px; align-items:center; flex-wrap:wrap;">
        <button id="saveBtn" type="button" disabled>Save</button>
        <button id="clearBtn" type="button">Clear</button>
        <span class="muted" id="editMsg"></span>
      </div>
      <div style="margin-top:14px;" class="muted">
        Tips: Click to select • Ctrl+Click multi-select • Shift+Click range • Right-click for menu
      </div>
    </div>
  </div>

  <div class="ctx" id="ctxMenu">
    <button id="ctxDelete" class="danger" type="button">Delete selected…</button>
  </div>

<script>
window.__CLIENTS_BOOTSTRAP__ = __CLIENTS_BOOTSTRAP_JSON__;
(function(){
  var rowsEl = document.getElementById("rows");
  var qEl = document.getElementById("q");
  var refreshBtn = document.getElementById("refreshBtn");
  var countLbl = document.getElementById("countLbl");

  var editIdEl = document.getElementById("editId");
  var editClientEl = document.getElementById("editClient");
  var editCompanyEl = document.getElementById("editCompany");
  var saveBtn = document.getElementById("saveBtn");
  var clearBtn = document.getElementById("clearBtn");
  var editMsg = document.getElementById("editMsg");

  var ctx = document.getElementById("ctxMenu");
  var ctxDelete = document.getElementById("ctxDelete");

  var items = [];
  var selected = [];
  var anchorIndex = null;
  var focusedId = null;

  function esc(s){
    return String(s || "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
  }
  function setEdit(id){
    focusedId = id;
    editMsg.textContent = "";
    if (!id){
      editIdEl.textContent = "—";
      editClientEl.value = "";
      editCompanyEl.value = "";
      saveBtn.disabled = true;
      return;
    }
    var it = items.find(function(x){ return String(x.id) === String(id); });
    if (!it){
      editIdEl.textContent = "—";
      editClientEl.value = "";
      editCompanyEl.value = "";
      saveBtn.disabled = true;
      return;
    }
    editIdEl.textContent = String(it.id);
    editClientEl.value = it.client_name || "";
    editCompanyEl.value = it.company_name || "";
    saveBtn.disabled = true;
  }
  function render(){
    rowsEl.innerHTML = "";
    for (var i=0;i<items.length;i++){
      var it = items[i];
      var div = document.createElement("div");
      div.className = "row";
      div.dataset.id = String(it.id);
      div.dataset.index = String(i);

      if (selected.indexOf(String(it.id)) >= 0){
        div.className += " sel";
      }

      var cid = document.createElement("div");
      cid.className = "cid";
      cid.textContent = String(it.id);

      var cn = document.createElement("div");
      cn.className = "cname";
      cn.textContent = (it.client_name || "");

      var comp = document.createElement("div");
      comp.className = "comp";
      comp.textContent = it.company_name || "";

      div.appendChild(cid);
      div.appendChild(cn);
      div.appendChild(comp);

      div.addEventListener("click", function(ev){
        var id = this.dataset.id;
        var idx = parseInt(this.dataset.index, 10);

        if (ev.shiftKey && anchorIndex !== null){
          var a = anchorIndex;
          var b = idx;
          if (a > b){ var t=a; a=b; b=t; }
          var next = [];
          for (var k=a;k<=b;k++){
            next.push(String(items[k].id));
          }
          selected = next;
        } else if (ev.ctrlKey || ev.metaKey){
          var p = selected.indexOf(String(id));
          if (p >= 0) selected.splice(p,1);
          else selected.push(String(id));
          anchorIndex = idx;
        } else {
          selected = [String(id)];
          anchorIndex = idx;
        }

        setEdit(id);
        render();
      });

      div.addEventListener("contextmenu", function(ev){
        ev.preventDefault();
        var id = this.dataset.id;
        var idx = parseInt(this.dataset.index, 10);

        if (selected.indexOf(String(id)) < 0){
          selected = [String(id)];
          anchorIndex = idx;
          setEdit(id);
          render();
        }
        showCtx(ev.clientX, ev.clientY);
      });

      rowsEl.appendChild(div);
    }

    countLbl.textContent = items.length ? (items.length + " clients") : "0 clients";
    ctxDelete.disabled = selected.length === 0;
  }

  function hideCtx(){ ctx.style.display = "none"; }
  function showCtx(x,y){
    ctx.style.display = "block";
    ctx.style.left = x + "px";
    ctx.style.top = y + "px";
  }

  document.addEventListener("click", function(){ hideCtx(); });
  window.addEventListener("scroll", function(){ hideCtx(); }, true);
  window.addEventListener("resize", function(){ hideCtx(); });

  function load(){
    hideCtx();
    rowsEl.innerHTML = "<div class='row'><span class='muted'>Loading…</span></div>";
    var q = qEl.value || "";
    var url = "/admin/clients.json";
    if (q){ url += "?q=" + encodeURIComponent(q); }
    fetch(url, { credentials: "same-origin" })
      .then(function(res){ return res.text().then(function(t){ return {ok:res.ok, status:res.status, text:t}; }); })
      .then(function(r){
        if (!r.ok){
          rowsEl.innerHTML = "<div class='row'><b>HTTP " + r.status + "</b><div style='margin-left:10px;white-space:pre-wrap;'>" + esc(r.text) + "</div></div>";
          return;
        }
        var data = null;
        try { data = JSON.parse(r.text); } catch(e) {}
        var arr = null;
        if (Array.isArray(data)) arr = data;
        else if (data && Array.isArray(data.value)) arr = data.value;

        if (!arr){
          var t = (r.text || "");
          var looksHtml = (t.indexOf("<!doctype") >= 0) || (t.indexOf("<html") >= 0);
          if (looksHtml){
            rowsEl.innerHTML = "<div class='row'><b>Session expired.</b> Reloading…</div>";
            window.location.reload();
            return;
          }
          rowsEl.innerHTML = "<div class='row'><b>Bad JSON</b><div style='margin-left:10px;white-space:pre-wrap;max-height:140px;overflow:auto;'>" + esc(t.slice(0, 2000)) + "</div></div>";
          return;
        }
        items = arr;

        var existing = {};
        for (var i=0;i<items.length;i++){ existing[String(items[i].id)] = true; }
        selected = selected.filter(function(id){ return existing[String(id)]; });

        if (focusedId && !existing[String(focusedId)]) focusedId = null;
        if (focusedId) setEdit(focusedId);
        else if (selected.length === 1) setEdit(selected[0]);
        else setEdit(null);

        render();
      })
      .catch(function(err){
        rowsEl.innerHTML = "<div class='row'>Load failed: " + esc(String(err)) + "</div>";
      });
  }

  refreshBtn.addEventListener("click", load);
  qEl.addEventListener("keydown", function(ev){
    if (ev.key === "Enter"){ load(); }
  });

  function setSaveEnabled(){
    if (!focusedId){ saveBtn.disabled = true; return; }
    var it = items.find(function(x){ return String(x.id) === String(focusedId); });
    if (!it){ saveBtn.disabled = true; return; }
    var changed = (String(editClientEl.value||"") !== String(it.client_name||"")) || (String(editCompanyEl.value||"") !== String(it.company_name||""));
    saveBtn.disabled = !changed;
  }
  editClientEl.addEventListener("input", setSaveEnabled);
  editCompanyEl.addEventListener("input", setSaveEnabled);

  clearBtn.addEventListener("click", function(){
    selected = [];
    anchorIndex = null;
    setEdit(null);
    render();
  });

  saveBtn.addEventListener("click", function(){
    if (!focusedId) return;

    var form = new FormData();
    form.append("client_name", editClientEl.value || "");
    form.append("company_name", editCompanyEl.value || "");

    saveBtn.disabled = true;
    editMsg.textContent = "Saving…";

    fetch("/admin/clients/" + encodeURIComponent(String(focusedId)) + "/update", {
      method: "POST",
      body: form,
      credentials: "same-origin"
    })
    .then(function(res){ return res.text().then(function(t){ return {ok:res.ok, status:res.status, text:t}; }); })
    .then(function(r){
      if (!r.ok){
        editMsg.textContent = "HTTP " + r.status;
        alert("Save failed (HTTP " + r.status + "):\n\n" + r.text);
        return;
      }
      editMsg.textContent = "Saved.";
      load();
    })
    .catch(function(err){
      editMsg.textContent = "Save failed.";
      alert("Save failed:\n\n" + String(err));
    });
  });

  ctxDelete.addEventListener("click", function(){
    hideCtx();
    if (!selected.length) return;

    var n = selected.length;
    if (!confirm("Delete " + n + " selected client(s)?\n\nFinalized orders will block deletion (we'll skip those).")) return;

    fetch("/admin/clients/delete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids: selected }),
      credentials: "same-origin"
    })
    .then(function(res){ return res.text().then(function(t){ return {ok:res.ok, status:res.status, text:t}; }); })
    .then(function(r){
      if (!r.ok){
        alert("Delete failed (HTTP " + r.status + "):\n\n" + r.text);
        return;
      }
      var data = null;
      try { data = JSON.parse(r.text); } catch(e) {}
      if (!data){
        alert("Delete response was not JSON:\n\n" + r.text);
        load();
        return;
      }
      var msg = "";
      if (data.deleted && data.deleted.length){
        msg += "Deleted: " + data.deleted.join(", ") + "\n";
      }
      if (data.blocked && data.blocked.length){
        msg += "\nSkipped (finalized orders): " + data.blocked.map(function(x){ return x.id; }).join(", ") + "\n";
      }
      if (data.not_found && data.not_found.length){
        msg += "\nNot found: " + data.not_found.join(", ") + "\n";
      }
      alert(msg || "Done.");
      selected = [];
      anchorIndex = null;
      focusedId = null;
      load();
    })
    .catch(function(err){
      alert("Delete failed:\n\n" + String(err));
    });
  });

  // Boot immediately, then auto-load from JSON.
  try {
    var boot = window.__CLIENTS_BOOTSTRAP__;
    if (boot && boot.value && Array.isArray(boot.value)) {
      items = boot.value;
      selected = [];
      anchorIndex = null;
      focusedId = null;
      render();
    }
  } catch(e) {}

  try { setTimeout(load, 0); } catch(e) {}
})();
</script>
</body>
</html>"""

    html = (
        html_tmpl.replace("__USERNAME__", username)
                 .replace("__MSG_BLOCK__", msg_html)
                 .replace("__ERR_BLOCK__", err_html)
                 .replace("__CLIENTS_BOOTSTRAP_JSON__", clients_bootstrap_json)
    )
    return HTMLResponse(content=html)

@app.post("/admin/clients/{client_id}/update", include_in_schema=False)
def admin_clients_update(
    request: Request,
    client_id: int,
    client_name: str = Form(...),
    company_name: str = Form(""),
    is_active: str | None = Form(None),
):
    gate = _require_admin_or_redirect(request)
    if gate is not None:
        return gate

    cn = (client_name or "").strip()
    co = (company_name or "").strip()
    active = bool(is_active is not None)

    if not cn:
        return RedirectResponse(url="/admin/clients?err=" + urllib.parse.quote("Client name cannot be blank."), status_code=303)

    db = SessionLocal()
    try:
        c = db.query(Client).filter(Client.id == client_id).first()
        if not c:
            return RedirectResponse(url="/admin/clients?err=" + urllib.parse.quote("Client not found."), status_code=303)

        c.client_name = cn
        c.company_name = (co or None)
        c.is_active = active

        db.add(c)
        db.commit()
    except Exception as e:
        db.rollback()
        return RedirectResponse(url="/admin/clients?err=" + urllib.parse.quote(f"Update failed: {e}"), status_code=303)
    finally:
        db.close()

    return RedirectResponse(url="/admin/clients?msg=" + urllib.parse.quote("Saved."), status_code=303)


@app.post("/admin/clients/{client_id}/toggle", include_in_schema=False)
def admin_clients_toggle(request: Request, client_id: int):
    gate = _require_admin_or_redirect(request)
    if gate is not None:
        return gate

    db = SessionLocal()
    try:
        c = db.query(Client).filter(Client.id == client_id).first()
        if not c:
            return RedirectResponse(url="/admin/clients?err=" + urllib.parse.quote("Client not found."), status_code=303)

        c.is_active = not bool(getattr(c, "is_active", True))
        db.add(c)
        db.commit()
    except Exception as e:
        db.rollback()
        return RedirectResponse(url="/admin/clients?err=" + urllib.parse.quote(f"Toggle failed: {e}"), status_code=303)
    finally:
        db.close()

    return RedirectResponse(url="/admin/clients?msg=" + urllib.parse.quote("Updated."), status_code=303)


# ---- Admin: Deleted Orders (web) ----
@app.get("/admin/deleted-orders", include_in_schema=False)
def admin_deleted_orders_page(request: Request, msg: str | None = None, err: str | None = None):
    gate = _require_admin_or_redirect(request)
    if gate is not None:
        return gate

    def _safe_sp_number(order_obj) -> str:
        """Return an SP# (e.g., SP000133) if available; otherwise empty string."""
        try:
            # Some schemas may denormalize SP onto the order.
            v = getattr(order_obj, "sp_number", None)
            if v:
                return str(v)
        except Exception:
            pass
        try:
            sp_obj = getattr(order_obj, "sp", None)
            if sp_obj is not None:
                v = getattr(sp_obj, "sp_number", None)
                if v:
                    return str(v)
        except Exception:
            pass
        return ""

    def fmt_dt(v):
        if not v:
            return ""
        s = str(v)
        return s.replace("T", " ")

    rows = []
    db = SessionLocal()
    try:
        # newest first
        q = db.query(Order).filter(getattr(Order, "is_deleted") == True)  # noqa: E712
        if hasattr(Order, "deleted_at"):
            q = q.order_by(getattr(Order, "deleted_at").desc(), getattr(Order, "id").desc())
        else:
            q = q.order_by(getattr(Order, "id").desc())
        deleted = q.limit(500).all()

        for o in deleted:
            sp_number = _html_escape(_safe_sp_number(o))
            oid = getattr(o, "id", "")
            artist = _html_escape(str(getattr(o, "artist", "") or ""))
            asset = _html_escape(str(getattr(o, "asset_type", "") or ""))
            status = _html_escape(str(getattr(o, "status", "") or ""))
            deleted_at = _html_escape(fmt_dt(getattr(o, "deleted_at", "")))
            deleted_by = _html_escape(str(getattr(o, "deleted_by", "") or ""))

            rows.append(
                f"""
                <tr>
                  <td class=\"nowrap\">{sp_number}</td>
                  <td>{oid}</td>
                  <td>{artist}</td>
                  <td>{asset}</td>
                  <td>{status}</td>
                  <td>{deleted_at}</td>
                  <td>{deleted_by}</td>
                  <td style=\"white-space:nowrap;\">
                    <a class=\"btnlink\" href=\"/order/{oid}\" target=\"_blank\" rel=\"noopener\">View</a>
                    <form method=\"post\" action=\"/admin/deleted-orders/{oid}/restore\" style=\"display:inline; margin:0; margin-left:6px;\" onsubmit=\"return confirm('Restore order {oid}?');\">
                      <button type=\"submit\">Restore</button>
                    </form>
                  </td>
                </tr>
                """
            )
    finally:
        db.close()

    username = _html_escape(str(request.session.get("username") or ""))
    msg_txt = _html_escape((msg or "").strip())
    err_txt = _html_escape((err or "").strip())

    body_rows = "\n".join(rows) if rows else "<tr><td colspan=\"8\" class=\"muted\">(none)</td></tr>"

    html = f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width,initial-scale=1\" />
  <title>BYP Ops — Deleted Orders</title>
  <style>
    body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; margin: 16px; max-width: 1200px; }}
    h1 {{ margin: 0 0 10px 0; font-size: 22px; }}
    .bar {{ display:flex; gap:10px; align-items:center; flex-wrap:wrap; margin: 10px 0 14px 0; }}
    a {{ color: inherit; }}
    button {{ padding: 8px 12px; border: 1px solid #888; border-radius: 10px; background: #f4f4f4; cursor: pointer; }}
    button:active {{ transform: translateY(1px); }}
    .btnlink {{ padding: 8px 12px; border: 1px solid #888; border-radius: 10px; background: #f4f4f4; cursor: pointer; text-decoration: none; display: inline-block; }}
    .btnlink:active {{ transform: translateY(1px); }}
    .card {{ border: 1px solid #ddd; border-radius: 12px; padding: 12px; background: #fff; }}
    .muted {{ color: #666; font-size: 13px; }}
    .ok {{ color: #0a7b27; font-weight: 700; white-space: pre-wrap; }}
    .err {{ color: #b00020; font-weight: 700; white-space: pre-wrap; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ padding: 8px; border-bottom: 1px solid #eee; text-align: left; vertical-align: top; font-size: 14px; }}
    th {{ font-size: 12px; color: #444; user-select: none; }}
    .nowrap {{ white-space: nowrap; }}
  </style>
</head>
<body>
  <h1>Admin — Deleted Orders</h1>

  <div class=\"bar\">
    <a class=\"btnlink\" href=\"/admin/users\">← Admin Users</a>
    <a class=\"btnlink\" href=\"/\">Search</a>
    <form method=\"post\" action=\"/logout\" style=\"margin:0;\">
      <button type=\"submit\">Logout</button>
    </form>
    <span class=\"muted\">Logged in as: <b>{username}</b></span>
  </div>

  <div class=\"ok\">{msg_txt}</div>
  <div class=\"err\">{err_txt}</div>

  <div class=\"card\">
    <div class=\"muted\" style=\"margin-bottom:10px;\">Newest first. Restore is idempotent. (Restore clears deleted_at/deleted_by so the order returns to normal search.)</div>
    <table>
      <thead>
        <tr>
          <th class=\"nowrap\">SP#</th>
          <th>ID</th>
          <th>Artist</th>
          <th>Asset</th>
          <th>Status</th>
          <th>Deleted At</th>
          <th>Deleted By</th>
          <th class=\"nowrap\">Actions</th>
        </tr>
      </thead>
      <tbody>
        {body_rows}
      </tbody>
    </table>
  </div>
</body>
</html>
"""

    return HTMLResponse(content=html)


@app.post("/admin/clients/delete", include_in_schema=False)
async def admin_clients_delete(request: Request):
    gate = _require_admin_or_redirect(request)
    if gate is not None:
        return gate

    try:
        data = await request.json()
    except Exception:
        data = {}

    ids = data.get("ids") or []
    # normalize ids to ints where possible
    norm_ids: list[int] = []
    for x in ids:
        try:
            norm_ids.append(int(str(x)))
        except Exception:
            continue

    deleted: list[int] = []
    not_found: list[int] = []
    blocked: list[dict] = []

    db = SessionLocal()
    try:
        for cid in norm_ids:
            c = db.query(Client).filter(Client.id == cid).first()
            if not c:
                not_found.append(cid)
                continue

            # Block deletion if any finalized orders reference this client_name
            try:
                cname = str(getattr(c, "client_name") or "")
                if cname:
                    q = db.query(Order).filter(
                        Order.client_name == cname,
                        Order.status == "finalized",
                        Order.is_deleted == False,  # noqa: E712
                    )
                    if q.count() > 0:
                        blocked.append({"id": cid, "client_name": cname})
                        continue
            except Exception:
                # If we can't verify, be conservative and block
                blocked.append({"id": cid, "client_name": str(getattr(c, "client_name") or "")})
                continue

            db.delete(c)
            deleted.append(cid)

        db.commit()
    except Exception as e:
        db.rollback()
        return JSONResponse({"error": str(e)}, status_code=500)
    finally:
        db.close()

    return JSONResponse({"deleted": deleted, "blocked": blocked, "not_found": not_found})



@app.post("/admin/deleted-orders/{order_id}/restore", include_in_schema=False)
def admin_deleted_orders_restore(request: Request, order_id: int):
    gate = _require_admin_or_redirect(request)
    if gate is not None:
        return gate

    db = SessionLocal()
    try:
        o = db.query(Order).filter(Order.id == order_id).first()
        if not o:
            return RedirectResponse(url="/admin/deleted-orders?err=Order+not+found", status_code=303)

        if not bool(getattr(o, "is_deleted", False)):
            return RedirectResponse(url="/admin/deleted-orders?msg=Order+already+active", status_code=303)

        # Capture deletion metadata for the success message (we clear it on restore so it returns to normal search).
        prev_deleted_at = getattr(o, "deleted_at", None)
        prev_deleted_by = getattr(o, "deleted_by", None)

        setattr(o, "is_deleted", False)
        if hasattr(o, "deleted_at"):
            setattr(o, "deleted_at", None)
        if hasattr(o, "deleted_by"):
            setattr(o, "deleted_by", None)
        if hasattr(o, "deleted_by_user_id"):
            setattr(o, "deleted_by_user_id", None)

        db.commit()

        # Keep the UI message useful but short.
        msg = f"Restored order {order_id}"
        if prev_deleted_by:
            msg += f" (was deleted by {prev_deleted_by})"
        return RedirectResponse(url="/admin/deleted-orders?msg=" + _url_q(msg), status_code=303)
    except Exception as e:
        db.rollback()
        return RedirectResponse(url="/admin/deleted-orders?err=" + _url_q(str(e)), status_code=303)
    finally:
        db.close()


# API routes
app.include_router(orders_router)

# --- Web UI (vanilla HTML/JS served by FastAPI) ---
APP_DIR = Path(__file__).resolve().parent
WEB_DIR = APP_DIR / "web"

# Serve static assets (JS/CSS) from /web/*
# Example: /web/app.js
app.mount("/web", StaticFiles(directory=WEB_DIR), name="web")
# Back-compat: older web builds referenced /static/* for assets.
app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


@app.get("/", include_in_schema=False)
def web_root(request: Request):
    # If not logged in, send to login.
    if not request.session.get("username"):
        return RedirectResponse(url="/login", status_code=303)

    # Browser UI
    return FileResponse(WEB_DIR / "index.html")


@app.get("/order/{order_id}", include_in_schema=False)
def web_order_detail(request: Request, order_id: int):
    # If not logged in, send to login.
    if not request.session.get("username"):
        return RedirectResponse(url="/login", status_code=303)

    # HTML page that fetches /orders/{id} JSON and renders it (human-friendly).
    # Supports inline edit + Save for a small set of fields + Revise/Add'l Vers + Finalize/Unfinalize actions.
    # NOTE: Keep JS syntax conservative (avoid optional-chaining) to support older mobile browsers.
    html = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>BYP Ops — Order __ORDER_ID__</title>
  <style>
    :root { color-scheme: light; }
    body {
      font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
      margin: 16px;
      max-width: 1100px;
    }
    h1 { margin: 0 0 8px 0; font-size: 22px; }
    h2 { margin: 0 0 10px 0; font-size: 16px; }
    .bar {
      display:flex; gap:10px; align-items:center; flex-wrap:wrap;
      margin: 10px 0 14px 0;
    }
    a { color: inherit; }
    button {
      padding: 8px 12px; border: 1px solid #888; border-radius: 10px;
      background: #f4f4f4; cursor: pointer;
    }
    button:active { transform: translateY(1px); }
    button:disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }
    .muted { color: #666; font-size: 13px; }
    .ok { color: #0a7b27; font-weight: 700; }
    .err { color: #b00020; font-weight: 700; white-space: pre-wrap; }
    .grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
    }
    @media (max-width: 900px) {
      .grid { grid-template-columns: 1fr; }
    }
    .card {
      border: 1px solid #ddd; border-radius: 12px; padding: 12px;
      background: #fff;
    }
    table { width: 100%; border-collapse: collapse; }
    th, td {
      padding: 8px; border-bottom: 1px solid #eee;
      text-align: left; vertical-align: top;
    }
    th {
      width: 220px; font-size: 12px; color: #444; user-select: none;
    }
    td { font-size: 14px; }
    .pill {
      display:inline-block; padding: 2px 8px; border-radius: 999px;
      border: 1px solid #ccc; font-size: 12px;
    }
    pre {
      margin: 0; white-space: pre-wrap; word-break: break-word;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
      font-size: 12px;
    }
    details summary { cursor: pointer; }

    /* Parent display copy widget */
    .copywrap {
      display:flex; gap:8px; align-items:center; flex-wrap:wrap;
    }
    .copywrap input {
      width: min(520px, 100%);
      padding: 8px 10px;
      border: 1px solid #ccc;
      border-radius: 10px;
      font-size: 14px;
      background: #fff;
    }

    /* Inline edit controls */
    .editbox {
      width: min(520px, 100%);
      padding: 8px 10px;
      border: 1px solid #ccc;
      border-radius: 10px;
      font-size: 14px;
      background: #fff;
      font-family: inherit;
    }
    textarea.editbox {
      min-height: 90px;
      resize: vertical;
      font-family: inherit;
    }
    .hint {
      font-size: 12px;
      color: #666;
      margin-top: 6px;
    }
  </style>
</head>
<body>
  <h1>Order <span class="pill">__ORDER_ID__</span></h1>

  <div class="bar">
    <button id="backBtn">← Back</button>
    <a class="muted" href="/orders/__ORDER_ID__" target="_blank" rel="noopener">Open JSON</a>
    <button id="openTrelloBtn" type="button" disabled>Open Trello Card</button>

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
    <button id="deleteBtn" type="button" disabled>Delete</button>

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
      console.log('DETAIL_PAGE_BUILD: web-delete-inline-v1');
    (function() {
      var ORDER_ID = __ORDER_ID__;

      var statusEl = document.getElementById("status");
      var okEl = document.getElementById("ok");
      var errEl = document.getElementById("error");

      var saveBtn = document.getElementById("saveBtn");
      var resetBtn = document.getElementById("resetBtn");
      var finalizeBtn = document.getElementById("finalizeBtn");
      var unfinalizeBtn = document.getElementById("unfinalizeBtn");
      var reviseBtn = document.getElementById("reviseBtn");
      var addlBtn = document.getElementById("addlBtn");
      var openTrelloBtn = document.getElementById("openTrelloBtn");

      var trelloCardId = "";



      var deleteBtn = document.getElementById("deleteBtn");

      var currentData = null;
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
      var currentClientId = null;
      var clientSuggestBox = null;
      var clientSuggestList = null;
      var clientSuggestTimer = null;
      var clientSelectedSnapshot = { name: null, company: null };

      // Track last-loaded values so we can enable Save only when dirty
      var baseline = {
        asset_type: "",
        notes: "",
        client_name: "",
        client_company_name: "",
        client_id: null
      };
      // Autosave state
      var autoSaveTimer = null;
      var autoSaveDelayMs = 900;
      var isDraftNow = false;
      var isSaving = false;
      var hasLoadedOnce = false;

      document.getElementById("backBtn").addEventListener("click", function() {
        // Always go back to main search.
        ensureSavedThen(function() {
          window.location.href = "/";
        });
      });

      // Warn if user tries to bail with unsaved changes still pending.
      window.addEventListener("beforeunload", function(e) {
        if (!hasLoadedOnce) return;
        if (isDirty() || isSaving) {
          e.preventDefault();
          e.returnValue = "";
          return "";
        }
      });

      if (openTrelloBtn) openTrelloBtn.addEventListener("click", function() {
        clearMsgs();
        if (!trelloCardId) {
          errEl.textContent = "No Trello card linked on this order.";
          return;
        }
        setBusy("Opening Trello…");
        fetch("/trello/card-url/" + encodeURIComponent(trelloCardId), { credentials: "same-origin" })
          .then(function(res) {
            return res.text().then(function(text) {
              if (res.status === 401 || res.status === 403 || (res.redirected && String(res.url).indexOf("/login") >= 0)) {
                window.location.href = "/login";
                return null;
              }
	              if (!res.ok) {
	                setBusy("");
	                // main.py renders this HTML from a Python string; newline escapes must be double-escaped.
	                errEl.textContent = "HTTP " + res.status + "\\n" + text;
	                return null;
	              }
              try { return JSON.parse(text); } catch (e) {
                setBusy("");
	                errEl.textContent = "Bad JSON\\n" + text;
                return null;
              }
            });
          })
          .then(function(data) {
            setBusy("");
            if (!data || !data.url) return;
            window.open(String(data.url), "_blank", "noopener");
          })
          .catch(function(e) {
            setBusy("");
            errEl.textContent = String(e);
          });
      });


      function esc(s) {
        var v = (s === null || s === undefined) ? "" : String(s);
        return v
          .replace(/&/g, "&amp;")
          .replace(/</g, "&lt;")
          .replace(/>/g, "&gt;")
          .replace(/"/g, "&quot;")
          .replace(/'/g, "&#039;");
      }

      function getVal(obj, path) {
        if (!obj) return undefined;
        var parts = path.split(".");
        var cur = obj;
        for (var i = 0; i < parts.length; i++) {
          if (cur === null || cur === undefined) return undefined;
          cur = cur[parts[i]];
        }
        return cur;
      }

      function addRow(tbody, label, value) {
        var tr = document.createElement("tr");
        var th = document.createElement("th");
        th.textContent = label;

        var td = document.createElement("td");
        if (value === null || value === undefined || value === "") {
          td.innerHTML = "<span class='muted'>(blank)</span>";
        } else if (typeof value === "object") {
          td.innerHTML = "<pre>" + esc(JSON.stringify(value, null, 2)) + "</pre>";
        } else {
          td.innerHTML = "<span>" + esc(value) + "</span>";
        }

        tr.appendChild(th);
        tr.appendChild(td);
        tbody.appendChild(tr);
      }

      function addInputRow(tbody, label, id, kind) {
        var tr = document.createElement("tr");

        var th = document.createElement("th");
        th.textContent = label;

        var td = document.createElement("td");
        var input;
        if (kind === "textarea") {
          input = document.createElement("textarea");
        } else {
          input = document.createElement("input");
          input.type = "text";
        }
        input.id = id;
        input.className = "editbox";
        td.appendChild(input);

        tr.appendChild(th);
        tr.appendChild(td);
        tbody.appendChild(tr);

        return input;
      }

      function addSelectRow(tbody, label, id, options) {
        var tr = document.createElement("tr");

        var th = document.createElement("th");
        th.textContent = label;

        var td = document.createElement("td");

        var sel = document.createElement("select");
        sel.id = id;
        sel.className = "editbox";

        // Populate options
        for (var i = 0; i < options.length; i++) {
          var opt = document.createElement("option");
          opt.value = options[i];
          opt.textContent = options[i];
          sel.appendChild(opt);
        }

        td.appendChild(sel);
        tr.appendChild(th);
        tr.appendChild(td);
        tbody.appendChild(tr);

        return sel;
      }

      function renderSection(tbody, data, fields) {
        tbody.innerHTML = "";
        for (var i = 0; i < fields.length; i++) {
          var f = fields[i];
          var val = getVal(data, f.key);
          addRow(tbody, f.label, val);
        }
      }

      function computeParentDisplay(data) {
        // Prefer server-provided parent_display (FM-style). Fallback to derive from sp.*.
        if (data && data.parent_display) return data.parent_display;

        var sp = (data && data.sp) ? data.sp : null;
        var rev = sp ? sp.revision_of : null;
        if (rev) return "Revision of " + rev;

        var addl = sp ? sp.additional_version_of : null;
        if (addl) return "Add'l vers of " + addl;

        return "";
      }

      function copyText(text, done) {
        if (!text) return done(false);

        // Prefer modern clipboard API when available.
        try {
          if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(text).then(function() {
              done(true);
            }).catch(function() {
              legacyCopy(text, done);
            });
            return;
          }
        } catch (e) {
          // fall through
        }
        legacyCopy(text, done);
      }

      function legacyCopy(text, done) {
        try {
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
        } catch (e) {
          done(false);
        }
      }

      function wireCopyWidget() {
        function selectAll() {
          parentInput.focus();
          parentInput.select();
          parentInput.setSelectionRange(0, parentInput.value.length);
        }

        parentInput.addEventListener("focus", function() {
          if (parentInput.value) {
            selectAll();
          }
        });

        parentInput.addEventListener("click", function() {
          if (!parentInput.value) return;
          selectAll();
          copyText(parentInput.value, function(){});
        });

        copyBtn.addEventListener("click", function() {
          if (!parentInput.value) return;
          selectAll();
          copyText(parentInput.value, function(){});
        });
      }

      function normalize(s) {
        return (s === null || s === undefined) ? "" : String(s);
      }

      function getDraft() {
        return {
          asset_type: normalize(assetTypeSelect ? assetTypeSelect.value : ""),
          notes: normalize(notesInput ? notesInput.value : ""),
          client_name: normalize(clientNameInput ? clientNameInput.value : ""),
          client_company_name: normalize(clientCompanyInput ? clientCompanyInput.value : ""),
          client_id: (currentClientId === null || typeof currentClientId === "undefined") ? null : currentClientId
        };
      }

      function setDraftFromBaseline() {
        if (assetTypeSelect) assetTypeSelect.value = baseline.asset_type;
        if (notesInput) notesInput.value = baseline.notes;
        if (clientNameInput) clientNameInput.value = baseline.client_name;
        if (clientCompanyInput) clientCompanyInput.value = baseline.client_company_name;
      }

      function isDirty() {
        var d = getDraft();
        return (
          d.asset_type !== baseline.asset_type ||
          d.notes !== baseline.notes ||
          d.client_name !== baseline.client_name ||
          d.client_company_name !== baseline.client_company_name ||
          (d.client_id || null) !== (baseline.client_id || null)
        );
      }

      function refreshDirtyUI() {
        var dirty = isDirty();
        if (isDraftNow) {
          // Keep Save enabled for draft orders (even if nothing changed yet).
          saveBtn.disabled = false;
        } else {
          saveBtn.disabled = true;
        }
        resetBtn.disabled = !dirty;
      }

      function scheduleAutoSave() {
        if (!hasLoadedOnce) return;
        if (!isDraftNow) return;
        if (!isDirty()) return;
        if (autoSaveTimer) clearTimeout(autoSaveTimer);
        autoSaveTimer = setTimeout(function() {
          saveAsync(true);
        }, autoSaveDelayMs);
      }

      function ensureSavedThen(fn) {
        // If we're not dirty, just go.
        if (!hasLoadedOnce || !isDirty()) {
          fn();
          return;
        }
        // If user is editing a non-draft, don't silently spam the API.
        if (!isDraftNow) {
          errEl.textContent = "This order isn't in DRAFT. Use Override Edit first.";
          return;
        }
        saveAsync(false).then(function(ok) {
          if (ok) fn();
        });
      }

      function setBusy(msg) {
        statusEl.textContent = msg || "";
      }

      function clearMsgs() {
        okEl.textContent = "";
        errEl.textContent = "";
      }

      function setActionsDisabled(disabled) {
        reviseBtn.disabled = disabled || reviseBtn.disabled;
        addlBtn.disabled = disabled || addlBtn.disabled;
        finalizeBtn.disabled = disabled || finalizeBtn.disabled;
        unfinalizeBtn.disabled = disabled || unfinalizeBtn.disabled;
      }

      function saveAsync(quiet) {
        clearMsgs();
        if (isSaving) return Promise.resolve(false);
        if (!isDraftNow) {
          if (!quiet) errEl.textContent = "This order isn't in DRAFT. Use Override Edit first.";
          return Promise.resolve(false);
        }

        isSaving = true;
        setBusy(quiet ? "Autosaving…" : "Saving…");
        saveBtn.disabled = true;

        var d = getDraft();
        var payload = {
          notes: d.notes,
          client_name: d.client_name,
          client_company_name: d.client_company_name
        };

        // Only send client_id when we actually have one selected.
        if (d.client_id !== null) {
          payload.client_id = d.client_id;
        }


        // Only send asset_type when it actually changed (avoids 400s on finalized orders).
        if (d.asset_type !== baseline.asset_type) {
          payload.asset_type = d.asset_type;
        }

        var p = Promise.resolve(null);
        if ((d.client_id === null) && ((d.client_name || "").trim() !== "")) {
          p = ensureClientExists(d.client_name, d.client_company_name);
        }

        return p.then(function(newId) {
          if (newId) payload.client_id = newId;
          return fetch("/orders/" + ORDER_ID, {
          credentials: "same-origin",
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        })
        .then(function(res) {
          return res.text().then(function(text) {
            if (!res.ok) {
              setBusy("");
              errEl.textContent = "HTTP " + res.status + "\\n" + text;
              refreshDirtyUI();
              return false;
            }

            // Update baseline locally so closing/finalizing won't lose changes.
            baseline = {
              asset_type: d.asset_type,
              notes: d.notes,
              client_name: d.client_name,
              client_company_name: d.client_company_name,
              client_id: (d.client_id || null)
            };

            okEl.textContent = quiet ? "Autosaved." : "Saved.";
            refreshDirtyUI();
            hasLoadedOnce = true;
            setBusy("Loaded.");
            return true;
          });
        })
        .catch(function(e) {
          setBusy("");
          errEl.textContent = String(e);
          refreshDirtyUI();
          return false;
        })
        .finally(function() {
          isSaving = false;
        });
        });
      }

      saveBtn.addEventListener("click", function() {
        saveAsync(false);
      });

      resetBtn.addEventListener("click", function() {
        clearMsgs();
        setDraftFromBaseline();
        refreshDirtyUI();
      });

      function postAndGo(path) {
        clearMsgs();
        setBusy("Working…");
        reviseBtn.disabled = true;
        addlBtn.disabled = true;
        finalizeBtn.disabled = true;
        unfinalizeBtn.disabled = true;

        fetch(path, { method: "POST", credentials: "same-origin" })
          .then(function(res) {
            return res.text().then(function(text) {
              if (!res.ok) {
                setBusy("");
                errEl.textContent = "HTTP " + res.status + "\\n" + text;
                return null;
              }
              try {
                return JSON.parse(text);
              } catch (e) {
                setBusy("");
                errEl.textContent = "Bad JSON response\\n" + text;
                return null;
              }
            });
          })
          .then(function(data) {
            if (!data || !data.id) return;
            // Replace so browser Back goes to search, not back to this order.
            window.location.replace("/order/" + data.id);
          })
          .catch(function(e) {
            setBusy("");
            errEl.textContent = String(e);
          });
      }

      function postAndReload(path, okMsg) {
        clearMsgs();
        setBusy("Working…");
        reviseBtn.disabled = true;
        addlBtn.disabled = true;
        finalizeBtn.disabled = true;
        unfinalizeBtn.disabled = true;

        fetch(path, { method: "POST", credentials: "same-origin" })
          .then(function(res) {
            return res.text().then(function(text) {
              if (!res.ok) {
                setBusy("");
                errEl.textContent = "HTTP " + res.status + "\\n" + text;
                return null;
              }
              okEl.textContent = okMsg || "Done.";
              return true;
            });
          })
          .then(function(ok) {
            if (ok) load();
          })
          .catch(function(e) {
            setBusy("");
            errEl.textContent = String(e);
          });
      }

      reviseBtn.addEventListener("click", function() {
        ensureSavedThen(function() {
          postAndGo("/orders/" + ORDER_ID + "/revise");
        });
      });

      addlBtn.addEventListener("click", function() {
        ensureSavedThen(function() {
          postAndGo("/orders/" + ORDER_ID + "/addl_vers");
        });
      });

      finalizeBtn.addEventListener("click", function() {
        ensureSavedThen(function() {
          postAndReload("/orders/" + ORDER_ID + "/finalize", "Finalized.");
        });
      });

      unfinalizeBtn.addEventListener("click", function() {
        postAndReload("/orders/" + ORDER_ID + "/unfinalize", "Unfinalized.");
      });


      function doDelete() {
        clearMsgs();
        var initials = window.prompt("Enter your initials to delete this order (e.g., SB):");
        if (initials === null) return;
        initials = String(initials || "").trim();
        if (!initials) {
          errEl.textContent = "Initials required.";
          return;
        }

        var isFinal = false;
        if (currentData && currentData.finalized_at) {
          isFinal = true;
        } else if (currentData && currentData.status) {
          var s = String(currentData.status).toLowerCase();
          if (s.indexOf("final") >= 0) isFinal = true;
        }

        if (isFinal) {
          var c1 = window.confirm("This order is FINALIZED. Deleting it is a big deal. Continue?");
          if (!c1) return;
          var c2 = window.confirm("Last chance. Really delete this FINALIZED order?");
          if (!c2) return;
        } else {
          var c0 = window.confirm("Delete this order?");
          if (!c0) return;
        }

        setBusy("Deleting…");
        if (deleteBtn) deleteBtn.disabled = true;

        var url = "/orders/" + ORDER_ID + "?initials=" + encodeURIComponent(initials);
        if (isFinal) url += "&force=true";

        fetch(url, { method: "DELETE", credentials: "same-origin" })
          .then(function(res) {
            return res.text().then(function(text) {
              if (!res.ok) {
                setBusy("");
                errEl.textContent = "HTTP " + res.status + "\\n" + text;
                if (deleteBtn) deleteBtn.disabled = false;
                return null;
              }
              okEl.textContent = "Deleted.";
              window.location.href = "/";
              return true;
            });
          })
          .catch(function(e) {
            setBusy("");
            errEl.textContent = String(e);
            if (deleteBtn) deleteBtn.disabled = false;
          });
      }

      if (deleteBtn) deleteBtn.addEventListener("click", doDelete);
function load() {
        clearMsgs();
        setBusy("Fetching…");

        fetch("/orders/" + ORDER_ID, { credentials: "same-origin" })
          .then(function(res) {
            return res.text().then(function(text) {
              if (!res.ok) {
                setBusy("");
                errEl.textContent = "HTTP " + res.status + "\\n" + text;
                return null;
              }
              try {
                return JSON.parse(text);
              } catch (e) {
                setBusy("");
                errEl.textContent = "Bad JSON\\n" + text;
                return null;
              }
            });
          })
          .then(function(data) {
            if (!data) return;

            currentData = data;

            // Trello quick-open
            trelloCardId = normalize(data.trello_card_id);
            if (openTrelloBtn) {
              openTrelloBtn.disabled = !trelloCardId;
            }

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
            if (at && assetOptions.indexOf(at) === -1) {
              assetOptions.unshift(at);
            }
            assetTypeSelect = addSelectRow(orderRows, "Asset Type", "editAssetType", assetOptions);
            assetTypeSelect.value = at || "";

            addRow(orderRows, "Status", data.status);

            notesInput = addInputRow(orderRows, "Notes", "editNotes", "textarea");

            addRow(orderRows, "Deleted?", data.is_deleted);
            addRow(orderRows, "Created", data.created_at);
            addRow(orderRows, "Updated", data.updated_at);

            // ----- SP section -----
            var spObj;
            if (data && typeof data.sp === "object" && data.sp) {
              spObj = data;
            } else {
              spObj = {
                sp: {
                  sp_number: data.sp_number,
                  order_type: data.sp_order_type || data.order_type,
                  revision_of: data.sp_revision_of || data.revision_of,
                  additional_version_of: data.additional_version_of
                }
              };
            }

            renderSection(spRows, spObj, [
              { label: "SP Number", key: "sp.sp_number" },
              { label: "Order Type", key: "sp.order_type" },
              { label: "Revision Of", key: "sp.revision_of" },
              { label: "Add'l Vers Of", key: "sp.additional_version_of" }
            ]);

            // ----- Client section (editable fields first) -----
            clientRows.innerHTML = "";
            clientNameInput = addInputRow(clientRows, "Client Name", "editClientName", "text");
            clientCompanyInput = addInputRow(clientRows, "Client Company", "editClientCompany", "text");

            // --- Client typeahead (fast) ---
            function ensureClientSuggestUI() {
              if (clientSuggestBox) return;
              clientSuggestBox = document.createElement("div");
              clientSuggestBox.style.position = "absolute";
              clientSuggestBox.style.zIndex = "9999";
              clientSuggestBox.style.background = "#fff";
              clientSuggestBox.style.border = "1px solid #ccc";
              clientSuggestBox.style.borderRadius = "10px";
              clientSuggestBox.style.boxShadow = "0 4px 18px rgba(0,0,0,.12)";
              clientSuggestBox.style.padding = "6px";
              clientSuggestBox.style.display = "none";
              clientSuggestBox.style.maxHeight = "220px";
              clientSuggestBox.style.overflowY = "auto";
              clientSuggestBox.style.minWidth = "260px";

              clientSuggestList = document.createElement("div");
              clientSuggestBox.appendChild(clientSuggestList);
              document.body.appendChild(clientSuggestBox);
            }

            function positionClientSuggest() {
              if (!clientSuggestBox || !clientNameInput) return;
              var r = clientNameInput.getBoundingClientRect();
              clientSuggestBox.style.left = (window.scrollX + r.left) + "px";
              clientSuggestBox.style.top = (window.scrollY + r.bottom + 6) + "px";
              clientSuggestBox.style.minWidth = Math.max(260, r.width) + "px";
            }

            function hideClientSuggest() {
              if (!clientSuggestBox) return;
              clientSuggestBox.style.display = "none";
              if (clientSuggestList) clientSuggestList.innerHTML = "";
            }

            // Keyboard nav state for client suggest
            var clientSuggestItems = [];
            var clientSuggestIndex = -1;

            function setClientSuggestActive(idx) {
              if (!clientSuggestBox) return;
              var kids = Array.prototype.slice.call(clientSuggestList.querySelectorAll(".byp-suggest-item"));
              if (!kids.length) { clientSuggestIndex = -1; return; }

              var n = idx;
              if (n < 0) n = 0;
              if (n >= kids.length) n = kids.length - 1;

              kids.forEach(function(el, i) {
                if (i === n) {
                  el.style.background = "#93c5fd";
                  el.style.border = "1px solid #1d4ed8";
                } else {
                  el.style.background = "transparent";
                  el.style.border = "1px solid transparent";
                }
                el.setAttribute("aria-selected", (i === n) ? "true" : "false");
              });

              clientSuggestIndex = n;
              try { kids[n].scrollIntoView({ block: "nearest" }); } catch (e) {}
            }

            function applyClientSuggestItem(it, items) {
              if (!it) return;
              var nm = (it.client_name || "").toString().trim();

              var getCo = function(x){
                try { return ((x.company_name || x.client_company_name || x.client_company || x.company) || "").toString(); }
                catch (e) { return ""; }
              };

              var co = getCo(it);
              if ((!co || !co.trim()) && nm && items && items.length) {
                for (var bi = 0; bi < items.length; bi++) {
                  var x = items[bi];
                  if (((x.client_name || "").toString()) === nm) {
                    var cand = getCo(x);
                    if (cand && cand.trim()) { co = cand; break; }
                  }
                }
              }
              co = (co || "").toString().trim();

              currentClientId = it.id;
              clientSelectedSnapshot = { name: nm, company: co };

              if (clientNameInput) clientNameInput.value = nm;
              if (clientCompanyInput) clientCompanyInput.value = co;

              hideClientSuggest();
              refreshDirtyUI();

              try { clientNameInput.focus(); clientNameInput.setSelectionRange(clientNameInput.value.length, clientNameInput.value.length); } catch (e) {}
            }

            function selectActiveClientSuggest() {
              if (clientSuggestIndex < 0 || clientSuggestIndex >= clientSuggestItems.length) return false;
              applyClientSuggestItem(clientSuggestItems[clientSuggestIndex], clientSuggestItems);
              return true;
            }

            function onClientNameKeyDown(e) {
              if (!clientSuggestBox || clientSuggestBox.style.display !== "block") return;
              var k = e.key || "";
              var code = e.keyCode || 0;

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

            
      function ensureClientExists(clientName, companyName) {
        var name = (clientName || "").trim();
        var company = (companyName || "").trim();
        if (!name) return Promise.resolve(null);

        return fetch("/orders/clients", {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json", "Accept": "application/json" },
          body: JSON.stringify({
            client_name: name,
            company_name: company || null,
            is_active: true
          })
        }).then(function(res) {
          if (!res.ok) return null;
          return res.json();
        }).then(function(data) {
          if (data && data.id != null) return data.id;
          return null;
        }).catch(function(_e) { return null; });
      }

function fetchClientSuggest(q) {
              return fetch("/orders/clients/suggest?q=" + encodeURIComponent(q) + "&limit=10", { credentials: "same-origin" })
                .then(function(res) {
                  if (!res.ok) { return []; }
                  return res.json();
                })
                .then(function(data) {
                  // API may return a raw array OR a wrapper object like { value: [...], Count: N } / { items: [...] }.
                  if (Array.isArray(data)) return data;
                  if (data && Array.isArray(data.value)) return data.value;
                  if (data && Array.isArray(data.items)) return data.items;
                  if (data && Array.isArray(data.results)) return data.results;
                  return [];
                })
                .catch(function() { return []; });
            }

            function renderClientSuggest(items) {
              ensureClientSuggestUI();
              clientSuggestList.innerHTML = "";
              clientSuggestItems = (items && items.slice) ? items.slice() : [];
              clientSuggestIndex = -1;

              if (!items || !items.length) {
                hideClientSuggest();
                return;
              }

              items.forEach(function(it, i) {
                var row = document.createElement("div");
                row.className = "byp-suggest-item";
                row.setAttribute("role","option");
                row.style.padding = "8px 10px";
                row.style.borderRadius = "8px";
                row.style.cursor = "pointer";
                row.style.userSelect = "none";

                var nm = (it.client_name || "").toString();
                var getCo = function(x){
                  try { return ((x.company_name || x.client_company_name || x.client_company || x.company) || "").toString(); } catch (e) { return ""; }
                };
                var co = getCo(it);
                if ((!co || !co.trim()) && nm && items && items.length) {
                  for (var bi = 0; bi < items.length; bi++) {
                    var x = items[bi];
                    if (((x.client_name || "").toString()) === nm) {
                      var cand = getCo(x);
                      if (cand && cand.trim()) { co = cand; break; }
                    }
                  }
                }
                co = (co || "").toString();
                row.textContent = co ? (nm + " — " + co) : nm;

                row.addEventListener("mouseenter", function(){ setClientSuggestActive(i); });
                row.addEventListener("mouseleave", function(){ if (clientSuggestIndex >= 0) setClientSuggestActive(clientSuggestIndex); });

                row.addEventListener("mousedown", function(ev) {
                  ev.preventDefault(); // keep focus
                  applyClientSuggestItem(it, items);
                });

                clientSuggestList.appendChild(row);
              });

              positionClientSuggest();
              clientSuggestBox.style.display = "block";
            }

            function onClientNameTyping() {
              if (!clientNameInput) return;

              // If user edits away from the selected suggestion, clear client_id (and company if it was auto-filled)
              var typed = normalize(clientNameInput.value || "");
              if (clientSelectedSnapshot.name !== null && typed !== normalize(clientSelectedSnapshot.name)) {
                currentClientId = null;
                if (clientCompanyInput && normalize(clientCompanyInput.value || "") === normalize(clientSelectedSnapshot.company || "")) {
                  clientCompanyInput.value = "";
                }
                clientSelectedSnapshot = { name: null, company: null };
              }

              if (clientSuggestTimer) clearTimeout(clientSuggestTimer);
              var q = typed.trim();
              if (q.length < 2) {
                hideClientSuggest();
                refreshDirtyUI();
                return;
              }

              clientSuggestTimer = setTimeout(function() {
                (function(expected) {
                  fetchClientSuggest(expected).then(function(items) {
                    renderClientSuggest(items);

                    // If the typed client name EXACTLY matches a suggestion, auto-fill company name (best match)
                    // without forcing a click/Enter.
                    try {
                      var currentTyped = normalize(clientNameInput ? clientNameInput.value : "").trim();
                      if (normalize(currentTyped).trim() !== normalize(expected).trim()) return;

                      // Do not overwrite a manually entered company.
                      if (!clientCompanyInput) return;
                      var companyNow = normalize(clientCompanyInput.value || "").trim();
                      if (companyNow) return;

                      var want = normalize(expected).trim().toLowerCase();
                      var best = null;
                      var bestCompany = "";

                      var getCo = function(x){
                        try { return ((x.company_name || x.client_company_name || x.client_company || x.company) || "").toString().trim(); }
                        catch (e) { return ""; }
                      };

                      for (var ii = 0; ii < (items || []).length; ii++) {
                        var it = items[ii];
                        var nm = ((it && it.client_name) ? it.client_name : "").toString().trim();
                        if (!nm) continue;
                        if (nm.toLowerCase() !== want) continue;

                        var co = getCo(it);
                        // prefer any non-empty company; otherwise keep first match
                        if (!best) best = it;
                        if (co && co.trim()) { best = it; bestCompany = co; break; }
                      }

                      if (best) {
                        bestCompany = bestCompany || getCo(best) || "";
                        if (bestCompany) {
                          clientCompanyInput.value = bestCompany;
                          currentClientId = best.id;
                          clientSelectedSnapshot = { name: normalize(best.client_name || "").trim(), company: bestCompany };
                          refreshDirtyUI();
                        }
                      }
                    } catch (e) {
                      // ignore
                    }
                  });
                })(q);
              }, 250);

              refreshDirtyUI();
            }

            // Best-effort: stop browser autofill from hijacking this field
            try {
              clientNameInput.setAttribute("autocomplete", "off");
              clientCompanyInput.setAttribute("autocomplete", "off");
            } catch (e) {}

            ensureClientSuggestUI();
            window.addEventListener("scroll", positionClientSuggest);
            window.addEventListener("resize", positionClientSuggest);

            clientNameInput.addEventListener("input", onClientNameTyping);
            clientNameInput.addEventListener("keydown", onClientNameKeyDown);
            clientNameInput.addEventListener("focus", function(){ onClientNameTyping(); });
            clientNameInput.addEventListener("blur", function(){ setTimeout(hideClientSuggest, 150); });

            addRow(clientRows, "Client Email", data.client_email);
            addRow(clientRows, "Client Phone", data.client_phone);

            // ----- Rep section -----
            renderSection(repRows, data, [
              { label: "Rep Code", key: "rep_code" },
              { label: "Rep Name", key: "rep_name" }
            ]);

            // Baseline values
            baseline = {
              asset_type: normalize(data.asset_type).toLowerCase(),
              notes: normalize(data.notes),
              client_name: normalize(data.client_name),
              client_company_name: normalize(data.client_company_name)
            };
            setDraftFromBaseline();

            // Wire dirty tracking
            function onChange() {
              okEl.textContent = "";
              refreshDirtyUI();
              scheduleAutoSave();
            }
            if (assetTypeSelect) assetTypeSelect.addEventListener("change", onChange);
            notesInput.addEventListener("input", onChange);
            clientNameInput.addEventListener("input", onChange);
            clientCompanyInput.addEventListener("input", onChange);

            // Enable action buttons once we know the order exists
            reviseBtn.disabled = false;
            addlBtn.disabled = false;

            if (deleteBtn) {
              deleteBtn.disabled = !!data.is_deleted;
            }

            // Editable only when draft
            var isDraft = false;
            if (data && data.status) {
              var ds = String(data.status).toLowerCase();
              if (ds.indexOf("draft") >= 0) isDraft = true;
            }
            isDraftNow = isDraft;
            if (assetTypeSelect) assetTypeSelect.disabled = !isDraft;
            if (notesInput) notesInput.disabled = !isDraft;
            if (clientNameInput) clientNameInput.disabled = !isDraft;
            if (clientCompanyInput) clientCompanyInput.disabled = !isDraft;

            // Finalize/Unfinalize: best-effort based on finalized_at or status text
            var isFinal = false;
            if (data && data.finalized_at) {
              isFinal = true;
            } else if (data && data.status) {
              var s = String(data.status).toLowerCase();
              if (s.indexOf("final") >= 0) isFinal = true;
            }

            finalizeBtn.disabled = isFinal;
            unfinalizeBtn.disabled = !isFinal;

            refreshDirtyUI();
            setBusy("Loaded.");
          })
          .catch(function(e) {
            setBusy("");
            errEl.textContent = String(e);
          });
      }

      wireCopyWidget();
      load();
    })();
  </script>
</body>
</html>
"""
    html = html.replace("__ORDER_ID__", str(order_id))
    return HTMLResponse(content=html)


@app.get("/health")
def health():
    return {"status": "BYP Ops backend online"}