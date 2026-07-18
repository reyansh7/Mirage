from __future__ import annotations

from app.world.formatter import CommandResult
from app.world.loader import get_world
from app.world.parser import ParsedCommand
from app.world.session import SessionState


def handle_database(session: SessionState, parsed: ParsedCommand) -> CommandResult:
    """Lightweight fake mysql client for SSH sessions."""
    if parsed.name not in ("mysql", "mariadb"):
        return CommandResult(stderr=f"{parsed.name}: command not found", exit_code=127)

    db = get_world().database
    # If -e QUERY provided, run static query
    query = None
    if "-e" in parsed.args:
        idx = parsed.args.index("-e")
        if idx + 1 < len(parsed.args):
            query = parsed.args[idx + 1]
    # Also accept trailing SQL-ish args
    if query is None and parsed.args:
        joined = " ".join(a for a in parsed.args if not a.startswith("-") and a not in ("corporate", "admin"))
        if "select" in joined.lower() or "show" in joined.lower():
            query = joined

    if not query:
        return CommandResult(
            stdout=(
                "Welcome to the MySQL monitor. Commands end with ; or \\g.\n"
                "Your MySQL connection id is 88\n"
                "Server version: 8.0.39 MySQL Community Server - GPL\n\n"
                "Type 'help;' or '\\h' for help.\n\n"
                "mysql> (non-interactive: use mysql -e \"SELECT ...\")"
            )
        )

    result = CommandResult(stdout=_run_query(query, db))
    # Annotate for command route → SQL_QUERY event
    result.file_events.append(
        {
            "type": "SQL_QUERY",
            "path": "",
            "action": "query",
            "query": query,
            "database": "corporate",
        }
    )
    return result


def _run_query(query: str, db: dict) -> str:
    q = " ".join(query.lower().split())
    if "show tables" in q:
        return "+-------------+\n| Tables_in_corporate |\n+-------------+\n| employees   |\n| departments |\n| projects    |\n| servers     |\n+-------------+"
    if "from employees" in q or q.strip() in ("select * from employees", "select * from employees;"):
        return _table(
            ["id", "name", "department", "title"],
            [[e["id"], e["name"], e["department"], e["title"]] for e in db["employees"]],
        )
    if "from departments" in q:
        return _table(
            ["id", "name", "head", "budget"],
            [[d["id"], d["name"], d["head"], d["budget"]] for d in db["departments"]],
        )
    if "from projects" in q:
        return _table(
            ["id", "name", "status", "owner"],
            [[p["id"], p["name"], p["status"], p["owner"]] for p in db["projects"]],
        )
    if "from servers" in q:
        return _table(
            ["id", "hostname", "ip", "role", "env"],
            [[s["id"], s["hostname"], s["ip"], s["role"], s["env"]] for s in db["servers"]],
        )
    return "ERROR 1064 (42000): You have an error in your SQL syntax (static honeypot)"


def _table(headers: list, rows: list[list]) -> str:
    cols = list(zip(*([headers] + [[str(c) for c in r] for r in rows]))) if rows else [[h] for h in headers]
    widths = [max(len(str(x)) for x in col) for col in cols]
    def fmt(row):
        return "| " + " | ".join(str(c).ljust(w) for c, w in zip(row, widths)) + " |"
    sep = "+" + "+".join("-" * (w + 2) for w in widths) + "+"
    lines = [sep, fmt(headers), sep]
    for r in rows:
        lines.append(fmt(r))
    lines.append(sep)
    return "\n".join(lines)
