# =========================
# FILE: C:\BYP_Ops_System\backend\app\routes\orders_v2.py
# =========================

import re

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, and_, or_
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.order import OrderCreate, OrderUpdate, OrderResponse
from app.models.orders import Order
from app.models.sp_master import SPNumber
from app.services.order_service import create_order as create_order_service

router = APIRouter(prefix="/orders", tags=["Orders"])


def _build_fm_field_filter(column, raw: str | None):
    """
    FileMaker-ish parsing PER FIELD:
      - No quotes: words are OR within that field
      - Quotes: each quoted phrase is AND (must be contained) within that field
      - If both exist: (AND phrases) AND (OR tokens)
      - Matching is case-insensitive "contains"
    """
    if not raw:
        return None

    raw = raw.strip()
    if not raw:
        return None

    phrases = [p.strip() for p in re.findall(r'"([^"]+)"', raw) if p.strip()]
    remainder = re.sub(r'"[^"]+"', " ", raw).strip()
    tokens = [t for t in re.split(r"\s+", remainder) if t]

    conds = []

    for phrase in phrases:
        conds.append(column.ilike(f"%{phrase}%"))

    if tokens:
        conds.append(or_(*[column.ilike(f"%{t}%") for t in tokens]))

    if not conds:
        return None

    return and_(*conds) if len(conds) > 1 else conds[0]


@router.post("/new", response_model=OrderResponse)
def create_order(payload: OrderCreate, db: Session = Depends(get_db)):
    return create_order_service(db, payload)


@router.get("/search", response_model=list[OrderResponse])
def search_orders(
    db: Session = Depends(get_db),

    # Deprecated/ignored: we’re field-based now
    q: str | None = Query(default=None),

    artist: str | None = Query(default=None),
    notes: str | None = Query(default=None),
    asset_type: str | None = Query(default=None),
    sp_number: str | None = Query(default=None),

    # NEW: searchable client fields
    client_name: str | None = Query(default=None),
    client_company_name: str | None = Query(default=None),
):
    qry = db.query(Order).outerjoin(SPNumber, Order.sp_id == SPNumber.id)

    f = _build_fm_field_filter(Order.artist, artist)
    if f is not None:
        qry = qry.filter(f)

    f = _build_fm_field_filter(Order.notes, notes)
    if f is not None:
        qry = qry.filter(f)

    f = _build_fm_field_filter(Order.asset_type, asset_type)
    if f is not None:
        qry = qry.filter(f)

    f = _build_fm_field_filter(SPNumber.sp_number, sp_number)
    if f is not None:
        qry = qry.filter(f)

    f = _build_fm_field_filter(Order.client_name, client_name)
    if f is not None:
        qry = qry.filter(f)

    f = _build_fm_field_filter(Order.client_company_name, client_company_name)
    if f is not None:
        qry = qry.filter(f)

    qry = qry.order_by(
        case((Order.sp_id == None, 1), else_=0),
        Order.sp_id.desc(),
        Order.id.desc(),
    )

    return qry.all()


@router.post("/{order_id}/revise", response_model=OrderResponse)
def revise_order(order_id: int, db: Session = Depends(get_db)):
    parent = db.query(Order).filter(Order.id == order_id).first()
    if not parent:
        raise HTTPException(status_code=404, detail="Order not found")

    payload = OrderCreate(
        artist=parent.artist,
        asset_type=parent.asset_type,
        notes=parent.notes,

        # carry client fields forward on revisions
        client_name=parent.client_name,
        client_company_name=parent.client_company_name,

        order_type=getattr(parent, "order_type", None),
        description=getattr(parent, "description", None),
        length=getattr(parent, "length", None),
        instructions=getattr(parent, "instructions", None),

        is_revision=True,
        parent_order_id=parent.id,
        revision_of=(parent.sp.sp_number if getattr(parent, "sp", None) else None),
    )

    new_order = create_order_service(db, payload)

    if getattr(parent, "sp", None) and getattr(new_order, "sp", None):
        new_order.sp.revision_of = parent.sp.sp_number
        if hasattr(new_order, "revision_of"):
            new_order.revision_of = parent.sp.sp_number

        db.commit()
        db.refresh(new_order)

    return new_order


@router.get("/{order_id}", response_model=OrderResponse)
def get_order(order_id: int, db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.patch("/{order_id}", response_model=OrderResponse)
def patch_order(order_id: int, payload: OrderUpdate, db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    updates = payload.model_dump(exclude_unset=True)

    if "asset_type" in updates and updates["asset_type"] != order.asset_type:
        raise HTTPException(status_code=400, detail="asset_type cannot be changed")

    for k, v in updates.items():
        setattr(order, k, v)

    db.commit()
    db.refresh(order)
    return order


@router.delete("/{order_id}")
def delete_order(order_id: int, db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    db.delete(order)
    db.commit()
    return {"deleted_id": order_id}


@router.get("/", response_model=list[OrderResponse])
def list_orders(db: Session = Depends(get_db)):
    return db.query(Order).all()
