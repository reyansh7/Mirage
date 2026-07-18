from __future__ import annotations

from app.world.formatter import CommandResult
from app.world.loader import get_world
from app.world.parser import ParsedCommand
from app.world.session import SessionState


def handle_system(session: SessionState, parsed: ParsedCommand) -> CommandResult:
    name = parsed.name
    world = get_world()

    if name == "whoami":
        return CommandResult(stdout=session.user)

    if name == "hostname":
        return CommandResult(stdout=world.users.get("hostname", "build-server-01"))

    if name == "uname":
        if "-a" in parsed.flags or parsed.flags == ["-a"]:
            return CommandResult(
                stdout=(
                    f"Linux {world.users.get('hostname')} "
                    f"{world.users.get('kernel')} #1 SMP "
                    f"{world.users.get('os')} {world.users.get('arch')} GNU/Linux"
                )
            )
        return CommandResult(stdout="Linux")

    if name == "id":
        rec = world.user_record(session.user)
        if not rec:
            return CommandResult(stdout=f"uid=1000({session.user}) gid=1000({session.user}) groups=1000({session.user})")
        groups = ",".join(f"{1000+i}({g})" for i, g in enumerate(rec.get("groups", [session.user])))
        return CommandResult(
            stdout=f"uid={rec['uid']}({rec['username']}) gid={rec['gid']}({rec['username']}) groups={groups}"
        )

    if name == "history":
        lines = [f"  {i}  {cmd}" for i, cmd in enumerate(session.history, 1)]
        return CommandResult(stdout="\n".join(lines))

    if name == "clear":
        return CommandResult(clear=True)

    if name in ("exit", "logout", "quit"):
        return CommandResult(stdout="logout", exit_session=True)

    if name == "help":
        return CommandResult(
            stdout=(
                "Available commands:\n"
                "  ls pwd cd cat touch mkdir rm find grep\n"
                "  whoami hostname uname id ps top systemctl\n"
                "  ip addr history clear help exit"
            )
        )

    if name == "ps":
        rows = ["  PID USER       CMD"]
        for p in world.services.get("processes", []):
            rows.append(f"{p['pid']:>5} {p['user']:<10} {p['cmd']}")
        return CommandResult(stdout="\n".join(rows))

    if name == "top":
        rows = [
            f"top - {world.users.get('hostname')} — load average: 0.12, 0.18, 0.09",
            "Tasks: 8 total",
            "  PID USER      %CPU %MEM COMMAND",
        ]
        for p in world.services.get("processes", [])[:8]:
            rows.append(f"{p['pid']:>5} {p['user']:<8}  0.3  1.2 {p['cmd'].split()[0]}")
        rows.append("\n(Press q to quit — static snapshot)")
        return CommandResult(stdout="\n".join(rows))

    if name == "ip":
        return _ip(parsed)

    if name == "ifconfig":
        return _ip(ParsedCommand(raw="ip addr", name="ip", args=["addr"], flags=[]))

    return CommandResult(stderr=f"{name}: command not found", exit_code=127)


def _ip(parsed: ParsedCommand) -> CommandResult:
    world = get_world()
    if not parsed.args or parsed.args[0] in ("addr", "a", "address"):
        blocks = []
        for i, iface in enumerate(world.network.get("interfaces", []), 1):
            lines = [f"{i}: {iface['name']}: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500"]
            if iface["name"] == "lo":
                lines = [f"{i}: {iface['name']}: <LOOPBACK,UP,LOWER_UP> mtu 65536"]
            if "mac" in iface:
                lines.append(f"    link/ether {iface['mac']} brd ff:ff:ff:ff:ff:ff")
            else:
                lines.append("    link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00")
            for addr in iface.get("addrs", []):
                if ":" in addr and not addr.startswith("127"):
                    # crude ipv6 skip display unless ::1
                    if addr.startswith("::"):
                        lines.append(f"    inet6 {addr} scope host")
                    else:
                        lines.append(f"    inet6 {addr} scope global")
                else:
                    lines.append(f"    inet {addr} scope {'host' if iface['name']=='lo' else 'global'} {iface['name']}")
            blocks.append("\n".join(lines))
        return CommandResult(stdout="\n".join(blocks))
    if parsed.args[0] == "route":
        return CommandResult(stdout="\n".join(world.network.get("routes", [])))
    return CommandResult(stderr="Usage: ip addr | ip route", exit_code=1)
