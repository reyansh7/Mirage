"""Central EventLogger — every service calls this instead of print()/ad-hoc POSTs."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import (
    CommandRecord,
    EventRecord,
    FileAccessRecord,
    SessionLocal,
    SessionRecord,
)
from app.events.schemas import EventOut, LiveEventMessage, SessionOut
from app.events.types import EventType, normalize_event_type
from app.events.websocket import hub


def _duration_seconds(session: SessionRecord) -> Optional[float]:
    if not session.start_time:
        return None
    end = session.end_time or datetime.now(timezone.utc)
    start = session.start_time
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    return max(0.0, (end - start).total_seconds())


def session_to_out(session: SessionRecord, event_count: Optional[int] = None) -> SessionOut:
    return SessionOut(
        id=session.id,
        start_time=session.start_time,
        end_time=session.end_time,
        source_ip=session.source_ip,
        service=session.service,
        country=session.country,
        status=session.status,
        username=session.username,
        user_agent=session.user_agent,
        end_reason=session.end_reason,
        meta=session.meta or {},
        duration_seconds=_duration_seconds(session),
        event_count=event_count,
    )


def event_to_out(record: EventRecord) -> EventOut:
    return EventOut(
        id=record.id,
        event_id=record.event_id,
        session_id=record.session_id,
        timestamp=record.timestamp,
        service=record.service,
        event_type=record.event_type,
        payload=record.payload or record.details or {},
        ip=record.ip,
    )


class EventLogger:
    """Flight-recorder logger used by SSH, HTTP, MySQL, and the command engine."""

    @staticmethod
    async def log(
        session_id: UUID | str | None,
        event_type: EventType | str,
        payload: dict[str, Any] | None = None,
        *,
        service: str = "ssh",
        ip: str | None = None,
        timestamp: datetime | None = None,
        db: AsyncSession | None = None,
    ) -> EventOut:
        owns_db = db is None
        if owns_db:
            db = SessionLocal()

        assert db is not None
        payload = dict(payload or {})
        et = normalize_event_type(
            event_type.value if isinstance(event_type, EventType) else str(event_type),
            payload,
        )
        sid: UUID | None = None
        if session_id is not None:
            sid = UUID(str(session_id)) if not isinstance(session_id, UUID) else session_id

        ts = timestamp or datetime.now(timezone.utc)
        event_id = f"evt_{uuid.uuid4().hex[:12]}"

        record = EventRecord(
            event_id=event_id,
            session_id=sid,
            timestamp=ts,
            service=service,
            event_type=et.value,
            payload=payload,
            ip=ip,
            # legacy mirrors
            event=et.value,
            details=payload,
        )
        try:
            db.add(record)
            await db.flush()

            if sid is not None:
                await EventLogger._side_tables(db, sid, et, payload, ts)
                # Update username on session if present
                if payload.get("user") or payload.get("username"):
                    sess = await db.get(SessionRecord, sid)
                    if sess and not sess.username:
                        sess.username = payload.get("user") or payload.get("username")

            await db.commit()
            await db.refresh(record)
            out = event_to_out(record)

            session_out = None
            if sid is not None:
                sess = await db.get(SessionRecord, sid)
                if sess:
                    session_out = session_to_out(sess)

            await hub.broadcast(
                LiveEventMessage(type="event", event=out, session=session_out).model_dump(
                    mode="json"
                )
            )
            return out
        finally:
            if owns_db:
                await db.close()

    @staticmethod
    async def _side_tables(
        db: AsyncSession,
        session_id: UUID,
        event_type: EventType,
        payload: dict[str, Any],
        ts: datetime,
    ) -> None:
        if event_type == EventType.COMMAND:
            db.add(
                CommandRecord(
                    session_id=session_id,
                    command=str(payload.get("command") or payload.get("raw") or ""),
                    cwd=payload.get("cwd"),
                    output=payload.get("output"),
                    exit_code=payload.get("exit_code"),
                    timestamp=ts,
                )
            )
        elif event_type in (
            EventType.FILE_READ,
            EventType.FILE_WRITE,
            EventType.FILE_DELETE,
        ):
            action = payload.get("action") or {
                EventType.FILE_READ: "read",
                EventType.FILE_WRITE: "write",
                EventType.FILE_DELETE: "delete",
            }[event_type]
            filename = payload.get("filename") or payload.get("path") or ""
            if filename:
                db.add(
                    FileAccessRecord(
                        session_id=session_id,
                        filename=str(filename),
                        action=str(action),
                        time=ts,
                    )
                )


# Convenience module-level alias matching the Phase 3 sketch
async def log(
    session_id: UUID | str | None,
    event_type: EventType | str,
    payload: dict[str, Any] | None = None,
    **kwargs: Any,
) -> EventOut:
    return await EventLogger.log(session_id, event_type, payload, **kwargs)
