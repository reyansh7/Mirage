"""Canonical event types for the Phase 3 flight recorder.

All services must emit one of these — never free-form strings.
"""

from __future__ import annotations

from enum import StrEnum


class EventType(StrEnum):
    COMMAND = "COMMAND"
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    FILE_READ = "FILE_READ"
    FILE_WRITE = "FILE_WRITE"
    FILE_DELETE = "FILE_DELETE"
    DIRECTORY_CHANGE = "DIRECTORY_CHANGE"
    HTTP_REQUEST = "HTTP_REQUEST"
    SQL_QUERY = "SQL_QUERY"
    NETWORK_SCAN = "NETWORK_SCAN"
    AUTH_FAILURE = "AUTH_FAILURE"
    AUTH_SUCCESS = "AUTH_SUCCESS"
    CONNECT = "CONNECT"
    SESSION_START = "SESSION_START"
    SESSION_END = "SESSION_END"


class SessionStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"


class ServiceName(StrEnum):
    SSH = "ssh"
    HTTP = "http"
    MYSQL = "mysql"
    FTP = "ftp"
    SYSTEM = "system"


# Map legacy Phase 1/2 free-form event names → typed enums
LEGACY_EVENT_MAP: dict[str, EventType] = {
    "SSH CONNECT": EventType.CONNECT,
    "SSH LOGIN": EventType.AUTH_SUCCESS,
    "SSH LOGIN FAILED": EventType.AUTH_FAILURE,
    "SSH COMMAND": EventType.COMMAND,
    "SSH WORLD SESSION": EventType.SESSION_START,
    "SSH SERVICE START": EventType.CONNECT,
    "HTTP GET": EventType.HTTP_REQUEST,
    "HTTP POST": EventType.HTTP_REQUEST,
    "HTTP PUT": EventType.HTTP_REQUEST,
    "HTTP DELETE": EventType.HTTP_REQUEST,
    "HTTP PATCH": EventType.HTTP_REQUEST,
    "HTTP HEAD": EventType.HTTP_REQUEST,
    "HTTP OPTIONS": EventType.HTTP_REQUEST,
    "HTTP LOGIN ATTEMPT": EventType.AUTH_FAILURE,  # refined by payload.success
    "MYSQL CONNECT": EventType.CONNECT,
    "MYSQL QUERY": EventType.SQL_QUERY,
    "MYSQL SERVICE START": EventType.CONNECT,
}


def normalize_event_type(raw: str, payload: dict | None = None) -> EventType:
    """Accept enum value or legacy string; return EventType."""
    payload = payload or {}
    upper = (raw or "").strip().upper().replace(" ", "_")
    try:
        return EventType(upper)
    except ValueError:
        pass
    try:
        return EventType(raw.strip())
    except ValueError:
        pass

    if raw.upper().startswith("HTTP ") and raw.upper() != "HTTP LOGIN ATTEMPT":
        return EventType.HTTP_REQUEST

    mapped = LEGACY_EVENT_MAP.get(raw.strip())
    if mapped is EventType.AUTH_FAILURE and "success" in payload:
        return EventType.AUTH_SUCCESS if payload["success"] else EventType.AUTH_FAILURE
    if mapped:
        return mapped
    return EventType.COMMAND
