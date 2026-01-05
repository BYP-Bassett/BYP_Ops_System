# app/models/audit_log.py

from sqlalchemy import Column, Integer, String
from app.models.base import Base


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, index=True)

    # ISO timestamp string for now (keeps SQLite/simple dev consistent with existing fields)
    ts = Column(String, index=True)

    # e.g., "delete", "create", "finalize", "unfinalize", "update"
    action = Column(String, index=True)

    # For now: initials. Later: user id / username from auth.
    actor = Column(String, index=True)

    # Optional target
    order_id = Column(Integer, index=True, nullable=True)

    # JSON snapshot or details (stored as text for SQLite)
    details_json = Column(String, nullable=True)
