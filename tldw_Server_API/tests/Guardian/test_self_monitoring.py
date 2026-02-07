"""
Tests for SelfMonitoringService — awareness-oriented self-monitoring
with pattern matching, dedup, escalation, cooldown, and crisis resources.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from tldw_Server_API.app.core.DB_Management.Guardian_DB import GuardianDB
from tldw_Server_API.app.core.Monitoring.self_monitoring_service import (
    CRISIS_DISCLAIMER,
    CRISIS_RESOURCES,
    SelfMonitoringCheckResult,
    SelfMonitoringService,
)


@pytest.fixture()
def db(tmp_path):
    return GuardianDB(str(tmp_path / "test_selfmon.db"))


@pytest.fixture()
def svc(db):
    return SelfMonitoringService(db)


def _create_rule(db, **kwargs):
    defaults = {
        "user_id": "user1",
        "name": "Test Rule",
        "patterns": ["test_word"],
        "notification_frequency": "every_message",
    }
    defaults.update(kwargs)
    return db.create_self_monitoring_rule(**defaults)


# ── Basic Matching ──────────────────────────────────────────


class TestBasicMatching:
    def test_empty_text_returns_not_triggered(self, svc):
        result = svc.check_text("", "user1")
        assert result.triggered is False
        assert result.action == "pass"

    def test_whitespace_text_returns_not_triggered(self, svc):
        result = svc.check_text("   ", "user1")
        assert result.triggered is False

    def test_no_rules_returns_not_triggered(self, svc):
        result = svc.check_text("hello world", "user1")
        assert result.triggered is False

    def test_literal_pattern_match(self, db, svc):
        _create_rule(db, patterns=["workout"])
        result = svc.check_text("I did a workout today", "user1")
        assert result.triggered is True
        assert result.action == "notify"
        assert len(result.alerts) == 1

    def test_regex_pattern_match(self, db, svc):
        _create_rule(db, patterns=[r"\bexercis\w+\b"], pattern_type="regex")
        result = svc.check_text("I was exercising this morning", "user1")
        assert result.triggered is True

    def test_case_insensitive(self, db, svc):
        _create_rule(db, patterns=["Workout"])
        result = svc.check_text("WORKOUT session", "user1")
        assert result.triggered is True

    def test_no_match_returns_not_triggered(self, db, svc):
        _create_rule(db, patterns=["workout"])
        result = svc.check_text("I read a book today", "user1")
        assert result.triggered is False

    def test_disabled_rule_not_evaluated(self, db, svc):
        _create_rule(db, patterns=["workout"], enabled=False)
        result = svc.check_text("workout session", "user1")
        assert result.triggered is False

    def test_multiple_patterns_any_match(self, db, svc):
        _create_rule(db, patterns=["workout", "exercise", "gym"])
        result = svc.check_text("going to the gym", "user1")
        assert result.triggered is True

    def test_multiple_rules_evaluated(self, db, svc):
        _create_rule(db, name="Fitness", patterns=["workout"], category="fitness")
        _create_rule(db, name="Diet", patterns=["diet"], category="nutrition")
        result = svc.check_text("workout and diet plan", "user1")
        assert result.triggered is True
        assert len(result.alerts) == 2


# ── Except Patterns (False Positive Exclusion) ──────────────


class TestExceptPatterns:
    def test_except_pattern_suppresses_match(self, db, svc):
        _create_rule(
            db,
            patterns=["suicide"],
            except_patterns=["suicide prevention", "academic study of suicide"],
        )
        result = svc.check_text("suicide prevention hotline is 988", "user1")
        assert result.triggered is False

    def test_except_pattern_only_suppresses_when_matched(self, db, svc):
        _create_rule(
            db,
            patterns=["suicide"],
            except_patterns=["prevention"],
        )
        # "suicidal" does NOT contain "suicide" as a substring (suicid-al vs suicid-e)
        # Use text that literally contains "suicide"
        result = svc.check_text("I think about suicide", "user1")
        assert result.triggered is True


# ── Phase Filtering ─────────────────────────────────────────


class TestPhaseFiltering:
    def test_input_phase_matches_input(self, db, svc):
        _create_rule(db, patterns=["keyword"], phase="input")
        result = svc.check_text("keyword here", "user1", phase="input")
        assert result.triggered is True

    def test_input_phase_skips_output(self, db, svc):
        _create_rule(db, patterns=["keyword"], phase="input")
        result = svc.check_text("keyword here", "user1", phase="output")
        assert result.triggered is False

    def test_both_phase_matches_any(self, db, svc):
        _create_rule(db, patterns=["keyword"], phase="both")
        assert svc.check_text("keyword", "user1", phase="input").triggered is True
        svc.invalidate_cache()
        assert svc.check_text("keyword", "user1", phase="output").triggered is True


# ── Min Context Length ──────────────────────────────────────


class TestMinContextLength:
    def test_short_text_skipped(self, db, svc):
        _create_rule(db, patterns=["word"], min_context_length=50)
        result = svc.check_text("word", "user1")
        assert result.triggered is False

    def test_long_enough_text_matches(self, db, svc):
        _create_rule(db, patterns=["word"], min_context_length=10)
        result = svc.check_text("this is a word in a longer sentence", "user1")
        assert result.triggered is True


# ── Action Priority ─────────────────────────────────────────


class TestActionPriority:
    def test_block_beats_notify(self, db, svc):
        _create_rule(db, name="R1", patterns=["bad"], action="notify")
        _create_rule(db, name="R2", patterns=["bad"], action="block")
        result = svc.check_text("bad text", "user1")
        assert result.action == "block"

    def test_redact_beats_notify(self, db, svc):
        _create_rule(db, name="R1", patterns=["bad"], action="notify")
        _create_rule(db, name="R2", patterns=["bad"], action="redact")
        result = svc.check_text("bad text", "user1")
        assert result.action == "redact"

    def test_block_message_set_for_block_action(self, db, svc):
        _create_rule(
            db, patterns=["bad"], action="block",
            block_message="Custom block msg",
        )
        result = svc.check_text("bad text", "user1")
        assert result.block_message == "Custom block msg"

    def test_default_block_message(self, db, svc):
        _create_rule(db, name="Crisis", patterns=["bad"], action="block")
        result = svc.check_text("bad text", "user1")
        assert "Crisis" in result.block_message


# ── Redaction ───────────────────────────────────────────────


class TestRedaction:
    def test_redact_replaces_pattern(self, db, svc):
        _create_rule(db, patterns=["secret"], action="redact")
        result = svc.check_text("this has secret data", "user1")
        assert result.action == "redact"
        assert result.redacted_text is not None
        assert "[SELF-REDACTED]" in result.redacted_text
        assert "secret" not in result.redacted_text


# ── Dedup ───────────────────────────────────────────────────


class TestDedup:
    def test_every_message_always_fires(self, db, svc):
        _create_rule(db, patterns=["word"], notification_frequency="every_message")
        svc.check_text("word", "user1", conversation_id="c1")
        result = svc.check_text("word", "user1", conversation_id="c1")
        assert result.triggered is True

    def test_once_per_conversation_dedup(self, db, svc):
        _create_rule(
            db, patterns=["word"],
            notification_frequency="once_per_conversation",
        )
        r1 = svc.check_text("word", "user1", conversation_id="c1")
        assert r1.triggered is True
        r2 = svc.check_text("word", "user1", conversation_id="c1")
        assert r2.triggered is False
        r3 = svc.check_text("word", "user1", conversation_id="c2")
        assert r3.triggered is True

    def test_once_per_day_dedup(self, db, svc):
        _create_rule(
            db, patterns=["word"],
            notification_frequency="once_per_day",
        )
        r1 = svc.check_text("word", "user1")
        assert r1.triggered is True
        r2 = svc.check_text("word", "user1")
        assert r2.triggered is False


# ── Escalation ──────────────────────────────────────────────


class TestEscalation:
    def test_session_escalation(self, db, svc):
        _create_rule(
            db, patterns=["trigger"],
            action="notify",
            escalation_session_threshold=3,
            escalation_session_action="block",
        )
        session = "sess1"
        for _ in range(2):
            r = svc.check_text("trigger word", "user1", session_id=session)
            assert r.triggered is True
        r3 = svc.check_text("trigger word", "user1", session_id=session)
        assert r3.triggered is True
        assert r3.action == "block"
        assert r3.escalation_triggered is True

    def test_session_reset_on_new_session(self, db, svc):
        _create_rule(
            db, patterns=["trigger"],
            action="notify",
            escalation_session_threshold=3,
            escalation_session_action="block",
        )
        for _ in range(2):
            svc.check_text("trigger", "user1", session_id="s1")
        r = svc.check_text("trigger", "user1", session_id="s2")
        assert r.action == "notify"

    def test_window_escalation(self, db, svc):
        _create_rule(
            db, patterns=["trigger"],
            action="notify",
            escalation_window_days=7,
            escalation_window_threshold=3,
            escalation_window_action="block",
        )
        for i in range(3):
            r = svc.check_text("trigger", "user1", session_id=f"s{i}")
        assert r.action == "block"
        assert r.escalation_triggered is True

    def test_no_escalation_when_disabled(self, db, svc):
        _create_rule(
            db, patterns=["trigger"],
            action="notify",
            escalation_session_threshold=0,
            escalation_window_threshold=0,
        )
        for _ in range(10):
            r = svc.check_text("trigger", "user1", session_id="s1")
        assert r.action == "notify"
        assert r.escalation_triggered is False


# ── Cooldown Protection ─────────────────────────────────────


class TestCooldownProtection:
    def test_can_disable_when_no_cooldown(self, db, svc):
        rule = _create_rule(db, patterns=["word"], cooldown_minutes=0)
        assert svc.can_disable_rule(rule) is True

    def test_can_disable_when_bypass_none(self, db, svc):
        rule = _create_rule(
            db, patterns=["word"],
            cooldown_minutes=60,
            bypass_protection="none",
        )
        assert svc.can_disable_rule(rule) is True

    def test_cannot_disable_within_cooldown(self, db, svc):
        rule = _create_rule(
            db, patterns=["word"],
            cooldown_minutes=99999,
            bypass_protection="cooldown",
        )
        assert svc.can_disable_rule(rule) is False

    def test_can_disable_after_cooldown(self, db, svc):
        rule = _create_rule(
            db, patterns=["word"],
            cooldown_minutes=60,
            bypass_protection="cooldown",
        )
        two_hours_ago = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        with db._lock:
            conn = db._connect()
            try:
                conn.execute(
                    "UPDATE self_monitoring_rules SET created_at = ? WHERE id = ?",
                    (two_hours_ago, rule.id),
                )
            finally:
                conn.close()
        updated_rule = db.get_self_monitoring_rule(rule.id)
        assert svc.can_disable_rule(updated_rule) is True

    def test_request_deactivation_immediate(self, db, svc):
        rule = _create_rule(db, patterns=["word"], cooldown_minutes=0)
        result = svc.request_deactivation(rule.id, "user1")
        assert result["ok"] is True
        assert result["status"] == "disabled_immediately"
        updated = db.get_self_monitoring_rule(rule.id)
        assert updated.enabled is False

    def test_request_deactivation_pending(self, db, svc):
        rule = _create_rule(
            db, patterns=["word"],
            cooldown_minutes=99999,
            bypass_protection="cooldown",
        )
        result = svc.request_deactivation(rule.id, "user1")
        assert result["ok"] is True
        assert result["status"] == "pending_deactivation"
        assert "deactivation_at" in result

    def test_request_deactivation_wrong_user(self, db, svc):
        rule = _create_rule(db, patterns=["word"])
        result = svc.request_deactivation(rule.id, "wrong_user")
        assert result["ok"] is False

    def test_request_deactivation_nonexistent(self, svc):
        result = svc.request_deactivation("nonexistent", "user1")
        assert result["ok"] is False


# ── Crisis Resources ────────────────────────────────────────


class TestCrisisResources:
    def test_crisis_resources_attached_when_enabled(self, db, svc):
        _create_rule(
            db, patterns=["crisis"],
            crisis_resources_enabled=True,
        )
        result = svc.check_text("crisis situation", "user1")
        assert result.triggered is True
        assert result.crisis_resources is not None
        assert len(result.crisis_resources) > 0

    def test_crisis_resources_not_attached_when_disabled(self, db, svc):
        _create_rule(
            db, patterns=["crisis"],
            crisis_resources_enabled=False,
        )
        result = svc.check_text("crisis situation", "user1")
        assert result.crisis_resources is None

    def test_get_crisis_resources(self, svc):
        resources = svc.get_crisis_resources()
        assert "resources" in resources
        assert "disclaimer" in resources
        assert len(resources["resources"]) > 0

    def test_crisis_resources_list(self):
        assert len(CRISIS_RESOURCES) >= 4
        assert any("988" in r["contact"] for r in CRISIS_RESOURCES)

    def test_crisis_disclaimer_exists(self):
        assert "crisis service" in CRISIS_DISCLAIMER.lower()
        assert "911" in CRISIS_DISCLAIMER


# ── Context Snippet ─────────────────────────────────────────


class TestContextSnippet:
    def test_silent_log_no_snippet(self, db, svc):
        _create_rule(db, patterns=["word"], display_mode="silent_log")
        result = svc.check_text("word here", "user1")
        assert result.triggered is True
        alerts = db.list_self_monitoring_alerts("user1")
        assert len(alerts) >= 1

    def test_long_text_truncated(self, db, svc):
        _create_rule(db, patterns=["word"])
        long_text = "word " + "x" * 300
        svc.check_text(long_text, "user1")
        alerts = db.list_self_monitoring_alerts("user1")
        assert len(alerts) >= 1
        snippet = alerts[0].context_snippet
        assert snippet is not None
        assert len(snippet) <= 203  # 200 + "..."


# ── Alert Recording ─────────────────────────────────────────


class TestAlertRecording:
    def test_alert_recorded_on_trigger(self, db, svc):
        _create_rule(db, name="Fitness", category="fitness", patterns=["workout"])
        svc.check_text("workout session", "user1", conversation_id="c1", session_id="s1")
        alerts = db.list_self_monitoring_alerts("user1")
        assert len(alerts) == 1
        alert = alerts[0]
        assert alert.rule_name == "Fitness"
        assert alert.category == "fitness"
        assert alert.conversation_id == "c1"
        assert alert.session_id == "s1"
        assert alert.phase == "input"

    def test_no_alert_when_no_match(self, db, svc):
        _create_rule(db, patterns=["workout"])
        svc.check_text("reading a book", "user1")
        alerts = db.list_self_monitoring_alerts("user1")
        assert len(alerts) == 0

    def test_alert_records_channels(self, db, svc):
        _create_rule(
            db, patterns=["word"],
            notification_channels=["in_app", "email"],
        )
        svc.check_text("word", "user1")
        alerts = db.list_self_monitoring_alerts("user1")
        assert alerts[0].notification_channels_used == ["in_app", "email"]

    def test_escalation_info_in_alert(self, db, svc):
        _create_rule(
            db, patterns=["trigger"],
            escalation_session_threshold=2,
            escalation_session_action="block",
        )
        svc.check_text("trigger", "user1", session_id="s1")
        svc.check_text("trigger", "user1", session_id="s1")
        alerts = db.list_self_monitoring_alerts("user1")
        escalated_alerts = [a for a in alerts if a.escalation_info]
        assert len(escalated_alerts) >= 1


# ── Cache ───────────────────────────────────────────────────


class TestCache:
    def test_cache_invalidation(self, db, svc):
        _create_rule(db, patterns=["word1"])
        r1 = svc.check_text("word1", "user1")
        assert r1.triggered is True

        _create_rule(db, patterns=["word2"])
        r2 = svc.check_text("word2", "user1")
        assert r2.triggered is False  # cached

        svc.invalidate_cache("user1")
        r3 = svc.check_text("word2", "user1")
        assert r3.triggered is True

    def test_invalidate_all(self, db, svc):
        _create_rule(db, patterns=["word"])
        svc.check_text("word", "user1")
        svc.invalidate_cache()
        result = svc.check_text("word", "user1")
        assert result.triggered is True

    def test_cache_ttl_expiry(self, db, svc):
        _create_rule(db, patterns=["cached_word"])
        svc.check_text("cached_word", "user1")
        # Force cache timestamp to be in the past
        with svc._lock:
            svc._cache_timestamps["user1:"] = 0.0
        # Add another rule
        _create_rule(db, patterns=["new_word"])
        result = svc.check_text("new_word", "user1")
        assert result.triggered is True


# ── Display Modes ───────────────────────────────────────────


class TestDisplayModes:
    def test_display_mode_in_result(self, db, svc):
        _create_rule(db, patterns=["word"], display_mode="sidebar_note")
        result = svc.check_text("word", "user1")
        assert result.display_mode == "sidebar_note"

    def test_display_mode_in_alert(self, db, svc):
        _create_rule(db, patterns=["word"], display_mode="post_session_summary")
        svc.check_text("word", "user1")
        alerts = db.list_self_monitoring_alerts("user1")
        assert alerts[0].display_mode == "post_session_summary"


# ── Invalid Pattern Handling ────────────────────────────────


class TestInvalidPatterns:
    def test_invalid_regex_rejected_at_creation(self, db, svc):
        with pytest.raises(ValueError, match="Unsafe regex pattern"):
            _create_rule(db, patterns=["[bad_regex"], pattern_type="regex")

    def test_rule_with_no_valid_patterns_rejected_at_creation(self, db, svc):
        with pytest.raises(ValueError, match="Unsafe regex pattern"):
            _create_rule(db, patterns=["[bad1", "[bad2"], pattern_type="regex")


# ── Default Result Fields ───────────────────────────────────


class TestDefaultResultFields:
    def test_default_check_result(self):
        r = SelfMonitoringCheckResult()
        assert r.triggered is False
        assert r.alerts == []
        assert r.action == "pass"
        assert r.redacted_text is None
        assert r.block_message is None
        assert r.display_mode == "inline_banner"
        assert r.crisis_resources is None
        assert r.escalation_triggered is False


# ── Deactivation Token Fields ────────────────────────────────


class TestDeactivationTokenFields:
    def test_token_roundtrip(self, db, svc):
        rule = _create_rule(db, patterns=["word"])
        assert rule.deactivation_confirmation_token is None
        assert rule.deactivation_requested_at is None
        # Set token
        db.update_self_monitoring_rule(
            rule.id,
            deactivation_confirmation_token="abc123",
            deactivation_requested_at="2026-02-07T12:00:00+00:00",
        )
        fetched = db.get_self_monitoring_rule(rule.id)
        assert fetched.deactivation_confirmation_token == "abc123"
        assert fetched.deactivation_requested_at == "2026-02-07T12:00:00+00:00"

    def test_token_update_and_clear(self, db, svc):
        rule = _create_rule(db, patterns=["word"])
        db.update_self_monitoring_rule(
            rule.id,
            deactivation_confirmation_token="token1",
            deactivation_requested_at="2026-02-07T12:00:00+00:00",
        )
        fetched = db.get_self_monitoring_rule(rule.id)
        assert fetched.deactivation_confirmation_token == "token1"
        # Clear token
        db.update_self_monitoring_rule(
            rule.id,
            deactivation_confirmation_token=None,
            deactivation_requested_at=None,
        )
        fetched2 = db.get_self_monitoring_rule(rule.id)
        assert fetched2.deactivation_confirmation_token is None
        assert fetched2.deactivation_requested_at is None


# ── Self-Monitoring Schedule Filtering ─────────────────────────


class TestSelfMonScheduleFiltering:
    def test_rule_skipped_outside_schedule(self, db, svc):
        """Rule linked to governance policy with non-matching day is skipped."""
        from datetime import datetime
        from zoneinfo import ZoneInfo
        now = datetime.now(ZoneInfo("UTC"))
        day_names = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        other_day = day_names[(now.weekday() + 3) % 7]
        gp = db.create_governance_policy(
            owner_user_id="user1",
            name="Weekday Policy",
            policy_mode="self",
            schedule_days=other_day,
            schedule_timezone="UTC",
        )
        _create_rule(db, patterns=["trigger"], governance_policy_id=gp.id)
        result = svc.check_text("trigger word", "user1")
        assert result.triggered is False


# ── Self-Monitoring Chat-Type Filtering ────────────────────────


class TestSelfMonChatTypeFiltering:
    def test_rule_skipped_for_wrong_chat_type(self, db, svc):
        gp = db.create_governance_policy(
            owner_user_id="user1",
            name="Character Only",
            policy_mode="self",
            scope_chat_types="character",
        )
        _create_rule(db, patterns=["trigger"], governance_policy_id=gp.id)
        result = svc.check_text("trigger word", "user1", chat_type="regular")
        assert result.triggered is False

    def test_rule_matches_correct_chat_type(self, db, svc):
        gp = db.create_governance_policy(
            owner_user_id="user1",
            name="Character Only",
            policy_mode="self",
            scope_chat_types="character",
        )
        _create_rule(db, patterns=["trigger"], governance_policy_id=gp.id)
        result = svc.check_text("trigger word", "user1", chat_type="character")
        assert result.triggered is True


# ── Confirmation Bypass ────────────────────────────────────────


class TestConfirmationBypass:
    def test_request_returns_token(self, db, svc):
        rule = _create_rule(
            db, patterns=["word"],
            bypass_protection="confirmation",
            cooldown_minutes=99999,
        )
        result = svc.request_deactivation(rule.id, "user1")
        assert result["ok"] is True
        assert result["status"] == "awaiting_confirmation"
        assert "confirmation_token" in result
        # Rule should still be enabled
        fetched = db.get_self_monitoring_rule(rule.id)
        assert fetched.enabled is True
        assert fetched.deactivation_confirmation_token == result["confirmation_token"]

    def test_confirm_with_correct_token_disables(self, db, svc):
        rule = _create_rule(
            db, patterns=["word"],
            bypass_protection="confirmation",
            cooldown_minutes=99999,
        )
        req = svc.request_deactivation(rule.id, "user1")
        token = req["confirmation_token"]
        confirm = svc.confirm_deactivation(rule.id, "user1", token)
        assert confirm["ok"] is True
        assert confirm["status"] == "disabled"
        fetched = db.get_self_monitoring_rule(rule.id)
        assert fetched.enabled is False
        assert fetched.deactivation_confirmation_token is None

    def test_confirm_with_wrong_token_fails(self, db, svc):
        rule = _create_rule(
            db, patterns=["word"],
            bypass_protection="confirmation",
            cooldown_minutes=99999,
        )
        svc.request_deactivation(rule.id, "user1")
        result = svc.confirm_deactivation(rule.id, "user1", "wrong_token")
        assert result["ok"] is False
        assert "Invalid" in result["error"]

    def test_confirm_wrong_user_fails(self, db, svc):
        rule = _create_rule(
            db, patterns=["word"],
            bypass_protection="confirmation",
            cooldown_minutes=99999,
        )
        req = svc.request_deactivation(rule.id, "user1")
        token = req["confirmation_token"]
        result = svc.confirm_deactivation(rule.id, "wrong_user", token)
        assert result["ok"] is False


# ── Partner Approval Bypass ────────────────────────────────────


class TestPartnerApprovalBypass:
    def test_request_returns_token_and_partner(self, db, svc):
        rule = _create_rule(
            db, patterns=["word"],
            bypass_protection="partner_approval",
            bypass_partner_user_id="partner1",
            cooldown_minutes=99999,
        )
        result = svc.request_deactivation(rule.id, "user1")
        assert result["ok"] is True
        assert result["status"] == "awaiting_partner_approval"
        assert "confirmation_token" in result
        assert result["partner_user_id"] == "partner1"

    def test_approve_by_correct_partner_disables(self, db, svc):
        rule = _create_rule(
            db, patterns=["word"],
            bypass_protection="partner_approval",
            bypass_partner_user_id="partner1",
            cooldown_minutes=99999,
        )
        req = svc.request_deactivation(rule.id, "user1")
        token = req["confirmation_token"]
        approve = svc.approve_deactivation(rule.id, "partner1", token)
        assert approve["ok"] is True
        assert approve["status"] == "disabled"
        fetched = db.get_self_monitoring_rule(rule.id)
        assert fetched.enabled is False

    def test_approve_by_wrong_partner_fails(self, db, svc):
        rule = _create_rule(
            db, patterns=["word"],
            bypass_protection="partner_approval",
            bypass_partner_user_id="partner1",
            cooldown_minutes=99999,
        )
        req = svc.request_deactivation(rule.id, "user1")
        token = req["confirmation_token"]
        result = svc.approve_deactivation(rule.id, "wrong_partner", token)
        assert result["ok"] is False
        assert "Not the designated partner" in result["error"]

    def test_approve_with_wrong_token_fails(self, db, svc):
        rule = _create_rule(
            db, patterns=["word"],
            bypass_protection="partner_approval",
            bypass_partner_user_id="partner1",
            cooldown_minutes=99999,
        )
        svc.request_deactivation(rule.id, "user1")
        result = svc.approve_deactivation(rule.id, "partner1", "wrong_token")
        assert result["ok"] is False
        assert "Invalid" in result["error"]
