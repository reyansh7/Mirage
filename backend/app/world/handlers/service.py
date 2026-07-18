from __future__ import annotations

from app.world.formatter import CommandResult
from app.world.loader import get_world
from app.world.parser import ParsedCommand
from app.world.session import SessionState


def handle_service(session: SessionState, parsed: ParsedCommand) -> CommandResult:
    if parsed.name != "systemctl":
        return CommandResult(stderr=f"{parsed.name}: command not found", exit_code=127)

    if not parsed.args:
        return CommandResult(stderr="systemctl: missing command", exit_code=1)

    action = parsed.args[0]
    unit = parsed.args[1] if len(parsed.args) > 1 else ""
    unit = unit.removesuffix(".service")

    services = get_world().services.get("services", {})

    if action == "status":
        if not unit:
            return CommandResult(stderr="systemctl status: missing unit", exit_code=1)
        svc = services.get(unit)
        if not svc:
            return CommandResult(
                stderr=f"Unit {unit}.service could not be found.",
                exit_code=4,
            )
        active_line = f"     Active: {svc['active']} ({svc['sub']}) since {svc['since']}"
        out = (
            f"* {svc['unit']} - {svc['description']}\n"
            f"     Loaded: {svc['load']} (/lib/systemd/system/{svc['unit']}; enabled)\n"
            f"{active_line}\n"
            f"   Main PID: 1000 ({unit})\n"
            f"      Tasks: 4\n"
            f"     Memory: 42.0M\n"
        )
        return CommandResult(stdout=out.rstrip())

    if action in ("start", "stop", "restart", "enable", "disable"):
        if unit not in services and unit:
            return CommandResult(stderr=f"Failed to {action} {unit}.service: Unit not found.", exit_code=5)
        # Static world — pretend success
        return CommandResult()

    if action == "list-units":
        lines = ["UNIT                 LOAD   ACTIVE SUB     DESCRIPTION"]
        for svc in services.values():
            lines.append(
                f"{svc['unit']:<20} {svc['load']:<6} {svc['active']:<6} {svc['sub']:<7} {svc['description']}"
            )
        # Deduplicate by unit name
        seen = set()
        uniq = [lines[0]]
        for line in lines[1:]:
            key = line.split()[0]
            if key in seen:
                continue
            seen.add(key)
            uniq.append(line)
        return CommandResult(stdout="\n".join(uniq))

    return CommandResult(stderr=f"systemctl: Unknown operation '{action}'", exit_code=1)
