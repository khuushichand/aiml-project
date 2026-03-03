from __future__ import annotations

from tldw_Server_API.app.core.deprecations.runtime_registry import (
    load_compat_registry,
    log_runtime_deprecation,
    reset_runtime_deprecation_cycle,
)


def test_all_runtime_compat_paths_registered():
    registry = load_compat_registry()
    assert "web_scraping_legacy_fallback" in registry  # nosec B101
    assert "llm_chat_legacy_session" in registry  # nosec B101


def test_deprecation_registry_emits_once_per_request_cycle(monkeypatch):
    emitted: list[str] = []

    def _capture_warning(message: str, *args, **kwargs):
        _ = (args, kwargs)
        emitted.append(str(message))

    monkeypatch.setattr(
        "tldw_Server_API.app.core.deprecations.runtime_registry.logger.warning",
        _capture_warning,
    )

    reset_runtime_deprecation_cycle()
    log_runtime_deprecation("web_scraping_legacy_fallback")
    log_runtime_deprecation("web_scraping_legacy_fallback")
    assert len(emitted) == 1  # nosec B101

    reset_runtime_deprecation_cycle()
    log_runtime_deprecation("web_scraping_legacy_fallback")
    assert len(emitted) == 2  # nosec B101
