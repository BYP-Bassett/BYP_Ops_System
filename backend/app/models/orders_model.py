# app/models/orders.py

from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, text, event
from sqlalchemy.orm import relationship

from app.models.base import Base
from app.models.sp_master import SPNumber


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)

    # Basic fields
    artist = Column(String, index=True)
    asset_type = Column(String)  # 'radio', 'video', 'art', or 'other'
    notes = Column(String, nullable=True)
    voice_talent = Column(String, nullable=True)  # Voice talent name (radio/video/other only)


    # Rep tracking
    rep_name = Column(String(100), nullable=False, server_default=text("'SB - Steve Bassett'"))
    rep_code = Column(String(10), nullable=False, server_default=text("'SB'"))

    # Client fields
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True)

    client_name = Column(String, nullable=True)
    client_company_name = Column(String, nullable=True)

    # SP link (radio & video only)
    sp_id = Column(Integer, ForeignKey("sp_master.id"), nullable=True)

    # ART code tracking (MMDDYY / MMDDYY-R#)
    art_number = Column(String, nullable=True)

    # Workflow fields
    order_type = Column(String, nullable=True)
    description = Column(String, nullable=True)
    length = Column(String, nullable=True)
    instructions = Column(String, nullable=True)

    # Revision tracking
    is_revision = Column(Boolean, default=False)
    parent_order_id = Column(Integer, nullable=True)
    revision_of = Column(String, nullable=True)

    # Draft vs finalized workflow
    status = Column(String, default="draft")  # 'draft' | 'finalized'
    finalized_at = Column(String, nullable=True)

    # Trello tracking
    trello_card_id = Column(String, nullable=True)
    trello_checklist_id = Column(String, nullable=True)

    # Soft delete + audit
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(String, nullable=True)
    deleted_by = Column(String, nullable=True)  # legacy (initials/username)

    # NEW: user-id based audit fields (preferred)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    updated_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    deleted_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    created_at = Column(String)

    updated_at = Column(String, nullable=True)
    # Relationship to SP
    sp = relationship(SPNumber, backref="orders")

    # Relationship to Client (optional; Orders also store snapshot client_name/company_name)
    client = relationship("Client", backref="orders")

    # Optional convenience relationships
    created_by_user = relationship("User", foreign_keys=[created_by_user_id])
    updated_by_user = relationship("User", foreign_keys=[updated_by_user_id])
    deleted_by_user = relationship("User", foreign_keys=[deleted_by_user_id])



def _utc_now_iso() -> str:
    # Example: 2026-01-09T21:33:12+00:00
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


# --- Rep sync guardrails (model-level) ---
# Prevents storing mismatched rep_name/rep_code even if a route forgets to normalize.

REP_NAME_BY_CODE = {
    "SB": "SB - Steve Bassett",
    "RM": "RM - Ron Mewis",
    "AML": "AML - Allison Lineberry",
    "JS": "JS - Jon Shults",
    "CD": "CD - Celine DeLeon",
}

def _rep_code_from_name(rep_name: str | None) -> str | None:
    if not rep_name:
        return None
    s = rep_name.strip()
    if not s:
        return None
    prefix = s.split("-", 1)[0].strip().upper()
    if 1 <= len(prefix) <= 4 and prefix.isalpha():
        return prefix
    return None

def _normalize_rep(target: "Order") -> None:
    # Note: On insert, DB server_default may populate values; if both are missing here, we leave it alone.
    code = (getattr(target, "rep_code", None) or "").strip().upper() or None
    name = (getattr(target, "rep_name", None) or "").strip() or None

    code_from_name = _rep_code_from_name(name)

    # If rep_name includes initials, that wins. Fix rep_code to match.
    if code_from_name:
        code = code_from_name
        # If we know the canonical display string, use it; else keep provided name as-is.
        name = REP_NAME_BY_CODE.get(code_from_name, name)

    # If we have a code but no name, fill name from mapping (or just the code).
    if code and not name:
        name = REP_NAME_BY_CODE.get(code, code)

    # Write back only if we have something (avoid stomping DB defaults with None)
    if code is not None:
        target.rep_code = code
    if name is not None:
        target.rep_name = name

@event.listens_for(Order, "before_insert")
def _order_before_insert(mapper, connection, target):
    # Ensure timestamps are always populated for new rows.
    if not getattr(target, 'created_at', None):
        target.created_at = _utc_now_iso()
    if not getattr(target, 'updated_at', None):
        target.updated_at = target.created_at
    _normalize_rep(target)

@event.listens_for(Order, "before_update")
def _order_before_update(mapper, connection, target):
    # Touch updated_at on any update.
    target.updated_at = _utc_now_iso()
    _normalize_rep(target)
