"""Database connection + ORM models for the session/event flight recorder.

Uses local Postgres (Docker). Schema matches the Phase 3 Supabase-style design.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://honeypot:honeypot@127.0.0.1:5432/honeypot_events",
)

engine = create_async_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class SessionRecord(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    source_ip: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    service: Mapped[str] = mapped_column(String(32), nullable=False, default="ssh")
    country: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    username: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    end_reason: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    # Legacy alias for Phase 1/2 code that expected created_at
    @property
    def created_at(self) -> datetime:
        return self.start_time


class EventRecord(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    service: Mapped[str] = mapped_column(String(32), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    ip: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Legacy column kept for read compatibility during transition
    event: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class FileAccessRecord(Base):
    __tablename__ = "files_accessed"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CommandRecord(Base):
    __tablename__ = "commands"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    command: Mapped[str] = mapped_column(Text, nullable=False)
    cwd: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    output: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    exit_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


async def _migrate_schema(conn) -> None:
    """Best-effort upgrades for existing Phase 1/2 Postgres volumes."""
    statements = [
        "ALTER TABLE sessions ADD COLUMN IF NOT EXISTS start_time TIMESTAMPTZ",
        "ALTER TABLE sessions ADD COLUMN IF NOT EXISTS end_time TIMESTAMPTZ",
        "ALTER TABLE sessions ADD COLUMN IF NOT EXISTS service VARCHAR(32) DEFAULT 'ssh'",
        "ALTER TABLE sessions ADD COLUMN IF NOT EXISTS country VARCHAR(64)",
        "ALTER TABLE sessions ADD COLUMN IF NOT EXISTS status VARCHAR(32) DEFAULT 'active'",
        "ALTER TABLE sessions ADD COLUMN IF NOT EXISTS username VARCHAR(128)",
        "ALTER TABLE sessions ADD COLUMN IF NOT EXISTS end_reason VARCHAR(128)",
        """
        DO $$ BEGIN
          IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name='sessions' AND column_name='created_at'
          ) THEN
            UPDATE sessions SET start_time = COALESCE(start_time, created_at)
            WHERE start_time IS NULL;
          END IF;
        END $$;
        """,
        "UPDATE sessions SET start_time = NOW() WHERE start_time IS NULL",
        "UPDATE sessions SET status = 'active' WHERE status IS NULL",
        "UPDATE sessions SET service = COALESCE(service, meta->>'service', 'ssh') WHERE service IS NULL OR service = ''",
        "ALTER TABLE events ADD COLUMN IF NOT EXISTS event_id VARCHAR(64)",
        "ALTER TABLE events ADD COLUMN IF NOT EXISTS event_type VARCHAR(64)",
        "ALTER TABLE events ADD COLUMN IF NOT EXISTS payload JSONB DEFAULT '{}'::jsonb",
        """
        UPDATE events SET event_type = COALESCE(event_type, event, 'COMMAND')
        WHERE event_type IS NULL
        """,
        """
        UPDATE events SET payload = COALESCE(payload, details, '{}'::jsonb)
        WHERE payload IS NULL OR payload = '{}'::jsonb
        """,
        """
        UPDATE events SET event_id = 'evt_' || id::text
        WHERE event_id IS NULL OR event_id = ''
        """,
        """
        DO $$ BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'events_event_id_key'
          ) THEN
            BEGIN
              ALTER TABLE events ADD CONSTRAINT events_event_id_key UNIQUE (event_id);
            EXCEPTION WHEN others THEN NULL;
            END;
          END IF;
        END $$;
        """,
        """
        CREATE TABLE IF NOT EXISTS files_accessed (
            id BIGSERIAL PRIMARY KEY,
            session_id UUID REFERENCES sessions(id) ON DELETE CASCADE,
            filename TEXT NOT NULL,
            action VARCHAR(32) NOT NULL,
            time TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS commands (
            id BIGSERIAL PRIMARY KEY,
            session_id UUID REFERENCES sessions(id) ON DELETE CASCADE,
            command TEXT NOT NULL,
            cwd TEXT,
            output TEXT,
            exit_code INTEGER,
            timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events (timestamp DESC)",
        "CREATE INDEX IF NOT EXISTS idx_events_session ON events (session_id)",
        "CREATE INDEX IF NOT EXISTS idx_events_type ON events (event_type)",
        "CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions (status)",
        "CREATE INDEX IF NOT EXISTS idx_sessions_start ON sessions (start_time DESC)",
        "CREATE INDEX IF NOT EXISTS idx_commands_session ON commands (session_id)",
        "CREATE INDEX IF NOT EXISTS idx_files_session ON files_accessed (session_id)",
    ]
    for stmt in statements:
        await conn.execute(text(stmt))


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _migrate_schema(conn)


async def get_db():
    async with SessionLocal() as session:
        yield session
