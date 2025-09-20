# Video Ingestion Pipeline

## Overview

Downloads videos (yt-dlp) or uses local files, then transcribes audio, optionally chunks text, and runs analysis/summarization. Batch-oriented and DB‑agnostic.

## Primary Functions

Module: `tldw_Server_API.app.core.Ingestion_Media_Processing.Video.Video_DL_Ingestion_Lib`

- `process_videos(inputs, start_time, end_time, diarize, vad_use, transcription_model, transcription_language, perform_analysis, custom_prompt, system_prompt, perform_chunking, chunk_method, max_chunk_size, chunk_overlap, use_adaptive_chunking, use_multi_level_chunking, chunk_language, summarize_recursively, api_name, use_cookies, cookies, timestamp_option, perform_confabulation_check, temp_dir=None, keep_original=False, perform_diarization=False) -> Dict[str, Any]`
- `process_single_video(...) -> Dict[str, Any]` (internal worker)

### Parameters (selected)

- inputs: URLs or local paths.
- start_time/end_time: optional partial transcription windows.
- transcription_model/language: passed to STT backend.
- perform_chunking/analysis/summarize_recursively: chunk and summarize transcript.
- use_cookies/cookies: for authenticated downloads.
- timestamp_option: include timestamps in transcript.
- temp_dir: directory managed by caller for downloads/intermediates.

### Return Structure (batch)

Same pattern as audio pipeline: `processed_count`, `errors_count`, `errors`, `results` (per item dict with transcript/chunks/analysis), and optional `confabulation_results`.

## Example

```python
from tldw_Server_API.app.core.Ingestion_Media_Processing.Video.Video_DL_Ingestion_Lib import process_videos

out = process_videos(
    inputs=["https://www.youtube.com/watch?v=...", "/abs/local/video.mp4"],
    start_time=None,
    end_time=None,
    diarize=False,
    vad_use=True,
    transcription_model="medium",
    transcription_language="en",
    perform_analysis=True,
    custom_prompt="Summarize as steps",
    system_prompt=None,
    perform_chunking=True,
    chunk_method="sentences",
    max_chunk_size=1000,
    chunk_overlap=150,
    use_adaptive_chunking=False,
    use_multi_level_chunking=False,
    chunk_language="en",
    summarize_recursively=False,
    api_name="openai",
    use_cookies=False,
    cookies=None,
    timestamp_option=True,
    perform_confabulation_check=False,
    temp_dir=None,
    keep_original=False,
    perform_diarization=False,
)
print(out["processed_count"], out["errors"])  # batch summary
```

## Endpoint Integration

- `POST /api/v1/media/process-videos` prepares uploads and URLs, calls `process_videos`, and normalizes results.

## Dependencies & Config

- Requires `ffmpeg` and `yt-dlp`.
- Summarization provider is chosen via `api_name`; credentials come from server config.

## Error Handling & Notes

- Download failures, missing ffmpeg, or unsupported formats produce per-item errors.
- If `temp_dir` is not supplied by the caller, endpoint creates and manages a temp directory.

