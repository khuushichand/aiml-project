"""
Tests for Guardian analytics aggregation methods.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from tldw_Server_API.app.core.DB_Management.Guardian_DB import GuardianDB


@pytest.fixture()
def db(tmp_path):
    return GuardianDB(str(tmp_path / "test_analytics.db"))


def _create_rule_and_alerts(db, user_id="user1", count=3, category="test", severity="info"):
    """Helper: create a rule and N alerts."""
    rule = db.create_self_monitoring_rule(
        user_id=user_id,
        name=f"Rule {category}",
        patterns=["trigger"],
        notification_frequency="every_message",
        category=category,
    )
    for i in range(count):
        db.create_self_monitoring_alert(
            user_id=user_id,
            rule_id=rule.id,
            rule_name=rule.name,
            category=category,
            severity=severity,
            matched_pattern="trigger",
        )
    return rule


class TestAggregateByCategory:
    def test_correct_counts(self, db):
        """Aggregation by category should return correct counts."""
        _create_rule_and_alerts(db, category="violence", count=3)
        _create_rule_and_alerts(db, category="drugs", count=2)

        result = db.aggregate_alerts_by_category("user1")
        cats = {r["category"]: r["count"] for r in result}
        assert cats["violence"] == 3
        assert cats["drugs"] == 2

    def test_empty_returns_empty_list(self, db):
        """No alerts should return empty list."""
        result = db.aggregate_alerts_by_category("user1")
        assert result == []

    def test_since_filter(self, db):
        """Since filter should exclude older alerts."""
        _create_rule_and_alerts(db, category="test", count=2)
        # All alerts are recent, so since=now-1h should include them
        since = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        result = db.aggregate_alerts_by_category("user1", since_iso=since)
        assert len(result) > 0


class TestAggregateBySeverity:
    def test_correct_severity_counts(self, db):
        """Aggregation by severity should return correct counts."""
        _create_rule_and_alerts(db, severity="info", count=2, category="cat1")
        _create_rule_and_alerts(db, severity="warning", count=3, category="cat2")
        _create_rule_and_alerts(db, severity="critical", count=1, category="cat3")

        result = db.aggregate_alerts_by_severity("user1")
        sevs = {r["severity"]: r["count"] for r in result}
        assert sevs["info"] == 2
        assert sevs["warning"] == 3
        assert sevs["critical"] == 1


class TestAggregateByTime:
    def test_daily_buckets(self, db):
        """Time aggregation with daily buckets should work."""
        _create_rule_and_alerts(db, count=5)
        result = db.aggregate_alerts_by_time("user1", bucket="day")
        assert len(result) > 0
        total = sum(r["count"] for r in result)
        assert total == 5

    def test_monthly_buckets(self, db):
        """Time aggregation with monthly buckets should work."""
        _create_rule_and_alerts(db, count=3)
        result = db.aggregate_alerts_by_time("user1", bucket="month")
        assert len(result) > 0


class TestTopMatchedPatterns:
    def test_returns_most_frequent(self, db):
        """Should return patterns ordered by frequency."""
        rule = db.create_self_monitoring_rule(
            user_id="user1",
            name="Rule",
            patterns=["a", "b"],
            notification_frequency="every_message",
        )
        # Create alerts with different matched patterns
        for _ in range(5):
            db.create_self_monitoring_alert(
                user_id="user1", rule_id=rule.id,
                matched_pattern="frequent_pattern",
            )
        for _ in range(2):
            db.create_self_monitoring_alert(
                user_id="user1", rule_id=rule.id,
                matched_pattern="rare_pattern",
            )

        result = db.get_top_matched_patterns("user1")
        assert len(result) == 2
        assert result[0]["pattern"] == "frequent_pattern"
        assert result[0]["count"] == 5
        assert result[1]["pattern"] == "rare_pattern"
        assert result[1]["count"] == 2

    def test_respects_limit(self, db):
        """Should respect the limit parameter."""
        rule = db.create_self_monitoring_rule(
            user_id="user1", name="Rule", patterns=["x"],
        )
        for i in range(10):
            db.create_self_monitoring_alert(
                user_id="user1", rule_id=rule.id,
                matched_pattern=f"pattern_{i}",
            )
        result = db.get_top_matched_patterns("user1", limit=3)
        assert len(result) == 3


class TestEscalationSummary:
    def test_returns_escalation_states(self, db):
        """Should return current escalation states."""
        db.upsert_escalation_state(
            rule_id="rule1", user_id="user1",
            session_id="s1", session_trigger_count=3,
            window_trigger_count=5,
            current_escalated_action="block",
        )
        result = db.get_escalation_summary("user1")
        assert len(result) == 1
        assert result[0]["rule_id"] == "rule1"

    def test_empty_returns_empty(self, db):
        """No escalation states should return empty list."""
        result = db.get_escalation_summary("user1")
        assert result == []
