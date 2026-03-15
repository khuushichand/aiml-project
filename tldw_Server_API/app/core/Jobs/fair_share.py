"""
Fair-share job scheduling.

Prevents any single user/org from monopolizing the job queue.
Uses a weighted round-robin approach based on active job counts.
"""
from __future__ import annotations

import os
from typing import Any

from loguru import logger


class FairShareScheduler:
    """Wraps JobManager to provide fair-share scheduling.

    Rules:
    1. Max concurrent jobs per user (configurable, default 5)
    2. Max concurrent jobs per org (configurable, default 20)
    3. Priority boost for users with fewer active jobs
    4. Starvation prevention: jobs waiting > threshold get priority bump
    """

    def __init__(
        self,
        max_per_user: int | None = None,
        max_per_org: int | None = None,
        starvation_threshold_seconds: int = 300,
    ) -> None:
        self.max_per_user = max_per_user or int(
            os.getenv("JOBS_MAX_PER_USER", "5")
        )
        self.max_per_org = max_per_org or int(
            os.getenv("JOBS_MAX_PER_ORG", "20")
        )
        self.starvation_threshold = starvation_threshold_seconds

    # ------------------------------------------------------------------
    # Admission control
    # ------------------------------------------------------------------

    def can_submit(self, user_id: int, active_count: int) -> bool:
        """Check if user can submit a new job.

        Args:
            user_id: The user requesting job submission.
            active_count: Number of currently active jobs for this user.

        Returns:
            True if the user is under their per-user concurrency limit.
        """
        return active_count < self.max_per_user

    def can_submit_org(self, org_id: int, active_count: int) -> bool:
        """Check if an organization can submit a new job.

        Args:
            org_id: The organization requesting job submission.
            active_count: Number of currently active jobs for this org.

        Returns:
            True if the org is under their per-org concurrency limit.
        """
        return active_count < self.max_per_org

    # ------------------------------------------------------------------
    # Priority calculation
    # ------------------------------------------------------------------

    def calculate_priority(
        self,
        user_id: int,
        active_count: int,
        wait_seconds: float = 0,
    ) -> int:
        """Calculate job priority (higher = more urgent).

        Applies a fair-share formula:
        - Base priority decreases as a user's active job count rises.
        - Starvation boost is applied if the job has been waiting too long.

        Args:
            user_id: The user owning the job.
            active_count: Number of active jobs for this user.
            wait_seconds: How long the job has been waiting (seconds).

        Returns:
            Priority score (higher values = run sooner).
        """
        base = max(0, 100 - (active_count * 10))
        starvation_boost = 50 if wait_seconds > self.starvation_threshold else 0
        priority = base + starvation_boost

        logger.debug(
            "Fair-share priority for user_id={}: base={}, starvation_boost={}, total={}",
            user_id,
            base,
            starvation_boost,
            priority,
        )

        return priority

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def get_limits(self) -> dict[str, Any]:
        """Return current scheduler limits for diagnostics."""
        return {
            "max_per_user": self.max_per_user,
            "max_per_org": self.max_per_org,
            "starvation_threshold_seconds": self.starvation_threshold,
        }
