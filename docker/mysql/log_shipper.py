#!/usr/bin/env python3
"""Watch MySQL general log and emit typed CONNECT / SQL_QUERY events."""

from __future__ import annotations

import os
import re
import time
from datetime import datetime, timezone

try:
    import requests
except ImportError:
    requests = None

API_URL = os.getenv("LOG_API_URL", "http://172.28.0.10:8000").rstrip("/")
LOG_PATH = "/var/log/mysql/general.log"

# connection_id → session_id
_CONN_SESSIONS: dict[str, str] = {}
_FALLBACK_SESSION: str | None = None

CONNECT_RE = re.compile(r"^\s*(\d+)\s+Connect\s+(\S+)", re.I)
QUERY_RE = re.compile(r"^\s*(\d+)\s+Query\s+(.+)$", re.I)
QUIT_RE = re.compile(r"^\s*(\d+)\s+Quit", re.I)


def ensure_session(user: str | None = None, conn_id: str | None = None) -> str | None:
    global _FALLBACK_SESSION
    if not requests:
        return None
    if conn_id and conn_id in _CONN_SESSIONS:
        return _CONN_SESSIONS[conn_id]
    try:
        resp = requests.post(
            f"{API_URL}/session",
            json={
                "source_ip": "mysql-client",
                "service": "mysql",
                "username": user,
                "user_agent": "mysql-log-shipper",
                "meta": {"conn_id": conn_id},
            },
            timeout=5,
        )
        if resp.ok:
            sid = resp.json().get("id")
            if sid and conn_id:
                _CONN_SESSIONS[conn_id] = sid
            elif sid:
                _FALLBACK_SESSION = sid
            return sid
    except Exception:
        pass
    return _FALLBACK_SESSION


def post_event(event_type: str, details: dict, ip=None, session: str | None = None) -> None:
    if not requests:
        return
    payload = {
        "service": "mysql",
        "event_type": event_type,
        "ip": ip,
        "session": session,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": details,
    }
    for _ in range(5):
        try:
            requests.post(f"{API_URL}/events", json=payload, timeout=5)
            return
        except Exception:
            time.sleep(2)


def _classify_sql(query: str) -> dict:
    q = query.strip()
    upper = q.upper()
    op = "OTHER"
    for keyword in ("SELECT", "INSERT", "UPDATE", "DELETE", "SHOW", "USE", "CREATE", "DROP"):
        if upper.startswith(keyword):
            op = keyword
            break
    return {
        "query": q[:500],
        "operation": op,
        "database": "corporate",
        "raw": q[:500],
    }


def handle_line(line: str) -> None:
    line = line.strip()
    if not line:
        return

    m = CONNECT_RE.search(line)
    if m:
        conn_id, user = m.group(1), m.group(2)
        # Strip @host if present
        username = user.split("@")[0]
        sid = ensure_session(username, conn_id)
        post_event(
            "CONNECT",
            {"user": username, "username": username, "conn_id": conn_id, "raw": line},
            session=sid,
        )
        post_event(
            "LOGIN",
            {"user": username, "username": username, "conn_id": conn_id},
            session=sid,
        )
        return

    m = QUERY_RE.search(line)
    if m:
        conn_id, query = m.group(1), m.group(2)
        sid = _CONN_SESSIONS.get(conn_id) or ensure_session(conn_id=conn_id)
        details = _classify_sql(query)
        details["conn_id"] = conn_id
        post_event("SQL_QUERY", details, session=sid)
        return

    m = QUIT_RE.search(line)
    if m:
        conn_id = m.group(1)
        sid = _CONN_SESSIONS.pop(conn_id, None)
        if sid and requests:
            try:
                requests.post(
                    f"{API_URL}/sessions/{sid}/end",
                    json={"reason": "mysql_quit"},
                    timeout=3,
                )
            except Exception:
                pass


def wait_for_api() -> None:
    if not requests:
        return
    for _ in range(60):
        try:
            if requests.get(f"{API_URL}/health", timeout=2).status_code < 500:
                return
        except Exception:
            time.sleep(2)


def follow(path: str):
    while not os.path.exists(path):
        time.sleep(1)
    with open(path, "r", encoding="utf-8", errors="ignore") as fh:
        fh.seek(0, os.SEEK_END)
        while True:
            line = fh.readline()
            if not line:
                time.sleep(0.5)
                continue
            handle_line(line)


if __name__ == "__main__":
    wait_for_api()
    post_event("CONNECT", {"message": "mysql log shipper online"}, session=ensure_session())
    follow(LOG_PATH)
