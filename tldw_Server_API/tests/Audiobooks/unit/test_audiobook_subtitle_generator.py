import pytest

from tldw_Server_API.app.api.v1.schemas.audiobook_schemas import AlignmentPayload, AlignmentWord
from tldw_Server_API.app.core.Audiobooks.subtitle_generator import generate_subtitles

pytestmark = pytest.mark.unit


def _make_alignment():
    words = [
        AlignmentWord(word="Hello", start_ms=0, end_ms=400),
        AlignmentWord(word="world.", start_ms=450, end_ms=900),
        AlignmentWord(word="Next", start_ms=1000, end_ms=1300),
        AlignmentWord(word="sentence.", start_ms=1350, end_ms=1800),
    ]
    return AlignmentPayload(engine="kokoro", sample_rate=24000, words=words)


def test_generate_srt_sentence_mode_splits_on_punctuation():
    alignment = _make_alignment()
    content = generate_subtitles(
        alignment,
        format="srt",
        mode="sentence",
        variant="wide",
    )
    blocks = [block for block in content.strip().split("\n\n") if block]
    assert len(blocks) == 2
    assert "Hello world." in blocks[0]
    assert "00:00:00,000 --> 00:00:00,900" in blocks[0]
    assert "Next sentence." in blocks[1]


def test_generate_word_count_groups_into_multiple_cues():
    alignment = _make_alignment()
    content = generate_subtitles(
        alignment,
        format="srt",
        mode="word_count",
        variant="wide",
        words_per_cue=2,
    )
    blocks = [block for block in content.strip().split("\n\n") if block]
    assert len(blocks) == 2
    assert "Hello world." in blocks[0]
    assert "Next sentence." in blocks[1]


def test_generate_vtt_includes_header_and_dot_time_format():
    alignment = _make_alignment()
    content = generate_subtitles(
        alignment,
        format="vtt",
        mode="word_count",
        variant="wide",
        words_per_cue=4,
    )
    assert content.startswith("WEBVTT")
    assert "00:00:00.000 --> 00:00:01.800" in content


def test_generate_ass_includes_dialogue_lines():
    alignment = _make_alignment()
    content = generate_subtitles(
        alignment,
        format="ass",
        mode="word_count",
        variant="wide",
        words_per_cue=4,
    )
    assert "[Events]" in content
    assert "Dialogue: 0,0:00:00.00,0:00:01.80" in content
    assert "Hello world." in content


def test_generate_rejects_negative_end_times():
    alignment = AlignmentPayload(
        engine="kokoro",
        sample_rate=24000,
        words=[AlignmentWord(word="Bad", start_ms=1000, end_ms=900)],
    )
    with pytest.raises(ValueError):
        generate_subtitles(alignment, format="srt", mode="line", variant="wide")
