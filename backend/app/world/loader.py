from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DATA_DIR = Path(__file__).resolve().parent / "data"


def _load_json(name: str) -> Any:
    with open(DATA_DIR / name, encoding="utf-8") as fh:
        return json.load(fh)


def _resolve_content(node: dict[str, Any]) -> str:
    if "content" in node:
        return node["content"]
    ref = node.get("content_ref")
    if ref:
        path = DATA_DIR / ref
        if path.exists():
            return path.read_text(encoding="utf-8")
        return f"[missing content_ref: {ref}]\n"
    return ""


class WorldData:
    """Loads static Phase-2 world JSON into memory."""

    def __init__(self) -> None:
        self.company = _load_json("company.json")
        self.users = _load_json("users.json")
        self.network = _load_json("network.json")
        self.services = _load_json("services.json")
        self.database = _load_json("database.json")
        raw_fs = _load_json("filesystem.json")
        self.filesystem: dict[str, dict[str, Any]] = {}
        for path, node in raw_fs.items():
            entry = dict(node)
            if entry.get("type") == "file":
                entry["content"] = _resolve_content(entry)
                entry.pop("content_ref", None)
            self.filesystem[self.norm(path)] = entry

    @staticmethod
    def norm(path: str) -> str:
        if not path:
            return "/"
        path = path.replace("\\", "/")
        if not path.startswith("/"):
            path = "/" + path
        parts: list[str] = []
        for part in path.split("/"):
            if part in ("", "."):
                continue
            if part == "..":
                if parts:
                    parts.pop()
                continue
            parts.append(part)
        return "/" + "/".join(parts) if parts else "/"

    def user_record(self, username: str) -> dict[str, Any] | None:
        for u in self.users.get("users", []):
            if u["username"] == username:
                return u
        return None

    def known_usernames(self) -> list[str]:
        return [u["username"] for u in self.users.get("users", [])]


_WORLD: WorldData | None = None


def get_world() -> WorldData:
    global _WORLD
    if _WORLD is None:
        _WORLD = WorldData()
    return _WORLD
