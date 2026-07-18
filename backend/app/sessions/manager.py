"""Session lifecycle manager — create, end, lookup."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import EventRecord, SessionLocal, SessionRecord
from app.events.logger import EventLogger, session_to_out
from app.events.schemas import SessionCreate, SessionOut
from app.events.types import EventType, SessionStatus
from app.events.websocket import hub


# Very small private-range / local heuristics; no external GeoIP dependency in Phase 3
def guess_country(ip: str | None) -> str | None:
    if not ip:
        return None
    if ip.startswith(("127.", "10.", "192.168.", "172.")) or ip in (
        "ssh-container",
        "mysql-container",
        "::1",
    ):
        return "Local"
    return "Unknown"


class SessionManager:
    @staticmethod
    async def create(
        data: SessionCreate,
        *,
        db: AsyncSession | None = None,
        emit_event: bool = True,
    ) -> SessionOut:
        owns_db = db is None
        if owns_db:
            db = SessionLocal()
        assert db is not None

        sid = data.id or uuid.uuid4()
        country = data.country or guess_country(data.source_ip)
        meta = dict(data.meta or {})
        if data.service and "service" not in meta:
            meta["service"] = data.service

        record = SessionRecord(
            id=sid,
            start_time=datetime.now(timezone.utc),
            source_ip=data.source_ip,
            service=data.service or "ssh",
            country=country,
            status=SessionStatus.ACTIVE.value,
            username=data.username,
            user_agent=data.user_agent,
            meta=meta,
        )
        try:
            db.add(record)
            await db.commit()
            await db.refresh(record)
            out = session_to_out(record, event_count=0)

            if emit_event:
                await EventLogger.log(
                    record.id,
                    EventType.SESSION_START,
                    {
                        "service": record.service,
                        "source_ip": record.source_ip,
                        "username": record.username,
                    },
                    service=record.service,
                    ip=record.source_ip,
                    db=db,
                )
                # re-fetch after event
                await db.refresh(record)
                out = session_to_out(record, event_count=1)

            await hub.broadcast(
                {"type": "session", "action": "created", "session": out.model_dump(mode="json")}
            )
            return out
        finally:
            if owns_db:
                await db.close()

    @staticmethod
    async def end(
        session_id: UUID | str,
        reason: str = "disconnect",
        *,
        db: AsyncSession | None = None,
        emit_event: bool = True,
    ) -> SessionOut | None:
        owns_db = db is None
        if owns_db:
            db = SessionLocal()
        assert db is not None

        sid = UUID(str(session_id))
        try:
            record = await db.get(SessionRecord, sid)
            if record is None:
                return None
            if record.status == SessionStatus.COMPLETED.value:
                return session_to_out(record)

            record.end_time = datetime.now(timezone.utc)
            record.status = SessionStatus.COMPLETED.value
            record.end_reason = reason
            await db.commit()
            await db.refresh(record)

            if emit_event:
                await EventLogger.log(
                    sid,
                    EventType.SESSION_END,
                    {"reason": reason, "duration_seconds": session_to_out(record).duration_seconds},
                    service=record.service,
                    ip=record.source_ip,
                    db=db,
                )
                await EventLogger.log(
                    sid,
                    EventType.LOGOUT,
                    {"reason": reason, "user": record.username},
                    service=record.service,
                    ip=record.source_ip,
                    db=db,
                )

            out = session_to_out(record)
            await hub.broadcast(
                {"type": "session", "action": "ended", "session": out.model_dump(mode="json")}
            )
            return out
        finally:
            if owns_db:
                await db.close()

    @staticmethod
    async def get(session_id: UUID | str, *, db: AsyncSession | None = None) -> SessionOut | None:
        owns_db = db is None
        if owns_db:
            db = SessionLocal()
        assert db is not None
        try:
            record = await db.get(SessionRecord, UUID(str(session_id)))
            if not record:
                return None
            count = await db.scalar(
                select(func.count()).select_from(EventRecord).where(EventRecord.session_id == record.id)
            )
            return session_to_out(record, event_count=int(count or 0))
        finally:
            if owns_db:
                await db.close()
