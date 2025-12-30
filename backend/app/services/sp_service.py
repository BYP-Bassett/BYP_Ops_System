from sqlalchemy.orm import Session
from datetime import datetime

from app.models.sp_master import SPNumber


def generate_next_sp(db: Session, order_type: str):
    last_sp = (
        db.query(SPNumber)
        .order_by(SPNumber.id.desc())
        .first()
    )

    if last_sp:
        next_number = int(last_sp.sp_number.replace("SP", "")) + 1
    else:
        next_number = 1

    sp_number = f"SP{next_number:06d}"

    new_sp = SPNumber(
        sp_number=sp_number,
        order_type=order_type,
        created_at=datetime.utcnow(),  # FIXED
        notes=None,
        revision_of=None,
    )

    db.add(new_sp)
    db.commit()
    db.refresh(new_sp)

    return new_sp
