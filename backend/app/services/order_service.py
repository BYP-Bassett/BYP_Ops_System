# app/services/order_service.py

from __future__ import annotations

from datetime import datetime
from sqlalchemy.orm import Session

from app.models.orders import Order
from app.services.sp_service import generate_next_sp


def get_order_by_id(db: Session, order_id: int):
    return db.query(Order).filter(Order.id == order_id).first()


def create_order(db: Session, data):
    # If Radio/Video → generate SP
    sp_record = None
    if data.asset_type in ["radio", "video"]:
        sp_record = generate_next_sp(db, data.asset_type)

    new_order = Order(
        artist=data.artist,
        asset_type=data.asset_type,
        notes=data.notes,

        client_name=getattr(data, "client_name", None),
        client_company_name=getattr(data, "client_company_name", None),

        sp_id=sp_record.id if sp_record else None,

        order_type=getattr(data, "order_type", None),
        description=getattr(data, "description", None),
        length=getattr(data, "length", None),
        instructions=getattr(data, "instructions", None),

        is_revision=getattr(data, "is_revision", False),
        parent_order_id=getattr(data, "parent_order_id", None),
        revision_of=getattr(data, "revision_of", None),

        status="draft",
        finalized_at=None,
        trello_card_id=None,
        trello_checklist_id=None,

        created_at=datetime.now().isoformat()
    )

    db.add(new_order)
    db.commit()
    db.refresh(new_order)

    return new_order


def finalize_order(db: Session, order: Order, trello_card_id: str, trello_checklist_id: str):
    order.status = "finalized"
    order.finalized_at = datetime.now().isoformat()
    order.trello_card_id = trello_card_id
    order.trello_checklist_id = trello_checklist_id
    db.commit()
    db.refresh(order)
    return order
