from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CommandResult:
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    clear: bool = False
    exit_session: bool = False
    # Side-channel for the flight recorder (FILE_READ / WRITE / DELETE)
    file_events: list[dict[str, Any]] = field(default_factory=list)

    def render(self) -> str:
        if self.clear:
            return "\033[2J\033[H"
        parts = []
        if self.stdout:
            parts.append(self.stdout.rstrip("\n"))
        if self.stderr:
            parts.append(self.stderr.rstrip("\n"))
        return "\n".join(parts)

    def add_file(self, event_type: str, path: str, action: str | None = None) -> None:
        self.file_events.append(
            {"type": event_type, "path": path, "action": action or event_type.lower()}
        )
