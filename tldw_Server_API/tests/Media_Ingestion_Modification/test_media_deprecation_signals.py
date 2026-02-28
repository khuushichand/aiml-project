import importlib.util
from pathlib import Path
import sys


def _load_signals_module():
    module_path = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "api"
        / "v1"
        / "endpoints"
        / "media"
        / "deprecation_signals.py"
    )
    spec = importlib.util.spec_from_file_location(
        "media_deprecation_signals_test_module",
        module_path,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_build_media_legacy_signal_includes_standard_headers():
    signals_module = _load_signals_module()
    signal = signals_module.build_media_legacy_signal(
        successor="/api/v1/media/process-videos",
        warning_code="legacy_compat_path",
    )
    assert signal.headers["Deprecation"] == "true"
    assert "Sunset" in signal.headers
    assert (
        signal.headers["Link"]
        == "</api/v1/media/process-videos>; rel=successor-version"
    )
    assert signal.payload["warning"] == "deprecated_endpoint"
    assert signal.payload["code"] == "legacy_compat_path"
    assert signal.payload["successor"] == "/api/v1/media/process-videos"


def test_apply_media_legacy_headers_updates_response_headers():
    signals_module = _load_signals_module()
    signal = signals_module.build_media_legacy_signal(
        successor="/api/v1/media/process-videos",
        warning_code="legacy_compat_path",
    )
    response = type("ResponseStub", (), {"headers": {}})()
    updated = signals_module.apply_media_legacy_headers(response, signal)
    assert updated is response
    assert response.headers.get("Deprecation") == "true"
    assert "Sunset" in response.headers
