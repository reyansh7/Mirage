# Phase 3 — Event Collection & Session Engine

Flight recorder for every attacker session. **Observe only** — no AI, LangGraph, MITRE, or behavior analysis.

## Architecture

```
Attacker
    │
    ▼
SSH / HTTP / MySQL
    │
    ▼
Command / Event Parser
    │
    ▼
EventLogger  ──► Postgres (sessions, events, commands, files_accessed)
    │
    └──► WebSocket /ws/events ──► Operator Dashboard
```

## What you get

| Capability | Endpoint / UI |
|------------|----------------|
| Create session | `POST /session` |
| End session | `POST /sessions/{id}/end` |
| List sessions | `GET /sessions` |
| Ingest event | `POST /events` |
| List events | `GET /events` |
| Timeline | `GET /sessions/{id}/timeline` |
| Replay frames | `GET /sessions/{id}/replay` |
| Live stream | `WS /ws/events` |
| Dashboard | http://127.0.0.1:8001/ |

## Event types (enums)

`COMMAND` · `LOGIN` · `LOGOUT` · `FILE_READ` · `FILE_WRITE` · `FILE_DELETE` · `DIRECTORY_CHANGE` · `HTTP_REQUEST` · `SQL_QUERY` · `NETWORK_SCAN` · `AUTH_FAILURE` · `AUTH_SUCCESS` · `CONNECT` · `SESSION_START` · `SESSION_END`

Every event is JSON:

```json
{
  "event_id": "evt_a1b2c3d4e5f6",
  "session_id": "…",
  "timestamp": "2026-07-20T14:35:10Z",
  "service": "ssh",
  "event_type": "COMMAND",
  "payload": {
    "command": "ls -la",
    "cwd": "/home/developer",
    "user": "developer",
    "output": "…",
    "exit_code": 0
  }
}
```

## Code layout

```
backend/app/
  events/
    types.py        # EventType enums
    logger.py       # EventLogger.log(session_id, event_type, payload)
    schemas.py
    websocket.py    # live fan-out
  sessions/
    manager.py      # create / end
    service.py      # list / timeline / replay
  database/
    connection.py   # Postgres (Supabase-compatible schema)
frontend/           # operator dashboard
```

## Session lifecycle

1. Attacker connects → `SessionManager.create` → UUID, `status=active`
2. Actions → `EventLogger.log` → `events` + side tables (`commands`, `files_accessed`) + WebSocket broadcast
3. Disconnect / logout → `SessionManager.end` → `end_time`, `duration`, `reason`

SSH world sessions reuse the **same UUID** as the DB session so commands, files, and replay stay linked.

## Dashboard tour

1. Open http://127.0.0.1:8001/
2. SSH in: `ssh -p 2222 developer@127.0.0.1` (`Welcome1!`)
3. Run `pwd`, `ls`, `cd Finance`, `cat …`
4. Watch the live stream update without refresh
5. Click the session → Timeline / Replay

## Storage note

Phase 3 uses the existing Docker **Postgres** event store with the same table shapes called out for Supabase (`sessions`, `events`, `files_accessed`, `commands`). Swap the connection URL later if you move to hosted Supabase — no AI layer required.

## Explicitly out of scope

- LangGraph / Gemini / GPT / RAG
- MITRE mapping
- Behavior / risk scoring (Risk column in the UI is deferred)
