# app/routes/orders.py

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

import json
import re

def _audit_details(order, details=None):
    d = dict(details or {})
    d.setdefault("order_id", getattr(order, "id", None))
    d.setdefault("sp_id", getattr(order, "sp_id", None))
    d.setdefault("sp_number", getattr(getattr(order, "sp", None), "sp_number", None))
    d.setdefault("artist", getattr(order, "artist", None))
    d.setdefault("asset_type", getattr(order, "asset_type", None))
    d.setdefault("status", getattr(order, "status", None))
    return d


from datetime import datetime
from sqlalchemy import or_, func, case
from sqlalchemy.orm import Session, joinedload

from app.database.session import get_db
from app.schemas.order import OrderCreate, OrderUpdate, OrderResponse

# Allow admin users to create orders on behalf of another rep by passing rep_code/rep_name.
# We keep this local (instead of editing the shared schema) to avoid rippling changes.
class OrderCreateWithRep(OrderCreate):
    rep_code: str | None = None
    rep_name: str | None = None
    client_id: int | None = None

# Allow rep reassignment on existing (non-finalized) orders via PATCH.
class OrderUpdateWithRep(OrderUpdate):
    rep_code: str | None = None
    rep_name: str | None = None
    client_id: int | None = None
from app.models.orders import Order
from app.models.users import User
from app.models.sp_master import SPNumber
from app.models.audit_log import AuditLog
from app.models.clients import Client
from app.services.order_service import create_order as create_order_service, finalize_order
from app.services.sp_service import generate_next_sp
from app.services.trello_service import rebuild_order_checklist, TrelloConfigError, card_exists


router = APIRouter(prefix="/orders", tags=["Orders"])

# ---- Auth dependencies (session-cookie based) ----
def _session_user(request: Request) -> dict | None:
    try:
        s = getattr(request, "session", None) or {}
        username = (s.get("username") or "").strip()
        if not username:
            return None
        return {
            "user_id": s.get("user_id"),
            "username": username,
            "role": (s.get("role") or "").strip().lower(),
            "rep_code": (s.get("rep_code") or "").strip().upper(),
            "rep_name": (s.get("rep_name") or "").strip(),
        }
    except Exception:
        return None


def require_login(request: Request) -> dict:
    u = _session_user(request)
    if not u:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return u


def require_admin(request: Request) -> dict:
    u = require_login(request)
    if u.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin required")
    return u


def _actor_from_session_or_initials(session_user: dict | None, initials: str | None) -> str:
    # Prefer explicit initials for backward compatibility, otherwise use rep_code, otherwise username.
    if initials and str(initials).strip():
        return _clean_actor(initials)
    if session_user:
        if session_user.get("rep_code"):
            return _clean_actor(session_user["rep_code"])
        if session_user.get("username"):
            return _clean_actor(session_user["username"])
    return "SYSTEM"

def _stamp_order_user_ids(order: Order, session_user: dict | None, *, created: bool = False, deleted: bool = False) -> None:
    """Populate the new user-id audit columns on Order from the current session user.

    - created=True sets created_by_user_id (and also updated_by_user_id)
    - deleted=True sets deleted_by_user_id (and also updated_by_user_id)
    Always sets updated_by_user_id when a user_id is present.
    """
    try:
        if not session_user:
            return
        uid = session_user.get("user_id")
        if uid is None:
            return
        # tolerate string ids
        try:
            uid_int = int(uid)
        except Exception:
            return

        if created and hasattr(order, "created_by_user_id"):
            try:
                setattr(order, "created_by_user_id", uid_int)
            except Exception:
                pass

        if deleted and hasattr(order, "deleted_by_user_id"):
            try:
                setattr(order, "deleted_by_user_id", uid_int)
            except Exception:
                pass

        if hasattr(order, "updated_by_user_id"):
            try:
                setattr(order, "updated_by_user_id", uid_int)
            except Exception:
                pass
    except Exception:
        # never let audit stamping break endpoint behavior
        return



class ClientSuggestItem(BaseModel):
    id: int
    client_name: str
    company_name: str | None = None


class ClientResponse(BaseModel):
    id: int
    client_name: str
    company_name: str | None = None
    is_active: bool


class ClientCreate(BaseModel):
    client_name: str
    company_name: str | None = None
    is_active: bool | None = True


class ClientUpdate(BaseModel):
    client_name: str | None = None
    company_name: str | None = None
    is_active: bool | None = None


class OrderSearchResponse(BaseModel):
    total: int
    items: list[OrderResponse]


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _order_snapshot(order: Order) -> dict:
    sp_num = None
    try:
        sp_num = order.sp.sp_number if getattr(order, "sp", None) else None
    except Exception:
        sp_num = None

    return {
        "id": order.id,
        "artist": order.artist,
        "asset_type": order.asset_type,
        "status": getattr(order, "status", None),
        "rep_name": getattr(order, "rep_name", None),
        "rep_code": getattr(order, "rep_code", None),
        "sp_number": sp_num,
        "sp_id": getattr(order, "sp_id", None),
        "client_name": getattr(order, "client_name", None),
        "client_company_name": getattr(order, "client_company_name", None),
        "notes": getattr(order, "notes", None),
        "instructions": getattr(order, "instructions", None),
        "trello_card_id": getattr(order, "trello_card_id", None),
        "trello_checklist_id": getattr(order, "trello_checklist_id", None),
        "is_deleted": getattr(order, "is_deleted", None),
        "deleted_at": getattr(order, "deleted_at", None),
        "deleted_by": getattr(order, "deleted_by", None),
    }


def _audit(
    db: Session,
    action: str,
    actor: str,
    order: Order | None = None,
    details: dict | None = None,
) -> None:
    payload = details or {}
    if order is not None:
        payload.setdefault("order", _order_snapshot(order))
    row = AuditLog(
        ts=_now_iso(),
        action=action,
        actor=actor,
        order_id=(order.id if order is not None else None),
        details_json=json.dumps(payload, ensure_ascii=False),
    )
    db.add(row)


def _clean_actor(initials: str | None) -> str:
    s = (initials or "").strip().upper()
    if not s:
        return "SYSTEM"
    if len(s) > 12:
        return s[:12]
    return s


def _diff_dict(before: dict, after: dict, keys: list[str]) -> dict:
    out = {}
    for k in keys:
        if before.get(k) != after.get(k):
            out[k] = {"before": before.get(k), "after": after.get(k)}
    return out


def _prepend_line(text: str | None, first_line: str) -> str:
    """Prepend a single line to a text blob, keeping existing content below it."""
    if not first_line:
        return text or ""
    existing = text or ""
    # Avoid duplicating the prefix if it already exists
    if existing.startswith(first_line):
        return existing
    if existing:
        return f"{first_line}\n{existing}"
    return first_line


def _parent_display(order: Order) -> str | None:
    """Return FM-style non-editable parent label for copy/paste."""
    try:
        sp = getattr(order, 'sp', None)
        if sp is None:
            return None
        rev = getattr(sp, 'revision_of', None)
        if rev:
            return f"Revision of {rev}"
        addl = getattr(sp, 'additional_version_of', None)
        if addl:
            return f"Add'l vers of {addl}"
        return None
    except Exception:
        return None



def _strip_auto_parent_prefixes(text: str | None) -> str:
    """Strip stacked auto-generated parent reference lines from the top of notes/instructions.

    We only want the immediate parent reference to appear on newly-created revision/add'l-vers orders.
    Older generations may already contain one or more of these lines; strip them so we don't stack forever.
    """
    if not text:
        return ""
    lines = text.splitlines()

    header_re = re.compile(r"^(revision of\s+SP\d+|add'l vers of\s+SP\d+)\s*$", re.IGNORECASE)

    i = 0
    saw_header = False
    while i < len(lines):
        line = lines[i].strip()
        if header_re.match(line):
            saw_header = True
            i += 1
            continue
        if saw_header and line == "":
            i += 1
            continue
        break

    cleaned = "\n".join(lines[i:])
    if saw_header:
        cleaned = cleaned.lstrip("\n")
    return cleaned


def _default_notes_for_new_order(asset_type: str, existing_notes: str | None) -> str | None:
    """Return default boilerplate notes for NEW orders by asset_type (radio/video only)."""
    at = (asset_type or "").strip().lower()
    if at == "radio":
        template = "**Voice**\n\n**Music**\n\n**Audio**"
    elif at == "video":
        template = "**Voice**\n\n**Music**\n\n**Audio**\n\n**Video**\n\nDrop files here: "
    else:
        return None

    existing = existing_notes or ""
    if existing.strip():
        # Put template at the top, keep user's content below with a blank line separator.
        return f"{template}\n\n{existing.lstrip()}"
    return template



@router.get("/", response_model=list[OrderResponse])
def list_orders(
    request: Request,
    db: Session = Depends(get_db),
    include_deleted: bool = Query(default=False, description="Include soft-deleted orders (admin use)."),
    session_user: dict = Depends(require_login),
):
    if include_deleted:
        if session_user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Admin required for include_deleted")

    q = db.query(Order)
    if not include_deleted:
        q = q.filter(or_(Order.is_deleted == False, Order.is_deleted.is_(None)))

    return (
        q
        .options(joinedload(Order.sp))
        .order_by(Order.id.desc())
        .all()
    )


# IMPORTANT:
# Static routes MUST come before "/{order_id}" or Starlette may match "search"/"new" as order_id.
def _orders_search_query(
    db: Session,
    *,
    artist: str | None,
    notes: str | None,
    asset_type: str | None,
    sp_number: str | None,
    client_name: str | None,
    client_company: str | None,
    client_company_name: str | None,
    status: str | None,
    rep_code: str | None,
    include_deleted: bool,
):
    q = db.query(Order)

    if not include_deleted:
        q = q.filter(Order.deleted_at.is_(None))

    if artist:
        a = artist.strip()
        q = q.filter(Order.artist.ilike(f"%{a}%"))

    if notes:
        n = notes.strip()
        q = q.filter(Order.notes.ilike(f"%{n}%"))

    if asset_type:
        q = q.filter(func.lower(func.trim(Order.asset_type)) == asset_type.strip().lower())

    if status:
        q = q.filter(func.lower(func.trim(Order.status)) == status.strip().lower())

    if rep_code:
        q = q.filter(func.upper(func.trim(Order.rep_code)) == rep_code.strip().upper())

    if sp_number:
        sn = sp_number.strip()
        # join SPNumber table only when needed
        q = q.join(SPNumber, Order.sp_id == SPNumber.id).filter(SPNumber.sp_number.ilike(f"%{sn}%"))

    if client_name:
        cn = client_name.strip()
        q = q.filter(Order.client_name.ilike(f"%{cn}%"))

    company_q = (client_company_name or client_company or "").strip()
    if company_q:
        q = q.filter(Order.client_company_name.ilike(f"%{company_q}%"))

    return q
def _apply_client_snapshot(db: Session, order: Order, client_id: int) -> None:
    """Set order.client_id and snapshot client_name/company from clients table.

    IMPORTANT: If the selected Client row has a blank company_name, but the Order currently
    has a non-blank client_company_name (user typed it / UI filled it), we "heal" the Client
    row by writing that company_name back to the Client before snapshotting. This prevents
    poisoned client rows from forever forcing company_name back to blank.
    """
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    if getattr(client, "is_active", True) is False:
        # still allow selecting inactive? keep strict for now
        raise HTTPException(status_code=400, detail="Client is inactive")

    incoming_company = (getattr(order, "client_company_name", None) or "").strip() or None
    if incoming_company:
        existing_company = (getattr(client, "company_name", None) or "").strip() or None
        if not existing_company:
            try:
                client.company_name = incoming_company
                db.flush()
            except Exception:
                # never block snapshot behavior
                pass

    order.client_id = client.id
    # Snapshot fields used in UI/export/emails (do NOT rewrite history later)
    order.client_name = client.client_name
    order.client_company_name = getattr(client, "company_name", None)


@router.get("/search", response_model=list[OrderResponse])
def search_orders(
    request: Request,
    db: Session = Depends(get_db),
    artist: str | None = Query(default=None, description="Artist contains (case-insensitive)."),
    notes: str | None = Query(default=None, description="Notes contains (case-insensitive)."),
    asset_type: str | None = Query(default=None, description="Asset type equals (radio/video/art)."),
    sp_number: str | None = Query(default=None, description="SP number contains (case-insensitive)."),
    client_name: str | None = Query(default=None, description="Client name contains (case-insensitive)."),
    client_company_name: str | None = Query(default=None, description="Client company contains (case-insensitive)."),
    client_company: str | None = Query(default=None, description="Client company contains (case-insensitive). (legacy param name)"),
    status: str | None = Query(default=None, description="draft or finalized"),
    rep_code: str | None = Query(default=None, description="Rep initials equals (e.g., SB)."),
    limit: int = Query(default=200, ge=1, le=1000, description="Max rows to return (pagination)."),
    offset: int = Query(default=0, ge=0, description="Rows to skip (pagination)."),
    include_deleted: bool = Query(default=False, description="Include soft-deleted orders (admin use)."),
    session_user: dict = Depends(require_login),
):
    if include_deleted:
        if session_user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Admin required for include_deleted")

    q = _orders_search_query(
        db,
        artist=artist,
        notes=notes,
        asset_type=asset_type,
        sp_number=sp_number,
        client_name=client_name,
        client_company=client_company,
        client_company_name=client_company_name,
        status=status,
        rep_code=rep_code,
        include_deleted=include_deleted,
    )

    q = q.order_by(Order.id.desc())
    q = q.offset(offset).limit(limit)
    return q.all()


@router.get("/search2", response_model=OrderSearchResponse)
def search_orders2(
    request: Request,
    db: Session = Depends(get_db),
    artist: str | None = Query(default=None, description="Artist contains (case-insensitive)."),
    notes: str | None = Query(default=None, description="Notes contains (case-insensitive)."),
    asset_type: str | None = Query(default=None, description="Asset type equals (radio/video/art)."),
    sp_number: str | None = Query(default=None, description="SP number contains (case-insensitive)."),
    client_name: str | None = Query(default=None, description="Client name contains (case-insensitive)."),
    client_company: str | None = Query(default=None, description="Client company contains (case-insensitive)."),
    client_company_name: str | None = Query(default=None, description="Client company contains (case-insensitive). (legacy param name)"),
    status: str | None = Query(default=None, description="draft or finalized (exact)."),
    rep_code: str | None = Query(default=None, description="Rep initials equals (e.g., SB)."),
    limit: int = Query(default=200, ge=1, le=1000, description="Max rows to return (pagination)."),
    offset: int = Query(default=0, ge=0, description="Rows to skip (pagination)."),
    include_deleted: bool = Query(default=False, description="Include soft-deleted orders (admin use)."),
):
    q = _orders_search_query(
        db,
        artist=artist,
        notes=notes,
        asset_type=asset_type,
        sp_number=sp_number,
        client_name=client_name,
        client_company=client_company,
        client_company_name=client_company_name,
        status=status,
        rep_code=rep_code,
        include_deleted=include_deleted,
    )

    total = q.order_by(None).count()
    items = (
        q.order_by(Order.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return {"total": total, "items": items}


# ---------------- Clients (fast version: company_name is plain text) ----------------

@router.get("/clients/suggest", response_model=list[ClientSuggestItem])
def clients_suggest(
    request: Request,
    q: str = Query(..., min_length=1, description="Client name search."),
    limit: int = Query(default=10, ge=1, le=50),
    include_inactive: bool = Query(default=False, description="Include inactive clients (admin use)."),
    db: Session = Depends(get_db),
    session_user: dict = Depends(require_login),
):
    qq = (q or "").strip()
    if not qq:
        return []

    if include_inactive and (session_user or {}).get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin required for include_inactive")

    qry = db.query(Client)
    if not include_inactive:
        qry = qry.filter(or_(Client.is_active == True, Client.is_active.is_(None)))

    # Case-insensitive contains search
    like = f"%{qq}%"
    qry = qry.filter(Client.client_name.ilike(like))

    rows = (
        qry.order_by(func.lower(Client.client_name).asc(), case((Client.company_name.is_(None), 1), else_=0).asc(), Client.id.asc())
        .limit(limit)
        .all()
    )

    return [
        {
            "id": r.id,
            "client_name": r.client_name,
            "company_name": getattr(r, "company_name", None),
        }
        for r in rows
    ]


@router.get("/clients/{client_id}", response_model=ClientResponse)
def get_client(
    request: Request,
    client_id: int,
    db: Session = Depends(get_db),
    session_user: dict = Depends(require_login),
):
    c = db.query(Client).filter(Client.id == client_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Client not found")
    return {
        "id": c.id,
        "client_name": c.client_name,
        "company_name": getattr(c, "company_name", None),
        "is_active": bool(getattr(c, "is_active", True)),
    }


@router.post("/clients", response_model=ClientResponse)
def create_client(
    request: Request,
    payload: ClientCreate,
    db: Session = Depends(get_db),
    session_user: dict = Depends(require_admin),
):
    name = (payload.client_name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="client_name is required")

    company = (payload.company_name or "").strip() or None

    # 1) Exact match: same client_name + same company_name (case-insensitive).
    if company:
        exact = (
            db.query(Client)
            .filter(func.lower(func.trim(Client.client_name)) == name.lower())
            .filter(func.lower(func.trim(Client.company_name)) == company.lower())
            .first()
        )
        if exact:
            if payload.is_active is not None:
                try:
                    exact.is_active = bool(payload.is_active)
                except Exception:
                    pass
                db.commit()
                db.refresh(exact)
            return {
                "id": exact.id,
                "client_name": exact.client_name,
                "company_name": getattr(exact, "company_name", None),
                "is_active": bool(getattr(exact, "is_active", True)),
            }

        # 2) Poisoned match: same client_name exists but has blank/NULL company_name.
        # If the user supplies a company now, update the existing row instead of returning a forever-blank client.
        poisoned = (
            db.query(Client)
            .filter(func.lower(func.trim(Client.client_name)) == name.lower())
            .filter(or_(Client.company_name.is_(None), func.trim(Client.company_name) == ""))
            .order_by(Client.id.asc())
            .first()
        )
        if poisoned:
            poisoned.company_name = company
            if payload.is_active is not None:
                try:
                    poisoned.is_active = bool(payload.is_active)
                except Exception:
                    pass
            db.commit()
            db.refresh(poisoned)
            return {
                "id": poisoned.id,
                "client_name": poisoned.client_name,
                "company_name": getattr(poisoned, "company_name", None),
                "is_active": bool(getattr(poisoned, "is_active", True)),
            }

    # 3) If company wasn't provided, avoid making duplicates: return the best existing match (prefer non-null company).
    if not company:
        existing_any = (
            db.query(Client)
            .filter(func.lower(func.trim(Client.client_name)) == name.lower())
            .order_by(case((Client.company_name.is_(None), 1), else_=0).asc(), Client.id.asc())
            .first()
        )
        if existing_any:
            if payload.is_active is not None:
                try:
                    existing_any.is_active = bool(payload.is_active)
                except Exception:
                    pass
                db.commit()
                db.refresh(existing_any)
            return {
                "id": existing_any.id,
                "client_name": existing_any.client_name,
                "company_name": getattr(existing_any, "company_name", None),
                "is_active": bool(getattr(existing_any, "is_active", True)),
            }

    # 4) Create a new client row.
    c = Client(
        client_name=name,
        company_name=company,
        is_active=(payload.is_active if payload.is_active is not None else True),
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return {
        "id": c.id,
        "client_name": c.client_name,
        "company_name": getattr(c, "company_name", None),
        "is_active": bool(getattr(c, "is_active", True)),
    }


@router.patch("/clients/{client_id}", response_model=ClientResponse)
def update_client(
    request: Request,
    client_id: int,
    payload: ClientUpdate,
    db: Session = Depends(get_db),
    session_user: dict = Depends(require_admin),
):
    c = db.query(Client).filter(Client.id == client_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Client not found")

    if payload.client_name is not None:
        name = (payload.client_name or "").strip()
        if not name:
            raise HTTPException(status_code=400, detail="client_name cannot be blank")
        c.client_name = name

    if payload.company_name is not None:
        c.company_name = (payload.company_name or "").strip() or None

    if payload.is_active is not None:
        c.is_active = bool(payload.is_active)

    db.commit()
    db.refresh(c)
    return {
        "id": c.id,
        "client_name": c.client_name,
        "company_name": getattr(c, "company_name", None),
        "is_active": bool(getattr(c, "is_active", True)),
    }




@router.post("/new", response_model=OrderResponse)
def create_order(
    request: Request,
    payload: OrderCreateWithRep,
    db: Session = Depends(get_db),
    session_user: dict = Depends(require_login),
    initials: str | None = Query(default=None, description="Your initials for audit log (optional)."),
):
    # Notes/instructions compatibility: accept Notes sent as "instructions" from older UIs.
    try:
        if getattr(payload, "notes", None) is None and getattr(payload, "instructions", None) is not None:
            payload.notes = payload.instructions  # type: ignore[attr-defined]
        if getattr(payload, "instructions", None) is None and getattr(payload, "notes", None) is not None:
            payload.instructions = payload.notes  # type: ignore[attr-defined]
    except Exception:
        pass

    # Auto-prepend default boilerplate for NEW radio/video orders (art excluded).
    default_notes = _default_notes_for_new_order(payload.asset_type, getattr(payload, "notes", None))
    if default_notes is not None:
        payload.notes = default_notes

    # Rep assignment rules:

    # Rep assignment:
    # - If rep_code/rep_name is provided, we accept it (used when creating an order for another rep).
    # - If omitted, default to the logged-in user’s rep_code/rep_name.
    desired_rep_code = (getattr(payload, "rep_code", None) or "").strip() or None
    desired_rep_name = (getattr(payload, "rep_name", None) or "").strip() or None

    # If only a "RM - Ron Mewis" style name came in, infer rep_code prefix.
    if not desired_rep_code and desired_rep_name:
        m = re.match(r"^\s*([A-Za-z0-9]{1,6})\s*[-–—]\s*.+$", desired_rep_name)
        if m:
            desired_rep_code = m.group(1).strip().upper()

    # Default to session rep if nothing was specified.
    if not desired_rep_code:
        desired_rep_code = (session_user.get("rep_code") or "").strip().upper() or None
    if not desired_rep_name:
        desired_rep_name = (session_user.get("rep_name") or "").strip() or (desired_rep_code or None)

    # Normalize
    if desired_rep_code:
        desired_rep_code = desired_rep_code.strip().upper()

    # Force the payload rep fields so the service layer persists them.
    try:
        setattr(payload, "rep_code", desired_rep_code)
        setattr(payload, "rep_name", desired_rep_name)
    except Exception:
        pass

    created = create_order_service(db, payload)

    # Reload with SP joined for consistent snapshot + API response.
    created = (
        db.query(Order)
        .options(joinedload(Order.sp))
        .filter(Order.id == created.id)
        .first()
    )


    # Client snapshot wiring: if client_id provided, link + snapshot from clients table.
    payload_client_id = getattr(payload, "client_id", None)
    if payload_client_id is not None:
        try:
            _apply_client_snapshot(db, created, int(payload_client_id))
            db.commit()
            db.refresh(created)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to apply client snapshot: {e}")

    _stamp_order_user_ids(created, session_user, created=True)
    actor = _actor_from_session_or_initials(session_user, initials)
    _audit(db, action="create", actor=actor, order=created, details={"endpoint": "/orders/new"})
    db.commit()

    return created


@router.post("/{order_id}/finalize", response_model=OrderResponse)
def finalize(
    request: Request,
    order_id: int,
    trello_card_id: str | None = Query(default=None, description="Optional: Trello card id. If omitted, uses stored value on the order."),
    trello_checklist_id: str | None = Query(default=None, description="Optional: Trello checklist id. If omitted, uses stored value on the order."),
    db: Session = Depends(get_db),
    session_user: dict = Depends(require_login),
    initials: str | None = Query(default=None, description="Your initials for audit log (optional)."),
):
    order = db.query(Order).options(joinedload(Order.sp)).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    before = _order_snapshot(order)

    is_admin = ((session_user or {}).get("role") == "admin")

    # Prefer explicit query params; otherwise fall back to stored linkage on the order.
    card_id = (trello_card_id or "").strip() or (getattr(order, "trello_card_id", None) or "").strip()
    checklist_id = (trello_checklist_id or "").strip() or (getattr(order, "trello_checklist_id", None) or "").strip()

    # Let the service handle missing Trello linkage:
    # - radio/video: auto-create Trello card + SP# checklist if missing
    # - other assets: will raise if linkage is missing (art comes later)
    try:
        updated = finalize_order(
            db,
            order,
            (card_id or None),
            (checklist_id or None),
        )
    except TrelloConfigError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Ensure SP joined (finalize_order may return the same instance, but we want a stable snapshot)
    updated = (
        db.query(Order)
        .options(joinedload(Order.sp))
        .filter(Order.id == order_id)
        .first()
    )

    _stamp_order_user_ids(updated, session_user)

    after = _order_snapshot(updated)
    actor = _actor_from_session_or_initials(session_user, initials)
    _audit(
        db,
        action="finalize",
        actor=actor,
        order=updated,
        details={
            "before": before,
            "after": after,
            "changes": _diff_dict(before, after, ["status", "finalized_at", "trello_card_id", "trello_checklist_id"]),
        },
    )
    db.commit()

    return updated


@router.post("/{order_id}/unfinalize", response_model=OrderResponse)
def unfinalize_order(
    request: Request,
    order_id: int,
    db: Session = Depends(get_db),
    session_user: dict = Depends(require_login),
    initials: str | None = Query(default=None, description="Your initials for audit log (optional)."),
):
    """Reopen a finalized order back to draft (no Trello required)."""
    order = (
        db.query(Order)
        .options(joinedload(Order.sp))
        .filter(Order.id == order_id)
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    before = _order_snapshot(order)

    # Always force it back to draft, even if it's already draft (idempotent)
    order.status = "draft"
    order.finalized_at = None


    _stamp_order_user_ids(order, session_user)
    after = _order_snapshot(order)

    actor = _actor_from_session_or_initials(session_user, initials)
    _audit(
        db,
        action="unfinalize",
        actor=actor,
        order=order,
        details={
            "before": before,
            "after": after,
            "changes": _diff_dict(before, after, ["status", "finalized_at"]),
        },
    )

    db.commit()
    db.refresh(order)
    return order



@router.post("/{order_id}/revise", response_model=OrderResponse)
def revise_order(
    request: Request,
    order_id: int,
    db: Session = Depends(get_db),
    session_user: dict = Depends(require_login),
    initials: str | None = Query(default=None, description="Your initials for audit log (optional)."),
):
    parent = db.query(Order).options(joinedload(Order.sp)).filter(Order.id == order_id).first()
    if not parent:
        raise HTTPException(status_code=404, detail="Order not found")

    parent_sp = (parent.sp.sp_number if getattr(parent, "sp", None) else None)
    prefix_line = f"Revision of {parent_sp}" if parent_sp else ""
    base_notes = _strip_auto_parent_prefixes(parent.notes)
    base_instructions = _strip_auto_parent_prefixes(getattr(parent, "instructions", None))
    child_notes = base_notes
    child_instructions = base_instructions

    payload = OrderCreate(
        artist=parent.artist,
        asset_type=parent.asset_type,
        rep_name=getattr(parent, "rep_name", None),
        rep_code=getattr(parent, "rep_code", None),
        notes=child_notes,

        client_name=getattr(parent, "client_name", None),
        client_company_name=getattr(parent, "client_company_name", None),

        order_type=getattr(parent, "order_type", None),
        description=getattr(parent, "description", None),
        length=getattr(parent, "length", None),
        instructions=child_instructions,

        is_revision=True,
        parent_order_id=parent.id,
        revision_of=(parent.sp.sp_number if getattr(parent, "sp", None) else None),
    )

    new_order = create_order_service(db, payload)
    # Revisions should stay on the SAME Trello card as the parent (if it exists).
    # IMPORTANT: we do NOT carry forward the checklist id, so finalize will create a fresh SP# checklist
    # on the existing card for this revision.
    parent_card_id = (getattr(parent, "trello_card_id", None) or "").strip()
    parent_checklist_id = (getattr(parent, "trello_checklist_id", None) or "").strip()
    
    resolved_card_id = None
    if parent_card_id and card_exists(parent_card_id):
        resolved_card_id = parent_card_id
    elif parent_checklist_id and card_exists(parent_checklist_id):
        # Looks like the parent stored IDs were swapped (card id stored in trello_checklist_id). Repair parent and use the real card id.
        resolved_card_id = parent_checklist_id
        if parent_card_id:
            parent.trello_checklist_id = parent_card_id
        parent.trello_card_id = parent_checklist_id
        db.commit()
    
    if resolved_card_id:
        new_order.trello_card_id = resolved_card_id
        new_order.trello_checklist_id = None

    # Carry forward rep fields from parent (create service may apply defaults)
    if getattr(parent, "rep_name", None) is not None:
        new_order.rep_name = parent.rep_name
    if getattr(parent, "rep_code", None) is not None:
        new_order.rep_code = parent.rep_code
    db.commit()
    db.refresh(new_order)

    _stamp_order_user_ids(new_order, session_user, created=True)


    # Ensure the SP record also tracks the revision chain



    if getattr(new_order, "sp_id", None):
        sp = db.query(SPNumber).filter(SPNumber.id == new_order.sp_id).first()
        if sp:
            sp.revision_of = (parent.sp.sp_number if getattr(parent, "sp", None) else None)
            db.commit()

    # Reload with SP joined for consistent API response
    new_order = (
        db.query(Order)
        .options(joinedload(Order.sp))
        .filter(Order.id == new_order.id)
        .first()
    )

    actor = _actor_from_session_or_initials(session_user, initials)
    _audit(db, action="create", actor=actor, order=new_order, details={"kind": "revision", "parent_order_id": parent.id})
    db.commit()

    return new_order


@router.post("/{order_id}/addl_vers", response_model=OrderResponse)
def addl_vers_order(
    request: Request,
    order_id: int,
    db: Session = Depends(get_db),
    session_user: dict = Depends(require_login),
    initials: str | None = Query(default=None, description="Your initials for audit log (optional)."),
):
    parent = db.query(Order).options(joinedload(Order.sp)).filter(Order.id == order_id).first()
    if not parent:
        raise HTTPException(status_code=404, detail="Order not found")

    parent_sp = (parent.sp.sp_number if getattr(parent, "sp", None) else None)
    prefix_line = f"Add'l vers of {parent_sp}" if parent_sp else ""
    base_notes = _strip_auto_parent_prefixes(parent.notes)
    base_instructions = _strip_auto_parent_prefixes(getattr(parent, "instructions", None))
    child_notes = base_notes
    child_instructions = base_instructions

    payload = OrderCreate(
        artist=parent.artist,
        asset_type=parent.asset_type,
        rep_name=getattr(parent, "rep_name", None),
        rep_code=getattr(parent, "rep_code", None),
        notes=child_notes,

        client_name=getattr(parent, "client_name", None),
        client_company_name=getattr(parent, "client_company_name", None),

        order_type=getattr(parent, "order_type", None),
        description=getattr(parent, "description", None),
        length=getattr(parent, "length", None),
        instructions=child_instructions,

        is_revision=False,
        parent_order_id=parent.id,
        revision_of=None,
    )

    new_order = create_order_service(db, payload)
    # Carry forward rep fields from parent (create service may apply defaults)
    if getattr(parent, "rep_name", None) is not None:
        new_order.rep_name = parent.rep_name
    if getattr(parent, "rep_code", None) is not None:
        new_order.rep_code = parent.rep_code
    db.commit()
    db.refresh(new_order)

    _stamp_order_user_ids(new_order, session_user, created=True)


    # Track additional-version chain on the SP record (immediate parent only)
    if getattr(new_order, "sp_id", None):
        sp = db.query(SPNumber).filter(SPNumber.id == new_order.sp_id).first()
        if sp:
            sp.additional_version_of = (parent.sp.sp_number if getattr(parent, "sp", None) else None)
            db.commit()

    # Reload with SP joined for consistent API response
    new_order = (
        db.query(Order)
        .options(joinedload(Order.sp))
        .filter(Order.id == new_order.id)
        .first()
    )

    actor = _actor_from_session_or_initials(session_user, initials)
    _audit(db, action="create", actor=actor, order=new_order, details={"kind": "addl_vers", "parent_order_id": parent.id})
    db.commit()

    return new_order





@router.post("/{order_id}/duplicate", response_model=OrderResponse)
def duplicate_order(
    request: Request,
    order_id: int,
    db: Session = Depends(get_db),
    session_user: dict = Depends(require_login),
    initials: str | None = Query(default=None, description="Your initials for audit log (optional)."),
):
    """Create a fresh draft copy of an order with the same fields (no revision/addl links)."""
    parent = db.query(Order).options(joinedload(Order.sp)).filter(Order.id == order_id).first()
    if not parent:
        raise HTTPException(status_code=404, detail="Order not found")

    payload = OrderCreate(
        artist=parent.artist,
        asset_type=parent.asset_type,
        rep_name=getattr(parent, "rep_name", None),
        rep_code=getattr(parent, "rep_code", None),
        notes=parent.notes,

        client_name=getattr(parent, "client_name", None),
        client_company_name=getattr(parent, "client_company_name", None),

        order_type=getattr(parent, "order_type", None),
        description=getattr(parent, "description", None),
        length=getattr(parent, "length", None),
        instructions=getattr(parent, "instructions", None),

        is_revision=False,
        parent_order_id=None,
        revision_of=None,
    )

    new_order = create_order_service(db, payload)
    # Carry forward rep fields from parent (create service may apply defaults)
    if getattr(parent, "rep_name", None) is not None:
        new_order.rep_name = parent.rep_name
    if getattr(parent, "rep_code", None) is not None:
        new_order.rep_code = parent.rep_code
    db.commit()
    db.refresh(new_order)

    _stamp_order_user_ids(new_order, session_user, created=True)


    # Reload with SP joined for consistent API response
    new_order = (
        db.query(Order)
        .options(joinedload(Order.sp))
        .filter(Order.id == new_order.id)
        .first()
    )

    actor = _actor_from_session_or_initials(session_user, initials)
    _audit(db, action="create", actor=actor, order=new_order, details={"kind": "duplicate", "source_order_id": parent.id})
    db.commit()

    return new_order


@router.get("/deleted")
def list_deleted_orders(
    request: Request,
    db: Session = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session_user: dict = Depends(require_login),
):
    """Admin-only: list soft-deleted orders (newest first)."""
    if (session_user or {}).get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin required")

    q = db.query(Order).options(joinedload(Order.sp)).filter(
        or_(Order.is_deleted == True, Order.deleted_at.isnot(None))
    )

    total = q.count()
    items = (
        q.order_by(Order.deleted_at.desc())
         .offset(offset)
         .limit(limit)
         .all()
    )

    def _summary(o: Order) -> dict:
        return {
            "id": getattr(o, "id", None),
            "artist": getattr(o, "artist", None),
            "asset_type": getattr(o, "asset_type", None),
            "status": getattr(o, "status", None),
            "deleted_at": getattr(o, "deleted_at", None),
            "deleted_by": getattr(o, "deleted_by", None),
        }

    return {"total": total, "items": [_summary(o) for o in items]}


@router.post("/{order_id}/restore")
def restore_deleted_order(
    request: Request,
    order_id: int,
    db: Session = Depends(get_db),
    session_user: dict = Depends(require_login),
):
    """Admin-only: restore a soft-deleted order. Idempotent."""
    if (session_user or {}).get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin required")

    order = db.query(Order).options(joinedload(Order.sp)).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # No-op if not deleted
    if not getattr(order, "is_deleted", False) and getattr(order, "deleted_at", None) is None:
        return {"status": "noop", "id": order_id}

    before = _order_snapshot(order)

    is_admin = ((session_user or {}).get("role") == "admin")

    if hasattr(order, "is_deleted"):
        order.is_deleted = False
    if hasattr(order, "deleted_at"):
        order.deleted_at = None
    if hasattr(order, "deleted_by"):
        order.deleted_by = None
    if hasattr(order, "deleted_by_user_id"):
        setattr(order, "deleted_by_user_id", None)

    after = _order_snapshot(order)

    actor = _actor_from_session_or_initials(session_user, None)
    _audit(db, action="restore", actor=actor, order=order, details={"changes": _diff_dict(before, after, ["is_deleted", "deleted_at", "deleted_by"])})

    db.commit()
    return {"status": "restored", "id": order_id}


@router.get("/{order_id}", response_model=OrderResponse)
def get_order(
    request: Request,
    order_id: int,
    db: Session = Depends(get_db),
    include_deleted: bool = Query(default=False, description="Include soft-deleted orders (admin use)."),
    session_user: dict = Depends(require_login),
):
    order = (
        db.query(Order)
        .options(joinedload(Order.sp))
        .filter(Order.id == order_id)
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if include_deleted:
        if session_user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Admin required for include_deleted")

    if not include_deleted and getattr(order, "is_deleted", False):
        raise HTTPException(status_code=404, detail="Order not found")

    # FM-style convenience label (non-editable)
    order.parent_display = _parent_display(order)

    return order


@router.delete("/{order_id}")
def delete_order(
    request: Request,
    order_id: int,
    initials: str = Query(..., description="Your initials (required)."),
    force: bool = Query(default=False, description="Allow deleting finalized orders."),
    db: Session = Depends(get_db),
    session_user: dict = Depends(require_login),
):
    order = db.query(Order).options(joinedload(Order.sp)).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    initials_clean = (initials or "").strip().upper()
    if not initials_clean or len(initials_clean) > 6 or not initials_clean.isalpha():
        raise HTTPException(status_code=400, detail="initials must be 1-6 letters")

    # Idempotent soft-delete
    if getattr(order, "is_deleted", False):
        return {"status": "deleted", "order_id": order_id, "initials": initials_clean, "soft": True, "already": True}

    if (order.status or "draft") == "finalized" and not force:
        raise HTTPException(status_code=400, detail="order is finalized; use force=true to delete")

    # Soft delete (do NOT delete SP rows; we want restore + audit later)
    order.is_deleted = True
    order.deleted_at = _now_iso()
    order.deleted_by = initials_clean


    _stamp_order_user_ids(order, session_user, deleted=True)
    _audit(
        db,
        action="delete",
        actor=initials_clean,
        order=order,
        details={"force": bool(force)},
    )

    db.commit()
    db.refresh(order)

    return {"status": "deleted", "order_id": order_id, "initials": initials_clean, "soft": True}


@router.patch("/{order_id}", response_model=OrderResponse)
def update_order(
    request: Request,
    order_id: int,
    payload: OrderUpdateWithRep,
    override: bool = Query(default=False, description="Allow override edit on finalized orders (unfinalizes to draft)."),
    db: Session = Depends(get_db),
    session_user: dict = Depends(require_login),
    initials: str | None = Query(default=None, description="Your initials for audit log (optional)."),
):
    order = db.query(Order).options(joinedload(Order.sp)).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if getattr(order, "is_deleted", False):
        raise HTTPException(status_code=404, detail="Order not found")

    before = _order_snapshot(order)

    # Track which fields were updated (for audit).
    touched_fields: list[str] = []

    # asset_type:
    # - Allowed for draft orders (common real-world fix: user picked wrong type)
    # - Allowed for finalized orders ONLY when override=true
    # - Always keep SP.order_type (and Order.order_type if present) in sync
    if payload.asset_type is not None and payload.asset_type != order.asset_type:
        old_asset = (getattr(order, "asset_type", "") or "").strip().lower()
        new_asset = (payload.asset_type or "").strip().lower()
        if new_asset not in {"radio", "video", "art"}:
            raise HTTPException(status_code=400, detail="asset_type must be one of: radio, video, art")

        is_finalized = (order.status or "draft") == "finalized"
        if is_finalized and not override:
            raise HTTPException(status_code=400, detail="asset_type cannot be changed")

        order.asset_type = new_asset
        touched_fields.append("asset_type")

        # Keep SP order_type in sync ONLY for radio/video.
        # If switching to ART, we intentionally do NOT mutate the SP row; ART orders don't use SP numbers.
        if new_asset in {"radio", "video"} and getattr(order, "sp", None) is not None:
            try:
                order.sp.order_type = new_asset
            except Exception:
                pass

        # Some builds also store order_type on the order row
        if hasattr(order, "order_type"):
            try:
                order.order_type = new_asset
                touched_fields.append("order_type")
            except Exception:
                pass


        # If switching INTO radio/video from ART (or any SP-less state), assign an SP# immediately.
        # This prevents "Art -> Radio/Video" orders from remaining SP-less forever.
        if new_asset in {"radio", "video"} and getattr(order, "sp_id", None) is None:
            try:
                sp_rec = generate_next_sp(db, new_asset)
                order.sp_id = sp_rec.id
                touched_fields.append("sp_id")
                # Attach relationship for immediate use (best-effort)
                try:
                    order.sp = sp_rec  # type: ignore[attr-defined]
                except Exception:
                    pass
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to assign SP number: {e}")

        # If switching INTO ART from radio/video, clear any existing SP linkage immediately.
        # ART orders must NOT carry an SP number. It's fine for sp_id to be blank until (re)finalize.
        if new_asset == "art" and getattr(order, "sp_id", None) is not None:
            try:
                order.sp_id = None
                touched_fields.append("sp_id")
            except Exception:
                pass
            # Best-effort: detach relationship cache so API responses don't show a stale sp_number.
            try:
                order.sp = None  # type: ignore[attr-defined]
            except Exception:
                pass

    # If this is an override edit of a finalized order, flip it back to draft NOW.
    # This is the whole point of override: user can edit, then finalize again.
    if override and (order.status or "").lower() == "finalized":
        order.status = "draft"
        touched_fields.append("status")
        # Clearing finalized_at is critical; otherwise /finalize is a no-op.
        try:
            order.finalized_at = None
            touched_fields.append("finalized_at")
        except Exception:
            pass

    # Rep reassignment.
    incoming_rep_code = (payload.rep_code or "").strip().upper()
    incoming_rep_name = (payload.rep_name or "").strip()

    rep_change_requested = bool(incoming_rep_code or incoming_rep_name)

    if rep_change_requested and not incoming_rep_code and incoming_rep_name:
        # Try infer rep_code from "RC - Name" style.
        if " - " in incoming_rep_name:
            incoming_rep_code = incoming_rep_name.split(" - ", 1)[0].strip().upper()

    # Determine whether any non-rep edits are requested (used for finalized gating).
    core_fields = ["notes", "client_name", "client_company_name"]
    other_edit_requested = False
    for f in core_fields:
        if getattr(payload, f, None) is not None:
            other_edit_requested = True
            break
    if getattr(payload, "asset_type", None) is not None and (payload.asset_type or "").strip():
        if (payload.asset_type or "").strip().lower() != (order.asset_type or "").strip().lower():
            other_edit_requested = True

    is_finalized = (order.status or "draft") == "finalized"
    is_admin = ((session_user or {}).get("role") == "admin")

    # Finalized orders are read-only unless override=true, except admin can change rep only.
    if is_finalized and not override:
        if rep_change_requested and not other_edit_requested:
            if not is_admin:
                raise HTTPException(status_code=400, detail="order is finalized; only admin can change rep")
        else:
            raise HTTPException(status_code=400, detail="order is finalized; use override=true to edit")

    # Apply rep change (if any).
    if rep_change_requested:
        if not incoming_rep_code:
            raise HTTPException(status_code=400, detail="rep_code is required to change rep")

        rep_user = (
            db.query(User)
            .filter(func.upper(User.rep_code) == incoming_rep_code.upper())
            .first()
        )
        resolved_rep_name = rep_user.rep_name if rep_user else incoming_rep_name

        order.rep_code = incoming_rep_code.upper()
        order.rep_name = (resolved_rep_name or "").strip()

        touched_fields.append("rep_code")
        touched_fields.append("rep_name")

# Apply allowed field updates (only if provided)
    # Notes/instructions compatibility: some UIs still use "instructions" as the Notes field.
    incoming_notes = getattr(payload, "notes", None)
    incoming_instructions = getattr(payload, "instructions", None)
    if incoming_notes is None and incoming_instructions is not None:
        incoming_notes = incoming_instructions
    if incoming_instructions is None and incoming_notes is not None:
        incoming_instructions = incoming_notes

    for field in [
        "artist",
        "notes",
        "client_name",
        "client_company_name",
        "order_type",
        "description",
        "length",
        "instructions",
        "is_revision",
        "parent_order_id",
        "revision_of",
    ]:
        if field == "notes":
            val = incoming_notes
        elif field == "instructions":
            val = incoming_instructions
        else:
            val = getattr(payload, field, None)
        if val is not None:
            setattr(order, field, val)
            touched_fields.append(field)

    # Client reassignment (optional): apply AFTER field updates so we can heal a poisoned client
    # using any company_name the user typed/filled on the order.
    if getattr(payload, "client_id", None) is not None:
        try:
            _apply_client_snapshot(db, order, int(payload.client_id))
            touched_fields.append("client_id")
            touched_fields.append("client_name")
            touched_fields.append("client_company_name")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to apply client snapshot: {e}")

    # If your OrderUpdate schema ever includes status, still block it here.
    if hasattr(payload, "status") and getattr(payload, "status") is not None:
        raise HTTPException(status_code=400, detail="status cannot be updated here; use /orders/{id}/finalize")
    _stamp_order_user_ids(order, session_user)


    db.commit()
    db.refresh(order)

    # Audit after all changes have settled (including possible Trello id changes)
    after = _order_snapshot(order)
    actor = _actor_from_session_or_initials(session_user, initials)
    _audit(
        db,
        action="update",
        actor=actor,
        order=order,
        details={
            "override": bool(override),
            "touched_fields": touched_fields,
            "before": before,
            "after": after,
            "changes": _diff_dict(before, after, [
                "artist",
                "asset_type",
                "notes",
                "client_name",
                "client_company_name",
                "order_type",
                "description",
                "length",
                "instructions",
                "trello_checklist_id",
            ]),
        },
    )
    db.commit()

    return order
