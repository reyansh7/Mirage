"""Session query helpers — list, timeline, replay."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import (
    CommandRecord,
    EventRecord,
    FileAccessRecord,
    SessionRecord,
)
from app.events.logger import event_to_out, session_to_out
from app.events.schemas import (
    CommandOut,
    EventOut,
    FileAccessOut,
    ReplayFrame,
    ReplayResponse,
    SessionListResponse,
    SessionOut,
    TimelineItem,
    TimelineResponse,
)
from app.events.types import EventType, SessionStatus


def _summarize(event_type: str, payload: dict) -> str:
    p = payload or {}
    if event_type == EventType.COMMAND:
        return f"$ {p.get('command', '')}".strip()
    if event_type == EventType.DIRECTORY_CHANGE:
        return f"cd {p.get('cwd') or p.get('path') or ''}"
    if event_type in (EventType.FILE_READ, EventType.FILE_WRITE, EventType.FILE_DELETE):
        return f"{event_type.split('_')[1].lower()} {p.get('filename') or p.get('path') or ''}"
    if event_type == EventType.HTTP_REQUEST:
        method = p.get("method", "GET")
        path = p.get("url") or p.get("path") or "/"
        code = p.get("status") or p.get("response_code")
        return f"{method} {path}" + (f" → {code}" if code else "")
    if event_type == EventType.SQL_QUERY:
        return str(p.get("query") or p.get("sql") or "")[:120]
    if event_type in (EventType.AUTH_SUCCESS, EventType.AUTH_FAILURE, EventType.LOGIN):
        user = p.get("user") or p.get("username") or "?"
        return f"{event_type}: {user}"
    if event_type == EventType.LOGOUT:
        return f"logout ({p.get('reason', 'disconnect')})"
    if event_type == EventType.CONNECT:
        return f"connect from {p.get('source_ip') or p.get('ip') or ''}"
    return event_type


class SessionService:
    @staticmethod
    async def list_sessions(
        db: AsyncSession,
        *,
        status: Optional[str] = None,
        service: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> SessionListResponse:
        q = select(SessionRecord)
        if status:
            q = q.where(SessionRecord.status == status)
        if service:
            q = q.where(SessionRecord.service == service)
        q = q.order_by(SessionRecord.start_time.desc()).offset(offset).limit(limit)

        rows = (await db.scalars(q)).all()
        total = await db.scalar(select(func.count()).select_from(SessionRecord)) or 0
        active = await db.scalar(
            select(func.count())
            .select_from(SessionRecord)
            .where(SessionRecord.status == SessionStatus.ACTIVE.value)
        ) or 0

        items: list[SessionOut] = []
        for row in rows:
            count = await db.scalar(
                select(func.count())
                .select_from(EventRecord)
                .where(EventRecord.session_id == row.id)
            )
            items.append(session_to_out(row, event_count=int(count or 0)))
        return SessionListResponse(items=items, total=int(total), active=int(active))

    @staticmethod
    async def list_events(
        db: AsyncSession,
        *,
        session_id: Optional[UUID] = None,
        event_type: Optional[str] = None,
        service: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[EventOut], int]:
        q = select(EventRecord)
        count_q = select(func.count()).select_from(EventRecord)
        if session_id:
            q = q.where(EventRecord.session_id == session_id)
            count_q = count_q.where(EventRecord.session_id == session_id)
        if event_type:
            q = q.where(EventRecord.event_type == event_type)
            count_q = count_q.where(EventRecord.event_type == event_type)
        if service:
            q = q.where(EventRecord.service == service)
            count_q = count_q.where(EventRecord.service == service)

        total = await db.scalar(count_q) or 0
        rows = (
            await db.scalars(q.order_by(EventRecord.timestamp.desc()).offset(offset).limit(limit))
        ).all()
        return [event_to_out(r) for r in rows], int(total)

    @staticmethod
    async def timeline(db: AsyncSession, session_id: UUID) -> TimelineResponse | None:
        session = await db.get(SessionRecord, session_id)
        if not session:
            return None
        rows = (
            await db.scalars(
                select(EventRecord)
                .where(EventRecord.session_id == session_id)
                .order_by(EventRecord.timestamp.asc())
            )
        ).all()
        items = [
            TimelineItem(
                timestamp=r.timestamp,
                event_type=r.event_type,
                service=r.service,
                summary=_summarize(r.event_type, r.payload or r.details or {}),
                payload=r.payload or r.details or {},
                event_id=r.event_id,
            )
            for r in rows
        ]
        count = len(items)
        return TimelineResponse(session=session_to_out(session, event_count=count), items=items)

    @staticmethod
    async def replay(db: AsyncSession, session_id: UUID) -> ReplayResponse | None:
        session = await db.get(SessionRecord, session_id)
        if not session:
            return None

        rows = (
            await db.scalars(
                select(EventRecord)
                .where(EventRecord.session_id == session_id)
                .order_by(EventRecord.timestamp.asc())
            )
        ).all()

        user = session.username or "attacker"
        frames: list[ReplayFrame] = []
        prev_ts: datetime | None = None

        for r in rows:
            payload = r.payload or r.details or {}
            delay = 400
            if prev_ts and r.timestamp:
                delta = (r.timestamp - prev_ts).total_seconds()
                delay = int(min(max(delta * 1000, 200), 2500))
            prev_ts = r.timestamp

            if r.event_type == EventType.COMMAND:
                frames.append(
                    ReplayFrame(
                        timestamp=r.timestamp,
                        event_type=r.event_type,
                        prompt=payload.get("prompt"),
                        command=payload.get("command"),
                        output=payload.get("output") or "",
                        cwd=payload.get("cwd"),
                        user=payload.get("user") or user,
                        delay_ms=delay,
                    )
                )
            elif r.event_type in (
                EventType.AUTH_SUCCESS,
                EventType.LOGIN,
                EventType.SESSION_START,
            ):
                frames.append(
                    ReplayFrame(
                        timestamp=r.timestamp,
                        event_type=r.event_type,
                        output=f"[login] {payload.get('user') or payload.get('username') or user}",
                        user=payload.get("user") or user,
                        delay_ms=delay,
                    )
                )
            elif r.event_type in (EventType.LOGOUT, EventType.SESSION_END):
                frames.append(
                    ReplayFrame(
                        timestamp=r.timestamp,
                        event_type=r.event_type,
                        output=f"[logout] {payload.get('reason', 'disconnect')}",
                        user=user,
                        delay_ms=delay,
                    )
                )
            elif r.event_type == EventType.DIRECTORY_CHANGE:
                frames.append(
                    ReplayFrame(
                        timestamp=r.timestamp,
                        event_type=r.event_type,
                        command=f"cd {payload.get('cwd') or payload.get('path') or ''}",
                        cwd=payload.get("cwd"),
                        user=user,
                        delay_ms=delay,
                    )
                )
            elif r.event_type in (EventType.FILE_READ, EventType.FILE_WRITE, EventType.FILE_DELETE):
                frames.append(
                    ReplayFrame(
                        timestamp=r.timestamp,
                        event_type=r.event_type,
                        output=f"[{r.event_type}] {payload.get('filename') or payload.get('path')}",
                        user=user,
                        delay_ms=delay,
                    )
                )
            elif r.event_type == EventType.SQL_QUERY:
                frames.append(
                    ReplayFrame(
                        timestamp=r.timestamp,
                        event_type=r.event_type,
                        command=str(payload.get("query") or "")[:200],
                        output="",
                        user=user,
                        delay_ms=delay,
                    )
                )
            elif r.event_type == EventType.HTTP_REQUEST:
                frames.append(
                    ReplayFrame(
                        timestamp=r.timestamp,
                        event_type=r.event_type,
                        output=(
                            f"{payload.get('method', 'GET')} "
                            f"{payload.get('url') or payload.get('path')} "
                            f"→ {payload.get('status') or payload.get('response_code') or ''}"
                        ),
                        user=user,
                        delay_ms=delay,
                    )
                )

        return ReplayResponse(session=session_to_out(session, event_count=len(rows)), frames=frames)

    @staticmethod
    async def files_for_session(db: AsyncSession, session_id: UUID) -> list[FileAccessOut]:
        rows = (
            await db.scalars(
                select(FileAccessRecord)
                .where(FileAccessRecord.session_id == session_id)
                .order_by(FileAccessRecord.time.asc())
            )
        ).all()
        return [FileAccessOut.model_validate(r) for r in rows]

    @staticmethod
    async def commands_for_session(db: AsyncSession, session_id: UUID) -> list[CommandOut]:
        rows = (
            await db.scalars(
                select(CommandRecord)
                .where(CommandRecord.session_id == session_id)
                .order_by(CommandRecord.timestamp.asc())
            )
        ).all()
        return [CommandOut.model_validate(r) for r in rows]
