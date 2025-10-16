import asyncio
import os
import pytest

from tldw_Server_API.app.core.TTS.adapters.vibevoice_adapter import VibeVoiceAdapter


@pytest.mark.unit
def test_preprocess_text_converts_bracket_markers_to_speaker_format():
    adapter = VibeVoiceAdapter({})
    raw = "[1]: Hello there\n[2]: And hi back"
    out = adapter.preprocess_text(raw)
    # Expect conversion to Speaker N: form
    assert "Speaker 1:" in out
    assert "Speaker 2:" in out


@pytest.mark.unit
def test_build_voice_samples_with_mapping_1_based_keys(tmp_path):
    # Prepare adapter with available voices mapping
    adapter = VibeVoiceAdapter({})
    adapter.available_voices = {
        "en-Alice_woman": "/voices/alice.wav",
        "en-Frank_man": "/voices/frank.wav",
    }

    text = "Speaker 1: Hello\nSpeaker 2: Hi"
    mapping = {"1": "en-Alice_woman", "2": "en-Frank_man"}

    res = adapter._build_voice_samples(
        formatted_text=text,
        voice_reference_path=None,
        primary_voice="speaker_1",
        speakers_to_voices=mapping,
    )

    assert res == ["/voices/alice.wav", "/voices/frank.wav"]


@pytest.mark.unit
def test_build_voice_samples_fallbacks_to_reference_then_files(tmp_path):
    # Create two fake voice files
    voices_dir = tmp_path / "voices"
    voices_dir.mkdir()
    (voices_dir / "a.wav").write_bytes(b"00")
    (voices_dir / "b.wav").write_bytes(b"11")

    adapter = VibeVoiceAdapter({"vibevoice_voices_dir": str(voices_dir)})
    adapter.available_voices = {}

    text = "Speaker 1: Hello\nSpeaker 2: Hi"
    # Provide explicit reference for first speaker
    ref = "/path/to/ref.wav"
    res = adapter._build_voice_samples(text, ref, "speaker_1", None)

    # First slot is the reference, second picked from voices_dir
    assert len(res) == 2
    assert res[0] == ref
    assert res[1].endswith(".wav")


@pytest.mark.unit
def test_default_mapping_merged_with_request_overrides():
    # Adapter with default mapping in config
    adapter = VibeVoiceAdapter({
        "vibevoice_speakers_to_voices": {"1": "en-Alice_woman"}
    })
    adapter.available_voices = {
        "en-Alice_woman": "/voices/alice.wav",
        "en-Frank_man": "/voices/frank.wav",
    }

    text = "Speaker 1: Hello\nSpeaker 2: Hi"

    # Request mapping overrides/extends defaults
    req_mapping = {"2": "en-Frank_man"}
    # Mirror adapter's merge semantics
    merged = {**adapter.default_speakers_to_voices, **req_mapping}

    res = adapter._build_voice_samples(
        formatted_text=text,
        voice_reference_path=None,
        primary_voice="speaker_1",
        speakers_to_voices=merged,
    )

    assert res == ["/voices/alice.wav", "/voices/frank.wav"]


@pytest.mark.unit
def test_request_overrides_default_for_same_speaker():
    adapter = VibeVoiceAdapter({
        "vibevoice_speakers_to_voices": {"1": "en-Alice_woman"}
    })
    adapter.available_voices = {
        "en-Alice_woman": "/voices/alice.wav",
    }

    text = "Speaker 1: Hello"
    # Override default with explicit path for speaker 1
    req_mapping = {"1": "/override/one.wav"}
    merged = {**adapter.default_speakers_to_voices, **req_mapping}

    res = adapter._build_voice_samples(
        formatted_text=text,
        voice_reference_path=None,
        primary_voice="speaker_1",
        speakers_to_voices=merged,
    )

    assert res == ["/override/one.wav"]
