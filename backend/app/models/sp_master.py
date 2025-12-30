from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from app.models.base import Base


class SPNumber(Base):
    __tablename__ = "sp_master"

    id = Column(Integer, primary_key=True, index=True)
    sp_number = Column(String, unique=True, index=True, nullable=False)
    order_type = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    notes = Column(String, nullable=True)

    # ADD THIS
    revision_of = Column(String, nullable=True)
