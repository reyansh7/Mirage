from __future__ import annotations

from app.world.loader import get_world
from app.world.parser import ParsedCommand
from app.world.session import SessionState


# Paths considered sensitive — non-owner/non-admin get permission denied
SENSITIVE_PREFIXES = (
    "/home/finance",
    "/opt/acme/hr/salary.xlsx",
    "/root",
)


def check_permission(session: SessionState, parsed: ParsedCommand, target_path: str | None = None) -> str | None:
    """Return an error string if denied, else None."""
    user = session.user
    if user in ("root", "admin"):
        return None

    world = get_world()
    path = target_path
    if path is None and parsed.args:
        # best-effort: first positional arg that looks like a path
        for a in parsed.args:
            if a.startswith("/") or a in (".", "..") or "/" in a:
                path = a
                break

    if not path:
        return None

    # Resolve roughly against cwd later in handlers; here check absolute sensitive prefixes
    abs_guess = path if path.startswith("/") else f"{session.cwd.rstrip('/')}/{path}"
    abs_guess = world.norm(abs_guess)

    for prefix in SENSITIVE_PREFIXES:
        if abs_guess == prefix or abs_guess.startswith(prefix + "/"):
            if user == "finance" and abs_guess.startswith("/home/finance"):
                return None
            if prefix.startswith("/home/"):
                owner = prefix.split("/")[2]
                if user == owner:
                    return None
            return f"bash: {parsed.name}: Permission denied"
    return None
