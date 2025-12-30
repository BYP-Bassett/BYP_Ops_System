from datetime import datetime
from pydantic import BaseModel
from typing import Optional


class SPBase(BaseModel):
    sp_number: str
    order_type: str
    notes: Optional[str] = None
    revision_of: Optional[str] = None


class SPCreate(SPBase):
    pass


class SPResponse(SPBase):
    id: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
