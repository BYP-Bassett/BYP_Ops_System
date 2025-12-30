# app/routes/orders.py

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.database.session import get_db
from app.schemas.order import OrderCreate, OrderUpdate, OrderResponse
from app.models.orders import Order
from app.models.sp_master import SPNumber
from app.services.order_service import create_order as create_order_service, finalize_order
from app.services.trello_service import rebuild_order_checklist, TrelloConfigError

router = APIRouter(prefix="/orders", tags=["Orders"])


@router.get("/", response_model=list[OrderResponse])
def list_orders(db: Session = Depends(get_db)):
    return (
        db.query(Order)
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
):
    q = db.query(Order).options(joinedload(Order.sp))

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

    if sp_number:
        sn = sp_number.strip()
        q = (
            q.join(SPNumber, Order.sp_id == SPNumber.id, isouter=True)
            .filter(SPNumber.sp_number.ilike(f"%{sn}%"))
        )

    return q.order_by(Order.id.desc()).all()


@router.post("/new", response_model=OrderResponse)
def create_order(payload: OrderCreate, db: Session = Depends(get_db)):
    return create_order_service(db, payload)


@router.post("/{order_id}/finalize", response_model=OrderResponse)
def finalize(
    order_id: int,
    trello_card_id: str = Query(..., description="Trello card id that already exists for this order."),
    trello_checklist_id: str = Query(..., description="Checklist id on that card (named as SP Number)."),
    db: Session = Depends(get_db),
):
    order = db.query(Order).options(joinedload(Order.sp)).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    trello_card_id = (trello_card_id or "").strip()
    trello_checklist_id = (trello_checklist_id or "").strip()
    if not trello_card_id or not trello_checklist_id:
        raise HTTPException(status_code=400, detail="trello_card_id and trello_checklist_id are required")

    return finalize_order(db, order, trello_card_id, trello_checklist_id)


@router.post("/{order_id}/revise", response_model=OrderResponse)
def revise_order(order_id: int, db: Session = Depends(get_db)):
    parent = db.query(Order).options(joinedload(Order.sp)).filter(Order.id == order_id).first()
    if not parent:
        raise HTTPException(status_code=404, detail="Order not found")

    payload = OrderCreate(
        artist=parent.artist,
        asset_type=parent.asset_type,
        notes=parent.notes,

        client_name=getattr(parent, "client_name", None),
        client_company_name=getattr(parent, "client_company_name", None),

        order_type=getattr(parent, "order_type", None),
        description=getattr(parent, "description", None),
        length=getattr(parent, "length", None),
        instructions=getattr(parent, "instructions", None),

        is_revision=True,
        parent_order_id=parent.id,
        revision_of=(parent.sp.sp_number if getattr(parent, "sp", None) else None),
    )
    return create_order_service(db, payload)


@router.get("/{order_id}", response_model=OrderResponse)
def get_order(order_id: int, db: Session = Depends(get_db)):
    order = (
        db.query(Order)
        .options(joinedload(Order.sp))
        .filter(Order.id == order_id)
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.patch("/{order_id}", response_model=OrderResponse)
def update_order(
    order_id: int,
    payload: OrderUpdate,
    override: bool = Query(default=False, description="Allow editing finalized orders + sync Trello checklist."),
    db: Session = Depends(get_db),
):
    order = db.query(Order).options(joinedload(Order.sp)).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # asset_type is immutable
    if payload.asset_type is not None and payload.asset_type != order.asset_type:
        raise HTTPException(status_code=400, detail="asset_type cannot be changed")

    # finalized orders are read-only unless override=true
    if (order.status or "draft") == "finalized" and not override:
        raise HTTPException(status_code=400, detail="order is finalized; use override=true to edit")

    # Apply allowed field updates (only if provided)
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
        val = getattr(payload, field, None)
        if val is not None:
            setattr(order, field, val)

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
        except TrelloConfigError as e:
            raise HTTPException(status_code=500, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Trello sync failed: {e}")

    return order
