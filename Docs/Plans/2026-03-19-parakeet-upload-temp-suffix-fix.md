# Parakeet Upload Temp Suffix Fix Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Prevent audio transcription uploads from being staged to extensionless temp files so Parakeet and downstream audio tooling receive a usable path and avoid backend-detection failures.

**Architecture:** Fix the upload staging logic at the API boundary by normalizing the temp-file suffix from the original filename or MIME type before writing the upload. Cover the regression with an endpoint-level test that verifies extensionless filenames still produce a staged path with a real audio suffix.

**Tech Stack:** FastAPI, pytest, tempfile, pathlib

---

## Stage 1: Trace Source Path
**Goal**: Confirm the upload endpoint is the source of extensionless temp audio files.
**Success Criteria**: Documented understanding that `/audio/transcriptions` uses `NamedTemporaryFile` with an empty suffix when filename lacks an extension.
**Tests**: None
**Status**: Complete

## Stage 2: Add Regression Test
**Goal**: Add a failing endpoint test for extensionless audio uploads.
**Success Criteria**: Test asserts the staged path observed by the transcription adapter has a non-empty audio suffix derived from request metadata.
**Tests**: `pytest tldw_Server_API/tests/Audio/test_audio_transcriptions_adapter_path.py -k extensionless -v`
**Status**: Complete

## Stage 3: Implement Source Fix
**Goal**: Normalize upload temp suffixes in the audio transcription endpoint.
**Success Criteria**: Endpoint derives a suffix from filename or content type and never stages extensionless temp files for audio uploads.
**Tests**: `pytest tldw_Server_API/tests/Audio/test_audio_transcriptions_adapter_path.py -k extensionless -v`
**Status**: Complete

## Stage 4: Verify and Close
**Goal**: Run targeted verification and security scan for touched files.
**Success Criteria**: Targeted tests pass and Bandit reports no new findings on touched files.
**Tests**: `pytest tldw_Server_API/tests/Audio/test_audio_transcriptions_adapter_path.py -v`
**Status**: Complete
