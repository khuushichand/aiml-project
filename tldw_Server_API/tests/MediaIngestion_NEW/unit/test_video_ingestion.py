from unittest.mock import patch

import pytest

from tldw_Server_API.app.core.Ingestion_Media_Processing.Video.Video_DL_Ingestion_Lib import (
    parse_and_expand_urls,
    process_videos,
)


@pytest.mark.unit
def test_parse_and_expand_urls_preserves_non_vimeo_entries():
    local_path = "/Users/example/video.mp4"
    generic_url = "https://example.com/video.mp4"

    expanded = parse_and_expand_urls([local_path, generic_url])

    assert local_path in expanded
    assert generic_url in expanded


@pytest.mark.unit
def test_parse_and_expand_urls_normalizes_vimeo():
    vimeo_url = "http://vimeo.com/12345"
    expanded = parse_and_expand_urls([vimeo_url])
    assert expanded == ["https://vimeo.com/12345"]


@pytest.mark.unit
@patch("tldw_Server_API.app.core.Ingestion_Media_Processing.Video.Video_DL_Ingestion_Lib._resolve_eval_api_key", return_value="resolved-key")
@patch("tldw_Server_API.app.core.Ingestion_Media_Processing.Video.Video_DL_Ingestion_Lib.run_geval")
@patch("tldw_Server_API.app.core.Ingestion_Media_Processing.Video.Video_DL_Ingestion_Lib.process_single_video")
def test_confabulation_check_invokes_geval(mock_single, mock_geval, _mock_resolve_key, tmp_path):
    transcript_text = "this is a transcript"
    summary_text = "summary content"

    mock_single.return_value = {
        "status": "Success",
        "input_ref": "https://example.com/video",
        "processing_source": "https://example.com/video",
        "media_type": "video",
        "metadata": {},
        "content": transcript_text,
        "segments": [],
        "chunks": [],
        "analysis": summary_text,
        "analysis_details": {},
        "error": None,
        "warnings": [],
    }
    mock_geval.return_value = {"metrics": {"coherence": 5}}

    result = process_videos(
        inputs=["https://example.com/video"],
        start_time=None,
        end_time=None,
        diarize=False,
        vad_use=False,
        transcription_model="whisper-small",
        transcription_language="en",
        perform_analysis=False,
        custom_prompt=None,
        system_prompt=None,
        perform_chunking=False,
        chunk_method=None,
        max_chunk_size=1000,
        chunk_overlap=0,
        use_adaptive_chunking=False,
        use_multi_level_chunking=False,
        chunk_language=None,
        summarize_recursively=False,
        api_name="openai",
        use_cookies=False,
        cookies=None,
        timestamp_option=False,
        perform_confabulation_check=True,
        temp_dir=str(tmp_path),
        keep_original=False,
        perform_diarization=False,
    )

    mock_geval.assert_called_once()
    args, kwargs = mock_geval.call_args
    assert args[:4] == (transcript_text, summary_text, "resolved-key", "openai")
    assert kwargs.get("user_identifier") is None
    assert result["processed_count"] == 1
    assert result["confabulation_results"].startswith("Confabulation checks completed")
