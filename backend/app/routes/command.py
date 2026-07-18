from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.events.logger import EventLogger
from app.events.schemas import SessionCreate
from app.events.types import EventType, ServiceName
from app.sessions.manager import SessionManager
from app.world.engine import get_engine
from app.world.session import get_session

router = APIRouter(tags=["world"])


class BootstrapRequest(BaseModel):
    user: str = "developer"
    source_ip: Optional[str] = None
    session_id: Optional[str] = None  # optional pre-created DB session


class BootstrapResponse(BaseModel):
    session_id: str
    user: str
    cwd: str
    banner: str
    prompt: str


class CommandRequest(BaseModel):
    session_id: str
    command: str
    user: Optional[str] = None


class CommandResponse(BaseModel):
    session_id: str
    output: str
    prompt: str
    cwd: str
    exit_code: int
    exit_session: bool = False


class WorldInfoResponse(BaseModel):
    company: dict[str, Any]
    hostname: str
    users: list[str]


@router.post("/world/session", response_model=BootstrapResponse)
async def bootstrap_world_session(payload: BootstrapRequest):
    engine = get_engine()
    # Align in-memory world session UUID with persistent flight-recorder session
    db_session = await SessionManager.create(
        SessionCreate(
            id=UUID(payload.session_id) if payload.session_id else None,
            source_ip=payload.source_ip,
            service=ServiceName.SSH.value,
            username=payload.user,
            meta={"world_user": payload.user},
        ),
        emit_event=True,
    )
    session, banner = engine.bootstrap(payload.user, session_id=str(db_session.id))
    await EventLogger.log(
        db_session.id,
        EventType.LOGIN,
        {"user": session.user, "cwd": session.cwd},
        service=ServiceName.SSH.value,
        ip=payload.source_ip,
    )
    await EventLogger.log(
        db_session.id,
        EventType.AUTH_SUCCESS,
        {"user": session.user, "method": "password"},
        service=ServiceName.SSH.value,
        ip=payload.source_ip,
    )
    return BootstrapResponse(
        session_id=session.id,
        user=session.user,
        cwd=session.cwd,
        banner=banner,
        prompt=engine.prompt(session),
    )


@router.post("/command", response_model=CommandResponse)
async def run_command(payload: CommandRequest):
    engine = get_engine()
    session = get_session(payload.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found; bootstrap again")

    cwd_before = session.cwd
    result = engine.execute(session, payload.command)
    output = result.render()
    prompt = engine.prompt(session)

    # Structured command event (flight recorder)
    await EventLogger.log(
        session.id,
        EventType.COMMAND,
        {
            "command": payload.command,
            "cwd": cwd_before,
            "user": session.user,
            "output": output[:8000] if output else "",
            "exit_code": result.exit_code,
            "prompt": prompt,
        },
        service=ServiceName.SSH.value,
    )

    # Directory change
    if session.cwd != cwd_before:
        await EventLogger.log(
            session.id,
            EventType.DIRECTORY_CHANGE,
            {"cwd": session.cwd, "from": cwd_before, "user": session.user},
            service=ServiceName.SSH.value,
        )

    # File / SQL side effects from handlers
    for file_evt in getattr(result, "file_events", []) or []:
        etype = file_evt.get("type")
        if etype == "SQL_QUERY" or etype == EventType.SQL_QUERY.value:
            await EventLogger.log(
                session.id,
                EventType.SQL_QUERY,
                {
                    "query": file_evt.get("query"),
                    "database": file_evt.get("database", "corporate"),
                    "user": session.user,
                },
                service=ServiceName.SSH.value,
            )
        else:
            await EventLogger.log(
                session.id,
                etype,
                {
                    "filename": file_evt.get("path"),
                    "path": file_evt.get("path"),
                    "user": session.user,
                    "action": file_evt.get("action"),
                },
                service=ServiceName.SSH.value,
            )

    if result.exit_session:
        await SessionManager.end(session.id, reason="logout")

    return CommandResponse(
        session_id=session.id,
        output=output,
        prompt=prompt,
        cwd=session.cwd,
        exit_code=result.exit_code,
        exit_session=result.exit_session,
    )


@router.get("/world/info", response_model=WorldInfoResponse)
async def world_info():
    world = get_engine().world
    return WorldInfoResponse(
        company=world.company,
        hostname=world.users.get("hostname", "build-server-01"),
        users=world.known_usernames(),
    )
