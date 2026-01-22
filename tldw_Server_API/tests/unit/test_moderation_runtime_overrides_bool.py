import json
import os
import tempfile

import pytest

from tldw_Server_API.app.core.Moderation.moderation_service import ModerationService


@pytest.mark.unit
def test_runtime_overrides_parse_false_string():
    svc = ModerationService()
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmp:
        json.dump({"pii_enabled": "false"}, tmp)
        tmp_path = tmp.name
    try:
        svc._runtime_override = {}
        svc._runtime_overrides_path = tmp_path
        svc._load_runtime_overrides_file()
        assert svc._runtime_override.get("pii_enabled") is False
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
