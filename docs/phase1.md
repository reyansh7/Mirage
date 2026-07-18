# Phase 1 — Infrastructure

## Goal

Ship an isolated Docker honeynet with SSH, HTTP, MySQL, and a central FastAPI logging API. No AI.

## Network

- Name: `honeynet`
- Subnet: `172.28.0.0/16`
- Bridge driver, fixed IPv4 per service

## Services

1. **postgres** — event store
2. **backend** — `POST /events`, `POST /session`, `GET /health`
3. **ssh** — OpenSSH decoy (`fake-server`)
4. **web** — fake intranet (`/`, `/login`, `/admin`, `/dashboard`)
5. **mysql** — decoy DB user `admin`

## Logging contract

Every decoy posts:

| Field     | Description        |
|-----------|--------------------|
| timestamp | ISO-8601 UTC       |
| service   | ssh / http / mysql |
| ip        | source IP if known |
| session   | UUID from `/session` |
| event     | e.g. `SSH LOGIN`   |
| details   | free-form JSON     |

## Next phases (out of scope)

- Cowrie / richer SSH deception
- LangGraph / AI response adaptation
- RAG / attacker profiling UI
