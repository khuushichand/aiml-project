"""Helpers for API deprecation response headers."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

_DEPRECATION_NONCRITICAL_EXCEPTIONS = (TypeError, ValueError, OverflowError)


def build_deprecation_headers(
    successor: str,
    *,
    default_sunset_days: int = 120,
) -> dict[str, str]:
    """Build standard deprecation headers with a UTC sunset timestamp."""
    try:
        sunset_days = int(os.getenv("DEPRECATION_SUNSET_DAYS", str(default_sunset_days)))
        if sunset_days < 1:
            raise ValueError("sunset days must be positive")
    except _DEPRECATION_NONCRITICAL_EXCEPTIONS:
        sunset_days = default_sunset_days

    sunset = (datetime.now(timezone.utc) + timedelta(days=sunset_days)).strftime(
        "%a, %d %b %Y %H:%M:%S GMT"
    )
    return {
        "Deprecation": "true",
        "Sunset": sunset,
        "Link": f"<{successor}>; rel=successor-version",
    }
