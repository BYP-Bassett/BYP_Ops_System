# app/services/order_service.py

from __future__ import annotations

import os
from datetime import datetime


from app.core.config import ensure_env_loaded
from sqlalchemy.orm import Session

from app.models.orders import Order
from app.services.sp_service import generate_next_sp
from app.services.trello_service import (
    create_card_in_list,
    create_checklist_on_card,
    ensure_sp_checklist,
    find_list_id_by_name,
    rebuild_order_checklist,
)



# Load backend/.env so Trello vars work without manual env setup
ensure_env_loaded()

def get_order_by_id(db: Session, order_id: int):
    return db.query(Order).filter(Order.id == order_id).first()


def create_order(db: Session, data):
    # If Radio/Video → generate SP (ART does NOT use SP numbers)
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
    Trello card description.

    Requirement:
      - Description should be the client name only (not a full order dump).
      - If client_name is blank, fall back to company_name.
    """
    client = (getattr(order, "client_name", None) or "").strip()
    company = (getattr(order, "client_company_name", None) or "").strip()

    if client:
        return client
    if company:
        return company
    return ""

def _notes_to_items_local(notes: str | None) -> list[str]:
    items: list[str] = []
    if not notes:
        return items
    for raw in (notes or '').splitlines():
        line = raw.strip()
        if not line:
            continue
        # strip leading bullets
        line = line.lstrip('-*•	 ').strip()
        if line:
            items.append(line)
    return items


def _art_checklist_name(*, db: Session, order: Order, now: datetime) -> str:
    """Return the ART checklist display code.

    Rules:
      - Originals / additional versions: MMDDYY (no -R#)
      - Revisions: MMDDYY-R# where # is 1-based revision count for the same root.
    """
    mmddyy = now.strftime("%m%d%y")

    is_rev = bool(getattr(order, "is_revision", False)) or bool(getattr(order, "revision_of", None))
    if not is_rev:
        return mmddyy

    # Prefer explicit revision_of root; fall back to parent_order_id/id.
    root_id = getattr(order, "revision_of", None) or getattr(order, "parent_order_id", None) or getattr(order, "id", None)

    r_num = 1
    try:
        if root_id:
            q = (
                db.query(Order)
                .filter(
                    Order.asset_type == "art",
                    Order.status == "finalized",
                    Order.trello_checklist_id.isnot(None),
                )
            )

            # Count only revisions for this root (exclude the original/addl versions).
            if hasattr(Order, "revision_of"):
                q = q.filter(Order.revision_of == root_id)
            else:
                # Defensive fallback for older schema.
                q = q.filter((Order.parent_order_id == root_id) & (Order.is_revision == True))

            existing = int(q.count() or 0)
            r_num = max(1, existing + 1)
    except Exception:
        r_num = 1

    return f"{mmddyy}-R{r_num}"



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

    ART target behavior:
      - If Trello linkage missing, create Trello card in rep's board "To Do" list.
      - Create checklist named MMDDYY-R# and populate items derived from notes.
      - Store Trello IDs on the order, then finalize.

    Non radio/video/art: requires linkage to already exist.
    """
    card_id = (trello_card_id or "").strip() or (getattr(order, "trello_card_id", None) or "").strip()
    checklist_id = (trello_checklist_id or "").strip() or (getattr(order, "trello_checklist_id", None) or "").strip()

    asset = (getattr(order, "asset_type", "") or "").strip().lower()

    # Additional versions must always create a NEW Trello card + checklist.
    # Never reuse parent linkage even if the order inherited Trello IDs.
    is_addl = bool(getattr(order, "is_additional_version", False)) or bool(getattr(order, "additional_version_of", None))
    if is_addl:
        card_id = ""
        checklist_id = ""

    if asset in ("radio", "video"):

        # Auto-assign SP if missing (defensive; also handled on asset_type flip).
        # Without this, Art->Radio/Video flips can fail at finalize time.
        if getattr(order, "sp_id", None) is None:
            sp_rec = generate_next_sp(db, asset)
            order.sp_id = sp_rec.id
            try:
                order.sp = sp_rec  # type: ignore[attr-defined]
            except Exception:
                pass
            db.commit()
            db.refresh(order)

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

        # IMPORTANT: if we're finalizing a draft that already has a Trello checklist linked
        # (common after Override Edit), we must rebuild the checklist so Trello matches the
        # updated notes. For radio/video, checklist name must be the SP#.
        if checklist_id:
            if not sp_number:
                raise RuntimeError("Cannot rebuild Trello checklist: SP number missing for this order.")
            checklist_id = rebuild_order_checklist(
                card_id=card_id,
                old_checklist_id=checklist_id,
                checklist_name=sp_number,
                notes=getattr(order, "notes", None),
            )
        else:
            if not sp_number:
                raise RuntimeError("Cannot create Trello checklist: SP number missing for this order.")
            checklist_id = ensure_sp_checklist(
                card_id=card_id,
                sp_number=sp_number,
                notes=getattr(order, "notes", None),
            )

    elif asset == "art":
        # ART uses date-based checklist codes like MMDDYY-R# (no SP numbers).
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

            desc = _build_card_desc(order, None)
            created = create_card_in_list(list_id=list_id, name=title, desc=desc or None)
            card_id = created["id"]

        # For ART, checklist name is MMDDYY-R# based on finalized siblings of the same root.
        # If we already have a checklist linked (e.g., after Override Edit), rebuild it so the
        # items reflect the updated notes.
        now = datetime.now()
        checklist_name = _art_checklist_name(db=db, order=order, now=now)
        # Store the human-friendly ART code in sp_number for UI parity.
        order.sp_number = checklist_name
        items = _notes_to_items_local(getattr(order, "notes", None))

        if checklist_id:
            checklist_id = rebuild_order_checklist(
                card_id=card_id,
                old_checklist_id=checklist_id,
                checklist_name=checklist_name,
                notes=getattr(order, "notes", None),
            )
        else:
            checklist_id = create_checklist_on_card(card_id=card_id, name=checklist_name, items=items)

    else:
        if not card_id or not checklist_id:
            raise RuntimeError(
                "Finalize requires Trello linkage for this asset type (radio/video/art auto-create only)."
            )
    order.status = "finalized"
    order.finalized_at = datetime.now().isoformat()
    order.trello_card_id = card_id
    order.trello_checklist_id = checklist_id

    db.commit()
    db.refresh(order)
    return order
