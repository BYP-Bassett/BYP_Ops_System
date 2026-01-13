# app/services/trello_service.py
# Trello sync utilities:
# - Delete existing checklist
# - Recreate checklist named as SP Number (or NEW for art)
# - Recreate checklist items from order.notes

from __future__ import annotations

import json
import os
from pathlib import Path

# Prefer the app's env-loader if present, but ALSO load .env ourselves with an explicit path
# so Trello auth never depends on the process working-directory.
try:
    from app.core.config import ensure_env_loaded as _ensure_env_loaded  # type: ignore
except Exception:  # pragma: no cover
    _ensure_env_loaded = None

try:
    from dotenv import load_dotenv  # type: ignore
except Exception:  # pragma: no cover
    load_dotenv = None

from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


TRELLO_API_BASE = "https://api.trello.com/1"


class TrelloConfigError(RuntimeError):
    pass


def _backend_root() -> Path:
    # File lives at: backend/app/services/trello_service.py -> parents[2] == backend
    return Path(__file__).resolve().parents[2]


def _load_env_strict() -> None:
    """Load backend/.env with an explicit path.

    Why: depending on process CWD or import-order to load env vars is brittle.
    We prefer python-dotenv if available, but we ALSO support a tiny manual
    parser so Trello credentials always load on Windows even if python-dotenv
    isn't installed.

    Rules:
    - Never clobber non-empty env vars already set in the process.
    - If the env var is missing OR blank, allow .env to fill it.
    """
    env_path = _backend_root() / ".env"
    if not env_path.exists():
        return

    # 1) Try python-dotenv (nice-to-have)
    if load_dotenv is not None:
        try:
            load_dotenv(dotenv_path=str(env_path), override=False)
        except Exception:
            # fall back to manual parsing below
            pass

    # 2) Manual parsing (works even without python-dotenv)
    try:
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip().lstrip('\ufeff')  # handle UTF-8 BOM
            v = v.strip()

            # strip surrounding quotes if present
            if len(v) >= 2 and ((v[0] == v[-1] == '"') or (v[0] == v[-1] == "'")):
                v = v[1:-1]

            if not k:
                continue

            # Only set if missing or blank
            cur = os.environ.get(k, "")
            if cur.strip() == "":
                os.environ[k] = v
    except Exception:
        # If env parsing fails, don't crash import; caller will raise a config error.
        return


def _trello_auth_params() -> dict:
    # Try the project's loader first (if any), then hard-load the known backend/.env path.
    if _ensure_env_loaded is not None:
        try:
            _ensure_env_loaded()
        except Exception:
            # Don't let a brittle loader break Trello; we'll try strict loading next.
            pass

    _load_env_strict()

    key = os.environ.get("TRELLO_KEY", "").strip()
    token = os.environ.get("TRELLO_TOKEN", "").strip()
    if not key or not token:
        env_path = _backend_root() / ".env"
        # Keep the original message so existing callers/tests don't get surprised,
        # but add one useful breadcrumb for debugging.
        raise TrelloConfigError(
            "Missing Trello credentials. Set TRELLO_KEY and TRELLO_TOKEN env vars. "
            f"(Checked: {env_path})"
        )
    return {"key": key, "token": token}


def _http_json(method: str, url: str, payload: dict | None = None, timeout: int = 20) -> dict:
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = Request(url, data=body, headers=headers, method=method)
    with urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
        return json.loads(raw) if raw else {}


def card_exists(card_id: str) -> bool:
    """Return True if the Trello card id is accessible with current key/token."""
    cid = (card_id or "").strip()
    if not cid:
        return False
    auth = _trello_auth_params()
    url = f"{TRELLO_API_BASE}/cards/{cid}?{urlencode(auth)}"
    try:
        _http_json("GET", url, payload=None, timeout=20)
        return True
    except HTTPError as e:
        if getattr(e, "code", None) == 404:
            return False
        raise


def _delete_checklist(checklist_id: str) -> None:
    auth = _trello_auth_params()
    url = f"{TRELLO_API_BASE}/checklists/{checklist_id}?{urlencode(auth)}"
    try:
        _http_json("DELETE", url, payload=None, timeout=20)
    except HTTPError as e:
        if e.code in (404,):
            return
        raise
    except URLError:
        raise


def _create_checklist(card_id: str, name: str) -> dict:
    auth = _trello_auth_params()
    url = f"{TRELLO_API_BASE}/cards/{card_id}/checklists?{urlencode({**auth, 'name': name})}"
    return _http_json("POST", url, payload=None, timeout=25)


def _add_check_item(checklist_id: str, name: str, pos: str = "bottom") -> dict:
    auth = _trello_auth_params()
    url = f"{TRELLO_API_BASE}/checklists/{checklist_id}/checkItems?{urlencode({**auth, 'name': name, 'pos': pos})}"
    return _http_json("POST", url, payload=None, timeout=25)


def _notes_to_items(notes: str | None) -> list[str]:
    if not notes:
        return []
    lines = notes.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    out: list[str] = []
    for line in lines:
        s = (line or "").strip()
        if not s:
            continue
        s = s.lstrip("-•").strip()
        if s:
            out.append(s)
    return out


# -------- New helpers for card + checklist creation (used by finalize flows) --------

def find_list_id_by_name(*, board_id: str, list_name: str) -> str:
    """
    Return Trello list id on a board by matching list name case-insensitively.
    Raises RuntimeError if not found.
    """
    auth = _trello_auth_params()
    url = f"{TRELLO_API_BASE}/boards/{board_id}/lists?{urlencode(auth)}"
    lists = _http_json("GET", url, payload=None, timeout=25)
    # Trello returns a JSON array; _http_json returns dict normally, but json.loads will parse arrays too.
    if not isinstance(lists, list):
        raise RuntimeError("Unexpected Trello response when listing board lists.")
    wanted = (list_name or "").strip().lower()
    for lst in lists:
        try:
            if (lst.get("name") or "").strip().lower() == wanted:
                return (lst.get("id") or "").strip()
        except Exception:
            continue
    raise RuntimeError(f'Trello list "{list_name}" not found on board {board_id}.')


def create_card_in_list(*, list_id: str, name: str, desc: str | None = None) -> dict:
    """
    Create a Trello card in the given list. Returns the Trello card JSON (must include id).
    """
    auth = _trello_auth_params()
    params = {**auth, "idList": list_id, "name": name}
    if desc is not None:
        params["desc"] = desc
    url = f"{TRELLO_API_BASE}/cards?{urlencode(params)}"
    created = _http_json("POST", url, payload=None, timeout=25)
    if not isinstance(created, dict) or not (created.get("id") or "").strip():
        raise RuntimeError("Trello did not return a card id when creating a new card.")
    return created


def create_checklist_on_card(*, card_id: str, name: str, items: list[str] | None = None) -> str:
    """
    Create a checklist on a card and optionally populate it with items.
    Returns the new checklist id.
    """
    created = _create_checklist(card_id, name)
    new_id = (created.get("id") or "").strip()
    if not new_id:
        raise RuntimeError("Trello did not return a checklist id when creating a new checklist.")

    if items:
        for item in items:
            s = (item or "").strip()
            if s:
                _add_check_item(new_id, s)

    return new_id


def ensure_sp_checklist(*, card_id: str, sp_number: str, notes: str | None) -> str:
    """
    Create a checklist named exactly as the SP# (e.g., SP000014), with items derived from notes.
    Returns checklist id.
    """
    name = (sp_number or "").strip()
    if not name:
        raise RuntimeError("SP number is required to create the Trello checklist name.")
    items = _notes_to_items(notes)
    return create_checklist_on_card(card_id=card_id, name=name, items=items)


def rebuild_order_checklist(*, card_id: str, old_checklist_id: str, checklist_name: str, notes: str | None) -> str:
    """
    Deletes the existing checklist and recreates it with fresh items.
    Returns the new checklist id.
    """
    _delete_checklist(old_checklist_id)

    created = _create_checklist(card_id, checklist_name)
    new_id = (created.get("id") or "").strip()
    if not new_id:
        raise RuntimeError("Trello did not return a checklist id when creating a new checklist.")

    for item in _notes_to_items(notes):
        _add_check_item(new_id, item)

    return new_id
