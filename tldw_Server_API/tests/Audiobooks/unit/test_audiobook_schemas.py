import pytest
from pydantic import ValidationError

from tldw_Server_API.app.api.v1.schemas.audiobook_schemas import (
    AlignmentPayload,
    AlignmentWord,
    AudiobookJobItem,
    AudiobookJobRequest,
    ChapterSelection,
    OutputOptions,
    SourceRef,
    SubtitleExportRequest,
    SubtitleOptions,
)

pytestmark = pytest.mark.unit


def _valid_source() -> SourceRef:
    return SourceRef(input_type="epub", upload_id="upload_1")


def _valid_chapters() -> list[ChapterSelection]:
    return [ChapterSelection(chapter_id="ch_001", include=True)]


def _valid_output() -> OutputOptions:
    return OutputOptions(formats=["mp3"])


def _valid_subtitles() -> SubtitleOptions:
    return SubtitleOptions(formats=["srt"], mode="sentence", variant="wide")


def _valid_alignment() -> AlignmentPayload:
    return AlignmentPayload(
        engine="kokoro",
        sample_rate=24000,
        words=[AlignmentWord(word="Hello", start_ms=0, end_ms=420)],
    )


def test_source_ref_requires_payload():
    with pytest.raises(ValidationError):
        SourceRef(input_type="epub")


def test_job_request_rejects_items_and_source():
    item = AudiobookJobItem(source=_valid_source())
    with pytest.raises(ValidationError):
        AudiobookJobRequest(project_title="Test", source=_valid_source(), items=[item])


def test_job_request_requires_output_and_subtitles_for_single_source():
    with pytest.raises(ValidationError):
        AudiobookJobRequest(project_title="Test", source=_valid_source(), chapters=_valid_chapters())


def test_job_request_batch_requires_defaults_or_item_overrides():
    item = AudiobookJobItem(source=_valid_source(), chapters=_valid_chapters())
    with pytest.raises(ValidationError):
        AudiobookJobRequest(project_title="Batch", items=[item])


def test_output_formats_must_not_be_empty():
    with pytest.raises(ValidationError):
        OutputOptions(formats=[])


def test_subtitle_export_defaults_words_per_cue():
    req = SubtitleExportRequest(
        format="srt",
        mode="word_count",
        variant="wide",
        alignment=_valid_alignment(),
    )
    assert req.words_per_cue == 12
