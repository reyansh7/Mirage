from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.events.types import EventType, ServiceName, SessionStatus


class EventCreate(BaseModel):
    """Ingest payload — accepts Phase 3 typed fields and Phase 1/2 legacy fields."""

    service: str = Field(..., examples=["ssh", "http", "mysql"])
    event_type: Optional[str] = Field(None, examples=["COMMAND", "AUTH_SUCCESS"])
    # Legacy
    event: Optional[str] = Field(None, examples=["SSH LOGIN", "HTTP GET"])
    ip: Optional[str] = None
    session: Optional[UUID] = None
    session_id: Optional[UUID] = None
    timestamp: Optional[datetime] = None
    payload: dict[str, Any] = Field(default_factory=dict)
    details: dict[str, Any] = Field(default_factory=dict)

    def resolved_session_id(self) -> Optional[UUID]:
        return self.session_id or self.session

    def resolved_payload(self) -> dict[str, Any]:
        return self.payload or self.details or {}

    def resolved_event_type(self) -> str:
        raw = self.event_type or self.event or "COMMAND"
        return raw


class EventOut(BaseModel):
    id: int
    event_id: str
    session_id: Optional[UUID]
    timestamp: datetime
    service: str
    event_type: str
    payload: dict[str, Any]
    ip: Optional[str] = None

    model_config = {"from_attributes": True}


class EventListResponse(BaseModel):
    items: list[EventOut]
    total: int


class SessionCreate(BaseModel):
    source_ip: Optional[str] = None
    user_agent: Optional[str] = None
    service: str = Field(default=ServiceName.SSH, examples=["ssh", "http", "mysql"])
    country: Optional[str] = None
    username: Optional[str] = None
    meta: dict[str, Any] = Field(default_factory=dict)
    # Optional client-supplied UUID (used to align world session + DB session)
    id: Optional[UUID] = None


class SessionEnd(BaseModel):
    reason: str = "disconnect"


class SessionOut(BaseModel):
    id: UUID
    start_time: datetime
    end_time: Optional[datetime] = None
    source_ip: Optional[str] = None
    service: str
    country: Optional[str] = None
    status: str
    username: Optional[str] = None
    user_agent: Optional[str] = None
    end_reason: Optional[str] = None
    meta: dict[str, Any] = Field(default_factory=dict)
    duration_seconds: Optional[float] = None
    event_count: Optional[int] = None

    model_config = {"from_attributes": True}


class SessionListResponse(BaseModel):
    items: list[SessionOut]
    total: int
    active: int


class TimelineItem(BaseModel):
    timestamp: datetime
    event_type: str
    service: str
    summary: str
    payload: dict[str, Any] = Field(default_factory=dict)
    event_id: str


class TimelineResponse(BaseModel):
    session: SessionOut
    items: list[TimelineItem]


class ReplayFrame(BaseModel):
    timestamp: datetime
    event_type: str
    prompt: Optional[str] = None
    command: Optional[str] = None
    output: Optional[str] = None
    cwd: Optional[str] = None
    user: Optional[str] = None
    delay_ms: int = 400


class ReplayResponse(BaseModel):
    session: SessionOut
    frames: list[ReplayFrame]


class FileAccessOut(BaseModel):
    id: int
    session_id: UUID
    filename: str
    action: str
    time: datetime

    model_config = {"from_attributes": True}


class CommandOut(BaseModel):
    id: int
    session_id: UUID
    command: str
    cwd: Optional[str]
    output: Optional[str]
    exit_code: Optional[int]
    timestamp: datetime

    model_config = {"from_attributes": True}


class LiveEventMessage(BaseModel):
    """WebSocket broadcast envelope."""

    type: str = "event"
    event: EventOut
    session: Optional[SessionOut] = None


__all__ = [
    "CommandOut",
    "EventCreate",
    "EventListResponse",
    "EventOut",
    "EventType",
    "FileAccessOut",
    "LiveEventMessage",
    "ReplayFrame",
    "ReplayResponse",
    "SessionCreate",
    "SessionEnd",
    "SessionListResponse",
    "SessionOut",
    "SessionStatus",
    "TimelineItem",
    "TimelineResponse",
]
