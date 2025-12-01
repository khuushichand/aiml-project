import json
from pathlib import Path

import pytest

from tldw_Server_API.app.core.TTS.adapters.base import AudioFormat, TTSRequest
from tldw_Server_API.app.core.TTS.adapters.kokoro_adapter import KokoroAdapter
from tldw_Server_API.app.core.TTS.phoneme_overrides import (
    PhonemeOverrideEntry,
    apply_overrides_to_text,
    load_override_entries,
    merge_override_entries,
    parse_override_entries,
)


def test_apply_overrides_respects_lang_and_boundaries():
    entries = [
        PhonemeOverrideEntry(term="OpenAI", phonemes="ow p en aɪ", lang="en", boundary=True),
        PhonemeOverrideEntry(term="bonjour", phonemes="b ɔ̃ ʒ u ʁ", lang="fr", boundary=True),
    ]
    text = "OpenAI builds tools. bonjour monde."
    updated = apply_overrides_to_text(text, entries, lang_hint="en-US")

    assert "[[ow p en aɪ]]" in updated
    # French entry is skipped because lang_hint is English
    assert "bonjour" in updated


def test_merge_precedence_request_wins():
    global_entries = parse_override_entries({"demo": "AAA"})
    provider_entries = parse_override_entries([{"term": "demo", "phonemes": "BBB", "boundary": False}])
    request_entries = parse_override_entries({"demo": "CCC"})

    merged = merge_override_entries(global_entries, provider_entries, request_entries)

    assert len(merged) == 1
    assert merged[0].phonemes == "CCC"
    assert merged[0].boundary is True  # request entry falls back to default boundary


def test_adapter_applies_request_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    # Write a small JSON override file so load_override_entries can find it
    override_file = tmp_path / "tts_phonemes.json"
    override_file.write_text(json.dumps({"demo": "AAA"}), encoding="utf-8")
    monkeypatch.setenv("TTS_PHONEME_OVERRIDES_PATH", str(override_file))

    adapter = KokoroAdapter({"kokoro_phoneme_overrides": {"demo": "BBB"}})
    request = TTSRequest(
        text="demo phrase",
        voice="af_bella",
        format=AudioFormat.MP3,
        extra_params={"phoneme_overrides": {"demo": "CCC"}},
    )

    # Ensure the global file is picked up
    assert load_override_entries(str(override_file))

    updated = adapter._apply_phoneme_overrides_to_text(request.text, request=request, lang_hint="en")

    assert "[[CCC]]" in updated
    # Request-level flag can disable overrides entirely
    request.extra_params["disable_phoneme_overrides"] = True
    assert adapter._phoneme_overrides_enabled_for_request(request) is False
