"""
Tests for fair-share job scheduling.

Covers:
- Admission control (per-user and per-org limits)
- Priority calculation with active job weighting
- Starvation prevention boost
- Configuration via env vars and constructor args
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from tldw_Server_API.app.core.Jobs.fair_share import FairShareScheduler


# ---------------------------------------------------------------------------
# Admission control tests
# ---------------------------------------------------------------------------


class TestCanSubmit:
    """Tests for user admission control."""

    def test_allows_when_under_limit(self):
        scheduler = FairShareScheduler(max_per_user=5)
        assert scheduler.can_submit(user_id=1, active_count=0) is True
        assert scheduler.can_submit(user_id=1, active_count=4) is True

    def test_blocks_when_at_limit(self):
        scheduler = FairShareScheduler(max_per_user=5)
        assert scheduler.can_submit(user_id=1, active_count=5) is False

    def test_blocks_when_over_limit(self):
        scheduler = FairShareScheduler(max_per_user=5)
        assert scheduler.can_submit(user_id=1, active_count=10) is False

    def test_custom_limit(self):
        scheduler = FairShareScheduler(max_per_user=2)
        assert scheduler.can_submit(user_id=1, active_count=1) is True
        assert scheduler.can_submit(user_id=1, active_count=2) is False


class TestCanSubmitOrg:
    """Tests for org admission control."""

    def test_allows_when_under_org_limit(self):
        scheduler = FairShareScheduler(max_per_org=20)
        assert scheduler.can_submit_org(org_id=1, active_count=0) is True
        assert scheduler.can_submit_org(org_id=1, active_count=19) is True

    def test_blocks_when_at_org_limit(self):
        scheduler = FairShareScheduler(max_per_org=20)
        assert scheduler.can_submit_org(org_id=1, active_count=20) is False

    def test_custom_org_limit(self):
        scheduler = FairShareScheduler(max_per_org=3)
        assert scheduler.can_submit_org(org_id=1, active_count=2) is True
        assert scheduler.can_submit_org(org_id=1, active_count=3) is False


# ---------------------------------------------------------------------------
# Priority calculation tests
# ---------------------------------------------------------------------------


class TestCalculatePriority:
    """Tests for fair-share priority calculation."""

    def test_max_priority_with_no_active_jobs(self):
        scheduler = FairShareScheduler()
        priority = scheduler.calculate_priority(user_id=1, active_count=0)
        assert priority == 100

    def test_priority_decreases_with_active_jobs(self):
        scheduler = FairShareScheduler()
        p0 = scheduler.calculate_priority(user_id=1, active_count=0)
        p3 = scheduler.calculate_priority(user_id=1, active_count=3)
        p5 = scheduler.calculate_priority(user_id=1, active_count=5)
        assert p0 > p3 > p5

    def test_priority_floors_at_zero(self):
        scheduler = FairShareScheduler()
        priority = scheduler.calculate_priority(user_id=1, active_count=15)
        # 100 - 150 = -50, but floored at 0
        assert priority == 0

    def test_starvation_boost_applied(self):
        scheduler = FairShareScheduler(starvation_threshold_seconds=300)
        normal = scheduler.calculate_priority(
            user_id=1, active_count=5, wait_seconds=100
        )
        starved = scheduler.calculate_priority(
            user_id=1, active_count=5, wait_seconds=301
        )
        assert starved == normal + 50

    def test_starvation_boost_not_applied_below_threshold(self):
        scheduler = FairShareScheduler(starvation_threshold_seconds=300)
        p1 = scheduler.calculate_priority(
            user_id=1, active_count=2, wait_seconds=0
        )
        p2 = scheduler.calculate_priority(
            user_id=1, active_count=2, wait_seconds=299
        )
        assert p1 == p2

    def test_starvation_boost_at_threshold_not_applied(self):
        """Boost requires strictly exceeding the threshold."""
        scheduler = FairShareScheduler(starvation_threshold_seconds=300)
        priority = scheduler.calculate_priority(
            user_id=1, active_count=0, wait_seconds=300
        )
        # At exactly threshold, not exceeded
        assert priority == 100


# ---------------------------------------------------------------------------
# Configuration tests
# ---------------------------------------------------------------------------


class TestSchedulerConfig:
    """Tests for scheduler configuration."""

    def test_default_limits(self):
        scheduler = FairShareScheduler()
        limits = scheduler.get_limits()
        assert limits["max_per_user"] == 5
        assert limits["max_per_org"] == 20
        assert limits["starvation_threshold_seconds"] == 300

    def test_custom_limits(self):
        scheduler = FairShareScheduler(
            max_per_user=10,
            max_per_org=50,
            starvation_threshold_seconds=600,
        )
        limits = scheduler.get_limits()
        assert limits["max_per_user"] == 10
        assert limits["max_per_org"] == 50
        assert limits["starvation_threshold_seconds"] == 600

    def test_env_var_configuration(self):
        """Limits can be set via environment variables."""
        with patch.dict(
            "os.environ",
            {"JOBS_MAX_PER_USER": "8", "JOBS_MAX_PER_ORG": "30"},
        ):
            scheduler = FairShareScheduler()
            assert scheduler.max_per_user == 8
            assert scheduler.max_per_org == 30

    def test_constructor_overrides_env(self):
        """Constructor args take precedence over env vars."""
        with patch.dict(
            "os.environ",
            {"JOBS_MAX_PER_USER": "8", "JOBS_MAX_PER_ORG": "30"},
        ):
            scheduler = FairShareScheduler(max_per_user=3, max_per_org=10)
            assert scheduler.max_per_user == 3
            assert scheduler.max_per_org == 10
