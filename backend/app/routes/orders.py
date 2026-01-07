# app/routes/orders.py

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

import json

def _audit_details(order, details=None):
    d = dict(details or {})
    d.setdefault("order_id", getattr(order, "id", None))
    d.setdefault("sp_id", getattr(order, "sp_id", None))
    d.setdefault("sp_number", getattr(getattr(order, "sp", None), "sp_number", None))
    d.setdefault("artist", getattr(order, "artist", None))
    d.setdefault("asset_type", getattr(order, "asset_type", None))
    d.setdefault("status", getattr(order, "status", None))
    return d


import datetime
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.database.session import get_db
from app.schemas.order import OrderCreate, OrderUpdate, OrderResponse
from app.models.orders import Order
from app.models.sp_master import SPNumber
from app.models.audit_log import AuditLog
from app.services.order_service import create_order as create_order_service, finalize_order
from app.services.trello_service import rebuild_order_checklist, TrelloConfigError

router = APIRouter(prefix="/orders", tags=["Orders"])

def _now_iso() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


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
    db: Session = Depends(get_db),
    include_deleted: bool = Query(default=False, description="Include soft-deleted orders (admin use)."),
):
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
@router.get("/search", response_model=list[OrderResponse])
def search_orders(
    db: Session = Depends(get_db),
    artist: str | None = Query(default=None, description="Artist contains (case-insensitive)."),
    notes: str | None = Query(default=None, description="Notes contains (case-insensitive)."),
    asset_type: str | None = Query(default=None, description="Asset type equals (radio/video/art)."),
    sp_number: str | None = Query(default=None, description="SP number contains (case-insensitive)."),
    client_name: str | None = Query(default=None, description="Client name contains (case-insensitive)."),
    client_company_name: str | None = Query(default=None, description="Client company contains (case-insensitive)."),
    status: str | None = Query(default=None, description="draft or finalized"),
    rep_code: str | None = Query(default=None, description="Rep initials equals (e.g., SB)."),
    include_deleted: bool = Query(default=False, description="Include soft-deleted orders (admin use)."),
):
    q = db.query(Order).options(joinedload(Order.sp))

    if not include_deleted:
        q = q.filter(or_(Order.is_deleted == False, Order.is_deleted.is_(None)))

    if artist:
        q = q.filter(Order.artist.ilike(f"%{artist.strip()}%"))
    if notes:
        q = q.filter(Order.notes.ilike(f"%{notes.strip()}%"))
    if asset_type:
        q = q.filter(Order.asset_type == asset_type.strip().lower())
    if client_name:
        q = q.filter(Order.client_name.ilike(f"%{client_name.strip()}%"))
    if client_company_name:
        q = q.filter(Order.client_company_name.ilike(f"%{client_company_name.strip()}%"))
    if status:
        q = q.filter(Order.status == status.strip().lower())

    if rep_code:
        q = q.filter(Order.rep_code == rep_code.strip().upper())

    if sp_number:
        sn = sp_number.strip()
        q = (
            q.join(SPNumber, Order.sp_id == SPNumber.id, isouter=True)
            .filter(SPNumber.sp_number.ilike(f"%{sn}%"))
        )

    return q.order_by(Order.id.desc()).all()


@router.post("/new", response_model=OrderResponse)
def create_order(
    payload: OrderCreate,
    db: Session = Depends(get_db),
    initials: str | None = Query(default=None, description="Your initials for audit log (optional)."),
):
    # Auto-prepend default boilerplate for NEW radio/video orders (art excluded).
    default_notes = _default_notes_for_new_order(payload.asset_type, getattr(payload, "notes", None))
    if default_notes is not None:
        payload.notes = default_notes

    created = create_order_service(db, payload)

    # Reload with SP joined for consistent snapshot + API response.
    created = (
        db.query(Order)
        .options(joinedload(Order.sp))
        .filter(Order.id == created.id)
        .first()
    )

    actor = _clean_actor(initials)
    _audit(db, action="create", actor=actor, order=created, details={"endpoint": "/orders/new"})
    db.commit()

    return created


@router.post("/{order_id}/finalize", response_model=OrderResponse)
def finalize(
    order_id: int,
    trello_card_id: str = Query(..., description="Trello card id that already exists for this order."),
    trello_checklist_id: str = Query(..., description="Checklist id on that card (named as SP Number)."),
    db: Session = Depends(get_db),
    initials: str | None = Query(default=None, description="Your initials for audit log (optional)."),
):
    order = db.query(Order).options(joinedload(Order.sp)).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    before = _order_snapshot(order)

    trello_card_id = (trello_card_id or "").strip()
    trello_checklist_id = (trello_checklist_id or "").strip()
    if not trello_card_id or not trello_checklist_id:
        raise HTTPException(status_code=400, detail="trello_card_id and trello_checklist_id are required")

    updated = finalize_order(db, order, trello_card_id, trello_checklist_id)

    # Ensure SP joined (finalize_order may return the same instance, but we want a stable snapshot)
    updated = (
        db.query(Order)
        .options(joinedload(Order.sp))
        .filter(Order.id == order_id)
        .first()
    )

    after = _order_snapshot(updated)
    actor = _clean_actor(initials)
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
    order_id: int,
    db: Session = Depends(get_db),
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

    after = _order_snapshot(order)

    actor = _clean_actor(initials)
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
    order_id: int,
    db: Session = Depends(get_db),
    initials: str | None = Query(default=None, description="Your initials for audit log (optional)."),
):
    parent = db.query(Order).options(joinedload(Order.sp)).filter(Order.id == order_id).first()
    if not parent:
        raise HTTPException(status_code=404, detail="Order not found")

    parent_sp = (parent.sp.sp_number if getattr(parent, "sp", None) else None)
    prefix_line = f"Revision of {parent_sp}" if parent_sp else ""
    child_notes = _prepend_line(parent.notes, prefix_line) if prefix_line else (parent.notes or "")
    child_instructions = _prepend_line(getattr(parent, "instructions", None), prefix_line) if prefix_line else (getattr(parent, "instructions", None) or "")

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

    actor = _clean_actor(initials)
    _audit(db, action="create", actor=actor, order=new_order, details={"kind": "revision", "parent_order_id": parent.id})
    db.commit()

    return new_order


@router.post("/{order_id}/addl_vers", response_model=OrderResponse)
def addl_vers_order(
    order_id: int,
    db: Session = Depends(get_db),
    initials: str | None = Query(default=None, description="Your initials for audit log (optional)."),
):
    parent = db.query(Order).options(joinedload(Order.sp)).filter(Order.id == order_id).first()
    if not parent:
        raise HTTPException(status_code=404, detail="Order not found")

    parent_sp = (parent.sp.sp_number if getattr(parent, "sp", None) else None)
    prefix_line = f"Add'l vers of {parent_sp}" if parent_sp else ""
    child_notes = _prepend_line(parent.notes, prefix_line) if prefix_line else (parent.notes or "")
    child_instructions = _prepend_line(getattr(parent, "instructions", None), prefix_line) if prefix_line else (getattr(parent, "instructions", None) or "")

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

    actor = _clean_actor(initials)
    _audit(db, action="create", actor=actor, order=new_order, details={"kind": "addl_vers", "parent_order_id": parent.id})
    db.commit()

    return new_order





@router.post("/{order_id}/duplicate", response_model=OrderResponse)
def duplicate_order(
    order_id: int,
    db: Session = Depends(get_db),
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

    # Reload with SP joined for consistent API response
    new_order = (
        db.query(Order)
        .options(joinedload(Order.sp))
        .filter(Order.id == new_order.id)
        .first()
    )

    actor = _clean_actor(initials)
    _audit(db, action="create", actor=actor, order=new_order, details={"kind": "duplicate", "source_order_id": parent.id})
    db.commit()

    return new_order

@router.get("/{order_id}", response_model=OrderResponse)
def get_order(
    order_id: int,
    db: Session = Depends(get_db),
    include_deleted: bool = Query(default=False, description="Include soft-deleted orders (admin use)."),
):
    order = (
        db.query(Order)
        .options(joinedload(Order.sp))
        .filter(Order.id == order_id)
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if not include_deleted and getattr(order, "is_deleted", False):
        raise HTTPException(status_code=404, detail="Order not found")

    return order


@router.delete("/{order_id}")
def delete_order(
    order_id: int,
    initials: str = Query(..., description="Your initials (required)."),
    force: bool = Query(default=False, description="Allow deleting finalized orders."),
    db: Session = Depends(get_db),
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
    order_id: int,
    payload: OrderUpdate,
    override: bool = Query(default=False, description="Allow editing finalized orders + sync Trello checklist."),
    db: Session = Depends(get_db),
    initials: str | None = Query(default=None, description="Your initials for audit log (optional)."),
):
    order = db.query(Order).options(joinedload(Order.sp)).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if getattr(order, "is_deleted", False):
        raise HTTPException(status_code=404, detail="Order not found")

    before = _order_snapshot(order)

    # asset_type is normally immutable.
    # EXCEPTION: draft "additional version" orders may change asset_type (e.g., radio -> video),
    # while still linking back to the original via additional_version_of.
    if payload.asset_type is not None and payload.asset_type != order.asset_type:
        new_asset = (payload.asset_type or "").strip().lower()
        if new_asset not in {"radio", "video", "art"}:
            raise HTTPException(status_code=400, detail="asset_type must be one of: radio, video, art")

        is_finalized = (order.status or "draft") == "finalized"
        is_addl = False
        try:
            is_addl = bool(getattr(getattr(order, "sp", None), "additional_version_of", None))
        except Exception:
            is_addl = False

        if is_finalized or not is_addl:
            raise HTTPException(status_code=400, detail="asset_type cannot be changed")

        order.asset_type = new_asset
        # Keep SP order_type in sync if present
        if getattr(order, "sp", None) is not None:
            try:
                order.sp.order_type = new_asset
            except Exception:
                pass
        # Some builds also store order_type on the order row
        if hasattr(order, "order_type"):
            try:
                order.order_type = new_asset
            except Exception:
                pass

    # finalized orders are read-only unless override=true
    if (order.status or "draft") == "finalized" and not override:
        raise HTTPException(status_code=400, detail="order is finalized; use override=true to edit")

    # Apply allowed field updates (only if provided)
    touched_fields: list[str] = []
    for field in [
        "artist",
        "rep_name",
        "rep_code",
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
        val = getattr(payload, field, None)
        if val is not None:
            setattr(order, field, val)
            touched_fields.append(field)

    # If your OrderUpdate schema ever includes status, still block it here.
    if hasattr(payload, "status") and getattr(payload, "status") is not None:
        raise HTTPException(status_code=400, detail="status cannot be updated here; use /orders/{id}/finalize")

    db.commit()
    db.refresh(order)

    # If this was an override edit on a finalized order with Trello linkage → rebuild checklist
    if override and (order.status or "").lower() == "finalized":
        if not order.trello_card_id or not order.trello_checklist_id:
            raise HTTPException(status_code=400, detail="finalized order missing trello_card_id/trello_checklist_id")
        try:
            checklist_name = "NEW"
            if getattr(order, "sp", None) and getattr(order.sp, "sp_number", None):
                checklist_name = order.sp.sp_number

            new_checklist_id = rebuild_order_checklist(
                card_id=order.trello_card_id,
                old_checklist_id=order.trello_checklist_id,
                checklist_name=checklist_name,
                notes=order.notes,
            )

            order.trello_checklist_id = new_checklist_id
            db.commit()
            db.refresh(order)
            touched_fields.append("trello_checklist_id")
        except TrelloConfigError as e:
            raise HTTPException(status_code=500, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Trello sync failed: {e}")

    # Audit after all changes have settled (including possible Trello id changes)
    after = _order_snapshot(order)
    actor = _clean_actor(initials)
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
                "rep_name",
                "rep_code",
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
