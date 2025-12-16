from __future__ import annotations

from datetime import datetime


def _strip_tzinfo(dt: datetime) -> datetime:
    """
    Strip timezone info for backend-agnostic timestamp storage.

    Converts an aware datetime to naive by removing tzinfo. Naive datetimes
    are preferred for consistent storage across different database backends.

    Args:
        dt: A datetime object (aware or naive).

    Returns:
        A naive datetime with tzinfo removed.
    """
    return dt.replace(tzinfo=None) if dt.tzinfo else dt
