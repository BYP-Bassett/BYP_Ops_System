# app/services/order_service.py

from __future__ import annotations

import os
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.orders import Order
from app.services.sp_service import generate_next_sp
from app.services.trello_service import (
    create_card_in_list,
    ensure_sp_checklist,
    find_list_id_by_name,
)


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
        notes=getattr(data, "notes", None),

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

        created_at=datetime.now().isoformat(),
    )

    db.add(new_order)
    db.commit()
    db.refresh(new_order)

    return new_order


def _env_board_id_for_rep(rep_code: str | None) -> str:
    """
    Board mapping by rep_code:
      - tries env var TRELLO_BOARD_ID_<REP> (e.g., TRELLO_BOARD_ID_SB)
      - falls back to TRELLO_DEFAULT_BOARD_ID
    """
    rep = (rep_code or "").strip().upper()
    if rep:
        val = os.environ.get(f"TRELLO_BOARD_ID_{rep}", "").strip()
        if val:
            return val
    return os.environ.get("TRELLO_DEFAULT_BOARD_ID", "").strip()


def _build_card_desc(order: Order, sp_number: str | None) -> str:
    """
    Minimal, human-friendly description. You can evolve this later.
    """
    lines: list[str] = []
    lines.append(f"Order ID: {order.id}")
    lines.append(f"Asset: {order.asset_type}")
    if sp_number:
        lines.append(f"SP: {sp_number}")
    if getattr(order, "client_name", None):
        lines.append(f"Client: {order.client_name}")
    if getattr(order, "client_company_name", None):
        lines.append(f"Company: {order.client_company_name}")
    if getattr(order, "notes", None):
        lines.append("")
        lines.append("Notes:")
        lines.append(order.notes)
    return "\n".join(lines).strip()


def finalize_order(
    db: Session,
    order: Order,
    trello_card_id: str | None,
    trello_checklist_id: str | None,
):
    """
    Finalize an order.

    Radio/Video target behavior:
      - If Trello linkage missing, create Trello card in rep's board "To Do" list.
      - Card title = full Artist field.
      - Create checklist named exactly SP# and populate items derived from notes.
      - Store Trello IDs on the order, then finalize.

    Non radio/video: requires linkage to already exist (Art later).
    """
    card_id = (trello_card_id or "").strip() or (getattr(order, "trello_card_id", None) or "").strip()
    checklist_id = (trello_checklist_id or "").strip() or (getattr(order, "trello_checklist_id", None) or "").strip()

    asset = (getattr(order, "asset_type", "") or "").strip().lower()

    if asset in ("radio", "video"):
        # Get SP number (relationship should lazy-load if needed)
        sp_number = None
        try:
            if getattr(order, "sp", None) is not None:
                sp_number = getattr(order.sp, "sp_number", None)
        except Exception:
            sp_number = None

        if not card_id:
            board_id = _env_board_id_for_rep(getattr(order, "rep_code", None))
            if not board_id:
                raise RuntimeError(
                    "Missing Trello board mapping. Set TRELLO_BOARD_ID_<REP> or TRELLO_DEFAULT_BOARD_ID."
                )

            list_name = os.environ.get("TRELLO_TODO_LIST_NAME", "To Do").strip() or "To Do"
            list_id = find_list_id_by_name(board_id=board_id, list_name=list_name)

            title = (getattr(order, "artist", "") or "").strip()
            if not title:
                raise RuntimeError("Cannot create Trello card: order.artist is blank.")

            desc = _build_card_desc(order, sp_number)
            created = create_card_in_list(list_id=list_id, name=title, desc=desc or None)
            card_id = created["id"]

        if not checklist_id:
            if not sp_number:
                raise RuntimeError("Cannot create Trello checklist: SP number missing for this order.")
            checklist_id = ensure_sp_checklist(
                card_id=card_id,
                sp_number=sp_number,
                notes=getattr(order, "notes", None),
            )

    else:
        if not card_id or not checklist_id:
            raise RuntimeError("Finalize requires Trello linkage for this asset type (radio/video auto-create only).")

    order.status = "finalized"
    order.finalized_at = datetime.now().isoformat()
    order.trello_card_id = card_id
    order.trello_checklist_id = checklist_id

    db.commit()
    db.refresh(order)
    return order
