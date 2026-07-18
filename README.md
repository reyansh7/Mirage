# Mirage

An AI-powered adaptive cyber deception platform that creates realistic enterprise environments to detect, analyze, and mislead attackers while providing real-time behavioral intelligence and threat analytics.

**Current build (Phases 1–3):** Dockerized honeynet with a static fake world (Acme Technologies) and a session / event flight recorder. AI / LangGraph / RAG are not enabled yet.

## Architecture

```
Attacker → SSH :2222 → fake_shell → POST /command → Command Engine → EventLogger
        → Web  :8080 → Acme Employee Portal     → EventLogger
        → MySQL:3307 → corporate DB             → EventLogger
        → API  :8001 → logging + world engine + live dashboard
                         ├─ Postgres (sessions / events / commands / files)
                         └─ WebSocket → operator UI
```

| Service | Presented as | Host port | Creds |
|---------|--------------|-----------|-------|
| SSH | `build-server-01` | 2222 | `developer` / `Welcome1!` |
| Web | Acme Employee Portal | 8080 | `admin` / `admin123` |
| MySQL | corporate | 3307 | `admin` / `admin123` |
| API + Dashboard | flight recorder | 8001 | — |

Also SSH users: `admin`/`admin123`, `jenkins`, `backup`, `finance`, `intern`

## Quick start

```bash
cd docker
docker compose up --build -d
# If MySQL or Postgres schema is stale from an older phase:
# docker compose down
# docker volume rm docker_mysql_data docker_postgres_data
# docker compose up --build -d
```

```bash
curl -s http://127.0.0.1:8001/health | jq
curl -s http://127.0.0.1:8001/sessions | jq
# Operator dashboard
xdg-open http://127.0.0.1:8001/   # or open in browser
```

## Phase 3 — watch an attacker live

1. Open the dashboard: http://127.0.0.1:8001/
2. SSH in and poke around:

```bash
ssh -p 2222 developer@127.0.0.1
# Welcome1!
pwd
ls
cd /home/developer
cat notes.md
```

3. In the dashboard: new session appears → click it → commands / files stream in → **Timeline** or **Replay**.

## Phase 2 SSH tour

Commands are **not** executed on the real container — they hit the Command Engine (`backend/app/world/`).

Try: `whoami`, `hostname`, `ls /`, `ls /home`, `cd /home/developer`, `cat notes.md`, `systemctl status apache2`, `ip addr`, `mysql -e "SELECT * FROM employees"`

## Docs

- `docs/phase1.md` — infrastructure
- `docs/phase2.md` — fake world / command engine
- `docs/phase3.md` — event collection & session engine

## Smoke test

```bash
./scripts/smoke-test.sh
```
