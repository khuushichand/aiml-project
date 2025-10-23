from unittest.mock import patch

import pytest

from tldw_Server_API.app.core.Ingestion_Media_Processing.Video.Video_DL_Ingestion_Lib import process_videos


@pytest.mark.integration
def test_process_videos_threads_end_time(tmp_path):
    input_media = tmp_path / "sample.mp4"
    input_media.write_bytes(b"\x00" * 2048)

    captured_kwargs = {}

    def fake_transcription(*args, **kwargs):
        captured_kwargs.update(kwargs)
        return "sample.wav", [{"Text": "hello world"}]

    with patch(
        "tldw_Server_API.app.core.Ingestion_Media_Processing.Video.Video_DL_Ingestion_Lib.perform_transcription",
        side_effect=fake_transcription,
    ):
        result = process_videos(
            inputs=[str(input_media)],
            start_time="2",
            end_time="5",
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
            api_name=None,
            use_cookies=False,
            cookies=None,
            timestamp_option=False,
            perform_confabulation_check=False,
            temp_dir=str(tmp_path),
            keep_original=False,
            perform_diarization=False,
            user_id=123,
        )

    assert captured_kwargs["offset"] == 2
    assert captured_kwargs["end_seconds"] == 5
    assert result["processed_count"] == 1
    assert result["errors_count"] == 0
