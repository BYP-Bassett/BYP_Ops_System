from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Default local dev DB (SQLite).
#
# IMPORTANT:
# Use an absolute path based on the backend root so the DB location does NOT depend on
# whatever directory uvicorn happens to be started from (which can accidentally create
# app\byp_ops.db and make orders "disappear").
BACKEND_DIR = Path(__file__).resolve().parents[2]  # .../backend
DEFAULT_DB_PATH = (BACKEND_DIR / "byp_ops.db").resolve()
DEFAULT_SQLITE_URL = f"sqlite:///{DEFAULT_DB_PATH.as_posix()}"

DATABASE_URL = (os.getenv("DATABASE_URL") or DEFAULT_SQLITE_URL).strip()

# If someone set DATABASE_URL to the old relative default, normalize it to the absolute backend DB.
if DATABASE_URL in ("sqlite:///./byp_ops.db", "sqlite:////./byp_ops.db"):
    DATABASE_URL = DEFAULT_SQLITE_URL

engine_kwargs: dict = {}
if DATABASE_URL.startswith("sqlite"):
    # SQLite-only setting (Postgres will reject it)
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()
