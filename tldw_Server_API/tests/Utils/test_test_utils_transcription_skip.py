import sys
from types import ModuleType

import pytest

from tldw_Server_API.tests.test_utils import (
    skip_if_transcription_model_unavailable,
    skip_if_whisper_model_not_cached_locally,
)


@pytest.mark.unit
def test_skip_if_transcription_model_unavailable_allows_usable_on_demand_model(monkeypatch):
    fake_audio_files = ModuleType("Audio_Files")
    fake_audio_files.check_transcription_model_status = lambda _model_name: {
        "available": False,
        "usable": True,
        "on_demand": True,
        "message": "Model will download on first use.",
    }
    monkeypatch.setitem(
        sys.modules,
        "tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Files",
        fake_audio_files,
    )

    skip_if_transcription_model_unavailable("whisper-large-v3")


@pytest.mark.unit
def test_skip_if_transcription_model_unavailable_skips_when_model_is_not_usable(monkeypatch):
    fake_audio_files = ModuleType("Audio_Files")
    fake_audio_files.check_transcription_model_status = lambda _model_name: {
        "available": False,
        "usable": False,
        "message": "Model unavailable.",
    }
    monkeypatch.setitem(
        sys.modules,
        "tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Files",
        fake_audio_files,
    )

    with pytest.raises(pytest.skip.Exception):
        skip_if_transcription_model_unavailable("whisper-large-v3")


@pytest.mark.unit
def test_skip_if_whisper_model_not_cached_locally_skips_when_model_is_not_cached(monkeypatch):
    fake_audio_files = ModuleType("Audio_Files")
    fake_audio_files.check_transcription_model_status = lambda _model_name: {
        "available": False,
        "usable": True,
        "on_demand": True,
        "message": "Model will download on first use.",
        "model": "large-v3",
    }
    monkeypatch.setitem(
        sys.modules,
        "tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Files",
        fake_audio_files,
    )

    with pytest.raises(pytest.skip.Exception):
        skip_if_whisper_model_not_cached_locally("whisper-1")
