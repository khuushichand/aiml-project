import os
import tempfile

import pytest

from tldw_Server_API.app.core.Moderation.moderation_service import ModerationService, ModerationPolicy


@pytest.mark.unit
def test_check_text_returns_sanitized_snippet_not_pattern():
    svc = ModerationService()
    lines = [
        "/token\\s*[=:]\\s*([A-Za-z0-9_-]{8,})/ -> block #confidential",
        "secret -> redact:[MASK] #pii",
    ]
    with tempfile.NamedTemporaryFile(mode="w+", delete=False) as tmp:
        tmp.write("\n".join(lines) + "\n")
        path = tmp.name
    try:
        rules = svc._load_block_patterns(path)
        pol = ModerationPolicy(
            enabled=True,
            input_enabled=True,
            output_enabled=True,
            input_action="block",
            output_action="redact",
            redact_replacement="[REDACTED]",
            per_user_overrides=False,
            block_patterns=rules,
            categories_enabled={"pii", "confidential"},
        )
        text = "please do not reveal token=ABCDEFGH and also keep this secret safe"
        flagged, sample = svc.check_text(text, pol)
        assert flagged is True
        assert sample is not None
        # The sample is sanitized; should not include the actual token or word 'secret'
        assert "ABCDEFGH" not in sample
        assert "secret" not in sample
        # But it should include the redaction marker
        assert ("[MASK]" in sample) or ("[REDACTED]" in sample)
    finally:
        try:
            os.unlink(path)
        except Exception:
            pass


@pytest.mark.unit
def test_check_text_respects_phase_enablement():
    svc = ModerationService()
    lines = [
        "secret -> block",
    ]
    with tempfile.NamedTemporaryFile(mode="w+", delete=False) as tmp:
        tmp.write("\n".join(lines) + "\n")
        path = tmp.name
    try:
        rules = svc._load_block_patterns(path)
        pol = ModerationPolicy(
            enabled=True,
            input_enabled=False,
            output_enabled=True,
            input_action="block",
            output_action="redact",
            redact_replacement="[REDACTED]",
            per_user_overrides=False,
            block_patterns=rules,
            categories_enabled=None,
        )
        flagged_in, _ = svc.check_text("secret", pol, phase="input")
        flagged_out, _ = svc.check_text("secret", pol, phase="output")
        assert flagged_in is False
        assert flagged_out is True
    finally:
        try:
            os.unlink(path)
        except Exception:
            pass


@pytest.mark.unit
def test_check_text_detects_long_match_across_window():
    svc = ModerationService()
    lines = [
        "/A.*B/ -> block",
    ]
    with tempfile.NamedTemporaryFile(mode="w+", delete=False) as tmp:
        tmp.write("\n".join(lines) + "\n")
        path = tmp.name
    try:
        rules = svc._load_block_patterns(path)
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
        svc._max_scan_chars = 50
        svc._match_window_chars = 5
        text = ("x" * 40) + "A" + ("x" * 90) + "B"
        flagged, _ = svc.check_text(text, pol, phase="input")
        assert flagged is True
    finally:
        try:
            os.unlink(path)
        except Exception:
            pass
