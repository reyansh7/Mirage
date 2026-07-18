#!/usr/bin/env python3
"""Interactive fake shell — forwards commands to the Phase-2 Command Engine API.

Never executes attacker commands on the real container OS.
Phase 3: session UUID is the flight-recorder session; commands are logged by the API.
"""

from __future__ import annotations

import os
import pwd
import sys

import requests

API_URL = os.getenv("LOG_API_URL", "http://172.28.0.10:8000").rstrip("/")


def current_user() -> str:
    try:
        return pwd.getpwuid(os.getuid()).pw_name
    except Exception:
        return os.getenv("USER", "developer")


def source_ip() -> str | None:
    return os.getenv("SSH_CLIENT", "").split(" ")[0] or None


def end_session(session_id: str, reason: str = "disconnect") -> None:
    try:
        requests.post(
            f"{API_URL}/sessions/{session_id}/end",
            json={"reason": reason},
            timeout=3,
        )
    except Exception:
        pass


def wait_for_api() -> None:
    for _ in range(60):
        try:
            if requests.get(f"{API_URL}/docs", timeout=2).status_code < 500:
                return
        except Exception:
            pass
        import time

        time.sleep(1)


def main() -> int:
    wait_for_api()
    user = current_user()
    # Map root logins into developer world for a friendlier demo
    world_user = "developer" if user == "root" else user
    ip = source_ip()

    try:
        resp = requests.post(
            f"{API_URL}/world/session",
            json={"user": world_user, "source_ip": ip},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        print(f"build-server-01: unable to start session ({exc})", file=sys.stderr)
        return 1

    session_id = data["session_id"]
    prompt = data["prompt"]
    print(data.get("banner", ""))
    print()

    # Non-interactive: ssh host 'ls /home' → SSH_ORIGINAL_COMMAND
    original = os.environ.get("SSH_ORIGINAL_COMMAND")
    if original:
        try:
            result = requests.post(
                f"{API_URL}/command",
                json={"session_id": session_id, "command": original, "user": world_user},
                timeout=15,
            )
            result.raise_for_status()
            payload = result.json()
            output = payload.get("output") or ""
            if output:
                print(output)
            end_session(session_id, reason="command_complete")
            return int(payload.get("exit_code") or 0)
        except Exception as exc:
            print(f"bash: {exc}", file=sys.stderr)
            end_session(session_id, reason="error")
            return 1

    exit_reason = "disconnect"
    while True:
        try:
            line = input(prompt)
        except (EOFError, KeyboardInterrupt):
            print()
            exit_reason = "eof"
            break

        command = line.rstrip("\n")
        if not command.strip():
            continue

        try:
            result = requests.post(
                f"{API_URL}/command",
                json={"session_id": session_id, "command": command, "user": world_user},
                timeout=15,
            )
            if result.status_code == 404:
                boot = requests.post(
                    f"{API_URL}/world/session",
                    json={"user": world_user, "source_ip": ip},
                    timeout=10,
                )
                boot.raise_for_status()
                data = boot.json()
                session_id = data["session_id"]
                prompt = data["prompt"]
                result = requests.post(
                    f"{API_URL}/command",
                    json={"session_id": session_id, "command": command, "user": world_user},
                    timeout=15,
                )
            result.raise_for_status()
            payload = result.json()
        except Exception as exc:
            print(f"bash: connection to command engine failed: {exc}", file=sys.stderr)
            continue

        output = payload.get("output") or ""
        if output:
            print(output)
        prompt = payload.get("prompt") or prompt
        if payload.get("exit_session"):
            exit_reason = "logout"
            break

    end_session(session_id, reason=exit_reason)
    return 0


if __name__ == "__main__":
    sys.exit(main())
