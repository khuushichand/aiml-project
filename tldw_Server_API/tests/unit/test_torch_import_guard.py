from __future__ import annotations

import pytest

from tldw_Server_API.app.core.Utils import torch_import_guard as tig


def _clear_probe_cache() -> None:
    tig._probe_torch_import_once.cache_clear()


def test_preflight_reports_failure_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Result:
        returncode = 1
        stderr = "fatal torch error"
        stdout = ""

    monkeypatch.delenv("TLDW_SKIP_TORCH_IMPORT_PREFLIGHT", raising=False)
    monkeypatch.setattr(tig.subprocess, "run", lambda *args, **kwargs: _Result())
    _clear_probe_cache()

    ok, reason = tig.can_import_torch_safely()

    assert ok is False
    assert "fatal torch error" in reason


def test_preflight_can_be_skipped_with_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TLDW_SKIP_TORCH_IMPORT_PREFLIGHT", "1")
    _clear_probe_cache()

    ok, reason = tig.can_import_torch_safely()

    assert ok is True
    assert "preflight skipped" in reason


def test_safe_import_raises_when_preflight_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tig, "can_import_torch_safely", lambda: (False, "probe failed"))

    with pytest.raises(ImportError, match="probe failed"):
        tig.safe_import_torch()

