# app/schemas/order.py

from __future__ import annotations

from pydantic import BaseModel, field_validator, ConfigDict
from typing import Optional

ALLOWED_ASSET_TYPES = {"radio", "video", "art"}
ALLOWED_STATUSES = {"draft", "finalized"}


class OrderCreate(BaseModel):
    artist: str
    asset_type: str
    notes: Optional[str] = None

    # soft delete
    is_deleted: Optional[bool] = None
    deleted_at: Optional[str] = None
    deleted_by: Optional[str] = None

    # client fields
    client_name: Optional[str] = None
    client_company_name: Optional[str] = None

    # workflow fields
    order_type: Optional[str] = None
    description: Optional[str] = None
    length: Optional[str] = None
    instructions: Optional[str] = None

    # revision fields
    is_revision: Optional[bool] = False
    parent_order_id: Optional[int] = None
    revision_of: Optional[str] = None

    @field_validator("asset_type", mode="before")
    @classmethod
    def normalize_and_validate_asset_type(cls, v):
        if v is None:
            raise ValueError("asset_type is required")
        s = str(v).strip().lower()
        if not s:
            raise ValueError("asset_type cannot be blank")
        if s not in ALLOWED_ASSET_TYPES:
            raise ValueError(
                f"asset_type must be one of: {', '.join(sorted(ALLOWED_ASSET_TYPES))}"
            )
        return s


class OrderUpdate(BaseModel):
    # all optional for PATCH
    artist: Optional[str] = None
    asset_type: Optional[str] = None
    notes: Optional[str] = None

    # soft delete
    is_deleted: Optional[bool] = None
    deleted_at: Optional[str] = None
    deleted_by: Optional[str] = None

    # client fields
    client_name: Optional[str] = None
    client_company_name: Optional[str] = None

    # workflow fields
    order_type: Optional[str] = None
    description: Optional[str] = None
    length: Optional[str] = None
    instructions: Optional[str] = None

    # revision fields
    is_revision: Optional[bool] = None
    parent_order_id: Optional[int] = None
    revision_of: Optional[str] = None

    # workflow status (tight controls in route)
    status: Optional[str] = None
    trello_card_id: Optional[str] = None
    trello_checklist_id: Optional[str] = None

    @field_validator("asset_type", mode="before")
    @classmethod
    def normalize_and_validate_asset_type_if_present(cls, v):
        if v is None:
            return None
        s = str(v).strip().lower()
        if not s:
            raise ValueError("asset_type cannot be blank")
        if s not in ALLOWED_ASSET_TYPES:
            raise ValueError(
                f"asset_type must be one of: {', '.join(sorted(ALLOWED_ASSET_TYPES))}"
            )
        return s

    @field_validator("status", mode="before")
    @classmethod
    def normalize_and_validate_status_if_present(cls, v):
        if v is None:
            return None
        s = str(v).strip().lower()
        if not s:
            raise ValueError("status cannot be blank")
        if s not in ALLOWED_STATUSES:
            raise ValueError(f"status must be one of: {', '.join(sorted(ALLOWED_STATUSES))}")
        return s


class SPLink(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sp_number: str
    order_type: str
    revision_of: Optional[str] = None
    additional_version_of: Optional[str] = None


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    artist: str
    asset_type: str
    notes: Optional[str] = None

    # soft delete
    is_deleted: Optional[bool] = None
    deleted_at: Optional[str] = None
    deleted_by: Optional[str] = None

    client_name: Optional[str] = None
    client_company_name: Optional[str] = None

    sp_id: Optional[int] = None
    sp: Optional[SPLink] = None

    # workflow
    status: Optional[str] = None
    finalized_at: Optional[str] = None

    # Trello tracking
    trello_card_id: Optional[str] = None
    trello_checklist_id: Optional[str] = None
