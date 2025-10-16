import os
import tempfile
from typing import Optional, Set

import pytest

from tldw_Server_API.app.core.Moderation.moderation_service import ModerationService, ModerationPolicy, PatternRule


@pytest.mark.unit
def test_parse_line_with_categories_suffix_after_action():
    svc = ModerationService()
    # Format: pattern -> action #cats
    expr, action, repl, cats = svc._parse_rule_line("/leak\\d+/ -> block #pii,confidential")
    assert expr == "/leak\\d+/"
    assert action == "block"
    assert repl is None
    assert cats == {"pii", "confidential"}

    expr2, action2, repl2, cats2 = svc._parse_rule_line("secret token -> redact:[MASK] #pii")
    assert expr2 == "secret token"
    assert action2 == "redact"
    assert repl2 == "[MASK]"
    assert cats2 == {"pii"}


@pytest.mark.unit
def test_load_block_patterns_and_evaluate_actions():
    svc = ModerationService()
    # Create a temporary blocklist with categories after action
    lines = [
        "/forbidden/ -> block #confidential",
        "secret -> redact:[MASK] #pii",
    ]
    with tempfile.NamedTemporaryFile(mode="w+", delete=False) as tmp:
        tmp.write("\n".join(lines) + "\n")
        tmp_path = tmp.name

    try:
        rules = svc._load_block_patterns(tmp_path)
        assert isinstance(rules, list) and len(rules) == 2
        # Ensure actions and categories are bound
        r0: PatternRule = rules[0]
        r1: PatternRule = rules[1]
        assert isinstance(r0, PatternRule) and isinstance(r1, PatternRule)
        assert r0.action == "block" and r0.categories == {"confidential"}
        assert r1.action == "redact" and r1.replacement == "[MASK]" and r1.categories == {"pii"}

        # Build a policy to evaluate
        pol = ModerationPolicy(
            enabled=True,
            input_enabled=True,
            output_enabled=True,
            input_action="block",
            output_action="redact",
            redact_replacement="[REDACTED]",
            per_user_overrides=False,
            block_patterns=rules,
            categories_enabled=None,
        )

        # Block action fires on input
        act, red, sample, cat = svc.evaluate_action("this is forbidden", pol, "input")
        assert act == "block" and sample and (cat == "confidential")

        # Redact action applies on output
        act2, red2, sample2, cat2 = svc.evaluate_action("found secret token", pol, "output")
        assert act2 == "redact" and red2 and "[MASK]" in red2
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass

@pytest.mark.unit
def test_warn_with_categories_and_category_label():
    svc = ModerationService()
    # Warning rule with category
    lines = [
        "/minor issue/ -> warn #confidential",
    ]
    with tempfile.NamedTemporaryFile(mode="w+", delete=False) as tmp:
        tmp.write("\n".join(lines) + "\n")
        tmp_path = tmp.name

    try:
        rules = svc._load_block_patterns(tmp_path)
        assert len(rules) == 1
        pol = ModerationPolicy(
            enabled=True,
            input_enabled=True,
            output_enabled=True,
            input_action="block",
            output_action="redact",
            redact_replacement="[REDACTED]",
            per_user_overrides=False,
            block_patterns=rules,
            categories_enabled=None,
        )
        act, red, sample, cat = svc.evaluate_action("this is a minor issue in docs", pol, "input")
        assert act == "warn" and sample and cat == "confidential"
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


@pytest.mark.unit
def test_invalid_and_dangerous_regex_lines_are_skipped():
    svc = ModerationService()
    lines = [
        "validliteral",
        "/(unclosed/ -> block #pii",  # invalid regex
        "/(a+)+$/ -> block",           # nested quantifiers (dangerous)
    ]
    with tempfile.NamedTemporaryFile(mode="w+", delete=False) as tmp:
        tmp.write("\n".join(lines) + "\n")
        tmp_path = tmp.name
    try:
        rules = svc._load_block_patterns(tmp_path)
        # Only the literal should survive
        assert len(rules) == 1
        # Ensure it actually matches
        pol = ModerationPolicy(enabled=True, block_patterns=rules)
        flagged, sample = svc.check_text("This contains validliteral term", pol)
        assert flagged and sample
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


@pytest.mark.unit
def test_replacement_limits_are_enforced():
    svc = ModerationService()
    # Create a simple redact rule
    lines = [
        "secret -> redact:[MASK]",
    ]
    with tempfile.NamedTemporaryFile(mode="w+", delete=False) as tmp:
        tmp.write("\n".join(lines) + "\n")
        tmp_path = tmp.name
    try:
        rules = svc._load_block_patterns(tmp_path)
        pol = ModerationPolicy(
            enabled=True,
            input_enabled=True,
            output_enabled=True,
            input_action="block",
            output_action="redact",
            redact_replacement="[REDACTED]",
            per_user_overrides=False,
            block_patterns=rules,
        )
        # Limit to one replacement per pattern
        svc._max_replacements_per_pattern = 1
        text = "secret and another secret and one more secret"
        red = svc.redact_text(text, pol)
        # Exactly one replacement expected with [MASK]
        assert red.count("[MASK]") == 1
        assert red.count("secret") >= 2
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
