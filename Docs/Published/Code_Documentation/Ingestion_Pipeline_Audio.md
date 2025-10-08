# Audio Ingestion Pipeline

## Overview

Transcribes audio inputs (URLs or local files), optionally chunks text, and runs analysis/summarization. Batch-oriented, DB‑agnostic; returns structured results for each input.

## Primary Function

`tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Files.process_audio_files`

Signature (abbreviated):

```
process_audio_files(
  inputs: List[str],
  transcription_model: str,
  transcription_language: Optional[str] = 'en',
  perform_chunking: bool = True,
  chunk_method: Optional[str] = None,
  max_chunk_size: int = 500,
  chunk_overlap: int = 200,
  use_adaptive_chunking: bool = False,
  use_multi_level_chunking: bool = False,
  chunk_language: Optional[str] = None,
  diarize: bool = False,
  vad_use: bool = False,
  timestamp_option: bool = True,
  perform_analysis: bool = True,
  api_name: Optional[str] = None,
  custom_prompt_input: Optional[str] = None,
  system_prompt_input: Optional[str] = None,
  summarize_recursively: bool = False,
  use_cookies: bool = False,
  cookies: Optional[str] = None,
  keep_original: bool = False,
  custom_title: Optional[str] = None,
  author: Optional[str] = None,
  temp_dir: Optional[str] = None,
) -> Dict[str, Any]
```

### Parameters

- inputs: URLs or absolute local paths to audio files.
- transcription_model: faster_whisper (e.g., `base`, `medium`, `large-v3`) or other configured models.
- transcription_language: target language (default `en`).
- diarize: enable speaker diarization; `vad_use`: enable voice activity detection.
- perform_chunking: chunk transcript; `chunk_method`: e.g., `sentences`.
- perform_analysis: use LLM summarization via `analyze`; `api_name` selects provider (keys from server config).
- summarize_recursively: combine per-chunk summaries into a higher-level summary.
- temp_dir: parent directory for temporary work files.

### Return Structure (batch)

```
{
  "processed_count": int,
  "errors_count": int,
  "errors": List[str],
  "results": [
    {
      "status": "Success"|"Warning"|"Error",
      "input_ref": str,                 # original URL/path
      "processing_source": str,         # local path actually processed
      "media_type": "audio",
      "metadata": dict,
      "content": str,                   # transcript text
      "segments": Optional[List],
      "chunks": Optional[List[Dict]],
      "analysis": Optional[str],
      "analysis_details": Dict,
      "error": Optional[str],
      "warnings": Optional[List[str]]
    }, ...
  ],
  "confabulation_results": Optional[str]
}
```

## Example

```python
from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Audio_Files import process_audio_files

res = process_audio_files(
    inputs=["https://soundcloud.com/...", "/abs/path/audio.wav"],
    transcription_model="large-v3",
    transcription_language="en",
    diarize=False,
    vad_use=True,
    perform_chunking=True,
    chunk_method="sentences",
    max_chunk_size=1200,
    chunk_overlap=200,
    perform_analysis=True,
    api_name="openai",
    summarize_recursively=True,
)
print(res["processed_count"], res["errors_count"])  # batch summary
for item in res.get("results", []):
    print(item["input_ref"], item["status"], len(item.get("chunks") or []))
```

## Endpoint Integration

- `POST /api/v1/media/process-audios` (media.py) adapts form data, saves validated uploads, and calls `process_audio_files`.

## Dependencies & Config

- Requires `ffmpeg` for conversion/transcoding.
- Summarization uses providers configured in server config; API keys are not passed to this function.
- Chunking uses `tldw_Server_API.app.core.Chunking` utilities.

## Error Handling & Notes

- Download errors, file size limits, cookie format issues, or conversion problems are mapped into per-item `status` and `error`.
- `results` may include structured warnings even when `status` is `Success`.
- Keep temp files by setting `keep_original=True` in the caller-managed temp dir.

