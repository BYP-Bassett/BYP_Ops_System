# app/services/trello_service.py
# Trello sync utilities:
# - Delete existing checklist
# - Recreate checklist named as SP Number (or NEW for art)
# - Recreate checklist items from order.notes

from __future__ import annotations

import json
import os
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


TRELLO_API_BASE = "https://api.trello.com/1"


class TrelloConfigError(RuntimeError):
    pass


def _trello_auth_params() -> dict:
    key = os.environ.get("TRELLO_KEY", "").strip()
    token = os.environ.get("TRELLO_TOKEN", "").strip()
    if not key or not token:
        raise TrelloConfigError("Missing Trello credentials. Set TRELLO_KEY and TRELLO_TOKEN env vars.")
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
