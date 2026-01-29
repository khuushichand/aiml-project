import pytest

from tldw_Server_API.app.core.Moderation import moderation_service as mod_service
from tldw_Server_API.app.core.Moderation.moderation_service import ModerationService


@pytest.mark.unit
def test_invalid_env_values_do_not_crash(monkeypatch):
    monkeypatch.setenv("MODERATION_MAX_SCAN_CHARS", "not-an-int")
    monkeypatch.setenv("MODERATION_MAX_REPLACEMENTS_PER_PATTERN", "nope")
    monkeypatch.setenv("MODERATION_MATCH_WINDOW_CHARS", "bad")
    monkeypatch.setenv("MODERATION_BLOCKLIST_WRITE_DEBOUNCE_MS", "NaN")
    monkeypatch.setattr(mod_service, "load_and_log_configs", lambda: {})
    monkeypatch.setattr(mod_service, "load_comprehensive_config", lambda: None)

    svc = ModerationService()
    assert svc._max_scan_chars == 200000
    assert svc._max_replacements_per_pattern == 1000
    assert svc._match_window_chars == 4096
    assert svc._write_debounce_ms == 0
