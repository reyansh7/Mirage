from __future__ import annotations

from app.world.formatter import CommandResult
from app.world.handlers import database, filesystem, service, system
from app.world.loader import get_world
from app.world.parser import ParsedCommand, parse_command
from app.world.permissions import check_permission
from app.world.session import SessionState, create_session

FILESYSTEM_CMDS = {"ls", "pwd", "cd", "cat", "touch", "mkdir", "rm", "find", "grep"}
SYSTEM_CMDS = {
    "whoami",
    "hostname",
    "uname",
    "id",
    "ps",
    "top",
    "history",
    "clear",
    "exit",
    "logout",
    "quit",
    "help",
    "ip",
    "ifconfig",
}
SERVICE_CMDS = {"systemctl"}
DATABASE_CMDS = {"mysql", "mariadb"}


class CommandEngine:
    """
    Input Command → Parser → Permission Checker → Handler → Formatter

    Handlers are swappable later for AI-driven responses (Phase 5+).
    """

    def __init__(self) -> None:
        self.world = get_world()

    def bootstrap(
        self, user: str | None = None, session_id: str | None = None
    ) -> tuple[SessionState, str]:
        session = create_session(user, session_id=session_id)
        return session, self.login_banner(session)

    def login_banner(self, session: SessionState) -> str:
        company = self.world.company
        os_name = self.world.users.get("os", "Ubuntu 24.04 LTS")
        lines = [
            f"{company.get('name', 'Acme Technologies')}",
            f"{os_name}",
            "",
            *company.get("banner", []),
            "",
            "Last login: Fri Jul 18 08:01:12 2026 from 10.0.5.99",
        ]
        return "\n".join(lines)

    def prompt(self, session: SessionState) -> str:
        host = self.world.users.get("hostname", "build-server-01")
        cwd = session.cwd
        home = "/root" if session.user == "root" else f"/home/{session.user}"
        rec = self.world.user_record(session.user)
        if rec:
            home = rec.get("home", home)
        display = "~" if cwd == home else cwd
        return f"{session.user}@{host}:{display}$ "

    def execute(self, session: SessionState, raw: str) -> CommandResult:
        text = raw.strip()
        if not text:
            return CommandResult()

        if ";" in text and not (text.startswith("mysql") and "-e" in text):
            outputs: list[str] = []
            file_events: list = []
            final = CommandResult()
            for part in text.split(";"):
                part = part.strip()
                if not part:
                    continue
                result = self._execute_one(session, part)
                rendered = result.render()
                if rendered:
                    outputs.append(rendered)
                file_events.extend(result.file_events)
                final = result
                if result.exit_session:
                    break
            merged = CommandResult(
                stdout="\n".join(outputs),
                exit_code=final.exit_code,
                exit_session=final.exit_session,
                clear=final.clear,
                file_events=file_events,
            )
            return merged

        return self._execute_one(session, text)

    def _execute_one(self, session: SessionState, raw: str) -> CommandResult:
        parsed = parse_command(raw)
        if parsed is None:
            return CommandResult()

        session.history.append(raw)

        denied = check_permission(session, parsed)
        if denied:
            return CommandResult(stderr=denied, exit_code=1)

        handler = self._route(parsed)
        if handler is None:
            return CommandResult(stderr=f"{parsed.name}: command not found", exit_code=127)
        return handler(session, parsed)

    def _route(self, parsed: ParsedCommand):
        name = parsed.name
        if name in FILESYSTEM_CMDS:
            return filesystem.handle_filesystem
        if name in SYSTEM_CMDS:
            return system.handle_system
        if name in SERVICE_CMDS:
            return service.handle_service
        if name in DATABASE_CMDS:
            return database.handle_database
        return None


_ENGINE: CommandEngine | None = None


def get_engine() -> CommandEngine:
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = CommandEngine()
    return _ENGINE
