"""Per-property chat session cache.

Backs ``ga reports chat --continue``. Sessions are keyed by property ID so
that switching properties never resumes the wrong conversation.

Only the session ID and a timestamp are persisted — never the user's query
or any part of the response.
"""

from __future__ import annotations

import json
import logging
import os
import platform
from datetime import datetime, timezone
from typing import Optional

from .constants import get_chat_sessions_path, get_config_dir

logger = logging.getLogger(__name__)


def _read_all() -> dict:
    """Load the whole cache, treating any unreadable state as empty.

    A corrupt cache is a convenience feature failing, not a reason to break
    the command the user actually asked for.
    """
    path = get_chat_sessions_path()
    if not path.exists():
        return {}

    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to read chat session cache: %s", exc)
        return {}

    return data if isinstance(data, dict) else {}


def _write_all(data: dict) -> None:
    path = get_chat_sessions_path()
    get_config_dir().mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))

    if platform.system() != "Windows":
        os.chmod(path, 0o600)


def save_session(property_id: str, session_id: str) -> None:
    """Record the most recent session for ``property_id``."""
    data = _read_all()
    data[str(property_id)] = {
        "sessionId": session_id,
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }
    _write_all(data)


def load_session(property_id: str) -> Optional[str]:
    """Return the cached session ID for ``property_id``, or None.

    Returns None for anything unusable — no file, unknown property, or an
    entry that is not the shape we wrote.
    """
    entry = _read_all().get(str(property_id))
    if not isinstance(entry, dict):
        return None

    session_id = entry.get("sessionId")
    return session_id if isinstance(session_id, str) and session_id else None


def clear_session(property_id: str) -> None:
    """Forget the cached session for ``property_id``, leaving others intact."""
    data = _read_all()
    if data.pop(str(property_id), None) is not None:
        _write_all(data)
