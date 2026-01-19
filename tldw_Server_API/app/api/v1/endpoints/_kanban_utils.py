from __future__ import annotations

"""
Shared utilities for Kanban API endpoints.
"""

from datetime import datetime, timezone
from typing import Optional


def to_db_timestamp(value: Optional[datetime]) -> Optional[str]:
    """Convert datetime to DB-friendly timestamp string."""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


__all__ = ["to_db_timestamp"]
