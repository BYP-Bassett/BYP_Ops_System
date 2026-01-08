from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.routes.orders import router as orders_router


app = FastAPI()

# API routes
app.include_router(orders_router)

# --- Web UI (Option 1: vanilla HTML/JS served by FastAPI) ---
APP_DIR = Path(__file__).resolve().parent
WEB_DIR = APP_DIR / "web"

# Serve static assets (JS/CSS) from /web/*
# Example: /web/app.js
app.mount("/web", StaticFiles(directory=WEB_DIR), name="web")


@app.get("/", include_in_schema=False)
def web_root():
    # Browser UI
    return FileResponse(WEB_DIR / "index.html")


@app.get("/health")
def health():
    # Simple JSON health endpoint (keeps the old "/" intent available)
    return {"status": "BYP Ops backend online"}
