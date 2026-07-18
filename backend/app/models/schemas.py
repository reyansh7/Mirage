"""Backward-compatible re-exports — prefer app.events.schemas."""

from __future__ import annotations

from pydantic import BaseModel

from app.events.schemas import (  # noqa: F401
    EventCreate,
    EventOut,
    SessionCreate,
    SessionOut,
)


class ServiceStatus(BaseModel):
    name: str
    healthy: bool
    detail: str = ""


class HealthResponse(BaseModel):
    status: str
    services: list[ServiceStatus]
