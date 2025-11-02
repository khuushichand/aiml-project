import os
import tempfile

import pytest

from tldw_Server_API.app.core.Moderation.moderation_service import ModerationService, ModerationPolicy


@pytest.mark.unit
def test_redact_text_respects_categories_enabled():
    svc = ModerationService()
    lines = [
        "secret -> redact:[MASK] #pii",
        "confidential -> redact:[CENSORED] #confidential",
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
            categories_enabled={"pii"},
        )
        text = "secret and confidential info"
        red = svc.redact_text(text, pol)
        # Only the PII-tagged rule should apply
        assert "[MASK]" in red
        assert "confidential" in red  # should not be redacted
    finally:
        try:
            os.unlink(path)
        except Exception:
            pass
