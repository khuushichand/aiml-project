import pytest

from tldw_Server_API.app.core.Claims_Extraction import claims_service


@pytest.mark.unit
def test_claims_settings_snapshot_uses_runtime_resolved_values(monkeypatch):
    monkeypatch.setitem(claims_service.settings, "CLAIMS_PROMPT_VALIDATION_MODE", "invalid-mode")
    monkeypatch.setitem(claims_service.settings, "CLAIMS_PROMPT_VALIDATION_STRICT", "yes")
    monkeypatch.setitem(claims_service.settings, "CLAIMS_ALIGNMENT_MODE", "not-a-mode")
    monkeypatch.setitem(claims_service.settings, "CLAIMS_ALIGNMENT_THRESHOLD", 2.5)
    monkeypatch.setitem(claims_service.settings, "CLAIMS_CONTEXT_WINDOW_CHARS", -42)
    monkeypatch.setitem(claims_service.settings, "CLAIMS_EXTRACTION_PASSES", 0)

    snapshot = claims_service._claims_settings_snapshot()

    assert snapshot["claims_prompt_validation_mode"] == "warning"
    assert snapshot["claims_prompt_validation_strict"] is True
    assert snapshot["claims_alignment_mode"] == "fuzzy"
    assert snapshot["claims_alignment_threshold"] == 1.0
    assert snapshot["claims_context_window_chars"] == 0
    assert snapshot["claims_extraction_passes"] == 1
