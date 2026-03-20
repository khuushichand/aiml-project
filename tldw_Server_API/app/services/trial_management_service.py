"""
Trial subscription management.

Handles trial creation, expiry tracking, and conversion metrics.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

from loguru import logger


class TrialManagementService:
    """Manages trial period lifecycle for user subscriptions."""

    def __init__(self) -> None:
        self.default_trial_days = int(os.getenv("TRIAL_DURATION_DAYS", "14"))

    def calculate_trial_expiry(self, start_date: datetime | None = None) -> datetime:
        """Calculate the trial expiry datetime from a given start date.

        Args:
            start_date: When the trial begins.  Defaults to now (UTC).

        Returns:
            The UTC datetime when the trial expires.
        """
        start = start_date or datetime.now(timezone.utc)
        return start + timedelta(days=self.default_trial_days)

    def is_trial_expired(self, trial_end: datetime) -> bool:
        """Check whether a trial has expired.

        Args:
            trial_end: The trial expiry datetime (must be timezone-aware UTC).
        """
        now = datetime.now(timezone.utc)
        # Ensure trial_end is tz-aware for comparison
        if trial_end.tzinfo is None:
            trial_end = trial_end.replace(tzinfo=timezone.utc)
        return now > trial_end

    def get_trial_status(self, user: dict[str, Any]) -> dict[str, Any]:
        """Get trial status for a user.

        Args:
            user: User dict expected to contain an optional ``trial_ends_at``
                key (ISO-format string or datetime).

        Returns:
            A dict with ``in_trial``, ``trial_ends_at``, ``expired``, and
            ``days_remaining`` keys.
        """
        trial_end = user.get("trial_ends_at")
        if not trial_end:
            return {"in_trial": False, "reason": "no_trial"}

        if isinstance(trial_end, str):
            trial_end = datetime.fromisoformat(trial_end)

        # Ensure tz-aware
        if trial_end.tzinfo is None:
            trial_end = trial_end.replace(tzinfo=timezone.utc)

        expired = self.is_trial_expired(trial_end)
        remaining = (
            max(0, (trial_end - datetime.now(timezone.utc)).days) if not expired else 0
        )

        return {
            "in_trial": not expired,
            "trial_ends_at": trial_end.isoformat(),
            "expired": expired,
            "days_remaining": remaining,
        }
