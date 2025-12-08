from __future__ import annotations

from datetime import datetime


def _strip_tzinfo(dt: datetime) -> datetime:
    """Strip timezone info for backend-agnostic timestamp storage."""
    return dt.replace(tzinfo=None) if getattr(dt, "tzinfo", None) else dt

