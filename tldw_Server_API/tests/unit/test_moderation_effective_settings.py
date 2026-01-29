import re

import pytest

from tldw_Server_API.app.core.Moderation.moderation_service import (
    ModerationPolicy,
    ModerationService,
    PatternRule,
)


@pytest.mark.unit
def test_effective_pii_respects_categories_enabled():
    svc = ModerationService()
    pii_rule = PatternRule(
        regex=re.compile(r"\\S+@\\S+"),
        action="redact",
        replacement="[PII]",
        categories={"pii", "pii_email"},
    )

    svc._global_policy = ModerationPolicy(
        enabled=True,
        input_enabled=True,
        output_enabled=True,
        input_action="block",
        output_action="redact",
        redact_replacement="[REDACTED]",
        per_user_overrides=False,
        block_patterns=[pii_rule],
        categories_enabled={"confidential"},
    )
    settings = svc.get_settings()
    assert settings["effective"]["pii_enabled"] is False

    svc._global_policy = ModerationPolicy(
        enabled=True,
        input_enabled=True,
        output_enabled=True,
        input_action="block",
        output_action="redact",
        redact_replacement="[REDACTED]",
        per_user_overrides=False,
        block_patterns=[pii_rule],
        categories_enabled={"pii_email"},
    )
    settings = svc.get_settings()
    assert settings["effective"]["pii_enabled"] is True


@pytest.mark.unit
def test_category_reporting_respects_allowlist():
    svc = ModerationService()
    rule = PatternRule(
        regex=re.compile(r"secret", re.IGNORECASE),
        action="block",
        categories={"pii", "confidential"},
    )
    pol = ModerationPolicy(
        enabled=True,
        input_enabled=True,
        output_enabled=True,
        input_action="block",
        output_action="redact",
        redact_replacement="[REDACTED]",
        per_user_overrides=False,
        block_patterns=[rule],
        categories_enabled={"pii"},
    )
    act, _red, _pattern, cat = svc.evaluate_action("secret", pol, "input")
    assert act == "block"
    assert cat == "pii"
