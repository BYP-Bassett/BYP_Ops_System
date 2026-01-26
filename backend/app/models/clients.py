# app/models/clients.py

from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, Boolean, text, event

from app.models.base import Base


class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)

    # Canonical identity
    client_name = Column(String, nullable=False, index=True)
    company_name = Column(String, nullable=True, index=True)

    is_active = Column(Boolean, nullable=False, server_default=text("1"))

    created_at = Column(String)
    updated_at = Column(String, nullable=True)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@event.listens_for(Client, "before_insert")
def _client_before_insert(mapper, connection, target):
    if not getattr(target, "created_at", None):
        target.created_at = _utc_now_iso()
    if not getattr(target, "updated_at", None):
        target.updated_at = target.created_at


@event.listens_for(Client, "before_update")
def _client_before_update(mapper, connection, target):
    target.updated_at = _utc_now_iso()
