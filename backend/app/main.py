from __future__ import annotations

import os
import hmac
import hashlib
import base64
from pathlib import Path

from fastapi import FastAPI, Form, Request, Body, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.routes.orders import router as orders_router

# DB / models (for auth)
from app.database.engine import SessionLocal
from app.models.users import User


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

                # Decide whether to respond like an API (401 JSON) or like a browser (303 to /login).
                # Desktop callers usually send Accept: */* (or application/json). Browser navigations usually include text/html.
                accept = (request.headers.get("accept") or "").lower()
                wants_html = ("text/html" in accept) and ("application/json" not in accept)

                is_api_path = path.startswith("/orders") or path.startswith("/admin") or path == "/me"

                # API endpoints (desktop + fetch calls) should get a hard 401.
                if is_api_path and not wants_html:
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


def _html_escape(s: str) -> str:
    return (
        (s or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#039;")
    )


# ---- Admin JSON API (for Desktop Admin Users parity) ----
def _require_admin_or_401(request: Request) -> None:
    if not _is_logged_in(request):
        raise HTTPException(status_code=401, detail="Not authenticated")
    if not _is_admin(request):
        raise HTTPException(status_code=403, detail="Admin only")


def _user_to_dict(u: User) -> dict:
    d = {
        "id": int(getattr(u, "id")),
        "username": str(getattr(u, "username") or ""),
        "rep_code": str(getattr(u, "rep_code") or ""),
        "rep_name": str(getattr(u, "rep_name") or ""),
        "role": str(getattr(u, "role") or "user"),
        "is_active": bool(getattr(u, "is_active", True)),
    }
    # Optional email field if model supports it
    if hasattr(u, "email"):
        try:
            d["email"] = str(getattr(u, "email") or "")
        except Exception:
            d["email"] = ""
    return d


def _list_users() -> list[dict]:
    db = SessionLocal()
    try:
        users = db.query(User).order_by(User.id.asc()).all()
        return [_user_to_dict(u) for u in users]
    finally:
        db.close()


@app.get("/admin/users/list", include_in_schema=False)
def admin_users_list(request: Request):
    _require_admin_or_401(request)
    return {"users": _list_users()}


@app.get("/admin/users/json", include_in_schema=False)
def admin_users_json(request: Request):
    _require_admin_or_401(request)
    return {"users": _list_users()}


@app.get("/admin/users.json", include_in_schema=False)
def admin_users_json_dot(request: Request):
    _require_admin_or_401(request)
    return {"users": _list_users()}


@app.get("/admin/api/users", include_in_schema=False)
def admin_api_users_list(request: Request):
    _require_admin_or_401(request)
    return {"users": _list_users()}


@app.post("/admin/users", include_in_schema=False)
def admin_users_create_json(request: Request, payload: dict = Body(...)):
    _require_admin_or_401(request)

    u = (str(payload.get("username") or "")).strip().lower()
    pw = (str(payload.get("password") or "")).strip()
    if not u:
        raise HTTPException(status_code=400, detail="username required")
    if not pw:
        raise HTTPException(status_code=400, detail="password required")

    rc = (str(payload.get("rep_code") or "")).strip()
    rn = (str(payload.get("rep_name") or "")).strip()
    role = (str(payload.get("role") or "user")).strip().lower()
    if role not in ("user", "admin"):
        role = "user"
    is_active = bool(payload.get("is_active", True))
    email = (str(payload.get("email") or "")).strip()

    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.username == u).first()
        if existing:
            raise HTTPException(status_code=409, detail="username already exists")

        new_user = User(
            username=u,
            rep_code=rc,
            rep_name=rn,
            role=role,
            is_active=is_active,
            password_hash="plain:" + pw,
        )
        if hasattr(new_user, "email"):
            try:
                setattr(new_user, "email", email)
            except Exception:
                pass

        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        return {"status": "ok", "user": _user_to_dict(new_user)}
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@app.post("/admin/users/create", include_in_schema=False)
def admin_users_create_alias(request: Request, payload: dict = Body(...)):
    # Alias for desktop callers
    return admin_users_create_json(request, payload)


@app.post("/admin/api/users", include_in_schema=False)
def admin_api_users_create(request: Request, payload: dict = Body(...)):
    # Alias for desktop callers
    return admin_users_create_json(request, payload)


@app.patch("/admin/users/{user_id}", include_in_schema=False)
def admin_users_patch(request: Request, user_id: int, payload: dict = Body(...)):
    _require_admin_or_401(request)
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == int(user_id)).first()
        if not user:
            raise HTTPException(status_code=404, detail="user not found")

        if "role" in payload:
            role = (str(payload.get("role") or "user")).strip().lower()
            if role not in ("user", "admin"):
                role = "user"
            setattr(user, "role", role)

        if "is_active" in payload:
            setattr(user, "is_active", bool(payload.get("is_active")))

        if "rep_code" in payload:
            setattr(user, "rep_code", (str(payload.get("rep_code") or "")).strip())

        if "rep_name" in payload:
            setattr(user, "rep_name", (str(payload.get("rep_name") or "")).strip())

        if "email" in payload and hasattr(user, "email"):
            try:
                setattr(user, "email", (str(payload.get("email") or "")).strip())
            except Exception:
                pass

        db.commit()
        db.refresh(user)
        return {"status": "ok", "user": _user_to_dict(user)}
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@app.post("/admin/users/{user_id}/password", include_in_schema=False)
def admin_users_set_password_json(request: Request, user_id: int, payload: dict = Body(...)):
    _require_admin_or_401(request)
    pw = (str(payload.get("password") or "")).strip()
    if not pw:
        raise HTTPException(status_code=400, detail="password required")

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == int(user_id)).first()
        if not user:
            raise HTTPException(status_code=404, detail="user not found")
        setattr(user, "password_hash", "plain:" + pw)
        db.commit()
        return {"status": "ok"}
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@app.post("/admin/users/{user_id}/role", include_in_schema=False)
def admin_users_set_role_json(request: Request, user_id: int, payload: dict = Body(...)):
    _require_admin_or_401(request)
    role = (str(payload.get("role") or "user")).strip().lower()
    if role not in ("admin", "user"):
        raise HTTPException(status_code=400, detail="role must be admin or user")
    return admin_users_patch(request, user_id, {"role": role})


@app.post("/admin/users/{user_id}/toggle", include_in_schema=False)
def admin_users_toggle_json(request: Request, user_id: int):
    _require_admin_or_401(request)
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == int(user_id)).first()
        if not user:
            raise HTTPException(status_code=404, detail="user not found")
        cur = bool(getattr(user, "is_active", True))
        setattr(user, "is_active", (not cur))
        db.commit()
        db.refresh(user)
        return {"status": "ok", "user": _user_to_dict(user)}
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

# ---- Admin: Users page ----
@app.get("/admin/users", include_in_schema=False)
def admin_users_page(request: Request, msg: str | None = None, err: str | None = None, json: int | None = None, format: str | None = None):
    gate = _require_admin_or_redirect(request)
    if gate is not None:
        return gate

    if (json is not None and int(json) == 1) or (str(format or '').strip().lower() == 'json'):
        return JSONResponse(content={"users": _list_users()})

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




# API routes
app.include_router(orders_router)

# --- Web UI (vanilla HTML/JS served by FastAPI) ---
APP_DIR = Path(__file__).resolve().parent
WEB_DIR = APP_DIR / "web"

# Serve static assets (JS/CSS) from /web/*
# Example: /web/app.js
app.mount("/web", StaticFiles(directory=WEB_DIR), name="web")


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

      // Track last-loaded values so we can enable Save only when dirty
      var baseline = {
        asset_type: "",
        notes: "",
        client_name: "",
        client_company_name: ""
      };

      document.getElementById("backBtn").addEventListener("click", function() {
        // Always go back to main search.
        window.location.href = "/";
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
          client_company_name: normalize(clientCompanyInput ? clientCompanyInput.value : "")
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
          d.client_company_name !== baseline.client_company_name
        );
      }

      function refreshDirtyUI() {
        var dirty = isDirty();
        saveBtn.disabled = !dirty;
        resetBtn.disabled = !dirty;
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

      function save() {
        clearMsgs();
        setBusy("Saving…");
        saveBtn.disabled = true;

        var d = getDraft();
        var payload = {
          notes: d.notes,
          client_name: d.client_name,
          client_company_name: d.client_company_name
        };

        // Only send asset_type when it actually changed (avoids 400s on finalized orders).
        if (d.asset_type !== baseline.asset_type) {
          payload.asset_type = d.asset_type;
        }

        fetch("/orders/" + ORDER_ID, {
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
              return null;
            }
            okEl.textContent = "Saved.";
            return true;
          });
        })
        .then(function(ok) {
          if (ok) load(); // reload to show updated_at + any server-side normalization
        })
        .catch(function(e) {
          setBusy("");
          errEl.textContent = String(e);
          refreshDirtyUI();
        });
      }

      saveBtn.addEventListener("click", save);

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

        fetch(path, { method: "POST" })
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

        fetch(path, { method: "POST" })
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
        postAndGo("/orders/" + ORDER_ID + "/revise");
      });

      addlBtn.addEventListener("click", function() {
        postAndGo("/orders/" + ORDER_ID + "/addl_vers");
      });

      finalizeBtn.addEventListener("click", function() {
        postAndReload("/orders/" + ORDER_ID + "/finalize", "Finalized.");
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

        fetch(url, { method: "DELETE" })
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

        fetch("/orders/" + ORDER_ID)
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

            // Asset Type editable only when draft
            var isDraft = false;
            if (data && data.status) {
              var ds = String(data.status).toLowerCase();
              if (ds.indexOf("draft") >= 0) isDraft = true;
            }
            if (assetTypeSelect) {
              assetTypeSelect.disabled = !isDraft;
            }

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
