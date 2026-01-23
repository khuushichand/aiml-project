# Audiobook Creation PRD (API-only, Kokoro TTS)

Status: Draft v0.1
Owner: Core Maintainers
Target Release: TBD

## 1) Summary
Provide an API-first audiobook creation pipeline that ingests book-like files, detects chapters, applies per-chapter voice settings, generates TTS audio, produces aligned subtitles (Kokoro only), and packages outputs in common audio formats (including M4B with chapters). The API will be suitable for client integrations; WebUI authoring and drag-and-drop UX are deferred to a later PRD.

## 2) Problem Statement
Clients want to turn documents into audiobooks with chapter control, voice tuning, and reliable subtitles. The current stack has robust ingestion, chunking, and TTS, but lacks a dedicated audiobook orchestration layer, TTS alignment outputs, subtitle generation, and chaptered packaging.

## 3) Goals and Non-Goals
### Goals (MVP -> v1)
- [ ] API to ingest EPUB/PDF/TXT/MD/SRT/VTT/ASS and return normalized text + chapter candidates.
- [ ] Chapter selection and per-chapter voice/speed settings in request payloads.
- [ ] Kokoro TTS generation with alignment metadata (word timestamps) per chapter.
- [ ] Subtitle export (SRT/VTT/ASS) with multiple segmentation modes and highlight variants.
- [ ] Output packaging to WAV/MP3/FLAC/OPUS and M4B with chapter markers.
- [ ] Queue mode for batch processing with per-item overrides.
- [ ] Reprocessing support via embedded chapter markers in source text.
- [ ] Optional spaCy sentence segmentation to improve subtitle splits.

### Non-Goals (initial)
- WebUI editor, drag-and-drop UX, and markdown preview.
- Multi-provider TTS selection with alignment parity (Kokoro alignment remains required for subtitles).
- Automatic audio mastering, loudness normalization, or advanced post-production effects.
- Full DAW-style editing or timeline-based UI.

## 4) Personas
- Client Integrator: wants stable API contracts for automated audiobook creation.
- Power User: wants per-chapter voice control and subtitle exports.
- Ops/SRE: needs predictable resource usage, quotas, and error visibility.

## 5) Success Metrics
- Job success rate and average time-to-audiobook.
- Chapter detection precision (manual overrides required per item).
- Subtitle alignment accuracy (mean absolute error vs. TTS alignment).
- Output packaging success rate (including M4B).

## 6) Scope
### In-Scope
- Ingestion and normalization of supported inputs:
  - EPUB/PDF/TXT/MD via existing ingestion.
  - SRT/VTT/ASS as text sources (timings ignored in MVP; cue boundaries preserved as segmentation hints).
- Upload validation updates for `.srt`, `.vtt`, `.ass` in `tldw_Server_API/app/core/Ingestion_Media_Processing/Upload_Sink.py`.
- Chapter detection for EPUB/PDF and custom chapter pattern support.
- Per-chapter voice and speed settings using Kokoro voices (default) or optional provider overrides for audio-only output.
- TTS alignment output and subtitle generation.
- Packaging: per-chapter files or merged audiobook; M4B with chapters.
- Batch queue processing using existing Jobs system.

### Out-of-Scope (initial)
- Client UI tooling (drag-and-drop, built-in editor, markdown preview).
- Cross-provider voice cloning and mixing beyond Kokoro capabilities.
- Automatic language detection or multilingual TTS.

## 7) Existing System Alignment
Leverage and extend these modules:
- TTS core: `tldw_Server_API/app/core/TTS/tts_service_v2.py`
- Kokoro adapter: `tldw_Server_API/app/core/TTS/adapters/kokoro_adapter.py`
- Audio API surface: `tldw_Server_API/app/api/v1/endpoints/audio.py`
- Ingestion: `tldw_Server_API/app/core/Ingestion_Media_Processing/Books/Book_Processing_Lib.py`
- PDF ingestion: `tldw_Server_API/app/core/Ingestion_Media_Processing/PDF/PDF_Processing_Lib.py`
- Chapter chunking: `tldw_Server_API/app/core/Chunking/strategies/ebook_chapters.py`
- Output artifacts: `tldw_Server_API/app/services/outputs_service.py`
- Jobs system: `tldw_Server_API/app/core/Jobs/manager.py`

## 8) Architecture Overview
Pipeline (API-first):
1. Ingest source -> extract text + metadata.
2. Chapter detection -> return selectable chapter list.
3. Apply per-chapter voice/speed settings.
4. Kokoro TTS -> audio + alignment metadata.
5. Subtitle generation from alignment -> SRT/VTT/ASS variants.
6. Package outputs (per-chapter or merged; optional M4B).
7. Persist outputs via Collections outputs and return download URLs.

## 9) API Surface (Proposed)
### 9.1 Parse and Chapter Preview
`POST /api/v1/audiobooks/parse`
- Input: file upload or raw text + type hint.
- Output: normalized text, chapter candidates, metadata.

Example request (JSON, uploaded file reference):
```json
{
  "source": {
    "input_type": "epub",
    "upload_id": "upload_4d8f"
  },
  "detect_chapters": true,
  "custom_chapter_pattern": null,
  "language": "en"
}
```

Example response:
```json
{
  "project_id": "abk_01J7Y2M4G1",
  "normalized_text": "Chapter 1...\n\nChapter 2...",
  "chapters": [
    {
      "chapter_id": "ch_001",
      "title": "Chapter 1",
      "start_offset": 0,
      "end_offset": 12458,
      "word_count": 2450
    },
    {
      "chapter_id": "ch_002",
      "title": "Chapter 2",
      "start_offset": 12459,
      "end_offset": 23877,
      "word_count": 2201
    }
  ],
  "metadata": {
    "title": "Example Book",
    "author": "Example Author",
    "source_type": "epub"
  }
}
```

Schema (draft):
```json
{
  "type": "object",
  "required": ["source"],
  "properties": {
    "source": { "$ref": "#/definitions/SourceRef" },
    "detect_chapters": { "type": "boolean", "default": true },
    "custom_chapter_pattern": { "type": ["string", "null"] },
    "language": { "type": ["string", "null"] },
    "max_chars": { "type": ["integer", "null"], "minimum": 1 }
  }
}
```

### 9.2 Create Audiobook Job
`POST /api/v1/audiobooks/jobs`
- Input: source reference (upload id, media id, or raw text) or `items[]`, chapter selection, per-chapter settings, output formats, subtitle modes, queue options.
- `tts_provider`/`tts_model` may be provided to override the TTS engine. Alignment + subtitle generation is supported only for Kokoro; when using a non-Kokoro provider, omit `subtitles` or the job will fail.
- `chapter_id` values must match the chapter ids returned by `/api/v1/audiobooks/parse`; unknown ids are rejected.
- Batch defaults: when `items[]` is provided, top-level `output` and `subtitles` act as defaults; each item may override or omit them to inherit defaults. Each item must resolve to effective `output` and `subtitles` (either per-item or inherited). Do not mix single-source fields with `items[]`.
- Output: job id and initial status.

Example request:
```json
{
  "project_title": "Example Book",
  "source": {
    "input_type": "epub",
    "upload_id": "upload_4d8f"
  },
  "chapters": [
    { "chapter_id": "ch_001", "include": true, "voice": "af_heart", "speed": 1.0 },
    { "chapter_id": "ch_002", "include": true, "voice": "am_adam", "speed": 0.98 }
  ],
  "output": {
    "merge": true,
    "per_chapter": true,
    "formats": ["mp3", "m4b"]
  },
  "subtitles": {
    "formats": ["srt", "vtt", "ass"],
    "mode": "sentence",
    "variant": "wide"
  },
  "queue": {
    "priority": 5,
    "batch_group": "client_batch_1"
  }
}
```

Example request (batch with defaults + per-item overrides):
```json
{
  "project_title": "Batch Import A",
  "output": {
    "merge": false,
    "per_chapter": true,
    "formats": ["mp3"]
  },
  "subtitles": {
    "formats": ["vtt"],
    "mode": "sentence",
    "variant": "wide"
  },
  "items": [
    {
      "source": { "input_type": "epub", "upload_id": "upload_aa01" },
      "chapters": [{ "chapter_id": "ch_001", "include": true, "voice": "af_heart", "speed": 1.0 }]
    },
    {
      "source": { "input_type": "pdf", "upload_id": "upload_bb02" },
      "chapters": [{ "chapter_id": "ch_003", "include": true, "voice": "am_adam", "speed": 0.98 }],
      "subtitles": { "formats": ["srt", "vtt"], "mode": "line", "variant": "narrow" },
      "output": { "merge": true, "per_chapter": false, "formats": ["mp3", "m4b"] }
    }
  ]
}
```

Example response:
```json
{
  "job_id": 12345,
  "project_id": "abk_01J7Y2M4G1",
  "status": "queued"
}
```

Schema (draft):
```json
{
  "type": "object",
  "properties": {
    "project_title": { "type": "string", "minLength": 1, "maxLength": 200 },
    "source": { "$ref": "#/definitions/SourceRef" },
    "items": {
      "type": "array",
      "items": { "$ref": "#/definitions/AudiobookJobItem" }
    },
    "tts_provider": { "type": ["string", "null"] },
    "tts_model": { "type": ["string", "null"] },
    "chapters": {
      "type": "array",
      "items": { "$ref": "#/definitions/ChapterSelection" }
    },
    "output": { "$ref": "#/definitions/OutputOptions" },
    "subtitles": { "$ref": "#/definitions/SubtitleOptions" },
    "queue": { "$ref": "#/definitions/QueueOptions" },
    "metadata": { "type": "object", "additionalProperties": true }
  },
  "oneOf": [
    {
      "required": ["project_title", "source", "chapters", "output", "subtitles"]
    },
    {
      "required": ["project_title", "items"]
    }
  ]
}
```

### 9.3 Job Status and Artifacts
`GET /api/v1/audiobooks/jobs/{job_id}`
`GET /api/v1/audiobooks/jobs/{job_id}/artifacts`
- Output: progress, errors, output artifact list, download URLs.

Example response (status):
```json
{
  "job_id": 12345,
  "project_id": "abk_01J7Y2M4G1",
  "status": "processing",
  "progress": {
    "stage": "audiobook_tts",
    "chapter_index": 2,
    "chapters_total": 10,
    "percent": 45
  },
  "errors": []
}
```

Example response (artifacts):
```json
{
  "project_id": "abk_01J7Y2M4G1",
  "artifacts": [
    {
      "artifact_type": "audio",
      "format": "mp3",
      "scope": "chapter",
      "chapter_id": "ch_001",
      "output_id": 456,
      "download_url": "/api/v1/outputs/456/download"
    },
    {
      "artifact_type": "subtitle",
      "format": "srt",
      "scope": "chapter",
      "chapter_id": "ch_001",
      "output_id": 789,
      "download_url": "/api/v1/outputs/789/download"
    },
    {
      "artifact_type": "alignment",
      "format": "json",
      "scope": "chapter",
      "chapter_id": "ch_001",
      "output_id": 790,
      "download_url": "/api/v1/outputs/790/download"
    }
  ]
}
```

Schema (draft):
```json
{
  "type": "object",
  "required": ["project_id", "artifacts"],
  "properties": {
    "project_id": { "type": "string" },
    "artifacts": {
      "type": "array",
      "items": { "$ref": "#/definitions/ArtifactInfo" }
    }
  }
}
```

### 9.4 Project Queries (API-only)
`GET /api/v1/audiobooks/projects`
`GET /api/v1/audiobooks/projects/{project_ref}`
`GET /api/v1/audiobooks/projects/{project_ref}/chapters`
`GET /api/v1/audiobooks/projects/{project_ref}/artifacts`
- `project_ref` accepts the external `project_id` (e.g., `abk_01J7Y2M4G1`) or the numeric DB id.
- Supports pagination via `limit` + `offset`.

Example response (projects):
```json
{
  "projects": [
    {
      "project_db_id": 12,
      "project_id": "abk_01J7Y2M4G1",
      "title": "Example Book",
      "status": "completed",
      "source_ref": { "input_type": "epub", "upload_id": "upload_4d8f" },
      "settings": { "project_id": "abk_01J7Y2M4G1", "project_title": "Example Book" },
      "created_at": "2025-01-21T10:00:00+00:00",
      "updated_at": "2025-01-21T10:05:00+00:00"
    }
  ]
}
```

Example response (project detail):
```json
{
  "project": {
    "project_db_id": 12,
    "project_id": "abk_01J7Y2M4G1",
    "title": "Example Book",
    "status": "completed",
    "source_ref": { "input_type": "epub", "upload_id": "upload_4d8f" },
    "settings": { "project_id": "abk_01J7Y2M4G1", "project_title": "Example Book" },
    "created_at": "2025-01-21T10:00:00+00:00",
    "updated_at": "2025-01-21T10:05:00+00:00"
  }
}
```

Example response (chapters):
```json
{
  "project_id": "abk_01J7Y2M4G1",
  "chapters": [
    {
      "id": 101,
      "chapter_index": 0,
      "title": "Chapter 1",
      "start_offset": 0,
      "end_offset": 12458,
      "voice_profile_id": null,
      "speed": 1.0,
      "metadata": { "chapter_id": "ch_001", "item_index": 0 }
    }
  ]
}
```

Example response (project artifacts):
```json
{
  "project_id": "abk_01J7Y2M4G1",
  "artifacts": [
    {
      "artifact_type": "audio",
      "format": "mp3",
      "scope": "chapter",
      "chapter_id": "ch_001",
      "output_id": 456,
      "download_url": "/api/v1/outputs/456/download"
    }
  ]
}
```

### 9.5 Voice Profiles (API-only support)
`POST /api/v1/audiobooks/voices/profiles`
`GET /api/v1/audiobooks/voices/profiles`
`DELETE /api/v1/audiobooks/voices/profiles/{profile_id}`
- Voice profiles reference Kokoro voices and per-chapter defaults.
- Mixing is modeled as a profile that sequences voices by segment rules (true blending is deferred).

Example request:
```json
{
  "name": "Narrator + Dialog",
  "default_voice": "af_heart",
  "default_speed": 1.0,
  "chapter_overrides": [
    { "chapter_id": "ch_005", "voice": "am_adam", "speed": 0.98 }
  ]
}
```

Example response:
```json
{
  "profile_id": "vp_01J7Y2NV6F",
  "name": "Narrator + Dialog",
  "default_voice": "af_heart",
  "default_speed": 1.0,
  "chapter_overrides": [
    { "chapter_id": "ch_005", "voice": "am_adam", "speed": 0.98 }
  ]
}
```

Schema (draft):
```json
{
  "type": "object",
  "required": ["name", "default_voice", "default_speed"],
  "properties": {
    "name": { "type": "string", "minLength": 1, "maxLength": 100 },
    "default_voice": { "type": "string" },
    "default_speed": { "type": "number", "minimum": 0.25, "maximum": 4.0 },
    "chapter_overrides": {
      "type": "array",
      "items": { "$ref": "#/definitions/ChapterVoiceOverride" }
    }
  }
}
```

### 9.5 Subtitle Export (Optional Direct)
`POST /api/v1/audiobooks/subtitles`
- Input: alignment payload or stored alignment output id + segmentation mode + style variant.
- Output: subtitle file content (SRT/VTT/ASS). When caching is enabled, response includes headers with output id/download URL.

Example request:
```json
{
  "format": "srt",
  "mode": "sentence",
  "variant": "wide",
  "alignment_output_id": 1234,
  "persist": true,
  "alignment": {
    "words": [
      { "word": "Hello", "start_ms": 0, "end_ms": 420 },
      { "word": "world", "start_ms": 450, "end_ms": 900 }
    ],
    "engine": "kokoro",
    "sample_rate": 24000
  }
}
```

Example response (text/plain):
```
1
00:00:00,000 --> 00:00:00,900
Hello world
```

Schema (draft):
```json
{
  "type": "object",
  "required": ["format", "mode", "variant"],
  "properties": {
    "format": { "type": "string", "enum": ["srt", "vtt", "ass"] },
    "mode": { "type": "string", "enum": ["line", "sentence", "word_count", "highlight"] },
    "variant": { "type": "string", "enum": ["wide", "narrow", "centered"] },
    "alignment": { "$ref": "#/definitions/AlignmentPayload" },
    "alignment_output_id": { "type": ["integer", "null"] },
    "persist": { "type": ["boolean", "null"], "description": "Persist subtitle output (cache)" },
    "cache_ttl_hours": { "type": ["integer", "null"], "minimum": 1 },
    "words_per_cue": { "type": ["integer", "null"], "minimum": 1 },
    "max_chars": { "type": ["integer", "null"], "minimum": 10 },
    "max_lines": { "type": ["integer", "null"], "minimum": 1 }
  }
}
```

### 9.6 Shared Schema Definitions (Draft)
```json
{
  "definitions": {
    "SourceRef": {
      "type": "object",
      "required": ["input_type"],
      "properties": {
        "input_type": { "type": "string", "enum": ["epub", "pdf", "txt", "md", "srt", "vtt", "ass"] },
        "upload_id": { "type": ["string", "null"] },
        "media_id": { "type": ["integer", "string", "null"] },
        "raw_text": { "type": ["string", "null"] }
      }
    },
    "ChapterSelection": {
      "type": "object",
      "required": ["chapter_id", "include"],
      "properties": {
        "chapter_id": { "type": "string" },
        "include": { "type": "boolean" },
        "voice": { "type": ["string", "null"] },
        "speed": { "type": ["number", "null"], "minimum": 0.25, "maximum": 4.0 }
      }
    },
    "OutputOptions": {
      "type": "object",
      "required": ["formats"],
      "properties": {
        "merge": { "type": "boolean", "default": true },
        "per_chapter": { "type": "boolean", "default": true },
        "formats": {
          "type": "array",
          "items": { "type": "string", "enum": ["wav", "mp3", "flac", "opus", "m4b"] }
        }
      }
    },
    "SubtitleOptions": {
      "type": "object",
      "required": ["formats", "mode", "variant"],
      "properties": {
        "formats": {
          "type": "array",
          "items": { "type": "string", "enum": ["srt", "vtt", "ass"] }
        },
        "mode": { "type": "string", "enum": ["line", "sentence", "word_count", "highlight"] },
        "variant": { "type": "string", "enum": ["wide", "narrow", "centered"] },
        "words_per_cue": { "type": ["integer", "null"], "minimum": 1 }
      }
    },
    "QueueOptions": {
      "type": "object",
      "properties": {
        "priority": { "type": "integer", "minimum": 1, "maximum": 10, "default": 5 },
        "batch_group": { "type": ["string", "null"], "maxLength": 100 }
      }
    },
    "AudiobookJobItem": {
      "type": "object",
      "required": ["source"],
      "properties": {
        "source": { "$ref": "#/definitions/SourceRef" },
        "tts_provider": { "type": ["string", "null"] },
        "tts_model": { "type": ["string", "null"] },
        "chapters": { "type": "array", "items": { "$ref": "#/definitions/ChapterSelection" } },
        "output": { "$ref": "#/definitions/OutputOptions" },
        "subtitles": { "$ref": "#/definitions/SubtitleOptions" },
        "metadata": { "type": "object", "additionalProperties": true }
      }
    },
    "ChapterVoiceOverride": {
      "type": "object",
      "required": ["chapter_id"],
      "properties": {
        "chapter_id": { "type": "string" },
        "voice": { "type": ["string", "null"] },
        "speed": { "type": ["number", "null"], "minimum": 0.25, "maximum": 4.0 }
      }
    },
    "AlignmentPayload": {
      "type": "object",
      "required": ["words", "engine", "sample_rate"],
      "properties": {
        "engine": { "type": "string", "enum": ["kokoro"] },
        "sample_rate": { "type": "integer", "minimum": 8000 },
        "words": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["word", "start_ms", "end_ms"],
            "properties": {
              "word": { "type": "string" },
              "start_ms": { "type": "integer", "minimum": 0 },
              "end_ms": { "type": "integer", "minimum": 0 },
              "char_start": { "type": ["integer", "null"] },
              "char_end": { "type": ["integer", "null"] }
            }
          }
        }
      }
    },
    "ArtifactInfo": {
      "type": "object",
      "required": ["artifact_type", "format", "output_id", "download_url"],
      "properties": {
        "artifact_type": { "type": "string", "enum": ["audio", "subtitle", "package", "alignment"] },
        "format": { "type": "string" },
        "scope": { "type": ["string", "null"], "enum": ["chapter", "merged", null] },
        "chapter_id": { "type": ["string", "null"] },
        "output_id": { "type": "integer" },
        "download_url": { "type": "string" }
      }
    }
  }
}
```

## 10) Data Model and Storage
Store audiobook metadata in the per-user Media DB (Collections tables) via `Collections_DB.py`.
Proposed tables (add via DB_Management abstractions):
- `audiobook_projects`: id, user_id, project_id (external), title, source_ref, status, created_at, updated_at, settings_json.
- `audiobook_chapters`: id, project_id, chapter_index, title, start_offset, end_offset, voice_profile_id, speed, metadata_json.
- `audiobook_artifacts`: id, project_id, artifact_type (audio/subtitle/package/alignment), format, output_id, metadata_json.

Audio, subtitle, and alignment files are stored as Collections outputs (existing outputs table) with metadata that links back to project and chapter ids.

### 10.1 Migration Mapping
- Add `tldw_Server_API/app/core/DB_Management/migrations/016_audiobook_tables.json` (SQLite) to create the three tables and indexes.
- Add `tldw_Server_API/app/core/DB_Management/migrations/018_audiobook_project_id.json` to add `project_id` + index.
- Extend `tldw_Server_API/app/core/DB_Management/Collections_DB.py` to include the new tables in `ensure_schema()` for both SQLite and Postgres.
- Add `Collections_DB` accessors for project/chapter/artifact create + list to keep API handlers DB-agnostic.

### 10.2 Output Artifact Mapping
- Store audio/subtitle/alignment files in `outputs` with:
  - `outputs.type`: `audiobook_audio`, `audiobook_subtitle`, `audiobook_package`, `audiobook_alignment`
  - `outputs.format`: `mp3`, `wav`, `flac`, `opus`, `m4b`, `srt`, `vtt`, `ass`, `json`
  - `outputs.metadata_json`: `project_id`, `chapter_id`, `chapter_index`, `voice`, `speed`, `subtitle_mode`, `alignment_engine`, `alignment_sample_rate`
- `audiobook_artifacts.output_id` references `outputs.id` as the primary file pointer (including alignment artifacts).
- Alignment artifacts use existing outputs retention/expiry behavior.
- Subtitle exports are generated on demand by default and are not persisted unless explicitly requested (or cached by policy).

## 11) TTS Alignment and Subtitle Generation
### 11.1 Alignment Source
- Use Kokoro timestamped assets and extend `kokoro_adapter.py` to emit word-level alignment in `TTSResponse.metadata`.
- Alignment/subtitles are only supported for Kokoro. Other providers are audio-only.
- Alignment metadata schema:
  - `alignment.words`: list of { word, start_ms, end_ms, char_start, char_end }
  - `alignment.sample_rate`: int
  - `alignment.engine`: "kokoro"
- Persist alignment as a first-class `outputs` artifact (`audiobook_alignment`) with a download URL.

### 11.2 Subtitle Modes
- `line`: treat newlines as hard cue boundaries; wrap long lines at word boundaries (max_lines=2).
- `sentence`: split on sentence boundaries (spaCy optional). Enforce max_duration and max_chars; if exceeded, fall back to `word_count`.
- `word_count`: fixed words_per_cue (default 12). Enforce min_duration=0.8s and max_duration=6s.
- `highlight`: requires word timestamps. ASS uses karaoke tags, VTT uses `<c.hl>` cues, SRT emits one cue per word (no styling).

### 11.3 Variants
- `wide`: max_chars=42, max_lines=2.
- `narrow`: max_chars=28, max_lines=2.
- `centered`: same as `wide`, plus centered alignment tags where supported (ASS/VTT). SRT falls back to `wide`.

### 11.4 Canonical Tag Markers (Reprocessing + Timestamp Anchors)
Detect embedded markers in text for segment boundaries and overrides. These are the canonical tags for reprocessing (normalized and re-emitted by the system). Other tags may be ignored.

Tag format:
- `[[key=value]]` or `[[key:attr=value]]`

Canonical keys and constraints:
- `chapter:title`: starts a new chapter. Value length <= 128.
- `chapter:id`: explicit chapter id, `[A-Za-z0-9_-]{1,64}`.
- `voice`: Kokoro voice id (must exist).
- `speed`: float 0.25-4.0.
- `ts`: `HH:MM:SS.mmm` anchor for the next cue block.

Parsing rules:
- Tags must appear on their own line to be recognized.
- Chapter tags create hard boundaries; explicit tags override detected chapters.
- `chapter:id` + `chapter:title` may appear in any order before the next text line; both apply to the next chapter block.
- `voice` and `speed` tags apply forward until replaced.
- `ts` anchors adjust alignment for the next block; if impossible, log warning and ignore.
- Tags are stripped before TTS but preserved in metadata for reprocessing.

### 11.5 Speed Adjustment
- Preferred: regenerate TTS with new speed.
- Optional: ffmpeg time-stretch for small adjustments (configurable threshold). When enabled, TTS is generated at 1.0x, audio is time-stretched, and alignment timestamps are scaled to match.

## 12) Output Formats and Packaging
Supported outputs:
- WAV, MP3, FLAC, OPUS (native TTS formats).
- M4B with chapters (packaging step).

Implementation notes:
- Extend `audio_converter.py` to include M4B packaging.
- Embed chapter markers in M4B metadata.
- Return per-chapter files and/or merged audiobook based on request. If M4B packaging fails when requested, the job fails (no fallback).

## 13) Queue and Batch Processing
Use Jobs system with a new domain `audiobook`:
- Job types: `audiobook_parse`, `audiobook_tts`, `audiobook_subtitles`, `audiobook_package`.
- Support batch mode: request accepts an array of items with per-item overrides.
- Enforce quotas via existing audio quota mechanisms plus per-user audiobook artifact caps.

## 14) Configuration and Feature Flags
Add configuration keys (examples):
- `AUDIOBOOK_ENABLE_SPACY=0/1`
- `AUDIOBOOK_SPACY_MODEL=en_core_web_sm` (optional)
- `AUDIOBOOK_DEFAULT_VOICE=af_heart`
- `AUDIOBOOK_DEFAULT_SPEED=1.0`
- `AUDIOBOOK_ALLOW_M4B=1`
- `AUDIOBOOK_MAX_CHARS=200000`
- `AUDIOBOOK_CHAPTER_MAX_CHARS=12000` (optional chunk size for long chapters)
- `AUDIOBOOK_TIME_STRETCH_MAX_RATIO=1.1` (enable ffmpeg atempo when requested speed is within `[1/max_ratio, max_ratio]`)
- `AUDIOBOOK_SUBTITLES_PERSIST=0/1` (default 0; on-demand generation)
- `AUDIOBOOK_SUBTITLES_CACHE_TTL_HOURS=24` (optional subtitle cache TTL when persisted)
- `AUDIOBOOK_ARTIFACT_QUOTA_MB=1024` (per-user cap for audiobook outputs)

## 15) Security and Compliance
- Validate uploads through ingestion pipeline (no direct file path usage).
- Sanitize text via existing TTS validation (`tts_validation.py`).
- Do not log raw content or API keys.
- Enforce size limits and quotas consistent with audio ingestion limits.

## 16) Performance and Limits
- Default concurrency aligned to TTS service limits.
- Chunk very large chapters to avoid long single requests.
- Provide progress updates per chapter for long jobs.

## 17) Testing Plan
- Unit tests:
  - Chapter detection + selection.
  - Kokoro alignment extraction.
  - Subtitle generators for each mode and format.
  - M4B packaging.
- Integration tests:
  - `POST /api/v1/audiobooks/parse`
  - `POST /api/v1/audiobooks/jobs` + job polling
  - Subtitle export from alignment metadata
- Property-based tests:
  - Subtitle segmentation invariants (monotonic timestamps, non-overlap).

## 18) Risks and Mitigations
- Kokoro alignment not exposed: add adapter metadata with strict tests.
- M4B packaging variability: fail the job with a clear error when M4B is requested and packaging fails.
- Subtitle drift for long chapters: enforce chunking + alignment stitching.
- spaCy dependency bloat: optional flag with graceful fallback to regex splits.

## 19) Decisions (Resolved)
- Canonical reprocessing tags: `chapter:id`, `chapter:title`, `voice`, `speed`, `ts` (see 11.4).
- Subtitle exports are generated on demand by default; persistence is opt-in or policy-driven.
- Per-user storage quotas are required for audiobook artifacts (audio, packages, alignment).

## 20) Open Questions
- None (for now).

## 21) Phased Delivery
Phase 0:
- Parse endpoint + chapter preview.
- Kokoro alignment metadata.
Phase 1:
- Job-based TTS generation + subtitle export.
- Output packaging (WAV/MP3/FLAC/OPUS).
Phase 2:
- M4B packaging with chapters.
- Voice profile API and batch queue enhancements.

## 22) Implementation Plan (Staged)
This staged plan matches the project guidelines (small, testable increments).

### Stage 0: API Contracts and Schema Scaffolding
**Goal**: Lock API contracts, request/response schemas, and error taxonomy.
**Deliverables**:
- Pydantic models under `tldw_Server_API/app/api/v1/schemas/audiobook_schemas.py`.
- Router skeleton under `tldw_Server_API/app/api/v1/endpoints/audiobooks.py`.
- OpenAPI examples aligned with this PRD.
**Success Criteria**:
- OpenAPI docs show all endpoints with example payloads.
- Schemas validate known-good fixtures.
**Tests**:
- Unit tests for schema validation.
**Status**: Complete

### Stage 1: Parse + Chapter Preview (Read Path)
**Goal**: Implement `/api/v1/audiobooks/parse` with chapter detection output.
**Deliverables**:
- Parse endpoint wired to ingestion + chapter detection (EPUB/PDF/TXT/MD).
- Support for SRT/VTT/ASS as text sources (timings ignored).
- Chapter candidate generation via `ebook_chapters` strategy.
**Success Criteria**:
- Returns normalized text and chapter list for all supported inputs.
- Handles custom chapter regex with existing safeguards.
**Tests**:
- Integration tests for EPUB and PDF parse.
- Unit tests for chapter selection logic.
**Status**: Complete

### Stage 2: Kokoro Alignment + Subtitle Generation (Core Engine)
**Goal**: Emit word-level alignment from Kokoro and generate subtitles.
**Deliverables**:
- Extend `kokoro_adapter.py` to return alignment metadata in `TTSResponse.metadata`.
- Subtitle generator module (SRT/VTT/ASS + variants/modes).
- Optional spaCy sentence splitting behind feature flag.
**Success Criteria**:
- Alignment metadata available for each generated chapter.
- Subtitles generated with monotonic timestamps and no overlaps.
**Tests**:
- Unit tests for alignment schema and subtitle generation invariants.
- Property-based tests for cue ordering and duration constraints.
**Status**: Complete

### Stage 3: Job Orchestration + Outputs
**Goal**: Create asynchronous audiobook jobs and persist artifacts.
**Deliverables**:
- New Jobs domain `audiobook` with staged job types.
- Output persistence to Collections outputs with metadata mapping.
- Artifacts endpoint returns download URLs.
**Success Criteria**:
- End-to-end job runs from parse -> TTS -> subtitles -> outputs.
- Job status exposes stage + per-chapter progress.
**Tests**:
- Integration test covering job create + poll + artifact retrieval.
**Status**: Complete

### Stage 4: Packaging + M4B
**Goal**: Support merged outputs and chaptered M4B packaging.
**Deliverables**:
- Extend `audio_converter.py` to package M4B.
- Embed chapter markers and title metadata.
**Success Criteria**:
- Merged audiobook files include correct chapter boundaries.
- M4B packaging failures surface as job failures when requested.
**Tests**:
- Unit tests for M4B packaging path and error failure.
**Status**: Complete

### Stage 5: Voice Profiles + Batch Queue Enhancements
**Goal**: Add voice profile API and batch processing overrides.
**Deliverables**:
- Voice profile CRUD endpoints.
- Batch job payload support with per-item overrides.
**Success Criteria**:
- Voice profiles applied correctly to chapter jobs.
- Batch queue processes multiple items with unique outputs.
**Tests**:
- Integration tests for profiles and batch queue behavior.
**Status**: Complete
