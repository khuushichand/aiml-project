import pytest

from tldw_Server_API.app.api.v1.endpoints.audio import audio_streaming


pytestmark = pytest.mark.unit


def test_audio_ws_compat_error_type_enabled_accepts_single_letter_y(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUDIO_WS_COMPAT_ERROR_TYPE", "y")

    assert audio_streaming._audio_ws_compat_error_type_enabled() is True


def test_audio_ws_compat_error_type_enabled_false_when_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUDIO_WS_COMPAT_ERROR_TYPE", "0")

    assert audio_streaming._audio_ws_compat_error_type_enabled() is False
