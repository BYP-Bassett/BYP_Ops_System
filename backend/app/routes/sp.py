from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.sp_master import SPNumber
from app.schemas.sp import SPResponse

router = APIRouter(prefix="/sp", tags=["SP"])


@router.get("/", response_model=list[SPResponse])
def list_sp(db: Session = Depends(get_db)):
    return db.query(SPNumber).order_by(SPNumber.id.desc()).all()


@router.get("/{sp_id}", response_model=SPResponse)
def get_sp(sp_id: int, db: Session = Depends(get_db)):
    sp = db.query(SPNumber).filter(SPNumber.id == sp_id).first()
    if not sp:
        raise HTTPException(status_code=404, detail="SP not found")
    return sp
