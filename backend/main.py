# main.py
# BYP Ops / SPOrder backend entrypoint
#
# NOTE:
# - Runs with: uvicorn main:app --reload
# - On startup: creates tables (dev) + applies lightweight SQLite ALTER TABLE migrations

from fastapi import FastAPI

from app.routes.orders import router as orders_router
from app.database.engine import engine
from app.models.base import Base
from app.database.migrate import migrate_sqlite_schema

app = FastAPI(title="BYP Ops Backend")

app.include_router(orders_router)


@app.on_event("startup")
def _startup():
    # Create tables if missing
    Base.metadata.create_all(bind=engine)

    # Apply lightweight SQLite migrations (adds new columns if needed)
    migrate_sqlite_schema()


@app.get("/")
def read_root():
    return {"status": "BYP Ops backend online"}
