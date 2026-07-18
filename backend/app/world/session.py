from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from app.world.loader import get_world


@dataclass
class SessionState:
    id: str
    user: str
    cwd: str
    history: list[str] = field(default_factory=list)
    # Ephemeral overlays for touch/mkdir/rm during a session
    overlay: dict[str, dict[str, Any]] = field(default_factory=dict)
    deleted: set[str] = field(default_factory=set)


_SESSIONS: dict[str, SessionState] = {}


def create_session(user: str | None = None, session_id: str | None = None) -> SessionState:
    world = get_world()
    username = user or world.users.get("default_user", "developer")
    if username not in world.known_usernames() and username != "root":
        username = world.users.get("default_user", "developer")
    home = "/root" if username == "root" else f"/home/{username}"
    rec = world.user_record(username)
    if rec:
        home = rec.get("home", home)
    state = SessionState(id=session_id or str(uuid4()), user=username, cwd=home)
    _SESSIONS[state.id] = state
    return state


def get_session(session_id: str) -> SessionState | None:
    return _SESSIONS.get(session_id)


def get_or_create_session(session_id: str | None, user: str | None = None) -> SessionState:
    if session_id and session_id in _SESSIONS:
        return _SESSIONS[session_id]
    return create_session(user)
