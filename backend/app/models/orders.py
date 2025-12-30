# app/models/orders.py

from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship

from app.models.base import Base
from app.models.sp_master import SPNumber


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)

    # Basic fields
    artist = Column(String, index=True)
    asset_type = Column(String)      # 'radio', 'video', or 'art'
    notes = Column(String, nullable=True)

    # Client fields (optional)
    client_name = Column(String, nullable=True)
    client_company_name = Column(String, nullable=True)

    # SP link (radio & video only)
    sp_id = Column(Integer, ForeignKey("sp_master.id"), nullable=True)

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
    status = Column(String, default="draft")           # 'draft' | 'finalized'
    finalized_at = Column(String, nullable=True)

    # Trello tracking (only meaningful once finalized)
    trello_card_id = Column(String, nullable=True)
    trello_checklist_id = Column(String, nullable=True)

    created_at = Column(String)

    # Relationship to SP
    sp = relationship(SPNumber, backref="orders")
