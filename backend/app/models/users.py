from __future__ import annotations

from sqlalchemy import Column, Integer, String, Boolean, event
from app.models.base import Base


def _utc_now_iso() -> str:
    # Match the project's existing "UTC ISO-ish" string convention: 2026-01-09T21:33:12+00:00
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)

    # Login/identity
    username = Column(String, unique=True, index=True, nullable=False)   # e.g. "sb"
    rep_code = Column(String, unique=True, index=True, nullable=False)   # e.g. "SB"
    rep_name = Column(String, nullable=False)                            # e.g. "SB - Steve Bassett"
    email = Column(String, nullable=True)

    # Auth (Phase 2+). Store password hashes only.
    password_hash = Column(String, nullable=True)

    # Permissions / status
    is_active = Column(Boolean, nullable=False, default=True)
    role = Column(String, nullable=False, default="user")  # "user" | "admin"

    # Timestamps (string, consistent with Orders/Audit)
    created_at = Column(String, nullable=True)
    updated_at = Column(String, nullable=True)


@event.listens_for(User, "before_insert")
def _user_before_insert(mapper, connection, target: User) -> None:
    now = _utc_now_iso()
    if not target.created_at:
        target.created_at = now
    if not target.updated_at:
        target.updated_at = target.created_at or now

    # Normalize: username lower, rep_code upper, rep_name trimmed
    if target.username:
        target.username = target.username.strip().lower()
    if target.rep_code:
        target.rep_code = target.rep_code.strip().upper()
    if target.rep_name:
        target.rep_name = target.rep_name.strip()


@event.listens_for(User, "before_update")
def _user_before_update(mapper, connection, target: User) -> None:
    target.updated_at = _utc_now_iso()

    if target.username:
        target.username = target.username.strip().lower()
    if target.rep_code:
        target.rep_code = target.rep_code.strip().upper()
    if target.rep_name:
        target.rep_name = target.rep_name.strip()
