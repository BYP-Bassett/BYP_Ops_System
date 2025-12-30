# =========================
# FILE: C:\BYP_Ops_System\backend\main_v2.py
# =========================

from fastapi import FastAPI
from app.routes.orders_v2 import router as orders_router
from app.database.migrate import run_migrations

app = FastAPI()

app.include_router(orders_router)

@app.on_event("startup")
def _startup():
    # Lightweight SQLite migrations (add missing columns safely)
    run_migrations()


@app.get("/")
def read_root():
    return {"status": "BYP Ops backend online"}
