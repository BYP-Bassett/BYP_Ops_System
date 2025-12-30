# app/main.py

from fastapi import FastAPI
from app.routes.orders import router as orders_router

app = FastAPI()

app.include_router(orders_router)

@app.get("/")
def read_root():
    return {"status": "BYP Ops backend online"}
