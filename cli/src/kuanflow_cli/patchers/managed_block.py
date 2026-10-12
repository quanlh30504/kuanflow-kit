"""Kuanflow-managed text blocks inside user files (contract C42).

A block is a begin marker line, a body, and an end marker line. Everything outside the block is
the user's and is kept byte-identical by ``upsert`` and ``remove``.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Literal

from kuanflow_cli.errors import BlockError

Style = Literal["html", "hash"]
Position = Literal["top", "bottom"]

_NOTE = "(managed by Kuanflow — edit via Kuanflow, not here)"
_BEGIN = {"html": f"<!-- kuanflow:begin {_NOTE} -->", "hash": f"# kuanflow:begin {_NOTE}"}
_BEGIN_PREFIX = {"html": "<!-- kuanflow:begin", "hash": "# kuanflow:begin"}
_END = {"html": "<!-- kuanflow:end -->", "hash": "# kuanflow:end"}


@dataclass(frozen=True)
class Block:
    """A found block: ``text[start:end]`` covers begin line through end line (incl. newline)."""

    start: int
    end: int
    body: str


def style_for(path: str) -> Style:
    """``html`` for Markdown (``*.md``), else ``hash``."""
    return "html" if path.endswith(".md") else "hash"


def find(text: str, style: Style) -> Block | None:
    """Locate the single block in ``text``; ``BlockError`` on broken or duplicate markers."""
    begin: tuple[int, int] | None = None  # (offset of begin line, offset after it)
    found: Block | None = None
    offset = 0
    for line in text.split("\n"):
        line_end = min(offset + len(line) + 1, len(text))
        stripped = line.rstrip()
        if stripped.startswith(_BEGIN_PREFIX[style]):
            if begin is not None or found is not None:
                raise BlockError(f"more than one '{_BEGIN_PREFIX[style]}' marker")
            begin = (offset, line_end)
        elif stripped == _END[style]:
            if begin is None:
                raise BlockError(f"'{_END[style]}' without a preceding begin marker")
            found = Block(begin[0], line_end, text[begin[1] : offset])
            begin = None
        offset = line_end
    if begin is not None:
        raise BlockError(f"'{_BEGIN_PREFIX[style]}' without '{_END[style]}'")
    return found


def _normalise(body: str) -> str:
    body = body.rstrip("\n")
    return body + "\n" if body else ""


def render_block(body: str, style: Style) -> str:
    """Canonical block text: begin, body (exactly one final newline), end."""
    return f"{_BEGIN[style]}\n{_normalise(body)}{_END[style]}\n"


def upsert(text: str | None, body: str, style: Style, position: Position) -> str:
    """Replace the block in ``text`` or add one at ``position`` (``None``/``""`` = no file)."""
    rendered = render_block(body, style)
    if not text:
        return rendered
    block = find(text, style)
    if block is not None:
        return text[: block.start] + rendered + text[block.end :]
    if position == "top":
        return rendered + "\n" + text
    return text + ("" if text.endswith("\n") else "\n") + "\n" + rendered


def remove(text: str, style: Style) -> str:
    """Drop the block and the blank-line separator ``upsert`` added; unchanged if no block."""
    block = find(text, style)
    if block is None:
        return text
    head, tail = text[: block.start], text[block.end :]
    if block.start == 0 and tail.startswith("\n"):
        tail = tail[1:]
    elif head.endswith("\n\n"):
        head = head[:-1]
    return head + tail


def body_sha256(text: str, style: Style) -> str | None:
    """sha256 hex of the block body (UTF-8), ``None`` when there is no block."""
    block = find(text, style)
    return None if block is None else hashlib.sha256(block.body.encode("utf-8")).hexdigest()
