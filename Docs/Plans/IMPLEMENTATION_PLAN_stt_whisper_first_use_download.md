# STT Whisper First-Use Download Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Restore first-use Whisper transcription downloads so the OpenAI-compatible audio transcription endpoint does not reject uncached models before the lazy faster-whisper load path runs.

**Architecture:** The regression lives in the REST transcription endpoint, not in the underlying transcription library. `Audio_Transcription_Lib.get_whisper_model(..., check_download_status=False)` already supports lazy first-use downloads, and media ingestion only surfaces preflight warnings. The fix should keep health/status introspection intact while removing the endpoint-level hard block that prevents the adapter path from executing.

**Tech Stack:** FastAPI, pytest, faster-whisper adapter/registry, Bandit

---

### Task 1: Capture the regression with a focused endpoint test

**Files:**
- Modify: `tldw_Server_API/tests/Audio/test_audio_transcription_language_normalization.py`
- Test: `tldw_Server_API/tests/Audio/test_audio_transcription_language_normalization.py`

**Step 1: Write the failing test**

Add a unit test that:
- mounts the audio transcription router with stubbed auth/quota helpers
- injects fake `Audio_Transcription_Lib` and `Audio_Files` modules through `sys.modules`
- returns `{"available": False, "usable": False, "on_demand": True}` from `check_transcription_model_status`
- provides a stub faster-whisper adapter whose `transcribe_batch` returns a valid transcript artifact
- asserts `POST /api/v1/audio/transcriptions` succeeds with `200` and returns the stub transcript

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Audio/test_audio_transcription_language_normalization.py -k first_use -v`

Expected: FAIL because the endpoint returns `503` with `status=model_downloading`.

### Task 2: Remove only the blocking preflight behavior

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/audio/audio_transcriptions.py`
- Reference: `tldw_Server_API/app/core/Ingestion_Media_Processing/Audio/Audio_Files.py`
- Reference: `tldw_Server_API/app/core/Ingestion_Media_Processing/Audio/Audio_Transcription_Lib.py`

**Step 1: Write minimal implementation**

Update the faster-whisper branch so it may still consult `check_transcription_model_status` for diagnostics, but it must not raise `503` merely because the model is not cached locally yet. Leave invalid-model validation and downstream transcription failures unchanged.

**Step 2: Run tests to verify green**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Audio/test_audio_transcription_language_normalization.py -k first_use -v`

Expected: PASS.

### Task 3: Verify touched scope and security scan

**Files:**
- Modify: `tldw_Server_API/tests/Audio/test_audio_transcription_language_normalization.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/audio/audio_transcriptions.py`

**Step 1: Run focused regression tests**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Audio/test_audio_transcription_language_normalization.py tldw_Server_API/tests/STT/test_audio_transcription_health.py -v`

Expected: PASS.

**Step 2: Run Bandit on touched scope**

Run: `source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/api/v1/endpoints/audio/audio_transcriptions.py tldw_Server_API/tests/Audio/test_audio_transcription_language_normalization.py -f json -o /tmp/bandit_stt_first_use_download.json`

Expected: No new findings in touched production code.
