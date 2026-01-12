# app/core/config.py
# Minimal config loader for local dev.
# Loads backend/.env into os.environ so you don't have to hand-set env vars each run.

from __future__ import annotations

import os
from pathlib import Path

_ENV_LOADED = False


def ensure_env_loaded() -> None:
    """Load C:\BYP_Ops_System\backend\.env (or relative backend/.env) once.

    - Does nothing if already loaded.
    - Does not overwrite existing os.environ values.
    - Supports lines like KEY=VALUE and 'export KEY=VALUE'.
    - Ignores blank lines and comments starting with '#'.
    """
    global _ENV_LOADED
    if _ENV_LOADED:
        return

    try:
        backend_root = Path(__file__).resolve().parents[2]  # .../backend
    except Exception:
        backend_root = Path.cwd()

    env_path = backend_root / ".env"
    if not env_path.exists():
        _ENV_LOADED = True
        return

    try:
        for raw_line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.lower().startswith("export "):
                line = line[7:].strip()
            if "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            if not key:
                continue
            val = val.strip()

            # Strip optional surrounding quotes
            if (len(val) >= 2) and ((val[0] == val[-1]) and val[0] in ("'", '"')):
                val = val[1:-1]

            # Do not clobber real environment variables
            if os.environ.get(key) is None:
                os.environ[key] = val
    finally:
        _ENV_LOADED = True


def getenv(name: str, default: str | None = None, *, required: bool = False) -> str | None:
    """Get env var after loading .env."""
    ensure_env_loaded()
    val = os.environ.get(name)
    if val is None or val.strip() == "":
        if required:
            raise RuntimeError(f"Missing required env var: {name}")
        return default
    return val.strip()
