from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String

from app.models.base import Base


class SPNumber(Base):
    __tablename__ = "sp_master"

    id = Column(Integer, primary_key=True, index=True)
    sp_number = Column(String, unique=True, index=True, nullable=False)
    order_type = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    notes = Column(String, nullable=True)

    # Linkage fields (only one should be set for a given SP)
    revision_of = Column(String, nullable=True)              # parent SP if this is a true revision
    additional_version_of = Column(String, nullable=True)    # parent SP if this is an additional version
