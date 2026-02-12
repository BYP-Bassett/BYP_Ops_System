# app/routes/voice_talents.py

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.database.session import get_db
from app.models.voice_talent import VoiceTalent
from app.models.orders import Order


router = APIRouter(prefix="/api/voice-talents", tags=["Voice Talents"])


# Auth helpers (copied from orders.py pattern)
def _session_user(request: Request) -> dict | None:
    try:
        s = getattr(request, "session", None) or {}
        username = (s.get("username") or "").strip()
        if not username:
            return None
        return {
            "user_id": s.get("user_id"),
            "username": username,
            "role": (s.get("role") or "").strip().lower(),
        }
    except Exception:
        return None


def require_login(request: Request) -> dict:
    u = _session_user(request)
    if not u:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return u


def require_admin(request: Request) -> dict:
    u = require_login(request)
    if u.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin required")
    return u


# Schemas
class VoiceTalentResponse(BaseModel):
    id: int
    name: str
    is_label: bool
    section: str
    sort_order: int

    class Config:
        from_attributes = True


class VoiceTalentCreate(BaseModel):
    name: str
    section: str  # 'IN_HOUSE' or 'OUTSIDE'


# Endpoints

@router.get("", response_model=list[VoiceTalentResponse])
def list_voice_talents(
    request: Request,
    db: Session = Depends(get_db),
    session_user: dict = Depends(require_login),
):
    """
    Get all voice talents ordered by section and sort_order.
    Includes both section labels (is_label=True) and selectable voices.
    """
    voices = (
        db.query(VoiceTalent)
        .order_by(VoiceTalent.section.asc(), VoiceTalent.sort_order.asc())
        .all()
    )
    return voices


@router.post("", response_model=VoiceTalentResponse)
def create_voice_talent(
    request: Request,
    payload: VoiceTalentCreate,
    db: Session = Depends(get_db),
    session_user: dict = Depends(require_login),
):
    """
    Add a new voice talent.
    Any logged-in user can add voices.
    """
    # Normalize name
    name = payload.name.strip()
    name = " ".join(name.split())  # Collapse multiple spaces
    # Normalize dash spacing
    name = name.replace(" - ", " - ")  # Ensure single space around dashes
    
    if not name:
        raise HTTPException(status_code=400, detail="Name cannot be blank")
    
    # Validate section
    section = payload.section.strip().upper()
    if section not in ("IN_HOUSE", "OUTSIDE"):
        raise HTTPException(status_code=400, detail="Section must be 'IN_HOUSE' or 'OUTSIDE'")
    
    # Check for duplicates (case-insensitive)
    existing = (
        db.query(VoiceTalent)
        .filter(VoiceTalent.is_label == False)
        .all()
    )
    for v in existing:
        if v.name.strip().lower() == name.lower():
            raise HTTPException(status_code=400, detail=f"Voice talent '{name}' already exists")
    
    # Determine sort_order: insert alphabetically among user-added voices in the same section
    # Get all non-label voices in this section
    section_voices = (
        db.query(VoiceTalent)
        .filter(VoiceTalent.section == section, VoiceTalent.is_label == False)
        .order_by(VoiceTalent.sort_order.asc())
        .all()
    )
    
    # Find the correct insertion point alphabetically
    insert_position = None
    for i, voice in enumerate(section_voices):
        if name.lower() < voice.name.lower():
            insert_position = voice.sort_order
            break
    
    # If no position found, append to end
    if insert_position is None:
        if section_voices:
            new_sort_order = section_voices[-1].sort_order + 1
        else:
            # First voice in this section (shouldn't happen with seeded data, but handle it)
            new_sort_order = 1001 if section == "IN_HOUSE" else 2001
    else:
        # Insert at this position - shift everything after it
        new_sort_order = insert_position
        # Increment sort_order for all items at or after this position in this section
        db.query(VoiceTalent).filter(
            VoiceTalent.section == section,
            VoiceTalent.sort_order >= insert_position
        ).update({VoiceTalent.sort_order: VoiceTalent.sort_order + 1})
        db.flush()
    
    # Create new voice
    new_voice = VoiceTalent(
        name=name,
        is_label=False,
        section=section,
        sort_order=new_sort_order,
        created_by_user_id=session_user.get("user_id"),
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    
    db.add(new_voice)
    db.commit()
    db.refresh(new_voice)
    
    return new_voice


@router.delete("/{voice_id}")
def delete_voice_talent(
    request: Request,
    voice_id: int,
    db: Session = Depends(get_db),
    session_user: dict = Depends(require_admin),
):
    """
    Delete a voice talent (admin only).
    Cannot delete section labels (is_label=True).
    Also clears voice_talent from any orders using this voice.
    """
    voice = db.query(VoiceTalent).filter(VoiceTalent.id == voice_id).first()
    if not voice:
        raise HTTPException(status_code=404, detail="Voice talent not found")
    
    if voice.is_label:
        raise HTTPException(status_code=400, detail="Cannot delete section labels")
    
    # Clear voice_talent from orders using this voice
    db.query(Order).filter(Order.voice_talent == voice.name).update(
        {Order.voice_talent: None}
    )
    
    db.delete(voice)
    db.commit()
    
    return {"success": True, "deleted_id": voice_id}
