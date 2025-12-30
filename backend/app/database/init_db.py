from app.database.engine import engine
from app.models.base import Base

# IMPORTANT: import models so tables are registered
from app.models import orders
from app.models import sp_master


def init_db():
    Base.metadata.create_all(bind=engine)
