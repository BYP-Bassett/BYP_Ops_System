# app/models/voice_talent.py

from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from app.models.base import Base


class VoiceTalent(Base):
    __tablename__ = "voice_talents"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    is_label = Column(Boolean, nullable=False, default=False)  # True for section headers
    section = Column(String, nullable=False, index=True)  # 'IN_HOUSE' or 'OUTSIDE'
    sort_order = Column(Integer, nullable=False, index=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(String, nullable=True)
