from __future__ import annotations

import fnmatch
import re

from app.events.types import EventType
from app.world.formatter import CommandResult
from app.world.fs import (
    exists,
    get_node,
    is_dir,
    is_file,
    list_children,
    parent_dir,
    read_file,
    resolve_path,
)
from app.world.loader import get_world
from app.world.parser import ParsedCommand
from app.world.session import SessionState


def handle_filesystem(session: SessionState, parsed: ParsedCommand) -> CommandResult:
    name = parsed.name
    if name == "ls":
        return _ls(session, parsed)
    if name == "pwd":
        return CommandResult(stdout=session.cwd)
    if name == "cd":
        return _cd(session, parsed)
    if name == "cat":
        return _cat(session, parsed)
    if name == "touch":
        return _touch(session, parsed)
    if name == "mkdir":
        return _mkdir(session, parsed)
    if name == "rm":
        return _rm(session, parsed)
    if name == "find":
        return _find(session, parsed)
    if name == "grep":
        return _grep(session, parsed)
    return CommandResult(stderr=f"{name}: handler missing", exit_code=127)


def _ls(session: SessionState, parsed: ParsedCommand) -> CommandResult:
    target = resolve_path(session, parsed.args[0] if parsed.args else None)
    long_fmt = any(f in ("-l", "-la", "-al", "-lah") or "l" in f.strip("-") for f in parsed.flags)
    show_all = any(f in ("-a", "-la", "-al", "-lah") or "a" in f.strip("-") for f in parsed.flags)

    if not exists(session, target):
        return CommandResult(stderr=f"ls: cannot access '{parsed.args[0] if parsed.args else target}': No such file or directory", exit_code=2)
    if is_file(session, target):
        return CommandResult(stdout=target.rsplit("/", 1)[-1])

    names = list_children(session, target)
    if show_all:
        names = [".", ".."] + names
    if not long_fmt:
        return CommandResult(stdout="  ".join(names) if names else "")

    lines = []
    for n in names:
        if n in (".", ".."):
            lines.append(f"drwxr-xr-x 2 {session.user} {session.user} 4096 Jul 18 12:00 {n}")
            continue
        path = get_world().norm(target.rstrip("/") + "/" + n) if target != "/" else "/" + n
        node = get_node(session, path) or {}
        owner = node.get("owner", "root")
        mode = node.get("mode", "755")
        kind = "d" if node.get("type") == "dir" else "-"
        perm = _mode_to_perm(kind, mode)
        size = len(node.get("content", "")) if node.get("type") == "file" else 4096
        lines.append(f"{perm} 1 {owner} {owner} {size:>6} Jul 18 12:00 {n}")
    return CommandResult(stdout="\n".join(lines))


def _mode_to_perm(kind: str, mode: str) -> str:
    try:
        m = int(str(mode)[-3:], 8)
    except ValueError:
        m = 0o755
    chars = []
    for shift in (6, 3, 0):
        triad = (m >> shift) & 0o7
        chars.append("r" if triad & 4 else "-")
        chars.append("w" if triad & 2 else "-")
        chars.append("x" if triad & 1 else "-")
    return kind + "".join(chars)


def _cd(session: SessionState, parsed: ParsedCommand) -> CommandResult:
    target = resolve_path(session, parsed.args[0] if parsed.args else "~")
    if not exists(session, target):
        return CommandResult(stderr=f"bash: cd: {parsed.args[0]}: No such file or directory", exit_code=1)
    if not is_dir(session, target):
        return CommandResult(stderr=f"bash: cd: {parsed.args[0]}: Not a directory", exit_code=1)
    session.cwd = target
    return CommandResult()


def _cat(session: SessionState, parsed: ParsedCommand) -> CommandResult:
    if not parsed.args:
        return CommandResult(stderr="cat: missing operand", exit_code=1)
    chunks = []
    result = CommandResult()
    for arg in parsed.args:
        path = resolve_path(session, arg)
        if not exists(session, path):
            return CommandResult(stderr=f"cat: {arg}: No such file or directory", exit_code=1)
        if is_dir(session, path):
            return CommandResult(stderr=f"cat: {arg}: Is a directory", exit_code=1)
        content = read_file(session, path)
        chunks.append(content if content is not None else "")
        result.add_file(EventType.FILE_READ.value, path, action="read")
    result.stdout = "".join(chunks).rstrip("\n")
    return result


def _touch(session: SessionState, parsed: ParsedCommand) -> CommandResult:
    if not parsed.args:
        return CommandResult(stderr="touch: missing file operand", exit_code=1)
    result = CommandResult()
    for arg in parsed.args:
        path = resolve_path(session, arg)
        if exists(session, path):
            result.add_file(EventType.FILE_WRITE.value, path, action="modify")
            continue
        parent = parent_dir(path)
        if not is_dir(session, parent):
            return CommandResult(stderr=f"touch: cannot touch '{arg}': No such file or directory", exit_code=1)
        session.deleted.discard(path)
        session.overlay[path] = {
            "type": "file",
            "owner": session.user,
            "mode": "644",
            "content": "",
        }
        result.add_file(EventType.FILE_WRITE.value, path, action="create")
    return result


def _mkdir(session: SessionState, parsed: ParsedCommand) -> CommandResult:
    if not parsed.args:
        return CommandResult(stderr="mkdir: missing operand", exit_code=1)
    result = CommandResult()
    for arg in parsed.args:
        path = resolve_path(session, arg)
        if exists(session, path):
            return CommandResult(stderr=f"mkdir: cannot create directory '{arg}': File exists", exit_code=1)
        parent = parent_dir(path)
        if not is_dir(session, parent):
            return CommandResult(stderr=f"mkdir: cannot create directory '{arg}': No such file or directory", exit_code=1)
        session.deleted.discard(path)
        session.overlay[path] = {"type": "dir", "owner": session.user, "mode": "755"}
        result.add_file(EventType.FILE_WRITE.value, path, action="create")
    return result


def _rm(session: SessionState, parsed: ParsedCommand) -> CommandResult:
    recursive = any(f in ("-r", "-rf", "-fr") or "r" in f.strip("-") for f in parsed.flags)
    if not parsed.args:
        return CommandResult(stderr="rm: missing operand", exit_code=1)
    result = CommandResult()
    for arg in parsed.args:
        path = resolve_path(session, arg)
        if not exists(session, path):
            return CommandResult(stderr=f"rm: cannot remove '{arg}': No such file or directory", exit_code=1)
        if is_dir(session, path) and not recursive:
            return CommandResult(stderr=f"rm: cannot remove '{arg}': Is a directory", exit_code=1)
        session.overlay.pop(path, None)
        session.deleted.add(path)
        result.add_file(EventType.FILE_DELETE.value, path, action="delete")
        if recursive and is_dir(session, path):
            prefix = path.rstrip("/") + "/"
            for p in list(session.overlay):
                if p.startswith(prefix):
                    session.overlay.pop(p, None)
                    session.deleted.add(p)
                    result.add_file(EventType.FILE_DELETE.value, p, action="delete")
            world = get_world()
            for p in world.filesystem:
                if p.startswith(prefix):
                    session.deleted.add(p)
                    result.add_file(EventType.FILE_DELETE.value, p, action="delete")
    return result


def _find(session: SessionState, parsed: ParsedCommand) -> CommandResult:
    start = resolve_path(session, parsed.args[0] if parsed.args else ".")
    name_pat = None
    if "-name" in parsed.args:
        idx = parsed.args.index("-name")
        if idx + 1 < len(parsed.args):
            name_pat = parsed.args[idx + 1]
    if not exists(session, start):
        return CommandResult(stderr=f"find: '{parsed.args[0] if parsed.args else start}': No such file or directory", exit_code=1)

    world = get_world()
    start = world.norm(start)
    matches = []
    for path in sorted(session.overlay.keys() | set(get_world().filesystem.keys())):
        if path in session.deleted:
            continue
        if path == start or path.startswith(start.rstrip("/") + "/") or start == "/":
            if start != "/" and not (path == start or path.startswith(start.rstrip("/") + "/")):
                continue
            base = path.rsplit("/", 1)[-1] or "/"
            if name_pat and not fnmatch.fnmatch(base, name_pat):
                continue
            matches.append(path)
    if start != "/" and start not in matches and exists(session, start):
        matches.insert(0, start)
    # Deduplicate preserve order
    seen = set()
    out = []
    for m in matches:
        if m not in seen:
            seen.add(m)
            out.append(m)
    return CommandResult(stdout="\n".join(out))


def _grep(session: SessionState, parsed: ParsedCommand) -> CommandResult:
    if len(parsed.args) < 2:
        return CommandResult(stderr="Usage: grep PATTERN FILE", exit_code=2)
    pattern, *files = parsed.args
    try:
        regex = re.compile(pattern)
    except re.error:
        regex = re.compile(re.escape(pattern))
    lines_out = []
    result = CommandResult()
    for f in files:
        path = resolve_path(session, f)
        if not exists(session, path):
            return CommandResult(stderr=f"grep: {f}: No such file or directory", exit_code=2)
        if is_dir(session, path):
            return CommandResult(stderr=f"grep: {f}: Is a directory", exit_code=2)
        content = read_file(session, path) or ""
        result.add_file(EventType.FILE_READ.value, path, action="read")
        for i, line in enumerate(content.splitlines(), 1):
            if regex.search(line):
                lines_out.append(f"{f}:{line}" if len(files) > 1 else line)
    result.stdout = "\n".join(lines_out)
    result.exit_code = 0 if lines_out else 1
    return result
