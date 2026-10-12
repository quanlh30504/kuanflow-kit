"""The single clock (contract C36c); ``KUANFLOW_NOW`` pins it for tests and reproducible runs."""

from __future__ import annotations

import os
from datetime import datetime


def now() -> datetime:
    """Current local time with offset, truncated to seconds (or ``KUANFLOW_NOW``)."""
    pinned = os.environ.get("KUANFLOW_NOW")
    value = datetime.fromisoformat(pinned) if pinned else datetime.now().astimezone()
    if value.tzinfo is None:
        value = value.astimezone()
    return value.replace(microsecond=0)


def iso() -> str:
    """Manifest form, e.g. ``2026-11-03T09:00:00+07:00``."""
    return now().isoformat(timespec="seconds")


def date() -> str:
    """Date form, e.g. ``2026-11-03``."""
    return now().date().isoformat()


def stamp() -> str:
    """Backup directory form, e.g. ``20261103T090000``."""
    return now().strftime("%Y%m%dT%H%M%S")
