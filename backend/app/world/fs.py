from __future__ import annotations

from typing import Any

from app.world.loader import WorldData, get_world
from app.world.session import SessionState


def resolve_path(session: SessionState, path: str | None) -> str:
    world = get_world()
    if not path or path == ".":
        return world.norm(session.cwd)
    if path == "~":
        return _home(session)
    if path.startswith("~/"):
        return world.norm(_home(session) + "/" + path[2:])
    if path.startswith("/"):
        return world.norm(path)
    return world.norm(session.cwd.rstrip("/") + "/" + path)


def _home(session: SessionState) -> str:
    world = get_world()
    if session.user == "root":
        return "/root"
    rec = world.user_record(session.user)
    return rec["home"] if rec else f"/home/{session.user}"


def effective_nodes(session: SessionState) -> dict[str, dict[str, Any]]:
    world = get_world()
    nodes = dict(world.filesystem)
    for path in session.deleted:
        nodes.pop(path, None)
        # also drop children of deleted dirs
    nodes = {p: n for p, n in nodes.items() if p not in session.deleted and not any(p.startswith(d.rstrip("/") + "/") for d in session.deleted)}
    nodes.update(session.overlay)
    return nodes


def get_node(session: SessionState, path: str) -> dict[str, Any] | None:
    world = get_world()
    path = world.norm(path)
    nodes = effective_nodes(session)
    return nodes.get(path)


def exists(session: SessionState, path: str) -> bool:
    return get_node(session, path) is not None


def is_dir(session: SessionState, path: str) -> bool:
    node = get_node(session, path)
    return bool(node and node.get("type") == "dir")


def is_file(session: SessionState, path: str) -> bool:
    node = get_node(session, path)
    return bool(node and node.get("type") == "file")


def list_children(session: SessionState, path: str) -> list[str]:
    world = get_world()
    path = world.norm(path)
    prefix = "/" if path == "/" else path.rstrip("/") + "/"
    names: set[str] = set()
    for p in effective_nodes(session):
        if path == "/":
            if p != "/" and p.count("/") == 1:
                names.add(p.lstrip("/"))
            continue
        if p.startswith(prefix):
            rest = p[len(prefix) :]
            if rest and "/" not in rest:
                names.add(rest)
    return sorted(names)


def read_file(session: SessionState, path: str) -> str | None:
    node = get_node(session, path)
    if not node or node.get("type") != "file":
        return None
    return node.get("content", "")


def parent_dir(path: str) -> str:
    world = get_world()
    path = world.norm(path)
    if path == "/":
        return "/"
    return world.norm(path.rsplit("/", 1)[0] or "/")
