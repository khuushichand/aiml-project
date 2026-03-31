from fastapi import HTTPException

import pytest

from tldw_Server_API.app.api.v1.endpoints.audio import audio_health


@pytest.mark.asyncio
async def test_collect_setup_stt_health_normalizes_http_exception(mocker):
    mocker.patch.object(
        audio_health,
        "get_stt_health",
        side_effect=HTTPException(
            status_code=400,
            detail={"message": "Invalid transcription model identifier"},
        ),
    )

    result = await audio_health.collect_setup_stt_health(model="bad-model")

    assert result["usable"] is False
    assert result["available"] is False
    assert result["status_code"] == 400
    assert result["message"] == "Invalid transcription model identifier"
    assert result["model"] == "bad-model"


@pytest.mark.asyncio
async def test_collect_setup_tts_health_normalizes_service_bootstrap_failure(mocker):
    mocker.patch.object(
        audio_health,
        "get_tts_service",
        side_effect=RuntimeError("adapter bootstrap exploded"),
    )

    result = await audio_health.collect_setup_tts_health()

    assert result["status"] == "error"
    assert result["providers"] == {"total": 0, "available": 0, "details": {}}
    assert result["message"] == "TTS health check failed"
    assert result["status_code"] == 500


@pytest.mark.asyncio
async def test_get_stt_health_sanitizes_suspicious_runtime_strings(mocker):
    mocker.patch(
        "tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Lib.parse_transcription_model",
        return_value=("whisper", None, None),
    )
    mocker.patch(
        "tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Transcription_Lib.validate_whisper_model_identifier",
        side_effect=lambda value: value,
    )
    mocker.patch(
        "tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Files.check_transcription_model_status",
        return_value={
            "available": False,
            "usable": False,
            "message": "Traceback: /Users/private/model.bin\nRuntimeError: boom",
            "details": "/Users/private/model.bin",
            "model": "whisper-1",
        },
    )

    result = await audio_health.get_stt_health(
        audio_health._build_internal_health_request("/api/v1/audio/transcriptions/health"),
        model="whisper-1",
        warm=False,
    )

    assert result["message"] == "Internal health diagnostics were suppressed."
    assert "details" not in result
