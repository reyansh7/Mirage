from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ParsedCommand:
    raw: str
    name: str
    args: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)


def parse_command(raw: str) -> ParsedCommand | None:
    text = raw.strip()
    if not text:
        return None
    # Strip simple sudo prefix for believable UX
    if text.startswith("sudo "):
        text = text[5:].lstrip()
    parts = _split(text)
    if not parts:
        return None
    name = parts[0]
    args: list[str] = []
    flags: list[str] = []
    for p in parts[1:]:
        if p.startswith("-") and p != "-":
            flags.append(p)
        else:
            args.append(p)
    return ParsedCommand(raw=raw.strip(), name=name, args=args, flags=flags)


def _split(text: str) -> list[str]:
    """Minimal shell-ish splitter (quotes supported)."""
    tokens: list[str] = []
    buf: list[str] = []
    quote: str | None = None
    for ch in text:
        if quote:
            if ch == quote:
                quote = None
            else:
                buf.append(ch)
            continue
        if ch in ('"', "'"):
            quote = ch
            continue
        if ch.isspace():
            if buf:
                tokens.append("".join(buf))
                buf = []
            continue
        buf.append(ch)
    if buf:
        tokens.append("".join(buf))
    return tokens
