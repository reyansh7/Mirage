#!/usr/bin/env python3
"""Tail SSH auth output and POST typed events to the honeypot logging API."""

from __future__ import annotations

import os
import re
import time
from datetime import datetime, timezone

import requests

API_URL = os.getenv("LOG_API_URL", "http://172.28.0.10:8000").rstrip("/")
LOG_PATH = "/var/log/sshd.log"

# Per source-IP active sessions (auth phase, before fake_shell bootstraps world session)
_IP_SESSIONS: dict[str, str] = {}

ACCEPTED = re.compile(r"Accepted\s+\w+\s+for\s+(\S+)\s+from\s+(\S+)", re.I)
FAILED = re.compile(
    r"Failed\s+\w+\s+for\s+(?:invalid user\s+)?(\S+)\s+from\s+(\S+)",
    re.I,
)
CONNECTION = re.compile(r"Connection from\s+(\S+)\s+port\s+(\d+)", re.I)
DISCONNECT = re.compile(r"Disconnected from(?:\s+user\s+\S+)?\s+(\S+)", re.I)


def ensure_session(ip: str | None, username: str | None = None) -> str | None:
    key = ip or "unknown"
    if key in _IP_SESSIONS:
        return _IP_SESSIONS[key]
    try:
        resp = requests.post(
            f"{API_URL}/session",
            json={
                "source_ip": ip,
                "service": "ssh",
                "username": username,
                "user_agent": "ssh-log-shipper",
                "meta": {"phase": "auth"},
            },
            timeout=5,
        )
        if resp.ok:
            sid = resp.json().get("id")
            if sid:
                _IP_SESSIONS[key] = sid
                return sid
    except Exception:
        pass
    return None


def post_event(event_type: str, ip, details: dict, session: str | None = None) -> None:
    payload = {
        "service": "ssh",
        "event_type": event_type,
        "ip": ip,
        "session": session or ensure_session(ip, details.get("user") or details.get("username")),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": details,
    }
    for _ in range(5):
        try:
            requests.post(f"{API_URL}/events", json=payload, timeout=5)
            return
        except Exception:
            time.sleep(2)


def handle_line(line: str) -> None:
    line = line.strip()
    if not line:
        return

    m = ACCEPTED.search(line)
    if m:
        user, ip = m.group(1), m.group(2)
        sid = ensure_session(ip, user)
        post_event(
            "AUTH_SUCCESS",
            ip,
            {"user": user, "username": user, "raw": line, "method": "password"},
            session=sid,
        )
        return

    m = FAILED.search(line)
    if m:
        user, ip = m.group(1), m.group(2)
        sid = ensure_session(ip, user)
        post_event(
            "AUTH_FAILURE",
            ip,
            {"user": user, "username": user, "raw": line, "success": False},
            session=sid,
        )
        return

    m = CONNECTION.search(line)
    if m:
        ip, port = m.group(1), m.group(2)
        sid = ensure_session(ip)
        post_event("CONNECT", ip, {"port": port, "raw": line}, session=sid)
        return

    m = DISCONNECT.search(line)
    if m:
        ip = m.group(1)
        sid = _IP_SESSIONS.pop(ip, None)
        if sid:
            try:
                requests.post(
                    f"{API_URL}/sessions/{sid}/end",
                    json={"reason": "ssh_disconnect"},
                    timeout=3,
                )
            except Exception:
                pass


def wait_for_api() -> None:
    for _ in range(60):
        try:
            if requests.get(f"{API_URL}/health", timeout=2).status_code < 500:
                return
        except Exception:
            time.sleep(2)


def follow(path: str) -> None:
    while not os.path.exists(path):
        time.sleep(0.5)
    with open(path, "r", encoding="utf-8", errors="ignore") as fh:
        fh.seek(0, os.SEEK_END)
        while True:
            line = fh.readline()
            if not line:
                time.sleep(0.3)
                continue
            handle_line(line)


if __name__ == "__main__":
    wait_for_api()
    post_event("CONNECT", None, {"message": "ssh log shipper online"})
    follow(LOG_PATH)
