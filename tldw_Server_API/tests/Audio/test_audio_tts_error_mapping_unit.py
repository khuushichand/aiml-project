"""Unit tests for API-facing TTS exception mapping."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from tldw_Server_API.app.core.Audio.tts_service import _raise_for_tts_error
from tldw_Server_API.app.core.TTS.tts_exceptions import (
    TTSModelLoadError,
    TTSModelNotFoundError,
    TTSNetworkError,
    TTSProviderInitializationError,
    TTSProviderUnavailableError,
    TTSResourceError,
    TTSTimeoutError,
)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("exc", "expected_status", "expected_message"),
    [
        (
            TTSProviderInitializationError("provider init failed", provider="kokoro"),
            503,
            "TTS service unavailable",
        ),
        (
            TTSModelLoadError("model load failed", provider="kokoro"),
            503,
            "TTS model unavailable",
        ),
        (
            TTSResourceError("resource unavailable", provider="kokoro"),
            503,
            "TTS service unavailable",
        ),
        (
            TTSProviderUnavailableError("provider unavailable", provider="openai"),
            503,
            "TTS provider unavailable",
        ),
        (
            TTSModelNotFoundError("missing model", provider="kokoro"),
            404,
            "Requested TTS model not found",
        ),
        (
            TTSNetworkError("network issue", provider="openai"),
            502,
            "TTS provider request failed",
        ),
        (
            TTSTimeoutError("provider timeout", provider="openai"),
            504,
            "TTS provider timed out",
        ),
    ],
)
def test_raise_for_tts_error_maps_extended_provider_and_runtime_failures(exc, expected_status, expected_message):
    with pytest.raises(HTTPException) as raised:
        _raise_for_tts_error(exc, request_id="req-123")

    assert raised.value.status_code == expected_status  # nosec B101
    assert raised.value.detail == {  # nosec B101
        "message": expected_message,
        "request_id": "req-123",
    }
