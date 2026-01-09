from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Default local dev DB (SQLite). For Postgres later, set:
#   $env:DATABASE_URL="postgresql+psycopg2://user:pass@host:5432/dbname"
DEFAULT_SQLITE_URL = "sqlite:///./byp_ops.db"

DATABASE_URL = (os.getenv("DATABASE_URL") or DEFAULT_SQLITE_URL).strip()

engine_kwargs: dict = {}
if DATABASE_URL.startswith("sqlite"):
    # SQLite-only setting (Postgres will reject it)
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()
