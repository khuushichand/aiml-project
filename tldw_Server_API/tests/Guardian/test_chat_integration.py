"""
test_chat_integration.py

Tests for guardian + self-monitoring integration with the chat pipeline
(moderate_input_messages) and the GuardianModerationProxy.
"""
from __future__ import annotations

import re
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from tldw_Server_API.app.core.DB_Management.Guardian_DB import GuardianDB
from tldw_Server_API.app.core.Moderation.moderation_service import (
    ModerationPolicy,
    ModerationService,
    PatternRule,
)
from tldw_Server_API.app.core.Moderation.supervised_policy import (
    GuardianModerationProxy,
    SupervisedPolicyEngine,
)
from tldw_Server_API.app.core.Monitoring.self_monitoring_service import (
    SelfMonitoringService,
)
from tldw_Server_API.app.core.Chat.chat_service import moderate_input_messages


# ── Fixtures ──────────────────────────────────────────────────


@pytest.fixture
def db(tmp_path):
    return GuardianDB(str(tmp_path / "test_guardian.db"))


@pytest.fixture
def engine(db):
    return SupervisedPolicyEngine(db)


@pytest.fixture
def selfmon(db):
    return SelfMonitoringService(db)


def _setup_active_relationship(db, guardian="guardian1", dependent="child1"):
    rel = db.create_relationship(guardian, dependent)
    db.accept_relationship(rel.id)
    return rel


class _FakeModerationService:
    """Minimal moderation service that evaluates PatternRule objects from policy.

    Real ModerationService.__init__ loads from config, which is undesirable
    in unit tests. This fake implements just enough for moderate_input_messages.
    """

    def __init__(self, base_policy: ModerationPolicy):
        self._policy = base_policy

    def get_effective_policy(self, user_id=None):
        return self._policy

    def evaluate_action_with_match(self, text, policy, phase):
        """Evaluate text against policy patterns and return (action, redacted, pattern, category, span)."""
        if not policy.enabled or not text or not policy.block_patterns:
            return "pass", None, None, None, None
        for rule in policy.block_patterns:
            if not isinstance(rule, PatternRule):
                continue
            m = rule.regex.search(text)
            if m:
                action = rule.action or (policy.input_action if phase == "input" else policy.output_action)
                redacted = None
                if action == "redact":
                    repl = rule.replacement or policy.redact_replacement or "[REDACTED]"
                    redacted = rule.regex.sub(repl, text)
                cats = rule.categories or set()
                cat = next(iter(cats), None)
                return action, redacted, rule.regex.pattern, cat, (m.start(), m.end())
        return "pass", None, None, None, None

    def check_text(self, text, policy, phase=None):
        if not policy.enabled or not text or not policy.block_patterns:
            return False, None
        for rule in policy.block_patterns:
            if not isinstance(rule, PatternRule):
                continue
            if rule.regex.search(text):
                return True, text[:50]
        return False, None

    def redact_text(self, text, policy):
        if not text or not policy.block_patterns:
            return text
        result = text
        for rule in policy.block_patterns:
            if not isinstance(rule, PatternRule):
                continue
            repl = rule.replacement or policy.redact_replacement or "[REDACTED]"
            result = rule.regex.sub(repl, result)
        return result

    def build_sanitized_snippet(self, text, policy, match_span, pattern=None):
        return text[:50] if text else None


def _make_moderation_service(policy=None):
    if policy is None:
        policy = ModerationPolicy(enabled=False)
    return _FakeModerationService(policy)


def _make_request_data(content="Hello world"):
    msg = SimpleNamespace(role="user", content=content, type="text")
    return SimpleNamespace(messages=[msg], conversation_id=None)


def _make_request(user_id=None):
    state = SimpleNamespace(user_id=user_id, team_ids=None, org_ids=None)
    return SimpleNamespace(state=state)


def _make_metrics():
    m = MagicMock()
    m.track_moderation_input = MagicMock()
    return m


# ── 1. Guardian overlay blocks input ─────────────────────────


class TestGuardianOverlayBlocksInput:
    @pytest.mark.asyncio
    async def test_block_policy_raises_400(self, db, engine):
        """A supervised policy with action=block should cause HTTPException(400)."""
        rel = _setup_active_relationship(db)
        db.create_policy(
            relationship_id=rel.id,
            pattern="bad word",
            action="block",
            severity="critical",
        )

        moderation_svc = _make_moderation_service(ModerationPolicy(enabled=False))
        request_data = _make_request_data("this has bad word in it")
        request = _make_request(user_id="child1")

        with pytest.raises(HTTPException) as exc_info:
            await moderate_input_messages(
                request_data=request_data,
                request=request,
                moderation_service=moderation_svc,
                topic_monitoring_service=None,
                metrics=_make_metrics(),
                audit_service=None,
                audit_context=None,
                client_id="client1",
                supervised_policy_engine=engine,
                dependent_user_id="child1",
            )
        assert exc_info.value.status_code == 400


# ── 2. Guardian overlay redacts input ────────────────────────


class TestGuardianOverlayRedactsInput:
    @pytest.mark.asyncio
    async def test_redact_policy_modifies_text(self, db, engine):
        """A supervised policy with action=redact should redact the content in-place."""
        rel = _setup_active_relationship(db)
        db.create_policy(
            relationship_id=rel.id,
            category="profanity",
            pattern="secret",
            action="redact",
            severity="warning",
        )

        moderation_svc = _make_moderation_service(ModerationPolicy(enabled=False))
        request_data = _make_request_data("the secret code is 42")
        request = _make_request(user_id="child1")

        await moderate_input_messages(
            request_data=request_data,
            request=request,
            moderation_service=moderation_svc,
            topic_monitoring_service=None,
            metrics=_make_metrics(),
            audit_service=None,
            audit_context=None,
            client_id="client1",
            supervised_policy_engine=engine,
            dependent_user_id="child1",
        )

        final_text = request_data.messages[0].content
        assert "secret" not in final_text
        assert "[REDACTED]" in final_text


# ── 3. Guardian overlay passes clean text ────────────────────


class TestGuardianOverlayPassesClean:
    @pytest.mark.asyncio
    async def test_clean_text_passes_through(self, db, engine):
        """Text that doesn't match any guardian policy should pass unchanged."""
        rel = _setup_active_relationship(db)
        db.create_policy(
            relationship_id=rel.id,
            category="violence",
            pattern="violent content",
            action="block",
            severity="critical",
        )

        moderation_svc = _make_moderation_service(ModerationPolicy(enabled=False))
        original = "this is perfectly fine text"
        request_data = _make_request_data(original)
        request = _make_request(user_id="child1")

        await moderate_input_messages(
            request_data=request_data,
            request=request,
            moderation_service=moderation_svc,
            topic_monitoring_service=None,
            metrics=_make_metrics(),
            audit_service=None,
            audit_context=None,
            client_id="client1",
            supervised_policy_engine=engine,
            dependent_user_id="child1",
        )

        assert request_data.messages[0].content == original


# ── 4. Self-monitoring blocks input ──────────────────────────


class TestSelfMonitoringBlocksInput:
    @pytest.mark.asyncio
    async def test_block_rule_raises_400(self, db, selfmon):
        """Self-monitoring rule with action=block should raise HTTPException(400)."""
        db.create_self_monitoring_rule(
            user_id="user1",
            name="doom_scroll_block",
            category="compulsive",
            patterns=["doom scrolling"],
            action="block",
            block_message="You configured this to be blocked.",
        )

        moderation_svc = _make_moderation_service(ModerationPolicy(enabled=False))
        request_data = _make_request_data("I've been doom scrolling all day")
        request = _make_request(user_id="user1")

        with pytest.raises(HTTPException) as exc_info:
            await moderate_input_messages(
                request_data=request_data,
                request=request,
                moderation_service=moderation_svc,
                topic_monitoring_service=None,
                metrics=_make_metrics(),
                audit_service=None,
                audit_context=None,
                client_id="user1",
                self_monitoring_service=selfmon,
            )
        assert exc_info.value.status_code == 400


# ── 5. Self-monitoring notifies but passes ───────────────────


class TestSelfMonitoringNotifyPasses:
    @pytest.mark.asyncio
    async def test_notify_rule_passes_text(self, db, selfmon):
        """Self-monitoring rule with action=notify should pass text through unchanged."""
        db.create_self_monitoring_rule(
            user_id="user1",
            name="late_night_notify",
            category="awareness",
            patterns=["late night"],
            action="notify",
        )

        moderation_svc = _make_moderation_service(ModerationPolicy(enabled=False))
        original = "I'm having a late night chat"
        request_data = _make_request_data(original)
        request = _make_request(user_id="user1")

        await moderate_input_messages(
            request_data=request_data,
            request=request,
            moderation_service=moderation_svc,
            topic_monitoring_service=None,
            metrics=_make_metrics(),
            audit_service=None,
            audit_context=None,
            client_id="user1",
            self_monitoring_service=selfmon,
        )

        assert request_data.messages[0].content == original


# ── 6. Feature flags ─────────────────────────────────────────


class TestFeatureFlagsDisable:
    def test_is_guardian_enabled_returns_true_by_default(self):
        from tldw_Server_API.app.core.feature_flags import is_guardian_enabled
        assert is_guardian_enabled() is True

    def test_is_self_monitoring_enabled_returns_true_by_default(self):
        from tldw_Server_API.app.core.feature_flags import is_self_monitoring_enabled
        assert is_self_monitoring_enabled() is True

    @patch("tldw_Server_API.app.core.feature_flags.settings")
    def test_guardian_disabled_via_settings(self, mock_settings):
        mock_settings.get.return_value = False
        from tldw_Server_API.app.core.feature_flags import is_guardian_enabled
        assert is_guardian_enabled() is False

    @patch("tldw_Server_API.app.core.feature_flags.settings")
    def test_self_monitoring_disabled_via_settings(self, mock_settings):
        mock_settings.get.return_value = False
        from tldw_Server_API.app.core.feature_flags import is_self_monitoring_enabled
        assert is_self_monitoring_enabled() is False


# ── 7. No guardian DB = graceful skip ────────────────────────


class TestNoGuardianGracefulSkip:
    @pytest.mark.asyncio
    async def test_none_services_normal_moderation(self):
        """When guardian services are None, normal moderation should still work."""
        moderation_svc = _make_moderation_service(ModerationPolicy(enabled=False))
        original = "normal text"
        request_data = _make_request_data(original)
        request = _make_request(user_id="user1")

        await moderate_input_messages(
            request_data=request_data,
            request=request,
            moderation_service=moderation_svc,
            topic_monitoring_service=None,
            metrics=_make_metrics(),
            audit_service=None,
            audit_context=None,
            client_id="client1",
            supervised_policy_engine=None,
            self_monitoring_service=None,
            dependent_user_id=None,
        )

        assert request_data.messages[0].content == original


# ── 8. GuardianModerationProxy ───────────────────────────────


class TestGuardianModerationProxy:
    def test_proxy_overlays_policy(self, db, engine):
        """Proxy should overlay guardian rules onto the base policy."""
        rel = _setup_active_relationship(db)
        db.create_policy(
            relationship_id=rel.id,
            category="violence",
            pattern="attack",
            action="block",
            severity="critical",
        )

        base_svc = _make_moderation_service(ModerationPolicy(enabled=False))
        proxy = GuardianModerationProxy(base_svc, engine, "child1")
        result_policy = proxy.get_effective_policy("child1")

        assert result_policy.enabled is True
        assert len(result_policy.block_patterns) >= 1
        pattern_strs = [r.regex.pattern for r in result_policy.block_patterns]
        assert any("attack" in p for p in pattern_strs)

    def test_proxy_delegates_other_methods(self, db, engine):
        """Proxy should delegate non-overridden methods to base service."""
        base_svc = _make_moderation_service(ModerationPolicy(enabled=False))
        proxy = GuardianModerationProxy(base_svc, engine, "child1")
        result = proxy.check_text("test", ModerationPolicy(), "input")
        assert result == (False, None)

    def test_proxy_handles_engine_error_gracefully(self, db):
        """If engine raises, proxy should return base policy."""
        engine = MagicMock(spec=SupervisedPolicyEngine)
        engine.build_moderation_policy_overlay.side_effect = RuntimeError("boom")

        base_policy = ModerationPolicy(enabled=False)
        base_svc = _make_moderation_service(base_policy)

        proxy = GuardianModerationProxy(base_svc, engine, "child1")
        result = proxy.get_effective_policy("child1")

        assert result is base_policy


# ── 9. Combined guardian + self-monitoring ───────────────────


class TestCombinedGuardianAndSelfMonitoring:
    @pytest.mark.asyncio
    async def test_both_services_active(self, db, engine, selfmon):
        """Both guardian and self-monitoring can be active simultaneously."""
        rel = _setup_active_relationship(db)
        db.create_policy(
            relationship_id=rel.id,
            category="violence",
            pattern="violent content",
            action="block",
            severity="critical",
        )
        db.create_self_monitoring_rule(
            user_id="child1",
            name="late_night",
            category="awareness",
            patterns=["late night"],
            action="notify",
        )

        moderation_svc = _make_moderation_service(ModerationPolicy(enabled=False))
        request_data = _make_request_data("late night study session")
        request = _make_request(user_id="child1")

        await moderate_input_messages(
            request_data=request_data,
            request=request,
            moderation_service=moderation_svc,
            topic_monitoring_service=None,
            metrics=_make_metrics(),
            audit_service=None,
            audit_context=None,
            client_id="child1",
            supervised_policy_engine=engine,
            self_monitoring_service=selfmon,
            dependent_user_id="child1",
        )

        assert request_data.messages[0].content == "late night study session"

    @pytest.mark.asyncio
    async def test_self_monitoring_block_takes_priority(self, db, engine, selfmon):
        """Self-monitoring block fires before guardian overlay moderation."""
        rel = _setup_active_relationship(db)
        db.create_policy(
            relationship_id=rel.id,
            category="profanity",
            pattern="secret",
            action="redact",
            severity="warning",
        )
        db.create_self_monitoring_rule(
            user_id="child1",
            name="doom_block",
            category="compulsive",
            patterns=["doom scrolling"],
            action="block",
            block_message="Blocked by self-monitoring.",
        )

        moderation_svc = _make_moderation_service(ModerationPolicy(enabled=False))
        request_data = _make_request_data("secret doom scrolling")
        request = _make_request(user_id="child1")

        with pytest.raises(HTTPException) as exc_info:
            await moderate_input_messages(
                request_data=request_data,
                request=request,
                moderation_service=moderation_svc,
                topic_monitoring_service=None,
                metrics=_make_metrics(),
                audit_service=None,
                audit_context=None,
                client_id="child1",
                supervised_policy_engine=engine,
                self_monitoring_service=selfmon,
                dependent_user_id="child1",
            )
        assert exc_info.value.status_code == 400
