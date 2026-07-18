-- Phase 3 event flight-recorder schema
-- Also created/migrated by SQLAlchemy on API startup

CREATE TABLE IF NOT EXISTS sessions (
    id UUID PRIMARY KEY,
    start_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    end_time TIMESTAMPTZ,
    source_ip VARCHAR(64),
    service VARCHAR(32) NOT NULL DEFAULT 'ssh',
    country VARCHAR(64),
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    username VARCHAR(128),
    user_agent TEXT,
    end_reason VARCHAR(128),
    meta JSONB DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS events (
    id BIGSERIAL PRIMARY KEY,
    event_id VARCHAR(64) NOT NULL UNIQUE,
    session_id UUID REFERENCES sessions(id) ON DELETE SET NULL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    service VARCHAR(32) NOT NULL,
    event_type VARCHAR(64) NOT NULL,
    payload JSONB DEFAULT '{}'::jsonb,
    ip VARCHAR(64),
    -- legacy mirrors
    event VARCHAR(128),
    details JSONB DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS files_accessed (
    id BIGSERIAL PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    action VARCHAR(32) NOT NULL,
    time TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS commands (
    id BIGSERIAL PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    command TEXT NOT NULL,
    cwd TEXT,
    output TEXT,
    exit_code INTEGER,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_events_service ON events (service);
CREATE INDEX IF NOT EXISTS idx_events_session ON events (session_id);
CREATE INDEX IF NOT EXISTS idx_events_type ON events (event_type);
CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions (status);
CREATE INDEX IF NOT EXISTS idx_sessions_start ON sessions (start_time DESC);
CREATE INDEX IF NOT EXISTS idx_commands_session ON commands (session_id);
CREATE INDEX IF NOT EXISTS idx_files_session ON files_accessed (session_id);
