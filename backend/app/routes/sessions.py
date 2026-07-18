from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import get_db
from app.events.schemas import (
    CommandOut,
    FileAccessOut,
    ReplayResponse,
    SessionCreate,
    SessionEnd,
    SessionListResponse,
    SessionOut,
    TimelineResponse,
)
from app.sessions.manager import SessionManager
from app.sessions.service import SessionService

router = APIRouter(tags=["sessions"])


@router.post("/session", response_model=SessionOut, status_code=201)
async def create_session(payload: SessionCreate, db: AsyncSession = Depends(get_db)):
    # Infer service from meta if callers still use Phase 1 shape
    if not payload.service and payload.meta.get("service"):
        payload.service = str(payload.meta["service"])
    return await SessionManager.create(payload, db=db)


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(
    status: Optional[str] = None,
    service: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    return await SessionService.list_sessions(
        db, status=status, service=service, limit=limit, offset=offset
    )


@router.get("/sessions/{session_id}", response_model=SessionOut)
async def get_session(session_id: UUID, db: AsyncSession = Depends(get_db)):
    out = await SessionManager.get(session_id, db=db)
    if not out:
        raise HTTPException(status_code=404, detail="session not found")
    return out


@router.post("/sessions/{session_id}/end", response_model=SessionOut)
async def end_session(
    session_id: UUID,
    payload: SessionEnd | None = None,
    db: AsyncSession = Depends(get_db),
):
    reason = (payload.reason if payload else "disconnect") or "disconnect"
    out = await SessionManager.end(session_id, reason=reason, db=db)
    if not out:
        raise HTTPException(status_code=404, detail="session not found")
    return out


@router.get("/sessions/{session_id}/timeline", response_model=TimelineResponse)
async def session_timeline(session_id: UUID, db: AsyncSession = Depends(get_db)):
    out = await SessionService.timeline(db, session_id)
    if not out:
        raise HTTPException(status_code=404, detail="session not found")
    return out


@router.get("/sessions/{session_id}/replay", response_model=ReplayResponse)
async def session_replay(session_id: UUID, db: AsyncSession = Depends(get_db)):
    out = await SessionService.replay(db, session_id)
    if not out:
        raise HTTPException(status_code=404, detail="session not found")
    return out


@router.get("/sessions/{session_id}/files", response_model=list[FileAccessOut])
async def session_files(session_id: UUID, db: AsyncSession = Depends(get_db)):
    return await SessionService.files_for_session(db, session_id)


@router.get("/sessions/{session_id}/commands", response_model=list[CommandOut])
async def session_commands(session_id: UUID, db: AsyncSession = Depends(get_db)):
    return await SessionService.commands_for_session(db, session_id)
