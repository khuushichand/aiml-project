import pytest

from tldw_Server_API.app.core.Audiobooks.tag_parser import (
    ChapterMarker,
    build_chapters_from_markers,
    parse_tagged_text,
)

pytestmark = pytest.mark.unit


def test_parse_tagged_text_strips_tags_and_emits_markers():
    raw = (
        "[[chapter:title=Intro]]\n"
        "Intro line.\n"
        "[[voice=af_heart]]\n"
        "[[speed=1.25]]\n"
        "More text.\n"
        "[[chapter:id=ch_custom]]\n"
        "[[chapter:title=Second]]\n"
        "Second line.\n"
        "[[ts=00:00:05.000]]\n"
        "Second continued.\n"
    )
    result = parse_tagged_text(raw)

    assert "[[" not in result.clean_text
    assert "Intro line." in result.clean_text
    assert "Second continued." in result.clean_text

    assert len(result.chapter_markers) == 2
    assert result.chapter_markers[0].title == "Intro"
    assert result.chapter_markers[1].chapter_id == "ch_custom"
    assert result.chapter_markers[1].title == "Second"

    more_offset = result.clean_text.index("More text.")
    assert result.voice_markers[0].offset == more_offset
    assert result.voice_markers[0].value == "af_heart"
    assert result.speed_markers[0].offset == more_offset
    assert result.speed_markers[0].value == 1.25

    ts_offset = result.clean_text.index("Second continued.")
    assert result.ts_markers[0].offset == ts_offset
    assert result.ts_markers[0].time_ms == 5000


def test_build_chapters_from_markers_respects_offsets_and_ids():
    text = "One.\nTwo.\nThree."
    markers = [
        ChapterMarker(offset=0, chapter_id=None, title="One"),
        ChapterMarker(offset=text.index("Two."), chapter_id="custom_id", title=None),
    ]

    chapters = build_chapters_from_markers(text, markers)

    assert len(chapters) == 2
    assert chapters[0].chapter_id == "ch_001"
    assert chapters[0].title == "One"
    assert chapters[0].start_offset == 0
    assert chapters[0].end_offset == text.index("Two.")
    assert chapters[1].chapter_id == "custom_id"
    assert chapters[1].start_offset == text.index("Two.")
