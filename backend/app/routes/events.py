from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, WebSocket
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import get_db
from app.events.logger import EventLogger, event_to_out
from app.events.schemas import EventCreate, EventListResponse, EventOut
from app.events.types import normalize_event_type
from app.events.websocket import websocket_endpoint
from app.sessions.service import SessionService

router = APIRouter(tags=["events"])


@router.post("/events", response_model=EventOut, status_code=201)
async def create_event(payload: EventCreate, db: AsyncSession = Depends(get_db)):
    body = payload.resolved_payload()
    et = normalize_event_type(payload.resolved_event_type(), body)
    # HTTP method into payload if legacy "HTTP GET"
    if et.value == "HTTP_REQUEST" and "method" not in body:
        raw = (payload.event or payload.event_type or "").upper()
        if raw.startswith("HTTP "):
            body = {**body, "method": raw.split(" ", 1)[1]}

    out = await EventLogger.log(
        payload.resolved_session_id(),
        et,
        body,
        service=payload.service,
        ip=payload.ip,
        timestamp=payload.timestamp,
        db=db,
    )
    return out


@router.get("/events", response_model=EventListResponse)
async def list_events(
    session_id: Optional[UUID] = None,
    event_type: Optional[str] = None,
    service: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    items, total = await SessionService.list_events(
        db,
        session_id=session_id,
        event_type=event_type,
        service=service,
        limit=limit,
        offset=offset,
    )
    return EventListResponse(items=items, total=total)


@router.get("/events/{event_id}", response_model=EventOut)
async def get_event(event_id: str, db: AsyncSession = Depends(get_db)):
    from sqlalchemy import select
    from app.database.connection import EventRecord
    from fastapi import HTTPException

    # allow evt_xxx or numeric id
    q = select(EventRecord)
    if event_id.isdigit():
        q = q.where(EventRecord.id == int(event_id))
    else:
        q = q.where(EventRecord.event_id == event_id)
    record = await db.scalar(q)
    if not record:
        raise HTTPException(status_code=404, detail="event not found")
    return event_to_out(record)


@router.websocket("/ws/events")
async def ws_events(websocket: WebSocket):
    await websocket_endpoint(websocket)
