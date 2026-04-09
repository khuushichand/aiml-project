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
            _ = None


@pytest.mark.unit
def test_update_settings_can_clear_runtime_overrides():
    svc = ModerationService()
    # Set an override, then clear it explicitly
    svc.update_settings(pii_enabled=True)
    assert svc.get_settings()["pii_enabled"] is True
    svc.update_settings(pii_enabled=None, clear_pii=True)
    assert "pii_enabled" not in svc._runtime_override
    assert svc.get_settings()["pii_enabled"] is None


@pytest.mark.unit
def test_update_settings_persist_failure_does_not_mutate_runtime_override(monkeypatch, tmp_path):
    """Persistence failures are noncritical: the in-memory override is still applied."""
    svc = ModerationService()
    svc._runtime_overrides_path = str(tmp_path / "runtime_overrides.json")
    svc._runtime_override = {"pii_enabled": False}

    def _raise_disk_full(*_args, **_kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(
        "tldw_Server_API.app.core.Moderation.moderation_service.os.fsync",
        _raise_disk_full,
    )

    # Should NOT raise; persistence failure is caught and logged.
    result = svc.update_settings(pii_enabled=True, persist=True)
    assert result is not None
    # The in-memory override should still be applied despite persistence failure.
    assert svc._runtime_override.get("pii_enabled") is True


@pytest.mark.unit
def test_runtime_overrides_ignore_invalid_string():
    svc = ModerationService()
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmp:
        json.dump({"pii_enabled": "nope"}, tmp)
        tmp_path = tmp.name
    try:
        svc._runtime_override = {}
        svc._runtime_overrides_path = tmp_path
        svc._load_runtime_overrides_file()
        assert "pii_enabled" not in svc._runtime_override
        assert svc.get_settings()["pii_enabled"] is None
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            _ = None
