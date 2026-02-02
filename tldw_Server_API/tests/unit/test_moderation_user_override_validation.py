import json

import pytest

from tldw_Server_API.app.core.Moderation.moderation_service import ModerationService


@pytest.mark.unit
def test_set_user_override_rejects_invalid_action(tmp_path):
    svc = ModerationService()
    overrides_path = tmp_path / "overrides.json"
    svc._user_overrides_path = str(overrides_path)

    res = svc.set_user_override("user1", {"input_action": "blok"})
    assert res["ok"] is False
    assert "invalid input_action" in (res.get("error") or "")
    assert overrides_path.exists() is False


@pytest.mark.unit
def test_load_user_overrides_sanitizes_invalid_action(tmp_path):
    overrides_path = tmp_path / "overrides.json"
    overrides_path.write_text(json.dumps({"user1": {"input_action": "blok", "output_action": "warn"}}))

    svc = ModerationService()
    svc._user_overrides_path = str(overrides_path)
    loaded = svc._load_user_overrides()

    user_override = loaded.get("user1") or {}
    assert "input_action" not in user_override
    assert user_override.get("output_action") == "warn"
