from __future__ import annotations

import asyncio
import os
import socket
from typing import List

import httpx

from app.models.schemas import ServiceStatus


async def _tcp_check(host: str, port: int, timeout: float = 2.0) -> tuple[bool, str]:
    try:
        await asyncio.wait_for(asyncio.open_connection(host, port), timeout=timeout)
        return True, "reachable"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


async def _http_check(url: str, timeout: float = 3.0) -> tuple[bool, str]:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url)
            if resp.status_code < 500:
                return True, f"HTTP {resp.status_code}"
            return False, f"HTTP {resp.status_code}"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


async def check_all_services() -> List[ServiceStatus]:
    ssh_host = os.getenv("SSH_HOST", "172.28.0.11")
    ssh_port = int(os.getenv("SSH_PORT", "22"))
    web_host = os.getenv("WEB_HOST", "172.28.0.12")
    web_port = int(os.getenv("WEB_PORT", "80"))
    mysql_host = os.getenv("MYSQL_HOST", "172.28.0.13")
    mysql_port = int(os.getenv("MYSQL_PORT", "3306"))

    ssh_ok, ssh_detail = await _tcp_check(ssh_host, ssh_port)
    web_ok, web_detail = await _http_check(f"http://{web_host}:{web_port}/")
    mysql_ok, mysql_detail = await _tcp_check(mysql_host, mysql_port)

    # Resolve local hostname for diagnostics
    try:
        hostname = socket.gethostname()
    except OSError:
        hostname = "unknown"

    return [
        ServiceStatus(name="api", healthy=True, detail=f"hostname={hostname}"),
        ServiceStatus(name="ssh", healthy=ssh_ok, detail=ssh_detail),
        ServiceStatus(name="website", healthy=web_ok, detail=web_detail),
        ServiceStatus(name="mysql", healthy=mysql_ok, detail=mysql_detail),
    ]
